# send_email.py
# ─────────────────────────────────────────────────────────────────────────────
# Email delivery module for PhishSim AI.
#
# Delivery priority (highest → lowest):
#   1. "brevo"   – Brevo HTTP REST API  (port 443, works on Render free tier)
#   2. "resend"  – Resend HTTP API      (port 443, requires verified domain)
#   3. "mailtrap"– Mailtrap SMTP sandbox (port 2525, safe-send / testing)
#   4. "smtp"    – Raw SMTP (Brevo relay / Gmail / corporate)
#   5. "local"   – smtp4dev / local dev server
#
# On Render free tier, prefer "brevo" — outbound port 587 is blocked for
# services that look like bulk mailers; port 443 (HTTPS) is never blocked.
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
    """Replace TRACKING_LINK placeholder and all <a href=…> targets."""
    body_html = body_html.replace("TRACKING_LINK", tracking_url)
    body_html = body_html.replace("PHISHING_LINK", tracking_url)  # DeepSeek variant

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
    Kept for backward-compatibility with app.py checks.

    Priority:
      1. explicit delivery_mode argument (from campaign)
      2. EMAIL_MODE env var
      3. Auto-detect: BREVO_API_KEY set → brevo
                      RESEND_API_KEY set → resend
                      else → local
    """
    explicit_mode = _clean(delivery_mode or os.getenv("EMAIL_MODE", "")).lower()

    # Normalize legacy/alias mode names
    if explicit_mode == "live":
        explicit_mode = "smtp"   # 'live' means real sending; resolved below

    # --- Brevo HTTP API (primary for Render — uses port 443, never blocked) ---
    # Activates when:
    #   a) explicit_mode is 'brevo', OR
    #   b) explicit_mode is 'smtp' / '' AND BREVO_API_KEY env var is set
    #      (Brevo is strictly better than raw SMTP on any cloud platform)
    use_brevo = (
        explicit_mode == "brevo"
        or (
            explicit_mode in ("smtp", "")
            and _clean(os.getenv("BREVO_API_KEY"))
        )
    )
    if use_brevo:
        print(f"[email_gen] Routing '{explicit_mode}' delivery via Brevo HTTP API.")
        return {
            "provider": "brevo",
            "from_email": _clean(
                os.getenv("BREVO_FROM_EMAIL")
                or os.getenv("EMAIL_FROM")
                or "training@phishsim.ai"
            ),
        }

    # --- Mailtrap SMTP sandbox (port 2525 — not blocked by Render) ---
    if explicit_mode == "mailtrap":
        mt_user = _clean(os.getenv("MAILTRAP_USER"))
        mt_pass = _clean(os.getenv("MAILTRAP_PASS"))
        if mailtrap_user_override:
            mt_user = mailtrap_user_override
        if mailtrap_pass_override:
            mt_pass = mailtrap_pass_override
        return {
            "provider": "smtp",
            "host": "sandbox.smtp.mailtrap.io",
            "port": 2525,
            "user": mt_user,
            "password": mt_pass,
            "encryption": "starttls",
            "from_email": _clean(os.getenv("EMAIL_FROM", "training@phishsim.ai")),
        }

    # --- Resend HTTP API ---
    if explicit_mode == "resend" or (
        is_deployed_environment()
        and explicit_mode not in ("smtp", "mailtrap", "brevo", "local")
        and _clean(os.getenv("RESEND_API_KEY"))
    ):
        return {
            "provider": "resend",
            "from_email": _clean(os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")),
        }

    # --- Brevo SMTP relay (port 587) ---
    if explicit_mode == "smtp":
        return {
            "provider": "smtp",
            "host": _clean(os.getenv("SMTP_HOST", "smtp-relay.brevo.com")),
            "port": int(_clean(os.getenv("SMTP_PORT", "587"))),
            "user": _clean(os.getenv("SMTP_USER")),
            "password": _clean(os.getenv("SMTP_PASS")),
            "encryption": _clean(os.getenv("SMTP_ENCRYPTION", "starttls")),
            "from_email": _clean(
                os.getenv("SMTP_FROM_EMAIL")
                or os.getenv("EMAIL_FROM")
                or "training@phishsim.local"
            ),
        }

    # --- Local smtp4dev / development fallback ---
    return {
        "provider": "local",
        "host": _clean(os.getenv("LOCAL_SMTP_HOST", "127.0.0.1")),
        "port": int(_clean(os.getenv("LOCAL_SMTP_PORT", "1025"))),
        "user": None,
        "password": None,
        "from_email": _clean(os.getenv("EMAIL_FROM", "training@phishsim.local")),
    }


# ─── Brevo startup verification (called once at import time) ──────────────────

def verify_brevo_connection():
    """
    Pings the Brevo account endpoint to confirm the API key is valid.
    Logs result to stdout — visible in Render / Heroku logs on every deploy.
    """
    api_key = _clean(os.getenv("BREVO_API_KEY"))
    if not api_key:
        print("[EMAIL] BREVO_API_KEY not set — Brevo delivery will be unavailable.")
        return False
    try:
        resp = requests.get(
            "https://api.brevo.com/v3/account",
            headers={"api-key": api_key},
            timeout=8,
        )
        if resp.ok:
            acct = resp.json()
            print(f"[EMAIL] Brevo connected — account: {acct.get('email', '(unknown)')}")
            return True
        print(f"[EMAIL] Brevo API key invalid — status {resp.status_code}: {resp.text[:120]}")
        return False
    except Exception as exc:
        print(f"[EMAIL] Brevo connection check failed: {exc}")
        return False


# Run once at import time so Render logs show status immediately.
verify_brevo_connection()


# ─── Main send function ───────────────────────────────────────────────────────

def send_phishing_email(
    to_email, subject, sender_name, body_html, tracking_id,
    delivery_mode=None, mailtrap_user=None, mailtrap_pass=None, reply_to=None,
):
    """
    Sends one phishing simulation email.

    Delivery path is resolved in this order:
      brevo → resend → mailtrap/smtp → local
    """
    base_url    = _clean(os.getenv("APP_BASE_URL", "http://127.0.0.1:5050"), "/")
    tracking_url = f"{base_url}/click/{tracking_id}"
    pixel_url    = f"{base_url}/pixel/{tracking_id}.png"
    report_url   = f"{base_url}/report/{tracking_id}"

    # Inject report button + tracking pixel if not already present
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

    # ── Brevo HTTP API ────────────────────────────────────────────────────────
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

    # ── Resend HTTP API ───────────────────────────────────────────────────────
    if settings["provider"] == "resend":
        return _send_via_resend(
            to_email=to_email,
            subject=subject,
            sender_name=sender_name,
            from_email=settings["from_email"],
            body_html=body_html,
            reply_to=reply_to,
        )

    # ── SMTP (Mailtrap sandbox / Brevo relay / local) ─────────────────────────
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
    """Send via Brevo REST API — uses HTTPS port 443, never blocked by Render."""
    api_key = _clean(os.getenv("BREVO_API_KEY"))
    if not api_key:
        return {"success": False, "error": "BREVO_API_KEY is not set in environment."}

    payload = {
        "sender":      {"name": sender_name, "email": from_email},
        "to":          [{"email": to_email}],
        "subject":     subject,
        "htmlContent": body_html,
        "headers": {
            "X-Campaign-ID":   str(tracking_id),
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
            print(f"[BREVO] Sent to {to_email} — messageId: {result.get('messageId', '?')}")
            return {"success": True, "error": None}
        error_text = resp.text[:300]
        print(f"[BREVO] Error {resp.status_code} for {to_email}: {error_text}")
        return {"success": False, "error": f"Brevo {resp.status_code}: {error_text}"}
    except Exception as exc:
        print(f"[BREVO] Exception for {to_email}: {exc}")
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
            print(f"[RESEND] Sent to {to_email}")
            return {"success": True, "error": None}
        error_text = resp.text[:300]
        print(f"[RESEND] Error {resp.status_code} for {to_email}: {error_text}")
        return {"success": False, "error": error_text}
    except Exception as exc:
        print(f"[RESEND] Exception for {to_email}: {exc}")
        return {"success": False, "error": str(exc)}


def _send_via_smtp(to_email, subject, sender_name, body_html, settings, reply_to):
    """Send via raw SMTP (Mailtrap sandbox, Brevo SMTP relay, or local dev)."""
    import smtplib
    import ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f'"{sender_name}" <{settings["from_email"]}>'
    msg["To"]      = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    msg["List-Unsubscribe"] = f'<mailto:{settings["from_email"]}?subject=unsubscribe>'
    msg["X-Mailer"]  = "PhishSim AI Security Platform"
    msg["Precedence"] = "bulk"
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
            print(f"[SMTP] Sent to {to_email} via {settings['host']}:{settings['port']}")
            return {"success": True, "error": None}
    except Exception as exc:
        print(f"[SMTP] Failed for {to_email}: {exc}")
        return {"success": False, "error": str(exc)}
