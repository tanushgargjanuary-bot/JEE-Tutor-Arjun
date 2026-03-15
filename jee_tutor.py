import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from groq import Groq
from datetime import datetime, date

# --- 1. THE AUTO-MIGRATOR (V3.4) ---
def ensure_database_schema():
    conn = sqlite3.connect('user_data.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    
    # NEW: Added 'user_summary' to track long-term memory
    columns_to_add = [
        ("referral_code", "TEXT"), ("pro_expiry", "DATE"),
        ("total_referrals", "INTEGER DEFAULT 0"), ("tos_agreed", "INTEGER DEFAULT 0"),
        ("payment_intent", "TEXT"), ("user_summary", "TEXT") 
    ]
    for col_name, col_type in columns_to_add:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError: pass 
    conn.commit(); conn.close()

ensure_database_schema()

# --- 2. PREMIUM UI & STYLE ---
st.set_page_config(page_title="Arjun | JEE Mentor", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    header {visibility: hidden;} footer {visibility: hidden;} #MainMenu {visibility: hidden;}
    .stApp { background: radial-gradient(circle at top right, #1e2129, #0e1117); font-family: 'Inter', sans-serif; }
    [data-testid="stChatMessage"] { background-color: #1c2128; border: 1px solid #30363d; border-radius: 12px; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: 800; color: #58a6ff; }
    div.stButton > button:first-child { background: linear-gradient(135deg, #238636 0%, #2ea043 100%); color: white; border-radius: 8px; font-weight: bold; width: 100%; }
    .side-box { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; backdrop-filter: blur(5px); }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CORE LOGIC & SUMMARIZER ---
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

def update_user_memory(username, chat_history):
    # Only summarize if history is substantial
    if len(chat_history) < 6: return 
    
    history_text = "\n".join([f"{m['role']}: {m['content']}" for m in chat_history[-6:]])
    summary_prompt = f"Based on this JEE prep chat history, summarize the student's current strengths, weaknesses, and concepts they just learned. Keep it under 50 words. \nHistory: {history_text}"
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are a memory agent. Summarize student progress."},
                      {"role": "user", "content": summary_prompt}]
        )
        new_summary = response.choices[0].message.content
        conn = sqlite3.connect('user_data.db'); c = conn.cursor()
        c.execute("UPDATE users SET user_summary = ? WHERE username = ?", (new_summary, username))
        conn.commit(); conn.close()
    except: pass

def generate_ref_code(username):
    return hashlib.sha256(username.encode()).hexdigest()[:6].upper()

# --- 4. SESSION & DATA ---
if 'username' not in st.session_state: st.session_state.username = "Tanush"

conn = sqlite3.connect('user_data.db'); c = conn.cursor()
c.execute("SELECT tos_agreed, pro_expiry, user_summary FROM users WHERE username = ?", (st.session_state.username,))
user_row = c.fetchone(); conn.close()

is_pro = False
if user_row and user_row[1] and datetime.strptime(user_row[1], '%Y-%m-%d').date() >= date.today():
    is_pro = True
memory_context = user_row[2] if user_row and user_row[2] else "New student. No history yet."

# --- 5. LAYOUT ---
col_dash, col_chat = st.columns([1, 2.5], gap="large")

with col_dash:
    st.title("🏹 Arjun")
    st.caption("JEE Mentor • AIR 92") # Updated to reflect "Top 100" status
    
    st.markdown('<div class="side-box">', unsafe_allow_html=True)
    st.subheader("Mentor Memo")
    st.caption(memory_context) # Shows what Arjun "remembers"
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="side-box">', unsafe_allow_html=True)
    st.write("🎁 **Refer & Earn Pro**")
    st.code(generate_ref_code(st.session_state.username), language=None)
    st.markdown('</div>', unsafe_allow_html=True)

with col_chat:
    st.header("Ask Arjun")
    
    if "messages" not in st.session_state:
        # THE NEW AUTHORITATIVE WELCOME MESSAGE
        welcome_text = (
            "I am Arjun. I ranked in the **Top 100 in JEE**, and I'm here to ensure you do the same. "
            "I'm not just a calculator; I'm your guide for the next 2 years. "
            "I won't give you answers—I'll give you the intuition to solve anything they throw at you. "
            "What concept are we mastering today?"
        )
        st.session_state.messages = [{"role": "assistant", "content": welcome_text}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("E.g., How do I approach multi-variable integration?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            sys_prompt = f"You are Arjun (AIR 92). You are an elite JEE mentor. Use Socratic Scaffolding. User Progress Memory: {memory_context}. Focus on building intuition."
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": sys_prompt}] + 
                         [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            )
            full_res = response.choices[0].message.content
            st.markdown(full_res)
        st.session_state.messages.append({"role": "assistant", "content": full_res})
        
        # Trigger Auto-Summarizer every few messages
        if len(st.session_state.messages) % 6 == 0:
            update_user_memory(st.session_state.username, st.session_state.messages)
