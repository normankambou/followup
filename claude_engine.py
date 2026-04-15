import anthropic
import json
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def analyze_transcript(transcript_text: str) -> dict:
    
    prompt = f"""You are a meeting intelligence assistant. Analyze the following meeting transcript and return a structured JSON response.

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
            "due_date": "specific date in YYYY-MM-DD format if mentioned, otherwise null",
            "priority": "high/medium/low",
            "priority_reason": "one sentence explaining why you ranked it this priority"
        }}
    ]
}}

Priority ranking rules:
- High: client-facing, has a hard deadline, blocks others
- Medium: internal, has a soft deadline, important but not urgent
- Low: no deadline mentioned, nice to have

Order the action_items array from highest to lowest priority."""

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