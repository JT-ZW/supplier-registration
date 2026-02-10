"""
Audit Logging Service
Provides centralized audit trail functionality for all major operations.
"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from app.db.supabase import get_db
from app.core.timezone import get_cat_now


class AuditAction:
    """Standard audit action constants."""
    # Authentication
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PASSWORD_RESET = "PASSWORD_RESET"
    
    # User Management
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_DELETED = "USER_DELETED"
    USER_ACTIVATED = "USER_ACTIVATED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    ACCOUNT_UNLOCKED = "ACCOUNT_UNLOCKED"
    
    # Vendor Management
    VENDOR_VIEWED = "VENDOR_VIEWED"
    VENDOR_LIST_VIEWED = "VENDOR_LIST_VIEWED"
    VENDOR_CREATED = "VENDOR_CREATED"
    VENDOR_UPDATED = "VENDOR_UPDATED"
    VENDOR_APPROVED = "VENDOR_APPROVED"
    VENDOR_REJECTED = "VENDOR_REJECTED"
    VENDOR_INFO_REQUESTED = "VENDOR_INFO_REQUESTED"
    VENDOR_ACTIVATED = "VENDOR_ACTIVATED"
    VENDOR_DEACTIVATED = "VENDOR_DEACTIVATED"
    
    # Document Management
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_VIEWED = "DOCUMENT_VIEWED"
    DOCUMENT_VERIFIED = "DOCUMENT_VERIFIED"
    DOCUMENT_REJECTED = "DOCUMENT_REJECTED"
    DOCUMENT_DELETED = "DOCUMENT_DELETED"
    
    # Messages
    MESSAGE_SENT = "MESSAGE_SENT"
    MESSAGE_VIEWED = "MESSAGE_VIEWED"
    MESSAGE_DELETED = "MESSAGE_DELETED"
    
    # Analytics
    ANALYTICS_VIEWED = "ANALYTICS_VIEWED"
    ANALYTICS_ACCESSED = "ANALYTICS_ACCESSED"
    REPORT_GENERATED = "REPORT_GENERATED"
    REPORT_EXPORTED = "REPORT_EXPORTED"


class AuditTargetType:
    """Standard audit target type constants."""
    ADMIN_USER = "ADMIN_USER"
    VENDOR = "VENDOR"
    SUPPLIER = "SUPPLIER"
    DOCUMENT = "DOCUMENT"
    MESSAGE = "MESSAGE"
    ANALYTICS = "ANALYTICS"
    SYSTEM = "SYSTEM"


class AuditService:
    """Service for creating and managing audit logs."""
    
    def __init__(self):
        self.db = get_db()
    
    def log(
        self,
        admin_id: str,
        admin_email: str,
        action: str,
        target_type: str,
        target_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> bool:
        """
        Create an audit log entry.
        
        Args:
            admin_id: ID of the admin performing the action
            admin_email: Email of the admin performing the action
            action: Action being performed (use AuditAction constants)
            target_type: Type of target being acted upon (use AuditTargetType constants)
            target_id: ID of the target entity (optional)
            details: Additional context as JSON (optional)
            ip_address: IP address of the request (optional)
        
        Returns:
            bool: True if logged successfully, False otherwise
        """
        try:
            log_data = {
                "admin_id": admin_id,
                "user_type": "admin",  # Required field in 004 schema
                "user_email": admin_email,
                "action": action,
                "resource_type": target_type,
                "created_at": get_cat_now().isoformat()
            }
            
            if target_id:
                log_data["resource_id"] = target_id
            
            if details:
                log_data["metadata"] = details  # Use 'metadata' field from 004 schema
            
            if ip_address:
                log_data["ip_address"] = ip_address
            
            self.db.client.table("audit_logs").insert(log_data).execute()
            return True
            
        except Exception as e:
            # Log the error but don't fail the main operation
            print(f"Audit logging error: {str(e)}")
            return False
    
    async def log_login(self, admin_id: str, admin_email: str, ip_address: Optional[str] = None, success: bool = True):
        """Log a login attempt."""
        action = AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED
        return self.log(
            admin_id=admin_id,
            admin_email=admin_email,
            action=action,
            target_type=AuditTargetType.ADMIN_USER,
            target_id=admin_id,
            ip_address=ip_address
        )
    
    async def log_logout(self, admin_id: str, admin_email: str, ip_address: Optional[str] = None):
        """Log a logout."""
        return self.log(
            admin_id=admin_id,
            admin_email=admin_email,
            action=AuditAction.LOGOUT,
            target_type=AuditTargetType.ADMIN_USER,
            target_id=admin_id,
            ip_address=ip_address
        )
    
    async def log_vendor_action(
        self,
        admin_id: str,
        admin_email: str,
        action: str,
        vendor_id: str,
        vendor_name: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ):
        """Log a vendor-related action."""
        log_details = {"vendor_name": vendor_name}
        if details:
            log_details.update(details)
        
        return self.log(
            admin_id=admin_id,
            admin_email=admin_email,
            action=action,
            target_type=AuditTargetType.VENDOR,
            target_id=vendor_id,
            details=log_details,
            ip_address=ip_address
        )
    
    async def log_document_action(
        self,
        admin_id: str,
        admin_email: str,
        action: str,
        document_id: str,
        document_type: str,
        vendor_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ):
        """Log a document-related action."""
        log_details = {"document_type": document_type}
        if vendor_id:
            log_details["vendor_id"] = vendor_id
        if details:
            log_details.update(details)
        
        return self.log(
            admin_id=admin_id,
            admin_email=admin_email,
            action=action,
            target_type=AuditTargetType.DOCUMENT,
            target_id=document_id,
            details=log_details,
            ip_address=ip_address
        )
    
    async def log_user_management(
        self,
        admin_id: str,
        admin_email: str,
        action: str,
        target_user_id: str,
        target_user_email: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ):
        """Log a user management action."""
        log_details = {"target_user_email": target_user_email}
        if details:
            log_details.update(details)
        
        return self.log(
            admin_id=admin_id,
            admin_email=admin_email,
            action=action,
            target_type=AuditTargetType.ADMIN_USER,
            target_id=target_user_id,
            details=log_details,
            ip_address=ip_address
        )
    
    async def log_message(
        self,
        admin_id: str,
        admin_email: str,
        action: str,
        message_id: str,
        vendor_id: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ):
        """Log a message-related action."""
        log_details = {"vendor_id": vendor_id}
        if details:
            log_details.update(details)
        
        return self.log(
            admin_id=admin_id,
            admin_email=admin_email,
            action=action,
            target_type=AuditTargetType.MESSAGE,
            target_id=message_id,
            details=log_details,
            ip_address=ip_address
        )
    
    async def log_analytics_access(
        self,
        admin_id: str,
        admin_email: str,
        action: str,
        report_type: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ):
        """Log analytics and report access."""
        log_details = {"report_type": report_type}
        if details:
            log_details.update(details)
        
        return self.log(
            admin_id=admin_id,
            admin_email=admin_email,
            action=action,
            target_type=AuditTargetType.ANALYTICS,
            details=log_details,
            ip_address=ip_address
        )


# Global instance
audit_service = AuditService()
