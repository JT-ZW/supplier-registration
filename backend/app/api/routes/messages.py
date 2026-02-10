"""
Message API endpoints for admin-vendor communication.
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from pydantic import UUID4

from app.models.message import (
    MessageCreate,
    MessageResponse,
    ThreadCreate,
    ThreadSummary,
    ThreadDetail,
    ThreadUpdate,
    ThreadListResponse,
    MarkAsReadRequest,
    UnreadCountResponse,
    BulkMessageRequest,
    BulkMessageResponse,
    MessageCategory,
    SenderType
)
from app.db.supabase import db
from app.api.deps import get_current_admin, get_current_vendor
from app.services.audit import audit_service
from app.models.audit import AuditAction, AuditResourceType
from app.core.email import email_service, EmailTemplate
from app.core.config import settings

router = APIRouter(prefix="/messages", tags=["messages"])


# ============================================================
# Helper Functions
# ============================================================

def parse_json_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse JSON string fields to Python objects.
    Supabase returns JSONB columns as JSON strings, but Pydantic expects dicts/lists.
    """
    if not data:
        return data
    
    parsed = data.copy()
    json_fields = ['attachments']  # Fields that are JSONB in the database
    
    for field in json_fields:
        if field in parsed and isinstance(parsed[field], str):
            try:
                parsed[field] = json.loads(parsed[field])
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, keep the original value or default to empty list
                parsed[field] = []
    
    return parsed


# ============================================================
# Vendor Endpoints
# ============================================================

@router.get("/vendor/threads", response_model=ThreadListResponse)
async def get_vendor_threads(
    request: Request,
    is_archived: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_vendor: dict = Depends(get_current_vendor)
):
    """Get message threads for the authenticated vendor."""
    try:
        result = await db.get_threads_for_supplier(
            supplier_id=current_vendor["id"],
            is_archived=is_archived,
            page=page,
            page_size=page_size
        )
        
        total_pages = (result["total"] + page_size - 1) // page_size
        
        return ThreadListResponse(
            threads=result["threads"],
            total=result["total"],
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch threads: {str(e)}"
        )


