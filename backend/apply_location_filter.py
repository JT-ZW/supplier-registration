"""
Apply location stats migration to filter for approved suppliers only
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def apply_migration():
    """Apply the location stats filter migration."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ SUPABASE_URL or SUPABASE_SERVICE_KEY not found in environment")
        return False
    
    # Create Supabase client
    supabase = create_client(supabase_url, supabase_key)
    
    # Read migration file
    migration_path = Path(__file__).parent / "app" / "db" / "migrations" / "018_filter_location_stats_approved_only.sql"
    
    if not migration_path.exists():
        print(f"❌ Migration file not found: {migration_path}")
        return False
    
    print(f"📖 Reading migration file: {migration_path}")
    with open(migration_path, 'r') as f:
        sql = f.read()
    
    # Remove comments and split by statement delimiter
    statements = []
    current_statement = []
    
    for line in sql.split('\n'):
        # Skip comment lines
        if line.strip().startswith('--') or line.strip().startswith('/*') or line.strip().startswith('*/'):
            continue
        
        current_statement.append(line)
        
        # If line ends with semicolon, it's a complete statement
        if line.strip().endswith(';'):
            stmt = '\n'.join(current_statement)
            if stmt.strip():
                statements.append(stmt.strip())
            current_statement = []
    
    print(f"🔧 Found {len(statements)} SQL statements to execute")
    
    # Execute each statement
    try:
        for i, statement in enumerate(statements, 1):
            if statement.strip():
                print(f"   Executing statement {i}/{len(statements)}...")
                # Execute using RPC call
                result = supabase.rpc('exec_sql', {'sql': statement}).execute()
                
        print("✅ Migration applied successfully!")
        print("📊 Location stats now show APPROVED suppliers only")
        return True
        
    except Exception as e:
        print(f"❌ Error applying migration: {e}")
        print("\n📝 Manual execution required:")
        print(f"   1. Go to Supabase SQL Editor: {supabase_url.replace('https://', 'https://supabase.com/dashboard/project/').replace('.supabase.co', '/sql')}")
        print(f"   2. Copy and paste SQL from: {migration_path}")
        print(f"   3. Click 'Run'")
        return False

if __name__ == "__main__":
    print("🚀 Applying location stats filter migration...")
    print("=" * 60)
    success = apply_migration()
    sys.exit(0 if success else 1)
