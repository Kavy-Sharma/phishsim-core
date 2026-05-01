import smtplib
import os
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

def smtp_login(server, user, password):
    """Uses AUTH LOGIN so Mailtrap's exact authentication/quota error is preserved."""
    code, response = server.docmd("AUTH", "LOGIN")
    if code != 334:
        raise smtplib.SMTPAuthenticationError(code, response)

    code, response = server.docmd(base64.b64encode(user.encode()).decode())
    if code != 334:
        raise smtplib.SMTPAuthenticationError(code, response)

    code, response = server.docmd(base64.b64encode(password.encode()).decode())
    if code != 235:
        raise smtplib.SMTPAuthenticationError(code, response)

def get_email_settings(delivery_mode=None):
    """Builds SMTP settings from .env without tying the app to one provider."""
    provider = (delivery_mode or os.getenv("EMAIL_PROVIDER", os.getenv("EMAIL_MODE", "mailtrap"))).strip().lower()

    if provider == "local":
        return {
            "provider": provider,
            "host": os.getenv("LOCAL_SMTP_HOST", "127.0.0.1"),
            "port": int(os.getenv("LOCAL_SMTP_PORT", "1025")),
            "user": None,
            "password": None,
            "encryption": "none",
            "from_email": os.getenv("EMAIL_FROM", "training@phishsim.local"),
        }

    if provider == "smtp":
        return {
            "provider": provider,
            "host": os.getenv("SMTP_HOST", ""),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "user": os.getenv("SMTP_USER"),
            "password": os.getenv("SMTP_PASS"),
            "encryption": os.getenv("SMTP_ENCRYPTION", "starttls").strip().lower(),
            "from_email": os.getenv("EMAIL_FROM", "security-training@example.com"),
        }

    return {
        "provider": "mailtrap",
        "host": os.getenv("MAILTRAP_HOST", "sandbox.smtp.mailtrap.io"),
        "port": int(os.getenv("MAILTRAP_PORT", "2525")),
        "user": os.getenv("MAILTRAP_USER"),
        "password": os.getenv("MAILTRAP_PASS"),
        "encryption": os.getenv("MAILTRAP_ENCRYPTION", "none").strip().lower(),
        "from_email": os.getenv("EMAIL_FROM", "noreply@phishsim-ai.com"),
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
    
    if settings["provider"] in ("mailtrap", "smtp") and (not settings["user"] or not settings["password"]):
        error = f"{settings['provider'].upper()} credentials missing from .env file."
        print(f"Error: {error}")
        return {"success": False, "error": error}
        
    try:
        smtp_class = smtplib.SMTP_SSL if settings["encryption"] == "ssl" else smtplib.SMTP
        with smtp_class(settings["host"], settings["port"], timeout=30) as server:
            if settings["encryption"] == "starttls":
                server.starttls()
            if settings["user"] and settings["password"]:
                smtp_login(server, settings["user"], settings["password"])
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
