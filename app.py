"""
Streamlit Dashboard for Tenzing Growth Agent
Main interface for managing leads and viewing analytics
"""
import streamlit as st
import pandas as pd
import time
from datetime import date, datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Dict

from threading import Thread
from playwright.sync_api import sync_playwright
from scanner import FacebookScanner
from comment_worker import CommentWorker

from database import (
    init_db, LeadDatabase, GroupDatabase, SettingsDatabase,
    DailyStatsDatabase, FollowUpDatabase, AuditLogDatabase, get_session
)
from models import Lead
from analytics import Analytics
        # Ensure Date Formatting Inline !!!
from content_generator import ContentGenerator
from config import BUSINESS_NAME, FACEBOOK_PROFILE_PATH, LLM_PROVIDER


def _facebook_login_worker() -> None:
    """Open a login-only browser. The scanner never reuses this object."""
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                FACEBOOK_PROFILE_PATH,
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            page = context.new_page()
            page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")

            while True:
                try:
                    if not context.pages:
                        break
                except Exception:
                    break
                time.sleep(1)

            SettingsDatabase.set_setting("facebook_login_validated", "true")
            SettingsDatabase.set_setting("facebook_login_validated_at", datetime.utcnow().isoformat())
    except Exception as e:
        st.session_state["fb_login_error"] = str(e)
    finally:
        st.session_state["fb_login_running"] = False

