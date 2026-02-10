"""Test to identify the exact error when reviewing profile changes."""
import sys
import os
from pprint import pprint

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import db

def test_review():
    """Test the apply_profile_changes RPC function."""
    request_id = "382e3324-7eeb-4042-828b-185c4a3e5191"
    
    try:
        # First, check the request details
        print("=" * 60)
        print("CHECKING PROFILE CHANGE REQUEST")
        print("=" * 60)
        
        request = db.client.table("profile_change_requests")\
            .select("*")\
            .eq("id", request_id)\
            .single()\
            .execute()
        
        print("\nRequest found:")
        print(f"  ID: {request.data['id']}")
        print(f"  Supplier ID: {request.data['supplier_id']}")
        print(f"  Status: {request.data['status']}")
        print(f"  Requested Changes:")
        pprint(request.data['requested_changes'], indent=4)
        
        # Now try to apply the changes
        print("\n" + "=" * 60)
        print("TESTING APPLY_PROFILE_CHANGES RPC")
        print("=" * 60)
        
        result = db.client.rpc("apply_profile_changes", {
            "p_request_id": request_id
        }).execute()
        
        print("\n✅ SUCCESS!")
        print(f"Result: {result.data}")
        
    except Exception as e:
        print("\n❌ ERROR!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        
        # Try to get more details
        if hasattr(e, 'message'):
            print(f"Detailed message: {e.message}")
        if hasattr(e, 'details'):
            print(f"Details: {e.details}")
        if hasattr(e, 'hint'):
            print(f"Hint: {e.hint}")

if __name__ == "__main__":
    test_review()
