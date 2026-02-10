"""Quick test to verify if the issue is code or database."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import db

print("Testing Database Functions...")
print("=" * 70)

# Test 1: Check if apply_profile_changes function exists and has business_category
try:
    print("\n1. Testing apply_profile_changes function...")
    
    # Try to get a pending request
    requests = db.client.table("profile_change_requests")\
        .select("*")\
        .eq("status", "PENDING")\
        .limit(1)\
        .execute()
    
    if requests.data:
        request_id = requests.data[0]["id"]
        print(f"   Found pending request: {request_id}")
        print(f"   Changes requested: {requests.data[0]['requested_changes']}")
        
        # Try to call the function (it will fail if request is not approved, but we can see the error)
        try:
            result = db.client.rpc("apply_profile_changes", {
                "p_request_id": request_id
            }).execute()
            print(f"   ✅ Function executed: {result.data}")
        except Exception as e:
            error_msg = str(e)
            if "Can only apply approved changes" in error_msg:
                print(f"   ✅ Function exists and checks status correctly")
            else:
                print(f"   ❌ Function error: {error_msg}")
    else:
        print("   ⚠️  No pending requests to test with")
        
except Exception as e:
    print(f"   ❌ Error: {str(e)}")

# Test 2: Test insert operation
try:
    print("\n2. Testing insert with immediate select...")
    
    # Get a test supplier
    supplier = db.client.table("suppliers")\
        .select("id")\
        .limit(1)\
        .execute()
    
    if supplier.data:
        supplier_id = supplier.data[0]["id"]
        
        # Try insert
        result = db.client.table("profile_change_requests").insert({
            "supplier_id": supplier_id,
            "requested_changes": {"test": "value"},
            "current_values": {"test": "old"},
            "status": "PENDING"
        }).execute()
        
        if result.data and len(result.data) > 0:
            inserted_id = result.data[0]["id"]
            print(f"   ✅ Insert returned data with ID: {inserted_id}")
            
            # Clean up
            db.client.table("profile_change_requests")\
                .delete()\
                .eq("id", inserted_id)\
                .execute()
            print(f"   ✅ Cleanup successful")
        else:
            print(f"   ❌ Insert did not return data: {result.data}")
            
except Exception as e:
    print(f"   ❌ Error: {str(e)}")

# Test 3: Test update operation
try:
    print("\n3. Testing update with separate select...")
    
    # Get a test supplier
    supplier = db.client.table("suppliers")\
        .select("id, phone")\
        .limit(1)\
        .execute()
    
    if supplier.data:
        supplier_id = supplier.data[0]["id"]
        old_phone = supplier.data[0].get("phone")
        
        # Try update
        db.client.table("suppliers")\
            .update({"phone": old_phone})\
            .eq("id", supplier_id)\
            .execute()
        
        # Then select
        result = db.client.table("suppliers")\
            .select("*")\
            .eq("id", supplier_id)\
            .single()\
            .execute()
        
        if result.data:
            print(f"   ✅ Update + Select pattern works")
        else:
            print(f"   ❌ Select after update failed")
            
except Exception as e:
    print(f"   ❌ Error: {str(e)}")

print("\n" + "=" * 70)
print("Test Complete")
