"""
Script to check and fix supplier status issues
"""
import asyncio
from datetime import datetime
from app.db.supabase import Database

async def main():
    db = Database()
    
    # Get all suppliers
    print("Checking all suppliers...")
    result = db._client.table("suppliers").select("id, company_name, email, status, created_at, submitted_at, reviewed_at").execute()
    
    if not result.data:
        print("No suppliers found")
        return
    
    print(f"\nFound {len(result.data)} suppliers:\n")
    print(f"{'ID':<10} {'Company Name':<30} {'Status':<20} {'submitted_at':<25}")
    print("-" * 90)
    
    incomplete_with_docs = []
    
    for supplier in result.data:
        submitted_at_str = supplier.get('submitted_at') or 'N/A'
        print(f"{supplier['id']:<10} {supplier.get('company_name', 'N/A'):<30} {supplier['status']:<20} {submitted_at_str:<25}")
        
        # Check if INCOMPLETE but has documents
        if supplier['status'] == 'INCOMPLETE':
            docs_result = db._client.table("documents").select("id").eq("supplier_id", supplier['id']).execute()
            if docs_result.data and len(docs_result.data) > 0:
                incomplete_with_docs.append(supplier)
    
    # Check for suppliers that should have been submitted
    if incomplete_with_docs:
        print(f"\n⚠️  Found {len(incomplete_with_docs)} suppliers with INCOMPLETE status but have uploaded documents:")
        
        for supplier in incomplete_with_docs:
            print(f"\n  - {supplier.get('company_name', 'N/A')} ({supplier['email']})")
            print(f"    ID: {supplier['id']}")
            
            # Check status history
            history_result = db._client.table("supplier_status_history").select("*").eq("supplier_id", supplier['id']).order("created_at").execute()
            
            if history_result.data:
                print(f"    Status history:")
                for entry in history_result.data:
                    print(f"      {entry['created_at']}: {entry.get('old_status', 'N/A')} -> {entry['new_status']}")
                
                # Check if they ever were SUBMITTED
                submitted_entries = [e for e in history_result.data if e['new_status'] == 'SUBMITTED']
                if submitted_entries:
                    print(f"\n    ✅ This supplier WAS submitted at {submitted_entries[0]['created_at']}")
                    print(f"    Fixing status to SUBMITTED...")
                    
                    # Fix the status
                    update_result = db._client.table("suppliers").update({
                        "status": "SUBMITTED",
                        "submitted_at": submitted_entries[0]['created_at'],
                        "updated_at": datetime.utcnow().isoformat()
                    }).eq("id", supplier['id']).execute()
                    
                    if update_result.data:
                        print(f"    ✅ Fixed! Status updated to SUBMITTED")
                    else:
                        print(f"    ❌ Failed to update status")
    
    print("\n" + "="*90)
    print("\nChecking for inconsistencies...")
    
    # Check for suppliers with SUBMITTED/UNDER_REVIEW but no submitted_at
    result2 = db._client.table("suppliers").select("*").in_("status", ["SUBMITTED", "UNDER_REVIEW", "APPROVED", "REJECTED"]).is_("submitted_at", "null").execute()
    
    if result2.data:
        print(f"\n⚠️  Found {len(result2.data)} suppliers with submitted status but missing submitted_at:")
        for supplier in result2.data:
            print(f"  - {supplier.get('company_name', 'N/A')} ({supplier['status']})")
            
            # Try to get from status history
            history_result = db._client.table("supplier_status_history").select("created_at").eq("supplier_id", supplier['id']).eq("new_status", "SUBMITTED").order("created_at").limit(1).execute()
            
            if history_result.data:
                submitted_at = history_result.data[0]['created_at']
                print(f"    Fixing with date from status history: {submitted_at}")
                
                update_result = db._client.table("suppliers").update({
                    "submitted_at": submitted_at,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", supplier['id']).execute()
                
                if update_result.data:
                    print(f"    ✅ Fixed!")
            else:
                # Use created_at as fallback
                fallback_date = supplier.get('reviewed_at') or supplier['created_at']
                print(f"    Using fallback date: {fallback_date}")
                
                update_result = db._client.table("suppliers").update({
                    "submitted_at": fallback_date,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", supplier['id']).execute()
                
                if update_result.data:
                    print(f"    ✅ Fixed with fallback date!")
    else:
        print("✅ All submitted suppliers have submitted_at dates")
    
    print("\n✅ Check complete!")

if __name__ == "__main__":
    asyncio.run(main())
