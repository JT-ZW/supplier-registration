"""
User management Pydantic models for admin and vendor user management.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator

from .enums import AdminRole


# ============== Admin User Management ==============

class AdminUserCreateRequest(BaseModel):
    """Request model for creating a new admin user."""
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Initial password")
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name")
    role: AdminRole = Field(..., description="User role")
    phone: Optional[str] = Field(None, max_length=30, description="Phone number")
    department: Optional[str] = Field(None, max_length=100, description="Department")
    position: Optional[str] = Field(None, max_length=100, description="Position/Job title")
    must_change_password: bool = Field(True, description="Require password change on first login")
    
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


class AdminUserUpdateRequest(BaseModel):
    """Request model for updating an admin user."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    role: Optional[AdminRole] = None
    phone: Optional[str] = Field(None, max_length=30)
    department: Optional[str] = Field(None, max_length=100)
    position: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class AdminPasswordResetRequest(BaseModel):
    """Request model for admin to reset another user's password."""
    new_password: str = Field(..., min_length=8, description="New password")
    must_change_password: bool = Field(True, description="Require password change on next login")
    
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


class AdminUserResponse(BaseModel):
    """Response model for admin user."""
    id: str
    email: str
    full_name: str
    role: str
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    is_active: bool
    must_change_password: bool
    last_login: Optional[datetime] = None
    last_password_change: Optional[datetime] = None
    failed_login_attempts: int
    account_locked_until: Optional[datetime] = None
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    
    class Config:
        from_attributes = True


class AdminUserListResponse(BaseModel):
    """Response model for paginated admin user list."""
    items: List[AdminUserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============== Vendor User Management ==============

class VendorUserUpdateRequest(BaseModel):
    """Request model for admin to update vendor information."""
    company_name: Optional[str] = Field(None, max_length=200)
    contact_person: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=30)
    is_active: Optional[bool] = None


class VendorPasswordResetRequest(BaseModel):
    """Request model for admin to reset vendor password."""
    new_password: str = Field(..., min_length=8, description="New password")
    notify_vendor: bool = Field(True, description="Send email notification to vendor")
    
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


class VendorUserResponse(BaseModel):
    """Response model for vendor user in admin context."""
    id: str
    company_name: str
    contact_person: str
    email: str
    phone: str
    business_category: str
    status: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    total_documents: int = 0
    verified_documents: int = 0
    documents_complete: bool = False
    
    class Config:
        from_attributes = True


class VendorUserListResponse(BaseModel):
    """Response model for paginated vendor user list."""
    items: List[VendorUserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UnlockAccountRequest(BaseModel):
    """Request model for unlocking a locked account."""
    reset_failed_attempts: bool = Field(True, description="Reset failed login attempts counter")