# Page configuration
st.set_page_config(
    page_title=f"{BUSINESS_NAME} - Lead Manager",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
init_db()

if "scanner" not in st.session_state:
    st.session_state["scanner"] = FacebookScanner()

# Custom CSS
st.markdown("""
<style>
.metric-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
    border-radius: 10px;
    color: white;
    text-align: center;
}
.high-score { background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%); }
.medium-score { background: linear-gradient(135deg, #ffa500 0%, #ff6500 100%); }
.low-score { background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%); }
</style>
""", unsafe_allow_html=True)

# Sidebar - Global Controls
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/globe.png", width=80)
    st.title(BUSINESS_NAME)
    st.caption(f"LLM Provider Mode: {LLM_PROVIDER}")
    st.divider()
    
    # Scanner Controls
    st.subheader("🔍 Scanner Controls")

    use_groups = st.checkbox(
        "Use Group List for Scanning", value=True,
        help="If disabled, scanner processes home/feed page instead"
    )
    SettingsDatabase.set_setting("scan_use_groups", "true" if use_groups else "false")
    
    scanner_state = st.session_state.get("scanner")
    comment_worker_state = st.session_state.get("comment_worker")
    
    if "fb_login_running" not in st.session_state:
        st.session_state["fb_login_running"] = False
    if "fb_login_error" not in st.session_state:
        st.session_state["fb_login_error"] = ""

    if st.button("Login to Facebook", use_container_width=True):
        if st.session_state["fb_login_running"]:
            st.info("Facebook login browser is already open.")
        else:
            st.session_state["fb_login_running"] = True
            st.session_state["fb_login_error"] = ""
            Thread(target=_facebook_login_worker, daemon=True).start()
            st.success("Browser launched. Please log in, then close the browser window.")

    if st.button("I have completed Facebook login", use_container_width=True):
        SettingsDatabase.set_setting("facebook_login_validated", "true")
        SettingsDatabase.set_setting("facebook_login_validated_at", datetime.utcnow().isoformat())
        st.success("Facebook login marked as validated. Close the login browser before starting the scanner.")

    if st.session_state.get("fb_login_error"):
        st.error(f"Facebook login error: {st.session_state['fb_login_error']}")

    validated_login = SettingsDatabase.get_setting("facebook_login_validated", "false").lower() == "true"
    validated_login_at = SettingsDatabase.get_setting("facebook_login_validated_at", "")
    if validated_login:
        st.caption(f"Login status: validated ({validated_login_at or 'timestamp unavailable'})")
    else:
        st.caption("Login status: not validated")
            
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Scanner"):
            SettingsDatabase.set_setting("scan_enabled", "true")
            SettingsDatabase.set_setting("debug_visible_browser", "true")
            if scanner_state and not scanner_state.running:
                try:
                    scanner_state.start()
                    st.success("Scanner started.")
                except Exception as e:
                    st.error(f"Could not start scanner: {e}")
            else:
                st.warning("Scanner is already running.")
    with col2:
        if st.button("Stop Scanner"):
            if scanner_state and scanner_state.running:
                scanner_state.stop()
                st.session_state.pop("scanner", None)
                st.warning("Scanner stopped.")
            else:
                st.info("Scanner is not running.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Comment Worker"):
            if not comment_worker_state:
                comment_worker_state = CommentWorker()
                st.session_state["comment_worker"] = comment_worker_state
                Thread(target=comment_worker_state.start, daemon=True).start()
                st.success("Comment worker started.")
            else:
                st.warning("Comment worker is already running.")
    with col2:
        if st.button("Stop Comment Worker"):
            if comment_worker_state and comment_worker_state.running:
                comment_worker_state.stop()
                st.session_state.pop("comment_worker", None)
                st.warning("Comment worker stopped.")
            else:
                st.info("Comment Worker is not running.")
    
    # Posting Controls
    st.subheader("💬 Posting Controls")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Enable Posting", use_container_width=True):
            SettingsDatabase.set_setting("posting_enabled", "true")
            st.success("Auto-posting enabled!")
    with col2:
        if st.button("⏸️ Disable Posting", use_container_width=True):
            SettingsDatabase.set_setting("posting_enabled", "false")
            st.warning("Auto-posting disabled")
    
    st.divider()
    
    # Add Group
    st.subheader("➕ Add Facebook Group")
    group_url = st.text_input("Facebook Group URL")
    group_name = st.text_input("Group Name (optional)")
    if st.button("Add Group", use_container_width=True):
        if group_url:
            try:
                GroupDatabase.create_or_update_group(group_name or "Unknown", group_url)
                st.success("✅ Group added!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error adding group: {e}")
        else:
            st.error("Please enter a URL")
    
    st.divider()
    
    # Show Current Groups
    st.subheader("📍 Currently Monitoring")
    all_groups = GroupDatabase.get_all_groups()
    if all_groups:
        for group in all_groups:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"✅ {group.group_name}")
                st.caption(f"Found: {group.leads_found or 0} leads")
            with col2:
                if st.button("×", key=f"delete_{group.id}", help="Remove group"):
                    try:
                        from sqlalchemy import delete
                        from models import Group as GroupModel
                        from database import get_session
                        session = get_session()
                        session.execute(delete(GroupModel).where(GroupModel.id == group.id))
                        session.commit()
                        session.close()
                        st.success("✅ Group removed!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
    else:
        st.info("No groups added yet. Add one above!")
    
    st.divider()
    st.caption(f"📊 Dashboard v1.0")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Main content
st.title(f"🌍 {BUSINESS_NAME} - Lead Manager")

# Create tabs
tabs = st.tabs([
    "📌 Dashboard",
    "🆕 New Leads",
    "⭐ High Value",
    "✅ Approved",
    "❌ Rejected",
    "📤 Posted",
    "📋 Follow-ups",
    "📊 Analytics",
    "🔍 All Leads",
    "📝 Content"
])

# Tab 1: Dashboard
with tabs[0]:
    st.subheader("Overview")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total = Analytics.get_total_leads()
        st.metric("Total Leads", total, delta="+5 today")
    
    with col2:
        new_count = LeadDatabase.count_leads("NEW")
        st.metric("New Leads", new_count, delta="Pending review")
    
    with col3:
        high = Analytics.get_high_value_leads()
        st.metric("High Value", high, delta="Score ≥ 8")
    
    with col4:
        posted = LeadDatabase.count_leads("POSTED")
        st.metric("Posted", posted, delta="Comments sent")
    
    with col5:
        conv = Analytics.get_conversion_rate()
        st.metric("Conversion", f"{conv:.1f}%", delta="Posted/Total")
    
    st.divider()
    
    # Today's stats
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Today's Activity")
        today_stats = Analytics.get_today_stats()
        st.write(f"Groups scanned: **{today_stats['groups_scanned']}**")
        st.write(f"Posts read: **{today_stats['posts_read']}**")
        st.write(f"Leads found: **{today_stats['leads_found']}**")
        st.write(f"High-value leads: **{today_stats['leads_high_value']}**")
        st.write(f"Comments posted: **{today_stats['comments_posted']}**")
    
    with col2:
        st.subheader("Lead Distribution")
        status_counts = Analytics.get_leads_by_status()
        fig = px.pie(
            values=list(status_counts.values()),
            names=list(status_counts.keys()),
            hole=0.3
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # Lead score distribution
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Lead Score Distribution")
        dist = Analytics.get_lead_score_distribution()
        fig = px.bar(
            x=list(dist.keys()),
            y=list(dist.values()),
            labels={'x': 'Score Range', 'y': 'Count'},
            color=list(dist.keys()),
            color_discrete_sequence=px.colors.sequential.Blues[::-1]
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Leads by Day (Last 7 days)")
        chart_data = Analytics.get_leads_by_date_chart(days=7)
        df = pd.DataFrame(list(chart_data.items()), columns=['Date', 'Leads'])
        fig = px.line(df, x='Date', y='Leads', markers=True)
        st.plotly_chart(fig, use_container_width=True)

# Tab 2: New Leads
with tabs[1]:
    st.subheader("🆕 New Leads Awaiting Review")
    st.write("DEBUG")

    new_leads = LeadDatabase.get_leads_by_status("NEW")

    st.write(f"Retrieved {len(new_leads)} NEW leads")

    if len(new_leads) > 0:
        st.write(new_leads[0].id)
    new_leads = LeadDatabase.get_leads_by_status("NEW")
    
    if new_leads:
        # Filter options
        col1, col2, col3 = st.columns(3)
        with col1:
            min_score = st.slider("Minimum Score", 0, 10, 0)
        with col2:
            destination_filter = st.text_input("Destination Filter")
        with col3:
            intent_filter = st.selectbox("Intent Filter", ["All"] + list(set([l.intent for l in new_leads if l.intent])))
        
        # Apply filters
        filtered_leads = [
            l for l in new_leads
            if l.lead_score >= min_score
            and (not destination_filter or destination_filter.lower() in (l.destination or "").lower())
            and (intent_filter == "All" or l.intent == intent_filter)
        ]
        
        st.write(f"Showing {len(filtered_leads)} of {len(new_leads)} leads")
        
        # Bulk Actions for New Leads
        with st.expander("📦 Bulk Delete Actions for New Leads"):
            col_bulk1, col_bulk2 = st.columns(2)
            with col_bulk1:
                selected_new_leads = st.multiselect(
                    "Select new leads to delete:",
                    options=filtered_leads,
                    format_func=lambda l: f"ID {l.id} - {l.author} ({l.destination or 'N/A'})",
                    key="bulk_selected_new_leads"
                )
                if selected_new_leads:
                    if st.button("🗑️ Delete Selected Leads", key="btn_delete_selected_new"):
                        count = 0
                        for lead in selected_new_leads:
                            if LeadDatabase.delete_lead(lead.id):
                                count += 1
                        st.success(f"Deleted {count} lead(s)!")
                        st.rerun()
            with col_bulk2:
                st.write(f"There are **{len(filtered_leads)}** new leads matching the filter.")
                confirm_delete_all_new = st.checkbox("I confirm that I want to delete all matching new leads", key="confirm_delete_all_new")
                if st.button("🗑️ Delete All Matching Leads", key="btn_delete_all_new", disabled=not confirm_delete_all_new):
                    count = 0
                    for lead in filtered_leads:
                        if LeadDatabase.delete_lead(lead.id):
                            count += 1
                    st.success(f"Deleted {count} matching lead(s)!")
                    st.rerun()
        
        for lead in filtered_leads:
            with st.expander(f"**{lead.author}** - {lead.destination or 'N/A'} (Score: {lead.lead_score}/10)"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"**Group:** {lead.group_name}")
                    st.write(f"**Post:** {lead.post_text[:200]}...")
                    st.write(f"**Intent:** {lead.intent}")
                    st.write(f"**Travel Date:** {lead.travel_date or 'Not mentioned'}")
                    st.write(f"**Group Size:** {lead.group_size or 'Not mentioned'}")
                    st.write(f"**Budget:** {lead.budget or 'Not mentioned'}")
                    st.write(f"**Reason for Score:** {lead.reason}")
                    st.write(f"**Post:** [View on Facebook]({lead.post_url})")
                    st.write("---")
                    st.write(f"**Suggested Reply:**\n{lead.suggested_reply}")
                
                with col2:
                    if st.button("✅ Approve", key=f"approve_{lead.id}"):
                        LeadDatabase.update_lead(lead.id, status="APPROVED")
                        AuditLogDatabase.log_action(lead.id, "APPROVED", "User approved")
                        st.success("Approved!")
                        st.rerun()
                    
                    if st.button("✏️ Edit", key=f"edit_{lead.id}"):
                        st.session_state[f"edit_{lead.id}"] = True
                    
                    if st.button("❌ Reject", key=f"reject_{lead.id}"):
                        LeadDatabase.update_lead(lead.id, status="REJECTED")
                        AuditLogDatabase.log_action(lead.id, "REJECTED", "User rejected")
                        st.warning("Rejected!")
                        st.rerun()

                    if st.button("🗑️ Delete", key=f"delete_lead_{lead.id}"):
                        LeadDatabase.delete_lead(lead.id)
                        st.success("Lead deleted!")
                        st.rerun()
                    
                    if st.session_state.get(f"edit_{lead.id}"):
                        st.write("---")
                        new_reply = st.text_area("Edit reply:", value=lead.suggested_reply, key=f"reply_{lead.id}")
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("💾 Save & Approve", key=f"save_{lead.id}"):
                                LeadDatabase.update_lead(lead.id, status="APPROVED", suggested_reply=new_reply)
                                AuditLogDatabase.log_action(lead.id, "APPROVED", "User edited and approved")
                                st.success("Saved and approved!")
                                st.rerun()
                        with col_b:
                            if st.button("Cancel", key=f"cancel_{lead.id}"):
                                st.session_state[f"edit_{lead.id}"] = False
                                st.rerun()
    else:
        st.info("✨ No new leads yet!")

# Tab 3: High Value Leads
with tabs[2]:
    st.subheader("⭐ High Value Leads (Score ≥ 8)")
    
    session = get_session()
    high_value = session.query(Lead).filter(Lead.lead_score >= 8).order_by(Lead.created_at.desc()).all()
    session.close()
    
    if high_value:
        df_data = []
        for lead in high_value:
            df_data.append({
                "Author": lead.author,
                "Destination": lead.destination or "N/A",
                "Score": lead.lead_score,
                "Intent": lead.intent,
                "Status": lead.status,
                "Created": lead.created_at.strftime("%Y-%m-%d")
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
        
        # Export button
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"high_value_leads_{date.today()}.csv",
            mime="text/csv"
        )
    else:
        st.info("No high value leads yet")


# Tab 4-7: Other status tabs
status_tabs = [
    ("✅ Approved", "APPROVED"),
    ("❌ Rejected", "REJECTED"),
    ("📤 Posted", "POSTED"),
    ("📋 Follow-ups", "FOLLOW_UP")
]

for tab_idx, (tab_name, status) in enumerate(status_tabs, start=3):
    with tabs[tab_idx]:
        st.subheader(f"{tab_name} Leads")
        
        if status == "FOLLOW_UP":
            # Special handling for follow-ups
            followups = FollowUpDatabase.get_upcoming_followups()
            if followups:
                df_data = []
                for fu in followups:
                    df_data.append({
                        "Lead": fu.lead.author,
                        "Date": fu.followup_date,
                        "Note": fu.note,
                        "Completed": fu.completed
                    })
                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No upcoming follow-ups")
        else:
            leads = LeadDatabase.get_leads_by_status(status)
            if leads:
                df_data = []
                for lead in leads:
                    df_data.append({
                        "Author": lead.author,
                        "Group": lead.group_name,
                        "Destination": lead.destination or "N/A",
                        "Score": lead.lead_score,
                        "Intent": lead.intent,
                        "Created": lead.created_at.strftime("%Y-%m-%d %H:%M")
                    })
                
                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True)
                
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"leads_{status.lower()}_{date.today()}.csv",
                    mime="text/csv"
                )
            else:
                st.info(f"No {status.lower()} leads yet")

# Tab 8: Analytics
with tabs[7]:
    st.subheader("📊 Analytics & Insights")
    
    # Top destinations
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Top Destinations")
        top_dest = Analytics.get_top_destinations(limit=10)
        if top_dest:
            df = pd.DataFrame(top_dest, columns=['Destination', 'Count'])
            fig = px.bar(df, x='Destination', y='Count', color='Count', color_continuous_scale='Viridis')
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Top Groups")
        top_groups = Analytics.get_top_groups(limit=10)
        if top_groups:
            df = pd.DataFrame(top_groups, columns=['Group', 'Count'])
            fig = px.bar(
                df,
                x='Count',
                y='Group',
                orientation='h',
                color='Count',
                color_continuous_scale='Plasma'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # Group Performance
    st.subheader("Group Performance Metrics")
    performance = Analytics.get_group_performance()
    if performance:
        df = pd.DataFrame(performance)
        st.dataframe(df, use_container_width=True)

# Tab 9: All Leads
with tabs[8]:
    st.subheader("🔍 All Leads - Advanced Search")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        search_author = st.text_input("Search Author")
    with col2:
        search_destination = st.text_input("Search Destination")
    with col3:
        filter_status = st.multiselect("Status", ["NEW", "REVIEWING", "APPROVED", "REJECTED", "POSTED", "FOLLOW_UP", "CLOSED"], default=["NEW"])
    with col4:
        min_score = st.slider("Min Score", 0, 10, 0)
    
    # Execute search
    all_leads = LeadDatabase.get_all_leads(limit=100)
    
    filtered_leads = [
        l for l in all_leads
        if (not search_author or search_author.lower() in l.author.lower())
        and (not search_destination or search_destination.lower() in (l.destination or "").lower())
        and l.status in filter_status
        and l.lead_score >= min_score
    ]
    
    if filtered_leads:
        df_data = []
        for lead in filtered_leads:
            df_data.append({
                "ID": lead.id,
                "Author": lead.author,
                "Group": lead.group_name,
                "Destination": lead.destination or "N/A",
                "Score": lead.lead_score,
                "Intent": lead.intent,
                "Status": lead.status,
                "Created": lead.created_at.strftime("%Y-%m-%d")
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"all_leads_{date.today()}.csv",
            mime="text/csv"
        )

        # Bulk actions section
        st.write("---")
        st.subheader("📦 Bulk Lead Actions")
        col_bulk1, col_bulk2 = st.columns(2)
        with col_bulk1:
            selected_leads = st.multiselect(
                "Select leads to delete:",
                options=filtered_leads,
                format_func=lambda l: f"ID {l.id} - {l.author} ({l.destination or 'N/A'})",
                key="bulk_selected_leads"
            )
            
            if selected_leads:
                st.write(f"Selected **{len(selected_leads)}** lead(s).")
                if st.button("🗑️ Delete Selected Leads", key="delete_selected_btn"):
                    for lead in selected_leads:
                        LeadDatabase.delete_lead(lead.id)
                    st.success(f"Successfully deleted {len(selected_leads)} lead(s)!")
                    st.rerun()
                    
        with col_bulk2:
            st.write(f"There are **{len(filtered_leads)}** leads matching current search filters.")
            
            # Confirm checkbox to prevent accidental click
            confirm_delete_all = st.checkbox("I confirm that I want to delete all matching leads", key="confirm_delete_all")
            if st.button("🗑️ Delete All Matching Leads", key="delete_all_matching_btn", disabled=not confirm_delete_all):
                count = 0
                for lead in filtered_leads:
                    if LeadDatabase.delete_lead(lead.id):
                        count += 1
                st.success(f"Successfully deleted {count} matching lead(s)!")
                st.rerun()

        # Lead management section
        st.write("---")
        st.subheader("✏️ Review, Update, or Delete a Lead")
        lead_options = {f"ID {l.id} - {l.author} ({l.destination or 'No destination'})": l for l in filtered_leads}
        selected_option = st.selectbox("Select a lead to update or delete:", ["-- Select a lead --"] + list(lead_options.keys()))
        
        if selected_option != "-- Select a lead --":
            selected_lead = lead_options[selected_option]
            
            # Show details and editable fields
            with st.container():
                col_edit1, col_edit2 = st.columns([2, 1])
                with col_edit1:
                    st.write(f"**Author:** {selected_lead.author} | **Group:** {selected_lead.group_name}")
                    st.write(f"**Post Link:** [View on Facebook]({selected_lead.post_url})")
                    st.write("**Post Content:**")
                    st.info(selected_lead.post_text)
                    
                    # Editable fields
                    new_reply = st.text_area("Suggested Reply", value=selected_lead.suggested_reply or "", key=f"all_reply_{selected_lead.id}")
                    new_notes = st.text_area("Notes", value=selected_lead.notes or "", key=f"all_notes_{selected_lead.id}")
                
                with col_edit2:
                    status_list = ["NEW", "REVIEWING", "APPROVED", "REJECTED", "POSTED", "FOLLOW_UP", "CLOSED"]
                    try:
                        status_index = status_list.index(selected_lead.status)
                    except ValueError:
                        status_index = 0
                        
                    new_status = st.selectbox(
                        "Status",
                        status_list,
                        index=status_index,
                        key=f"all_status_{selected_lead.id}"
                    )
                    new_dest = st.text_input("Destination", value=selected_lead.destination or "", key=f"all_dest_{selected_lead.id}")
                    new_intent = st.text_input("Intent", value=selected_lead.intent or "", key=f"all_intent_{selected_lead.id}")
                    new_score = st.slider("Score", 0, 10, int(selected_lead.lead_score or 0), key=f"all_score_{selected_lead.id}")
                    
                    st.write("")
                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if st.button("💾 Save Changes", key=f"all_save_{selected_lead.id}", use_container_width=True):
                            success = LeadDatabase.update_lead(
                                selected_lead.id,
                                status=new_status,
                                destination=new_dest,
                                intent=new_intent,
                                lead_score=new_score,
                                suggested_reply=new_reply,
                                notes=new_notes
                            )
                            if success:
                                AuditLogDatabase.log_action(selected_lead.id, "UPDATED", f"Updated details via search page. Status: {new_status}")
                                st.success("Changes saved!")
                                st.rerun()
                            else:
                                st.error("Failed to save changes.")
                    with c_btn2:
                        if st.button("🗑️ Delete Lead", key=f"all_delete_{selected_lead.id}", use_container_width=True):
                            success = LeadDatabase.delete_lead(selected_lead.id)
                            if success:
                                st.success("Lead deleted successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to delete lead.")
    else:
        st.info("No leads found matching criteria")

# Tab 10: Content
with tabs[9]:
    st.subheader("📝 Content Generation")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("Generate daily Facebook travel content suggestions")
    
    with col2:
        if st.button("🎨 Generate Content"):
            generator = ContentGenerator()
            content = generator.generate_daily_content()
            if content:
                st.success("Content generated!")
                st.write(content)
            else:
                st.error("Failed to generate content")
    
    st.divider()
    
    st.subheader("Pending Review")
    generator = ContentGenerator()
    pending = generator.get_pending_content()
    
    if pending:
        for item in pending:
            with st.expander(f"**{item.topic}** - {item.created_at.strftime('%Y-%m-%d %H:%M')}"):
                st.write(item.content_text)
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("✅ Approve", key=f"approve_content_{item.id}"):
                        generator.approve_content(item.id)
                        st.success("Approved!")
                        st.rerun()
                with col2:
                    if st.button("📤 Mark Posted", key=f"posted_content_{item.id}"):
                        generator.mark_posted(item.id)
                        st.success("Marked as posted!")
                        st.rerun()
                with col3:
                    if st.button("🗑️ Delete", key=f"delete_content_{item.id}"):
                        if generator.delete_content(item.id):
                            st.success("Deleted!")
                            st.rerun()
                        else:
                            st.error("Failed to delete content.")
    else:
        st.info("No content pending review")

# Footer
st.divider()
st.caption(f"🌍 {BUSINESS_NAME} - AI-Powered Lead Manager | Powered by Ollama (Qwen3)")
