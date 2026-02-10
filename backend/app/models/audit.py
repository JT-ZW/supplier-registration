"""
Audit trail models for tracking system activities.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class AuditAction(str, Enum):
    """Enumeration of auditable actions in the system."""
    
    # Supplier actions
    SUPPLIER_CREATED = "supplier_created"
    SUPPLIER_UPDATED = "supplier_updated"
    SUPPLIER_SUBMITTED = "supplier_submitted"
    SUPPLIER_APPROVED = "supplier_approved"
    SUPPLIER_REJECTED = "supplier_rejected"
    SUPPLIER_STATUS_CHANGED = "supplier_status_changed"
    SUPPLIER_VIEWED = "supplier_viewed"
    
    # Document actions
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_VERIFIED = "document_verified"
    DOCUMENT_REJECTED = "document_rejected"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_DOWNLOADED = "document_downloaded"
    DOCUMENT_VIEWED = "document_viewed"
    
    # Admin actions
    ADMIN_LOGIN = "admin_login"
    ADMIN_LOGOUT = "admin_logout"
    ADMIN_CREATED = "admin_created"
    ADMIN_UPDATED = "admin_updated"
    ADMIN_ROLE_CHANGED = "admin_role_changed"
    
    # Vendor actions
    VENDOR_LOGIN = "vendor_login"
    VENDOR_PASSWORD_CHANGED = "vendor_password_changed"
    
    # Message actions
    MESSAGE_SENT = "message_sent"
    MESSAGE_READ = "message_read"
    MESSAGE_UPDATED = "message_updated"
    
    # System actions
    REPORT_GENERATED = "report_generated"
    SETTINGS_UPDATED = "settings_updated"
    BULK_ACTION_PERFORMED = "bulk_action_performed"
    DATA_IMPORTED = "data_imported"
    DATA_EXPORTED = "data_exported"


class AuditResourceType(str, Enum):
    """Types of resources that can be audited."""
    SUPPLIER = "supplier"
    DOCUMENT = "document"
    ADMIN = "admin"
    VENDOR = "vendor"
    MESSAGE = "message"
    SYSTEM = "system"
    REPORT = "report"


# ============== Request Models ==============

class AuditLogCreateRequest(BaseModel):
    """Internal request model for creating audit logs."""
    user_id: Optional[str] = None
    user_type: str = Field(..., description="admin, vendor, or system")
    action: AuditAction
    resource_type: AuditResourceType
    resource_id: Optional[str] = None
    changes: Optional[Dict[str, Any]] = Field(None, description="Before/after values")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AuditLogFilterRequest(BaseModel):
    """Request model for filtering audit logs."""
    user_id: Optional[str] = None
    action: Optional[List[AuditAction]] = None
    resource_type: Optional[AuditResourceType] = None
    resource_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


# ============== Response Models ==============

class AuditLogResponse(BaseModel):
    """Response model for audit log entry."""
    id: str
    admin_id: Optional[str] = None
    supplier_id: Optional[str] = None
    user_type: str
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    action: str
    action_description: Optional[str] = None
    resource_type: str
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    changes: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Response model for list of audit logs."""
    items: List[AuditLogResponse]
    total: int
    limit: int
    offset: int


class AuditLogStatsResponse(BaseModel):
    """Response model for audit log statistics."""
    total_actions: int
    actions_by_type: Dict[str, int]
    actions_by_user: List[Dict[str, Any]]
    recent_activity: List[AuditLogResponse]
    most_active_resources: List[Dict[str, Any]]


# Action display names for UI
AUDIT_ACTION_LABELS = {
    AuditAction.SUPPLIER_CREATED: "Supplier Registered",
    AuditAction.SUPPLIER_UPDATED: "Supplier Updated",
    AuditAction.SUPPLIER_SUBMITTED: "Application Submitted",
    AuditAction.SUPPLIER_APPROVED: "Supplier Approved",
    AuditAction.SUPPLIER_REJECTED: "Supplier Rejected",
    AuditAction.SUPPLIER_STATUS_CHANGED: "Status Changed",
    AuditAction.DOCUMENT_UPLOADED: "Document Uploaded",
    AuditAction.DOCUMENT_VERIFIED: "Document Verified",
    AuditAction.DOCUMENT_REJECTED: "Document Rejected",
    AuditAction.DOCUMENT_DELETED: "Document Deleted",
    AuditAction.DOCUMENT_DOWNLOADED: "Document Downloaded",
    AuditAction.DOCUMENT_VIEWED: "Document Viewed",
    AuditAction.ADMIN_LOGIN: "Admin Login",
    AuditAction.ADMIN_LOGOUT: "Admin Logout",
    AuditAction.ADMIN_CREATED: "Admin User Created",
    AuditAction.ADMIN_UPDATED: "Admin User Updated",
    AuditAction.ADMIN_ROLE_CHANGED: "Admin Role Changed",
    AuditAction.VENDOR_LOGIN: "Vendor Login",
    AuditAction.VENDOR_PASSWORD_CHANGED: "Password Changed",
    AuditAction.MESSAGE_SENT: "Message Sent",
    AuditAction.MESSAGE_READ: "Message Read",
    AuditAction.REPORT_GENERATED: "Report Generated",
    AuditAction.SETTINGS_UPDATED: "Settings Updated",
    AuditAction.BULK_ACTION_PERFORMED: "Bulk Action Performed",
    AuditAction.DATA_IMPORTED: "Data Imported",
    AuditAction.DATA_EXPORTED: "Data Exported",
}
