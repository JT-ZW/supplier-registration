"""
Admin authentication and application review API routes.
These endpoints require admin authentication.
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4
from fastapi import APIRouter, HTTPException, status, Depends, Request, Query

from ...db.supabase import db
from ...models import (
    AdminLoginRequest,
    AdminCreateRequest,
    AdminPasswordChangeRequest,
    ApplicationReviewRequest,
    RequestMoreInfoRequest,
    RefreshTokenRequest,
    DocumentVerifyRequest,
    TokenResponse,
    AdminResponse,
    AdminProfileResponse,
    AuditLogListResponse,
    SupplierListResponse,
    SupplierResponse,
    SuccessResponse,
    SupplierStatus,
    DocumentVerificationStatus,
    AdminAction,
)
from ...api.deps import get_current_admin, PaginationParams, FilterParams, get_client_ip, get_user_agent
from ...core.security import (
    verify_password,
    hash_password,
    create_token_pair,
    verify_refresh_token,
)
from ...core.email import email_service, EmailTemplate
from ...core.config import settings


router = APIRouter(prefix="/admin", tags=["Admin"])


# ============== Authentication ==============

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Admin login",
    description="Authenticate admin user and receive JWT tokens."
)
async def login(request: AdminLoginRequest, http_request: Request):
    """Admin login endpoint."""
    # Get admin by email
    admin = await db.get_admin_by_email(request.email)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(request.password, admin["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if admin is active
    if not admin.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is deactivated"
        )
    
    # Update last login
    await db.update_admin(admin["id"], {
        "last_login": datetime.utcnow().isoformat()
    })
    
    # Create audit log
    await db.create_audit_log({
        "id": str(uuid4()),
        "admin_id": admin["id"],
        "admin_email": admin["email"],
        "action": AdminAction.LOGIN.value,
        "target_type": "admin",
        "target_id": admin["id"],
        "details": {"message": "Admin logged in", "user_agent": get_user_agent(http_request)},
        "ip_address": get_client_ip(http_request),
    })
    
    # Generate tokens
    tokens = create_token_pair(admin["id"], admin["email"])
    
    return TokenResponse(**tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get a new access token using a refresh token."
)
async def refresh_token(request: RefreshTokenRequest):
    """Refresh access token using refresh token."""
    payload = verify_refresh_token(request.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    admin_id = payload.get("sub")
    email = payload.get("email")
    
    if not admin_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Verify admin still exists and is active
    admin = await db.get_admin_by_id(admin_id)
    if not admin or not admin.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin account not found or deactivated"
        )
    
    # Generate new token pair
    tokens = create_token_pair(admin_id, email)
    
    return TokenResponse(**tokens)


@router.get(
    "/me",
    response_model=AdminResponse,
    summary="Get current admin profile",
    description="Get the authenticated admin user's profile."
)
async def get_current_admin_profile(current_admin: dict = Depends(get_current_admin)):
    """Get current admin user profile."""
    return AdminResponse(**current_admin)


@router.post(
    "/change-password",
    response_model=SuccessResponse,
    summary="Change password",
    description="Change the current admin user's password."
)
async def change_password(
    request: AdminPasswordChangeRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Change admin password."""
    # Verify current password
    if not verify_password(request.current_password, current_admin["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Hash new password
    new_hash = hash_password(request.new_password)
    
    # Update password
    await db.update_admin(current_admin["id"], {
        "password_hash": new_hash
    })
    
    return SuccessResponse(
        success=True,
        message="Password changed successfully"
    )


# ============== Supplier Application Management ==============

@router.get(
    "/suppliers",
    response_model=SupplierListResponse,
    summary="List supplier applications",
    description="Get paginated list of supplier applications with filtering."
)
async def list_suppliers(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    current_admin: dict = Depends(get_current_admin)
):
    """List supplier applications with pagination and filtering."""
    result = await db.list_suppliers(
        status=filters.status,
        category=filters.category,
        search=filters.search,
        page=pagination.page,
        page_size=pagination.page_size,
        order_by=filters.sort_by,
        ascending=filters.ascending,
    )
    
    return SupplierListResponse(**result)


@router.get(
    "/suppliers/{supplier_id}",
    response_model=SupplierResponse,
    summary="Get supplier application details",
    description="Get detailed information about a supplier application."
)
async def get_supplier_details(
    supplier_id: str,
    http_request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """Get supplier application details."""
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    # Create audit log
    await db.create_audit_log({
        "id": str(uuid4()),
        "admin_id": current_admin["id"],
        "admin_email": current_admin["email"],
        "action": AdminAction.VIEW_APPLICATION.value,
        "target_type": "supplier",
        "target_id": supplier_id,
        "details": {"message": f"Viewed application for {supplier['company_name']}"},
        "ip_address": get_client_ip(http_request),
    })
    
    return SupplierResponse(**supplier)


@router.post(
    "/suppliers/{supplier_id}/review",
    response_model=SuccessResponse,
    summary="Review supplier application",
    description="Approve, reject, or request more info for a supplier application."
)
async def review_application(
    supplier_id: str,
    request: ApplicationReviewRequest,
    http_request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """Review and update the status of a supplier application."""
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    previous_status = supplier["status"]
    new_status = request.action.value
    
    # Prepare update data
    update_data = {
        "status": new_status,
        "reviewed_at": datetime.utcnow().isoformat(),
        "reviewed_by": current_admin["id"],
        "updated_at": datetime.utcnow().isoformat(),
    }
    
    if request.notes:
        update_data["admin_notes"] = request.notes
    
    # Add specific fields based on action
    if request.action == SupplierStatus.REJECTED and request.notes:
        update_data["rejection_reason"] = request.notes
    
    # Update supplier
    await db.update_supplier(supplier_id, update_data)
    
    # Create review history record
    # (You may want to create a separate function for this)
    
    # Create audit log
    action_map = {
        SupplierStatus.APPROVED: AdminAction.APPROVE_APPLICATION,
        SupplierStatus.REJECTED: AdminAction.REJECT_APPLICATION,
        SupplierStatus.NEED_MORE_INFO: AdminAction.REQUEST_MORE_INFO,
        SupplierStatus.UNDER_REVIEW: AdminAction.VIEW_APPLICATION,
    }
    
    await db.create_audit_log({
        "id": str(uuid4()),
        "admin_id": current_admin["id"],
        "admin_email": current_admin["email"],
        "action": action_map.get(request.action, AdminAction.VIEW_APPLICATION).value,
        "target_type": "supplier",
        "target_id": supplier_id,
        "details": {"message": f"Changed status from {previous_status} to {new_status}", "notes": request.notes or None},
        "ip_address": get_client_ip(http_request),
    })
    
    # Send email notification
    try:
        if request.action == SupplierStatus.APPROVED:
            await email_service.send_template_email(
                to_email=supplier["email"],
                template=EmailTemplate.SUPPLIER_APPROVED,
                data={
                    "supplier_name": supplier["company_name"],
                    "contact_person": supplier["contact_person_name"],
                    "supplier_id": supplier_id,
                },
                to_name=supplier["contact_person_name"]
            )
        elif request.action == SupplierStatus.REJECTED:
            await email_service.send_template_email(
                to_email=supplier["email"],
                template=EmailTemplate.SUPPLIER_REJECTED,
                data={
                    "supplier_name": supplier["company_name"],
                    "contact_person": supplier["contact_person_name"],
                    "supplier_id": supplier_id,
                    "rejection_reason": request.notes or "No reason provided",
                },
                to_name=supplier["contact_person_name"]
            )
    except Exception as e:
        print(f"Failed to send email: {e}")
    
    return SuccessResponse(
        success=True,
        message=f"Application status updated to {new_status}"
    )


@router.post(
    "/suppliers/{supplier_id}/request-info",
    response_model=SuccessResponse,
    summary="Request more information",
    description="Request additional information or documents from supplier."
)
async def request_more_info(
    supplier_id: str,
    request: RequestMoreInfoRequest,
    http_request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """Request more information from a supplier."""
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    # Update supplier status
    update_data = {
        "status": SupplierStatus.NEED_MORE_INFO.value,
        "info_request_message": request.message,
        "reviewed_at": datetime.utcnow().isoformat(),
        "reviewed_by": current_admin["id"],
        "updated_at": datetime.utcnow().isoformat(),
    }
    
    await db.update_supplier(supplier_id, update_data)
    
    # Create audit log
    await db.create_audit_log({
        "id": str(uuid4()),
        "admin_id": current_admin["id"],
        "admin_email": current_admin["email"],
        "action": AdminAction.REQUEST_MORE_INFO.value,
        "target_type": "supplier",
        "target_id": supplier_id,
        "details": {"message": request.message},
        "ip_address": get_client_ip(http_request),
    })
    
    # Send email
    try:
        await email_service.send_template_email(
            to_email=supplier["email"],
            template=EmailTemplate.SUPPLIER_MORE_INFO_REQUESTED,
            data={
                "supplier_name": supplier["company_name"],
                "contact_person": supplier["contact_person_name"],
                "supplier_id": supplier_id,
                "request_message": request.message,
                "update_link": f"{settings.FRONTEND_URL}/register/{supplier_id}",
            },
            to_name=supplier["contact_person_name"]
        )
    except Exception as e:
        print(f"Failed to send email: {e}")
    
    return SuccessResponse(
        success=True,
        message="Request sent to supplier"
    )


# ============== Document Verification ==============

@router.post(
    "/documents/{document_id}/verify",
    response_model=SuccessResponse,
    summary="Verify or reject document",
    description="Admin can verify or reject an uploaded document."
)
async def verify_document(
    document_id: str,
    request: DocumentVerifyRequest,
    http_request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """Verify or reject a document."""
    document = await db.get_document_by_id(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Update document
    update_data = {
        "verification_status": request.status.value,
        "verified_at": datetime.utcnow().isoformat(),
        "verified_by": current_admin["id"],
    }
    
    if request.rejection_reason:
        update_data["rejection_reason"] = request.rejection_reason
    
    await db.update_document(document_id, update_data)
    
    # Create audit log
    action = (
        AdminAction.APPROVE_DOCUMENT
        if request.status == DocumentVerificationStatus.VERIFIED
        else AdminAction.REJECT_DOCUMENT
    )
    
    await db.create_audit_log({
        "id": str(uuid4()),
        "admin_id": current_admin["id"],
        "admin_email": current_admin["email"],
        "action": action.value,
        "target_type": "document",
        "target_id": document_id,
        "details": {"document_type": document['document_type'], "status": request.status.value, "supplier_id": document["supplier_id"]},
        "ip_address": get_client_ip(http_request),
    })
    
    return SuccessResponse(
        success=True,
        message=f"Document {request.status.value}"
    )


@router.delete(
    "/suppliers/{supplier_id}",
    response_model=SuccessResponse,
    summary="Delete supplier",
    description="Permanently delete a supplier and all associated documents."
)
async def delete_supplier(
    supplier_id: str,
    http_request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """Delete a supplier and all their documents."""
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    # Get all documents for this supplier
    documents = await db.get_documents_by_supplier(supplier_id)
    
    # Delete documents from storage (don't fail if files don't exist)
    from ...core.storage import storage_service
    for doc in documents:
        try:
            storage_service.delete_file(doc["s3_key"])
            print(f"✅ Deleted file: {doc['s3_key']}")
        except Exception as e:
            # Log but don't fail - file might not exist in storage
            print(f"⚠️ Could not delete file {doc['s3_key']}: {str(e)}")
    
    # Delete supplier from database (this will cascade delete documents due to foreign key)
    await db.delete_supplier(supplier_id)
    
    # Log the action
    await db.create_audit_log({
        "id": str(uuid4()),
        "admin_id": current_admin["id"],
        "admin_email": current_admin["email"],
        "action": AdminAction.DELETE_SUPPLIER.value,
        "target_type": "supplier",
        "target_id": supplier_id,
        "details": {"company_name": supplier["company_name"], "email": supplier["email"]},
        "ip_address": get_client_ip(http_request),
    })
    
    return SuccessResponse(
        success=True,
        message="Supplier deleted successfully"
    )


# ============== Audit Logs ==============

@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="Get audit logs",
    description="Get paginated list of audit logs."
)
async def get_audit_logs(
    pagination: PaginationParams = Depends(),
    supplier_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    current_admin: dict = Depends(get_current_admin)
):
    """Get audit logs with filtering."""
    result = await db.list_audit_logs(
        supplier_id=supplier_id,
        action=action,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    
    return AuditLogListResponse(**result)
