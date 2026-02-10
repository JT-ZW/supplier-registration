"""Check the current apply_profile_changes function in database."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import db

# Query the function definition
result = db.client.rpc('exec_sql', {
    'sql': """
    SELECT pg_get_functiondef(oid) as definition
    FROM pg_proc 
    WHERE proname = 'apply_profile_changes';
    """
}).execute()

print("Current apply_profile_changes function in database:")
print("=" * 70)
if result.data:
    definition = result.data[0]['definition']
    print(definition)
    
    # Check if business_category is in the function
    if 'business_category' in definition:
        print("\n✅ Function HAS business_category field")
    else:
        print("\n❌ Function MISSING business_category field - NEEDS FIX!")
else:
    print("Could not retrieve function definition")
