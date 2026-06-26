import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.database import init_db, create_user, list_users

def main():
    init_db()
    print("=== LIDT Report Generator — Admin Setup ===\n")

    existing = list_users()
    if existing:
        print("Existing users:")
        for u in existing:
            role = "admin" if u["is_admin"] else "user"
            print(f"  [{u['id']}] {u['username']} ({role})")
        print()

    username = input("New username: ").strip()
    if not username:
        print("Username cannot be empty."); return

    password = input("Password: ").strip()
    if not password:
        print("Password cannot be empty."); return

    is_admin = input("Admin? (y/n): ").strip().lower() == "y"

    try:
        create_user(username, password, is_admin=is_admin)
        role = "admin" if is_admin else "user"
        print(f"\nUser '{username}' created as {role}.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()