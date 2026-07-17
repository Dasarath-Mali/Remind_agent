"""
Pulls upcoming coursework (assignments, tests, quizzes) due dates from
Google Classroom across all active courses the user is enrolled in.

NOTE ON TIME ZONES: Classroom's API returns dueDate/dueTime as separate
fields representing UTC. We combine them into a UTC-aware datetime here.
If reminders feel off by a few hours, double check your system time zone
vs. UTC in reminder_engine.py.
"""
import datetime as dt
from googleapiclient.discovery import build

from config import Config
from connectors.google_auth import get_google_credentials


def get_upcoming_coursework() -> list[dict]:
    creds = get_google_credentials()
    service = build("classroom", "v1", credentials=creds)

    now = dt.datetime.now(dt.timezone.utc)
    horizon = now + dt.timedelta(hours=Config.LOOKAHEAD_HOURS)

    items = []
    courses_resp = service.courses().list(courseStates=["ACTIVE"]).execute()
    for course in courses_resp.get("courses", []):
        course_id = course["id"]
        course_name = course.get("name", "Classroom")

        coursework_resp = service.courses().courseWork().list(courseId=course_id).execute()
        for work in coursework_resp.get("courseWork", []):
            due_date = work.get("dueDate")
            due_time = work.get("dueTime")
            if not due_date:
                continue  # no deadline set, nothing to remind about

            start_time = dt.datetime(
                year=due_date.get("year"),
                month=due_date.get("month"),
                day=due_date.get("day"),
                hour=due_time.get("hours", 23) if due_time else 23,
                minute=due_time.get("minutes", 59) if due_time else 59,
                tzinfo=dt.timezone.utc,
            )

            if now <= start_time <= horizon:
                work_type = "test/quiz" if _looks_like_test(work.get("title", "")) else "assignment"
                items.append({
                    "id": f"classroom-{work['id']}",
                    "title": f"{work.get('title', '(untitled)')} ({course_name})",
                    "type": work_type,
                    "start_time": start_time,
                    "source": "Google Classroom",
                })

    return items


def _looks_like_test(title: str) -> bool:
    keywords = ("test", "quiz", "exam", "midterm", "final")
    lowered = title.lower()
    return any(k in lowered for k in keywords)
