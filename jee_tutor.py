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
