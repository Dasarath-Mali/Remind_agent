"""
Finds open meeting slots on your calendar and books them for guests.
Only checks free/busy - a guest booking a slot never sees your event
titles or details, only whether a time is taken or open.
"""
import datetime as dt

from config import Config
from connectors.calendar_source import get_busy_periods, create_event

BUSINESS_START_HOUR = 9
BUSINESS_END_HOUR = 18
SLOT_MINUTES = 30
DAYS_AHEAD = 7
MAX_SLOTS = 6


def _overlaps(start, end, busy_periods) -> bool:
    return any(start < b_end and end > b_start for b_start, b_end in busy_periods)


def find_available_slots() -> list[tuple]:
    """Returns up to MAX_SLOTS (start, end) tuples, both tz-aware UTC datetimes."""
    now = dt.datetime.now(dt.timezone.utc)
    horizon = now + dt.timedelta(days=DAYS_AHEAD)
    busy_periods = get_busy_periods(now, horizon)

    slots = []
    day_cursor = now.date()
    for day_offset in range(DAYS_AHEAD + 1):
        day = day_cursor + dt.timedelta(days=day_offset)
        if day.weekday() >= 5:  # skip weekends
            continue

        slot_start = dt.datetime(day.year, day.month, day.day, BUSINESS_START_HOUR,
                                  tzinfo=dt.timezone.utc)
        day_end = dt.datetime(day.year, day.month, day.day, BUSINESS_END_HOUR,
                               tzinfo=dt.timezone.utc)

        while slot_start + dt.timedelta(minutes=SLOT_MINUTES) <= day_end:
            slot_end = slot_start + dt.timedelta(minutes=SLOT_MINUTES)
            if slot_start > now and not _overlaps(slot_start, slot_end, busy_periods):
                slots.append((slot_start, slot_end))
                if len(slots) >= MAX_SLOTS:
                    return slots
            slot_start = slot_end

    return slots


def book_slot(start: dt.datetime, end: dt.datetime, guest_name: str, chat_id: int) -> dict:
    return create_event(
        summary=f"Meeting with {guest_name}",
        start_dt=start,
        end_dt=end,
        description=f"Booked via Telegram bot by {guest_name} (chat id {chat_id})",
    )
