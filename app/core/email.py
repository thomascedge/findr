import os
from app.core.s3 import ses_client

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
FRONTEND_URL = os.getenv("FRONTEND_URL")


def send_verification_email(email: str, token: str, username: str):
    ses_client.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [email]},
        Message={
            "Subject": {"Data": "Verify your Findr email"},
            "Body": {
                "Text": {
                    "Data": f"Hi {username},\nClick the link below to verify your email:\n{FRONTEND_URL}/verify-email?token={token}\nThis link expires in 24 hours."
                }
            },
        },
    )


def send_password_reset_email(email: str, token: str):
    ses_client.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [email]},
        Message={
            "Subject": {"Data": "Reset your Findr password"},
            "Body": {
                "Text": {
                    "Data": f"Click the link below to change your password:\n{FRONTEND_URL}/change-password?token={token}\nThis link expires in 1 hour.\n If you did not request a password change, click this link {FRONTEND_URL}/report."
                }
            },
        },
    )
