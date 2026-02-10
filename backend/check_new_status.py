"""Check if there are any suppliers with 'NEW' status in the database"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import Database

def check_new_status():
    """Check for suppliers with NEW status"""
    db = Database()
    
    supplier_id = "83702397-8c9c-42da-af83-eedf58b7b77b"
    
    print("\n=== Checking Supplier Status ===")
    
    try:
        # Check specific supplier
        result = db.client.table("suppliers").select(
            "id, company_name, status"
        ).eq("id", supplier_id).execute()
        
        if result.data and len(result.data) > 0:
            supplier = result.data[0]
            print(f"\nSupplier: {supplier['company_name']}")
            print(f"Current Status: '{supplier['status']}'")
            print(f"Status Type: {type(supplier['status'])}")
            
            if supplier['status'] == 'NEW':
                print("\n⚠️  WARNING: Supplier has 'NEW' status!")
                print("This status doesn't exist in the enum and will cause errors.")
            else:
                print("\n✓ Status looks OK")
        
        # Check if ANY suppliers have NEW status
        print("\n=== Checking All Suppliers for 'NEW' Status ===")
        all_result = db.client.table("suppliers").select("id, company_name, status").execute()
        
        new_status_suppliers = [s for s in all_result.data if s['status'] == 'NEW']
        
        if new_status_suppliers:
            print(f"\n⚠️  Found {len(new_status_suppliers)} supplier(s) with 'NEW' status:")
            for s in new_status_suppliers:
                print(f"  - {s['company_name']} (ID: {s['id']})")
        else:
            print("\n✓ No suppliers found with 'NEW' status")
            
        # Show all unique status values
        print("\n=== All Unique Status Values in Database ===")
        unique_statuses = set(s['status'] for s in all_result.data)
        for status in sorted(unique_statuses):
            print(f"  - '{status}'")
            
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_new_status()
