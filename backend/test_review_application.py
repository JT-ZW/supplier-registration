"""Test the review application endpoint"""
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import Database
from app.models.enums import SupplierStatus
from datetime import datetime

def test_review():
    """Test reviewing an application"""
    db = Database()
    
    supplier_id = "83702397-8c9c-42da-af83-eedf58b7b77b"
    admin_id = "some-admin-id"  # Replace with actual admin ID if needed
    
    # Test data - exactly what would be sent from review_application endpoint
    update_data = {
        "status": SupplierStatus.APPROVED.value,  # Should be "APPROVED"
        "reviewed_at": datetime.utcnow().isoformat(),
        "reviewed_by": admin_id,
        "updated_at": datetime.utcnow().isoformat(),
        "admin_notes": "Test approval notes",
    }
    
    print("\n=== Testing Review Application ===")
    print(f"Supplier ID: {supplier_id}")
    print(f"Update Data: {json.dumps(update_data, indent=2)}")
    print(f"Status Value: '{update_data['status']}' (type: {type(update_data['status'])})")
    
    try:
        # First check current status
        current = db.client.table("suppliers").select("status, company_name").eq("id", supplier_id).execute()
        if current.data:
            print(f"\nCurrent Status: {current.data[0]['status']}")
            print(f"Company: {current.data[0]['company_name']}")
        
        # Try the update
        print("\nAttempting update...")
        result = db.client.table("suppliers").update(update_data).eq("id", supplier_id).execute()
        
        if result.data:
            print(f"\n✓ SUCCESS!")
            print(f"New Status: {result.data[0]['status']}")
            print(f"Reviewed At: {result.data[0].get('reviewed_at')}")
        else:
            print("\n✗ FAILED: No data returned")
            
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        print(f"Error Type: {type(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_review()
