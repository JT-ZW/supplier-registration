"""
Test script to verify audit logging is working correctly.
Run this after fixing the audit_service.py to confirm logs are being created.
"""

import asyncio
import sys
import os
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.audit_service import audit_service, AuditAction, AuditTargetType


async def test_audit_logging():
    """Test that audit logging works with the 004 schema."""
    
    print("Testing audit logging with 004 schema...")
    print("-" * 50)
    
    # Generate valid UUIDs for testing
    test_admin_id = str(uuid.uuid4())
    test_vendor_id = str(uuid.uuid4())
    
    print(f"\nUsing test admin_id: {test_admin_id}")
    print(f"Using test vendor_id: {test_vendor_id}")
    
    # Test 1: Simple login log
    print("\n1. Testing login log...")
    result = audit_service.log_login(
        admin_id=test_admin_id,
        admin_email="test-audit@example.com",
        ip_address="127.0.0.1",
        success=True
    )
    print(f"   Result: {'✓ SUCCESS' if result else '✗ FAILED'}")
    
    # Test 2: Analytics access log
    print("\n2. Testing analytics access log...")
    result = await audit_service.log_analytics_access(
        admin_id=test_admin_id,
        admin_email="test-audit@example.com",
        action=AuditAction.ANALYTICS_ACCESSED,
        report_type="dashboard",
        details={"report": "monthly_trends", "period": "12_months"},
        ip_address="127.0.0.1"
    )
    print(f"   Result: {'✓ SUCCESS' if result else '✗ FAILED'}")
    
    # Test 3: Vendor action log
    print("\n3. Testing vendor action log...")
    result = audit_service.log_vendor_action(
        admin_id=test_admin_id,
        admin_email="test-audit@example.com",
        action=AuditAction.VENDOR_VIEWED,
        vendor_id=test_vendor_id,
        vendor_name="Test Vendor Co.",
        details={"status": "approved"},
        ip_address="127.0.0.1"
    )
    print(f"   Result: {'✓ SUCCESS' if result else '✗ FAILED'}")
    
    print("\n" + "-" * 50)
    print("✓ All tests completed!")
    print("\nTo verify in Supabase:")
    print("  SELECT id, user_type, user_email, action, resource_type, created_at")
    print("  FROM audit_logs")
    print("  WHERE user_email = 'test-audit@example.com'")
    print("  ORDER BY created_at DESC LIMIT 10;")


if __name__ == "__main__":
    asyncio.run(test_audit_logging())
