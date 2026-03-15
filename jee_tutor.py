import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from groq import Groq
from datetime import datetime, date

# --- 1. THE AUTO-MIGRATOR ---
def ensure_database_schema():
    conn = sqlite3.connect('user_data.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    columns_to_add = [
        ("referral_code", "TEXT"), ("pro_expiry", "DATE"),
        ("total_referrals", "INTEGER DEFAULT 0"), ("tos_agreed", "INTEGER DEFAULT 0"),
        ("payment_intent", "TEXT") 
    ]
    for col_name, col_type in columns_to_add:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError: pass 
    conn.commit(); conn.close()

ensure_database_schema()

# --- 2. PREMIUM UI & CSS INJECTION ---
st.set_page_config(page_title="Arjun | JEE Mentor", layout="wide", initial_sidebar_state="collapsed")

# This is the "Golden Wrapper" CSS
st.markdown("""
    <style>
    /* Hide Streamlit elements */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    /* Background and Fonts */
    .stApp {
        background: radial-gradient(circle at top right, #1e2129, #0e1117);
        font-family: 'Inter', sans-serif;
    }
    
    /* Custom Chat Bubbles */
    [data-testid="stChatMessage"] {
        background-color: #1c2128;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* Metric Card Styling */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 800;
        color: #58a6ff;
    }
    
    /* Capitalist Upgrade Button */
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: bold;
        padding: 0.5rem 1rem;
        width: 100%;
    }
    
    /* Glassmorphism sidebar replacement */
    .side-box {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 20px;
        backdrop-filter: blur(5px);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CORE LOGIC ---
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

def generate_ref_code(username):
    return hashlib.sha256(username.encode()).hexdigest()[:6].upper()

# --- 4. SESSION & STATUS ---
if 'username' not in st.session_state: st.session_state.username = "Tanush"

conn = sqlite3.connect('user_data.db'); c = conn.cursor()
c.execute("SELECT tos_agreed, pro_expiry FROM users WHERE username = ?", (st.session_state.username,))
user_row = c.fetchone(); conn.close()

is_pro = False
if user_row and user_row[1] and datetime.strptime(user_row[1], '%Y-%m-%d').date() >= date.today():
    is_pro = True

# --- 5. MAIN PAGE LAYOUT ---
col_dash, col_chat = st.columns([1, 2.5], gap="large")

with col_dash:
    st.title("🏹 Arjun")
    st.caption("AI Mentor • AIR 347")
    
    # Dashboard Box
    st.markdown('<div class="side-box">', unsafe_allow_html=True)
    st.subheader("Study Progress")
    m1, m2 = st.columns(2)
    m1.metric("Doubts", "12")
    m2.metric("Streak", "4 Days")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Plan Box
    st.markdown('<div class="side-box">', unsafe_allow_html=True)
    if is_pro:
        st.success("⭐ PRO PLAN ACTIVE")
    else:
        st.info("⚪ BASIC PLAN")
        if st.button("🚀 Upgrade to Pro"):
            st.toast("Opening secure payment intent...")
    st.markdown('</div>', unsafe_allow_html=True)

    # Referral Box
    st.markdown('<div class="side-box">', unsafe_allow_html=True)
    st.write("🎁 **Refer & Earn**")
    st.code(generate_ref_code(st.session_state.username), language=None)
    st.caption("Get 3 days for every friend.")
    st.markdown('</div>', unsafe_allow_html=True)

with col_chat:
    st.header("Doubt Resolution")
    
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hey! I'm Arjun. Drop a physics, chemistry, or math doubt below."}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Explain the photoelectric effect..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            sys_prompt = "You are Arjun, a blunt JEE mentor. Use Socratic Scaffolding. LaTeX for math."
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": sys_prompt}] + 
                         [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            )
            full_res = response.choices[0].message.content
            st.markdown(full_res)
        st.session_state.messages.append({"role": "assistant", "content": full_res})
