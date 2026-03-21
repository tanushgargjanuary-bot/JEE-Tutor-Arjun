import sqlite3

def migrate():
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    
    print("🚀 Starting Migration...")
    
    # 1. Add new columns to the users table
    try:
        c.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
        print("✅ Added referral_code column.")
    except sqlite3.OperationalError:
        print("ℹ️ referral_code column already exists.")

    try:
        c.execute("ALTER TABLE users ADD COLUMN pro_expiry DATE")
        print("✅ Added pro_expiry column.")
    except sqlite3.OperationalError:
        print("ℹ️ pro_expiry column already exists.")

    try:
        c.execute("ALTER TABLE users ADD COLUMN total_referrals INTEGER DEFAULT 0")
        print("✅ Added total_referrals column.")
    except sqlite3.OperationalError:
        print("ℹ️ total_referrals column already exists.")

    # 2. Create the referrals tracking table
    c.execute('''CREATE TABLE IF NOT EXISTS referrals 
                 (referrer_id TEXT, referee_id TEXT, timestamp DATETIME, 
                 PRIMARY KEY (referrer_id, referee_id))''')
    print("✅ Referrals table ready.")

    conn.commit()
    conn.close()
    print("🏁 Migration Finished!")

if __name__ == "__main__":
    migrate()
