import os
import requests
from dotenv import load_dotenv

load_dotenv()

LOCAL_PROVIDERS = {"local", "smtp4dev", "sandbox"}

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

def get_email_settings(delivery_mode=None):
    """Returns settings dict — kept for compatibility with app.py checks.

    Priority:
      1. explicit delivery_mode argument (from campaign)
      2. EMAIL_MODE env var
      3. Auto-detect: deployed → mailtrap (if configured) or resend
    """
    explicit_mode = _clean(delivery_mode or os.getenv("EMAIL_MODE", "")).lower()

    # --- Mailtrap sandbox (works on Render: port 2525 is NOT blocked) ---
    if explicit_mode == "mailtrap":
        return {
            "provider": "smtp",
            "host": "sandbox.smtp.mailtrap.io",
            "port": 2525,
            "user": _clean(os.getenv("MAILTRAP_USER")),
            "password": _clean(os.getenv("MAILTRAP_PASS")),
            "encryption": "starttls",
            "from_email": _clean(os.getenv("EMAIL_FROM", "training@phishsim.ai")),
        }

    # --- Resend HTTP API (requires a verified custom domain for real inboxes) ---
    if explicit_mode == "resend" or (
        is_deployed_environment()
        and explicit_mode not in ("smtp", "mailtrap", "local")
        and _clean(os.getenv("RESEND_API_KEY"))
    ):
        return {
            "provider": "resend",
            "host": "api.resend.com",
            "port": 443,
            "user": "resend",
            "password": _clean(os.getenv("RESEND_API_KEY")),
            "encryption": "https",
            "from_email": _clean(os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")),
        }

    # --- Real Gmail / corporate SMTP ---
    if explicit_mode == "smtp":
        return {
            "provider": "smtp",
            "host": _clean(os.getenv("SMTP_HOST")),
            "port": int(_clean(os.getenv("SMTP_PORT", "587"))),
            "user": _clean(os.getenv("SMTP_USER")),
            "password": _clean(os.getenv("SMTP_PASS")),
            "encryption": _clean(os.getenv("SMTP_ENCRYPTION", "starttls")),
            "from_email": _clean(os.getenv("SMTP_FROM_EMAIL", os.getenv("EMAIL_FROM", "training@phishsim.local"))),
        }

    # --- Local smtp4dev / default ---
    return {
        "provider": "local",
        "host": _clean(os.getenv("LOCAL_SMTP_HOST", "127.0.0.1")),
        "port": int(_clean(os.getenv("LOCAL_SMTP_PORT", "1025"))),
        "user": None,
        "password": None,
        "from_email": _clean(os.getenv("EMAIL_FROM"), "training@phishsim.local"),
    }


def send_phishing_email(to_email, subject, sender_name, body_html, tracking_id, delivery_mode=None):
    """Sends one phishing simulation email."""

    base_url = _clean(os.getenv("APP_BASE_URL", "http://127.0.0.1:5000"), "/")
    tracking_url = f"{base_url}/click/{tracking_id}"
    pixel_url    = f"{base_url}/pixel/{tracking_id}.png"
    report_url   = f"{base_url}/report/{tracking_id}"

    body_html = body_html.replace("TRACKING_LINK", tracking_url)

    report_button_html = f"""
    <br><br>
    <div style="font-family:Arial,sans-serif;text-align:center;margin-top:30px;padding:20px;
                border-top:1px solid #e0e0e0;background-color:#f9f9f9;border-radius:8px;">
        <p style="font-size:13px;color:#555;margin-bottom:12px;">
            If you suspect this email is a phishing attempt, please report it immediately.</p>
        <a href="{report_url}"
           style="background-color:#dc3545;color:white;padding:10px 20px;text-decoration:none;
                  border-radius:4px;font-weight:bold;font-size:14px;display:inline-block;">
            Report Suspicious Email</a>
    </div>
    """
    body_html += report_button_html
    body_html += f'\n<img src="{pixel_url}" width="1" height="1" style="display:none;" />'

    settings = get_email_settings(delivery_mode)

    if settings["provider"] == "resend":
        api_key = _clean(os.getenv("RESEND_API_KEY"))
        if not api_key:
            return {"success": False, "error": "RESEND_API_KEY missing from environment."}

        payload = {
            "from": f"{sender_name} <{settings['from_email']}>",
            "to": [to_email],
            "subject": subject,
            "html": body_html,
        }
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10,
            )
            if response.status_code in (200, 201):
                print(f"Resend: sent to {to_email}")
                return {"success": True, "error": None}
            else:
                error = response.text
                print(f"Resend error for {to_email}: {error}")
                return {"success": False, "error": error}
        except Exception as e:
            print(f"Resend exception for {to_email}: {e}")
            return {"success": False, "error": str(e)}

    # SMTP delivery path (local or explicit smtp mode)
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{sender_name} <{settings['from_email']}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(settings["host"], settings["port"], timeout=6) as server:
            if settings["encryption"] == "starttls":
                server.starttls()
            if settings["user"] and settings["password"]:
                server.login(settings["user"], settings["password"])
            server.send_message(msg)
            print(f"SMTP: sent to {to_email} using {settings['host']}:{settings['port']}")
            return {"success": True, "error": None}
    except Exception as e:
        print(f"SMTP failed for {to_email}: {e}")
        return {"success": False, "error": str(e)}
