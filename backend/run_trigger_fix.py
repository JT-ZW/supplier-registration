#!/usr/bin/env python3
"""Run trigger fix migration."""

import os
from dotenv import load_dotenv
from postgrest import SyncPostgrestClient

# Load environment variables
load_dotenv()

# Initialize PostgREST client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

# Read the migration SQL
with open("app/db/migrations/012_fix_trigger_field_mismatches.sql", "r") as f:
    migration_sql = f.read()

# Execute via psycopg2 for raw SQL
import psycopg2

# Parse connection from Supabase URL
# Format: https://project.supabase.co
project_ref = supabase_url.replace("https://", "").split(".")[0]

# Use Supabase PostgreSQL connection
# Note: We'll need the direct database URL
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("ERROR: DATABASE_URL not found in environment")
    print("Please add your Supabase database URL to .env file")
    print("Format: postgresql://postgres:[password]@db.[project].supabase.co:5432/postgres")
    exit(1)

print("Connecting to database...")
try:
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    print("Executing migration...")
    cursor.execute(migration_sql)
    conn.commit()
    
    print("✓ Migration completed successfully!")
    print("  - Fixed track_supplier_status_change() trigger")
    print("  - Fixed track_document_status_change() trigger")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"✗ Migration failed: {e}")
    if 'conn' in locals():
        conn.rollback()
        conn.close()
