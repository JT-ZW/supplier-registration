"""Apply migration to fix apply_profile_changes function."""
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import db

def apply_migration():
    """Apply the migration to fix apply_profile_changes function."""
    
    migration_file = Path(__file__).parent / "app" / "db" / "migrations" / "013_fix_apply_profile_changes.sql"
    
    print("=" * 70)
    print("APPLYING MIGRATION: Fix apply_profile_changes Function")
    print("=" * 70)
    print(f"\nReading migration from: {migration_file}")
    
    try:
        # Read migration SQL
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        print("\n📝 Migration SQL loaded successfully")
        print(f"   Length: {len(sql)} characters")
        
        # Apply migration
        print("\n🔄 Applying migration to database...")
        
        result = db.client.rpc('exec_sql', {'sql': sql}).execute()
        
        print("✅ Migration applied successfully!")
        print("\n" + "=" * 70)
        print("WHAT WAS FIXED:")
        print("=" * 70)
        print("✅ Added missing 'business_category' field to apply_profile_changes()")
        print("✅ business_category is now properly updated when profile changes are approved")
        print("\nThis fixes the 500 error when approving profile changes that include")
        print("business category updates.")
        print("\n" + "=" * 70)
        
    except Exception as e:
        print(f"\n❌ ERROR applying migration!")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)}")
        
        # Try direct SQL execution instead
        print("\n🔄 Trying direct SQL execution...")
        try:
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql = f.read()
            
            # Execute directly through postgrest
            result = db.client.postgrest.session.post(
                f"{db.client.postgrest.base_url}/rpc/exec_sql",
                json={"sql": sql}
            )
            
            if result.status_code == 200:
                print("✅ Migration applied successfully via direct execution!")
            else:
                print(f"❌ Failed: {result.status_code} - {result.text}")
                
        except Exception as e2:
            print(f"❌ Direct execution also failed: {str(e2)}")
            print("\n📋 MANUAL STEPS REQUIRED:")
            print("=" * 70)
            print("Please run this SQL in your Supabase SQL Editor:")
            print("\n" + sql)
            print("\n" + "=" * 70)

if __name__ == "__main__":
    apply_migration()
