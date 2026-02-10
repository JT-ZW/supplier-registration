"""Check supplier status in database"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import Database

def check_status():
    """Check the actual status in the database"""
    db = Database()
    
    supplier_id = "83702397-8c9c-42da-af83-eedf58b7b77b"
    
    try:
        result = db.client.table("suppliers").select(
            "id, company_name, status, submitted_at, reviewed_at, created_at, updated_at"
        ).eq("id", supplier_id).execute()
        
        if result.data and len(result.data) > 0:
            supplier = result.data[0]
            print("\n=== Supplier Status ===")
            print(f"Company: {supplier['company_name']}")
            print(f"ID: {supplier['id']}")
            print(f"Status: {supplier['status']}")
            print(f"Submitted At: {supplier.get('submitted_at', 'NULL')}")
            print(f"Reviewed At: {supplier.get('reviewed_at', 'NULL')}")
            print(f"Created At: {supplier['created_at']}")
            print(f"Updated At: {supplier['updated_at']}")
            print("=" * 40)
        else:
            print(f"No supplier found with ID: {supplier_id}")
            
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    check_status()
