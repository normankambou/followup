# CLAUDE.md — FollowUp Project Context

## What This Project Does
FollowUp is an AI-powered meeting intelligence tool that turns raw meeting transcripts into structured, prioritized action items and automatically schedules them on Google Calendar. It uses Claude as the core intelligence layer for transcript analysis, priority ranking, and conflict resolution between calendar events.

## Project Structure
- `app.py` — Streamlit frontend and main application logic
- `claude_engine.py` — All Anthropic API calls. Handles transcript analysis, attendee extraction, action item generation, priority ranking, and duration estimation
- `calendar_engine.py` — Google Calendar integration. Handles event creation, conflict detection, priority assessment between events, reschedule option generation, and slot finding logic
- `notification_engine.py` — Gmail SMTP integration for email notifications to action item owners and displaced event attendees
- `auth.py` — One-time Google OAuth authentication script
- `sample_transcript.txt` — Sample meeting transcript for testing
- `.env` — Environment variables (not committed to git)
- `credentials.json` — Google OAuth credentials (not committed to git)
- `token.json` — Google OAuth token generated after auth (not committed to git)

## Environment Variables Required
ANTHROPIC_API_KEY=your_anthropic_api_key
SENDER_EMAIL=your_gmail_address
SENDER_PASSWORD=your_gmail_app_password

## How to Run
conda activate meeting-summarizer
cd "path/to/GTM Project Work"
python auth.py  # only needed once to authenticate Google Calendar
streamlit run app.py

## Key Dependencies
pip install anthropic streamlit google-auth-oauthlib google-auth-httplib2 google-api-python-client python-dotenv

## How Claude Is Used

### 1. Transcript Analysis (claude_engine.py)
The `analyze_transcript()` function sends the full transcript to Claude with today's date injected into the prompt. Claude returns structured JSON containing:
- Auto-detected attendees
- 2-3 sentence meeting summary
- Action items with owner, due date (resolved from relative references like "tomorrow" or "end of next week"), priority level, priority reasoning, and estimated duration

### 2. Calendar Conflict Resolution (calendar_engine.py)
The `assess_priority_with_claude()` function is called when a new action item conflicts with an existing calendar event at 9am on the due date. Claude receives both event details and returns a JSON decision on which should take priority and why. The user is always shown this reasoning and asked to confirm before anything is moved.

## Scheduling Logic
- Always attempts to schedule new action items at 9am on the due date
- If a conflict exists at 9am, Claude assesses priority between the two events
- If the new item wins, the user is shown 4-5 reschedule options for the displaced event
- Options include: same time next workday, first available same day, first available next workday, same time one week out (low/medium priority only), first available two workdays out
- Skips weekends automatically
- Flags past due dates and asks user whether to reschedule to next available workday

## Known Limitations & Future Work
- Currently schedules all action items at 9am — future versions should consider task type and owner availability
- Attendee email matching is manual — future versions should suggest frequent collaborators based on history
- Only supports one Google Calendar account — future versions should support multi-user environments
- No persistent storage of past meetings — a database layer would enable cross-meeting pattern recognition and accountability tracking
- Conflict resolution only checks the 9am slot — future versions should check the full preferred duration window

## Testing
Use `sample_transcript.txt` which contains:
- Relative date references (tomorrow, end of next week, next Monday, two weeks from today)
- A built-in scheduling conflict on April 20th between Kevin's Meridian checklist and Data Team Sync
- Varied task durations from 15 minutes to half a day
- Multiple owners and dependencies

To trigger the conflict test: ensure "Data Team Sync" exists at 9am on April 20th in Google Calendar, then schedule Kevin's "Send Meridian onboarding checklist at 9am" action item.