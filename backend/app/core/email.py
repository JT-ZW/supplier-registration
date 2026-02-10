"""
Email notification service using SendGrid or SMTP.
"""

from typing import Optional, Dict, Any, List
from enum import Enum
import asyncio
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .config import settings


class EmailTemplate(str, Enum):
    """Email template types."""
    SUPPLIER_REGISTRATION_SUBMITTED = "supplier_registration_submitted"
    SUPPLIER_APPROVED = "supplier_approved"
    SUPPLIER_REJECTED = "supplier_rejected"
    SUPPLIER_MORE_INFO_REQUESTED = "supplier_more_info_requested"
    ADMIN_NEW_APPLICATION = "admin_new_application"
    ADMIN_APPLICATION_SUBMITTED = "admin_application_submitted"
    ADMIN_PROFILE_UPDATED = "admin_profile_updated"
    ADMIN_PROFILE_CHANGE_REQUEST = "admin_profile_change_request"
    ADMIN_DOCUMENT_UPLOADED = "admin_document_uploaded"
    ADMIN_NEW_MESSAGE = "admin_new_message"
    VENDOR_MESSAGE_REPLY = "vendor_message_reply"


class EmailService:
    """
    Service for sending email notifications.
    Supports both SendGrid and SMTP backends.
    """
    
    def __init__(self):
        """Initialize email service with configured provider."""
        self._use_sendgrid = bool(settings.SENDGRID_API_KEY)
        
        if self._use_sendgrid:
            self._sendgrid_client = SendGridAPIClient(settings.SENDGRID_API_KEY)
    
    def _get_template_content(
        self,
        template: EmailTemplate,
        data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Get email subject and body for a template.
        
        Args:
            template: Email template type
            data: Data to interpolate into template
            
        Returns:
            Dictionary with 'subject' and 'body' keys
        """
        templates = {
            EmailTemplate.SUPPLIER_REGISTRATION_SUBMITTED: {
                "subject": "Supplier Registration Received - {supplier_name}",
                "body": """
                <h2>Thank you for your registration!</h2>
                <p>Dear {contact_person},</p>
                <p>We have received your supplier registration application for <strong>{supplier_name}</strong>.</p>
                <p>Your application is now under review. We will notify you once a decision has been made.</p>
                <p><strong>Application Reference:</strong> {supplier_id}</p>
                <p>If you have any questions, please don't hesitate to contact us.</p>
                <br>
                <p>Best regards,</p>
                <p>The Procurement Team</p>
                """
            },
            EmailTemplate.SUPPLIER_APPROVED: {
                "subject": "Supplier Registration Approved - {supplier_name}",
                "body": """
                <h2>Congratulations! Your registration has been approved.</h2>
                <p>Dear {contact_person},</p>
                <p>We are pleased to inform you that your supplier registration for <strong>{supplier_name}</strong> has been approved.</p>
                <p>You are now an approved supplier in our system and may be contacted for procurement opportunities.</p>
                <p><strong>Application Reference:</strong> {supplier_id}</p>
                <br>
                <p>Best regards,</p>
                <p>The Procurement Team</p>
                """
            },
            EmailTemplate.SUPPLIER_REJECTED: {
                "subject": "Supplier Registration Status - {supplier_name}",
                "body": """
                <h2>Registration Application Update</h2>
                <p>Dear {contact_person},</p>
                <p>We regret to inform you that your supplier registration for <strong>{supplier_name}</strong> could not be approved at this time.</p>
                <p><strong>Reason:</strong> {rejection_reason}</p>
                <p>If you believe this decision was made in error or would like to reapply in the future, please contact our procurement team.</p>
                <p><strong>Application Reference:</strong> {supplier_id}</p>
                <br>
                <p>Best regards,</p>
                <p>The Procurement Team</p>
                """
            },
            EmailTemplate.SUPPLIER_MORE_INFO_REQUESTED: {
                "subject": "Additional Information Required - {supplier_name}",
                "body": """
                <h2>Additional Information Required</h2>
                <p>Dear {contact_person},</p>
                <p>We have reviewed your supplier registration for <strong>{supplier_name}</strong> and require additional information to proceed.</p>
                <p><strong>Details:</strong></p>
                <p>{request_message}</p>
                <p>Please visit the link below to update your application:</p>
                <p><a href="{update_link}">Update Your Application</a></p>
                <p><strong>Application Reference:</strong> {supplier_id}</p>
                <br>
                <p>Best regards,</p>
                <p>The Procurement Team</p>
                """
            },
            EmailTemplate.ADMIN_NEW_APPLICATION: {
                "subject": "New Supplier Application - {supplier_name}",
                "body": """
                <h2>New Supplier Registration</h2>
                <p>A new supplier registration has been submitted and is awaiting review.</p>
                <p><strong>Supplier Name:</strong> {supplier_name}</p>
                <p><strong>Category:</strong> {category}</p>
                <p><strong>Location:</strong> {location}</p>
                <p><strong>Contact Person:</strong> {contact_person}</p>
                <p><strong>Application ID:</strong> {supplier_id}</p>
                <p><a href="{review_link}">Review Application</a></p>
                <br>
                <p>Procurement System</p>
                """
            },
            EmailTemplate.ADMIN_APPLICATION_SUBMITTED: {
                "subject": "Application Submitted for Review - {supplier_name}",
                "body": """
                <h2>Application Ready for Review</h2>
                <p>A supplier has completed and submitted their application for review.</p>
                <p><strong>Supplier Name:</strong> {supplier_name}</p>
                <p><strong>Registration Number:</strong> {registration_number}</p>
                <p><strong>Category:</strong> {category}</p>
                <p><strong>Contact Person:</strong> {contact_person}</p>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Phone:</strong> {phone}</p>
                <p><strong>Submitted At:</strong> {submitted_at}</p>
                <p><strong>Application ID:</strong> {supplier_id}</p>
                <p><a href="{review_link}">Review Application Now</a></p>
                <br>
                <p>Procurement System</p>
                """
            },
            EmailTemplate.ADMIN_PROFILE_UPDATED: {
                "subject": "Supplier Profile Updated - {supplier_name}",
                "body": """
                <h2>Supplier Profile Update</h2>
                <p>A supplier has updated their profile information.</p>
                <p><strong>Supplier Name:</strong> {supplier_name}</p>
                <p><strong>Registration Number:</strong> {registration_number}</p>
                <p><strong>Current Status:</strong> {status}</p>
                <p><strong>Updated At:</strong> {updated_at}</p>
                <p><strong>Application ID:</strong> {supplier_id}</p>
                <p>Changes may require review if the supplier is in {affected_statuses} status.</p>
                <p><a href="{review_link}">View Updated Profile</a></p>
                <br>
                <p>Procurement System</p>
                """
            },
            EmailTemplate.ADMIN_PROFILE_CHANGE_REQUEST: {
                "subject": "Profile Change Request - {supplier_name}",
                "body": """
                <h2>Profile Change Request Requires Approval</h2>
                <p>A supplier has submitted a profile change request that requires admin review and approval.</p>
                <p><strong>Supplier Name:</strong> {supplier_name}</p>
                <p><strong>Registration Number:</strong> {registration_number}</p>
                <p><strong>Current Status:</strong> {status}</p>
                <p><strong>Submitted At:</strong> {submitted_at}</p>
                <p><strong>Fields Requested for Change:</strong></p>
                <ul>
                {field_list}
                </ul>
                <p><strong>Application ID:</strong> {supplier_id}</p>
                <p>Please review the changes as soon as possible.</p>
                <p><a href="{review_link}" style="display: inline-block; background-color: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Review Profile Changes</a></p>
                <br>
                <p>Procurement System</p>
                """
            },
            EmailTemplate.ADMIN_DOCUMENT_UPLOADED: {
                "subject": "New Document Uploaded - {supplier_name}",
                "body": """
                <h2>Document Upload Notification</h2>
                <p>A supplier has uploaded or replaced a document.</p>
                <p><strong>Supplier Name:</strong> {supplier_name}</p>
                <p><strong>Document Type:</strong> {document_type}</p>
                <p><strong>Filename:</strong> {filename}</p>
                <p><strong>Action:</strong> {action}</p>
                <p><strong>Uploaded At:</strong> {uploaded_at}</p>
                <p><strong>Application ID:</strong> {supplier_id}</p>
                <p>This document may require verification.</p>
                <p><a href="{review_link}">Review Document</a></p>
                <br>
                <p>Procurement System</p>
                """
            },
            EmailTemplate.ADMIN_NEW_MESSAGE: {
                "subject": "New Message from {supplier_name}",
                "body": """
                <h2>New Message Received</h2>
                <p>You have received a new message from a vendor.</p>
                <p><strong>From:</strong> {supplier_name}</p>
                <p><strong>Subject:</strong> {thread_subject}</p>
                <p><strong>Message Preview:</strong></p>
                <blockquote style="background-color: #f5f5f5; padding: 15px; border-left: 4px solid #2563eb;">
                {message_preview}
                </blockquote>
                <p><strong>Sent At:</strong> {sent_at}</p>
                <p><a href="{message_link}" style="display: inline-block; background-color: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Full Conversation</a></p>
                <br>
                <p>Procurement System</p>
                """
            },
            EmailTemplate.VENDOR_MESSAGE_REPLY: {
                "subject": "Response to: {thread_subject}",
                "body": """
                <h2>You Have a New Reply</h2>
                <p>Dear {contact_person},</p>
                <p>The admin has responded to your message.</p>
                <p><strong>Subject:</strong> {thread_subject}</p>
                <p><strong>Admin Response:</strong></p>
                <blockquote style="background-color: #f5f5f5; padding: 15px; border-left: 4px solid #2563eb;">
                {message_preview}
                </blockquote>
                <p><strong>Replied At:</strong> {sent_at}</p>
                <p><a href="{message_link}" style="display: inline-block; background-color: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Full Conversation</a></p>
                <br>
                <p>Best regards,</p>
                <p>The Procurement Team</p>
                """
            }
        }
        
        template_data = templates.get(template, {
            "subject": "Notification",
            "body": "<p>You have a new notification.</p>"
        })
        
        # Interpolate data into template
        subject = template_data["subject"].format(**data)
        body = template_data["body"].format(**data)
        
        return {"subject": subject, "body": body}
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        to_name: Optional[str] = None
    ) -> bool:
        """
        Send an email using the configured provider.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML body content
            to_name: Optional recipient name
            
        Returns:
            True if email was sent successfully
        """
        if self._use_sendgrid:
            return await self._send_via_sendgrid(to_email, subject, html_content, to_name)
        else:
            return await self._send_via_smtp(to_email, subject, html_content, to_name)
    
    async def _send_via_sendgrid(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        to_name: Optional[str] = None
    ) -> bool:
        """Send email via SendGrid."""
        try:
            message = Mail(
                from_email=Email(settings.FROM_EMAIL, settings.FROM_NAME),
                to_emails=To(to_email, to_name),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            # Run in executor since sendgrid client is synchronous
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._sendgrid_client.send(message)
            )
            return True
            
        except Exception as e:
            print(f"SendGrid email error: {str(e)}")
            return False
    
    async def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        to_name: Optional[str] = None
    ) -> bool:
        """Send email via SMTP."""
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>"
            message["To"] = f"{to_name} <{to_email}>" if to_name else to_email
            
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD,
                use_tls=True
            )
            return True
            
        except Exception as e:
            print(f"SMTP email error: {str(e)}")
            return False
    
    async def send_template_email(
        self,
        to_email: str,
        template: EmailTemplate,
        data: Dict[str, Any],
        to_name: Optional[str] = None
    ) -> bool:
        """
        Send an email using a predefined template.
        
        Args:
            to_email: Recipient email address
            template: Email template to use
            data: Data to interpolate into template
            to_name: Optional recipient name
            
        Returns:
            True if email was sent successfully
        """
        content = self._get_template_content(template, data)
        return await self.send_email(
            to_email=to_email,
            subject=content["subject"],
            html_content=content["body"],
            to_name=to_name
        )
    
    async def send_bulk_emails(
        self,
        recipients: List[Dict[str, Any]],
        template: EmailTemplate,
        common_data: Dict[str, Any]
    ) -> Dict[str, bool]:
        """
        Send the same template email to multiple recipients.
        
        Args:
            recipients: List of dicts with 'email' and optional 'name' keys
            template: Email template to use
            common_data: Common data for all emails
            
        Returns:
            Dictionary mapping email addresses to send success status
        """
        results = {}
        for recipient in recipients:
            email = recipient.get("email")
            name = recipient.get("name")
            success = await self.send_template_email(
                to_email=email,
                template=template,
                data=common_data,
                to_name=name
            )
            results[email] = success
        return results


# Singleton instance
email_service = EmailService()
