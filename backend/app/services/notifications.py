"""Notification service for creating and managing notifications."""
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID

from ..db.supabase import Database, get_db
from ..models.notification import (
    NotificationCreate,
    NotificationResponse,
    NotificationType,
    RecipientType,
    BulkNotificationCreate
)
from ..core.email import email_service, EmailTemplate


class NotificationService:
    """Service for managing notifications."""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def create_notification(
        self,
        notification: NotificationCreate
    ) -> NotificationResponse:
        """
        Create a new notification.
        
        Args:
            notification: Notification data
            
        Returns:
            Created notification
        """
        # Insert notification into database
        result = self.db.client.table("notifications").insert({
            "recipient_id": str(notification.recipient_id),
            "recipient_type": notification.recipient_type.value,
            "type": notification.type.value,
            "title": notification.title,
            "message": notification.message,
            "action_url": notification.action_url,
            "action_label": notification.action_label,
            "resource_type": notification.resource_type,
            "resource_id": str(notification.resource_id) if notification.resource_id else None,
            "metadata": notification.metadata,
            "send_email": notification.send_email,
            "expires_at": notification.expires_at.isoformat() if notification.expires_at else None
        }).execute()
        
        created_notification = NotificationResponse(**result.data[0])
        
        # Send email if requested
        if notification.send_email:
            asyncio.create_task(
                self._send_notification_email(created_notification, notification.metadata)
            )
        
        return created_notification
    
    async def create_bulk_notifications(
        self,
        bulk_notification: BulkNotificationCreate
    ) -> List[NotificationResponse]:
        """
        Create notifications for multiple recipients.
        
        Args:
            bulk_notification: Bulk notification data
            
        Returns:
            List of created notifications
        """
        notifications = []
        for recipient_id in bulk_notification.recipient_ids:
            notification = NotificationCreate(
                recipient_id=recipient_id,
                recipient_type=bulk_notification.recipient_type,
                type=bulk_notification.type,
                title=bulk_notification.title,
                message=bulk_notification.message,
                action_url=bulk_notification.action_url,
                action_label=bulk_notification.action_label,
                resource_type=bulk_notification.resource_type,
                resource_id=bulk_notification.resource_id,
                metadata=bulk_notification.metadata,
                send_email=bulk_notification.send_email,
                expires_at=bulk_notification.expires_at
            )
            created = await self.create_notification(notification)
            notifications.append(created)
        
        return notifications
    
    async def get_user_notifications(
        self,
        recipient_id: UUID,
        recipient_type: RecipientType,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get notifications for a user.
        
        Args:
            recipient_id: User ID
            recipient_type: User type (admin/vendor/supplier)
            unread_only: Only return unread notifications
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            Dictionary with items, total, and unread_count
        """
        query = self.db.client.table("notifications")\
            .select("*", count="exact")\
            .eq("recipient_id", str(recipient_id))\
            .eq("recipient_type", recipient_type.value)\
            .is_("deleted_at", "null")\
            .order("created_at", desc=True)\
            .range(offset, offset + limit - 1)
        
        if unread_only:
            query = query.eq("is_read", False)
        
        result = query.execute()
        
        # Get unread count
        unread_count = await self.get_unread_count(recipient_id, recipient_type)
        
        return {
            "items": result.data,
            "total": result.count,
            "unread_count": unread_count
        }
    
    async def get_notification(
        self,
        notification_id: UUID
    ) -> Optional[NotificationResponse]:
        """Get a single notification by ID."""
        result = self.db.client.table("notifications")\
            .select("*")\
            .eq("id", str(notification_id))\
            .is_("deleted_at", "null")\
            .maybe_single()\
            .execute()
        
        if result.data:
            return NotificationResponse(**result.data)
        return None
    
    async def mark_as_read(
        self,
        notification_ids: List[UUID]
    ) -> int:
        """
        Mark notifications as read.
        
        Args:
            notification_ids: List of notification IDs
            
        Returns:
            Number of notifications marked as read
        """
        result = self.db.client.rpc(
            "mark_notifications_read",
            {"p_notification_ids": [str(nid) for nid in notification_ids]}
        ).execute()
        
        return result.data if result.data else 0
    
    async def mark_all_as_read(
        self,
        recipient_id: UUID,
        recipient_type: RecipientType
    ) -> int:
        """
        Mark all notifications as read for a user.
        
        Args:
            recipient_id: User ID
            recipient_type: User type
            
        Returns:
            Number of notifications marked as read
        """
        result = self.db.client.rpc(
            "mark_all_read",
            {
                "p_recipient_id": str(recipient_id),
                "p_recipient_type": recipient_type.value
            }
        ).execute()
        
        return result.data if result.data else 0
    
    async def delete_notification(
        self,
        notification_id: UUID
    ) -> bool:
        """
        Soft delete a notification.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            True if deleted successfully
        """
        result = self.db.client.table("notifications")\
            .update({"deleted_at": datetime.utcnow().isoformat()})\
            .eq("id", str(notification_id))\
            .execute()
        
        return len(result.data) > 0
    
    async def get_unread_count(
        self,
        recipient_id: UUID,
        recipient_type: RecipientType
    ) -> int:
        """
        Get count of unread notifications for a user.
        
        Args:
            recipient_id: User ID
            recipient_type: User type
            
        Returns:
            Count of unread notifications
        """
        result = self.db.client.rpc(
            "get_unread_count",
            {
                "p_recipient_id": str(recipient_id),
                "p_recipient_type": recipient_type.value
            }
        ).execute()
        
        return result.data if result.data else 0
    
    async def get_statistics(
        self,
        recipient_id: UUID,
        recipient_type: RecipientType
    ) -> Dict[str, Any]:
        """
        Get notification statistics for a user.
        
        Args:
            recipient_id: User ID
            recipient_type: User type
            
        Returns:
            Dictionary with statistics
        """
        # Get total count
        total_result = self.db.client.table("notifications")\
            .select("*", count="exact")\
            .eq("recipient_id", str(recipient_id))\
            .eq("recipient_type", recipient_type.value)\
            .is_("deleted_at", "null")\
            .execute()
        
        # Get unread count
        unread_count = await self.get_unread_count(recipient_id, recipient_type)
        
        # Get count by type
        type_result = self.db.client.table("notifications")\
            .select("type")\
            .eq("recipient_id", str(recipient_id))\
            .eq("recipient_type", recipient_type.value)\
            .is_("deleted_at", "null")\
            .execute()
        
        by_type = {}
        for item in type_result.data:
            notification_type = item["type"]
            by_type[notification_type] = by_type.get(notification_type, 0) + 1
        
        # Get recent count (last 24 hours)
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        recent_result = self.db.client.table("notifications")\
            .select("*", count="exact")\
            .eq("recipient_id", str(recipient_id))\
            .eq("recipient_type", recipient_type.value)\
            .is_("deleted_at", "null")\
            .gte("created_at", yesterday)\
            .execute()
        
        return {
            "total_notifications": total_result.count,
            "unread_count": unread_count,
            "by_type": by_type,
            "recent_count": recent_result.count
        }
    
    async def cleanup_old_notifications(
        self,
        days_to_keep: int = 90
    ) -> int:
        """
        Delete old read notifications.
        
        Args:
            days_to_keep: Number of days to keep read notifications
            
        Returns:
            Number of notifications deleted
        """
        result = self.db.client.rpc(
            "cleanup_old_notifications",
            {"p_days_to_keep": days_to_keep}
        ).execute()
        
        return result.data if result.data else 0
    
    async def expire_old_notifications(self) -> None:
        """Expire notifications that have passed their expiration date."""
        self.db.client.rpc("expire_old_notifications").execute()
    
    async def _send_notification_email(
        self,
        notification: NotificationResponse,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Send email for a notification.
        
        Args:
            notification: Notification to send
            metadata: Additional metadata for email
        """
        try:
            # Get recipient email from metadata or fetch from database
            recipient_email = metadata.get("email")
            recipient_name = metadata.get("name")
            
            if not recipient_email:
                # Could fetch from suppliers or admins table based on recipient_type
                return
            
            # Map notification type to email template
            template_map = {
                NotificationType.SUPPLIER_STATUS_CHANGE: EmailTemplate.SUPPLIER_APPROVED,  # Will vary based on status
                NotificationType.DOCUMENT_VERIFICATION: EmailTemplate.ADMIN_DOCUMENT_UPLOADED,
                NotificationType.APPLICATION_SUBMITTED: EmailTemplate.ADMIN_APPLICATION_SUBMITTED,
            }
            
            email_template = template_map.get(notification.type)
            if not email_template:
                # Send generic notification email
                await email_service.send_email(
                    to_email=recipient_email,
                    subject=notification.title,
                    html_content=f"<p>{notification.message}</p>",
                    to_name=recipient_name
                )
            else:
                # Send template email
                await email_service.send_template_email(
                    to_email=recipient_email,
                    template=email_template,
                    data=metadata,
                    to_name=recipient_name
                )
            
            # Mark email as sent
            self.db.client.table("notifications")\
                .update({
                    "email_sent": True,
                    "email_sent_at": datetime.utcnow().isoformat()
                })\
                .eq("id", str(notification.id))\
                .execute()
                
        except Exception as e:
            print(f"Error sending notification email: {str(e)}")
    
    # Helper methods for creating specific notification types
    
    async def notify_supplier_status_change(
        self,
        supplier_id: UUID,
        supplier_name: str,
        supplier_email: str,
        contact_person: str,
        old_status: str,
        new_status: str,
        comments: Optional[str] = None
    ) -> NotificationResponse:
        """Create notification for supplier status change."""
        status_messages = {
            "approved": f"Congratulations! Your application for {supplier_name} has been approved.",
            "rejected": f"Your application for {supplier_name} has been reviewed. Please check your email for details.",
            "more_info_required": f"Additional information is required for your application for {supplier_name}.",
        }
        
        message = status_messages.get(new_status, f"Your supplier status has changed to {new_status}.")
        if comments:
            message += f" Comments: {comments}"
        
        return await self.create_notification(NotificationCreate(
            recipient_id=supplier_id,
            recipient_type=RecipientType.VENDOR,
            type=NotificationType.SUPPLIER_STATUS_CHANGE,
            title="Application Status Update",
            message=message,
            action_url=f"/vendor/dashboard",
            action_label="View Dashboard",
            resource_type="supplier",
            resource_id=supplier_id,
            metadata={
                "old_status": old_status,
                "new_status": new_status,
                "supplier_name": supplier_name,
                "email": supplier_email,
                "name": contact_person,
                "comments": comments
            },
            send_email=True
        ))
    
    async def notify_document_verified(
        self,
        supplier_id: UUID,
        document_type: str,
        verification_status: str,
        metadata: Dict[str, Any]
    ) -> NotificationResponse:
        """Create notification for document verification."""
        status_text = "verified" if verification_status == "verified" else "requires attention"
        
        return await self.create_notification(NotificationCreate(
            recipient_id=supplier_id,
            recipient_type=RecipientType.VENDOR,
            type=NotificationType.DOCUMENT_VERIFICATION,
            title=f"Document {status_text.title()}",
            message=f"Your {document_type} has been {status_text}.",
            action_url=f"/vendor/documents",
            action_label="View Documents",
            resource_type="document",
            resource_id=metadata.get("document_id"),
            metadata=metadata,
            send_email=verification_status != "verified"  # Only email if not verified
        ))
    
    async def notify_admins_application_submitted(
        self,
        admin_ids: List[UUID],
        supplier_id: UUID,
        supplier_name: str,
        category: str,
        metadata: Dict[str, Any]
    ) -> List[NotificationResponse]:
        """Notify all admins of new application submission."""
        bulk_notification = BulkNotificationCreate(
            recipient_ids=admin_ids,
            recipient_type=RecipientType.ADMIN,
            type=NotificationType.APPLICATION_SUBMITTED,
            title="New Supplier Application",
            message=f"{supplier_name} has submitted an application for review ({category}).",
            action_url=f"/admin/supplier/{supplier_id}",
            action_label="Review Application",
            resource_type="supplier",
            resource_id=supplier_id,
            metadata=metadata,
            send_email=True
        )
        
        return await self.create_bulk_notifications(bulk_notification)


def get_notification_service(db: Database = None) -> NotificationService:
    """Get notification service instance."""
    if db is None:
        from ..db.supabase import get_db
        db = next(get_db())
    return NotificationService(db)
