"""
Central configuration for the agent.
Everything is read from environment variables (via a local .env file)
so no secrets ever live in code.
"""
import os
import platform
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _int_list(name: str, default: str) -> list[int]:
    raw = os.getenv(name, default)
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


class Config:
    # --- runtime / OS ---
    OS_NAME = platform.system()  # 'Windows', 'Darwin', 'Linux'

    # --- channels ---
    ENABLE_TELEGRAM = _bool("ENABLE_TELEGRAM", True)
    ENABLE_WHATSAPP = _bool("ENABLE_WHATSAPP", False)
    ENABLE_EMAIL = _bool("ENABLE_EMAIL", False)

    # --- sources ---
    ENABLE_GOOGLE_CALENDAR = _bool("ENABLE_GOOGLE_CALENDAR", True)
    ENABLE_GOOGLE_CLASSROOM = _bool("ENABLE_GOOGLE_CLASSROOM", True)

    # --- timing ---
    REMINDER_OFFSETS_MINUTES = _int_list("REMINDER_OFFSETS_MINUTES", "1440,60,15")
    CHECK_FREQUENCY_MINUTES = int(os.getenv("CHECK_FREQUENCY_MINUTES", "5"))
    LOOKAHEAD_HOURS = int(os.getenv("LOOKAHEAD_HOURS", "72"))

    # --- google ---
    GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    GOOGLE_TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
    # Full "calendar" scope (not calendar.readonly) - needed so the agent
    # can both read events AND create new ones (add-meeting, bookings),
    # and query free/busy for the booking flow.
    GOOGLE_SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/classroom.courses.readonly",
        "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
        "https://www.googleapis.com/auth/classroom.announcements.readonly",
    ]

    # --- telegram ---
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # --- whatsapp ---
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_TO_NUMBER = os.getenv("WHATSAPP_TO_NUMBER", "")
    WHATSAPP_SEND_MODE = os.getenv("WHATSAPP_SEND_MODE", "template")
    WHATSAPP_TEMPLATE_NAME = os.getenv("WHATSAPP_TEMPLATE_NAME", "reminder_alert")
    WHATSAPP_TEMPLATE_LANG = os.getenv("WHATSAPP_TEMPLATE_LANG", "en_US")

    # --- email ---
    EMAIL_SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "465"))
    EMAIL_USER = os.getenv("EMAIL_USER", "")
    EMAIL_PASS = os.getenv("EMAIL_PASS", "")
    EMAIL_TO = os.getenv("EMAIL_TO", "")

    # --- storage ---
    DB_FILE = os.getenv("DB_FILE", "agent_state.db")

    # --- display ---
    # IANA name, e.g. "Asia/Kolkata", "America/New_York". Internally
    # everything is still stored/compared in UTC - this only affects
    # what gets shown to you and to guests booking a slot.
    LOCAL_TIMEZONE_NAME = os.getenv("LOCAL_TIMEZONE", "UTC")

    @classmethod
    def local_tz(cls) -> ZoneInfo:
        return ZoneInfo(cls.LOCAL_TIMEZONE_NAME)

    @classmethod
    def validate(cls):
        """Fail loudly (once, at startup) instead of silently misbehaving later."""
        problems = []
        try:
            cls.local_tz()
        except Exception as e:
            problems.append(
                f"LOCAL_TIMEZONE '{cls.LOCAL_TIMEZONE_NAME}' couldn't be loaded ({e}). "
                "On Windows this almost always means the 'tzdata' package isn't installed - "
                "run: pip install tzdata"
            )
        if cls.ENABLE_TELEGRAM and not (cls.TELEGRAM_BOT_TOKEN and cls.TELEGRAM_CHAT_ID):
            problems.append("Telegram is enabled but TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID is missing.")
        if cls.ENABLE_WHATSAPP and not (cls.WHATSAPP_TOKEN and cls.WHATSAPP_PHONE_NUMBER_ID and cls.WHATSAPP_TO_NUMBER):
            problems.append("WhatsApp is enabled but WHATSAPP_TOKEN/WHATSAPP_PHONE_NUMBER_ID/WHATSAPP_TO_NUMBER is missing.")
        if cls.ENABLE_EMAIL and not (cls.EMAIL_USER and cls.EMAIL_PASS and cls.EMAIL_TO):
            problems.append("Email is enabled but EMAIL_USER/EMAIL_PASS/EMAIL_TO is missing.")
        if (cls.ENABLE_GOOGLE_CALENDAR or cls.ENABLE_GOOGLE_CLASSROOM) and not os.path.exists(cls.GOOGLE_CREDENTIALS_FILE):
            problems.append(
                f"Google source(s) enabled but '{cls.GOOGLE_CREDENTIALS_FILE}' was not found. "
                "Download OAuth credentials from Google Cloud Console."
            )
        if problems:
            raise SystemExit(
                "Config problems found:\n  - " + "\n  - ".join(problems) +
                "\n\nFix your .env file (see .env.example) and try again."
            )
