"""Get admin user ID."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import db

# Get admin users
result = db.client.table("admin_users").select("id, email, full_name").execute()

print("Admin Users:")
for admin in result.data:
    print(f"  ID: {admin['id']}")
    print(f"  Email: {admin['email']}")
    print(f"  Name: {admin['full_name']}")
    print()
