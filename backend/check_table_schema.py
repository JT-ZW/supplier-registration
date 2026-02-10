#!/usr/bin/env python3
"""Check actual database schema for suppliers and documents tables."""

import os
from dotenv import load_dotenv
from postgrest import SyncPostgrestClient

# Load environment variables
load_dotenv()

# Initialize PostgREST client directly
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
rest_url = f"{supabase_url}/rest/v1"

def check_table_columns(table_name):
    """Query PostgreSQL information schema to get column names."""
    print(f"\n{'='*60}")
    print(f"Columns in {table_name} table:")
    print(f"{'='*60}")
    
    # Get a sample record to see what columns exist
    try:
        client = SyncPostgrestClient(rest_url, headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}"
        })
        result = client.from_(table_name).select("*").limit(1).execute()
        if result.data:
            columns = list(result.data[0].keys())
            for i, col in enumerate(sorted(columns), 1):
                print(f"{i:2}. {col}")
        else:
            print(f"No data in {table_name} table to inspect")
    except Exception as e:
        print(f"Error querying {table_name}: {e}")

if __name__ == "__main__":
    check_table_columns("suppliers")
    check_table_columns("documents")
    print(f"\n{'='*60}\n")
