"""
Create initial admin user in production database.
"""
import sys
import os
from datetime import datetime
from uuid import uuid4

sys.path.insert(0, os.path.dirname(__file__))

from app.core.security import hash_password
from app.db.supabase import db
from app.core.timezone import get_cat_now

# Admin details
ADMIN_EMAIL = "Jeffrey.Murungweni@rtg.co.zw"
ADMIN_PASSWORD = "Admin@123"
ADMIN_NAME = "Jeffrey Murungweni"

def create_admin():
    """Create or update admin user."""
    print(f"\n🔧 Setting up admin user: {ADMIN_EMAIL}")
    
    # Check if admin already exists
    existing = db.client.table("admin_users").select("*").eq("email", ADMIN_EMAIL).execute()
    
    if existing.data:
        print(f"✓ Admin user already exists")
        admin = existing.data[0]
        
        # Update password
        print(f"⚙️  Updating password...")
        password_hash = hash_password(ADMIN_PASSWORD)
        
        update_result = db.client.table("admin_users").update({
            "password_hash": password_hash,
            "last_password_change": get_cat_now().isoformat(),
            "failed_login_attempts": 0,
            "is_active": True,
        }).eq("id", admin["id"]).execute()
        
        if update_result.data:
            print(f"✅ Admin password updated successfully")
            print(f"\n📧 Email: {ADMIN_EMAIL}")
            print(f"🔑 Password: {ADMIN_PASSWORD}")
            print(f"👤 Name: {admin['full_name']}")
            print(f"🎭 Role: {admin['role']}")
        else:
            print(f"❌ Failed to update password")
    else:
        print(f"⚙️  Creating new admin user...")
        
        # Hash password
        password_hash = hash_password(ADMIN_PASSWORD)
        
        # Create admin user
        admin_data = {
            "id": str(uuid4()),
            "email": ADMIN_EMAIL,
            "password_hash": password_hash,
            "full_name": ADMIN_NAME,
            "role": "SYSTEM_ADMIN",
            "phone": None,
            "department": "IT",
            "position": "System Administrator",
            "is_active": True,
            "must_change_password": False,
            "failed_login_attempts": 0,
            "created_at": get_cat_now().isoformat(),
            "last_password_change": get_cat_now().isoformat(),
        }
        
        result = db.client.table("admin_users").insert(admin_data).execute()
        
        if result.data:
            admin = result.data[0]
            print(f"✅ Admin user created successfully!")
            print(f"\n📧 Email: {ADMIN_EMAIL}")
            print(f"🔑 Password: {ADMIN_PASSWORD}")
            print(f"👤 Name: {ADMIN_NAME}")
            print(f"🎭 Role: SYSTEM_ADMIN")
            print(f"🆔 ID: {admin['id']}")
        else:
            print(f"❌ Failed to create admin user")
            return False
    
    print(f"\n✅ Setup complete! You can now login at:")
    print(f"   https://procurement-frontend.fly.dev/admin/login")
    return True

if __name__ == "__main__":
    try:
        create_admin()
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)
