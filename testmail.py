from send_email import send_phishing_email
import os
import sys


mode = sys.argv[1] if len(sys.argv) > 1 else os.getenv("EMAIL_MODE", "auto")

print(f"Testing PhishSim email delivery mode: {mode}")


result = send_phishing_email(
    to_email=os.getenv("TEST_EMAIL_TO", "test@example.com"),
    subject="Test Email from PhishSim",
    sender_name="PhishSim Test",
    body_html="<p>This is a PhishSim SMTP test.</p><p><a href='TRACKING_LINK'>Test tracking link</a></p>",
    tracking_id=f"{mode}-diagnostic",
    delivery_mode=mode,
)

if result["success"]:
    print("Email accepted by SMTP server.")
else:
    print(f"Email failed: {result['error']}")
