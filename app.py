import streamlit as st
import datetime
import os
from claude_engine import analyze_transcript
from calendar_engine import (
    create_calendar_event,
    move_event_to_slot,
    create_action_item_event,
    get_calendar_service,
    next_workday,
    find_free_slot,
    get_existing_events
)
from notification_engine import notify_event_scheduled, notify_event_rescheduled

st.set_page_config(page_title="FollowUp", layout="wide", page_icon="↗")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&family=Inter:wght@300;400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: linear-gradient(160deg, #0f172a 0%, #1e293b 50%, #0f2044 100%);
    min-height: 100vh;
}

.followup-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 40px 0 6px 0;
}

.followup-logo {
    background: white;
    border-radius: 16px;
    width: 52px;
    height: 52px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 26px;
    box-shadow: 0 4px 24px rgba(255,255,255,0.15);
}

.followup-title {
    font-family: 'Nunito', sans-serif;
    font-size: 46px;
    font-weight: 900;
    color: white;
    letter-spacing: -1px;
    margin: 0;
    line-height: 1;
    text-shadow: 0 0 30px rgba(255,255,255,0.3), 3px 3px 0px rgba(255,255,255,0.1);
    -webkit-text-stroke: 1px rgba(255,255,255,0.6);
}

.followup-subtitle {
    font-family: 'Inter', sans-serif;
    font-size: 15px;
    color: rgba(255,255,255,0.5);
    margin: 0 0 36px 0;
}

.stButton > button {
    background: linear-gradient(135deg, #3b82f6, #2563eb);
    color: white;
    border: none;
    border-radius: 12px;
    padding: 10px 24px;
    font-family: 'Nunito', sans-serif;
    font-weight: 700;
    font-size: 14px;
    transition: all 0.2s ease;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
    width: 100%;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(59, 130, 246, 0.5);
}

.stTextArea textarea, .stTextInput input {
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.15);
    background: rgba(255,255,255,0.07);
    color: white;
    font-family: 'Inter', sans-serif;
    font-size: 14px;
}

.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.stTextArea textarea::placeholder, .stTextInput input::placeholder {
    color: rgba(255,255,255,0.3);
}

div[data-testid="stExpander"] {
    background: rgba(255,255,255,0.06);
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.1);
    margin-bottom: 10px;
    backdrop-filter: blur(10px);
}

div[data-testid="stExpander"]:hover {
    border-color: rgba(59,130,246,0.4);
    background: rgba(255,255,255,0.09);
}

div[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.05);
    border-radius: 16px;
    border: 2px dashed rgba(255,255,255,0.2);
}

div[data-testid="stFileUploader"]:hover { border-color: #3b82f6; }

h1, h2, h3, h4 {
    font-family: 'Nunito', sans-serif;
    font-weight: 800;
    color: white !important;
}

p, label, .stMarkdown { color: rgba(255,255,255,0.75) !important; }

.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 4px;
    gap: 4px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
    color: rgba(255,255,255,0.6);
    font-family: 'Nunito', sans-serif;
    font-weight: 700;
    font-size: 14px;
}

