"""
Test script for Audit Trail System
Run this after applying the database migration to verify everything works.
"""
import asyncio
import sys
from datetime import datetime, timedelta

# Add parent directory to path to import app modules
sys.path.append('..')

from app.db.supabase import db
from app.models.audit import AuditAction, AuditResourceType


async def test_create_audit_log():
    """Test creating an audit log entry."""
    print("Testing: Create audit log...")
    
    try:
        audit_data = {
            "user_id": None,  # System action
            "user_type": "system",
            "action": AuditAction.SYSTEM_STARTUP.value,
            "resource_type": AuditResourceType.SYSTEM.value,
            "resource_id": None,
            "changes": None,
            "metadata": {
                "test": "audit_trail_test",
                "timestamp": datetime.utcnow().isoformat()
            },
            "ip_address": "127.0.0.1",
            "user_agent": "Test Script"
        }
        
        result = await db.create_audit_log(audit_data)
        
        if result:
            print("✅ Create audit log: SUCCESS")
            print(f"   Created audit log with ID: {result['id']}")
            return result['id']
        else:
            print("❌ Create audit log: FAILED - No result returned")
            return None
            
    except Exception as e:
        print(f"❌ Create audit log: FAILED - {str(e)}")
        return None


async def test_get_audit_logs():
    """Test retrieving audit logs with filters."""
    print("\nTesting: Get audit logs...")
    
    try:
        # Test 1: Get all recent logs
        result = await db.get_audit_logs(limit=10)
        print(f"✅ Get audit logs: SUCCESS - Retrieved {len(result['items'])} logs")
        
        # Test 2: Filter by user type
        result = await db.get_audit_logs(user_type="system", limit=5)
        print(f"✅ Filter by user_type: SUCCESS - Retrieved {len(result['items'])} system logs")
        
        # Test 3: Filter by action
        result = await db.get_audit_logs(action=AuditAction.SYSTEM_STARTUP.value, limit=5)
        print(f"✅ Filter by action: SUCCESS - Retrieved {len(result['items'])} SYSTEM_STARTUP logs")
        
        return True
        
    except Exception as e:
        print(f"❌ Get audit logs: FAILED - {str(e)}")
        return False


async def test_get_recent_activity():
    """Test getting recent activity."""
    print("\nTesting: Get recent activity...")
    
    try:
        # Get last 7 days of activity
        result = await db.get_recent_activity(days=7, limit=20)
        print(f"✅ Get recent activity: SUCCESS - Retrieved {len(result)} activities")
        
        return True
        
    except Exception as e:
        print(f"❌ Get recent activity: FAILED - {str(e)}")
        return False


async def test_get_audit_statistics():
    """Test getting audit statistics."""
    print("\nTesting: Get audit statistics...")
    
    try:
        # Get stats for last 30 days
        start_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        end_date = datetime.utcnow().isoformat()
        
        result = await db.get_audit_statistics(
            start_date=start_date,
            end_date=end_date
        )
        
        if isinstance(result, list) and len(result) > 0:
            result = result[0]
        
        total = result.get("total_actions", 0) if isinstance(result, dict) else 0
        print(f"✅ Get audit statistics: SUCCESS - Total actions: {total}")
        
        return True
        
    except Exception as e:
        print(f"❌ Get audit statistics: FAILED - {str(e)}")
        return False


async def test_get_resource_audit_trail():
    """Test getting audit trail for a specific resource."""
    print("\nTesting: Get resource audit trail...")
    
    try:
        # Try to get audit trail for SYSTEM resource
        result = await db.get_resource_audit_trail(
            resource_type=AuditResourceType.SYSTEM.value,
            resource_id=None,
            limit=10
        )
        print(f"✅ Get resource audit trail: SUCCESS - Retrieved {len(result)} entries")
        
        return True
        
    except Exception as e:
        print(f"❌ Get resource audit trail: FAILED - {str(e)}")
        return False


async def run_all_tests():
    """Run all audit trail tests."""
    print("=" * 60)
    print("AUDIT TRAIL SYSTEM - TEST SUITE")
    print("=" * 60)
    print()
    
    # Test 1: Create audit log
    audit_id = await test_create_audit_log()
    
    if audit_id:
        # Wait a moment for database to process
        await asyncio.sleep(0.5)
        
        # Test 2: Get audit logs
        await test_get_audit_logs()
        
        # Test 3: Get recent activity
        await test_get_recent_activity()
        
        # Test 4: Get audit statistics
        await test_get_audit_statistics()
        
        # Test 5: Get resource audit trail
        await test_get_resource_audit_trail()
    
    print()
    print("=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. ✅ Check the results above - all tests should show SUCCESS")
    print("2. ✅ Login to admin portal and navigate to /admin/audit")
    print("3. ✅ Verify you can see the test audit log entries")
    print("4. ✅ Test the filters (action type, resource type, dates)")
    print("5. ✅ Perform real actions (login, approve supplier, upload document)")
    print("6. ✅ Verify those actions appear in the audit log")


if __name__ == "__main__":
    # Run tests
    asyncio.run(run_all_tests())
