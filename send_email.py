import smtplib
import os
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()


LOCAL_PROVIDERS = {"local", "smtp4dev", "sandbox"}
SMTP_PROVIDERS = {"smtp", "gmail", "live", "production", "prod"}
DEPLOYMENT_ENV_VARS = (
    "RENDER",
    "RENDER_EXTERNAL_URL",
    "K_SERVICE",
    "DYNO",
    "WEBSITE_HOSTNAME",
    "VERCEL",
    "FLY_APP_NAME",
)


def _clean(value, default=""):
    return (value if value is not None else default).strip()


def _is_truthy(value):
    return _clean(value).lower() in ("1", "true", "yes", "on")


def is_deployed_environment():
    """Best-effort check for hosted environments where smtp4dev is unavailable."""
    explicit = _clean(os.getenv("PHISHSIM_ENV") or os.getenv("APP_ENV")).lower()
    if explicit in ("production", "prod", "live", "deployed"):
        return True
    if explicit in ("development", "dev", "local"):
        return False
    return any(_clean(os.getenv(name)) for name in DEPLOYMENT_ENV_VARS)


def resolve_email_provider(delivery_mode=None):
    """Resolves explicit or auto delivery mode to a concrete SMTP provider."""
    requested = _clean(
        delivery_mode or os.getenv("EMAIL_PROVIDER") or os.getenv("EMAIL_MODE") or "auto"
    ).lower()

    if requested in LOCAL_PROVIDERS:
        return "local"
    if requested in SMTP_PROVIDERS:
        return "smtp"
    if requested == "mailtrap":
        return "mailtrap"
    if requested in ("auto", ""):
        return "smtp" if is_deployed_environment() else "local"

    return requested


def _smtp_password():
    password = os.getenv("SMTP_PASS")
    host = _clean(os.getenv("SMTP_HOST", ""))
    if password and "gmail" in host.lower() and _is_truthy(os.getenv("SMTP_STRIP_PASSWORD_SPACES", "true")):
        return password.replace(" ", "")
    return password


def get_email_settings(delivery_mode=None):
    """Builds SMTP settings from .env without tying the app to one provider."""
    provider = resolve_email_provider(delivery_mode)

    if provider == "local":
        return {
            "provider": provider,
            "host": _clean(os.getenv("LOCAL_SMTP_HOST", "127.0.0.1")),
            "port": int(_clean(os.getenv("LOCAL_SMTP_PORT", "1025"))),
            "user": None,
            "password": None,
            "encryption": "none",
            "from_email": _clean(os.getenv("LOCAL_EMAIL_FROM") or os.getenv("EMAIL_FROM"), "training@phishsim.local"),
        }

    if provider == "smtp":
        smtp_user = _clean(os.getenv("SMTP_USER"))
        host = _clean(os.getenv("SMTP_HOST") or ("smtp.gmail.com" if smtp_user else ""))
        return {
            "provider": provider,
            "host": host,
            "port": int(_clean(os.getenv("SMTP_PORT", "587"))),
            "user": smtp_user,
            "password": _smtp_password(),
            "encryption": _clean(os.getenv("SMTP_ENCRYPTION", "starttls")).lower(),
            "from_email": _clean(os.getenv("SMTP_FROM_EMAIL") or os.getenv("SMTP_USER") or os.getenv("EMAIL_FROM"), "security-training@example.com"),
        }

    return {
        "provider": "mailtrap",
        "host": _clean(os.getenv("MAILTRAP_HOST", "sandbox.smtp.mailtrap.io")),
        "port": int(_clean(os.getenv("MAILTRAP_PORT", "2525"))),
        "user": _clean(os.getenv("MAILTRAP_USER")),
        "password": os.getenv("MAILTRAP_PASS"),
        "encryption": _clean(os.getenv("MAILTRAP_ENCRYPTION", "none")).lower(),
        "from_email": _clean(os.getenv("MAILTRAP_FROM_EMAIL") or os.getenv("EMAIL_FROM"), "noreply@phishsim-ai.com"),
    }


def send_phishing_email(to_email, subject, sender_name, body_html, tracking_id, delivery_mode=None):
    """Sends one authorized phishing simulation email through the configured SMTP provider."""
    
    # Replace placeholder with real tracking link
    base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
    tracking_url = f"{base_url}/click/{tracking_id}"
    pixel_url = f"{base_url}/pixel/{tracking_id}.png"
    report_url = f"{base_url}/report/{tracking_id}"
    
    body_html = body_html.replace("TRACKING_LINK", tracking_url)
    
    # Add a professional "Report Suspicious Email" button.
    report_button_html = f"""
    <br><br>
    <div style="font-family: Arial, sans-serif; text-align: center; margin-top: 30px; padding: 20px; border-top: 1px solid #e0e0e0; background-color: #f9f9f9; border-radius: 8px;">
        <p style="font-size: 13px; color: #555; margin-bottom: 12px;">If you suspect this email is a phishing attempt, please report it immediately.</p>
        <a href="{report_url}" style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 14px; display: inline-block;">Report Suspicious Email</a>
    </div>
    """
    body_html += report_button_html
    
    # Add invisible tracking pixel at the end of the email
    body_html += f'\n<img src="{pixel_url}" width="1" height="1" style="display:none;" />'
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    settings = get_email_settings(delivery_mode)
    msg["From"] = f"{sender_name} <{settings['from_email']}>"
    msg["To"] = to_email
    
    msg.attach(MIMEText(body_html, "html"))


    if not settings["host"]:
        error = f"{settings['provider'].upper()} host missing from .env file."
        print(f"Error: {error}")
        return {"success": False, "error": error}
    
    if settings["provider"] in ("mailtrap", "smtp") and (not settings["user"] or not settings["password"]):
        error = f"{settings['provider'].upper()} credentials missing from .env file."
        print(f"Error: {error}")
        return {"success": False, "error": error}
        
    try:
        smtp_class = smtplib.SMTP_SSL if settings["encryption"] == "ssl" else smtplib.SMTP
        timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS", "6"))
        with smtp_class(settings["host"], settings["port"], timeout=timeout) as server:
            if settings["encryption"] == "starttls":
                server.ehlo()
                server.starttls()
                server.ehlo()
            if settings["user"] and settings["password"]:
                server.login(settings["user"], settings["password"])
            server.send_message(msg)
            print(f"Successfully sent simulation email to {to_email} via {settings['provider']}")
            return {"success": True, "error": None}
    except Exception as e:
        if isinstance(e, smtplib.SMTPAuthenticationError):
            smtp_error = e.smtp_error.decode(errors="replace") if isinstance(e.smtp_error, bytes) else str(e.smtp_error)
            error = f"{e.smtp_code} {smtp_error}"
        else:
            error = str(e)
        print(f"Failed to send email to {to_email}: {error}")
        return {"success": False, "error": error}