@router.get("/vendor/thread/{thread_id}", response_model=ThreadDetail)
async def get_vendor_thread_detail(
    request: Request,
    thread_id: UUID4,
    current_vendor: dict = Depends(get_current_vendor)
):
    """Get detailed thread information with all messages."""
    try:
        # Get thread details
        thread = await db.get_thread_by_id(str(thread_id))
        
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread not found"
            )
        
        # Verify vendor has access to this thread
        if thread["supplier_id"] != current_vendor["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get all messages
        messages = await db.get_thread_messages(str(thread_id))
        
        # Parse JSON fields in messages
        parsed_messages = [parse_json_fields(msg) for msg in messages]
        
        # Mark messages as read
        await db.mark_thread_as_read(str(thread_id), "vendor")
        
        return ThreadDetail(
            **thread,
            messages=parsed_messages
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch thread: {str(e)}"
        )


@router.post("/vendor/thread", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_vendor_thread(
    request: Request,
    thread_data: ThreadCreate,
    current_vendor: dict = Depends(get_current_vendor)
):
    """Create a new message thread as vendor."""
    try:
        # Verify the vendor is creating thread for themselves
        if str(thread_data.supplier_id) != current_vendor["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only create threads for your own account"
            )
        
        thread = await db.create_message_thread(
            subject=thread_data.subject,
            supplier_id=str(thread_data.supplier_id),
            category_id=str(thread_data.category_id) if thread_data.category_id else None,
            priority=thread_data.priority.value,
            sender_type="vendor",
            sender_id=current_vendor["id"],
            sender_name=current_vendor.get("company_name", "Vendor"),
            message_text=thread_data.initial_message
        )
        
        # Audit log
        await audit_service.log_action_from_request(
            request=request,
            action=AuditAction.MESSAGE_SENT,
            resource_type=AuditResourceType.MESSAGE,
            resource_id=thread["id"],
            resource_name=thread_data.subject,
            current_user=current_vendor,
            metadata={"thread_created": True}
        )
        
        # Send email notification to admin about new thread
        try:
            message_preview = thread_data.initial_message[:200] + ("..." if len(thread_data.initial_message) > 200 else "")
            await email_service.send_template_email(
                to_email=settings.ADMIN_EMAIL,
                template=EmailTemplate.ADMIN_NEW_MESSAGE,
                data={
                    "supplier_name": current_vendor.get("company_name", "Vendor"),
                    "thread_subject": thread_data.subject,
                    "message_preview": message_preview,
                    "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "message_link": f"{settings.FRONTEND_URL}/admin/messages?thread={thread['id']}"
                },
                to_name="Admin"
            )
        except Exception as e:
            # Don't fail the request if email fails
            print(f"Failed to send email notification: {str(e)}")
        
        return {"message": "Thread created successfully", "thread": thread}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create thread: {str(e)}"
        )


@router.post("/vendor/message", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_vendor_message(
    request: Request,
    message_data: MessageCreate,
    current_vendor: dict = Depends(get_current_vendor)
):
    """Send a message in an existing thread as vendor."""
    try:
        if not message_data.thread_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="thread_id is required"
            )
        
        # Verify vendor has access to this thread
        thread = await db.get_thread_by_id(str(message_data.thread_id))
        
        if not thread or thread["supplier_id"] != current_vendor["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Add message
        message = await db.add_message_to_thread(
            thread_id=str(message_data.thread_id),
            sender_type="vendor",
            sender_id=current_vendor["id"],
            sender_name=current_vendor.get("company_name", "Vendor"),
            message_text=message_data.message_text,
            attachments=message_data.attachments
        )
        
        # Audit log
        await audit_service.log_action_from_request(
            request=request,
            action=AuditAction.MESSAGE_SENT,
            resource_type=AuditResourceType.MESSAGE,
            resource_id=message["id"],
            resource_name=thread["subject"],
            current_user=current_vendor,
            metadata={"thread_id": str(message_data.thread_id)}
        )
        
        # Send email notification to admin
        try:
            message_preview = message_data.message_text[:200] + ("..." if len(message_data.message_text) > 200 else "")
            await email_service.send_template_email(
                to_email=settings.ADMIN_EMAIL,
                template=EmailTemplate.ADMIN_NEW_MESSAGE,
                data={
                    "supplier_name": current_vendor.get("company_name", "Vendor"),
                    "thread_subject": thread["subject"],
                    "message_preview": message_preview,
                    "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "message_link": f"{settings.FRONTEND_URL}/admin/messages?thread={message_data.thread_id}"
                },
                to_name="Admin"
            )
        except Exception as e:
            # Don't fail the request if email fails
            print(f"Failed to send email notification: {str(e)}")
        
        return MessageResponse(**parse_json_fields(message))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )


@router.get("/vendor/unread-count", response_model=dict)
async def get_vendor_unread_count(
    request: Request,
    current_vendor: dict = Depends(get_current_vendor)
):
    """Get unread message count for vendor."""
    try:
        count = await db.get_unread_count(current_vendor["id"], "vendor")
        return {"unread_count": count}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch unread count: {str(e)}"
        )


# ============================================================
# Admin Endpoints
# ============================================================

@router.get("/admin/threads", response_model=ThreadListResponse)
async def get_admin_threads(
    request: Request,
    is_archived: Optional[bool] = Query(None),
    category_id: Optional[UUID4] = Query(None),
    priority: Optional[str] = Query(None),
    has_unread: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_admin: dict = Depends(get_current_admin)
):
    """Get all message threads for admin."""
    try:
        result = await db.get_all_threads(
            is_archived=is_archived,
            category_id=str(category_id) if category_id else None,
            priority=priority,
            has_unread=has_unread,
            page=page,
            page_size=page_size
        )
        
        total_pages = (result["total"] + page_size - 1) // page_size
        
        return ThreadListResponse(
            threads=result["threads"],
            total=result["total"],
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch threads: {str(e)}"
        )


