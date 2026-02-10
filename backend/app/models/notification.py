"""Notification models and enums."""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, UUID4


class NotificationType(str, Enum):
    """Types of notifications."""
    SUPPLIER_STATUS_CHANGE = "supplier_status_change"
    DOCUMENT_VERIFICATION = "document_verification"
    DOCUMENT_UPLOADED = "document_uploaded"
    PROFILE_UPDATE_REQUESTED = "profile_update_requested"
    APPLICATION_SUBMITTED = "application_submitted"
    NEW_MESSAGE = "new_message"
    SYSTEM_ANNOUNCEMENT = "system_announcement"


class RecipientType(str, Enum):
    """Types of notification recipients."""
    ADMIN = "admin"
    VENDOR = "vendor"
    SUPPLIER = "supplier"


# Notification type labels for UI display
NOTIFICATION_TYPE_LABELS = {
    NotificationType.SUPPLIER_STATUS_CHANGE: "Status Update",
    NotificationType.DOCUMENT_VERIFICATION: "Document Verified",
    NotificationType.DOCUMENT_UPLOADED: "Document Upload",
    NotificationType.PROFILE_UPDATE_REQUESTED: "Update Requested",
    NotificationType.APPLICATION_SUBMITTED: "Application Submitted",
    NotificationType.NEW_MESSAGE: "New Message",
    NotificationType.SYSTEM_ANNOUNCEMENT: "Announcement"
}


class NotificationBase(BaseModel):
    """Base notification model."""
    recipient_id: UUID4
    recipient_type: RecipientType
    type: NotificationType
    title: str = Field(..., max_length=255)
    message: str
    action_url: Optional[str] = Field(None, max_length=500)
    action_label: Optional[str] = Field(None, max_length=100)
    resource_type: Optional[str] = Field(None, max_length=50)
    resource_id: Optional[UUID4] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    send_email: bool = False
    expires_at: Optional[datetime] = None


class NotificationCreate(NotificationBase):
    """Create notification request."""
    pass


class NotificationResponse(NotificationBase):
    """Notification response model."""
    id: UUID4
    is_read: bool
    read_at: Optional[datetime] = None
    email_sent: bool
    email_sent_at: Optional[datetime] = None
    created_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationUpdate(BaseModel):
    """Update notification model."""
    is_read: Optional[bool] = None


class NotificationListResponse(BaseModel):
    """Paginated notification list response."""
    items: list[NotificationResponse]
    total: int
    unread_count: int
    limit: int
    offset: int


class NotificationStatsResponse(BaseModel):
    """Notification statistics."""
    total_notifications: int
    unread_count: int
    by_type: Dict[str, int]
    recent_count: int  # Last 24 hours


class MarkReadRequest(BaseModel):
    """Request to mark notifications as read."""
    notification_ids: list[UUID4]


class BulkNotificationCreate(BaseModel):
    """Create notifications for multiple recipients."""
    recipient_ids: list[UUID4]
    recipient_type: RecipientType
    type: NotificationType
    title: str = Field(..., max_length=255)
    message: str
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[UUID4] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    send_email: bool = False
    expires_at: Optional[datetime] = None
