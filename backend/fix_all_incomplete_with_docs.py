"""
Script to fix ALL suppliers with INCOMPLETE status but have complete profiles and documents.
This ensures data consistency across the system.
"""
import asyncio
from datetime import datetime, timezone
from app.db.supabase import Database

async def main():
    db = Database()
    
    print("=" * 90)
    print("FIXING ALL INCOMPLETE SUPPLIERS WITH COMPLETE PROFILES AND DOCUMENTS")
    print("=" * 90)
    
    # Get all INCOMPLETE suppliers
    result = db._client.table("suppliers").select("*").eq("status", "INCOMPLETE").execute()
    
    if not result.data:
        print("\n✅ No INCOMPLETE suppliers found. All good!")
        return
    
    print(f"\nFound {len(result.data)} INCOMPLETE suppliers. Checking which ones should be SUBMITTED...")
    
    fixed_count = 0
    needs_attention = []
    
    for supplier in result.data:
        print(f"\n{'─' * 90}")
        print(f"Checking: {supplier.get('company_name', 'N/A')} ({supplier['email']})")
        
        # Check if profile is complete
        required_fields = ["company_name", "registration_number", "contact_person_name", "email", "phone", "business_category"]
        missing_fields = [f for f in required_fields if not supplier.get(f)]
        
        # Check if documents are uploaded
        docs_result = db._client.table("documents").select("*").eq("supplier_id", supplier['id']).execute()
        has_docs = docs_result.data and len(docs_result.data) > 0
        
        print(f"  Profile complete: {not missing_fields}")
        print(f"  Documents uploaded: {len(docs_result.data) if docs_result.data else 0}")
        
        if missing_fields:
            print(f"  ⏭️  SKIP: Missing fields: {', '.join(missing_fields)}")
            needs_attention.append({
                "supplier": supplier,
                "reason": f"Missing fields: {', '.join(missing_fields)}"
            })
            continue
        
        if not has_docs:
            print(f"  ⏭️  SKIP: No documents uploaded")
            needs_attention.append({
                "supplier": supplier,
                "reason": "No documents uploaded"
            })
            continue
        
        # This supplier should be SUBMITTED!
        print(f"  ✅ Profile complete and documents uploaded. Fixing status...")
        
        # Check if there's a submission in status history
        history_result = db._client.table("supplier_status_history").select("*").eq("supplier_id", supplier['id']).eq("new_status", "SUBMITTED").order("created_at").execute()
        
        if history_result.data:
            # Use the historical submission date
            submitted_at = history_result.data[0]['created_at']
            print(f"  📅 Using historical submission date: {submitted_at}")
        else:
            # Use current timestamp
            submitted_at = datetime.now(timezone.utc).isoformat()
            print(f"  📅 Using current timestamp: {submitted_at}")
        
        # Update the supplier
        update_result = db._client.table("suppliers").update({
            "status": "SUBMITTED",
            "submitted_at": submitted_at,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", supplier['id']).execute()
        
        if update_result.data:
            print(f"  ✅ SUCCESS! Updated to SUBMITTED")
            fixed_count += 1
            
            # Log status change to history
            try:
                db._client.table("supplier_status_history").insert({
                    "supplier_id": supplier['id'],
                    "old_status": "INCOMPLETE",
                    "new_status": "SUBMITTED",
                    "changed_by": "system_auto_fix",
                    "reason": "Auto-fixed: Complete profile with uploaded documents"
                }).execute()
                print(f"  📝 Status history logged")
            except Exception as e:
                print(f"  ⚠️  Failed to log history: {str(e)}")
        else:
            print(f"  ❌ FAILED to update supplier")
    
    print(f"\n{'=' * 90}")
    print(f"\nSUMMARY:")
    print(f"  ✅ Fixed: {fixed_count} suppliers")
    print(f"  ⏭️  Skipped: {len(needs_attention)} suppliers (legitimately incomplete)")
    
    if needs_attention:
        print(f"\n  Suppliers that need attention (legitimately incomplete):")
        for item in needs_attention:
            s = item['supplier']
            print(f"    - {s.get('company_name', 'N/A')} ({s['email']}): {item['reason']}")
    
    print(f"\n{'=' * 90}")
    print("✅ DONE! All inconsistencies have been resolved.")
    print("=" * 90)

if __name__ == "__main__":
    asyncio.run(main())