@router.get("/admin/thread/{thread_id}", response_model=ThreadDetail)
async def get_admin_thread_detail(
    request: Request,
    thread_id: UUID4,
    current_admin: dict = Depends(get_current_admin)
):
    """Get detailed thread information for admin."""
    try:
        thread = await db.get_thread_by_id(str(thread_id))
        
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread not found"
            )
        
        messages = await db.get_thread_messages(str(thread_id))
        
        # Parse JSON fields in messages
        parsed_messages = [parse_json_fields(msg) for msg in messages]
        
        # Mark messages as read for admin
        await db.mark_thread_as_read(str(thread_id), "admin")
        
        return ThreadDetail(
            **thread,
            messages=parsed_messages
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch thread: {str(e)}"
        )


@router.post("/admin/thread", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_admin_thread(
    request: Request,
    thread_data: ThreadCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """Create a new message thread as admin."""
    try:
        thread = await db.create_message_thread(
            subject=thread_data.subject,
            supplier_id=str(thread_data.supplier_id),
            category_id=str(thread_data.category_id) if thread_data.category_id else None,
            priority=thread_data.priority.value,
            sender_type="admin",
            sender_id=current_admin["id"],
            sender_name=current_admin.get("email", "Admin"),
            message_text=thread_data.initial_message
        )
        
        # Audit log
        await audit_service.log_action_from_request(
            request=request,
            action=AuditAction.MESSAGE_SENT,
            resource_type=AuditResourceType.MESSAGE,
            resource_id=thread["id"],
            resource_name=thread_data.subject,
            current_user=current_admin,
            metadata={"thread_created": True, "supplier_id": str(thread_data.supplier_id)}
        )
        
        # Send email notification to vendor about new thread
        try:
            supplier = await db.get_supplier_by_id(str(thread_data.supplier_id))
            if supplier and supplier.get("email"):
                message_preview = thread_data.initial_message[:200] + ("..." if len(thread_data.initial_message) > 200 else "")
                await email_service.send_template_email(
                    to_email=supplier["email"],
                    template=EmailTemplate.VENDOR_MESSAGE_REPLY,
                    data={
                        "contact_person": supplier.get("contact_person_name", "Vendor"),
                        "thread_subject": thread_data.subject,
                        "message_preview": message_preview,
                        "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "message_link": f"{settings.FRONTEND_URL}/vendor/messages?thread={thread['id']}"
                    },
                    to_name=supplier.get("contact_person_name")
                )
        except Exception as e:
            # Don't fail the request if email fails
            print(f"Failed to send email notification: {str(e)}")
        
        return {"message": "Thread created successfully", "thread": thread}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create thread: {str(e)}"
        )


@router.post("/admin/message", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_admin_message(
    request: Request,
    message_data: MessageCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """Send a message as admin."""
    try:
        if not message_data.thread_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="thread_id is required"
            )
        
        thread = await db.get_thread_by_id(str(message_data.thread_id))
        
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread not found"
            )
        
        message = await db.add_message_to_thread(
            thread_id=str(message_data.thread_id),
            sender_type="admin",
            sender_id=current_admin["id"],
            sender_name=current_admin.get("email", "Admin"),
            message_text=message_data.message_text,
            attachments=message_data.attachments
        )
        
        # Audit log
        await audit_service.log_action_from_request(
            request=request,
            action=AuditAction.MESSAGE_SENT,
            resource_type=AuditResourceType.MESSAGE,
            resource_id=message["id"],
            resource_name=thread["subject"],
            current_user=current_admin,
            metadata={"thread_id": str(message_data.thread_id), "supplier_id": thread["supplier_id"]}
        )
        
        # Send email notification to vendor
        try:
            # Get supplier details for email
            supplier = await db.get_supplier_by_id(thread["supplier_id"])
            if supplier and supplier.get("email"):
                message_preview = message_data.message_text[:200] + ("..." if len(message_data.message_text) > 200 else "")
                await email_service.send_template_email(
                    to_email=supplier["email"],
                    template=EmailTemplate.VENDOR_MESSAGE_REPLY,
                    data={
                        "contact_person": supplier.get("contact_person_name", "Vendor"),
                        "thread_subject": thread["subject"],
                        "message_preview": message_preview,
                        "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "message_link": f"{settings.FRONTEND_URL}/vendor/messages?thread={message_data.thread_id}"
                    },
                    to_name=supplier.get("contact_person_name")
                )
        except Exception as e:
            # Don't fail the request if email fails
            print(f"Failed to send email notification: {str(e)}")
        
        return MessageResponse(**parse_json_fields(message))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )


