import sqlite3
import bcrypt
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect("database/auth_system.db")
conn.row_factory = sqlite3.Row

cur = conn.execute("SELECT user_id, username, password_hash FROM users")
for row in cur.fetchall():
    ph = row["password_hash"]
    print(f"\nUser: {row['username']}")
    print(f"  Hash type: {type(ph)}")
    
    for test_pw in ["Admin@123", "Demo@123", "Password@123", "Test@123", "Nandh@123", 
                     "admin123", "demo123", "Faculty@123", "Harctik@123", "harctik001@AK",
                     "Qwerty@123", "Welcome@123"]:
        try:
            if isinstance(ph, str):
                ph_bytes = ph.encode("utf-8")
            else:
                ph_bytes = ph
            if bcrypt.checkpw(test_pw.encode("utf-8"), ph_bytes):
                print(f"  >>> PASSWORD FOUND: {test_pw}")
                break
        except Exception as e:
            print(f"  Error with {test_pw}: {e}")
            break
    else:
        print(f"  No common password matched")

conn.close()
