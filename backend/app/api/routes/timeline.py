"""Timeline API routes"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID

from ..deps import get_current_vendor, get_current_admin
from ...models.timeline import TimelineResponse, TimelineEvent, ActivityLogCreate, StatusHistoryEvent
from ...db.supabase import db


router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("/vendor", response_model=TimelineResponse)
async def get_vendor_timeline(
    limit: int = 50,
    current_vendor: dict = Depends(get_current_vendor)
):
    """
    Get timeline for current vendor's application.
    Shows status changes, document updates, and key activities.
    """
    supplier_id = current_vendor["id"]
    
    try:
        # Get timeline events
        events_data = await db.get_supplier_timeline(supplier_id, limit)
        
        # Convert to TimelineEvent models
        events = [TimelineEvent(**event) for event in events_data]
        
        return TimelineResponse(
            events=events,
            total=len(events),
            supplier_id=UUID(supplier_id)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch timeline: {str(e)}"
        )


@router.get("/vendor/status-history", response_model=list[StatusHistoryEvent])
async def get_vendor_status_history(
    current_vendor: dict = Depends(get_current_vendor)
):
    """
    Get status change history for current vendor.
    Shows only application status transitions.
    """
    supplier_id = current_vendor["id"]
    
    try:
        history_data = await db.get_supplier_status_history(supplier_id)
        return [StatusHistoryEvent(**event) for event in history_data]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch status history: {str(e)}"
        )


@router.get("/admin/supplier/{supplier_id}", response_model=TimelineResponse)
async def get_supplier_timeline_admin(
    supplier_id: UUID,
    limit: int = 50,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Admin endpoint to view timeline for any supplier.
    """
    try:
        # Get timeline events
        events_data = await db.get_supplier_timeline(str(supplier_id), limit)
        
        # Convert to TimelineEvent models
        events = [TimelineEvent(**event) for event in events_data]
        
        return TimelineResponse(
            events=events,
            total=len(events),
            supplier_id=supplier_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch timeline: {str(e)}"
        )


@router.get("/admin/supplier/{supplier_id}/status-history", response_model=list[StatusHistoryEvent])
async def get_supplier_status_history_admin(
    supplier_id: UUID,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Admin endpoint to view status history for any supplier.
    """
    try:
        history_data = await db.get_supplier_status_history(str(supplier_id))
        return [StatusHistoryEvent(**event) for event in history_data]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch status history: {str(e)}"
        )


@router.post("/admin/log-activity")
async def log_activity_admin(
    activity: ActivityLogCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Admin endpoint to manually log a supplier activity.
    Useful for tracking offline interactions or custom events.
    """
    try:
        activity_id = await db.log_supplier_activity(
            supplier_id=str(activity.supplier_id),
            activity_type=activity.activity_type,
            activity_title=activity.activity_title,
            activity_description=activity.activity_description,
            actor_type=activity.actor_type,
            actor_id=str(activity.actor_id) if activity.actor_id else None,
            actor_name=activity.actor_name,
            metadata=activity.metadata
        )
        
        return {
            "message": "Activity logged successfully",
            "activity_id": activity_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log activity: {str(e)}"
        )
