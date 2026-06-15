"""Reset the local SQLite database — remove all users and related data."""
import sqlite3

conn = sqlite3.connect("database/auth_system.db")
c = conn.cursor()

# Get all table names
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print("Tables found:", tables)

# Delete from all related tables in correct order (foreign keys)
delete_order = [
    "investments", "beneficiaries", "cards", "notifications",
    "device_fingerprints", "enrollment_state", "enrollment_history",
    "session_risk_timeline", "session_snapshots",
    "mouse_events", "keystroke_events",
    "behavioral_data", "auth_events", "audit_evidence",
    "otp_codes", "password_reset_tokens", "consent_records",
    "sessions", "model_metadata", "users",
]

for table in delete_order:
    if table in tables:
        c.execute(f"DELETE FROM {table}")
        print(f"  Cleared {table}: {c.rowcount} rows deleted")

conn.commit()

# Verify
c.execute("SELECT COUNT(*) FROM users")
print(f"\nUsers remaining: {c.fetchone()[0]}")
conn.close()
print("Done! Database is fresh — ready for new signups.")
