"""
Admin-related Pydantic models for request/response validation.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator

from .enums import AdminAction, SupplierStatus


# ============== Request Models ==============

class AdminLoginRequest(BaseModel):
    """Request model for admin login."""
    email: EmailStr = Field(..., description="Admin email address")
    password: str = Field(..., min_length=8, description="Admin password")


class AdminCreateRequest(BaseModel):
    """Request model for creating a new admin user."""
    email: EmailStr = Field(..., description="Admin email address")
    password: str = Field(..., min_length=8, description="Admin password")
    name: str = Field(..., min_length=2, max_length=100, description="Admin full name")
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class AdminPasswordChangeRequest(BaseModel):
    """Request model for changing admin password."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    
    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class ApplicationReviewRequest(BaseModel):
    """Request model for admin to review a supplier application."""
    action: SupplierStatus = Field(..., description="Action to take on the application")
    notes: Optional[str] = Field(None, max_length=1000, description="Admin notes")
    
    @field_validator("action")
    @classmethod
    def validate_action(cls, v: SupplierStatus) -> SupplierStatus:
        """Ensure only valid review actions are allowed."""
        allowed_actions = [
            SupplierStatus.APPROVED,
            SupplierStatus.REJECTED,
            SupplierStatus.NEED_MORE_INFO,
            SupplierStatus.UNDER_REVIEW,
        ]
        if v not in allowed_actions:
            raise ValueError(f"Action must be one of: {', '.join([a.value for a in allowed_actions])}")
        return v


class RequestMoreInfoRequest(BaseModel):
    """Request model for requesting more info from supplier."""
    message: str = Field(..., min_length=10, max_length=2000, description="Message to supplier explaining what is needed")
    requested_documents: Optional[List[str]] = Field(None, description="Specific documents that need to be re-uploaded")


class RefreshTokenRequest(BaseModel):
    """Request model for refreshing access token."""
    refresh_token: str = Field(..., description="Refresh token")


# ============== Response Models ==============

class TokenResponse(BaseModel):
    """Response model for authentication tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminResponse(BaseModel):
    """Response model for admin user data."""
    id: str
    email: str
    full_name: str
    role: str
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AdminProfileResponse(BaseModel):
    """Response model for admin profile with additional details."""
    id: str
    email: str
    full_name: str
    role: str
    created_at: datetime
    last_login: Optional[datetime] = None
    total_reviews: int = 0
    
    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Response model for audit log entry."""
    id: str
    admin_id: str
    admin_name: Optional[str] = None
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    action: AdminAction
    details: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime
    
    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Response model for paginated audit log list."""
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReviewHistoryResponse(BaseModel):
    """Response model for application review history."""
    id: str
    supplier_id: str
    admin_id: str
    admin_name: str
    previous_status: SupplierStatus
    new_status: SupplierStatus
    notes: Optional[str] = None
    timestamp: datetime
    
    class Config:
        from_attributes = True
