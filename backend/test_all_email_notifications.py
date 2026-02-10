"""
Comprehensive test script for all email notifications.
Tests all email templates to verify email delivery is working.
"""

import asyncio
from app.db.supabase import db
from app.core.email import email_service, EmailTemplate
from app.core.config import settings
from datetime import datetime, timezone


async def test_all_emails():
    """Test all email notification types."""
    print("=" * 80)
    print("COMPREHENSIVE EMAIL NOTIFICATION TEST")
    print("=" * 80)
    
    # Get test recipient info
    print("\n1. Getting admin and test vendor emails...")
    try:
        admin_emails = await db.get_active_admin_emails()
        print(f"   ✓ Found {len(admin_emails)} active admin(s)")
        for admin in admin_emails:
            print(f"     - {admin['name']} ({admin['email']})")
    except Exception as e:
        print(f"   ✗ Error getting admin emails: {str(e)}")
        return
    
    if not admin_emails:
        print("   ⚠ No active admins found. Cannot test admin notifications.")
        admin_emails = []
    
    # Test vendor email (using first admin as test recipient)
    test_vendor_email = admin_emails[0]['email'] if admin_emails else "test@example.com"
    test_vendor_name = "Test Vendor Contact"
    
    print(f"\n   Using test vendor email: {test_vendor_email}")
    
    # Track all test results
    test_results = []
    
    # ============================================================
    # TEST 1: Profile Change Request (Admin notification)
    # ============================================================
    print("\n" + "-" * 80)
    print("TEST 1: Profile Change Request Notification (to Admins)")
    print("-" * 80)
    
    if admin_emails:
        try:
            field_list_html = "".join([
                "<li><strong>Company Name</strong></li>",
                "<li><strong>Tax ID Number</strong></li>",
                "<li><strong>Bank Account Details</strong></li>"
            ])
            
            email_data = {
                "supplier_name": "Test Supplier Company",
                "registration_number": "TEST-12345",
                "status": "APPROVED",
                "submitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "supplier_id": "test-uuid-12345",
                "field_list": field_list_html,
                "review_link": f"{settings.FRONTEND_URL}/admin/supplier/test-uuid-12345"
            }
            
            results = await email_service.send_bulk_emails(
                recipients=admin_emails,
                template=EmailTemplate.ADMIN_PROFILE_CHANGE_REQUEST,
                common_data=email_data
            )
            
            success_count = sum(1 for s in results.values() if s)
            test_results.append(("Profile Change Request", success_count > 0))
            print(f"   Result: {success_count}/{len(results)} emails sent")
            
        except Exception as e:
            test_results.append(("Profile Change Request", False))
            print(f"   ✗ Error: {str(e)}")
    else:
        print("   ⚠ Skipped - No admin emails available")
    
    # ============================================================
    # TEST 2: Vendor Application Submitted (Vendor confirmation)
    # ============================================================
    print("\n" + "-" * 80)
    print("TEST 2: Application Submitted Confirmation (to Vendor)")
    print("-" * 80)
    
    try:
        success = await email_service.send_template_email(
            to_email=test_vendor_email,
            template=EmailTemplate.SUPPLIER_REGISTRATION_SUBMITTED,
            data={
                "supplier_name": "Test Supplier Company",
                "contact_person": test_vendor_name,
                "supplier_id": "test-uuid-12345"
            },
            to_name=test_vendor_name
        )
        
        test_results.append(("Application Submitted Confirmation", success))
        status = "✓ Sent" if success else "✗ Failed"
        print(f"   {status}: {test_vendor_email}")
        
    except Exception as e:
        test_results.append(("Application Submitted Confirmation", False))
        print(f"   ✗ Error: {str(e)}")
    
    # ============================================================
    # TEST 3: Admin notification (Application submitted)
    # ============================================================
    print("\n" + "-" * 80)
    print("TEST 3: Application Submitted Notification (to Admin)")
    print("-" * 80)
    
    try:
        success = await email_service.send_template_email(
            to_email=settings.ADMIN_EMAIL,
            template=EmailTemplate.ADMIN_APPLICATION_SUBMITTED,
            data={
                "supplier_name": "Test Supplier Company",
                "registration_number": "TEST-12345",
                "category": "Construction",
                "contact_person": test_vendor_name,
                "email": test_vendor_email,
                "phone": "+263 123 456 789",
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "supplier_id": "test-uuid-12345",
                "review_link": f"{settings.FRONTEND_URL}/admin/suppliers/test-uuid-12345"
            },
            to_name="Admin Team"
        )
        
        test_results.append(("Application Submitted (Admin)", success))
        status = "✓ Sent" if success else "✗ Failed"
        print(f"   {status}: {settings.ADMIN_EMAIL}")
        
    except Exception as e:
        test_results.append(("Application Submitted (Admin)", False))
        print(f"   ✗ Error: {str(e)}")
    
    # ============================================================
    # TEST 4: More Info Request (to Vendor)
    # ============================================================
    print("\n" + "-" * 80)
    print("TEST 4: More Info Request (to Vendor)")
    print("-" * 80)
    
    try:
        success = await email_service.send_template_email(
            to_email=test_vendor_email,
            template=EmailTemplate.SUPPLIER_MORE_INFO_REQUESTED,
            data={
                "supplier_name": "Test Supplier Company",
                "contact_person": test_vendor_name,
                "supplier_id": "test-uuid-12345",
                "request_message": "Please provide updated tax clearance certificate dated within the last 3 months.",
                "update_link": f"{settings.FRONTEND_URL}/register/test-uuid-12345"
            },
            to_name=test_vendor_name
        )
        
        test_results.append(("More Info Request", success))
        status = "✓ Sent" if success else "✗ Failed"
        print(f"   {status}: {test_vendor_email}")
        
    except Exception as e:
        test_results.append(("More Info Request", False))
        print(f"   ✗ Error: {str(e)}")
    
    # ============================================================
    # TEST 5: Application Approved (to Vendor)
    # ============================================================
    print("\n" + "-" * 80)
    print("TEST 5: Application Approved (to Vendor)")
    print("-" * 80)
    
    try:
        success = await email_service.send_template_email(
            to_email=test_vendor_email,
            template=EmailTemplate.SUPPLIER_APPROVED,
            data={
                "supplier_name": "Test Supplier Company",
                "contact_person": test_vendor_name,
                "supplier_id": "test-uuid-12345"
            },
            to_name=test_vendor_name
        )
        
        test_results.append(("Application Approved", success))
        status = "✓ Sent" if success else "✗ Failed"
        print(f"   {status}: {test_vendor_email}")
        
    except Exception as e:
        test_results.append(("Application Approved", False))
        print(f"   ✗ Error: {str(e)}")
    
    # ============================================================
    # TEST 6: Application Rejected (to Vendor)
    # ============================================================
    print("\n" + "-" * 80)
    print("TEST 6: Application Rejected (to Vendor)")
    print("-" * 80)
    
    try:
        success = await email_service.send_template_email(
            to_email=test_vendor_email,
            template=EmailTemplate.SUPPLIER_REJECTED,
            data={
                "supplier_name": "Test Supplier Company",
                "contact_person": test_vendor_name,
                "supplier_id": "test-uuid-12345",
                "rejection_reason": "Incomplete documentation - missing tax clearance certificate."
            },
            to_name=test_vendor_name
        )
        
        test_results.append(("Application Rejected", success))
        status = "✓ Sent" if success else "✗ Failed"
        print(f"   {status}: {test_vendor_email}")
        
    except Exception as e:
        test_results.append(("Application Rejected", False))
        print(f"   ✗ Error: {str(e)}")
    
    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, success in test_results if success)
    total = len(test_results)
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {(passed/total*100):.1f}%\n")
    
    print("Individual Results:")
    for test_name, success in test_results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print("\n" + "=" * 80)
    
    if passed == total:
        print("🎉 ALL EMAIL NOTIFICATIONS WORKING PERFECTLY!")
    elif passed > 0:
        print("⚠️  SOME EMAIL NOTIFICATIONS FAILED - CHECK CONFIGURATION")
    else:
        print("❌ ALL EMAIL NOTIFICATIONS FAILED - CHECK EMAIL SERVICE SETUP")
    
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_all_emails())
