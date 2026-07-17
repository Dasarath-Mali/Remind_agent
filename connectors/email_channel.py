"""
Email channel (outbound). Sends reminders via SMTP over SSL.
For Gmail: enable 2FA, then create an "App Password" to use here
instead of your real password.
"""
import smtplib
from email.mime.text import MIMEText

from config import Config


def send(message: str, subject: str = "Reminder") -> bool:
    if not (Config.EMAIL_USER and Config.EMAIL_PASS and Config.EMAIL_TO):
        return False

    msg = MIMEText(message)
    msg["Subject"] = subject
    msg["From"] = Config.EMAIL_USER
    msg["To"] = Config.EMAIL_TO

    try:
        with smtplib.SMTP_SSL(Config.EMAIL_SMTP_HOST, Config.EMAIL_SMTP_PORT) as server:
            server.login(Config.EMAIL_USER, Config.EMAIL_PASS)
            server.sendmail(Config.EMAIL_USER, [Config.EMAIL_TO], msg.as_string())
        return True
    except Exception as e:
        print(f"[email] send failed: {e}")
        return False
