"""
Pulls upcoming events (meetings) from the user's primary Google Calendar.
"""
import datetime as dt
from googleapiclient.discovery import build

from config import Config
from connectors.google_auth import get_google_credentials


def _service():
    creds = get_google_credentials()
    return build("calendar", "v3", credentials=creds)


def get_upcoming_events() -> list[dict]:
    """
    Returns a normalized list of items:
    { id, title, type='meeting', start_time (datetime, tz-aware), source }
    """
    service = _service()

    now = dt.datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + dt.timedelta(hours=Config.LOOKAHEAD_HOURS)).isoformat() + "Z"

    events_result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    items = []
    for event in events_result.get("items", []):
        start_raw = event["start"].get("dateTime", event["start"].get("date"))
        if not start_raw:
            continue
        try:
            start_time = dt.datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        except ValueError:
            continue

        items.append({
            "id": f"gcal-{event['id']}",
            "title": event.get("summary", "(No title)"),
            "type": "meeting",
            "start_time": start_time,
            "source": "Google Calendar",
        })

    return items


def create_event(summary: str, start_dt: dt.datetime, end_dt: dt.datetime,
                  description: str = "", attendee_email: str | None = None) -> dict:
    """Creates an event on the primary calendar. start_dt/end_dt must be tz-aware."""
    service = _service()
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_dt.isoformat()},
        "end": {"dateTime": end_dt.isoformat()},
    }
    if attendee_email:
        body["attendees"] = [{"email": attendee_email}]
    return service.events().insert(calendarId="primary", body=body).execute()


def get_busy_periods(time_min: dt.datetime, time_max: dt.datetime) -> list[tuple]:
    """Free/busy check - never exposes event titles, just occupied time ranges."""
    service = _service()
    result = service.freebusy().query(body={
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "items": [{"id": "primary"}],
    }).execute()

    busy = []
    for period in result["calendars"]["primary"]["busy"]:
        start = dt.datetime.fromisoformat(period["start"].replace("Z", "+00:00"))
        end = dt.datetime.fromisoformat(period["end"].replace("Z", "+00:00"))
        busy.append((start, end))
    return busy
