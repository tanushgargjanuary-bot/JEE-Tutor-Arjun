import streamlit as st
import sqlite3
import hashlib
from datetime import datetime, date

# --- 1. THE AUTO-MIGRATOR (Runs on every boot) ---
def ensure_database_schema():
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    
    # Check and add columns to 'users' table
    columns_to_add = [
        ("referral_code", "TEXT"),
        ("pro_expiry", "DATE"),
        ("total_referrals", "INTEGER DEFAULT 0")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass # Column already exists, keep moving

    # Ensure the referrals tracking table exists
    c.execute('''CREATE TABLE IF NOT EXISTS referrals 
                 (referrer_id TEXT, referee_id TEXT, timestamp DATETIME, 
                 PRIMARY KEY (referrer_id, referee_id))''')
    
    conn.commit()
    conn.close()

# Run the migrator before the app starts
ensure_database_schema()

# --- 2. AUTH & REFERRAL LOGIC ---
# (The rest of your Groq client and functions go here...)
