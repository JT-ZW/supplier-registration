"""Test the expiry RPC function"""
import sys
import os
from uuid import UUID

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import Database

def test_expiry_rpc():
    """Test if get_supplier_expiring_documents RPC works"""
    db = Database()
    
    # Use a test supplier ID (you can change this to an actual ID from your database)
    test_supplier_id = "83702397-8c9c-42da-af83-eedf58b7b77b"  # From error logs
    
    try:
        print(f"Testing RPC with supplier_id: {test_supplier_id}")
        print("Calling: get_supplier_expiring_documents")
        print(f"Parameters: p_supplier_id={test_supplier_id}, p_days_threshold=90")
        
        result = db.client.rpc(
            "get_supplier_expiring_documents",
            {"p_supplier_id": test_supplier_id, "p_days_threshold": 90}
        ).execute()
        
        print("\n✓ Success!")
        print(f"Data returned: {result.data}")
        print(f"Number of records: {len(result.data) if result.data else 0}")
        
    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}")
        print(f"Message: {str(e)}")
        
        # Try to get more details
        if hasattr(e, 'message'):
            print(f"Error message: {e.message}")
        if hasattr(e, 'details'):
            print(f"Error details: {e.details}")
        if hasattr(e, 'hint'):
            print(f"Error hint: {e.hint}")
        if hasattr(e, 'code'):
            print(f"Error code: {e.code}")


if __name__ == "__main__":
    test_expiry_rpc()
