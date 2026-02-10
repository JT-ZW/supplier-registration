"""Test profile change approval directly to identify exact error."""
import sys
import os
import traceback

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import db

def test_approval():
    """Test the profile change approval flow."""
    
    request_id = "382e3324-7eeb-4042-828b-185c4a3e5191"
    
    print("=" * 70)
    print("STEP 1: Check Profile Change Request")
    print("=" * 70)
    
    try:
        request = db.client.table("profile_change_requests")\
            .select("*")\
            .eq("id", request_id)\
            .single()\
            .execute()
        
        print(f"✅ Request found: {request.data['id']}")
        print(f"   Status: {request.data['status']}")
        print(f"   Supplier ID: {request.data['supplier_id']}")
        print(f"   Requested changes: {request.data['requested_changes']}")
        
    except Exception as e:
        print(f"❌ ERROR fetching request: {str(e)}")
        return
    
    print("\n" + "=" * 70)
    print("STEP 2: Update Request Status to APPROVED")
    print("=" * 70)
    
    try:
        from datetime import datetime, timezone
        
        result = db.client.table("profile_change_requests")\
            .update({
                "status": "APPROVED",
                "reviewed_by": "bce9a402-994e-4526-a763-47815f2f601b",  # Jeffrey's admin ID
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "review_notes": "Test approval"
            })\
            .eq("id", request_id)\
            .execute()
        
        # Fetch updated record
        result = db.client.table("profile_change_requests")\
            .select("*")\
            .eq("id", request_id)\
            .single()\
            .execute()
        
        print(f"✅ Status updated to APPROVED")
        print(f"   Reviewed at: {result.data['reviewed_at']}")
        
    except Exception as e:
        print(f"❌ ERROR updating status: {str(e)}")
        traceback.print_exc()
        return
    
    print("\n" + "=" * 70)
    print("STEP 3: Apply Profile Changes (RPC)")
    print("=" * 70)
    
    try:
        result = db.client.rpc("apply_profile_changes", {
            "p_request_id": request_id
        }).execute()
        
        print(f"✅ Changes applied successfully!")
        print(f"   Result: {result.data}")
        
    except Exception as e:
        print(f"❌ ERROR applying changes:")
        print(f"   Type: {type(e).__name__}")
        print(f"   Message: {str(e)}")
        
        # Get more details
        if hasattr(e, '__dict__'):
            print(f"   Details: {e.__dict__}")
        
        traceback.print_exc()
        
        # Rollback
        print("\n⚠️  Rolling back status change...")
        db.client.table("profile_change_requests").update({
            "status": "PENDING",
            "reviewed_by": None,
            "reviewed_at": None,
            "review_notes": None
        }).eq("id", request_id).execute()
        print("   Status rolled back to PENDING")
        return
    
    print("\n" + "=" * 70)
    print("STEP 4: Verify Supplier Profile Updated")
    print("=" * 70)
    
    try:
        supplier = db.client.table("suppliers")\
            .select("*")\
            .eq("id", request.data['supplier_id'])\
            .single()\
            .execute()
        
        print(f"✅ Supplier profile:")
        print(f"   Company: {supplier.data['company_name']}")
        print(f"   Category: {supplier.data['business_category']}")
        print(f"   Email: {supplier.data['email']}")
        print(f"   Updated at: {supplier.data['updated_at']}")
        
    except Exception as e:
        print(f"❌ ERROR fetching supplier: {str(e)}")

if __name__ == "__main__":
    test_approval()
