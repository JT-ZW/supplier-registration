"""
Profile change request API endpoints.
Handles vendor profile change requests and admin approvals.
Implements hybrid approach: some fields update directly, others require approval.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from pydantic import UUID4

from app.models.profile_change import (
    ProfileChangeRequest,
    ProfileChangeResponse,
    ProfileChangeReviewRequest,
    ProfileChangeListItem,
    ProfileChangeHistoryItem,
)
from app.models.profile_update import ProfileUpdateResponse
from app.db.supabase import db
from app.api.deps import get_current_admin, get_current_vendor
from app.services.audit import audit_service
from app.models.audit import AuditAction, AuditResourceType
from app.core.profile_permissions import validate_field_permissions, separate_changes_by_permission
from app.core.email import email_service, EmailTemplate
from app.core.config import settings
import json

router = APIRouter(prefix="/profile-changes", tags=["profile-changes"])


# ============================================================
# Helper Functions
# ============================================================

def parse_json_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse JSON string fields back to dictionaries."""
    if isinstance(data.get("requested_changes"), str):
        data["requested_changes"] = json.loads(data["requested_changes"])
    if isinstance(data.get("current_values"), str):
        data["current_values"] = json.loads(data["current_values"])
    return data


# ============================================================
# Vendor Endpoints
# ============================================================

@router.post("/vendor/request", response_model=ProfileUpdateResponse)
async def submit_profile_change_request(
    request: Request,
    change_request: ProfileChangeRequest,
    current_vendor: dict = Depends(get_current_vendor)
):
    """
    Submit profile changes as a vendor.
    Implements hybrid approach:
    - Direct update fields: applied immediately
    - Approval-required fields: create change request for admin review
    - Read-only fields: rejected with error
    
    Returns information about which changes were applied and which require approval.
    """
    try:
        supplier_id = current_vendor["id"]
        
        # Validate field permissions
        is_valid, error_msg, categorized = validate_field_permissions(
            change_request.requested_changes
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Get current supplier data
        current_supplier = await db.get_supplier_by_id(supplier_id)
        if not current_supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found"
            )
        
        # Initialize response data
        direct_updates_applied = 0
        approval_request_created = False
        change_request_id = None
        approval_request_data = None
        
        # Apply direct updates immediately
        if categorized["direct"]:
            update_result = await db.update_supplier(supplier_id, categorized["direct"])
            if update_result:
                direct_updates_applied = len(categorized["direct"])
                
                # Log direct updates
                await audit_service.log_action_from_request(
                    request=request,
                    action=AuditAction.SUPPLIER_UPDATED,
                    resource_type=AuditResourceType.SUPPLIER,
                    resource_id=supplier_id,
                    resource_name=current_supplier.get("company_name", ""),
                    current_user=current_vendor,
                    metadata={
                        "update_type": "direct",
                        "fields_updated": list(categorized["direct"].keys()),
                        "changes": categorized["direct"]
                    }
                )
        
        # Create approval request for sensitive fields
        if categorized["approval_required"]:
            # Build current values snapshot
            current_values = {}
            for field in categorized["approval_required"].keys():
                if field in current_supplier:
                    current_values[field] = current_supplier[field]
            
            # Cancel any pending requests for approval-required changes
            db.client.rpc("cancel_pending_profile_changes", {
                "p_supplier_id": supplier_id
            }).execute()
            
            # Create new approval request
            insert_result = db.client.table("profile_change_requests").insert({
                "supplier_id": supplier_id,
                "requested_changes": categorized["approval_required"],
                "current_values": current_values,
                "status": "PENDING"
            }).execute()
            
            if insert_result.data and len(insert_result.data) > 0:
                # Get the inserted record ID
                inserted_id = insert_result.data[0]["id"]
                
                # Fetch the complete record
                result = db.client.table("profile_change_requests")\
                    .select("*")\
                    .eq("id", inserted_id)\
                    .single()\
                    .execute()
                
                # Parse JSON fields before using
                parsed_data = parse_json_fields(result.data)
                approval_request_created = True
                change_request_id = parsed_data["id"]
                approval_request_data = parsed_data
                
                # Log approval request
                await audit_service.log_action_from_request(
                    request=request,
                    action=AuditAction.SUPPLIER_UPDATED,
                    resource_type=AuditResourceType.SUPPLIER,
                    resource_id=supplier_id,
                    resource_name=current_supplier.get("company_name", ""),
                    current_user=current_vendor,
                    metadata={
                        "update_type": "approval_request",
                        "change_request_id": str(parsed_data["id"]),
                        "fields_requested": list(categorized["approval_required"].keys()),
                        "requested_changes": categorized["approval_required"]
                    }
                )
                
                # Send email notification to admins
                try:
                    admin_emails = await db.get_active_admin_emails()
                    if admin_emails:
                        # Build field list HTML
                        field_list_html = "".join([
                            f"<li><strong>{field}</strong></li>"
                            for field in categorized["approval_required"].keys()
                        ])
                        
                        # Prepare email data
                        email_data = {
                            "supplier_name": current_supplier.get("company_name", "Unknown"),
                            "registration_number": current_supplier.get("registration_number", "N/A"),
                            "status": current_supplier.get("status", "PENDING"),
                            "submitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                            "supplier_id": supplier_id,
                            "field_list": field_list_html,
                            "review_link": f"{settings.FRONTEND_URL}/admin/supplier/{supplier_id}"
                        }
                        
                        # Send email to all active admins
                        print(f"Sending profile change notification to {len(admin_emails)} admin(s)...")
                        results = await email_service.send_bulk_emails(
                            recipients=admin_emails,
                            template=EmailTemplate.ADMIN_PROFILE_CHANGE_REQUEST,
                            common_data=email_data
                        )
                        
                        success_count = sum(1 for s in results.values() if s)
                        print(f"Profile change emails sent: {success_count}/{len(results)} successful")
                    else:
                        print("Warning: No active admin emails found for profile change notification")
                except Exception as email_error:
                    # Log email error but don't fail the request
                    import traceback
                    print(f"Failed to send profile change notification emails: {str(email_error)}")
                    print(f"Traceback: {traceback.format_exc()}")
        
        # Build success message
        message_parts = []
        if direct_updates_applied > 0:
            message_parts.append(f"{direct_updates_applied} field(s) updated immediately")
        if approval_request_created:
            message_parts.append(f"{len(categorized['approval_required'])} field(s) pending admin approval")
        
        message = "Profile update processed. " + ". ".join(message_parts) + "."
        
        return ProfileUpdateResponse(
            success=True,
            message=message,
            direct_updates_applied=direct_updates_applied,
            approval_request_created=approval_request_created,
            change_request_id=change_request_id,
            direct_fields=list(categorized["direct"].keys()),
            approval_required_fields=list(categorized["approval_required"].keys()),
            approval_request=approval_request_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process profile changes: {str(e)}"
        )


