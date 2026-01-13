"""
Quick test script to verify SendGrid email is working.
Run this to send a test email.
"""
import asyncio
from app.core.email import EmailService, EmailTemplate

async def test_email():
    """Send a test email."""
    email_service = EmailService()
    
    # Test data
    test_data = {
        "supplier_name": "Test Company Ltd",
        "contact_person": "Jeffrey",
        "supplier_id": "TEST-12345",
    }
    
    # Your email to receive the test
    recipient_email = "murungwenij@africau.edu"
    
    print(f"🚀 Sending test email to: {recipient_email}")
    print(f"📧 Using SendGrid API")
    
    try:
        await email_service.send_template_email(
            to_email=recipient_email,
            template=EmailTemplate.SUPPLIER_REGISTRATION_SUBMITTED,
            data=test_data
        )
        print("✅ Test email sent successfully!")
        print(f"📬 Check your inbox at: {recipient_email}")
        print("⚠️  If you don't see it, check your spam folder")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        print(f"Error type: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(test_email())
