import datetime
import os
import json
import anthropic
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
TIMEZONE = "America/New_York"
WORK_START = datetime.time(9, 0)
WORK_END = datetime.time(17, 0)


def get_calendar_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    service = build("calendar", "v3", credentials=creds)
    return service


def next_workday(date: datetime.date, days_ahead: int = 1) -> datetime.date:
    result = date + datetime.timedelta(days=days_ahead)
    while result.weekday() >= 5:
        result += datetime.timedelta(days=1)
    return result


def get_existing_events(service, date: datetime.date) -> list:
    try:
        start_of_day = datetime.datetime.combine(date, datetime.time(0, 0)).isoformat() + "Z"
        end_of_day = datetime.datetime.combine(date, datetime.time(23, 59)).isoformat() + "Z"
        events_result = service.events().list(
            calendarId="primary",
            timeMin=start_of_day,
            timeMax=end_of_day,
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        return events_result.get("items", [])
    except Exception as e:
        print(f"Error fetching events for {date}: {e}")
        return []


def parse_event_time(event: dict, field: str):
    dt_str = event.get(field, {}).get("dateTime")
    if not dt_str:
        return None
    try:
        return datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def get_event_at_time(events: list, target_time: datetime.time, duration_minutes: int = 60):
    target_dt = datetime.datetime.combine(datetime.date.today(), target_time)
    target_end = target_dt + datetime.timedelta(minutes=duration_minutes)
    for event in events:
        start_dt = parse_event_time(event, "start")
        end_dt = parse_event_time(event, "end")
        if start_dt and end_dt:
            if not (target_end.time() <= start_dt.time() or target_time >= end_dt.time()):
                return event
    return None


def find_free_slot(
    existing_events: list,
    target_date: datetime.date,
    duration_minutes: int = 60,
    exclude_event_id: str = None
):
    busy_slots = []
    for event in existing_events:
        if exclude_event_id and event.get("id") == exclude_event_id:
            continue
        start_dt = parse_event_time(event, "start")
        end_dt = parse_event_time(event, "end")
        if start_dt and end_dt:
            busy_slots.append((start_dt.time(), end_dt.time()))

    current_time = WORK_START
    while current_time < WORK_END:
        slot_end = (
            datetime.datetime.combine(target_date, current_time) +
            datetime.timedelta(minutes=duration_minutes)
        ).time()
        if slot_end > WORK_END:
            break
        conflict = False
        for busy_start, busy_end in busy_slots:
            if not (slot_end <= busy_start or current_time >= busy_end):
                conflict = True
                next_start = (
                    datetime.datetime.combine(target_date, busy_end) +
                    datetime.timedelta(minutes=1)
                ).time()
                current_time = next_start
                break
        if not conflict:
            return current_time
    return None


def assess_priority_with_claude(
    new_task: str,
    new_priority: str,
    existing_event_title: str,
    existing_event_description: str
) -> dict:
    prompt = f"""You are a scheduling assistant. Two calendar events are competing for the same time slot. Decide which should take priority.

New Action Item:
- Task: {new_task}
- Priority Level: {new_priority}

Existing Calendar Event:
- Title: {existing_event_title}
- Description: {existing_event_description or 'No description'}

Return ONLY valid JSON with this structure:
{{
    "winner": "new" or "existing",
    "reason": "one sentence explaining your decision"
}}

Consider both the urgency and nature of each event. Client-facing and blocking tasks should generally outweigh internal syncs."""

    try:
        message = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        response = message.content[0].text.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        return json.loads(response.strip())
    except Exception as e:
        print(f"Claude priority assessment error: {e}")
        return {"winner": "existing", "reason": "Could not assess priority, defaulting to keeping existing event."}


def generate_reschedule_options(
    service,
    event: dict,
    original_date: datetime.date,
    priority: str,
    duration_minutes: int = 60
) -> list:
    original_time = parse_event_time(event, "start")
    event_time = original_time.time() if original_time else WORK_START
    options = []

    # Option 1: Same time, next workday
    next_day = next_workday(original_date, 1)
    next_day_events = get_existing_events(service, next_day)
    slot_at_same_time = get_event_at_time(next_day_events, event_time, duration_minutes)
    if not slot_at_same_time:
        options.append({
            "date": next_day,
            "time": event_time,
            "label": f"Same time ({event_time.strftime('%I:%M %p')}), next workday — {next_day.strftime('%A, %B %d')}"
        })

    # Option 2: First available slot, same day
    same_day_events = get_existing_events(service, original_date)
    free_same_day = find_free_slot(same_day_events, original_date, duration_minutes, exclude_event_id=event.get("id"))
    if free_same_day and free_same_day != event_time:
        options.append({
            "date": original_date,
            "time": free_same_day,
            "label": f"First available today — {original_date.strftime('%A, %B %d')} at {free_same_day.strftime('%I:%M %p')}"
        })

    # Option 3: First available slot, next workday
    free_next_day = find_free_slot(next_day_events, next_day, duration_minutes)
    if free_next_day and not any(
        o["date"] == next_day and o["time"] == free_next_day for o in options
    ):
        options.append({
            "date": next_day,
            "time": free_next_day,
            "label": f"First available next workday — {next_day.strftime('%A, %B %d')} at {free_next_day.strftime('%I:%M %p')}"
        })

    # Option 4: Same time one week out (only if priority is not high)
    if priority.lower() != "high":
        one_week = next_workday(original_date, 7)
        one_week_events = get_existing_events(service, one_week)
        slot_one_week = get_event_at_time(one_week_events, event_time, duration_minutes)
        if not slot_one_week:
            options.append({
                "date": one_week,
                "time": event_time,
                "label": f"Same time, one week out — {one_week.strftime('%A, %B %d')} at {event_time.strftime('%I:%M %p')}"
            })

    # Option 5: First available two workdays out
    two_days = next_workday(original_date, 2)
    two_days_events = get_existing_events(service, two_days)
    free_two_days = find_free_slot(two_days_events, two_days, duration_minutes)
    if free_two_days and not any(
        o["date"] == two_days and o["time"] == free_two_days for o in options
    ):
        options.append({
            "date": two_days,
            "time": free_two_days,
            "label": f"First available in two workdays — {two_days.strftime('%A, %B %d')} at {free_two_days.strftime('%I:%M %p')}"
        })

    return options[:5]


def move_event_to_slot(
    service,
    event: dict,
    new_date: datetime.date,
    new_time: datetime.time,
    duration_minutes: int = 60
):
    try:
        start_dt = datetime.datetime.combine(new_date, new_time)
        end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)
        event["start"] = {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE}
        event["end"] = {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE}
        updated = service.events().update(
            calendarId="primary",
            eventId=event["id"],
            body=event
        ).execute()
        return updated, start_dt.strftime("%B %d at %I:%M %p")
    except Exception as e:
        print(f"Error moving event: {e}")
        return None, str(e)


