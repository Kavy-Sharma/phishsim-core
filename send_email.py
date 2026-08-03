# send_email.py
# ─────────────────────────────────────────────────────────────────────────────
# Email delivery module for PhishSim AI.
#
# Delivery priority (highest → lowest):
#   1. "brevo"    – Brevo HTTP REST API  (port 443 — always works on Render)
#   2. "resend"   – Resend HTTP API      (port 443, requires verified domain)
#   3. "mailtrap" – Mailtrap SMTP sandbox (port 2525, testing only)
#   4. "smtp"     – Raw SMTP relay       (only when BREVO_API_KEY is absent)
#   5. "local"    – smtp4dev / dev server
#
# KEY RULE: When BREVO_API_KEY is set, ALL real-send modes ("smtp", "brevo",
# "live", "") are automatically upgraded to Brevo HTTP API (port 443).
# Render blocks outbound port 587 — raw SMTP will ALWAYS time out there.
# ─────────────────────────────────────────────────────────────────────────────

import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()


# ─── Utilities ────────────────────────────────────────────────────────────────

def _clean(value, default=""):
    return (value if value is not None else default).strip()


def is_deployed_environment():
    DEPLOYMENT_ENV_VARS = (
        "RENDER", "RENDER_EXTERNAL_URL", "K_SERVICE",
        "DYNO", "WEBSITE_HOSTNAME", "VERCEL", "FLY_APP_NAME",
    )
    explicit = _clean(os.getenv("PHISHSIM_ENV") or os.getenv("APP_ENV")).lower()
    if explicit in ("production", "prod", "live", "deployed"):
        return True
    if explicit in ("development", "dev", "local"):
        return False
    return any(_clean(os.getenv(name)) for name in DEPLOYMENT_ENV_VARS)


# ─── Link-tracking helper ─────────────────────────────────────────────────────

def replace_all_links_with_tracking(body_html, tracking_url):
    """Replace TRACKING_LINK / PHISHING_LINK placeholders and all <a href=…> targets."""
    body_html = body_html.replace("TRACKING_LINK", tracking_url)
    body_html = body_html.replace("PHISHING_LINK", tracking_url)

    def _replacer(match):
        return f"{match.group(1)}{match.group(2)}{tracking_url}{match.group(2)}{match.group(4)}"

    body_html = re.sub(
        r'(<a\b[^>]*?\bhref\s*=\s*)(["\'"])(.*?)\2([^>]*?>)',
        _replacer,
        body_html,
        flags=re.IGNORECASE,
    )
    return body_html


# ─── Settings resolver ────────────────────────────────────────────────────────

