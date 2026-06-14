import os
import sys
from cryptography.fernet import Fernet
from app.app_impl import create_app
from app.extensions import get_db

def rotate_keys(old_key: str, new_key: str):
    print("Rotating BACKUP_FERNET keys...")
    app = create_app()
    with app.app_context():
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Fetch all encrypted backup codes
            cursor.execute("SELECT code_id, user_id, code_hash, encrypted_code FROM backup_codes")
            rows = cursor.fetchall()
            
            if not rows:
                print("No backup codes found to rotate.")
                return

            old_f = Fernet(old_key.encode('utf-8'))
            new_f = Fernet(new_key.encode('utf-8'))
            
            success = 0
            failed = 0
            
            for row in rows:
                try:
                    # Decrypt with old key
                    decrypted = old_f.decrypt(row['encrypted_code'].encode('utf-8')).decode('utf-8')
                    # Encrypt with new key
                    re_encrypted = new_f.encrypt(decrypted.encode('utf-8')).decode('utf-8')
                    
                    # Update DB
                    cursor.execute(
                        "UPDATE backup_codes SET encrypted_code = ? WHERE code_id = ?",
                        (re_encrypted, row['code_id'])
                    )
                    success += 1
                except Exception as e:
                    print(f"Failed to rotate code_id {row['code_id']}: {e}")
                    failed += 1
                    
            if hasattr(conn, "commit"):
                conn.commit()
            
            print(f"Rotation complete. {success} succeeded, {failed} failed.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python rotate_fernet_key.py <OLD_KEY> <NEW_KEY>")
        print("Generate a new key using: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode('utf-8'))\"")
        sys.exit(1)
        
    old_key = sys.argv[1]
    new_key = sys.argv[2]
    rotate_keys(old_key, new_key)
