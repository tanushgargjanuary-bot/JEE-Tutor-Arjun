import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from groq import Groq
from datetime import datetime, date

# --- 1. DATABASE SETUP ---
def ensure_database_schema():
    conn = sqlite3.connect('user_data.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    columns_to_add = [
        ("referral_code", "TEXT"), ("pro_expiry", "DATE"),
        ("total_referrals", "INTEGER DEFAULT 0"), ("tos_agreed", "INTEGER DEFAULT 0"),
        ("payment_intent", "TEXT"), ("user_summary", "TEXT") 
    ]
    for col_name, col_type in columns_to_add:
        try: c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError: pass 
    c.execute('''CREATE TABLE IF NOT EXISTS referrals 
                 (referrer_id TEXT, referee_id TEXT, timestamp DATETIME, PRIMARY KEY (referrer_id, referee_id))''')
    conn.commit(); conn.close()

ensure_database_schema()

# --- 2. UI & CSS ---
st.set_page_config(page_title="Arjun | JEE Mentor", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    header {visibility: hidden;} footer {visibility: hidden;} #MainMenu {visibility: hidden;}
    .stApp { background: radial-gradient(circle at top right, #1e2129, #0e1117); font-family: 'Inter', sans-serif; }
    [data-testid="stChatMessage"] { background-color: #1c2128; border: 1px solid #30363d; border-radius: 12px; margin-bottom: 10px; }
    div.stButton > button:first-child { background: linear-gradient(135deg, #238636 0%, #2ea043 100%); color: white; border-radius: 8px; font-weight: bold; width: 100%; border: none; }
    .side-box { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; backdrop-filter: blur(5px); }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIC & HELPERS ---
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if 'username' not in st.session_state: st.session_state.username = "Tanush"

def get_user_data():
    conn = sqlite3.connect('user_data.db'); c = conn.cursor()
    c.execute("SELECT tos_agreed, pro_expiry, user_summary FROM users WHERE username = ?", (st.session_state.username,))
    data = c.fetchone(); conn.close()
    return data

def generate_ref_code(username):
    return hashlib.sha256(username.encode()).hexdigest()[:6].upper()

# --- 4. THE TERMS OF SERVICE FIX ---
user_info = get_user_data()
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
            conn = sqlite3.connect('user_data.db'); c = conn.cursor()
            c.execute("UPDATE users SET tos_agreed = 1 WHERE username = ?", (st.session_state.username,))
            conn.commit(); conn.close()
            st.session_state.tos_confirmed = 1
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
            conn = sqlite3.connect('user_data.db'); c = conn.cursor()
            c.execute("UPDATE users SET payment_intent = 'Monthly' WHERE username = ?", (st.session_state.username,))
            conn.commit(); conn.close(); st.toast("Team notified!")
    with c2:
        if st.button("Yearly - ₹3,999", type="primary"):
            conn = sqlite3.connect('user_data.db'); c = conn.cursor()
            c.execute("UPDATE users SET payment_intent = 'Yearly' WHERE username = ?", (st.session_state.username,))
            conn.commit(); conn.close(); st.toast("Team notified!")

# --- 6. LAYOUT ---
col_dash, col_chat = st.columns([1, 2.5], gap="large")

with col_dash:
    st.title("🏹 Arjun")
    st.caption("JEE Mentor • AIR 92")
    
    st.markdown(f'<div class="side-box"><b>Mentor Memo:</b><br><small>{memory_context}</small></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="side-box">', unsafe_allow_html=True)
    if is_pro: st.success("⭐ PRO ACTIVE")
    else:
        st.info("⚪ BASIC")
        if st.button("🚀 Upgrade"): show_pricing()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="side-box">', unsafe_allow_html=True)
    st.write("🎁 **Referral Code**")
    st.code(generate_ref_code(st.session_state.username), language=None)
    st.markdown('</div>', unsafe_allow_html=True)

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
            api_msgs = [{"role": "system", "content": sys}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages if m["content"].strip()]
            try:
                res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=api_msgs)
                ans = res.choices[0].message.content
                st.markdown(ans)
                st.session_state.messages.append({"role": "assistant", "content": ans})
            except Exception as e: st.error(f"Error: {e}")
    st.rerun()