@router.post("/admin/bulk-message", response_model=BulkMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_bulk_admin_message(
    request: Request,
    bulk_data: BulkMessageRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Send a message to multiple suppliers at once."""
    try:
        thread_ids = []
        errors = []
        success_count = 0
        
        for supplier_id in bulk_data.supplier_ids:
            try:
                thread = await db.create_message_thread(
                    subject=bulk_data.subject,
                    supplier_id=str(supplier_id),
                    category_id=str(bulk_data.category_id) if bulk_data.category_id else None,
                    priority=bulk_data.priority.value,
                    sender_type="admin",
                    sender_id=current_admin["id"],
                    sender_name=current_admin.get("email", "Admin"),
                    message_text=bulk_data.message_text
                )
                thread_ids.append(thread["id"])
                success_count += 1
            except Exception as e:
                errors.append({
                    "supplier_id": str(supplier_id),
                    "error": str(e)
                })
        
        # Audit log
        await audit_service.log_action_from_request(
            request=request,
            action=AuditAction.MESSAGE_SENT,
            resource_type=AuditResourceType.MESSAGE,
            resource_name=f"Bulk: {bulk_data.subject}",
            current_user=current_admin,
            metadata={
                "bulk_message": True,
                "success_count": success_count,
                "failed_count": len(errors),
                "supplier_count": len(bulk_data.supplier_ids)
            }
        )
        
        return BulkMessageResponse(
            success_count=success_count,
            failed_count=len(errors),
            thread_ids=thread_ids,
            errors=errors if errors else None
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send bulk messages: {str(e)}"
        )


@router.patch("/admin/thread/{thread_id}", response_model=dict)
async def update_admin_thread(
    request: Request,
    thread_id: UUID4,
    update_data: ThreadUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """Update thread properties (subject, category, priority, archive status)."""
    try:
        updates = {k: v for k, v in update_data.dict(exclude_unset=True).items() if v is not None}
        
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update data provided"
            )
        
        thread = await db.update_thread(str(thread_id), updates)
        
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread not found"
            )
        
        # Audit log
        await audit_service.log_action_from_request(
            request=request,
            action=AuditAction.MESSAGE_UPDATED,
            resource_type=AuditResourceType.MESSAGE,
            resource_id=str(thread_id),
            resource_name=thread.get("subject", "Thread"),
            current_user=current_admin,
            changes=updates
        )
        
        return {"message": "Thread updated successfully", "thread": thread}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update thread: {str(e)}"
        )


@router.get("/admin/unread-count", response_model=dict)
async def get_admin_unread_count(
    request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """Get total unread message count for admin."""
    try:
        count = await db.get_unread_count(current_admin["id"], "admin")
        return {"unread_count": count}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch unread count: {str(e)}"
        )


# ============================================================
# Shared Endpoints
# ============================================================

@router.get("/categories", response_model=List[MessageCategory])
async def get_message_categories():
    """Get all message categories."""
    try:
        categories = await db.get_message_categories()
        return categories
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch categories: {str(e)}"
        )
