"""
Quick script to apply the document expiry type fix migration.
Run this from the backend directory: python apply_expiry_fix.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.supabase import get_db

def apply_migration():
    """Apply the expiry type fix migration."""
    print("🔧 Applying document expiry type fix migration...")
    
    # Read the migration file
    migration_file = Path(__file__).parent / "app" / "db" / "migrations" / "011_fix_expiry_type_mismatch.sql"
    
    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Split into individual statements
    statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--')]
    
    db = get_db()
    
    print(f"📝 Found {len(statements)} SQL statements to execute...")
    
    # Execute each statement
    for i, statement in enumerate(statements, 1):
        if not statement or statement.startswith('--'):
            continue
            
        try:
            # For CREATE OR REPLACE FUNCTION, we need to execute as a single block
            if 'CREATE OR REPLACE FUNCTION' in statement:
                # Find the function name
                func_name = statement.split('(')[0].split()[-1]
                print(f"  [{i}/{len(statements)}] Updating function: {func_name}...")
            else:
                print(f"  [{i}/{len(statements)}] Executing statement...")
            
            # Execute via Supabase (note: Supabase might not support direct SQL execution)
            # We'll need to use the SQL editor in Supabase dashboard
            print(f"    ⚠️  Please run this SQL manually in Supabase SQL Editor")
            
        except Exception as e:
            print(f"    ❌ Error: {str(e)}")
            return False
    
    print("\n✅ Migration instructions prepared!")
    print("\n" + "="*60)
    print("MANUAL STEP REQUIRED:")
    print("="*60)
    print("\n1. Go to: https://supabase.com/dashboard")
    print("2. Select your project")
    print("3. Navigate to: SQL Editor")
    print(f"4. Copy the contents of: {migration_file}")
    print("5. Paste into SQL Editor and click 'Run'")
    print("\n" + "="*60)
    
    return True

if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1)
