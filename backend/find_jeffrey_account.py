"""
Script to find and fix Jeffrey's supplier account
"""
import asyncio
from datetime import datetime
from app.db.supabase import Database

async def main():
    db = Database()
    
    # Search for Jeffrey's account
    print("Searching for Jeffrey's supplier account...")
    result = db._client.table("suppliers").select("*").ilike("contact_person_name", "%Jeffrey%Murungweni%").execute()
    
    if not result.data:
        print("No suppliers found with name Jeffrey Murungweni")
        # Try searching by company name or email pattern
        result = db._client.table("suppliers").select("*").order("created_at", desc=True).limit(10).execute()
        print(f"\nLast 10 suppliers created:")
        for s in result.data:
            print(f"  - {s.get('company_name', 'N/A')} | {s.get('contact_person_name', 'N/A')} | {s['email']} | Status: {s['status']}")
        return
    
    for supplier in result.data:
        print(f"\n{'='*80}")
        print(f"Found supplier:")
        print(f"  ID: {supplier['id']}")
        print(f"  Company: {supplier.get('company_name', 'N/A')}")
        print(f"  Contact: {supplier.get('contact_person_name', 'N/A')}")
        print(f"  Email: {supplier['email']}")
        print(f"  Status: {supplier['status']}")
        print(f"  Created: {supplier['created_at']}")
        print(f"  Submitted: {supplier.get('submitted_at', 'NOT SET')}")
        print(f"  Reviewed: {supplier.get('reviewed_at', 'NOT SET')}")
        
        # Check if there are documents
        docs_result = db._client.table("documents").select("*").eq("supplier_id", supplier['id']).execute()
        print(f"\n  Documents: {len(docs_result.data)} uploaded")
        for doc in docs_result.data[:5]:  # Show first 5
            print(f"    - {doc.get('document_type', 'Unknown')} | Status: {doc.get('verification_status', 'N/A')}")
        
        # Check status history
        history_result = db._client.table("supplier_status_history").select("*").eq("supplier_id", supplier['id']).order("created_at").execute()
        
        print(f"\n  Status History ({len(history_result.data)} entries):")
        for entry in history_result.data:
            print(f"    {entry['created_at']}: {entry.get('old_status', 'NULL')} -> {entry['new_status']}")
        
        # Check if status is INCOMPLETE and there are documents 
        if supplier['status'] == 'INCOMPLETE' and docs_result.data:
            print(f"\n  ⚠️  ISSUE DETECTED: Status is INCOMPLETE but {len(docs_result.data)} documents exist!")
            
            # Check if they have SUBMITTED in history
            submitted_entries = [e for e in history_result.data if e['new_status'] == 'SUBMITTED']
            
            if submitted_entries:
                print(f"  ✅ Found SUBMITTED in history at: {submitted_entries[0]['created_at']}")
                print(f"\n  Fixing status to SUBMITTED...")
                
                update_result = db._client.table("suppliers").update({
                    "status": "SUBMITTED",
                    "submitted_at": submitted_entries[0]['created_at'],
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", supplier['id']).execute()
                
                if update_result.data:
                    print(f"  ✅ SUCCESS! Status updated to SUBMITTED")
                    print(f"  ✅ submitted_at set to: {submitted_entries[0]['created_at']}")
                else:
                    print(f"  ❌ FAILED to update status")
            else:
                print(f"  ℹ️  No SUBMITTED found in history.")
                print(f"  This might be a case where submission failed partway through.")
                print(f"  \nWe can manually set it to SUBMITTED if documents are uploaded.")
                
                # If profile is complete and documents exist, set to SUBMITTED
                required_fields = ["company_name", "registration_number", "contact_person_name", "email", "phone", "business_category"]
                missing = [f for f in required_fields if not supplier.get(f)]
                
                if not missing and docs_result.data:
                    print(f"  ✓ Profile complete, documents exist. Safe to set SUBMITTED.")
                    print(f"\n  Fixing status to SUBMITTED...")
                    
                    update_result = db._client.table("suppliers").update({
                        "status": "SUBMITTED",
                        "submitted_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat()
                    }).eq("id", supplier['id']).execute()
                    
                    if update_result.data:
                        print(f"  ✅ SUCCESS! Status updated to SUBMITTED")
                    else:
                        print(f"  ❌ FAILED to update status")
                else:
                    print(f"  ✗ Missing required fields: {missing}")
        elif supplier['status'] != 'INCOMPLETE':
            print(f"\n  ✅ Status is {supplier['status']} - looks correct")
    
    print(f"\n{'='*80}\n")

if __name__ == "__main__":
    asyncio.run(main())
