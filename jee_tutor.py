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
from google_auth import get_google_client_id, get_google_client_secret, get_redirect_uri
from mermaid_renderer import extract_and_render_mermaid, extract_csv_coordinates, remove_csv_blocks

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
    """Classify a user query into subject category (aggressive detection)."""
    query_lower = user_query.strip().lower()

    # Greetings & short talk → GENERAL
    if query_lower in ["hi", "hello", "hey", "who are you", "what is this"] or len(query_lower) < 4:
        return "GENERAL"

    # Admin/strategy keywords → GENERAL
    if any(t in query_lower for t in ["syllabus", "date", "weightage", "tips", "strategy", "prep", "how to"]):
        return "GENERAL"

    # Aggressive PHYSICS detection (keyword-based, before AI classification)
    physics_keywords = [
        "block", "incline", "friction", "mass", "force", "velocity", "acceleration",
        "newton", "momentum", "energy", "work", "power", "gravity", "tension",
        "pulley", "spring", "oscillation", "wave", "lens", "mirror", "refraction",
        "electric", "magnetic", "field", "circuit", "current", "voltage", "resistance",
        "capacitor", "inductor", "emf", "flux", "potential", "kinetic", "thermo",
        "entropy", "pressure", "density", "buoyancy", "torque", "angular", "rotation"
    ]
    if any(kw in query_lower for kw in physics_keywords):
        return "PHYSICS"

    # Aggressive CHEMISTRY detection
    chemistry_keywords = [
        "reaction", "compound", "molecule", "bond", "electron", "orbital", "acid",
        "base", "ph", "oxidation", "reduction", "redox", "catalyst", "equilibrium",
        "organic", "inorganic", "polymer", "isomer", "benzene", "functional group",
        "stoichiometry", "mole", "concentration", "titration", "precipitate", "ion"
    ]
    if any(kw in query_lower for kw in chemistry_keywords):
        return "CHEMISTRY"

    # Aggressive MATHEMATICS detection
    math_keywords = [
        "function", "derivative", "integral", "limit", "continuity", "differential",
        "equation", "algebra", "calculus", "matrix", "determinant", "vector",
        "probability", "statistics", "trigonometry", "sin", "cos", "tan", "log",
        "sequence", "series", "progression", "permutation", "combination", "set theory"
    ]
    if any(kw in query_lower for kw in math_keywords):
        return "MATHEMATICS"

    # Fallback to AI classification for ambiguous queries
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

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_data' not in st.session_state:
    st.session_state.user_data = None
if 'feedback_submitted' not in st.session_state:
    st.session_state.feedback_submitted = False
if 'show_admin' not in st.session_state:
    st.session_state.show_admin = False
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'pending_prompt' not in st.session_state:
    st.session_state.pending_prompt = None
if 'mode_selected' not in st.session_state:
    st.session_state.mode_selected = None


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

        # Google OAuth
        st.divider()
        st.caption("Or continue with")

        client_id = get_google_client_id()
        client_secret = get_google_client_secret()
        redirect_uri = get_redirect_uri()

        if client_id and client_secret:
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests
            import requests as http_requests

            google_auth_url = (
                f"https://accounts.google.com/o/oauth2/v2/auth?"
                f"client_id={client_id}&"
                f"redirect_uri={redirect_uri}&"
                f"response_type=code&"
                f"scope=openid%20email%20profile&"
                f"access_type=offline&"
                f"prompt=select_account"
            )

            if st.button("🔐 Sign in with Google", use_container_width=True):
                st.info(
                    f"👉 [**Click here to sign in with Google**]({google_auth_url})")
                st.caption("A Google popup will appear. Select your account.")

                query_params = st.query_params
                auth_code = query_params.get("code")

                if auth_code:
                    try:
                        token_response = http_requests.post(
                            "https://oauth2.googleapis.com/token",
                            data={
                                "code": auth_code,
                                "client_id": client_id,
                                "client_secret": client_secret,
                                "redirect_uri": redirect_uri,
                                "grant_type": "authorization_code"
                            },
                            timeout=10
                        )
                        token_data = token_response.json()

                        if "id_token" in token_data:
                            id_info = id_token.verify_oauth2_token(
                                token_data["id_token"],
                                google_requests.Request(),
                                client_id
                            )

                            user = get_or_create_google_user(
                                id_info.get("email"),
                                id_info.get("name"),
                                id_info.get("sub")
                            )

                            if user:
                                st.session_state.logged_in = True
                                st.session_state.user_data = user
                                st.session_state.feedback_submitted = has_submitted_feedback(
                                    user['id'])
                                st.success(f"Welcome, {user['username']}!")
                                st.query_params.clear()
                                st.rerun()
                            else:
                                st.error("Failed to create user account")
                        else:
                            st.error(f"Invalid token response: {token_data}")
                    except Exception as e:
                        st.error(f"Google login failed: {str(e)}")
        else:
            st.info("🔧 Google login not configured. Add credentials to secrets.toml")

        st.divider()

        if auth_mode == "Login":
            st.subheader("🔐 Login")
            login_username = st.text_input("Username", key="login_user")
            login_password = st.text_input(
                "Password", type="password", key="login_pass")

            if st.button("Login", use_container_width=True):
                if login_username and login_password:
                    user = authenticate_user(login_username, login_password)
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
                    st.warning("Please enter username and password")
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
                    if success:
                        st.success(message)
                    else:
                        st.error(message)

