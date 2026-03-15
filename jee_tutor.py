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
    st.toast(f"🚀 Team notified! We'll contact you for the {plan} setup.")

def process_referral(current_user, entered_code):
    if entered_code == "FOUNDER_BETA_2026":
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

# --- 3. THE "GOLDEN WRAPPER" STYLE INJECTION ---
st.set_page_config(page_title="Arjun | JEE Mentor", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* Global Styles */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }

    /* Main Background - Deep Slate */
    .stApp {
        background: radial-gradient(circle at top right, #1a1c23, #0e1117);
    }

    /* Sidebar - Glassmorphism Effect */
    [data-testid="stSidebar"] {
        background-color: rgba(22, 27, 34, 0.95);
        border-right: 1px solid #30363d;
        backdrop-filter: blur(10px);
    }

    /* Custom Chat Bubbles */
    [data-testid="stChatMessage"] {
        background-color: #1c2128;
        border: 1px solid #30363d;
        border-radius: 15px;
        margin-bottom: 10px;
        padding: 15px;
    }

    /* The "Capitalist" Upgrade Button - Pulsing Success Green */
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: white;
        border: none;
        padding: 0.6rem 1.2rem;
        border-radius: 10px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 1px;
        box-shadow: 0 4px 15px rgba(35, 134, 54, 0.3);
        transition: all 0.3s ease;
    }

    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(46, 160, 67, 0.5);
        color: white;
    }

    /* Hide Streamlit Header/Footer for a "Standalone App" feel */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 4. THE FIXED TERMS OF SERVICE MODAL ---
if not st.session_state.tos_agreed:
    @st.dialog("📜 Terms of Service")
    def show_tos():
        st.write("""
        **Welcome to Arjun.** By using this JEE Mentor, you agree to:
        1. **Educational Use Only:** Arjun is an AI assistant designed to build intuition. Always cross-reference critical formulas with official JEE textbooks.
        2. **Fair Play:** You will not attempt to exploit the referral system.
        3. **Data Privacy:** We use your interaction data to improve the Socratic logic. Your personal details are never sold.
        4. **Limitation of Liability:** We are not responsible for exam results. We provide the tools; you provide the hard work.
        """)
        if st.button("I Agree & Accept", type="primary", use_container_width=True):
            conn = sqlite3.connect('user_data.db'); c = conn.cursor()
            c.execute("UPDATE users SET tos_agreed = 1 WHERE username = ?", (st.session_state.username,))
            conn.commit(); conn.close()
            st.session_state.tos_agreed = 1  # Updates state to break the loop
            st.rerun()
    
    show_tos()
    st.stop()

# --- 5. PRICING MODAL ---
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

# --- 6. POLISHED SIDEBAR ---
with st.sidebar:
    st.title("🏹 Arjun")
    st.caption("24/7 JEE Doubt Resolution")
    
    # FOUNDER'S ADMIN CONSOLE
    with st.expander("⚙️ Admin Console"):
        admin_pass = st.text_input("Passcode", type="password")
        if admin_pass == "FOUNDER_BETA_2026":
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

# --- 7. CLEAN CHAT INTERFACE ---
st.header("Ask Arjun")
st.caption("Paste your doubt in Physics, Chemistry, or Math. Let's break it down.")

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
