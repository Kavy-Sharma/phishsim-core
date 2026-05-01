from send_email import send_phishing_email
import os


print(
    "Testing Mailtrap SMTP "
    f"{os.getenv('MAILTRAP_HOST', 'sandbox.smtp.mailtrap.io')}:"
    f"{os.getenv('MAILTRAP_PORT', '2525')} "
    f"encryption={os.getenv('MAILTRAP_ENCRYPTION', 'none')}"
)


result = send_phishing_email(
    to_email="test@example.com",
    subject="Test Email from PhishSim",
    sender_name="PhishSim Test",
    body_html="<p>This is a Mailtrap SMTP test from PhishSim.</p><p><a href='TRACKING_LINK'>Test tracking link</a></p>",
    tracking_id="mailtrap-diagnostic"
)

if result["success"]:
    print("Email accepted by Mailtrap SMTP.")
else:
    print(f"Email failed: {result['error']}")