@router.get("/vendor/my-requests", response_model=List[ProfileChangeHistoryItem])
async def get_vendor_change_requests(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    current_vendor: dict = Depends(get_current_vendor)
):
    """Get all profile change requests for the current vendor."""
    try:
        result = db.client.rpc("get_profile_change_history", {
            "p_supplier_id": current_vendor["id"],
            "p_limit": limit
        }).execute()
        
        if not result.data:
            return []
        
        # Parse JSON fields in each item
        parsed_items = [parse_json_fields(item) for item in result.data]
        return [ProfileChangeHistoryItem(**item) for item in parsed_items]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch change requests: {str(e)}"
        )


@router.get("/vendor/pending", response_model=Optional[ProfileChangeResponse])
async def get_vendor_pending_request(
    request: Request,
    current_vendor: dict = Depends(get_current_vendor)
):
    """Get the current pending profile change request for the vendor."""
    try:
        result = db.client.table("profile_change_requests")\
            .select("*")\
            .eq("supplier_id", current_vendor["id"])\
            .eq("status", "PENDING")\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        
        if result.data:
            parsed_data = parse_json_fields(result.data[0])
            return ProfileChangeResponse(**parsed_data)
        return None
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending request: {str(e)}"
        )


# ============================================================
# Admin Endpoints
# ============================================================

@router.get("/admin/pending", response_model=List[ProfileChangeListItem])
async def get_pending_profile_changes(
    request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """Get all pending profile change requests (admin view)."""
    try:
        result = db.client.rpc("get_pending_profile_changes").execute()
        
        if not result.data:
            return []
        
        # Parse JSON fields in each item
        parsed_items = [parse_json_fields(item) for item in result.data]
        return [ProfileChangeListItem(**item) for item in parsed_items]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending changes: {str(e)}"
        )


@router.get("/admin/all", response_model=List[ProfileChangeResponse])
async def get_all_profile_changes(
    request: Request,
    status_filter: Optional[str] = Query(None, regex="^(PENDING|APPROVED|REJECTED|CANCELLED)$"),
    supplier_id: Optional[UUID4] = None,
    limit: int = Query(100, ge=1, le=500),
    current_admin: dict = Depends(get_current_admin)
):
    """Get all profile change requests with optional filters."""
    try:
        query = db.client.table("profile_change_requests").select("*")
        
        if status_filter:
            query = query.eq("status", status_filter)
        if supplier_id:
            query = query.eq("supplier_id", str(supplier_id))
        
        result = query.order("created_at", desc=True).limit(limit).execute()
        
        return [ProfileChangeResponse(**parse_json_fields(item)) for item in result.data] if result.data else []
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile changes: {str(e)}"
        )


