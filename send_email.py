import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

def send_phishing_email(to_email, subject, sender_name, body_html, tracking_id):
    """Sends one phishing simulation email via Mailtrap."""
    
    # Replace placeholder with real tracking link
    # Using localhost for now since we're testing locally
    tracking_url = f"http://127.0.0.1:5000/click/{tracking_id}"
    pixel_url = f"http://127.0.0.1:5000/pixel/{tracking_id}.png"
    report_url = f"http://127.0.0.1:5000/report/{tracking_id}"
    
    body_html = body_html.replace("TRACKING_LINK", tracking_url)
    
    # Add a professional "Report Suspicious Email" button
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
    # You can set a more realistic sender email domain later 
    msg["From"] = f"{sender_name} <noreply@phishsim-ai.com>"
    msg["To"] = to_email
    
    msg.attach(MIMEText(body_html, "html"))
    
    # Connect to Mailtrap
    user = os.getenv("MAILTRAP_USER")
    password = os.getenv("MAILTRAP_PASS")
    
    if not user or not password:
        print("Error: Mailtrap credentials missing from .env file.")
        return
        
    try:
        with smtplib.SMTP("sandbox.smtp.mailtrap.io", 2525) as server:
            server.login(user, password)
            server.send_message(msg)
            print(f"Successfully sent simulation email to {to_email}")
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
