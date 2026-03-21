import streamlit as st
from groq import Groq
import sqlite3
import hashlib
import secrets as secrets_lib
from datetime import datetime, timedelta
import pandas as pd
import json
import os

# ============================================================================
# 1. CONFIGURATION & SECRETS
# ============================================================================
ADMIN_PASSCODE = "FOUNDER_BETA_2026"

# Secure API key handling: Use st.secrets for deployment, fallback for local dev


def get_groq_api_key():
    """Get GROQ API key from st.secrets (deployment) or environment (local dev)."""
    try:
        # Try Streamlit Cloud secrets first
        return st.secrets["GROQ_API_KEY"]
    except (FileNotFoundError, KeyError, AttributeError):
        # Fallback to environment variable or hardcoded (local dev only)
        return os.getenv("GROQ_API_KEY", "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")


GROQ_API_KEY = get_groq_api_key()
client = Groq(api_key=GROQ_API_KEY)

# ============================================================================
# 2. DATABASE LAYER (SQLite Persistence)
# ============================================================================
DB_PATH = "user_data.db"


def get_db_connection():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize database schema with users and feedback tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table with referral system fields
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            user_type TEXT DEFAULT 'BASIC',
            pro_expiry TIMESTAMP NULL,
            referral_code TEXT UNIQUE,
            referred_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Feedback table (locks referral UI until submitted)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            feedback_text TEXT NOT NULL,
            rating INTEGER,
            category TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Query table for tracking usage (with Socratic audit)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            subject TEXT,
            query_text TEXT,
            response_text TEXT,
            is_socratic BOOLEAN DEFAULT 1,
            audit_notes TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Add feedback_submitted column to users table for persistence
    # (handles existing tables without this column)
    try:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN feedback_submitted BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        # Column already exists
        pass

    conn.commit()
    conn.close()

# ============================================================================
# 3. USER AUTHENTICATION & REFERRAL SYSTEM
# ============================================================================


def hash_password(password):
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_referral_code():
    """Generate a unique 6-character referral code."""
    return secrets_lib.token_hex(3).upper()


def create_user(username, password, email=None, referral_code_input=None):
    """Create a new user with optional referral."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if username exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return False, "Username already exists"

        # Generate referral code for new user
        my_referral_code = generate_referral_code()

        # Validate referrer code if provided
        referrer_id = None
        if referral_code_input:
            cursor.execute("SELECT id, user_type, pro_expiry FROM users WHERE referral_code = ?",
                           (referral_code_input.upper(),))
            referrer = cursor.fetchone()
            if referrer:
                referrer_id = referral_code_input.upper()

        # Create user
        password_hash = hash_password(password)
        cursor.execute("""
            INSERT INTO users (username, password_hash, email, referral_code, referred_by)
            VALUES (?, ?, ?, ?, ?)
        """, (username, password_hash, email, my_referral_code, referrer_id))

        user_id = cursor.lastrowid

        # Apply referral bonus if valid referrer
        if referrer_id:
            # Referee gets +2 days BASIC
            cursor.execute("""
                UPDATE users 
                SET user_type = 'BASIC', 
                    pro_expiry = datetime('now', '+2 days')
                WHERE id = ?
            """, (user_id,))

            # Referrer gets +3 days
            cursor.execute("""
                UPDATE users 
                SET pro_expiry = datetime(COALESCE(pro_expiry, 'now'), '+3 days')
                WHERE referral_code = ?
            """, (referrer_id,))

        conn.commit()
        conn.close()
        return True, "User created successfully!"

    except Exception as e:
        conn.close()
        return False, str(e)


def authenticate_user(username, password):
    """Authenticate user and return user data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    password_hash = hash_password(password)
    cursor.execute("""
        SELECT * FROM users 
        WHERE username = ? AND password_hash = ?
    """, (username, password_hash))

    user = cursor.fetchone()
    conn.close()

    if user:
        # Update last_active
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET last_active = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (user['id'],))
        conn.commit()
        conn.close()
        return dict(user)
    return None


