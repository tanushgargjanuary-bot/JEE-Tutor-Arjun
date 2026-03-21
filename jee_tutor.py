"""Arjun - JEE Vertical Reasoning Engine (AIR 92 Elite Mentor)"""

import json
import os

import pandas as pd
import streamlit as st
from groq import Groq

from database import (
    init_database, create_user, authenticate_user, get_user_by_id,
    has_submitted_feedback, submit_feedback, is_pro_user,
    apply_referral_code, get_db_connection, get_or_create_google_user,
)
from prompts import PROMPTS
from google_auth import verify_google_token, get_google_client_id

ADMIN_PASSCODE = "FOUNDER_BETA_2026"


def get_groq_api_key():
    """Retrieve GROQ API key securely from st.secrets or environment."""
    try:
        return st.secrets["GROQ_API_KEY"]
    except (FileNotFoundError, KeyError, AttributeError):
        key = os.getenv("GROQ_API_KEY")
        if key:
            return key
        raise ValueError(
            "GROQ_API_KEY not found. Add to st.secrets or environment.")


client = Groq(api_key=get_groq_api_key())


def route_subject(user_query):
    """Classify a user query into subject category."""
    query_lower = user_query.strip().lower()
    if query_lower in ["hi", "hello", "hey", "who are you", "what is this"] or len(query_lower) < 4:
        return "GENERAL"
    if any(t in query_lower for t in ["syllabus", "date", "weightage", "tips", "strategy", "prep", "how to"]):
        return "GENERAL"
    try:
        classification = client.chat.completions.create(
            model="llama-3.3-70b-versatile", temperature=0.0,
            messages=[
                {"role": "system", "content": "Classify: PHYSICS, CHEMISTRY, or MATHEMATICS. Output ONLY one word."},
                {"role": "user", "content": user_query}
            ]
        )
        return classification.choices[0].message.content.strip().upper()
    except Exception:
        return "GENERAL"


st.set_page_config(page_title="Arjun - JEE Vertical Reasoner",
                   layout="wide", page_icon="🏹")
init_database()

for key in ['logged_in', 'user_data', 'feedback_submitted', 'show_admin', 'messages']:
    if key not in st.session_state:
        st.session_state[key] = False if key == 'logged_in' else (
            [] if key == 'messages' else None)


def show_feedback_page():
    """Render the feedback submission page."""
    st.subheader("📝 Submit Feedback")
    user = st.session_state.user_data

    if st.session_state.feedback_submitted:
        st.success("✅ Feedback already submitted! Thank you for your input.")
        st.info("Your referral code is now unlocked in the 🎁 Referrals section.")
        return

    st.markdown(
        "### Why Submit Feedback?\n- 🔓 **Unlock Referrals**\n- 📈 **Shape Arjun**\n- 🎁 **Earn PRO Days**")

    with st.form("feedback_form"):
        rating = st.slider("Rate Arjun (1-5)", 1, 5, 4)
        category = st.selectbox("Category", [
                                "General Feedback", "Bug Report", "Feature Request", "Success Story"])
        feedback_text = st.text_area(
            "Your Feedback", height=150, placeholder="Share your experience...")
        if st.form_submit_button("Submit Feedback", use_container_width=True):
            if len(feedback_text.strip()) < 10:
                st.error(
                    "Please provide more detailed feedback (at least 10 characters)")
            else:
                submit_feedback(
                    user['id'], feedback_text.strip(), rating, category)
                st.session_state.feedback_submitted = True
                st.session_state.user_data = get_user_by_id(user['id'])
                st.success(
                    "🎉 Feedback submitted! Your referral code is now unlocked!")
                st.balloons()
                st.rerun()


