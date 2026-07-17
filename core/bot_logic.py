"""
All Telegram conversation logic lives here.

- Messages from YOU (TELEGRAM_CHAT_ID) get the full command set, including
  /addmeeting to write to your calendar.
- Messages from anyone else are treated as guests: auto-reply + a /book
  flow that checks your real availability and creates the event itself.

Conversation state is kept in memory per chat_id. If the agent restarts
mid-conversation, that one conversation resets - guests just run /book
again, which is an acceptable tradeoff for a personal tool.
"""
import datetime as dt

from config import Config
from core import reminder_engine
from core.booking_engine import find_available_slots, book_slot
from connectors import telegram_channel

_conversations: dict[int, dict] = {}


def _is_owner(chat_id) -> bool:
    return str(chat_id) == str(Config.TELEGRAM_CHAT_ID)


def _to_local(t: dt.datetime) -> dt.datetime:
    return t.astimezone(Config.local_tz())


def _fmt(t: dt.datetime) -> str:
    tz_label = Config.LOCAL_TIMEZONE_NAME
    return f"{_to_local(t).strftime('%a %d %b, %H:%M')} ({tz_label})"


def handle_message(chat_id: int, text: str, from_user: dict) -> str:
    text = text.strip()

    if chat_id in _conversations:
        return _continue_flow(chat_id, text, from_user)

    command = text.split()[0].lower() if text else ""

    if _is_owner(chat_id):
        return _handle_owner_command(chat_id, command)

    return _handle_guest_message(chat_id, command, text, from_user)


# ---------------- Owner ----------------

def _handle_owner_command(chat_id, command):
    if command in ("/today", "/agenda"):
        return reminder_engine.build_agenda_text()
    if command == "/ping":
        return "I'm alive and watching your calendar/classroom. ✅"
    if command == "/addmeeting":
        _conversations[chat_id] = {"flow": "add_meeting", "step": "title", "data": {}}
        return "Let's add a meeting. What's the title? (type /cancel anytime to stop)"
    if command == "/start":
        return (
            "Hey! I'm your assistant.\n"
            "/today - your full agenda\n"
            "/addmeeting - add something to your calendar\n"
            "/ping - check I'm alive\n\n"
            "Anyone else who messages me gets an auto-reply and can book "
            "time with you via /book, checked against your real availability."
        )
    return "Unknown command. Try /today, /addmeeting, or /ping."


def _continue_add_meeting(chat_id, text, state):
    step, data = state["step"], state["data"]

    if step == "title":
        data["title"] = text
        state["step"] = "when"
        return f"When? Use format: YYYY-MM-DD HH:MM, in your local time ({Config.LOCAL_TIMEZONE_NAME}). e.g. 2026-07-20 15:00"

    if step == "when":
        try:
            naive = dt.datetime.strptime(text, "%Y-%m-%d %H:%M")
            start = naive.replace(tzinfo=Config.local_tz()).astimezone(dt.timezone.utc)
        except ValueError:
            return "Didn't understand that. Use format: YYYY-MM-DD HH:MM"
        data["start"] = start
        state["step"] = "duration"
        return "How long, in minutes? (just reply a number, e.g. 30)"

    if step == "duration":
        try:
            minutes = int(text)
        except ValueError:
            return "Please reply with just a number, e.g. 30"
        start = data["start"]
        end = start + dt.timedelta(minutes=minutes)
        _conversations.pop(chat_id, None)
        try:
            from connectors.calendar_source import create_event
            create_event(data["title"], start, end)
            return f"Done! Added '{data['title']}' on {_fmt(start)}."
        except Exception as e:
            return f"Couldn't create the event: {e}"

    _conversations.pop(chat_id, None)
    return "Something went wrong there, let's start over."


# ---------------- Guest ----------------

def _handle_guest_message(chat_id, command, text, from_user):
    if command == "/book":
        return _start_booking(chat_id)
    name = from_user.get("first_name", "there")
    if command == "/start" or not text.startswith("/"):
        return (
            f"Hi {name}! This is an automated assistant. "
            "If you'd like to book a meeting, type /book to see available times."
        )
    return "Type /book to see available meeting times."


def _start_booking(chat_id):
    slots = find_available_slots()
    if not slots:
        return "Sorry, no open slots in the next week. Try again later."

    lines = ["Here are the available times - reply with a number:"]
    for i, (start, _end) in enumerate(slots, start=1):
        lines.append(f"{i}) {_fmt(start)}")
    lines.append("(/cancel to stop)")

    _conversations[chat_id] = {"flow": "book", "step": "choose_slot", "data": {"slots": slots}}
    return "\n".join(lines)


def _continue_booking(chat_id, text, state):
    step, data = state["step"], state["data"]

    if step == "choose_slot":
        try:
            idx = int(text) - 1
            if idx < 0:
                raise ValueError
            start, end = data["slots"][idx]
        except (ValueError, IndexError):
            return "Please reply with a valid number from the list."
        data["chosen"] = (start, end)
        state["step"] = "name"
        return "Great - what's your name?"

    if step == "name":
        start, end = data["chosen"]
        guest_name = text
        _conversations.pop(chat_id, None)
        try:
            book_slot(start, end, guest_name, chat_id)
        except Exception as e:
            return f"Sorry, something went wrong booking that: {e}"

        telegram_channel.send(
            f"📅 New booking: {guest_name} booked {_fmt(start)}",
            chat_id=Config.TELEGRAM_CHAT_ID,
        )
        return f"You're booked for {_fmt(start)}. See you then!"

    _conversations.pop(chat_id, None)
    return "Something went wrong there, let's start over."


# ---------------- Shared ----------------

def _continue_flow(chat_id, text, from_user):
    if text.lower() in ("cancel", "/cancel"):
        _conversations.pop(chat_id, None)
        return "Cancelled."

    state = _conversations[chat_id]
    if state["flow"] == "add_meeting":
        return _continue_add_meeting(chat_id, text, state)
    if state["flow"] == "book":
        return _continue_booking(chat_id, text, state)

    _conversations.pop(chat_id, None)
    return "Something went wrong there, let's start over."