def create_action_item_event(
    service,
    task: str,
    owner: str,
    target_date: datetime.date,
    target_time: datetime.time,
    duration_minutes: int = 60
):
    try:
        start_dt = datetime.datetime.combine(target_date, target_time)
        end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)
        event = {
            "summary": f"[Action Item] {task}",
            "description": f"Owner: {owner}\nCreated by FollowUp",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 24 * 60},
                    {"method": "popup", "minutes": 30},
                ],
            },
        }
        created = service.events().insert(calendarId="primary", body=event).execute()
        return created, start_dt.strftime("%B %d at %I:%M %p")
    except Exception as e:
        print(f"Error creating action item event: {e}")
        return None, str(e)


def create_calendar_event(
    task: str,
    owner: str,
    due_date: str,
    priority: str,
    duration_minutes: int = 60
):
    service = get_calendar_service()
    today = datetime.date.today()

    if due_date:
        try:
            target_date = datetime.date.fromisoformat(due_date)
        except Exception:
            target_date = next_workday(today)
    else:
        target_date = next_workday(today)

    # If date is in the past, flag it for user to confirm
    if target_date < today:
        return None, "past_date", target_date.isoformat()

    # Skip weekends
    while target_date.weekday() >= 5:
        target_date += datetime.timedelta(days=1)

    existing_events = get_existing_events(service, target_date)
    conflicting_event = get_event_at_time(existing_events, WORK_START, duration_minutes)

    if conflicting_event:
        priority_result = assess_priority_with_claude(
            new_task=task,
            new_priority=priority,
            existing_event_title=conflicting_event.get("summary", "Untitled"),
            existing_event_description=conflicting_event.get("description", "")
        )

        if priority_result["winner"] == "new":
            # Always require user confirmation regardless of who created the event
            is_our_event = "FollowUp" in conflicting_event.get("description", "") or \
                           "Meeting Summarizer" in conflicting_event.get("description", "")
            reschedule_options = generate_reschedule_options(
                service, conflicting_event, target_date, priority, duration_minutes
            )
            conflict = {
                "event": conflicting_event,
                "reason": priority_result["reason"],
                "is_our_event": is_our_event,
                "preferred_time": WORK_START.strftime("%I:%M %p"),
                "target_date": target_date.isoformat(),
                "reschedule_options": reschedule_options,
                "attendee_emails": [
                    a["email"] for a in conflicting_event.get("attendees", [])
                ]
            }
            return None, "conflict", [conflict]
        else:
            # Existing wins — find next free slot for new item
            free_slot = find_free_slot(existing_events, target_date, duration_minutes)
            if free_slot is None:
                target_date = next_workday(target_date)
                existing_events = get_existing_events(service, target_date)
                free_slot = find_free_slot(existing_events, target_date, duration_minutes)
            if free_slot is None:
                return None, "no_slot", []
            created, scheduled_time = create_action_item_event(
                service, task, owner, target_date, free_slot, duration_minutes
            )
            if created:
                return created.get("htmlLink"), "success", scheduled_time
            return None, "no_slot", []

    # No conflict at 9am — schedule directly
    created, scheduled_time = create_action_item_event(
        service, task, owner, target_date, WORK_START, duration_minutes
    )
    if created:
        return created.get("htmlLink"), "success", scheduled_time
    return None, "no_slot", []