"""
Fix submitted_at dates for suppliers using status history.

This script updates the submitted_at field for all suppliers by:
1. Using the actual submission timestamp from supplier_status_history table
2. Falling back to reviewed_at or created_at for suppliers without history

Run this script from the backend directory:
    python fix_submitted_at_dates.py
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

def get_supabase_client() -> Client:
    """Initialize Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment")
    
    return create_client(url, key)


def fix_submitted_at_dates():
    """Fix submitted_at dates for all suppliers."""
    print("🔧 Fixing submitted_at dates for suppliers...")
    print("=" * 60)
    
    client = get_supabase_client()
    
    # First, check current state
    print("\n📊 Current state - checking suppliers without submitted_at:")
    
    # Get all non-incomplete suppliers
    result = client.from_("suppliers").select(
        "id, company_name, status, created_at, submitted_at, reviewed_at"
    ).neq("status", "INCOMPLETE").execute()
    
    suppliers = result.data
    missing_count = sum(1 for s in suppliers if not s.get('submitted_at'))
    
    print(f"  Total non-INCOMPLETE suppliers: {len(suppliers)}")
    print(f"  Missing submitted_at: {missing_count}")
    
    if missing_count == 0:
        print("\n✅ All suppliers already have submitted_at dates!")
        return
    
    # Show which ones are missing
    print("\n📋 Suppliers missing submitted_at:")
    for supplier in suppliers:
        if not supplier.get('submitted_at'):
            print(f"  - {supplier['company_name']} ({supplier['status']})")
    
    # Fix each supplier
    print("\n🔄 Fixing submitted_at dates...")
    fixed_count = 0
    
    for supplier in suppliers:
        if not supplier.get('submitted_at'):
            supplier_id = supplier['id']
            status = supplier['status']
            
            # Try to get submission date from status history
            history = client.from_("supplier_status_history").select(
                "created_at"
            ).eq(
                "supplier_id", supplier_id
            ).eq(
                "new_status", "SUBMITTED"
            ).order(
                "created_at", desc=False
            ).limit(1).execute()
            
            # Determine submitted_at
            if history.data and len(history.data) > 0:
                # Use actual submission time from history
                submitted_at = history.data[0]['created_at']
                source = "status history"
            elif supplier.get('reviewed_at'):
                # Use reviewed_at for approved/rejected
                submitted_at = supplier['reviewed_at']
                source = "reviewed_at"
            else:
                # Fallback to created_at
                submitted_at = supplier['created_at']
                source = "created_at (fallback)"
            
            # Update the supplier
            try:
                client.from_("suppliers").update({
                    "submitted_at": submitted_at
                }).eq("id", supplier_id).execute()
                
                print(f"  ✓ {supplier['company_name']}: {submitted_at[:10]} (from {source})")
                fixed_count += 1
            except Exception as e:
                print(f"  ✗ {supplier['company_name']}: Error - {str(e)}")
    
    print(f"\n✅ Fixed {fixed_count} suppliers!")
    
    # Show final state
    print("\n📊 Final verification:")
    result = client.from_("suppliers").select(
        "id, company_name, status, submitted_at"
    ).neq("status", "INCOMPLETE").execute()
    
    suppliers = result.data
    missing_count = sum(1 for s in suppliers if not s.get('submitted_at'))
    
    print(f"  Total non-INCOMPLETE suppliers: {len(suppliers)}")
    print(f"  Missing submitted_at: {missing_count}")
    
    if missing_count == 0:
        print("\n✅ All suppliers now have submitted_at dates!")
    
    print("=" * 60)


if __name__ == "__main__":
    fix_submitted_at_dates()
