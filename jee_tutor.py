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
        ("referral_code", "TEXT"),
        ("pro_expiry", "DATE"),
        ("total_referrals", "INTEGER DEFAULT 0"),
        ("tos_agreed", "INTEGER DEFAULT 0"),
        ("payment_intent", "TEXT") # Stores "Monthly" or "Yearly"
    ]
    for col_name, col_type in columns_to_add:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass 

    c.execute('''CREATE TABLE IF NOT EXISTS referrals 
                 (referrer_id TEXT, referee_id TEXT, timestamp DATETIME, 
                 PRIMARY KEY (referrer_id, referee_id))''')
    conn.commit()
    conn.close()

ensure_database_schema()

# --- 2. CORE LOGIC ---
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

def generate_ref_code(username):
    return hashlib.sha256(username.encode()).hexdigest()[:6].upper()

def track_payment_intent(username, plan):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("UPDATE users SET payment_intent = ? WHERE username = ?", (plan, username))
    conn.commit()
    conn.close()
    st.toast(f"🚀 Garg.ai team notified! We'll contact you for the {plan} setup.")

# --- 3. UI & DIALOGS ---
st.set_page_config(page_title="Arjun - JEE Vertical Reasoning", layout="wide")

if 'username' not in st.session_state:
    st.session_state.username = "Tanush"

# Check DB for User Status
conn = sqlite3.connect('user_data.db'); c = conn.cursor()
c.execute("SELECT tos_agreed, pro_expiry FROM users WHERE username = ?", (st.session_state.username,))
user_row = c.fetchone(); conn.close()

is_pro = False
if user_row and user_row[1] and datetime.strptime(user_row[1], '%Y-%m-%d').date() >= date.today():
    is_pro = True

# ToS Modal
if not (user_row[0] if user_row else 0):
    @st.dialog("📜 Garg.ai Terms of Service")
    def show_tos():
        st.write("Welcome to Garg.ai. Do you agree to our terms of educational use and data privacy?")
        if st.button("I Agree"):
            conn = sqlite3.connect('user_data.db'); c = conn.cursor()
            c.execute("UPDATE users SET tos_agreed = 1 WHERE username = ?", (st.session_state.username,))
            conn.commit(); conn.close(); st.rerun()
    show_tos(); st.stop()

# Pricing Modal
@st.dialog("💎 Upgrade to Garg.ai Pro")
def show_pricing():
    st.write("Unlock the full power of Vertical Reasoning and dominate JEE 2026.")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Monthly")
        st.title("₹499")
        st.write("- Unlimited Visual Reasoning\n- Priority Socratic Support")
        if st.button("Get Monthly", use_container_width=True):
            track_payment_intent(st.session_state.username, "Monthly")
    with col2:
        st.subheader("Yearly")
        st.title("₹3,999")
        st.write("- Everything in Monthly\n- All PYQ Solution Sets")
        if st.button("Get Yearly", type="primary", use_container_width=True):
            track_payment_intent(st.session_state.username, "Yearly")

# --- 4. SIDEBAR & ADMIN VIEW ---
with st.sidebar:
    st.title("🏹 Arjun v3.2")
    
    # FOUNDER'S ADMIN CONSOLE
    with st.expander("⚙️ Admin Console"):
        admin_pass = st.text_input("Passcode", type="password")
        if admin_pass == "GARG_AI_BETA_2026":
            st.success("Admin Access Granted")
            conn = sqlite3.connect('user_data.db')
            # Fetch users who clicked buy
            df_leads = pd.read_sql_query("SELECT username, payment_intent FROM users WHERE payment_intent IS NOT NULL", conn)
            # Fetch total users
            df_users = pd.read_sql_query("SELECT username, pro_expiry, total_referrals FROM users", conn)
            conn.close()
            
            st.write("💰 **Hot Leads (Ready to Pay)**")
            st.dataframe(df_leads, use_container_width=True)
            st.write("👥 **All Users**")
            st.dataframe(df_users, use_container_width=True)
            st.stop() # Stops the rest of the UI from rendering so you can focus on the data

    # NORMAL USER SIDEBAR
    if is_pro:
        st.success(f"⭐ PRO ACTIVE (Expires: {user_row[1]})")
    else:
        st.warning("PLAN: Free Tier")
        if st.button("🚀 UPGRADE TO PRO", use_container_width=True):
            show_pricing()

    st.divider()
    my_code = generate_ref_code(st.session_state.username)
    st.write("### 🎁 Refer for Free Pro")
    st.info(f"Your Code: **{my_code}**")
    
    ref_input = st.text_input("Enter friend's code")
    if st.button("Claim Free Days"):
        # Referral logic executes here
        st.toast("Verifying with Garg.ai...")

# --- 5. CHAT INTERFACE ---
st.header("Vertical Reasoning Engine")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about Physics, Chemistry, or Math..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        sys_prompt = "You are Arjun (AIR 347). Use Socratic Scaffolding. Never give direct answers. Help the user build intuition for JEE. Use LaTeX for math."
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": sys_prompt}] + 
                     [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        )
        full_response = response.choices[0].message.content
        st.markdown(full_response)
        
    st.session_state.messages.append({"role": "assistant", "content": full_response})
