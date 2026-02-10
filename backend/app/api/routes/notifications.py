"""Notification API routes."""
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from uuid import UUID

from ...api.deps import get_current_admin, get_current_vendor
from ...db.supabase import get_db, Database
from ...models.notification import (
    NotificationCreate,
    NotificationResponse,
    NotificationListResponse,
    NotificationStatsResponse,
    MarkReadRequest,
    BulkNotificationCreate,
    RecipientType,
    NotificationType,
    NOTIFICATION_TYPE_LABELS
)
from ...services.notifications import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/me", response_model=NotificationListResponse)
async def get_my_notifications(
    unread_only: bool = Query(False, description="Only return unread notifications"),
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: dict = Depends(get_current_vendor),
    db: Database = Depends(get_db)
):
    """
    Get notifications for the current user (vendor).
    """
    notification_service = NotificationService(db)
    
    result = await notification_service.get_user_notifications(
        recipient_id=UUID(current_user["id"]),
        recipient_type=RecipientType.VENDOR,
        unread_only=unread_only,
        limit=limit,
        offset=offset
    )
    
    return NotificationListResponse(
        items=[NotificationResponse(**item) for item in result["items"]],
        total=result["total"],
        unread_count=result["unread_count"],
        limit=limit,
        offset=offset
    )


@router.get("/admin/me", response_model=NotificationListResponse)
async def get_admin_notifications(
    unread_only: bool = Query(False, description="Only return unread notifications"),
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db)
):
    """
    Get notifications for the current admin.
    Admin only.
    """
    notification_service = NotificationService(db)
    
    result = await notification_service.get_user_notifications(
        recipient_id=UUID(current_admin["id"]),
        recipient_type=RecipientType.ADMIN,
        unread_only=unread_only,
        limit=limit,
        offset=offset
    )
    
    return NotificationListResponse(
        items=[NotificationResponse(**item) for item in result["items"]],
        total=result["total"],
        unread_count=result["unread_count"],
        limit=limit,
        offset=offset
    )


@router.get("/me/unread-count")
async def get_unread_count(
    current_user: dict = Depends(get_current_vendor),
    db: Database = Depends(get_db)
):
    """Get unread notification count for current vendor."""
    notification_service = NotificationService(db)
    count = await notification_service.get_unread_count(
        recipient_id=UUID(current_user["id"]),
        recipient_type=RecipientType.VENDOR
    )
    return {"unread_count": count}


@router.get("/admin/me/unread-count")
async def get_admin_unread_count(
    current_admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db)
):
    """Get unread notification count for current admin."""
    notification_service = NotificationService(db)
    count = await notification_service.get_unread_count(
        recipient_id=UUID(current_admin["id"]),
        recipient_type=RecipientType.ADMIN
    )
    return {"unread_count": count}


@router.get("/me/statistics", response_model=NotificationStatsResponse)
async def get_my_statistics(
    current_user: dict = Depends(get_current_vendor),
    db: Database = Depends(get_db)
):
    """Get notification statistics for current vendor."""
    notification_service = NotificationService(db)
    stats = await notification_service.get_statistics(
        recipient_id=UUID(current_user["id"]),
        recipient_type=RecipientType.VENDOR
    )
    return NotificationStatsResponse(**stats)


@router.get("/admin/me/statistics", response_model=NotificationStatsResponse)
async def get_admin_statistics(
    current_admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db)
):
    """Get notification statistics for current admin."""
    notification_service = NotificationService(db)
    stats = await notification_service.get_statistics(
        recipient_id=UUID(current_admin["id"]),
        recipient_type=RecipientType.ADMIN
    )
    return NotificationStatsResponse(**stats)


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: UUID,
    current_user: dict = Depends(get_current_vendor),
    db: Database = Depends(get_db)
):
    """Get a specific notification."""
    notification_service = NotificationService(db)
    notification = await notification_service.get_notification(notification_id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    # Verify ownership
    if str(notification.recipient_id) != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this notification"
        )
    
    return notification


@router.post("/mark-read")
async def mark_notifications_read(
    request: MarkReadRequest,
    current_user: dict = Depends(get_current_vendor),
    db: Database = Depends(get_db)
):
    """Mark specific notifications as read."""
    notification_service = NotificationService(db)
    
    # Verify ownership of all notifications
    for notification_id in request.notification_ids:
        notification = await notification_service.get_notification(notification_id)
        if notification and str(notification.recipient_id) != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify these notifications"
            )
    
    count = await notification_service.mark_as_read(request.notification_ids)
    return {"message": f"Marked {count} notifications as read", "count": count}


@router.post("/mark-all-read")
async def mark_all_read(
    current_user: dict = Depends(get_current_vendor),
    db: Database = Depends(get_db)
):
    """Mark all notifications as read for current vendor."""
    notification_service = NotificationService(db)
    count = await notification_service.mark_all_as_read(
        recipient_id=UUID(current_user["id"]),
        recipient_type=RecipientType.VENDOR
    )
    return {"message": f"Marked {count} notifications as read", "count": count}


@router.post("/admin/mark-all-read")
async def admin_mark_all_read(
    current_admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db)
):
    """Mark all notifications as read for current admin."""
    notification_service = NotificationService(db)
    count = await notification_service.mark_all_as_read(
        recipient_id=UUID(current_admin["id"]),
        recipient_type=RecipientType.ADMIN
    )
    return {"message": f"Marked {count} notifications as read", "count": count}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    current_user: dict = Depends(get_current_vendor),
    db: Database = Depends(get_db)
):
    """Delete a notification."""
    notification_service = NotificationService(db)
    
    # Verify ownership
    notification = await notification_service.get_notification(notification_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    if str(notification.recipient_id) != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this notification"
        )
    
    success = await notification_service.delete_notification(notification_id)
    if success:
        return {"message": "Notification deleted"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete notification"
        )


# Admin-only routes for creating notifications

@router.post("/admin/create", response_model=NotificationResponse)
async def create_notification(
    notification: NotificationCreate,
    current_admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db)
):
    """
    Create a notification.
    Admin only.
    """
    notification_service = NotificationService(db)
    return await notification_service.create_notification(notification)


@router.post("/admin/create-bulk")
async def create_bulk_notifications(
    bulk_notification: BulkNotificationCreate,
    current_admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db)
):
    """
    Create notifications for multiple recipients.
    Admin only.
    """
    notification_service = NotificationService(db)
    notifications = await notification_service.create_bulk_notifications(bulk_notification)
    return {
        "message": f"Created {len(notifications)} notifications",
        "count": len(notifications),
        "notifications": notifications
    }


@router.get("/admin/types")
async def get_notification_types(
    current_admin: dict = Depends(get_current_admin)
):
    """
    Get list of all notification types.
    Admin only.
    """
    return {
        "types": [
            {
                "value": nt.value,
                "label": NOTIFICATION_TYPE_LABELS.get(nt, nt.value)
            }
            for nt in NotificationType
        ]
    }


@router.post("/admin/cleanup")
async def cleanup_old_notifications(
    days_to_keep: int = Query(90, ge=1, le=365),
    current_admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db)
):
    """
    Clean up old read notifications.
    Admin only.
    """
    notification_service = NotificationService(db)
    count = await notification_service.cleanup_old_notifications(days_to_keep)
    return {"message": f"Cleaned up {count} old notifications", "count": count}