def get_user_by_id(user_id):
    """Get user data by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


def has_submitted_feedback(user_id):
    """Check if user has submitted feedback (checks DB flag for persistence)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # First check the feedback_submitted flag in users table
    cursor.execute(
        "SELECT feedback_submitted FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()

    if result and result['feedback_submitted']:
        conn.close()
        return True

    # Fallback: check if feedback exists in feedback table
    cursor.execute("SELECT id FROM feedback WHERE user_id = ?", (user_id,))
    fb_result = cursor.fetchone()
    conn.close()

    # Sync the flag if feedback exists but flag wasn't set
    if fb_result:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET feedback_submitted = 1 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True

    return False


def submit_feedback(user_id, feedback_text, rating, category):
    """Submit feedback for a user and mark feedback_submitted flag."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO feedback (user_id, feedback_text, rating, category)
        VALUES (?, ?, ?, ?)
    """, (user_id, feedback_text, rating, category))

    # Update the feedback_submitted flag in users table for persistence
    cursor.execute("""
        UPDATE users SET feedback_submitted = 1 WHERE id = ?
    """, (user_id,))

    conn.commit()
    conn.close()


def audit_socratic_response(query, response):
    """
    Post-Query Audit: Check if Arjun stayed Socratic or gave a direct answer.
    Returns (is_socratic: bool, audit_notes: str)
    """
    try:
        audit_prompt = f"""You are evaluating if a JEE tutor response follows Socratic teaching methods.

A response is NON-SOCRATIC if it:
- Directly gives the final answer without guiding questions
- Solves the entire problem without explaining the approach first
- Does not encourage student to think about edge cases or traps

A response is SOCRATIC if it:
- Starts with a conceptual question or hints at the approach
- Breaks down the problem into steps before solving
- Mentions common traps, edge cases, or verification steps
- Encourages student intuition over rote calculation

Student Query: {query[:500]}

Tutor Response: {response[:1000]}

Output ONLY JSON: {{"is_socratic": true/false, "reason": "brief explanation"}}
"""
        audit = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            messages=[{"role": "system", "content": "Output ONLY valid JSON."},
                      {"role": "user", "content": audit_prompt}]
        )

        result = json.loads(audit.choices[0].message.content.strip())
        return result.get('is_socratic', True), result.get('reason', '')

    except Exception as e:
        # Default to True on audit failure
        return True, f"Audit error: {str(e)}"


def is_pro_user(user_data):
    """Check if user has PRO access."""
    if not user_data:
        return False
    if user_data.get('user_type') == 'PRO':
        return True
    pro_expiry = user_data.get('pro_expiry')
    if pro_expiry:
        try:
            expiry = datetime.fromisoformat(pro_expiry)
            return datetime.now() < expiry
        except:
            pass
    return False


def apply_referral_code(user_id, referral_code):
    """Apply a referral code to extend PRO access."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Validate referral code
    cursor.execute("SELECT id, user_type, pro_expiry FROM users WHERE referral_code = ?",
                   (referral_code.upper(),))
    referrer = cursor.fetchone()

    if not referrer:
        conn.close()
        return False, "Invalid referral code"

    if referrer['id'] == user_id:
        conn.close()
        return False, "Cannot use your own referral code"

    # Check if already used by this user
    user = get_user_by_id(user_id)
    if user and user.get('referred_by'):
        conn.close()
        return False, "Referral code already used"

    # Apply +2 days to user (referee)
    cursor.execute("""
        UPDATE users 
        SET referred_by = ?, 
            pro_expiry = datetime(COALESCE(pro_expiry, 'now'), '+2 days')
        WHERE id = ?
    """, (referral_code.upper(), user_id))

    # Apply +3 days to referrer
    cursor.execute("""
        UPDATE users 
        SET pro_expiry = datetime(COALESCE(pro_expiry, 'now'), '+3 days')
        WHERE referral_code = ?
    """, (referral_code.upper(),))

    conn.commit()
    conn.close()
    return True, "Referral applied! +2 days for you, +3 days for referrer"


# ============================================================================
# 4. MASTER QUALITY PROMPTS (Socratic + High-Depth)
# ============================================================================
STRICT_GUARDRAIL = """
### CRITICAL RULES:
- NO PREAMBLE. NO CONVERSATIONAL FLUFF.
- SELF-VERIFICATION: Verify logic against JEE Advanced standards before outputting.
- TERMINATE immediately after the technical explanation.
"""

PROMPTS = {
    "CHEMISTRY": f"""You are a JEE Chemistry Specialist (AIR < 100).
- REASONING: Focus on Electronic Effects (Resonance > Hyperconjugation > Inductive).
- VISUALS: Use Mermaid.js (graph LR) for reaction maps.
- GROUNDING: Cite NCERT Class 11/12 Units.
{STRICT_GUARDRAIL}""",

    "PHYSICS": f"""You are a JEE Physics Specialist (AIR < 100).
