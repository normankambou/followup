import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

def send_email(to_emails: list, subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(to_emails)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_emails, msg.as_string())

def notify_event_scheduled(task: str, owner_email: str, scheduled_time: str):
    send_email(
        to_emails=[owner_email],
        subject=f"Action Item Scheduled: {task}",
        body=f"""Hi,

Your action item has been scheduled on your Google Calendar.

Task: {task}
Scheduled: {scheduled_time}

This was created automatically by Meeting Summarizer.
"""
    )

def notify_event_rescheduled(
    original_event_title: str,
    original_time: str,
    new_time: str,
    attendee_emails: list,
    reason: str
):
    send_email(
        to_emails=attendee_emails,
        subject=f"Meeting Rescheduled: {original_event_title}",
        body=f"""Hi,

Your meeting has been rescheduled by Meeting Summarizer to accommodate a higher priority action item.

Meeting: {original_event_title}
Original Time: {original_time}
New Time: {new_time}
Reason: {reason}

This was done automatically by Meeting Summarizer.
"""
    )