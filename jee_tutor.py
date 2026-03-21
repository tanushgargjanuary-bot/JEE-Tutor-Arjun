<<<<<<< HEAD
"""Arjun - JEE Vertical Reasoning Engine (AIR 92 Elite Mentor)"""

import json
import os

import pandas as pd
import streamlit as st
from groq import Groq

from database import (
    init_database, create_user, authenticate_user, get_user_by_id,
    has_submitted_feedback, submit_feedback, is_pro_user,
    apply_referral_code, get_db_connection,
)
from prompts import PROMPTS

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
=======
import streamlit as st
import sqlite3
import hashlib
import time
import pandas as pd
from groq import Groq
from datetime import datetime, date

# --- 1. DATABASE SETUP ---
def db_execute(query, params=(), fetchone=False, fetchall=False, commit=True):
    conn = sqlite3.connect('user_data.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute(query, params)
        if fetchone: return c.fetchone()
        if fetchall: return c.fetchall()
        if commit: conn.commit()
    finally:
        conn.close()

def ensure_database_schema():
    db_execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    columns_to_add = [
        ("referral_code", "TEXT"), ("pro_expiry", "DATE"),
        ("total_referrals", "INTEGER DEFAULT 0"), ("tos_agreed", "INTEGER DEFAULT 0"),
        ("payment_intent", "TEXT"), ("user_summary", "TEXT") 
    ]
    for col_name, col_type in columns_to_add:
        try: db_execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError: pass 
    db_execute('''CREATE TABLE IF NOT EXISTS referrals 
                 (referrer_id TEXT, referee_id TEXT, timestamp DATETIME, PRIMARY KEY (referrer_id, referee_id))''')
    db_execute('''CREATE TABLE IF NOT EXISTS feedback 
                 (username TEXT, timestamp DATETIME, feedback_text TEXT)''')

def migrate_referral_codes():
    """One-time migration: populate referral_code for any user that doesn't have one yet."""
    users_missing_code = db_execute(
        "SELECT username FROM users WHERE referral_code IS NULL OR referral_code = ''",
        fetchall=True
    )
    if users_missing_code:
        for (uname,) in users_missing_code:
            code = hashlib.sha256(uname.encode()).hexdigest()[:6].upper()
            db_execute("UPDATE users SET referral_code = ? WHERE username = ?", (code, uname))

ensure_database_schema()
migrate_referral_codes()

# --- 2. UI & CSS ---
st.set_page_config(page_title="Arjun | JEE Mentor", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    header {visibility: hidden;} footer {visibility: hidden;} #MainMenu {visibility: hidden;}
    .stApp { background: radial-gradient(circle at top right, #1e2129, #0e1117); font-family: 'Inter', sans-serif; }
    [data-testid="stChatMessage"] { background-color: #1c2128; border: 1px solid #30363d; border-radius: 12px; margin-bottom: 10px; }
    div.stButton > button:first-child { background: linear-gradient(135deg, #238636 0%, #2ea043 100%); color: white; border-radius: 8px; font-weight: bold; width: 100%; border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIC & HELPERS ---
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("🔑 Groq API Key missing! Please add it to .streamlit/secrets.toml")
    st.stop()

if 'username' not in st.session_state: st.session_state.username = "Tanush"

if 'user_data' not in st.session_state:
    data = db_execute("SELECT tos_agreed, pro_expiry, user_summary, referral_code FROM users WHERE username = ?", (st.session_state.username,), fetchone=True)
    if data:
        # If the referral code is missing in DB, generate and save it
        if not data[3]:
            ref_code = hashlib.sha256(st.session_state.username.encode()).hexdigest()[:6].upper()
            db_execute("UPDATE users SET referral_code = ? WHERE username = ?", (ref_code, st.session_state.username))
            data = (data[0], data[1], data[2], ref_code)
    else:
        # New user entry
        ref_code = hashlib.sha256(st.session_state.username.encode()).hexdigest()[:6].upper()
        db_execute("INSERT INTO users (username, referral_code) VALUES (?, ?)", (st.session_state.username, ref_code))
        data = (0, None, "New student. Let's build your AIR profile.", ref_code)
    st.session_state.user_data = data

if 'feedback_submitted' not in st.session_state:
    st.session_state.feedback_submitted = bool(db_execute("SELECT 1 FROM feedback WHERE username = ?", (st.session_state.username,), fetchone=True))

def generate_ref_code(username):
    return hashlib.sha256(username.encode()).hexdigest()[:6].upper()

def process_referral(current_user, entered_code):
    entered_code = entered_code.strip().upper()  # Sanitize input
    if not entered_code:
        return "⚠️ Please enter a referral code."
    if entered_code == "FOUNDER_BETA_2026":
        db_execute("UPDATE users SET pro_expiry = '2027-01-01' WHERE username = ?", (current_user,))
        return "👑 Founder's access granted."

    if entered_code == generate_ref_code(current_user):
        return "🚫 No self-referrals."

    # Instant lookup using the referral_code column
    referrer = db_execute("SELECT username FROM users WHERE referral_code = ?", (entered_code,), fetchone=True)

    if not referrer:
        return "❌ Code not found."
    
    referrer_username = referrer[0]

    if db_execute("SELECT 1 FROM referrals WHERE referee_id = ?", (current_user,), fetchone=True):
        return "⚠️ You've already used a code."

    # Ensure referrer exists in table and give rewards
    db_execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (referrer_username,))
    db_execute("UPDATE users SET pro_expiry = DATE(COALESCE(pro_expiry, CURRENT_DATE), '+3 days'), total_referrals = COALESCE(total_referrals, 0) + 1 WHERE username = ?", (referrer_username,))
    db_execute("UPDATE users SET pro_expiry = DATE(COALESCE(pro_expiry, CURRENT_DATE), '+2 days') WHERE username = ?", (current_user,))
    db_execute("INSERT INTO referrals (referrer_id, referee_id, timestamp) VALUES (?, ?, ?)", (referrer_username, current_user, datetime.now()))
    
    # Invalidate cache
    if 'user_data' in st.session_state: del st.session_state.user_data
    
    return f"✅ Success! You got 2 days and {referrer_username} got 3 days of Pro."

# --- 4. THE TERMS OF SERVICE FIX ---
user_info = st.session_state.user_data
# Priority 1: Check Session State, Priority 2: Check Database
if 'tos_confirmed' not in st.session_state:
    st.session_state.tos_confirmed = user_info[0] if user_info else 0

if not st.session_state.tos_confirmed:
    @st.dialog("📜 Welcome to Arjun")
    def tos_dialog():
        st.write("### Founder's Terms")
        st.write("1. Arjun is an **intuition builder**, not a calculator.")
        st.write("2. We use Socratic teaching. Don't ask for direct answers.")
        st.write("3. You agree to verify critical data with official textbooks.")
        if st.button("I Agree & Start Learning", type="primary", use_container_width=True):
            db_execute("UPDATE users SET tos_agreed = 1 WHERE username = ?", (st.session_state.username,))
            st.session_state.tos_confirmed = 1
            if 'user_data' in st.session_state: del st.session_state.user_data
            st.rerun() # Force clear the dialog
    tos_dialog()
    st.stop()

# --- 5. DASHBOARD DATA ---
is_pro = bool(user_info and user_info[1] and datetime.strptime(user_info[1], '%Y-%m-%d').date() >= date.today())
memory_context = user_info[2] if user_info and user_info[2] else "New student. Let's build your AIR profile."

@st.dialog("💎 Upgrade to Pro")
def show_pricing():
    st.write("Unlock the full power of Arjun.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Monthly - ₹499"): 
            db_execute("UPDATE users SET payment_intent = 'Monthly' WHERE username = ?", (st.session_state.username,))
            st.toast("Team notified!")
    with c2:
        if st.button("Yearly - ₹3,999", type="primary"):
            db_execute("UPDATE users SET payment_intent = 'Yearly' WHERE username = ?", (st.session_state.username,))
            st.toast("Team notified!")

# --- 6. LAYOUT ---
col_dash, col_chat = st.columns([1, 2.5], gap="large")

with col_dash:
    st.title("🏹 Arjun")
    st.caption("JEE Mentor • AIR 92")
    
    # Clean, native Streamlit containers instead of hacky HTML
    with st.container(border=True):
        st.markdown("**Mentor Memo:**")
        st.caption(memory_context)
        
    with st.container(border=True):
        if is_pro: 
            st.success("⭐ PRO ACTIVE")
        else:
            st.info("⚪ BASIC")
            if st.button("🚀 Upgrade", use_container_width=True): show_pricing()
            
    with st.container(border=True):
        st.markdown("**Your Feedback**")
        if not st.session_state.feedback_submitted:
            f_text = st.text_area("How is Arjun helping you today?", placeholder="My first impression is...", key="f_input")
            if st.button("Submit Feedback", use_container_width=True):
                if f_text.strip():
                    ref_code = generate_ref_code(st.session_state.username)
                    db_execute("INSERT INTO feedback (username, timestamp, feedback_text) VALUES (?, ?, ?)", 
                             (st.session_state.username, datetime.now(), f_text))
                    db_execute("UPDATE users SET referral_code = ? WHERE username = ?", (ref_code, st.session_state.username))
                    st.session_state.feedback_submitted = True
                    if 'user_data' in st.session_state: del st.session_state.user_data
                    st.success("Thank you!")
                    st.rerun()
                else:
                    st.warning("Please enter some feedback first!")
        else:
            st.success("✅ Feedback submitted. Thanks for the review!")
            
    with st.container(border=True):
        if not st.session_state.feedback_submitted:
            st.write("🎁 **Referral Code**")
            st.info("Unlock your Referral Code by sharing your first impression of Arjun.")
        else:
            st.write("🎁 **Referral Code**")
            st.code(user_info[3], language=None)
            
            st.divider()
            
            ref_input = st.text_input("Friend's Code", placeholder="Enter code...", key="ref_input")
            if st.button("Apply Code", use_container_width=True): 
                result = process_referral(st.session_state.username, ref_input)
                st.toast(result)
                if "✅" in result:
                    st.rerun()  # Refresh Pro status immediately
            
    with st.expander("⚙️ Admin Console"):
        if st.text_input("Passcode", type="password") == "FOUNDER_BETA_2026":
            conn = sqlite3.connect('user_data.db')
            st.dataframe(pd.read_sql_query("SELECT username, payment_intent FROM users WHERE payment_intent IS NOT NULL", conn))
            st.dataframe(pd.read_sql_query("SELECT username, referral_code, pro_expiry, total_referrals FROM users", conn))
            st.markdown("### User Feedback")
            st.dataframe(pd.read_sql_query("SELECT * FROM feedback", conn))
            conn.close()

# --- 7. CHAT & BRAIN ---
with col_chat:
    st.header("Ask Arjun")
    if "messages" not in st.session_state:
        welcome_text = (
            "I am Arjun. I ranked in the **Top 100 in JEE**, and I'm here to ensure you do the same. "
            "I'm not just a calculator; I'm your guide for the next 2 years. "
            "I won't give you answers—I'll give you the intuition to solve anything they throw at you. "
            "What concept are we mastering today?"
        )
        st.session_state.messages = [{"role": "assistant", "content": welcome_text}]

    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Ask about Physics, Chemistry, or Math..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with col_chat:
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            sys = f"You are Arjun (AIR 92). Elite JEE mentor. Use STRICT Socratic Scaffolding. Lead with one conceptual question. Memory: {memory_context}. Use LaTeX for math."
            api_messages = [{"role": "system", "content": sys}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages if m["content"].strip()]
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=api_messages
                    )
                    full_res = response.choices[0].message.content
                    st.markdown(full_res)
                    st.session_state.messages.append({"role": "assistant", "content": full_res})
                    break # Success!
                except Exception as e:
                    if "429" in str(e) and attempt < max_retries - 1:
                        time.sleep(2) # Wait 2 seconds and retry
                        continue
                    else:
                        st.error("Arjun is thinking deeply (Rate Limit). Try again in 10 seconds.")
                        break
    st.rerun()
>>>>>>> ab235158ac2c702f5b7aafc031ccfb43e937d8bf