def show_referrals_page():
    """Render the referral program page."""
    user = st.session_state.user_data

    if not st.session_state.feedback_submitted:
        st.subheader("🎁 Referral Program")
        st.warning("🔒 Referral code is locked until you submit feedback.")
        st.info(
            "👈 Go to **Feedback** section to submit your review and unlock your referral code!")
        st.markdown("### How Referrals Work\n| Action | Reward |\n|--------|--------|\n| Friend signs up | They get **+2 days** PRO |\n| Friend signs up | You get **+3 days** PRO |")
        return

    st.subheader("🎁 Referral Program")
    st.success("🎉 Referral system unlocked!")
    st.markdown("### ✨ Your Referral Code")
    st.code(user.get('referral_code', 'N/A'), language="text")
    st.info(
        f"**Share with friends!**\n- They get **+2 days** PRO\n- You get **+3 days** PRO")

    st.divider()
    with st.form("apply_referral"):
        code_input = st.text_input(
            "Enter Referral Code", placeholder="Enter your friend's code")
        if st.form_submit_button("Apply Code", use_container_width=True):
            if code_input.strip():
                success, message = apply_referral_code(
                    user['id'], code_input.strip())
                if success:
                    st.success(message)
                    st.session_state.user_data = get_user_by_id(user['id'])
                    st.rerun()
                else:
                    st.error(message)

    st.divider()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE referred_by = ?",
                   (user.get('referral_code'),))
    referred_count = cursor.fetchone()['count']
    conn.close()
    st.metric("Friends Referred", referred_count)
    if referred_count > 0:
        st.write(f"**Total PRO Days Earned**: {referred_count * 3} days")


def show_profile_page():
    """Render the user profile page."""
    user = st.session_state.user_data
    st.subheader("👤 Your Profile")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Username", user['username'])
        st.metric("Email", user.get('email', 'Not provided'))
    with col2:
        st.metric("Status", "👑 PRO" if is_pro_user(user) else "⚡ BASIC")
        st.metric("Member Since", user.get('created_at', 'N/A'))

    st.divider()
    if is_pro_user(user):
        st.success(f"👑 PRO Access until: {user.get('pro_expiry', 'N/A')}")
    else:
        st.info("⚡ Complete daily problems and submit feedback to unlock PRO features!")

    st.divider()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT subject, COUNT(*) as count FROM query_log WHERE user_id = ? GROUP BY subject", (user['id'],))
    stats = cursor.fetchall()
    conn.close()
    if stats:
        st.bar_chart(pd.DataFrame(stats, columns=[
                     'Subject', 'Problems Solved']).set_index('Subject'))
    else:
        st.caption("No problems solved yet. Start learning!")


def show_admin_users():
    """Render admin console: Users table view."""
    st.subheader("🔐 Admin Console - Users")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
    users = cursor.fetchall()
    conn.close()
    if users:
        df = pd.DataFrame(users, columns=[desc[0]
                          for desc in cursor.description])
        display_df = df[['id', 'username', 'email', 'user_type',
                         'pro_expiry', 'referral_code', 'referred_by', 'created_at']].copy()
        display_df.columns = ['ID', 'Username', 'Email', 'Type',
                              'PRO Expiry', 'Ref Code', 'Referred By', 'Joined']
        st.dataframe(display_df, use_container_width=True)
        st.metric("Total Users", len(users))
    else:
        st.info("No users registered yet")


def show_admin_feedback():
    """Render admin console: Feedback table view."""
    st.subheader("🔐 Admin Console - Feedback")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT f.*, u.username FROM feedback f JOIN users u ON f.user_id = u.id ORDER BY f.submitted_at DESC")
    feedback = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    if feedback:
        df = pd.DataFrame(feedback, columns=columns)
        display_df = df[['id', 'username', 'feedback_text',
                         'rating', 'category', 'submitted_at']].copy()
        display_df.columns = ['ID', 'User', 'Feedback',
                              'Rating', 'Category', 'Submitted']
        st.dataframe(display_df, use_container_width=True)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Feedback", len(feedback))
        col2.metric("Avg Rating", f"{df['rating'].mean():.1f}/5")
        col3.metric("Response Rate", f"{len(feedback)} submissions")
    else:
        st.info("No feedback submitted yet")


