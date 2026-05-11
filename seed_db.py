import os
from app.app_impl import create_app
from app.database import DatabaseManager
from app.config import Settings

def seed():
    settings = Settings()
    # Ensure directory exists for SQLite
    if settings.DATABASE_PATH != ":memory:":
        os.makedirs(os.path.dirname(settings.DATABASE_PATH), exist_ok=True)

    print(f"Connecting to database at {settings.DATABASE_PATH}...")
    db = DatabaseManager(settings.DATABASE_PATH)
    
    # Try to create an admin user
    try:
        user_id, mfa_secret = db.create_user("faculty_admin", "faculty@example.com", "password123")
        if user_id:
            db.update_user_role(user_id, "admin")
            print(f"✅ Successfully created admin user: 'faculty_admin' with password 'password123'")
        else:
            print(f"ℹ️ User 'faculty_admin' already exists.")
    except Exception as e:
        print(f"Error creating user: {e}")

    # Create a regular user for testing
    try:
        user_id, mfa_secret = db.create_user("demo_user", "demo@example.com", "demo123")
        if user_id:
            print(f"✅ Successfully created test user: 'demo_user' with password 'demo123'")
        else:
            print(f"ℹ️ User 'demo_user' already exists.")
    except Exception as e:
        print(f"Error creating test user: {e}")
        
    print("Database seeding complete!")

if __name__ == "__main__":
    seed()