def get_email_settings(delivery_mode=None, mailtrap_user_override=None, mailtrap_pass_override=None):
    """
    Returns a settings dict for the requested delivery mode.

    When BREVO_API_KEY is set, 'smtp' and 'live' modes are automatically
    upgraded to Brevo HTTP API — raw SMTP port 587 is blocked on Render.
    """
    explicit_mode = _clean(delivery_mode or os.getenv("EMAIL_MODE", "")).lower()

    # Normalize alias names
    if explicit_mode == "live":
        explicit_mode = "smtp"  # 'live' = real sending; see upgrade logic below

    # ── Brevo HTTP API — activated for 'brevo', 'smtp', or '' when key is set ──
    # Brevo uses port 443 (HTTPS). Render NEVER blocks port 443.
    # Raw SMTP port 587 is blocked on Render free tier → always prefer Brevo.
    use_brevo = explicit_mode == "brevo" or (
        explicit_mode in ("smtp", "") and _clean(os.getenv("BREVO_API_KEY"))
    )
    if use_brevo:
        print(f"[send_email] Routing '{explicit_mode}' via Brevo HTTP API (port 443).")
        return {
            "provider":   "brevo",
            "from_email": _clean(
                os.getenv("BREVO_FROM_EMAIL")
                or os.getenv("EMAIL_FROM")
                or "training@phishsim.ai"
            ),
        }

    # ── Mailtrap SMTP sandbox (port 2525 — not blocked by Render) ───────────
    if explicit_mode == "mailtrap":
        mt_user = _clean(mailtrap_user_override or os.getenv("MAILTRAP_USER"))
        mt_pass = _clean(mailtrap_pass_override or os.getenv("MAILTRAP_PASS"))
        return {
            "provider":   "smtp",
            "host":       "sandbox.smtp.mailtrap.io",
            "port":       2525,
            "user":       mt_user,
            "password":   mt_pass,
            "encryption": "starttls",
            "from_email": _clean(os.getenv("EMAIL_FROM", "training@phishsim.ai")),
        }

    # ── Resend HTTP API ───────────────────────────────────────────────────────
    if explicit_mode == "resend" or (
        is_deployed_environment()
        and explicit_mode not in ("smtp", "mailtrap", "brevo", "local")
        and _clean(os.getenv("RESEND_API_KEY"))
    ):
        return {
            "provider":   "resend",
            "from_email": _clean(os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")),
        }

    # ── Raw SMTP relay (only reached when BREVO_API_KEY is absent) ───────────
    if explicit_mode == "smtp":
        return {
            "provider":   "smtp",
            "host":       _clean(os.getenv("SMTP_HOST", "smtp-relay.brevo.com")),
            "port":       int(_clean(os.getenv("SMTP_PORT", "587"))),
            "user":       _clean(os.getenv("SMTP_USER")),
            "password":   _clean(os.getenv("SMTP_PASS")),
            "encryption": _clean(os.getenv("SMTP_ENCRYPTION", "starttls")),
            "from_email": _clean(
                os.getenv("SMTP_FROM_EMAIL")
                or os.getenv("EMAIL_FROM")
                or "training@phishsim.local"
            ),
        }

    # ── Local smtp4dev / development fallback ────────────────────────────────
    return {
        "provider":   "local",
        "host":       _clean(os.getenv("LOCAL_SMTP_HOST", "127.0.0.1")),
        "port":       int(_clean(os.getenv("LOCAL_SMTP_PORT", "1025"))),
        "user":       None,
        "password":   None,
        "from_email": _clean(os.getenv("EMAIL_FROM", "training@phishsim.local")),
    }


# ─── Brevo startup verification ───────────────────────────────────────────────

def verify_brevo_connection():
    """
    Pings Brevo /v3/account on startup to confirm the API key is valid.
    Printed to stdout → visible in Render logs on every deploy.
    """
    api_key = _clean(os.getenv("BREVO_API_KEY"))
    if not api_key:
        print("[EMAIL] BREVO_API_KEY not set — Brevo delivery unavailable.")
        return False
    try:
        resp = requests.get(
            "https://api.brevo.com/v3/account",
            headers={"api-key": api_key},
            timeout=8,
        )
        if resp.ok:
            acct = resp.json()
            email = acct.get("email", "(unknown)")
            plan  = acct.get("plan", [{}])[0].get("type", "unknown") if acct.get("plan") else "unknown"
            print(f"[EMAIL] Brevo OK — account: {email} | plan: {plan}")
            # Warn if the configured from_email looks unverified
            from_email = _clean(
                os.getenv("BREVO_FROM_EMAIL") or os.getenv("EMAIL_FROM") or ""
            )
            if not from_email or from_email in ("training@phishsim.ai", "training@phishsim.local"):
                print(
                    "[EMAIL] WARNING: BREVO_FROM_EMAIL is not set or is the default placeholder. "
                    "Emails will be accepted by Brevo but silently discarded — they will NEVER arrive. "
                    "Action: Brevo dashboard > Settings > Senders & IPs > add your email, verify it, "
                    "then set BREVO_FROM_EMAIL=that-email on Render."
                )
            else:
                print(f"[EMAIL] Brevo will send FROM: {from_email}")
            return True
        print(f"[EMAIL] Brevo key invalid — {resp.status_code}: {resp.text[:120]}")
        return False
    except Exception as exc:
        print(f"[EMAIL] Brevo connection check failed: {exc}")
        return False


# Run once at import — Render logs show status immediately on every boot.
verify_brevo_connection()


# ─── Main public send function ────────────────────────────────────────────────

def send_phishing_email(
    to_email, subject, sender_name, body_html, tracking_id,
    delivery_mode=None, mailtrap_user=None, mailtrap_pass=None, reply_to=None,
):
    """
    Send one phishing simulation email.
    Delivery provider is resolved by get_email_settings().
    """
    raw_base = os.getenv("APP_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://127.0.0.1:5050"
    base_url = _clean(raw_base).rstrip("/")
    tracking_url = f"{base_url}/click/{tracking_id}"
    pixel_url    = f"{base_url}/pixel/{tracking_id}.png"
    report_url   = f"{base_url}/report/{tracking_id}"

    # Inject report button + open-tracking pixel (skipped if already present)
    if "Report Suspicious Email" not in body_html:
        body_html = replace_all_links_with_tracking(body_html, tracking_url)
        body_html += f"""
    <br><br>
    <div style="font-family:Arial,sans-serif;text-align:center;margin-top:30px;
                padding:20px;border-top:1px solid #e0e0e0;background:#f9f9f9;border-radius:8px;">
        <p style="font-size:13px;color:#555;margin-bottom:12px;">
            If you suspect this email is a phishing attempt, please report it immediately.</p>
        <a href="{report_url}"
           style="background:#dc3545;color:#fff;padding:10px 20px;text-decoration:none;
                  border-radius:4px;font-weight:bold;font-size:14px;display:inline-block;">
            Report Suspicious Email</a>
    </div>"""
        body_html += f'\n<img src="{pixel_url}" width="1" height="1" style="display:none;" />'

    settings = get_email_settings(
        delivery_mode,
        mailtrap_user_override=mailtrap_user,
        mailtrap_pass_override=mailtrap_pass,
    )

    if settings["provider"] == "brevo":
        return _send_via_brevo(
            to_email=to_email,
            subject=subject,
            sender_name=sender_name,
            from_email=settings["from_email"],
            body_html=body_html,
            reply_to=reply_to,
            tracking_id=tracking_id,
        )

    if settings["provider"] == "resend":
        return _send_via_resend(
            to_email=to_email,
            subject=subject,
            sender_name=sender_name,
            from_email=settings["from_email"],
            body_html=body_html,
            reply_to=reply_to,
        )

    # SMTP path (Mailtrap sandbox, local dev, or raw relay as last resort)
    return _send_via_smtp(
        to_email=to_email,
        subject=subject,
        sender_name=sender_name,
        body_html=body_html,
        settings=settings,
        reply_to=reply_to,
    )


def send_plain_email(
    to_email, subject, body_html,
    delivery_mode=None, mailtrap_user=None, mailtrap_pass=None, reply_to=None,
):
    """
    Send one plain email (e.g. exposure scan report) without injecting tracking pixels or report buttons.
    """
    settings = get_email_settings(
        delivery_mode,
        mailtrap_user_override=mailtrap_user,
        mailtrap_pass_override=mailtrap_pass,
    )
    
    sender_name = "PhishSim AI Exposure Shield"

    if settings["provider"] == "brevo":
        return _send_via_brevo(
            to_email=to_email,
            subject=subject,
            sender_name=sender_name,
            from_email=settings["from_email"],
            body_html=body_html,
            reply_to=reply_to,
            tracking_id="exposure-scan",
        )

    if settings["provider"] == "resend":
        return _send_via_resend(
            to_email=to_email,
            subject=subject,
            sender_name=sender_name,
            from_email=settings["from_email"],
            body_html=body_html,
            reply_to=reply_to,
        )

    # smtp/local providers
    return _send_via_smtp(
        to_email=to_email,
        subject=subject,
        sender_name=sender_name,
        body_html=body_html,
        settings=settings,
        reply_to=reply_to,
    )


# ─── Provider implementations ─────────────────────────────────────────────────

def _send_via_brevo(to_email, subject, sender_name, from_email, body_html, reply_to, tracking_id):
    """
    Send via Brevo Transactional Email REST API.
    Uses HTTPS port 443 — never blocked by Render or any other cloud host.
    """
    api_key = _clean(os.getenv("BREVO_API_KEY"))
    if not api_key:
        return {"success": False, "error": "BREVO_API_KEY is not set."}

    # Early warning: unverified from_email → Brevo accepts but Gmail discards
    if not from_email or from_email in ("training@phishsim.ai", "training@phishsim.local"):
        print(
            f"[BREVO] WARNING: from_email='{from_email}' is the unverified default. "
            "Brevo will accept the send request and return a messageId, but Gmail WILL silently "
            "discard the email because SPF/DKIM will fail for this domain. "
            "Fix: Set BREVO_FROM_EMAIL=<your-verified-sender> on Render."
        )

    print(f"[BREVO] Sending  from='{from_email}'  to='{to_email}'  subject='{subject[:60]}'")

    payload = {
        "sender":      {"name": sender_name, "email": from_email},
        "to":          [{"email": to_email}],
        "subject":     subject,
        "htmlContent": body_html,
        "tags":        ["phishsim-campaign"],   # appears in Brevo > Transactional > Logs
        "headers": {
            "X-Campaign-ID":    str(tracking_id),
            "List-Unsubscribe": f"<mailto:{from_email}?subject=unsubscribe>",
        },
    }
    if reply_to:
        payload["replyTo"] = {"email": reply_to}

    try:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept":       "application/json",
                "api-key":      api_key,
                "content-type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if resp.ok:
            result = resp.json()
            msg_id = result.get("messageId", "?")
            print(f"[BREVO] Accepted  to='{to_email}'  messageId='{msg_id}'")
            return {"success": True, "error": None}
        error_text = resp.text[:500]
        print(f"[BREVO] ERROR {resp.status_code} for '{to_email}': {error_text}")
        return {"success": False, "error": f"Brevo {resp.status_code}: {error_text}"}
    except Exception as exc:
        print(f"[BREVO] Exception for '{to_email}': {exc}")
        return {"success": False, "error": str(exc)}


def _send_via_resend(to_email, subject, sender_name, from_email, body_html, reply_to):
    """Send via Resend HTTP API."""
    api_key = _clean(os.getenv("RESEND_API_KEY"))
    if not api_key:
        return {"success": False, "error": "RESEND_API_KEY missing from environment."}

    payload = {
        "from":    f'"{sender_name}" <{from_email}>',
        "to":      [to_email],
        "subject": subject,
        "html":    body_html,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=12,
        )
        if resp.status_code in (200, 201):
            print(f"[RESEND] Sent to '{to_email}'")
            return {"success": True, "error": None}
        error_text = resp.text[:300]
        print(f"[RESEND] Error {resp.status_code} for '{to_email}': {error_text}")
        return {"success": False, "error": error_text}
    except Exception as exc:
        print(f"[RESEND] Exception for '{to_email}': {exc}")
        return {"success": False, "error": str(exc)}


def _send_via_smtp(to_email, subject, sender_name, body_html, settings, reply_to):
    """
    Send via raw SMTP.
    Used for: Mailtrap sandbox (port 2525) and local dev (port 1025).
    NOT used when BREVO_API_KEY is set — Brevo HTTP API takes priority.
    """
    import smtplib
    import ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["Subject"]        = subject
    msg["From"]           = f'"{sender_name}" <{settings["from_email"]}>'
    msg["To"]             = to_email
    msg["List-Unsubscribe"] = f'<mailto:{settings["from_email"]}?subject=unsubscribe>'
    msg["X-Mailer"]       = "PhishSim AI Security Platform"
    msg["Precedence"]     = "bulk"
    if reply_to:
        msg["Reply-To"]   = reply_to
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(settings["host"], settings["port"], timeout=10) as server:
            server.sock.settimeout(15)
            if settings.get("encryption") == "starttls":
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                server.starttls(context=ctx)
            if settings.get("user") and settings.get("password"):
                server.login(settings["user"], settings["password"])
            server.send_message(msg)
            print(f"[SMTP] Sent to '{to_email}' via {settings['host']}:{settings['port']}")
            return {"success": True, "error": None}
    except Exception as exc:
        print(f"[SMTP] Failed for '{to_email}': {exc}")
        return {"success": False, "error": str(exc)}
