import streamlit as st
import sqlite3
import hashlib
from groq import Groq
from datetime import datetime, date

# --- 1. THE AUTO-MIGRATOR (Schema Guard) ---
def ensure_database_schema():
    conn = sqlite3.connect('user_data.db', check_same_thread=False)
    c = conn.cursor()
    
    # Ensure core users table
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT)''')
    
    # Add referral and pro columns if missing
    columns_to_add = [
        ("referral_code", "TEXT"),
        ("pro_expiry", "DATE"),
        ("total_referrals", "INTEGER DEFAULT 0")
    ]
    for col_name, col_type in columns_to_add:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass # Column already exists

    # Ensure referral tracking table
    c.execute('''CREATE TABLE IF NOT EXISTS referrals 
                 (referrer_id TEXT, referee_id TEXT, timestamp DATETIME, 
                 PRIMARY KEY (referrer_id, referee_id))''')
    
    conn.commit()
    conn.close()

ensure_database_schema()

# --- 2. CORE BUSINESS LOGIC ---
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

def generate_ref_code(username):
    # Deterministic 6-char code
    return hashlib.sha256(username.encode()).hexdigest()[:6].upper()

def process_referral(current_user, entered_code):
    # --- ANTI-EXPLOIT CHECK 1: The Founder's Cheat Code ---
    if entered_code == "GARG_AI_BETA_2026":
        conn = sqlite3.connect('user_data.db')
        c = conn.cursor()
        c.execute("UPDATE users SET pro_expiry = '2027-01-01' WHERE username = ?", (current_user,))
        conn.commit()
        conn.close()
        return "👑 Founder's access granted. Welcome to the inner circle."

    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    
    # --- ANTI-EXPLOIT CHECK 2: Existence & Self-Referral ---
    c.execute("SELECT username, total_referrals FROM users WHERE referral_code = ?", (entered_code,))
    referrer = c.fetchone()
    
    if not referrer:
        return "❌ Code not found in Garg.ai database."
    
    if entered_code == generate_ref_code(current_user):
        return "🚫 You cannot refer yourself, champ."

    # --- ANTI-EXPLOIT CHECK 3: Double-Dipping ---
    c.execute("SELECT * FROM referrals WHERE referee_id = ?", (current_user,))
    if c.fetchone():
        return "⚠️ You've already used a referral code!"

    # --- ANTI-EXPLOIT CHECK 4: The 10-Referral Cap ---
    if referrer[1] >= 10:
        return "📈 This mentor has maxed out their rewards."

    # SUCCESS: Grant Rewards (3 days for Referrer, 2 days for User)
    c.execute("UPDATE users SET pro_expiry = DATE(COALESCE(pro_expiry, CURRENT_DATE), '+3 days'), total_referrals = total_referrals + 1 WHERE referral_code = ?", (entered_code,))
    c.execute("UPDATE users SET pro_expiry = DATE(COALESCE(pro_expiry, CURRENT_DATE), '+2 days') WHERE username = ?", (current_user,))
    c.execute("INSERT INTO referrals (referrer_id, referee_id, timestamp) VALUES (?, ?, CURRENT_TIMESTAMP)", (entered_code, current_user))
    
    conn.commit()
    conn.close()
    return "✅ Success! Pro days added to both accounts."

# --- 3. UI & SIDEBAR ---
st.set_page_config(page_title="Arjun - JEE Vertical Reasoning", layout="wide")

# Session state initialization
if 'username' not in st.session_state:
    st.session_state.username = "Tanush" # Default for testing - replace with your Login logic

with st.sidebar:
    st.title("🏹 Arjun v3.1")
    st.caption("Garg.ai - Frontier Reasoning for JEE")
    st.divider()
    
    # Referral Display
    my_code = generate_ref_code(st.session_state.username)
    st.write("### 🎁 Refer & Earn Pro")
    st.info(f"Your Code: **{my_code}**")
    st.caption("Get 3 days of Pro for every friend you invite.")
    
    # Apply Code UI
    ref_input = st.text_input("Friend's Code", placeholder="E.g. 7A3B2C")
    if st.button("Apply Code"):
        with st.spinner("Verifying with Garg.ai..."):
            msg = process_referral(st.session_state.username, ref_input)
            st.toast(msg)
            
    st.divider()
    st.subheader("Account Status")
    # Pro Status Logic
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT pro_expiry FROM users WHERE username = ?", (st.session_state.username,))
    row = c.fetchone()
    conn.close()
    
    if row and row[0] and datetime.strptime(row[0], '%Y-%m-%d').date() >= date.today():
        st.success(f"PRO ACTIVE (Expires: {row[0]})")
    else:
        st.warning("BASIC PLAN - Refer friends to unlock PRO.")

# --- 4. MAIN ENGINE (CHEST & CHAT) ---
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
        # Socratic System Prompt for Vertical Reasoning
        sys_prompt = "You are Arjun (AIR 347). Use Socratic Scaffolding. Never give direct answers. Help the user build intuition for JEE. Use LaTeX for math."
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": sys_prompt}] + 
                     [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        )
        full_response = response.choices[0].message.content
        st.markdown(full_response)
        
    st.session_state.messages.append({"role": "assistant", "content": full_response})
