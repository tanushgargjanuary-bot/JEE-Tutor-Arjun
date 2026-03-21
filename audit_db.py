"""
Database Schema Audit Script for Arjun (JEE Tutor)
Run this to verify the database schema is correctly initialized.
"""
import sqlite3
import os

DB_PATH = "user_data.db"

def audit_schema():
    """Audit the database schema."""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database '{DB_PATH}' does not exist yet.")
        print("   Run the Streamlit app first to initialize the database.")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 60)
    print("🔍 ARJUN DATABASE SCHEMA AUDIT")
    print("=" * 60)
    
    # Check tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    expected_tables = ['users', 'feedback', 'query_log']
    
    print("\n📊 TABLES CHECK:")
    for table in expected_tables:
        if table in tables:
            print(f"   ✅ {table}")
        else:
            print(f"   ❌ {table} - MISSING!")
    
    # Audit users table
    print("\n👤 USERS TABLE SCHEMA:")
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"   - {col[1]} ({col[2]})")
    
    # Audit feedback table
    print("\n📝 FEEDBACK TABLE SCHEMA:")
    cursor.execute("PRAGMA table_info(feedback)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"   - {col[1]} ({col[2]})")
    
    # Audit query_log table
    print("\n📈 QUERY_LOG TABLE SCHEMA:")
    cursor.execute("PRAGMA table_info(query_log)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"   - {col[1]} ({col[2]})")
    
    # Stats
    print("\n📊 DATA STATS:")
    cursor.execute("SELECT COUNT(*) FROM users")
    print(f"   Total Users: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM feedback")
    print(f"   Total Feedback: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM query_log")
    print(f"   Total Queries: {cursor.fetchone()[0]}")
    
    # Check for users with feedback
    print("\n🔓 FEEDBACK GATE STATUS:")
    cursor.execute("""
        SELECT u.username, 
               CASE WHEN f.id IS NOT NULL THEN '✅ Unlocked' ELSE '🔒 Locked' END as status
        FROM users u
        LEFT JOIN feedback f ON u.id = f.user_id
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]}")
    
    conn.close()
    print("\n" + "=" * 60)
    print("✅ AUDIT COMPLETE")
    print("=" * 60)
    return True

if __name__ == "__main__":
    audit_schema()