st.divider()

# ============================================================================
# MAIN CONTENT AREA (Conversational Chat Interface with Mode Selection)
# ============================================================================

if st.session_state.logged_in:
    st.header("📚 JEE Vertical Reasoning Engine")
    st.caption("Choose your learning mode for each question")

    if not is_pro_user(st.session_state.user_data):
        st.warning(
            "⚡ BASIC Plan: Complete problems daily to unlock PRO features. Submit feedback to unlock referrals!")

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            content = message["content"]
            content = extract_and_render_mermaid(content)
            coords = extract_csv_coordinates(content)
            if coords:
                df = pd.DataFrame(coords, columns=['x', 'y'])
                st.line_chart(df.set_index('x'))
                content = remove_csv_blocks(content)
            st.markdown(content)

    # Mode selection UI
    if st.session_state.pending_prompt and not st.session_state.mode_selected:
        st.divider()
        st.info("🎯 Choose your learning mode:")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("🚀 Quick Solve", use_container_width=True, key="quick_solve_btn"):
                st.session_state.mode_selected = "direct"
                st.rerun()

        with col2:
            if st.button("🧠 Socratic Guide", use_container_width=True, key="socratic_btn"):
                st.session_state.mode_selected = "socratic"
                st.rerun()

        if st.button("❌ Cancel", use_container_width=True, key="cancel_btn"):
            st.session_state.pending_prompt = None
            st.rerun()
        st.stop()

    # Process if mode selected
    if st.session_state.pending_prompt and st.session_state.mode_selected:
        prompt = st.session_state.pending_prompt
        mode = st.session_state.mode_selected

        # Show user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Show assistant response
        with st.chat_message("assistant"):
            with st.spinner("🔬 Analyzing..."):
                subject = route_subject(prompt)
                subject_prompts = PROMPTS.get(subject, PROMPTS["GENERAL"])
                system_prompt = subject_prompts.get(
                    mode, subject_prompts["socratic"])

                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile", temperature=0.2,
                    messages=[{"role": "system", "content": system_prompt}, {
                        "role": "user", "content": prompt}]
                )
                response = completion.choices[0].message.content

                # Render and display
                response = extract_and_render_mermaid(response)
                coords = extract_csv_coordinates(response)
                if coords:
                    df = pd.DataFrame(coords, columns=['x', 'y'])
                    st.line_chart(df.set_index('x'))
                    response = remove_csv_blocks(response)
                st.markdown(response)

        # Save to history and DB
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append(
            {"role": "assistant", "content": response})

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO query_log (user_id, subject, query_text, response_text, is_socratic, audit_notes) VALUES (?, ?, ?, ?, ?, ?)",
            (st.session_state.user_data['id'], subject, prompt,
             response, mode == "socratic", f"Mode: {mode}")
        )
        conn.commit()
        conn.close()

        # Reset state
        st.session_state.pending_prompt = None
        st.session_state.mode_selected = None
        st.rerun()

    # Chat input - only shows when no pending prompt
    if not st.session_state.pending_prompt:
        if prompt := st.chat_input("Ask a JEE Physics, Chemistry, or Math question..."):
            st.session_state.pending_prompt = prompt
            st.rerun()

else:
    st.header("🏹 Welcome to Arjun")
    st.subheader(
        "Elite JEE Mentor - Building Intuition, Not Just Solving Homework")
    st.markdown("### Why Arjun?\n**🎯 Socratic Scaffolding**: We guide you through conceptual questions.\n**⚡ Groq-Powered**: High-speed reasoning for JEE Advanced.\n**📚 NCERT Grounded**: Every solution cites relevant concepts.\n**🔍 Trap Detection**: We identify edge cases before you make mistakes.")
    st.info("👈 Login or Sign Up in the sidebar to start solving!")
