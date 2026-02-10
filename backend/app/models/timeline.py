"""Timeline models for supplier application tracking"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    """Timeline event model"""
    id: UUID
    event_type: str
    event_title: str
    event_description: str
    actor_type: str
    actor_name: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    
    class Config:
        from_attributes = True


class StatusHistoryEvent(BaseModel):
    """Status history event model"""
    id: UUID
    old_status: Optional[str]
    new_status: str
    changed_by_type: str
    changed_by_name: str
    reason: Optional[str]
    admin_notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class TimelineResponse(BaseModel):
    """Timeline response model"""
    events: List[TimelineEvent]
    total: int
    supplier_id: UUID
    

class ActivityLogCreate(BaseModel):
    """Model for creating activity log entries"""
    supplier_id: UUID
    activity_type: str
    activity_title: str
    activity_description: Optional[str] = None
    actor_type: str
    actor_id: Optional[UUID] = None
    actor_name: str
    metadata: dict = Field(default_factory=dict)
