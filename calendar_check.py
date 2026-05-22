"""Google Calendar integration -- detect current/upcoming event subject."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

_PROJECT_DIR = Path(__file__).parent
_CREDENTIALS_FILE = _PROJECT_DIR / "credentials.json"
_TOKEN_FILE = _PROJECT_DIR / "token.json"


def _get_calendar_service():
    """Authenticate and return a Google Calendar service object, or None."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        return None

    if not _CREDENTIALS_FILE.exists():
        return None

    creds: Optional[Credentials] = None
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(_CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        _TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    from googleapiclient.discovery import build
    return build("calendar", "v3", credentials=creds)


def get_candidate_events() -> list[str]:
    """
    Return up to two candidate event names ordered by preference:
      [0] Currently running event (start <= now <= end)
      [1] Next upcoming event starting within 60 minutes (if any)

    Searches all selected calendars, not just primary.
    Two candidates are returned when the user may have left one meeting early
    and joined the next one early -- the session window should ask which one.
    Returns an empty list if calendar is unavailable or no events found.
    """
    service = _get_calendar_service()
    if service is None:
        return []

    now_dt = datetime.now(timezone.utc)
    # Look back 4 hours (in case monitor detected meeting late) and
    # ahead 60 minutes (generous window for people who join early).
    time_min = (now_dt - timedelta(hours=4)).isoformat()
    time_max = (now_dt + timedelta(minutes=60)).isoformat()

    # Collect all calendar IDs the user has selected
    try:
        cal_list = service.calendarList().list().execute()
        calendar_ids = [
            c["id"] for c in cal_list.get("items", [])
            if c.get("selected", True)
        ]
    except Exception:
        calendar_ids = ["primary"]

    running: Optional[str] = None
    upcoming: Optional[str] = None

    for cal_id in calendar_ids:
        try:
            events_result = (
                service.events()
                .list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except Exception:
            continue

        for event in events_result.get("items", []):
            start_str = event["start"].get("dateTime") or event["start"].get("date")
            end_str = event["end"].get("dateTime") or event["end"].get("date")
            if not start_str or not end_str:
                continue
            try:
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end   = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            if start <= now_dt <= end and running is None:
                running = event.get("summary", "Unknown Subject")
            elif now_dt < start and upcoming is None:
                upcoming = event.get("summary", "Unknown Subject")

        if running and upcoming:
            break  # found both, no need to check more calendars

    candidates: list[str] = []
    if running:
        candidates.append(running)
    if upcoming:
        candidates.append(upcoming)
    return candidates


def is_calendar_configured() -> bool:
    """Return True if credentials.json exists (calendar feature is set up)."""
    return _CREDENTIALS_FILE.exists()


def get_current_event_subject() -> Optional[str]:
    """Return the primary candidate event subject, or None."""
    candidates = get_candidate_events()
    return candidates[0] if candidates else None