@router.get("/admin/{request_id}", response_model=ProfileChangeResponse)
async def get_profile_change_detail(
    request: Request,
    request_id: UUID4,
    current_admin: dict = Depends(get_current_admin)
):
    """Get detailed information about a specific profile change request."""
    try:
        result = db.client.table("profile_change_requests")\
            .select("*")\
            .eq("id", str(request_id))\
            .single()\
            .execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile change request not found"
            )
        
        parsed_data = parse_json_fields(result.data)
        return ProfileChangeResponse(**parsed_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile change: {str(e)}"
        )


@router.post("/admin/{request_id}/review", response_model=ProfileChangeResponse)
async def review_profile_change(
    request: Request,
    request_id: UUID4,
    review: ProfileChangeReviewRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Approve or reject a profile change request.
    If approved, automatically applies changes to supplier record.
    Sends email notification to vendor.
    """
    try:
        # Get the change request
        change_request = db.client.table("profile_change_requests")\
            .select("*")\
            .eq("id", str(request_id))\
            .single()\
            .execute()
        
        if not change_request.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile change request not found"
            )
        
        if change_request.data["status"] != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot review request with status: {change_request.data['status']}"
            )
        
        # Update request status
        new_status = "APPROVED" if review.action == "approve" else "REJECTED"
        
        db.client.table("profile_change_requests").update({
            "status": new_status,
            "reviewed_by": current_admin["id"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "review_notes": review.review_notes
        }).eq("id", str(request_id)).execute()
        
        # Fetch the updated record
        update_result = db.client.table("profile_change_requests")\
            .select("*")\
            .eq("id", str(request_id))\
            .single()\
            .execute()
        
        if not update_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update request status"
            )
        
        # If approved, apply changes
        if review.action == "approve":
            try:
                db.client.rpc("apply_profile_changes", {
                    "p_request_id": str(request_id)
                }).execute()
            except Exception as e:
                # Rollback status change if apply fails
                db.client.table("profile_change_requests").update({
                    "status": "PENDING",
                    "reviewed_by": None,
                    "reviewed_at": None,
                    "review_notes": None
                }).eq("id", str(request_id)).execute()
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to apply profile changes: {str(e)}"
                )
        
        # Get supplier info for email
        supplier = await db.get_supplier_by_id(change_request.data["supplier_id"])
        
        # TODO: Send email notification
        # This will be implemented when we add email service
        # For now, we'll log it in the activity
        
        # Log audit action
        await audit_service.log_action_from_request(
            request=request,
            action=AuditAction.SUPPLIER_UPDATED if review.action == "approve" else AuditAction.SUPPLIER_REJECTED,
            resource_type=AuditResourceType.SUPPLIER,
            resource_id=change_request.data["supplier_id"],
            resource_name=supplier.get("company_name", "") if supplier else "",
            current_user=current_admin,
            metadata={
                "change_request_id": str(request_id),
                "action": review.action,
                "review_notes": review.review_notes,
                "requested_changes": change_request.data["requested_changes"]
            }
        )
        
        # Parse JSON fields if they're strings
        response_data = dict(update_result.data)
        if isinstance(response_data.get("requested_changes"), str):
            response_data["requested_changes"] = json.loads(response_data["requested_changes"])
        if isinstance(response_data.get("current_values"), str):
            response_data["current_values"] = json.loads(response_data["current_values"])
        
        return ProfileChangeResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to review profile change: {str(e)}"
        )


@router.get("/admin/supplier/{supplier_id}/history", response_model=List[ProfileChangeHistoryItem])
async def get_supplier_change_history(
    request: Request,
    supplier_id: UUID4,
    limit: int = Query(50, ge=1, le=100),
    current_admin: dict = Depends(get_current_admin)
):
    """Get profile change history for a specific supplier."""
    try:
        result = db.client.rpc("get_profile_change_history", {
            "p_supplier_id": str(supplier_id),
            "p_limit": limit
        }).execute()
        
        if not result.data:
            return []
        
        # Parse JSON fields in each item
        parsed_items = [parse_json_fields(item) for item in result.data]
        return [ProfileChangeHistoryItem(**item) for item in parsed_items]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch change history: {str(e)}"
        )
