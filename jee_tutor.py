import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from groq import Groq
from datetime import datetime, date

# --- 1. THE AUTO-MIGRATOR & DB SETUP ---
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

# --- 2. PREMIUM UI & CSS INJECTION ---
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

# --- 3. CORE LOGIC, REFERRALS & MEMORY ---
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

def generate_ref_code(username):
    return hashlib.sha256(username.encode()).hexdigest()[:6].upper()

def track_payment_intent(username, plan):
    conn = sqlite3.connect('user_data.db'); c = conn.cursor()
    c.execute("UPDATE users SET payment_intent = ? WHERE username = ?", (plan, username))
    conn.commit(); conn.close()
    st.toast(f"🚀 Garg.ai team notified! We'll contact you for the {plan} setup.")

def process_referral(current_user, entered_code):
    if entered_code == "FOUNDER_BETA_2026":
        conn = sqlite3.connect('user_data.db'); c = conn.cursor()
        c.execute("UPDATE users SET pro_expiry = '2027-01-01' WHERE username = ?", (current_user,))
        conn.commit(); conn.close()
        return "👑 Founder's access granted."
    
    conn = sqlite3.connect('user_data.db'); c = conn.cursor()
    c.execute("SELECT username, total_referrals FROM users WHERE referral_code = ?", (entered_code,))
    referrer = c.fetchone()
    
    if not referrer: return "❌ Code not found."
    if entered_code == generate_ref_code(current_user): return "🚫 No self-referrals."
    
    c.execute("SELECT * FROM referrals WHERE referee_id = ?", (current_user,))
    if c.fetchone(): return "⚠️ You've already used a code."
    
    c.execute("UPDATE users SET pro_expiry = DATE(COALESCE(pro_expiry, CURRENT_DATE), '+3 days'), total_referrals = total_referrals + 1 WHERE referral_code = ?", (entered_code,))
    c.execute("UPDATE users SET pro_expiry = DATE(COALESCE(pro_expiry, CURRENT_DATE), '+2 days') WHERE username = ?", (current_user,))
    c.execute("INSERT INTO referrals (referrer_id, referee_id) VALUES (?, ?)", (entered_code, current_user))
    conn.commit(); conn.close()
    return "✅ Success! Pro days added."

def update_user_memory(username, chat_history):
    if len(chat_history) < 6: return 
    history_text = "\n".join([f"{m['role']}: {m['content']}" for m in chat_history[-6:]])
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Summarize student's conceptual gaps in under 40 words."}, 
                      {"role": "user", "content": history_text}]
        )
        conn = sqlite3.connect('user_data.db'); c = conn.cursor()
        c.execute("UPDATE users SET user_summary = ? WHERE username = ?", (response.choices[0].message.content, username))
        conn.commit(); conn.close()
    except: pass

# --- 4. SESSION & DB FETCH ---
if 'username' not in st.session_state: st.session_state.username = "Tanush"

conn = sqlite3.connect('user_data.db'); c = conn.cursor()
c.execute("SELECT tos_agreed, pro_expiry, user_summary FROM users WHERE username = ?", (st.session_state.username,))
user_row = c.fetchone(); conn.close()

if 'tos_agreed' not in st.session_state: st.session_state.tos_agreed = user_row[0] if user_row else 0
is_pro = bool(user_row and user_row[1] and datetime.strptime(user_row[1], '%Y-%m-%d').date() >= date.today())
memory_context = user_row[2] if user_row and user_row[2] else "New student. Let's start building your JEE profile."

# --- 5. MODALS (TOS & PRICING) ---
if not st.session_state.tos_agreed:
    @st.dialog("📜 Terms of Service")
    def show_tos():
        st.write("By using Arjun, you agree this is an intuition-building tool. Verify critical formulas with textbooks.")
        if st.button("I Agree", type="primary", use_container_width=True):
            conn = sqlite3.connect('user_data.db'); c = conn.cursor()
            c.execute("UPDATE users SET tos_agreed = 1 WHERE username = ?", (st.session_state.username,))
            conn.commit(); conn.close()
            st.session_state.tos_agreed = 1; st.rerun()
    show_tos(); st.stop()

@st.dialog("💎 Upgrade to Pro")
def show_pricing():
    st.write("Unlock the full power of Arjun and dominate JEE.")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Monthly"); st.title("₹499")
        if st.button("Get Monthly", use_container_width=True): track_payment_intent(st.session_state.username, "Monthly")
    with col2:
        st.subheader("Yearly"); st.title("₹3,999")
        if st.button("Get Yearly", type="primary", use_container_width=True): track_payment_intent(st.session_state.username, "Yearly")

