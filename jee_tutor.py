import streamlit as st
import sqlite3
import hashlib
from groq import Groq
from datetime import datetime, date

# --- 1. THE AUTO-MIGRATOR (Schema Guard) ---
def ensure_database_schema():
    conn = sqlite3.connect('user_data.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    
    # NEW: Added 'tos_agreed' to the migration list
    columns_to_add = [
        ("referral_code", "TEXT"),
        ("pro_expiry", "DATE"),
        ("total_referrals", "INTEGER DEFAULT 0"),
        ("tos_agreed", "INTEGER DEFAULT 0") 
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

# --- 2. CORE BUSINESS LOGIC ---
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

def generate_ref_code(username):
    return hashlib.sha256(username.encode()).hexdigest()[:6].upper()

def agree_to_tos(username):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("UPDATE users SET tos_agreed = 1 WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    st.session_state.tos_agreed = 1

def process_referral(current_user, entered_code):
    if entered_code == "GARG_AI_BETA_2026":
        conn = sqlite3.connect('user_data.db')
        c = conn.cursor()
        c.execute("UPDATE users SET pro_expiry = '2027-01-01' WHERE username = ?", (current_user,))
        conn.commit()
        conn.close()
        return "👑 Founder's access granted."

    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT username, total_referrals FROM users WHERE referral_code = ?", (entered_code,))
    referrer = c.fetchone()
    
    if not referrer: return "❌ Code not found."
    if entered_code == generate_ref_code(current_user): return "🚫 No self-referrals."

    c.execute("SELECT * FROM referrals WHERE referee_id = ?", (current_user,))
    if c.fetchone(): return "⚠️ Already used a code."

    if referrer[1] >= 10: return "📈 Referral limit reached."

    c.execute("UPDATE users SET pro_expiry = DATE(COALESCE(pro_expiry, CURRENT_DATE), '+3 days'), total_referrals = total_referrals + 1 WHERE referral_code = ?", (entered_code,))
    c.execute("UPDATE users SET pro_expiry = DATE(COALESCE(pro_expiry, CURRENT_DATE), '+2 days') WHERE username = ?", (current_user,))
    c.execute("INSERT INTO referrals (referrer_id, referee_id, timestamp) VALUES (?, ?, CURRENT_TIMESTAMP)", (entered_code, current_user))
    conn.commit()
    conn.close()
    return "✅ Success! Pro days added."

# --- 3. UI & SESSIONS ---
st.set_page_config(page_title="Arjun - JEE Vertical Reasoning", layout="wide")

if 'username' not in st.session_state:
    st.session_state.username = "Tanush" # Replace with real login logic

# Check ToS Status from DB
conn = sqlite3.connect('user_data.db')
c = conn.cursor()
c.execute("SELECT tos_agreed FROM users WHERE username = ?", (st.session_state.username,))
row = c.fetchone()
conn.close()
st.session_state.tos_agreed = row[0] if row else 0

# --- 4. THE TERMS OF SERVICE MODAL ---
if not st.session_state.tos_agreed:
    @st.dialog("📜 Garg.ai Terms of Service")
    def show_tos():
        st.write("""
        Welcome to **Garg.ai**. By using our JEE Mentor (Arjun), you agree to:
        1. **Educational Use Only**: Arjun is an AI assistant. While highly accurate, always cross-reference critical formulas with official JEE textbooks.
        2. **Fair Play**: You will not attempt to exploit the referral system or reverse-engineer the reasoning engine.
        3. **Data Privacy**: We use your interaction data to improve Arjun's Socratic logic. Your personal details are never sold.
        4. **Limitation of Liability**: Garg.ai is not responsible for exam results. We provide the tools; you provide the hard work.
        """)
        if st.button("I Agree & Accept Terms"):
            agree_to_tos(st.session_state.username)
            st.rerun()

    show_tos()
    st.stop() # Stops the rest of the app from loading until agreed

# --- 5. MAIN APP (Only visible after ToS agreement) ---
with st.sidebar:
    st.title("🏹 Arjun v3.1")
    st.caption("Garg.ai - Frontier AI")
    st.divider()
    
    my_code = generate_ref_code(st.session_state.username)
    st.write("### 🎁 Refer & Earn Pro")
    st.info(f"Code: **{my_code}**")
    
    ref_input = st.text_input("Friend's Code")
    if st.button("Apply Code"):
        st.toast(process_referral(st.session_state.username, ref_input))
            
    st.divider()
    conn = sqlite3.connect('user_data.db'); c = conn.cursor()
    c.execute("SELECT pro_expiry FROM users WHERE username = ?", (st.session_state.username,))
    row = c.fetchone(); conn.close()
    
    if row and row[0] and datetime.strptime(row[0], '%Y-%m-%d').date() >= date.today():
        st.success(f"PRO ACTIVE (Expires: {row[0]})")
    else:
        st.warning("BASIC PLAN")

st.header("Vertical Reasoning Engine")
# (Chat logic remains the same below)
