"""
Profile change request models.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, UUID4, Field


class ProfileChangeRequest(BaseModel):
    """Request model for submitting profile changes."""
    requested_changes: Dict[str, Any] = Field(
        ...,
        description="Dictionary of fields to change with new values"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "requested_changes": {
                    "company_name": "New Company Name Ltd",
                    "email": "newemail@company.com",
                    "phone": "+263 4 123456"
                }
            }
        }


class ProfileChangeResponse(BaseModel):
    """Response model for profile change requests."""
    id: UUID4
    supplier_id: UUID4
    requested_changes: Dict[str, Any]
    current_values: Dict[str, Any]
    status: str
    reviewed_by: Optional[UUID4] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProfileChangeReviewRequest(BaseModel):
    """Request model for admin to review profile changes."""
    action: str = Field(..., pattern="^(approve|reject)$")
    review_notes: Optional[str] = Field(
        None,
        description="Admin's notes or reason for the decision"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "action": "approve",
                "review_notes": "All information verified and approved"
            }
        }


class ProfileChangeListItem(BaseModel):
    """List item for profile change requests."""
    id: UUID4
    supplier_id: UUID4
    company_name: str
    email: str
    requested_changes: Dict[str, Any]
    current_values: Dict[str, Any]
    status: str
    created_at: datetime
    days_pending: Optional[int] = None
    
    class Config:
        from_attributes = True


class ProfileChangeHistoryItem(BaseModel):
    """History item for profile change requests."""
    id: UUID4
    requested_changes: Dict[str, Any]
    current_values: Dict[str, Any]
    status: str
    reviewed_by_name: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
