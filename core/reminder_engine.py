"""
The brain of the agent:
1. Gather upcoming items from every enabled source (Calendar, Classroom).
2. For each configured reminder offset (e.g. 60 minutes before), check
   whether "now" has just crossed that trigger point for that item.
3. Dispatch the reminder across every enabled channel.
4. Record what was sent so it never repeats.
"""
import datetime as dt

from config import Config
from core.storage import Storage
from connectors import telegram_channel, whatsapp_channel, email_channel

storage = Storage(Config.DB_FILE)


def _gather_items() -> list[dict]:
    items = []

    if Config.ENABLE_GOOGLE_CALENDAR:
        try:
            from connectors.calendar_source import get_upcoming_events
            items.extend(get_upcoming_events())
        except Exception as e:
            print(f"[reminder_engine] calendar fetch failed: {e}")

    if Config.ENABLE_GOOGLE_CLASSROOM:
        try:
            from connectors.classroom_source import get_upcoming_coursework
            items.extend(get_upcoming_coursework())
        except Exception as e:
            print(f"[reminder_engine] classroom fetch failed: {e}")

    return items


def _format_message(item: dict, offset_minutes: int) -> str:
    when = "today" if offset_minutes < 60 * 24 else f"in {offset_minutes // 60}h"
    label = {
        "meeting": "Meeting",
        "assignment": "Assignment due",
        "test/quiz": "Test/Quiz",
    }.get(item["type"], "Reminder")

    local_time = item["start_time"].astimezone(Config.local_tz()).strftime("%a %d %b, %H:%M")
    return (
        f"⏰ {label}: {item['title']}\n"
        f"Starts/due: {local_time} ({Config.LOCAL_TIMEZONE_NAME})\n"
        f"Reminder set for {offset_minutes} min before ({item['source']})"
    )


def _dispatch(message: str):
    sent_anywhere = False
    if Config.ENABLE_TELEGRAM:
        sent_anywhere = telegram_channel.send(message) or sent_anywhere
    if Config.ENABLE_WHATSAPP:
        sent_anywhere = whatsapp_channel.send(message) or sent_anywhere
    if Config.ENABLE_EMAIL:
        sent_anywhere = email_channel.send(message, subject="Reminder from your agent") or sent_anywhere
    return sent_anywhere


def run_check_cycle():
    """Called on a timer. Checks all items against all reminder offsets."""
    now = dt.datetime.now(dt.timezone.utc)
    items = _gather_items()
    tolerance = dt.timedelta(minutes=max(Config.CHECK_FREQUENCY_MINUTES, 1))

    for item in items:
        start_time = item["start_time"]
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=dt.timezone.utc)

        for offset in Config.REMINDER_OFFSETS_MINUTES:
            trigger_at = start_time - dt.timedelta(minutes=offset)
            # Fire if "now" has just crossed the trigger point since the last check.
            if trigger_at <= now <= trigger_at + tolerance:
                if not storage.already_sent(item["id"], offset):
                    message = _format_message(item, offset)
                    if _dispatch(message):
                        storage.mark_sent(item["id"], offset)
                        print(f"[reminder_engine] sent reminder: {item['title']} ({offset}m)")

    storage.cleanup_older_than(days=30)


def build_agenda_text() -> str:
    """Used by the Telegram /today and /agenda commands."""
    items = _gather_items()
    if not items:
        return "Nothing coming up in the lookahead window. 🎉"

    items.sort(key=lambda i: i["start_time"])
    lines = ["Here's what's coming up:"]
    for item in items:
        when = item["start_time"].astimezone(Config.local_tz()).strftime("%a %d %b, %H:%M")
        lines.append(f"• [{item['type']}] {item['title']} — {when} {Config.LOCAL_TIMEZONE_NAME} ({item['source']})")
    return "\n".join(lines)