def show_admin_queries():
    """Render admin console: Query analytics dashboard."""
    st.subheader("🔐 Admin Console - Query Analytics")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM query_log")
    total = cursor.fetchone()['count']
    cursor.execute(
        "SELECT subject, COUNT(*) as count FROM query_log GROUP BY subject")
    by_subject = cursor.fetchall()
    cursor.execute(
        "SELECT q.*, u.username FROM query_log q LEFT JOIN users u ON q.user_id = u.id ORDER BY q.timestamp DESC LIMIT 20")
    recent = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()

    col1, col2 = st.columns(2)
    col1.metric("Total Queries", total)
    if by_subject:
        col2.bar_chart(pd.DataFrame(by_subject, columns=[
                       'subject', 'count']).set_index('subject'))
    if recent:
        st.subheader("Recent Queries")
        df = pd.DataFrame(recent, columns=columns)
        display_df = df[['id', 'username', 'subject',
                         'query_text', 'timestamp']].copy()
        display_df.columns = ['ID', 'User', 'Subject', 'Query', 'Time']
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No queries logged yet")


# ============================================================================
# SIDEBAR NAVIGATION
# ============================================================================

with st.sidebar:
    st.image("https://img.icons8.com/color/96/target.png", width=60)
    st.title("🏹 Arjun")
    st.caption("AIR 92 Elite JEE Mentor")
    st.divider()

    if st.session_state.logged_in:
        user = st.session_state.user_data
        st.write(f"**Welcome, {user['username']}**")
        st.info(f"Status: {'👑 PRO' if is_pro_user(user) else '⚡ BASIC'}")
        if is_pro_user(user):
            st.caption(f"Pro expires: {user.get('pro_expiry', 'N/A')}")

        st.divider()
        page = st.radio("Navigate", [
                        "📚 Solve Problems", "📝 Feedback", "🎁 Referrals", "👤 Profile"], index=0)
        st.divider()

        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_data = None
            st.session_state.feedback_submitted = False
            st.rerun()

        if st.text_input("Admin Access", type="password", key="admin_input") == ADMIN_PASSCODE:
            st.session_state.show_admin = True
            st.rerun()

        if st.session_state.show_admin:
            st.divider()
            st.warning("🔐 ADMIN CONSOLE")
            if st.button("📊 View Users", use_container_width=True):
                page = "admin_users"
            if st.button("💬 View Feedback", use_container_width=True):
                page = "admin_feedback"
            if st.button("📈 Query Analytics", use_container_width=True):
                page = "admin_queries"
            if st.button("❌ Close Admin", use_container_width=True):
                st.session_state.show_admin = False
                st.rerun()

        if page == "📝 Feedback":
            show_feedback_page()
        elif page == "🎁 Referrals":
            show_referrals_page()
        elif page == "👤 Profile":
            show_profile_page()
        elif page == "admin_users":
            show_admin_users()
        elif page == "admin_feedback":
            show_admin_feedback()
        elif page == "admin_queries":
            show_admin_queries()

    else:
        auth_mode = st.radio("Account", ["Login", "Sign Up"])

        # Google OAuth Login (shown for both Login and Sign Up)
        st.divider()
        st.caption("Or continue with")

        client_id = get_google_client_id()
        if client_id:
            from streamlit_oauth import OAuth2Component
            oauth2 = OAuth2Component()

            if st.button("🔐 Sign in with Google", use_container_width=True):
                try:
                    result = oauth2.authorize_button(
                        name="Continue with Google",
                        client_id=client_id,
                        endpoint="https://accounts.google.com/o/oauth2/v2/auth",
                        token_endpoint="https://oauth2.googleapis.com/token",
                        redirect_uri="postmessage",
                        scope="openid email profile",
                        icon="data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Cpath fill='%23FFC107' d='M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8c-6.627 0-12-5.373-12-12c0-6.627 5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4C12.955 4 4 12.955 4 24c0 11.045 8.955 20 20 20c11.045 0 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z'/%3E%3Cpath fill='%23FF3D00' d='m6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z'/%3E%3Cpath fill='%234CAF50' d='M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.018 0-9.292-3.119-11.069-7.386l-6.533 5.042C9.906 41.59 16.433 44 24 44z'/%3E%3Cpath fill='%231976D2' d='M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z'/%3E%3C/svg%3E",
                        use_container_width=True
                    )

                    if result and 'token' in result:
                        token = result['token']
                        user_info = verify_google_token(
                            token.get('id_token', ''))

                        if user_info:
                            user = get_or_create_google_user(
                                user_info['email'],
                                user_info['name'],
                                user_info['google_id']
                            )

                            if user:
                                st.session_state.logged_in = True
                                st.session_state.user_data = user
                                st.session_state.feedback_submitted = has_submitted_feedback(
                                    user['id'])
                                st.success(f"Welcome, {user['username']}!")
                                st.rerun()
                            else:
                                st.error("Failed to create user account")
                        else:
                            st.error("Invalid Google token")
                except Exception as e:
                    st.error(f"Google login failed: {str(e)}")
        else:
            st.info("🔧 Google login not configured. Add credentials to secrets.toml")

        st.divider()

        if auth_mode == "Login":
            st.subheader("🔐 Login")
            if st.button("Login", use_container_width=True):
                user = authenticate_user(st.text_input("Username", key="login_user"), st.text_input(
                    "Password", type="password", key="login_pass"))
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_data = user
                    st.session_state.feedback_submitted = has_submitted_feedback(
                        user['id'])
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        else:
            st.subheader("📝 Create Account")
            new_username = st.text_input("Username", key="signup_user")
            new_password = st.text_input(
                "Password", type="password", key="signup_pass")
            confirm_password = st.text_input(
                "Confirm Password", type="password", key="signup_confirm")
            referral_input = st.text_input(
                "Referral Code (optional)", key="signup_referral")
            if st.button("Sign Up", use_container_width=True):
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                elif len(new_password) < 4:
                    st.error("Password must be at least 4 characters")
                else:
                    success, message = create_user(
                        new_username, new_password, None, referral_input)
                    st.success(message) if success else st.error(message)

