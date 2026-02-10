"""
Test script to verify expiry database functions exist and work
"""
import asyncio
from app.db.supabase import get_supabase_client

async def test_expiry_functions():
    """Test if expiry database functions are available"""
    client = get_supabase_client()
    
    print("Testing expiry database functions...")
    print("-" * 50)
    
    # Test 1: Check if get_expiring_documents function exists
    try:
        result = await client.rpc("get_expiring_documents", {"p_days_threshold": 90})
        print("✅ get_expiring_documents: SUCCESS")
        print(f"   Found {len(result.data) if result.data else 0} expiring documents")
    except Exception as e:
        print(f"❌ get_expiring_documents: FAILED")
        print(f"   Error: {str(e)}")
    
    # Test 2: Check if get_expired_documents function exists
    try:
        result = await client.rpc("get_expired_documents")
        print("✅ get_expired_documents: SUCCESS")
        print(f"   Found {len(result.data) if result.data else 0} expired documents")
    except Exception as e:
        print(f"❌ get_expired_documents: FAILED")
        print(f"   Error: {str(e)}")
    
    # Test 3: Check if get_expiry_alert_stats function exists
    try:
        result = await client.rpc("get_expiry_alert_stats")
        print("✅ get_expiry_alert_stats: SUCCESS")
        if result.data and len(result.data) > 0:
            stats = result.data[0]
            print(f"   Total alerts: {stats.get('total_alerts', 0)}")
            print(f"   Pending alerts: {stats.get('pending_alerts', 0)}")
            print(f"   Expired documents: {stats.get('expired_documents', 0)}")
    except Exception as e:
        print(f"❌ get_expiry_alert_stats: FAILED")
        print(f"   Error: {str(e)}")
    
    # Test 4: Check if get_pending_alerts function exists
    try:
        result = await client.rpc("get_pending_alerts")
        print("✅ get_pending_alerts: SUCCESS")
        print(f"   Found {len(result.data) if result.data else 0} pending alerts")
    except Exception as e:
        print(f"❌ get_pending_alerts: FAILED")
        print(f"   Error: {str(e)}")
    
    # Test 5: Check if document_expiry_alerts table exists
    try:
        result = await client.table("document_expiry_alerts").select("*").limit(1).execute()
        print("✅ document_expiry_alerts table: EXISTS")
    except Exception as e:
        print(f"❌ document_expiry_alerts table: NOT FOUND")
        print(f"   Error: {str(e)}")
    
    # Test 6: Check if documents table has expiry_date column
    try:
        result = await client.table("documents").select("id, expiry_date").limit(1).execute()
        print("✅ documents.expiry_date column: EXISTS")
    except Exception as e:
        print(f"❌ documents.expiry_date column: NOT FOUND")
        print(f"   Error: {str(e)}")
    
    print("-" * 50)
    print("\nIf any tests failed, run the migration:")
    print("psql -h <host> -U <user> -d <database> -f backend/app/db/migrations/010_document_expiry.sql")

if __name__ == "__main__":
    asyncio.run(test_expiry_functions())
