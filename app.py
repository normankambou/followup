import streamlit as st
import datetime
import os
from claude_engine import analyze_transcript
from calendar_engine import (
    create_calendar_event,
    move_event_to_slot,
    create_action_item_event,
    get_calendar_service
)
from notification_engine import notify_event_scheduled, notify_event_rescheduled

st.set_page_config(page_title="Meeting Minutes Summarizer", layout="wide")

st.title("📋 Meeting Minutes Summarizer")
st.markdown("Upload a transcript and get AI-powered summaries with prioritized action items.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Step 1: Upload Transcript")
    transcript_file = st.file_uploader("Choose a text file", type="txt")
    if transcript_file:
        transcript_text = transcript_file.read().decode("utf-8")
        st.success("Transcript loaded!")

with col2:
    st.subheader("Step 2: Enter Attendee Emails (Optional)")
    st.markdown("Attendees will be auto-detected from the transcript. Emails are used for notifications.")
    emails_input = st.text_area(
        "Enter attendee emails (comma-separated, in order of names as they appear)",
        placeholder="jordan@email.com, marcus@email.com, priya@email.com"
    )
    email_list = [e.strip() for e in emails_input.split(",") if e.strip()]

if transcript_file:
    if st.button("Generate Summary & Action Items"):
        with st.spinner("Claude is analyzing your meeting..."):
            result = analyze_transcript(transcript_text)
            attendees = result.get("attendees", [])
            attendee_emails = dict(zip(attendees, email_list)) if attendees and email_list else {}
        st.session_state["result"] = result
        st.session_state["attendees"] = attendees
        st.session_state["attendee_emails"] = attendee_emails
        st.session_state["pending_conflicts"] = {}
        st.session_state["scheduled"] = {}

if "result" in st.session_state:
    result = st.session_state["result"]
    attendee_emails = st.session_state.get("attendee_emails", {})
    attendees = st.session_state.get("attendees", [])

    st.subheader("Meeting Summary")
    st.write(result["summary"])

    st.subheader(f"Attendees Detected: {', '.join(attendees)}")

    st.subheader("Action Items (Prioritized)")
    priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}

    if st.button("📅 Add All to Google Calendar"):
        with st.spinner("Scheduling all action items..."):
            for item in result["action_items"]:
                conflict_key = f"conflict_{item['id']}"
                scheduled_key = f"scheduled_{item['id']}"
                if scheduled_key in st.session_state:
                    continue
                try:
                    owner_email = attendee_emails.get(item["owner"], "")
                    link, status, extra = create_calendar_event(
                        task=item["task"],
                        owner=item["owner"],
                        due_date=item["due_date"],
                        priority=item["priority"]
                    )
                    if status == "success":
                        st.session_state[scheduled_key] = extra
                        if owner_email:
                            notify_event_scheduled(
                                task=item["task"],
                                owner_email=owner_email,
                                scheduled_time=extra
                            )
                    elif status == "conflict":
                        st.session_state[conflict_key] = extra
                    elif status == "no_slot":
                        st.warning(f"No available slot found for: {item['task']}")
                except Exception as e:
                    st.error(f"Error scheduling '{item['task']}': {str(e)}")
        st.rerun()

    st.divider()

    for item in result["action_items"]:
        icon = priority_icon.get(item["priority"], "⚪")
        scheduled_key = f"scheduled_{item['id']}"
        conflict_key = f"conflict_{item['id']}"

        with st.expander(f"{icon} {item['task']} — {item['owner']}"):
            st.write(f"**Priority:** {item['priority'].capitalize()}")
            st.write(f"**Reason:** {item['priority_reason']}")
            st.write(f"**Due Date:** {item['due_date'] or 'Not specified'}")

            # Already scheduled
            if scheduled_key in st.session_state:
                st.success(f"✅ Scheduled for {st.session_state[scheduled_key]}")

            # Conflict resolution UI
            elif conflict_key in st.session_state:
                conflicts = st.session_state[conflict_key]
                for i, conflict in enumerate(conflicts):
                    event_title = conflict["event"].get("summary", "Untitled")
                    st.warning(f"⚠️ Conflict with: **{event_title}** at {conflict['preferred_time']} on {conflict['target_date']}")
                    st.write(f"**Claude's reasoning:** {conflict['reason']}")

                    if not conflict["is_our_event"]:
                        st.write("This event was **not** created by Meeting Summarizer.")

                    st.write("**Where should we move the conflicting event?**")

                    options = conflict.get("reschedule_options", [])
                    if not options:
                        st.error("No available reschedule slots found.")
                    else:
                        option_labels = [o["label"] for o in options]
                        selected_label = st.radio(
                            "Select a new time slot for the displaced event:",
                            option_labels,
                            key=f"radio_{item['id']}_{i}"
                        )
                        selected_option = next(o for o in options if o["label"] == selected_label)

                        col_confirm, col_cancel = st.columns(2)
                        with col_confirm:
                            if st.button("✅ Confirm & Reschedule", key=f"confirm_{item['id']}_{i}"):
                                service = get_calendar_service()
                                updated, new_time = move_event_to_slot(
                                    service,
                                    conflict["event"],
                                    selected_option["date"],
                                    selected_option["time"]
                                )
                                if updated:
                                    notify_event_rescheduled(
                                        original_event_title=event_title,
                                        original_time=conflict["event"]["start"].get("dateTime", ""),
                                        new_time=new_time,
                                        attendee_emails=conflict["attendee_emails"] or [os.getenv("SENDER_EMAIL")],
                                        reason=conflict["reason"]
                                    )
                                    # Now create the action item at the freed 9am slot
                                    target_date = datetime.date.fromisoformat(conflict["target_date"])
                                    created, scheduled_time = create_action_item_event(
                                        service,
                                        item["task"],
                                        item["owner"],
                                        target_date,
                                        datetime.time(9, 0)
                                    )
                                    if created:
                                        owner_email = attendee_emails.get(item["owner"], "")
                                        if owner_email:
                                            notify_event_scheduled(
                                                task=item["task"],
                                                owner_email=owner_email,
                                                scheduled_time=scheduled_time
                                            )
                                        st.session_state[scheduled_key] = scheduled_time
                                        del st.session_state[conflict_key]
                                        st.rerun()
                                else:
                                    st.error(f"Failed to reschedule: {new_time}")

                        with col_cancel:
                            if st.button("❌ Cancel", key=f"cancel_{item['id']}_{i}"):
                                del st.session_state[conflict_key]
                                st.info("Cancelled. Action item was not scheduled.")
                                st.rerun()

            # Individual add button
            else:
                if st.button(f"📅 Add to Google Calendar", key=f"cal_{item['id']}"):
                    with st.spinner("Checking calendar and scheduling..."):
                        try:
                            owner_email = attendee_emails.get(item["owner"], "")
                            link, status, extra = create_calendar_event(
                                task=item["task"],
                                owner=item["owner"],
                                due_date=item["due_date"],
                                priority=item["priority"]
                            )
                            if status == "success":
                                st.session_state[scheduled_key] = extra
                                if owner_email:
                                    notify_event_scheduled(
                                        task=item["task"],
                                        owner_email=owner_email,
                                        scheduled_time=extra
                                    )
                                st.rerun()
                            elif status == "conflict":
                                st.session_state[conflict_key] = extra
                                st.rerun()
                            elif status == "no_slot":
                                st.error("No available time slots found in the next 2 days.")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")