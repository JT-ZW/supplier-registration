"""
Message-related Pydantic models for request/response validation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, UUID4
from enum import Enum


class SenderType(str, Enum):
    """Message sender type."""
    ADMIN = "admin"
    VENDOR = "vendor"


class MessagePriority(str, Enum):
    """Message thread priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageCategoryBase(BaseModel):
    """Base message category model."""
    name: str
    description: Optional[str] = None
    color: str = "blue"
    icon: Optional[str] = None


class MessageCategory(MessageCategoryBase):
    """Message category response model."""
    id: UUID4
    created_at: datetime


class MessageCreate(BaseModel):
    """Request model for creating a message."""
    thread_id: Optional[UUID4] = None  # None if creating new thread
    message_text: str = Field(..., min_length=1, max_length=5000)
    attachments: Optional[List[Dict[str, Any]]] = None
    
    # Only for new threads
    subject: Optional[str] = Field(None, max_length=200)
    supplier_id: Optional[UUID4] = None
    category_id: Optional[UUID4] = None
    priority: MessagePriority = MessagePriority.NORMAL


class MessageResponse(BaseModel):
    """Response model for a message."""
    id: UUID4
    thread_id: UUID4
    sender_type: SenderType
    sender_id: UUID4
    sender_name: str
    message_text: str
    attachments: List[Dict[str, Any]]
    read_by_admin: bool
    read_by_vendor: bool
    read_at: Optional[datetime] = None
    created_at: datetime


class ThreadCreate(BaseModel):
    """Request model for creating a message thread."""
    subject: str = Field(..., min_length=1, max_length=200)
    supplier_id: UUID4
    category_id: Optional[UUID4] = None
    priority: MessagePriority = MessagePriority.NORMAL
    initial_message: str = Field(..., min_length=1, max_length=5000)


class ThreadSummary(BaseModel):
    """Summary model for message thread list."""
    id: UUID4
    subject: str
    supplier_id: UUID4
    supplier_name: str
    category_id: Optional[UUID4] = None
    category_name: Optional[str] = None
    category_color: Optional[str] = None
    priority: MessagePriority
    is_archived: bool
    last_message_at: datetime
    last_message_by: Optional[SenderType] = None
    last_message: Optional[str] = None
    unread_by_admin: int
    unread_by_vendor: int
    message_count: int
    created_at: datetime


class ThreadDetail(BaseModel):
    """Detailed model for a single thread with messages."""
    id: UUID4
    subject: str
    supplier_id: UUID4
    supplier_name: str
    category_id: Optional[UUID4] = None
    category_name: Optional[str] = None
    category_color: Optional[str] = None
    priority: MessagePriority
    is_archived: bool
    last_message_at: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None
    messages: List[MessageResponse]


class ThreadUpdate(BaseModel):
    """Request model for updating thread properties."""
    subject: Optional[str] = Field(None, max_length=200)
    category_id: Optional[UUID4] = None
    priority: Optional[MessagePriority] = None
    is_archived: Optional[bool] = None


class MarkAsReadRequest(BaseModel):
    """Request to mark messages as read."""
    thread_id: UUID4


class UnreadCountResponse(BaseModel):
    """Response with unread message count."""
    total_unread: int
    threads_with_unread: List[Dict[str, Any]]


class ThreadListResponse(BaseModel):
    """Response for thread list with pagination."""
    threads: List[ThreadSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class BulkMessageRequest(BaseModel):
    """Request for sending bulk messages to multiple suppliers."""
    subject: str = Field(..., min_length=1, max_length=200)
    message_text: str = Field(..., min_length=1, max_length=5000)
    supplier_ids: List[UUID4] = Field(..., min_items=1)
    category_id: Optional[UUID4] = None
    priority: MessagePriority = MessagePriority.NORMAL


class BulkMessageResponse(BaseModel):
    """Response for bulk message operation."""
    success_count: int
    failed_count: int
    thread_ids: List[UUID4]
    errors: Optional[List[Dict[str, Any]]] = None
