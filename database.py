"""
Database Layer for Arjun - JEE Vertical Reasoning Engine

Handles all SQLite database operations including user authentication,
feedback management, referral system, and query logging.
"""

import bcrypt
import sqlite3
from datetime import datetime

import secrets as secrets_lib

DB_PATH = "user_data.db"
BCRYPT_ROUNDS = 12


def get_db_connection():
    """Create and return a SQLite database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize database schema with all required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

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

    try:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN feedback_submitted BOOLEAN DEFAULT 0"
        )
    except sqlite3.OperationalError:
        pass

    # Add indexes for query performance
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_referral ON users(referral_code)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_query_log_user ON query_log(user_id, timestamp)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(user_id, submitted_at)")

    conn.commit()
    conn.close()


def hash_password(password):
    """Hash password using bcrypt with salt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(password, password_hash):
    """Verify password against bcrypt hash."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def generate_referral_code():
    """Generate a unique 6-character referral code."""
    return secrets_lib.token_hex(3).upper()


def create_user(username, password, email=None, referral_code_input=None):
    """Create a new user account with optional referral code."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return False, "Username already exists"

        my_referral_code = generate_referral_code()

        referrer_id = None
        if referral_code_input:
            cursor.execute(
                "SELECT id, user_type, pro_expiry FROM users WHERE referral_code = ?",
                (referral_code_input.upper(),)
            )
            referrer = cursor.fetchone()
            if referrer:
                referrer_id = referral_code_input.upper()

        password_hash = hash_password(password)
        cursor.execute("""
            INSERT INTO users (username, password_hash, email, referral_code, referred_by)
            VALUES (?, ?, ?, ?, ?)
        """, (username, password_hash, email, my_referral_code, referrer_id))

        user_id = cursor.lastrowid

        if referrer_id:
            cursor.execute("""
                UPDATE users
                SET user_type = 'BASIC',
                    pro_expiry = datetime('now', '+2 days')
                WHERE id = ?
            """, (user_id,))

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
    """Authenticate a user with username and password."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()

    if user and verify_password(password, user['password_hash']):
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
    """Retrieve user data by user ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


def has_submitted_feedback(user_id):
    """Check if a user has submitted feedback."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT feedback_submitted FROM users WHERE id = ?",
        (user_id,)
    )
    result = cursor.fetchone()

    if result and result['feedback_submitted']:
        conn.close()
        return True

    cursor.execute(
        "SELECT id FROM feedback WHERE user_id = ?",
        (user_id,)
    )
    fb_result = cursor.fetchone()
    conn.close()

    if fb_result:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET feedback_submitted = 1 WHERE id = ?",
            (user_id,)
        )
        conn.commit()
        conn.close()
        return True

    return False


def submit_feedback(user_id, feedback_text, rating, category):
    """Submit user feedback and mark feedback_submitted flag."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO feedback (user_id, feedback_text, rating, category)
        VALUES (?, ?, ?, ?)
    """, (user_id, feedback_text, rating, category))

    cursor.execute("""
        UPDATE users SET feedback_submitted = 1 WHERE id = ?
    """, (user_id,))

    conn.commit()
    conn.close()


def is_pro_user(user_data):
    """Check if a user has PRO access status."""
    if not user_data:
        return False
    if user_data.get('user_type') == 'PRO':
        return True
    pro_expiry = user_data.get('pro_expiry')
    if pro_expiry:
        try:
            expiry = datetime.fromisoformat(pro_expiry)
            return datetime.now() < expiry
        except (ValueError, TypeError):
            pass
    return False


def apply_referral_code(user_id, referral_code):
    """Apply a referral code to extend PRO access."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, user_type, pro_expiry FROM users WHERE referral_code = ?",
        (referral_code.upper(),)
    )
    referrer = cursor.fetchone()

    if not referrer:
        conn.close()
        return False, "Invalid referral code"

    if referrer['id'] == user_id:
        conn.close()
        return False, "Cannot use your own referral code"

    user = get_user_by_id(user_id)
    if user and user.get('referred_by'):
        conn.close()
        return False, "Referral code already used"

    cursor.execute("""
        UPDATE users
        SET referred_by = ?,
            pro_expiry = datetime(COALESCE(pro_expiry, 'now'), '+2 days')
        WHERE id = ?
    """, (referral_code.upper(), user_id))

    cursor.execute("""
        UPDATE users
        SET pro_expiry = datetime(COALESCE(pro_expiry, 'now'), '+3 days')
        WHERE referral_code = ?
    """, (referral_code.upper(),))

    conn.commit()
    conn.close()
    return True, "Referral applied! +2 days for you, +3 days for referrer"
