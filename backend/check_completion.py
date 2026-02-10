"""Check supplier completion details"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import Database

def check_completion():
    """Check what's actually complete"""
    db = Database()
    
    supplier_id = "83702397-8c9c-42da-af83-eedf58b7b77b"
    
    try:
        # Get supplier
        result = db.client.table("suppliers").select("*").eq("id", supplier_id).execute()
        
        if result.data and len(result.data) > 0:
            supplier = result.data[0]
            
            print("\n=== Profile Completeness ===")
            required_fields = {
                "company_name": supplier.get("company_name"),
                "registration_number": supplier.get("registration_number"),
                "contact_person_name": supplier.get("contact_person_name"),
                "email": supplier.get("email"),
                "phone_number": supplier.get("phone"),  # Note: field name
                "business_category": supplier.get("business_category"),
                "physical_address": supplier.get("street_address"),  # Note: field name
            }
            
            for field, value in required_fields.items():
                status = "✓" if value and str(value).strip() else "✗"
                print(f"{status} {field}: {value if value else 'MISSING'}")
            
            filled = sum(1 for v in required_fields.values() if v and str(v).strip())
            print(f"\nProfile: {filled}/{len(required_fields)} fields complete ({filled/len(required_fields)*100:.0f}%)")
            
            # Get documents
            docs_result = db.client.table("documents").select(
                "id, document_type, s3_key, verification_status"
            ).eq("supplier_id", supplier_id).execute()
            
            print("\n=== Documents ===")
            if docs_result.data:
                uploaded = sum(1 for d in docs_result.data if d.get("s3_key"))
                verified = sum(1 for d in docs_result.data if d.get("verification_status") == "VERIFIED")
                
                print(f"Total: {len(docs_result.data)}")
                print(f"Uploaded: {uploaded}/{len(docs_result.data)}")
                print(f"Verified: {verified}/{len(docs_result.data)}")
                
                for doc in docs_result.data:
                    has_file = "✓" if doc.get("s3_key") else "✗"
                    ver_status = doc.get("verification_status", "PENDING")
                    print(f"  {has_file} {doc['document_type']}: {ver_status}")
            else:
                print("No documents found")
            
            print("\n=== Ready to Submit? ===")
            if filled == len(required_fields) and docs_result.data and all(d.get("s3_key") for d in docs_result.data):
                print("✓ YES - All requirements met!")
            else:
                print("✗ NO - Missing:")
                if filled < len(required_fields):
                    print(f"  - Complete profile ({filled}/{len(required_fields)})")
                if not docs_result.data:
                    print("  - Upload documents")
                elif not all(d.get("s3_key") for d in docs_result.data):
                    missing = sum(1 for d in docs_result.data if not d.get("s3_key"))
                    print(f"  - Upload {missing} documents")
            
            print("=" * 50)
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_completion()
