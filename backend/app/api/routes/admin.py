"""
Admin authentication and application review API routes.
These endpoints require admin authentication.
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4
import asyncio
from fastapi import APIRouter, HTTPException, status, Depends, Request, Query, Body

from ...db.supabase import db
from ...services.audit_service import audit_service, AuditAction
from ...api.deps import get_client_ip
from ...models import (
    AdminLoginRequest,
    AdminCreateRequest,
    AdminPasswordChangeRequest,
    ApplicationReviewRequest,
    RequestMoreInfoRequest,
    RefreshTokenRequest,
    DocumentVerifyRequest,
    DocumentUploadRequest,
    DocumentMetadataCreateRequest,
    PresignedUrlResponse,
    TokenResponse,
    AdminResponse,
    AdminProfileResponse,
    AuditLogListResponse,
    SupplierListResponse,
    SupplierResponse,
    SuccessResponse,
    SupplierStatus,
    DocumentVerificationStatus,
    DocumentType,
    AdminAction,
)
from ...models.audit import AuditAction, AuditResourceType
from ...api.deps import get_current_admin, PaginationParams, FilterParams, get_client_ip, get_user_agent
from ...core.security import (
    verify_password,
    hash_password,
    create_token_pair,
    verify_refresh_token,
)
from ...core.email import email_service, EmailTemplate
from ...core.config import settings
from ...core.storage import storage_service


router = APIRouter(prefix="/admin", tags=["Admin"])


# ============== Helper Functions ==============

async def check_evaluation_form_exists(supplier_id: str) -> bool:
    """Check if evaluation form has been uploaded for a supplier."""
    documents = await db.get_documents_by_supplier(supplier_id)
    for doc in documents:
        if doc.get("document_type") == DocumentType.EVALUATION_FORM.value:
            return True
    return False


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
        # Log failed login attempt
        audit_service.log_login(
            admin_id=admin["id"],
            admin_email=admin["email"],
            ip_address=get_client_ip(http_request),
            success=False
        )
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
    
    # Log successful login
    audit_service.log_login(
        admin_id=admin["id"],
        admin_email=admin["email"],
        ip_address=get_client_ip(http_request),
        success=True
    )
    
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
    description="Get paginated list of supplier applications with advanced filtering."
)
async def list_suppliers(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    current_admin: dict = Depends(get_current_admin)
):
    """List supplier applications with pagination and advanced filtering."""
    result = await db.list_suppliers(
        status=filters.status,
        category=filters.category,
        search=filters.search,
        company_name=filters.company_name,
        email=filters.email,
        contact_person=filters.contact_person,
        registration_number=filters.registration_number,
        tax_id=filters.tax_id,
        phone=filters.phone,
        city=filters.city,
        country=filters.country,
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
    
    # Log vendor view with new audit service
    await audit_service.log_vendor_action(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=AuditAction.SUPPLIER_VIEWED,
        vendor_id=supplier_id,
        vendor_name=supplier['company_name'],
        details={"view_timestamp": datetime.utcnow().isoformat()},
        ip_address=get_client_ip(http_request)
    )
    
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
    
    # **NEW: Check if evaluation form is uploaded before allowing approval/rejection**
    if request.action in [SupplierStatus.APPROVED, SupplierStatus.REJECTED]:
        has_evaluation_form = await check_evaluation_form_exists(supplier_id)
        if not has_evaluation_form:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supplier Evaluation Form must be uploaded before approving or rejecting the application. Please upload the evaluation form first."
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
    elif request.action == SupplierStatus.NEED_MORE_INFO and request.notes:
        update_data["info_request_message"] = request.notes
    
    # Update supplier
    await db.update_supplier(supplier_id, update_data)
    
    # Create audit log with new centralized service
    from ...services.notifications import NotificationService
    
    # Determine audit action based on review action
    if request.action == SupplierStatus.APPROVED:
        audit_action = AuditAction.SUPPLIER_APPROVED
    elif request.action == SupplierStatus.REJECTED:
        audit_action = AuditAction.SUPPLIER_REJECTED
    elif request.action == SupplierStatus.NEED_MORE_INFO:
        audit_action = AuditAction.SUPPLIER_STATUS_CHANGED
    else:
        audit_action = AuditAction.SUPPLIER_STATUS_CHANGED
    
    # Log the review action
    await audit_service.log_vendor_action(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=audit_action,
        vendor_id=supplier_id,
        vendor_name=supplier.get("company_name"),
        details={
            "old_status": previous_status,
            "new_status": new_status,
            "notes": request.notes,
            "reviewed_by": current_admin["email"]
        },
        ip_address=get_client_ip(http_request)
    )
    
    # Send in-app notification
    notification_service = NotificationService(db)
    asyncio.create_task(
        notification_service.notify_supplier_status_change(
            supplier_id=supplier_id,
            supplier_name=supplier["company_name"],
            supplier_email=supplier["email"],
            contact_person=supplier["contact_person_name"],
            old_status=previous_status,
            new_status=new_status,
            comments=request.notes
        )
    )
    
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


# ============== Evaluation Form Upload (Admin Only) ==============

@router.post(
    "/suppliers/{supplier_id}/evaluation-form/upload-url",
    response_model=PresignedUrlResponse,
    summary="Get presigned URL for evaluation form upload",
    description="Admin endpoint to get presigned URL for uploading supplier evaluation form."
)
async def get_evaluation_form_upload_url(
    supplier_id: str,
    filename: str = Query(..., description="Name of the evaluation form file"),
    file_size: int = Query(..., gt=0, description="File size in bytes"),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Generate presigned URL for admin to upload supplier evaluation form.
    This form must be uploaded before approving or rejecting a supplier.
    """
    # Validate supplier exists
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    # Validate file type (PDF only for evaluation forms)
    if not filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evaluation form must be a PDF file"
        )
    
    # Validate file size
    if file_size > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed ({settings.MAX_FILE_SIZE_MB}MB)"
        )
    
    # Check if evaluation form already exists - if yes, we'll replace it
    existing_docs = await db.get_documents_by_supplier(supplier_id)
    for doc in existing_docs:
        if doc["document_type"] == DocumentType.EVALUATION_FORM.value:
            # Delete existing evaluation form (will be replaced)
            await db.delete_document(doc["id"])
            break
    
    try:
        # Generate presigned URL
        presigned_data = storage_service.generate_presigned_upload_url(
            supplier_id=supplier_id,
            document_type=DocumentType.EVALUATION_FORM.value,
            filename=filename,
            content_type="application/pdf",
            file_size=file_size,
        )
        
        return PresignedUrlResponse(
            upload_url=presigned_data["upload_url"],
            file_key=presigned_data["file_path"],
            expires_in=presigned_data["expires_in"],
            fields=presigned_data.get("token"),
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/suppliers/{supplier_id}/evaluation-form/confirm",
    response_model=SuccessResponse,
    summary="Confirm evaluation form upload",
    description="Confirm that evaluation form was successfully uploaded."
)
async def confirm_evaluation_form_upload(
    supplier_id: str,
    file_key: str = Body(..., embed=True),
    filename: str = Body(..., embed=True),
    file_size: int = Body(..., embed=True),
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Confirm evaluation form upload and save metadata."""
    # Validate supplier exists
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    # Create document metadata
    document_data = {
        "id": str(uuid4()),
        "supplier_id": supplier_id,
        "document_type": DocumentType.EVALUATION_FORM.value,
        "file_name": filename,
        "s3_key": file_key,
        "file_size": file_size,
        "content_type": "application/pdf",
        "uploaded_at": datetime.utcnow().isoformat(),
        "uploaded_by": current_admin["id"],  # Track who uploaded
        "verification_status": "VERIFIED",  # Auto-verify admin uploads
        "verified_at": datetime.utcnow().isoformat(),
        "verified_by": current_admin["id"],
    }
    
    # Save to database
    await db.create_document(document_data)
    
    # Log the upload
    await audit_service.log_document_action(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=AuditAction.DOCUMENT_UPLOADED,
        document_id=document_data["id"],
        document_type=DocumentType.EVALUATION_FORM.value,
        vendor_id=supplier_id,
        details={
            "filename": filename,
            "uploaded_by_admin": True,
            "file_key": file_key,
            "supplier_name": supplier.get("company_name")
        },
        ip_address=get_client_ip(http_request) if http_request else None
    )
    
    return SuccessResponse(
        success=True,
        message="Supplier Evaluation Form uploaded successfully"
    )


@router.get(
    "/suppliers/{supplier_id}/evaluation-form/status",
    summary="Check evaluation form status",
    description="Check if evaluation form has been uploaded for a supplier."
)
async def get_evaluation_form_status(
    supplier_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Check if evaluation form exists for a supplier."""
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    has_form = await check_evaluation_form_exists(supplier_id)
    
    # If form exists, get the document details
    evaluation_form = None
    if has_form:
        documents = await db.get_documents_by_supplier(supplier_id)
        for doc in documents:
            if doc.get("document_type") == DocumentType.EVALUATION_FORM.value:
                evaluation_form = {
                    "id": doc["id"],
                    "file_name": doc["file_name"],
                    "uploaded_at": doc["uploaded_at"],
                    "uploaded_by": doc.get("uploaded_by"),
                }
                break
    
    return {
        "has_evaluation_form": has_form,
        "evaluation_form": evaluation_form,
        "can_approve_reject": has_form
    }


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
    
    # Log info request with new audit service
    await audit_service.log_vendor_action(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=AuditAction.SUPPLIER_STATUS_CHANGED,
        vendor_id=supplier_id,
        vendor_name=supplier["company_name"],
        details={"message": request.message},
        ip_address=get_client_ip(http_request)
    )
    
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
        print(f"More info request email sent to vendor: {supplier['email']}")
    except Exception as e:
        import traceback
        print(f"Failed to send more info email: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
    
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
        update_data["verification_comments"] = request.rejection_reason
    
    await db.update_document(document_id, update_data)
    
    # Get supplier info for notification
    supplier = await db.get_supplier_by_id(document["supplier_id"])
    
    # Log document verification with new audit service
    audit_action = AuditAction.DOCUMENT_VERIFIED if request.status == DocumentVerificationStatus.VERIFIED else AuditAction.DOCUMENT_REJECTED
    
    await audit_service.log_document_action(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=audit_action,
        document_id=document_id,
        document_type=document["document_type"],
        vendor_id=document["supplier_id"],
        details={
            "status": request.status.value,
            "rejection_reason": request.rejection_reason,
            "file_name": document.get("file_name"),
            "vendor_name": supplier.get("company_name") if supplier else None
        },
        ip_address=get_client_ip(http_request)
    )
    
    # Send in-app notification to supplier
    from ...services.notifications import NotificationService
    notification_service = NotificationService(db)
    
    if supplier:
        asyncio.create_task(
            notification_service.notify_document_verified(
                supplier_id=document["supplier_id"],
                document_type=document["document_type"],
                verification_status=request.status.value,
                metadata={
                    "document_id": document_id,
                    "file_name": document["file_name"],
                    "rejection_reason": request.rejection_reason,
                    "supplier_name": supplier["company_name"],
                    "email": supplier["email"],
                    "name": supplier["contact_person_name"]
                }
            )
        )
    
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


# ============== Bulk Operations ==============

@router.post(
    "/suppliers/bulk-action",
    response_model=dict,
    summary="Perform bulk action on suppliers",
    description="Apply the same action to multiple suppliers at once."
)
async def bulk_supplier_action(
    request: dict,
    http_request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Perform bulk operations on suppliers.
    
    Request body:
    - supplier_ids: List of supplier IDs
    - action: "approve", "reject", or "under_review"
    """
    supplier_ids = request.get("supplier_ids", [])
    action = request.get("action", "")
    
    if not supplier_ids or not action:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="supplier_ids and action are required"
        )
    
    # Map action to status
    action_map = {
        "approve": SupplierStatus.APPROVED.value,
        "reject": SupplierStatus.REJECTED.value,
        "under_review": SupplierStatus.UNDER_REVIEW.value
    }
    
    new_status = action_map.get(action)
    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {action}"
        )
    
    successful = 0
    failed = 0
    errors = []
    
    from ...services.audit import audit_service
    from ...services.notifications import NotificationService
    notification_service = NotificationService(db)
    
    for supplier_id in supplier_ids:
        try:
            # Get supplier
            supplier = await db.get_supplier_by_id(supplier_id)
            if not supplier:
                failed += 1
                errors.append(f"Supplier {supplier_id} not found")
                continue
            
            previous_status = supplier["status"]
            
            # Update supplier status
            await db.update_supplier(supplier_id, {
                "status": new_status,
                "reviewed_at": datetime.utcnow().isoformat(),
                "reviewed_by": current_admin["id"],
                "updated_at": datetime.utcnow().isoformat(),
            })
            
            # Create audit log
            audit_action_map = {
                "approve": AuditAction.SUPPLIER_APPROVED,
                "reject": AuditAction.SUPPLIER_REJECTED,
                "under_review": AuditAction.SUPPLIER_STATUS_CHANGED
            }
            
            asyncio.create_task(
                audit_service.log_action_from_request(
                    request=http_request,
                    action=audit_action_map.get(action, AuditAction.SUPPLIER_STATUS_CHANGED),
                    resource_type=AuditResourceType.SUPPLIER,
                    resource_id=supplier_id,
                    resource_name=supplier.get("company_name"),
                    changes={
                        "status": {"old": previous_status, "new": new_status}
                    },
                    metadata={
                        "bulk_operation": True,
                        "reviewed_by": current_admin["email"]
                    },
                    current_user=current_admin
                )
            )
            
            # Send notification to vendor
            if action in ["approve", "reject"]:
                asyncio.create_task(
                    notification_service.notify_supplier_status_change(
                        supplier_id=supplier_id,
                        supplier_name=supplier["company_name"],
                        supplier_email=supplier["email"],
                        contact_person=supplier["contact_person_name"],
                        old_status=previous_status,
                        new_status=new_status,
                        comments=f"Bulk {action} operation"
                    )
                )
            
            successful += 1
            
        except Exception as e:
            failed += 1
            errors.append(f"Error processing {supplier_id}: {str(e)}")
            print(f"Bulk action error for {supplier_id}: {str(e)}")
    
    return {
        "successful": successful,
        "failed": failed,
        "total": len(supplier_ids),
        "errors": errors if errors else None,
        "message": f"Processed {successful} suppliers successfully. {failed} failed."
    }


@router.post("/documents/bulk-verify")
async def bulk_document_verification(
    request: Request,
    document_ids: List[str] = Body(...),
    status: DocumentVerificationStatus = Body(...),
    comments: Optional[str] = Body(None),
    admin: dict = Depends(get_current_admin)
):
    """
    Verify or reject multiple documents in bulk.
    """
    from ...services.notifications import NotificationService
    
    # Validate inputs
    if not document_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided")
    
    if status not in [DocumentVerificationStatus.VERIFIED, DocumentVerificationStatus.REJECTED]:
        raise HTTPException(
            status_code=400,
            detail="Status must be either VERIFIED or REJECTED"
        )
    
    notification_service = NotificationService(db)
    successful = 0
    failed = 0
    errors = []
    
    for doc_id in document_ids:
        try:
            # Get document details
            document = await db.get_document_by_id(doc_id)
            if not document:
                errors.append(f"Document {doc_id} not found")
                failed += 1
                continue
            
            # Update document verification status
            update_data = {
                "verification_status": status.value,
                "verified_at": datetime.utcnow().isoformat() if status == DocumentVerificationStatus.VERIFIED else None,
                "verification_comments": comments,
                "verified_by": admin["id"]
            }
            
            await db.update_document(doc_id, update_data)
            
            # Get supplier info
            supplier = await db.get_supplier_by_id(document["supplier_id"])
            
            # Log document verification with audit service
            audit_action = AuditAction.DOCUMENT_VERIFIED if status == DocumentVerificationStatus.VERIFIED else AuditAction.DOCUMENT_REJECTED
            
            await audit_service.log_document_action(
                admin_id=admin["id"],
                admin_email=admin["email"],
                action=audit_action,
                document_id=doc_id,
                document_type=document["document_type"],
                vendor_id=document["supplier_id"],
                details={
                    "status": status.value,
                    "rejection_reason": comments,
                    "file_name": document.get("file_name"),
                    "vendor_name": supplier.get("company_name") if supplier else None
                },
                ip_address=get_client_ip(request)
            )
            
            # Send notification to vendor
            if supplier:
                asyncio.create_task(
                    notification_service.notify_document_verified(
                        supplier_id=document["supplier_id"],
                        document_type=document["document_type"],
                        verification_status=status.value,
                        metadata={
                            "document_id": doc_id,
                            "file_name": document.get("file_name"),
                            "rejection_reason": comments,
                            "supplier_name": supplier["company_name"],
                            "email": supplier["email"],
                            "name": supplier["contact_person_name"]
                        }
                    )
                )
            
            successful += 1
            
        except Exception as e:
            failed += 1
            errors.append(f"Error processing document {doc_id}: {str(e)}")
            print(f"Bulk document verification error for {doc_id}: {str(e)}")
    
    return {
        "successful": successful,
        "failed": failed,
        "total": len(document_ids),
        "errors": errors if errors else None,
        "message": f"Processed {successful} documents successfully. {failed} failed."
    }
