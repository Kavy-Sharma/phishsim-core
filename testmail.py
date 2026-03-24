import smtplib
import os
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

user = os.getenv("MAILTRAP_USER")
password = os.getenv("MAILTRAP_PASS")

msg = MIMEMultipart()
msg["Subject"] = "Test Email from PhishSim"
msg["From"] = "test@phishsim.com"
msg["To"] = "test@example.com"

body = "This is your first test email 🚀"
msg.attach(MIMEText(body, "plain"))

with smtplib.SMTP("sandbox.smtp.mailtrap.io", 2525) as server:
    server.login(user, password)
    server.send_message(msg)

print("Email sent successfully!")