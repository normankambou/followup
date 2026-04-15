import anthropic
import json
import os
import datetime
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def analyze_transcript(transcript_text: str) -> dict:
    today = datetime.date.today()
    day_name = today.strftime("%A")
    date_str = today.strftime("%Y-%m-%d")

    prompt = f"""You are a meeting intelligence assistant. Analyze the following meeting transcript and return a structured JSON response.

Today's date is {day_name}, {date_str}. Use this to resolve any relative date references in the transcript such as "tomorrow", "next Monday", "end of week", "in two weeks", "by Friday", etc. Always convert them to an absolute date in YYYY-MM-DD format.

Transcript:
{transcript_text}

Return ONLY valid JSON with this exact structure, no other text:
{{
    "attendees": ["list", "of", "attendee", "names", "extracted", "from", "transcript"],
    "summary": "2-3 sentence summary of what the meeting was about",
    "action_items": [
        {{
            "id": 1,
            "task": "clear description of the task",
            "owner": "person responsible (must be one of the attendees)",
            "due_date": "YYYY-MM-DD format. Convert ALL relative dates using today's date. Only return null if absolutely no time reference exists anywhere in the transcript for this item.",
            "duration_minutes": 30,
            "priority": "high/medium/low",
            "priority_reason": "one sentence explaining why you ranked it this priority"
        }}
    ]
}}

Rules:
- Priority: High = client-facing, hard deadline, blocks others. Medium = internal, soft deadline. Low = no deadline, nice to have.
- Duration: estimate realistically. A quick email = 15 min. A report = 60-90 min. A call = 30-60 min. A full audit = 120 min.
- Due dates: be aggressive about resolving relative references. "Tomorrow morning", "end of next week", "by Friday" should all resolve to specific dates.
- Order action_items from highest to lowest priority."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    response_text = message.content[0].text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    result = json.loads(response_text.strip())
    return result