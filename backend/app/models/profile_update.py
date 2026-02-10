"""
Additional models for hybrid profile change response.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, UUID4


class ProfileUpdateResponse(BaseModel):
    """Response for hybrid profile update submissions."""
    success: bool
    message: str
    direct_updates_applied: int
    approval_request_created: bool
    change_request_id: Optional[UUID4] = None
    direct_fields: List[str]
    approval_required_fields: List[str]
    approval_request: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Profile update processed. 3 fields updated immediately. 2 fields pending admin approval.",
                "direct_updates_applied": 3,
                "approval_request_created": True,
                "change_request_id": "123e4567-e89b-12d3-a456-426614174000",
                "direct_fields": ["phone", "contact_person", "website"],
                "approval_required_fields": ["company_name", "email"],
                "approval_request": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "status": "PENDING"
                }
            }
        }