.stTabs [aria-selected="true"] { background: #3b82f6; color: white; }

hr { border-color: rgba(255,255,255,0.1); margin: 24px 0; }
</style>

<div class="followup-header">
    <div class="followup-logo">↗</div>
    <h1 class="followup-title">FollowUp</h1>
</div>
<p class="followup-subtitle">Turn any meeting transcript into scheduled, prioritized action items — powered by Claude.</p>
""", unsafe_allow_html=True)

col1, col2 = st.columns([3, 2])

with col1:
    tab1, tab2 = st.tabs(["📂 Upload File", "✏️ Type Here"])
    transcript_text = None

    with tab1:
        transcript_file = st.file_uploader("Choose a .txt file", type="txt", label_visibility="collapsed")
        if transcript_file:
            transcript_text = transcript_file.read().decode("utf-8")
            st.success("Transcript loaded!")

    with tab2:
        pasted_text = st.text_area(
            "transcript_input",
            height=250,
            placeholder="Paste or type your transcript here...\n\nJordan: Alright let's get started...",
            label_visibility="collapsed",
            key="transcript_paste_input"
        )
        if pasted_text and pasted_text.strip():
            transcript_text = pasted_text.strip()

if transcript_text:
    if st.button("✨ Generate Summary & Action Items"):
        with st.spinner("Claude is analyzing your meeting..."):
            result = analyze_transcript(transcript_text)
            attendees = result.get("attendees", [])
        st.session_state["result"] = result
        st.session_state["attendees"] = attendees
        st.session_state["pending_conflicts"] = {}
        st.session_state["scheduled"] = {}

if "result" in st.session_state:
    result = st.session_state["result"]
    attendees = st.session_state.get("attendees", [])

    st.subheader("📝 Meeting Summary")
    st.write(result["summary"])
    st.markdown(f"**👥 Attendees:** {', '.join(attendees)}")

    st.subheader("✅ Action Items")
    priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}

    if st.button("📅 Add All to Google Calendar"):
        with st.spinner("Scheduling all action items..."):
            for item in result["action_items"]:
                conflict_key = f"conflict_{item['id']}"
                scheduled_key = f"scheduled_{item['id']}"
                past_key = f"past_{item['id']}"
                if scheduled_key in st.session_state:
                    continue
                try:
                    duration = item.get("duration_minutes", 60)
                    link, status, extra = create_calendar_event(
                        task=item["task"],
                        owner=item["owner"],
                        due_date=item["due_date"],
                        priority=item["priority"],
                        duration_minutes=duration
                    )
                    if status == "success":
                        st.session_state[scheduled_key] = extra
                    elif status == "conflict":
                        st.session_state[conflict_key] = extra
                    elif status == "past_date":
                        st.session_state[past_key] = extra
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
        past_key = f"past_{item['id']}"
        duration = item.get("duration_minutes", 60)
        email_key = f"email_{item['id']}"

        with st.expander(f"{icon} {item['task']} — {item['owner']}"):
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.markdown(f"**Priority:** {item['priority'].capitalize()}")
            with col_b:
                st.markdown(f"**Due:** {item['due_date'] or 'Not specified'}")
            with col_c:
                st.markdown(f"**Duration:** {duration} min")

            st.markdown(f"*{item['priority_reason']}*")

            # Already scheduled
            if scheduled_key in st.session_state:
                st.success(f"✅ Scheduled for {st.session_state[scheduled_key]}")

            # Past date warning
            elif past_key in st.session_state:
                past_date = st.session_state[past_key]
                st.warning(f"⚠️ The due date ({past_date}) is in the past. What would you like to do?")
                col_today, col_skip = st.columns(2)
                with col_today:
                    if st.button("📅 Schedule for next available date", key=f"past_reschedule_{item['id']}"):
                        service = get_calendar_service()
                        new_date = next_workday(datetime.date.today())
                        existing = get_existing_events(service, new_date)
                        free_slot = find_free_slot(existing, new_date, duration)
                        if free_slot:
                            created, scheduled_time = create_action_item_event(
                                service, item["task"], item["owner"], new_date, free_slot, duration
                            )
                            if created:
                                st.session_state[scheduled_key] = scheduled_time
                                del st.session_state[past_key]
                                st.rerun()
                        else:
                            st.error("No available slots found.")
                with col_skip:
                    if st.button("❌ Skip this item", key=f"past_skip_{item['id']}"):
                        del st.session_state[past_key]
                        st.rerun()

            # Conflict resolution
            elif conflict_key in st.session_state:
                conflicts = st.session_state[conflict_key]
                for i, conflict in enumerate(conflicts):
                    event_title = conflict["event"].get("summary", "Untitled")
                    st.warning(f"⚠️ Conflict with: **{event_title}** at {conflict['preferred_time']} on {conflict['target_date']}")
                    st.markdown(f"**Claude's reasoning:** {conflict['reason']}")
                    if not conflict["is_our_event"]:
                        st.markdown("This event was **not** created by FollowUp.")
                    st.markdown("**Where should we move the conflicting event?**")
                    options = conflict.get("reschedule_options", [])
                    if not options:
                        st.error("No available reschedule slots found.")
                    else:
                        option_labels = [o["label"] for o in options]
                        selected_label = st.radio(
                            "Select a new time slot:",
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
                                    selected_option["time"],
                                    duration
                                )
                                if updated:
                                    notify_emails = st.session_state.get(email_key, "")
                                    if notify_emails:
                                        notify_event_rescheduled(
                                            original_event_title=event_title,
                                            original_time=conflict["event"]["start"].get("dateTime", ""),
                                            new_time=new_time,
                                            attendee_emails=[e.strip() for e in notify_emails.split(",") if e.strip()],
                                            reason=conflict["reason"]
                                        )
                                    target_date = datetime.date.fromisoformat(conflict["target_date"])
                                    created, scheduled_time = create_action_item_event(
                                        service,
                                        item["task"],
                                        item["owner"],
                                        target_date,
                                        datetime.time(9, 0),
                                        duration
                                    )
                                    if created:
                                        notify_emails = st.session_state.get(email_key, "")
                                        if notify_emails:
                                            for email in [e.strip() for e in notify_emails.split(",") if e.strip()]:
                                                notify_event_scheduled(
                                                    task=item["task"],
                                                    owner_email=email,
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

            # Default — show notify input and add button
            else:
                notify_emails = st.text_input(
                    "Notify (optional)",
                    placeholder="email1@co.com, email2@co.com",
                    key=email_key,
                    label_visibility="visible"
                )

                if st.button(f"📅 Add to Google Calendar", key=f"cal_{item['id']}"):
                    with st.spinner("Checking calendar and scheduling..."):
                        try:
                            link, status, extra = create_calendar_event(
                                task=item["task"],
                                owner=item["owner"],
                                due_date=item["due_date"],
                                priority=item["priority"],
                                duration_minutes=duration
                            )
                            if status == "success":
                                st.session_state[scheduled_key] = extra
                                if notify_emails:
                                    for email in [e.strip() for e in notify_emails.split(",") if e.strip()]:
                                        notify_event_scheduled(
                                            task=item["task"],
                                            owner_email=email,
                                            scheduled_time=extra
                                        )
                                st.rerun()
                            elif status == "conflict":
                                st.session_state[conflict_key] = extra
                                st.rerun()
                            elif status == "past_date":
                                st.session_state[past_key] = extra
                                st.rerun()
                            elif status == "no_slot":
                                st.error("No available time slots found in the next 2 days.")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")