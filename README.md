# Followup — AI-Powered Meeting Intelligence Tool

Built with Python, Streamlit, and the Anthropic Claude API.

## What It Does

Followup turns any meeting transcript into structured, actionable outcomes. Upload a transcript, and the app will:

- **Auto-detect attendees** from the transcript
- **Summarize the meeting** in 2-3 sentences
- **Extract and prioritize action items** using Claude, ranked by urgency and business impact
- **Detect calendar conflicts** when scheduling action items on Google Calendar
- **Use Claude to assess priority** between the new action item and any existing event in the conflicted time slot
- **Suggest reschedule options** for the displaced event and let the user choose
- **Send email notifications** to action item owners and affected attendees when events are scheduled or moved

## The Problem It Solves

Most meetings end with unclear ownership, forgotten action items, and no follow-through. Followup eliminates that entirely — turning spoken decisions into scheduled, tracked commitments automatically.

## Tech Stack

- **Python** — core backend logic
- **Streamlit** — frontend UI
- **Anthropic Claude API** — meeting summarization, action item extraction, priority assessment
- **Google Calendar API** — event creation, conflict detection, rescheduling
- **Gmail SMTP** — email notifications
- **OAuth 2.0** — secure Google authentication

## How Claude Is Used

Claude is the intelligence layer powering three distinct features:

1. **Transcript Analysis** — extracts attendees, summary, action items, owners, due dates, and priority levels from raw meeting text, returned as structured JSON
2. **Priority Ranking** — ranks action items by urgency using custom business logic (client-facing > internal, hard deadline > soft deadline, blocking > non-blocking)
3. **Conflict Resolution** — when a new action item conflicts with an existing calendar event, Claude reads both events and decides which should take priority, with reasoning explained to the user

## Setup Instructions

### Prerequisites
- Python 3.10+
- Anaconda
- Anthropic API key (console.anthropic.com)
- Google Cloud project with Calendar API enabled and OAuth 2.0 credentials

### Installation

Clone the repo and install dependencies:

conda create -n meeting-summarizer python=3.13
conda activate meeting-summarizer
pip install anthropic fastapi uvicorn python-multipart streamlit google-auth-oauthlib google-auth-httplib2 google-api-python-client python-dotenv

### Environment Variables

Create a .env file in the root directory with the following:

ANTHROPIC_API_KEY=your_anthropic_api_key
SENDER_EMAIL=your_gmail_address
SENDER_PASSWORD=your_gmail_app_password

### Google Calendar Setup

1. Add your credentials.json file from Google Cloud Console to the root directory
2. Run the auth script once to generate your token:

python auth.py

### Run the App

streamlit run app.py

## Key Features In Depth

### Intelligent Conflict Resolution
When scheduling an action item and a conflict is detected at the preferred time slot, Claude evaluates both events and determines which takes priority. If the new item wins, the user is presented with 4-5 suggested time slots for the displaced event — including same time next workday, first available slot same day, first available next workday, and more. The user selects a slot, confirms, and both events are updated automatically.

### Smart Scheduling Logic
- Always attempts to schedule at 9am on the due date first
- Skips weekends automatically
- Falls back to next available workday if no slot exists
- Respects existing calendar events when finding free slots

### Email Notifications
- Action item owners receive a confirmation when their task is scheduled
- All attendees of a displaced event receive a rescheduling notice with the reason and new time

## Sample Transcript
A sample transcript (sample_transcript.txt) is included to demonstrate the full feature set, including built-in scheduling conflicts for testing the conflict resolution flow.

## Author
Norman Kambou — github.com/normankambou