- REASONING: Start from fundamental laws. Use Variable Extraction first.
- VISUALS: Describe FBD setup in Mermaid.js.
{STRICT_GUARDRAIL}""",

    "MATHEMATICS": f"""You are a JEE Mathematics Specialist (AIR < 100).
- REASONING: State Domain/Range and check for boundary edge cases (0, infinity).
- VISUALS: Use LaTeX for every single step.
{STRICT_GUARDRAIL}""",

    "GENERAL": f"""You are the JEE Vertical Reasoning Engine (AIR < 100 Coach).

### INTENT HANDLING:
1. GREETING (Hi/Hello): Reply with a professional welcome. State you are a specialized JEE Reasoning Engine. Ask for a Physics, Chemistry, or Math query.
2. IDENTITY (Who are you?): Explain your 'Vertical Reasoning' edge, NCERT grounding, and 'Trap Detection' logic.
3. SYLLABUS/STRATEGY: Provide granular tables for weightage and 5-year trend analysis.

{STRICT_GUARDRAIL}"""
}

# ============================================================================
# 5. SMARTER ROUTER
# ============================================================================


def route_subject(user_query):
    query_lower = user_query.strip().lower()

    # Intent 1: Greetings & Short Talk
    greetings = ["hi", "hello", "hey", "who are you", "what is this"]
    if query_lower in greetings or len(query_lower) < 4:
        return "GENERAL"

    # Intent 2: Administrative/Strategy
    admin_triggers = ["syllabus", "date", "weightage",
                      "tips", "strategy", "prep", "how to"]
    if any(trigger in query_lower for trigger in admin_triggers):
        return "GENERAL"

    # Intent 3: Technical Subject Routing (AI-Powered)
    try:
        classification = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            messages=[{"role": "system", "content": "Classify: PHYSICS, CHEMISTRY, or MATHEMATICS. Output ONLY one word."},
                      {"role": "user", "content": user_query}]
        )
        return classification.choices[0].message.content.strip().upper()
    except:
        return "GENERAL"


# ============================================================================
# 6. STREAMLIT APP
# ============================================================================
st.set_page_config(page_title="Arjun - JEE Vertical Reasoner",
                   layout="wide", page_icon="🏹")

# Initialize database on startup
init_database()

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_data' not in st.session_state:
    st.session_state.user_data = None
if 'feedback_submitted' not in st.session_state:
    st.session_state.feedback_submitted = False
if 'show_admin' not in st.session_state:
    st.session_state.show_admin = False

# ============================================================================
# SIDEBAR NAVIGATION
# ============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/target.png", width=60)
    st.title("🏹 Arjun")
    st.caption("AIR 92 Elite JEE Mentor")

    st.divider()

    if st.session_state.logged_in:
        user = st.session_state.user_data
        st.write(f"**Welcome, {user['username']}**")

        # Display user status
        pro_status = "👑 PRO" if is_pro_user(user) else "⚡ BASIC"
        st.info(f"Status: {pro_status}")

        if is_pro_user(user):
            expiry = user.get('pro_expiry', 'N/A')
            st.caption(f"Pro expires: {expiry}")

        st.divider()

        # Navigation
        page = st.radio("Navigate", [
                        "📚 Solve Problems", "📝 Feedback", "🎁 Referrals", "👤 Profile"], index=0)

        st.divider()

        # Logout
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_data = None
            st.session_state.feedback_submitted = False
            st.rerun()

        # Admin access (hidden trigger)
        admin_trigger = st.text_input(
            "Admin Access", type="password", key="admin_input")
        if admin_trigger == ADMIN_PASSCODE:
            st.session_state.show_admin = True
            st.rerun()

        # Admin page
        if st.session_state.show_admin:
            st.divider()
            st.warning("🔐 ADMIN CONSOLE")

            if st.button("📊 View Users", use_container_width=True):
                page = "admin_users"
            if st.button("💬 View Feedback", use_container_width=True):
                page = "admin_feedback"
            if st.button("📈 Query Analytics", use_container_width=True):
                page = "admin_queries"
            if st.button("❌ Close Admin", use_container_width=True):
                st.session_state.show_admin = False
                st.rerun()

        # Route to page
        if page == "📝 Feedback":
            show_feedback_page()
        elif page == "🎁 Referrals":
            show_referrals_page()
        elif page == "👤 Profile":
            show_profile_page()
        elif page == "admin_users":
            show_admin_users()
        elif page == "admin_feedback":
            show_admin_feedback()
        elif page == "admin_queries":
            show_admin_queries()
        else:
            pass  # Stay on main solve page

    else:
        # Login/Signup page
        auth_mode = st.radio("Account", ["Login", "Sign Up"])

        if auth_mode == "Login":
            st.subheader("🔐 Login")
            login_username = st.text_input("Username", key="login_user")
            login_password = st.text_input(
                "Password", type="password", key="login_pass")

            if st.button("Login", use_container_width=True):
                user = authenticate_user(login_username, login_password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_data = user
                    st.session_state.feedback_submitted = has_submitted_feedback(
                        user['id'])
                    st.success("Login successful!")
                    st.toast("✅ Login successful! Welcome back.",
                             icon="success")
                    st.rerun()
                else:
                    st.error("Invalid credentials")

        else:  # Sign Up
            st.subheader("📝 Create Account")
            new_username = st.text_input("Username", key="signup_user")
            new_email = st.text_input("Email (optional)", key="signup_email")
            new_password = st.text_input(
                "Password", type="password", key="signup_pass")
            confirm_password = st.text_input(
                "Confirm Password", type="password", key="signup_confirm")
            referral_input = st.text_input(
                "Referral Code (optional)", key="signup_referral")

            if st.button("Sign Up", use_container_width=True):
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                elif len(new_password) < 4:
                    st.error("Password must be at least 4 characters")
                else:
                    success, message = create_user(
                        new_username, new_password, new_email, referral_input)
                    if success:
                        st.success(message)
                        st.toast("✅ Account created! Please login.",
                                 icon="success")
                        st.info("Please login with your credentials")
                    else:
                        st.error(message)

st.divider()

# ============================================================================
# MAIN CONTENT AREA
# ============================================================================
if st.session_state.logged_in:
    st.header("📚 JEE Vertical Reasoning Engine")
    st.caption("Socratic Scaffolding • Trap Detection • NCERT Grounding")

    # Pro gate message
    if not is_pro_user(st.session_state.user_data):
        st.warning(
            "⚡ BASIC Plan: Complete problems daily to unlock PRO features. Submit feedback to unlock referrals!")

    user_input = st.text_area("Enter your JEE problem or ask about our edge:", height=150,
                              placeholder="e.g., Find the limit: lim(x→0) sin(x)/x")

    if st.button("🧠 Generate Expert Solution"):
        if user_input:
            with st.spinner("🔬 Analyzing via Multi-Agent Chain..."):
                subject = route_subject(user_input)

                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    temperature=0.2,
                    messages=[
                        {"role": "system", "content": PROMPTS.get(
                            subject, PROMPTS["GENERAL"])},
                        {"role": "user", "content": user_input}
                    ]
                )

                response = completion.choices[0].message.content

                # Post-Query Socratic Audit (async-style, non-blocking UX)
                is_socratic, audit_notes = audit_socratic_response(
                    user_input, response)

                # Log query with audit results
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO query_log (user_id, subject, query_text, response_text, is_socratic, audit_notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (st.session_state.user_data['id'], subject, user_input,
                      response, is_socratic, audit_notes))
                conn.commit()
                conn.close()

                st.info(f"🎯 Expert Vertical Engaged: {subject}")
                st.markdown(response)

                # Show audit status (subtle, for Alpha testing)
                if not is_socratic:
                    st.caption(
                        "🔍 Alpha Audit: This response may have given too direct an answer. We're improving!")

                st.divider()

                col1, col2 = st.columns(2)
                with col1:
                    if st.download_button("📥 Download .txt", data=response,
                                          file_name=f"JEE_{subject}_Solution.txt",
                                          use_container_width=True):
                        pass
                with col2:
                    st.download_button("📋 Copy Solution", data=response,
                                       file_name="solution.txt",
                                       use_container_width=True)
        else:
            st.warning("Please enter a problem to solve")

else:
    # Landing page for non-logged-in users
    st.header("🏹 Welcome to Arjun")
    st.subheader(
        "Elite JEE Mentor - Building Intuition, Not Just Solving Homework")

    st.markdown("""
    ### Why Arjun?
    
    **🎯 Socratic Scaffolding**: We don't just give answers. We guide you through conceptual questions that build deep intuition.
    
    **⚡ Groq-Powered (Llama 3.3 70B)**: High-speed reasoning specifically tuned for JEE Advanced complexity.
    
    **📚 NCERT Grounded**: Every solution cites relevant NCERT Class 11/12 concepts.
    
    **🔍 Trap Detection**: We identify hidden discontinuities, edge cases, and common mistakes before you make them.
    """)

    st.info("👈 Login or Sign Up in the sidebar to start solving!")

# ============================================================================
# PAGE FUNCTIONS
# ============================================================================


def show_feedback_page():
    """Feedback submission page."""
    st.subheader("📝 Submit Feedback")

    user = st.session_state.user_data

    # Check if already submitted
    if st.session_state.feedback_submitted:
        st.success("✅ Feedback already submitted! Thank you for your input.")
        st.info("Your referral code is now unlocked in the 🎁 Referrals section.")
        return

    st.markdown("""
    ### Why Submit Feedback?
    
    - 🔓 **Unlock Referrals**: Get your unique referral code to invite friends
    - 📈 **Shape Arjun**: Your input directly improves the mentor
    - 🎁 **Earn PRO Days**: Both you and your referrals get bonus access
    """)

    with st.form("feedback_form"):
        rating = st.slider("Rate Arjun (1-5)", 1, 5, 4)
        category = st.selectbox("Category", [
                                "General Feedback", "Bug Report", "Feature Request", "Success Story"])
        feedback_text = st.text_area("Your Feedback", height=150,
                                     placeholder="Share your experience, suggestions, or any issues you've encountered...")

        submitted = st.form_submit_button(
            "Submit Feedback", use_container_width=True)

        if submitted:
            if len(feedback_text.strip()) < 10:
                st.error(
                    "Please provide more detailed feedback (at least 10 characters)")
            else:
                submit_feedback(
                    user['id'], feedback_text.strip(), rating, category)
                st.session_state.feedback_submitted = True

                # Refresh user data
                st.session_state.user_data = get_user_by_id(user['id'])

                # MAGIC MOMENT: Celebrate the unlock
                st.success(
                    "🎉 Feedback submitted! Your referral code is now unlocked!")
                st.toast("🎉 Referrals unlocked! Check it out in the sidebar.",
                         icon="success")
                st.balloons()
                st.rerun()


def show_referrals_page():
    """Referral system page - HIDDEN until feedback submitted."""
    user = st.session_state.user_data

    # FEEDBACK GATE: Hide entire referral UI if feedback not submitted
    if not st.session_state.feedback_submitted:
        st.subheader("🎁 Referral Program")
        st.warning("🔒 Referral code is locked until you submit feedback.")
        st.info(
            "👈 Go to **Feedback** section to submit your review and unlock your referral code!")

        st.markdown("""
        ### How Referrals Work
        
        | Action | Reward |
        |--------|--------|
        | Your friend signs up with your code | They get **+2 days** PRO |
        | Your friend signs up with your code | You get **+3 days** PRO |
        | Unlimited referrals | Stack your PRO access! |
        """)
        return

    # Referral UI (unlocked after feedback)
    st.subheader("🎁 Referral Program")

    # MAGIC MOMENT: Celebrate the unlocked state
    st.success("🎉 Referral system unlocked! Start earning PRO days!")
    st.markdown("### ✨ Your Referral Code")

    referral_code = user.get('referral_code', 'N/A')

    # Display referral code prominently with celebratory styling
    st.code(referral_code, language="text")

    st.info(f"""
    **Share this code with friends!**
    
    - They get **+2 days** PRO access
    - You get **+3 days** PRO access
    - No limit on referrals!
    """)

    st.divider()

    # Apply referral code form
    st.subheader("🎟️ Have a Referral Code?")

    with st.form("apply_referral"):
        code_input = st.text_input(
            "Enter Referral Code", placeholder="Enter your friend's code")
        applied = st.form_submit_button("Apply Code", use_container_width=True)

        if applied:
            if code_input.strip():
                success, message = apply_referral_code(
                    user['id'], code_input.strip())
                if success:
                    st.success(message)
                    st.toast("🎁 Referral applied! PRO days added.",
                             icon="success")
                    # Refresh user data
                    st.session_state.user_data = get_user_by_id(user['id'])
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.warning("Please enter a referral code")

    # Referral stats
    st.divider()
    st.subheader("📊 Your Referral Stats")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as count FROM users WHERE referred_by = ?
    """, (referral_code,))
    referred_count = cursor.fetchone()['count']
    conn.close()

    st.metric("Friends Referred", referred_count)

    if referred_count > 0:
        st.write(f"**Total PRO Days Earned**: {referred_count * 3} days")