# --- 6. LAYOUT SPLIT ---
col_dash, col_chat = st.columns([1, 2.5], gap="large")

with col_dash:
    st.title("🏹 Arjun")
    st.caption("JEE Mentor • AIR 92")
    
    st.markdown('<div class="side-box">', unsafe_allow_html=True)
    st.subheader("Mentor Memo"); st.caption(memory_context)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="side-box">', unsafe_allow_html=True)
    if is_pro: st.success("⭐ PRO ACTIVE")
    else:
        st.info("⚪ BASIC")
        if st.button("🚀 Upgrade to Pro"): show_pricing()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="side-box">', unsafe_allow_html=True)
    st.write("🎁 **Refer & Earn**")
    st.code(generate_ref_code(st.session_state.username), language=None)
    ref_input = st.text_input("Friend's Code", placeholder="Enter code...", key="ref_in")
    if st.button("Apply Code"): st.toast(process_referral(st.session_state.username, ref_input))
    st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("⚙️ Admin Console"):
        if st.text_input("Passcode", type="password") == "FOUNDER_BETA_2026":
            conn = sqlite3.connect('user_data.db')
            st.dataframe(pd.read_sql_query("SELECT username, payment_intent FROM users WHERE payment_intent IS NOT NULL", conn))
            st.dataframe(pd.read_sql_query("SELECT username, pro_expiry, total_referrals FROM users", conn))
            conn.close()

# --- 7. CHAT INTERFACE (FIXED TO BOTTOM) ---
with col_chat:
    st.header("Ask Arjun")
    
    # Message Container
    if "messages" not in st.session_state:
        welcome_text = "I am Arjun. I ranked in the **Top 100 in JEE**. I'm here to build your intuition, not just solve your homework. What are we mastering today?"
        st.session_state.messages = [{"role": "assistant", "content": welcome_text}]

    # This loop now stays inside the column
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# THIS IS THE FIX: Move chat_input OUTSIDE of the 'with col_chat' block
# Streamlit will automatically pin it to the bottom of the screen.
if prompt := st.chat_input("E.g., How do I find the center of mass of a semi-circle?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # We trigger a rerun to show the user message immediately
    with col_chat:
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            sys_msg = f"You are Arjun (AIR 92). Elite JEE mentor. Use STRICT Socratic Scaffolding. NEVER give the final answer immediately. Lead with conceptual questions. Memory: {memory_context}. Use LaTeX."
            api_messages = [{"role": "system", "content": sys_msg}]
            for m in st.session_state.messages:
                if m["content"].strip():
                    api_messages.append({"role": m["role"], "content": m["content"]})

            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=api_messages
                )
                full_res = response.choices[0].message.content
                st.markdown(full_res)
                st.session_state.messages.append({"role": "assistant", "content": full_res})
                
                # Update memory every 6 messages
                if len(st.session_state.messages) % 6 == 0:
                    update_user_memory(st.session_state.username, st.session_state.messages)
                    
            except Exception as e:
                st.error(f"Brain Overloaded. Details: {e}")
    
    st.rerun() # Refresh to keep everything in sync

# --- 7. CLEAN CHAT INTERFACE ---
with col_chat:
    st.header("Ask Arjun")
    
    if "messages" not in st.session_state:
        welcome_text = "I am Arjun. I ranked in the **Top 100 in JEE**. I'm here to build your intuition, not just solve your homework. What are we mastering today?"
        st.session_state.messages = [{"role": "assistant", "content": welcome_text}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])

    if prompt := st.chat_input("E.g., How do I approach multi-variable integration?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            sys_msg = f"You are Arjun (AIR 92). Elite JEE mentor. Use STRICT Socratic Scaffolding. NEVER give the final answer or full derivation immediately. Your goal is to lead the student to the realization by asking one conceptual leading question at a time. Memory: {memory_context}. Use LaTeX."
            api_messages = [{"role": "system", "content": sys_msg}]
            for m in st.session_state.messages:
                if m["content"].strip(): api_messages.append({"role": m["role"], "content": m["content"]})

            try:
                response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=api_messages)
                full_res = response.choices[0].message.content
                st.markdown(full_res)
                st.session_state.messages.append({"role": "assistant", "content": full_res})
                
                if len(st.session_state.messages) % 6 == 0:
                    update_user_memory(st.session_state.username, st.session_state.messages)
            except Exception as e: st.error(f"Brain Overloaded. Details: {e}")
