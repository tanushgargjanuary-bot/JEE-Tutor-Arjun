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
        ("payment_intent", "TEXT") 
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

def process_referral(current_user, entered_code):
    if entered_code == "GARG_AI_BETA_2026":
        conn = sqlite3.connect('user_data.db')
        c = conn.cursor()
        c.execute("UPDATE users SET pro_expiry = '2027-01-01' WHERE username = ?", (current_user,))
        conn.commit(); conn.close()
        return "👑 Founder's access granted."

    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT username, total_referrals FROM users WHERE referral_code = ?", (entered_code,))
    referrer = c.fetchone()
    
    if not referrer: return "❌ Code not found."
    if entered_code == generate_ref_code(current_user): return "🚫 Nice try. No self-referrals."

    c.execute("SELECT * FROM referrals WHERE referee_id = ?", (current_user,))
    if c.fetchone(): return "⚠️ You've already used a referral code."

    if referrer[1] >= 10: return "📈 This mentor has reached their referral limit."

    c.execute("UPDATE users SET pro_expiry = DATE(COALESCE(pro_expiry, CURRENT_DATE), '+3 days'), total_referrals = total_referrals + 1 WHERE referral_code = ?", (entered_code,))
    c.execute("UPDATE users SET pro_expiry = DATE(COALESCE(pro_expiry, CURRENT_DATE), '+2 days') WHERE username = ?", (current_user,))
    c.execute("INSERT INTO referrals (referrer_id, referee_id, timestamp) VALUES (?, ?, CURRENT_TIMESTAMP)", (entered_code, current_user))
    
    conn.commit()
    conn.close()
    return "✅ Success! Pro days added to your account."

# --- 3. UI SETUP & SESSION ---
st.set_page_config(page_title="Ask Arjun | JEE Mentor", layout="wide")

if 'username' not in st.session_state:
    st.session_state.username = "Tanush" # Replace with your actual auth logic later

# Check DB for User Status
conn = sqlite3.connect('user_data.db'); c = conn.cursor()
c.execute("SELECT tos_agreed, pro_expiry FROM users WHERE username = ?", (st.session_state.username,))
user_row = c.fetchone(); conn.close()

is_pro = False
if user_row and user_row[1] and datetime.strptime(user_row[1], '%Y-%m-%d').date() >= date.today():
    is_pro = True

# ToS Modal
if not (user_row[0] if user_row else 0):
    @st.dialog("📜 Welcome to Ask Arjun")
    def show_tos():
        st.write("Before we start, please agree to our terms of educational use. Arjun is an AI mentor designed to build your intuition. Always verify critical formulas with your textbook.")
        if st.button("I Agree & Accept", type="primary", use_container_width=True):
            conn = sqlite3.connect('user_data.db'); c = conn.cursor()
            c.execute("UPDATE users SET tos_agreed = 1 WHERE username = ?", (st.session_state.username,))
            conn.commit(); conn.close(); st.rerun()
    show_tos(); st.stop()

# Pricing Modal
@st.dialog("💎 Upgrade to Pro")
def show_pricing():
    st.write("Unlock the full power of Arjun and dominate JEE 2026.")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Monthly")
        st.title("₹499")
        st.write("- Unlimited Visual Socratic Help\n- Priority Sourcing")
        if st.button("Get Monthly", use_container_width=True):
            track_payment_intent(st.session_state.username, "Monthly")
    with col2:
        st.subheader("Yearly")
        st.title("₹3,999")
        st.write("- Everything in Monthly\n- All PYQ Solution Sets")
        if st.button("Get Yearly", type="primary", use_container_width=True):
            track_payment_intent(st.session_state.username, "Yearly")

# --- 4. POLISHED SIDEBAR ---
with st.sidebar:
    st.title("🏹 Arjun")
    st.caption("Powered by Garg.ai | 24/7 Doubt Resolution")
    
    # FOUNDER'S ADMIN CONSOLE (Hidden)
    with st.expander("⚙️ Admin Console"):
        admin_pass = st.text_input("Passcode", type="password")
        if admin_pass == "GARG_AI_BETA_2026":
            st.success("Admin Access Granted")
            conn = sqlite3.connect('user_data.db')
            df_leads = pd.read_sql_query("SELECT username, payment_intent FROM users WHERE payment_intent IS NOT NULL", conn)
            df_users = pd.read_sql_query("SELECT username, pro_expiry, total_referrals FROM users", conn)
            conn.close()
            st.write("💰 **Hot Leads**")
            st.dataframe(df_leads, use_container_width=True)
            st.write("👥 **All Users**")
            st.dataframe(df_users, use_container_width=True)
            st.stop()

    st.divider()

    # ACCOUNT STATUS
    st.subheader("Your Plan")
    if is_pro:
        st.markdown(f"**Tier:** 🟢 PRO")
        st.caption(f"Valid until: {user_row[1]}")
    else:
        st.markdown("**Tier:** ⚪ Basic")
        st.caption("Unlock PYQ sets & priority doubt solving.")
        if st.button("⚡ Upgrade to Pro", use_container_width=True, type="primary"):
            show_pricing()

    st.divider()
    
    # REFERRAL ENGINE
    st.write("### 🎁 Earn Free Pro")
    my_code = generate_ref_code(st.session_state.username)
    st.caption("Share this code to get 3 free days of Pro.")
    st.code(my_code, language=None) 
    
    ref_input = st.text_input("Friend's Code", placeholder="Enter code here...")
    if st.button("Apply Code", use_container_width=True):
        st.toast(process_referral(st.session_state.username, ref_input))

# --- 5. CLEAN CHAT INTERFACE ---
st.header("Ask Arjun")
st.caption("Paste your doubt in Physics, Chemistry, or Math. Let's break it down.")

# Welcome Message Logic
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hey! I'm Arjun. Drop a physics, chemistry, or math doubt below and let's figure it out together. (No direct answers, I'm here to help you actually learn it)."}
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("E.g., How do I find the center of mass of a semi-circle?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        sys_prompt = "You are Arjun (AIR 347). You are a blunt but highly effective JEE mentor. Use Socratic Scaffolding. Never give direct answers. Give a hint, explain a concept, and ask a follow up question to build the user's intuition. Use LaTeX for math."
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": sys_prompt}] + 
                     [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        )
        full_response = response.choices[0].message.content
        st.markdown(full_response)
        
    st.session_state.messages.append({"role": "assistant", "content": full_response})