def show_profile_page():
    """User profile page."""
    user = st.session_state.user_data
    st.subheader("👤 Your Profile")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Username", user['username'])
        st.metric("Email", user.get('email', 'Not provided'))

    with col2:
        pro_status = "👑 PRO" if is_pro_user(user) else "⚡ BASIC"
        st.metric("Status", pro_status)
        st.metric("Member Since", user.get('created_at', 'N/A'))

    st.divider()

    # PRO expiry info
    if is_pro_user(user):
        expiry = user.get('pro_expiry', 'N/A')
        st.success(f"👑 PRO Access until: {expiry}")
    else:
        st.info("⚡ Complete daily problems and submit feedback to unlock PRO features!")

    st.divider()

    # Usage stats
    st.subheader("📊 Your Activity")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT subject, COUNT(*) as count 
        FROM query_log 
        WHERE user_id = ? 
        GROUP BY subject
    """, (user['id'],))
    stats = cursor.fetchall()
    conn.close()

    if stats:
        df = pd.DataFrame(stats, columns=['Subject', 'Problems Solved'])
        st.bar_chart(df.set_index('Subject'))
    else:
        st.caption("No problems solved yet. Start learning!")

# ============================================================================
# ADMIN CONSOLE PAGES
# ============================================================================


def show_admin_users():
    """Admin: View all users."""
    st.subheader("🔐 Admin Console - Users")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
    users = cursor.fetchall()
    conn.close()

    if users:
        df = pd.DataFrame(users, columns=[desc[0]
                          for desc in cursor.description])

        # Display key columns
        display_df = df[['id', 'username', 'email', 'user_type', 'pro_expiry',
                         'referral_code', 'referred_by', 'created_at']].copy()
        display_df.columns = ['ID', 'Username', 'Email', 'Type', 'PRO Expiry',
                              'Ref Code', 'Referred By', 'Joined']
        st.dataframe(display_df, use_container_width=True)

        st.metric("Total Users", len(users))
    else:
        st.info("No users registered yet")


def show_admin_feedback():
    """Admin: View all feedback."""
    st.subheader("🔐 Admin Console - Feedback")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT f.*, u.username 
        FROM feedback f 
        JOIN users u ON f.user_id = u.id 
        ORDER BY f.submitted_at DESC
    """)
    feedback = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()

    if feedback:
        df = pd.DataFrame(feedback, columns=columns)

        # Display
        display_df = df[['id', 'username', 'feedback_text',
                         'rating', 'category', 'submitted_at']].copy()
        display_df.columns = ['ID', 'User', 'Feedback',
                              'Rating', 'Category', 'Submitted']
        st.dataframe(display_df, use_container_width=True)

        # Stats
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Feedback", len(feedback))
        col2.metric("Avg Rating", f"{df['rating'].mean():.1f}/5")
        col3.metric("Response Rate", f"{len(feedback)} submissions")
    else:
        st.info("No feedback submitted yet")


def show_admin_queries():
    """Admin: View query analytics."""
    st.subheader("🔐 Admin Console - Query Analytics")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total queries
    cursor.execute("SELECT COUNT(*) as count FROM query_log")
    total = cursor.fetchone()['count']

    # By subject
    cursor.execute("""
        SELECT subject, COUNT(*) as count 
        FROM query_log 
        GROUP BY subject
    """)
    by_subject = cursor.fetchall()

    # Recent queries
    cursor.execute("""
        SELECT q.*, u.username 
        FROM query_log q 
        LEFT JOIN users u ON q.user_id = u.id 
        ORDER BY q.timestamp DESC 
        LIMIT 20
    """)
    recent = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    conn.close()

    col1, col2 = st.columns(2)
    col1.metric("Total Queries", total)

    if by_subject:
        df = pd.DataFrame(by_subject, columns=['subject', 'count'])
        col2.bar_chart(df.set_index('subject'))

    if recent:
        st.subheader("Recent Queries")
        df = pd.DataFrame(recent, columns=columns)
        display_df = df[['id', 'username', 'subject',
                         'query_text', 'timestamp']].copy()
        display_df.columns = ['ID', 'User', 'Subject', 'Query', 'Time']
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No queries logged yet")