st.divider()

# ============================================================================
# MAIN CONTENT AREA (Conversational Chat Interface)
# ============================================================================

if st.session_state.logged_in:
    st.header("📚 JEE Vertical Reasoning Engine")
    st.caption("Socratic Scaffolding • Trap Detection • NCERT Grounding")

    if not is_pro_user(st.session_state.user_data):
        st.warning(
            "⚡ BASIC Plan: Complete problems daily to unlock PRO features. Submit feedback to unlock referrals!")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask a JEE Physics, Chemistry, or Math question..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("🔬 Analyzing via Multi-Agent Chain..."):
                subject = route_subject(prompt)
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile", temperature=0.2,
                    messages=[{"role": "system", "content": PROMPTS.get(subject, PROMPTS["GENERAL"])}, {
                        "role": "user", "content": prompt}]
                )
                response = completion.choices[0].message.content
                st.markdown(response)

        st.session_state.messages.append(
            {"role": "assistant", "content": response})

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO query_log (user_id, subject, query_text, response_text, is_socratic, audit_notes) VALUES (?, ?, ?, ?, ?, ?)",
                       (st.session_state.user_data['id'], subject, prompt, response, True, "Audit skipped for latency"))
        conn.commit()
        conn.close()

else:
    st.header("🏹 Welcome to Arjun")
    st.subheader(
        "Elite JEE Mentor - Building Intuition, Not Just Solving Homework")
    st.markdown("### Why Arjun?\n**🎯 Socratic Scaffolding**: We guide you through conceptual questions.\n**⚡ Groq-Powered**: High-speed reasoning for JEE Advanced.\n**📚 NCERT Grounded**: Every solution cites relevant concepts.\n**🔍 Trap Detection**: We identify edge cases before you make mistakes.")
    st.info("👈 Login or Sign Up in the sidebar to start solving!")
