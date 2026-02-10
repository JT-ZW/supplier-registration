"""
Test script for profile change email notifications.
Verifies that email notifications are sent to admins when a profile change request is created.
"""

import asyncio
from app.db.supabase import db
from app.core.email import email_service, EmailTemplate
from app.core.config import settings
from datetime import datetime, timezone


async def test_profile_change_email():
    """Test sending profile change request email to admins."""
    print("=" * 60)
    print("PROFILE CHANGE EMAIL NOTIFICATION TEST")
    print("=" * 60)
    
    # Test 1: Get active admin emails
    print("\n1. Fetching active admin emails...")
    try:
        admin_emails = await db.get_active_admin_emails()
        print(f"   ✓ Found {len(admin_emails)} active admin(s)")
        for admin in admin_emails:
            print(f"     - {admin['name']} ({admin['email']})")
    except Exception as e:
        print(f"   ✗ Error getting admin emails: {str(e)}")
        return
    
    if not admin_emails:
        print("   ⚠ No active admins found. Cannot send test email.")
        return
    
    # Test 2: Prepare test email data
    print("\n2. Preparing test email data...")
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
    print("   ✓ Email data prepared")
    
    # Test 3: Send test email
    print("\n3. Sending test email notifications...")
    try:
        results = await email_service.send_bulk_emails(
            recipients=admin_emails,
            template=EmailTemplate.ADMIN_PROFILE_CHANGE_REQUEST,
            common_data=email_data
        )
        
        print("\n   Email sending results:")
        for email, success in results.items():
            status = "✓ Sent" if success else "✗ Failed"
            print(f"     {status}: {email}")
        
        success_count = sum(1 for s in results.values() if s)
        print(f"\n   Summary: {success_count}/{len(results)} emails sent successfully")
        
    except Exception as e:
        print(f"   ✗ Error sending emails: {str(e)}")
        return
    
    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_profile_change_email())
