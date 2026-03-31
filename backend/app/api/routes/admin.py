"""
Admin authentication and application review API routes.
These endpoints require admin authentication.
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4
from pydantic import UUID4, BaseModel
import asyncio
import secrets
import string
import traceback
from fastapi import APIRouter, HTTPException, status, Depends, Request, Query, Body

from ...db.supabase import db
from ...services.audit_service import audit_service
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
    AdminRegisterSupplierRequest,
)
from ...models.profile_change import ProfileChangeReviewRequest
from ...models.supplier import TradeReferenceListResponse
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
from ...core.cache_invalidation import invalidate_analytics_cache
from ...core.logger import logger


router = APIRouter(prefix="/admin", tags=["Admin"])


# ============== Helper Functions ==============

async def check_evaluation_form_exists(supplier_id: str) -> bool:
    """Check if evaluation form has been uploaded for a supplier."""
    documents = await db.get_documents_by_supplier(supplier_id)
    for doc in documents:
        if doc.get("document_type") == DocumentType.EVALUATION_FORM.value:
            return True
    return False


async def check_suspension_evidence_exists(supplier_id: str) -> bool:
    """Check if a suspension evidence document has been uploaded for a supplier."""
    documents = await db.get_documents_by_supplier(supplier_id)
    for doc in documents:
        if doc.get("document_type") == DocumentType.SUSPENSION_EVIDENCE.value:
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
        await audit_service.log_login(
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
    await audit_service.log_login(
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

@router.post(
    "/suppliers/register",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin registers a supplier on their behalf",
    description="Creates a supplier account on behalf of a supplier who cannot register themselves. Auto-generates and emails credentials."
)
async def admin_register_supplier(
    request: AdminRegisterSupplierRequest,
    http_request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Register a new supplier on behalf of the admin.

    Creates the supplier record, auto-generates a temporary password, and emails
    the credentials to the supplier. The supplier is created in INCOMPLETE status so the
    admin can upload documents using the existing document endpoints before optionally
    submitting on behalf. If submit_immediately is True, status is set to SUBMITTED.
    """
    from ...models.enums import get_supplier_type, compute_business_size, compute_esg_flags

    # Duplicate email check
    existing = await db.get_supplier_by_email(request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A supplier with this email address already exists"
        )

    # Generate a secure temporary password
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    temp_password = "".join(secrets.choice(alphabet) for _ in range(12))

    # Derive supplier type, business size, and ESG flags
    supplier_type = get_supplier_type(request.country, request.is_small_scale_farmer)
    business_size = compute_business_size(request.employee_count)
    key_persons_raw = [kp.model_dump() for kp in request.key_persons]
    esg_flags = compute_esg_flags(key_persons_raw)

    initial_status = (
        SupplierStatus.SUBMITTED.value if request.submit_immediately
        else SupplierStatus.INCOMPLETE.value
    )

    supplier_data = {
        "id": str(uuid4()),
        "company_name": request.company_name,
        "business_category": request.business_category.value,
        "registration_number": request.registration_number,
        "tax_id": request.tax_id,
        "years_in_business": request.years_in_business,
        "website": request.website,
        "employee_count": request.employee_count,
        "is_small_scale_farmer": request.is_small_scale_farmer,
        "business_size": business_size.value if business_size else None,
        "esg_women_owned": esg_flags["esg_women_owned"],
        "esg_youth_owned": esg_flags["esg_youth_owned"],
        "contact_person_name": request.contact_person_name,
        "contact_person_title": request.contact_person_title,
        "email": request.email,
        "phone": request.phone,
        "street_address": request.street_address,
        "city": request.city,
        "state_province": request.state_province,
        "postal_code": request.postal_code or "",
        "country": request.country,
        "password_hash": hash_password(temp_password),
        "status": initial_status,
        "registered_by_admin": True,
        "registered_by_admin_email": current_admin["email"],
        "created_at": datetime.utcnow().isoformat(),
    }

    supplier = await db.create_supplier(supplier_data)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create supplier"
        )

    supplier_id = supplier["id"]

    # Persist key persons
    for kp in request.key_persons:
        kp_data = {
            "supplier_id": supplier_id,
            "full_name": kp.full_name,
            "gender": kp.gender.value,
            "date_of_birth": kp.date_of_birth.isoformat() if kp.date_of_birth else None,
            "role": kp.role.value,
        }
        await db.create_key_person(kp_data)

    # Persist trade references
    for ref in request.trade_references:
        ref_data = {
            "supplier_id": supplier_id,
            "company_name": ref.company_name,
            "contact_person_name": ref.contact_person_name,
            "email": str(ref.email),
            "phone": ref.phone,
            "relationship": ref.relationship,
            "service_product": ref.service_product,
            "contract_start_date": ref.contract_start_date.isoformat() if ref.contract_start_date else None,
            "contract_end_date": ref.contract_end_date.isoformat() if ref.contract_end_date else None,
            "annual_spend": ref.annual_spend,
            "permission_granted": ref.permission_granted,
        }
        await db.create_trade_reference(ref_data)

    # Persist categories
    for cat in request.business_categories:
        cat_data = {
            "supplier_id": supplier_id,
            "category": cat.value,
            "compliance_status": "PENDING",
        }
        await db.create_supplier_category(cat_data)

    # Audit log
    await audit_service.log_vendor_action(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=AuditAction.SUPPLIER_CREATED,
        vendor_id=supplier_id,
        vendor_name=supplier["company_name"],
        details={
            "registered_by_admin": True,
            "category": supplier["business_category"],
            "submit_immediately": request.submit_immediately,
        }
    )

    # Email credentials to supplier
    try:
        app_status = (
            "Submitted for review" if request.submit_immediately
            else "Incomplete – documents still need to be uploaded"
        )
        await email_service.send_template_email(
            to_email=supplier["email"],
            template=EmailTemplate.ADMIN_REGISTERED_SUPPLIER,
            data={
                "contact_person": supplier["contact_person_name"],
                "supplier_name": supplier["company_name"],
                "email": supplier["email"],
                "temp_password": temp_password,
                "application_status": app_status,
                "portal_url": settings.FRONTEND_URL,
            },
            to_name=supplier["contact_person_name"]
        )
    except Exception as e:
        logger.warning("Failed to send credentials email to %s: %s", supplier['email'], e)

    await invalidate_analytics_cache()

    return supplier


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
        date_from=filters.date_from,
        date_to=filters.date_to,
        page=pagination.page,
        page_size=pagination.page_size,
        order_by=filters.sort_by,
        ascending=filters.ascending,
    )

    # Enrich each supplier with all their categories from supplier_categories
    if result["items"]:
        supplier_ids = [s["id"] for s in result["items"]]
        all_cats = db.client.table("supplier_categories").select("supplier_id, category").in_("supplier_id", supplier_ids).execute()
        cats_by_supplier: dict = {}
        for row in (all_cats.data or []):
            cats_by_supplier.setdefault(row["supplier_id"], []).append(row["category"])
        for s in result["items"]:
            s["business_categories"] = cats_by_supplier.get(s["id"]) or [s["business_category"]]

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
    
    # Auto-transition: when an admin opens a SUBMITTED application it moves to UNDER_REVIEW,
    # signalling that the review process has begun.
    if supplier["status"] == SupplierStatus.SUBMITTED.value:
        await db.update_supplier(supplier_id, {
            "status": SupplierStatus.UNDER_REVIEW.value,
            "updated_at": datetime.utcnow().isoformat(),
        })
        await audit_service.log_vendor_action(
            admin_id=current_admin["id"],
            admin_email=current_admin["email"],
            action=AuditAction.SUPPLIER_STATUS_CHANGED,
            vendor_id=supplier_id,
            vendor_name=supplier['company_name'],
            details={
                "old_status": SupplierStatus.SUBMITTED.value,
                "new_status": SupplierStatus.UNDER_REVIEW.value,
                "reason": "Admin opened application — review started"
            },
            ip_address=get_client_ip(http_request)
        )
        # Refresh supplier data so the returned object reflects the new status
        supplier = await db.get_supplier_by_id(supplier_id)
    
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

    # Fetch all categories from supplier_categories table (supports multi-category)
    cat_rows = await db.get_supplier_categories(supplier_id)
    biz_categories = [r["category"] for r in cat_rows] if cat_rows else [supplier["business_category"]]

    return SupplierResponse(**{**supplier, "business_categories": biz_categories})


@router.get(
    "/suppliers/{supplier_id}/trade-references",
    response_model=TradeReferenceListResponse,
    summary="Get supplier trade references",
    description="Get trade references captured during supplier registration."
)
async def get_supplier_trade_references(
    supplier_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Get trade references for a supplier."""
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )

    items = await db.get_trade_references_by_supplier(supplier_id)
    return TradeReferenceListResponse(
        supplier_id=supplier_id,
        items=items,
        total=len(items),
    )


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
    
    # Check if evaluation form is uploaded before allowing approval/rejection
    if request.action in [SupplierStatus.APPROVED, SupplierStatus.REJECTED]:
        has_evaluation_form = await check_evaluation_form_exists(supplier_id)
        if not has_evaluation_form:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supplier Evaluation Form must be uploaded before approving or rejecting the application. Please upload the evaluation form first."
            )

    # All supplier documents must be individually verified before approval
    if request.action == SupplierStatus.APPROVED:
        supplier_docs = await db.get_documents_by_supplier(supplier_id)
        unverified = [
            doc for doc in supplier_docs
            if doc.get("document_type") != "EVALUATION_FORM"
            and doc.get("verification_status") != "VERIFIED"
        ]
        if unverified:
            unverified_names = ", ".join(
                doc.get("document_type", "Unknown").replace("_", " ").title()
                for doc in unverified
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"All supplier documents must be verified before approval. "
                       f"The following documents are still pending or rejected: {unverified_names}"
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

    # When re-approving a previously suspended / compliance-required supplier,
    # clear the suspension fields so they no longer appear in the suspended list.
    if request.action == SupplierStatus.APPROVED and previous_status in (
        SupplierStatus.SUSPENDED.value, SupplierStatus.COMPLIANCE_REQUIRED.value
    ):
        update_data["suspended_at"] = None
        update_data["suspension_reason"] = None

    # Update supplier (may raise if the status-history trigger constraint fails;
    # that should be impossible after migration 035, but guard just in case).
    try:
        await db.update_supplier(supplier_id, update_data)
    except Exception as db_err:
        err_str = str(db_err)
        if "check_status_values" in err_str or "23514" in err_str:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Database constraint error: the supplier_status_history table is missing "
                    "the COMPLIANCE_REQUIRED status value. Please run migration "
                    "035_fix_status_history_constraint.sql in the Supabase SQL Editor."
                )
            )
        raise
    
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
        logger.warning("Failed to send email: %s", e)

    await invalidate_analytics_cache()

    # Keep per-category compliance current whenever a supplier's status changes.
    # This is cheap and ensures the sustainability dashboard reflects approval immediately.
    try:
        await db.recompute_supplier_category_compliance(supplier_id)
    except Exception as compliance_err:
        logger.warning("compliance recompute skipped for %s: %s", supplier_id, compliance_err)

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


# ============== Suspension Evidence Upload (Admin Only) ==============

@router.post(
    "/suppliers/{supplier_id}/suspension-evidence/upload-url",
    response_model=PresignedUrlResponse,
    summary="Get presigned URL for suspension evidence upload",
    description="Admin endpoint to get presigned URL for uploading suspension evidence document."
)
async def get_suspension_evidence_upload_url(
    supplier_id: str,
    filename: str = Query(..., description="Name of the evidence file"),
    file_size: int = Query(..., gt=0, description="File size in bytes"),
    current_admin: dict = Depends(get_current_admin)
):
    """Generate presigned URL for admin to upload suspension evidence document."""
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )

    if not filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Suspension evidence must be a PDF file"
        )

    if file_size > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed ({settings.MAX_FILE_SIZE_MB}MB)"
        )

    # Delete any existing suspension evidence document (replaced by new upload)
    existing_docs = await db.get_documents_by_supplier(supplier_id)
    for doc in existing_docs:
        if doc["document_type"] == DocumentType.SUSPENSION_EVIDENCE.value:
            await db.delete_document(doc["id"])
            break

    try:
        presigned_data = storage_service.generate_presigned_upload_url(
            supplier_id=supplier_id,
            document_type=DocumentType.SUSPENSION_EVIDENCE.value,
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/suppliers/{supplier_id}/suspension-evidence/confirm",
    response_model=SuccessResponse,
    summary="Confirm suspension evidence upload",
    description="Confirm that suspension evidence document was successfully uploaded."
)
async def confirm_suspension_evidence_upload(
    supplier_id: str,
    file_key: str = Body(..., embed=True),
    filename: str = Body(..., embed=True),
    file_size: int = Body(..., embed=True),
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Confirm suspension evidence upload and save metadata."""
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )

    document_data = {
        "id": str(uuid4()),
        "supplier_id": supplier_id,
        "document_type": DocumentType.SUSPENSION_EVIDENCE.value,
        "file_name": filename,
        "s3_key": file_key,
        "file_size": file_size,
        "content_type": "application/pdf",
        "uploaded_at": datetime.utcnow().isoformat(),
        "uploaded_by": current_admin["id"],
        "verification_status": "VERIFIED",
        "verified_at": datetime.utcnow().isoformat(),
        "verified_by": current_admin["id"],
    }
    try:
        await db.create_document(document_data)
    except Exception as exc:
        error_text = str(exc)
        if "invalid input value for enum document_type" in error_text and "SUSPENSION_EVIDENCE" in error_text:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Database enum value missing for SUSPENSION_EVIDENCE. "
                    "Run migration 044_add_suspension_evidence_document_type.sql in Supabase."
                ),
            )
        raise

    await audit_service.log_document_action(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=AuditAction.DOCUMENT_UPLOADED,
        document_id=document_data["id"],
        document_type=DocumentType.SUSPENSION_EVIDENCE.value,
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
        message="Suspension evidence document uploaded successfully"
    )


@router.get(
    "/suppliers/{supplier_id}/suspension-evidence/status",
    summary="Check suspension evidence status",
    description="Check if a suspension evidence document has been uploaded for a supplier."
)
async def get_suspension_evidence_status(
    supplier_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Check if suspension evidence document exists for a supplier."""
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )

    has_evidence = await check_suspension_evidence_exists(supplier_id)
    evidence = None
    if has_evidence:
        documents = await db.get_documents_by_supplier(supplier_id)
        for doc in documents:
            if doc.get("document_type") == DocumentType.SUSPENSION_EVIDENCE.value:
                evidence = {
                    "id": doc["id"],
                    "file_name": doc["file_name"],
                    "uploaded_at": doc["uploaded_at"],
                    "uploaded_by": doc.get("uploaded_by"),
                }
                break

    return {
        "has_evidence": has_evidence,
        "evidence": evidence,
        "can_suspend": has_evidence
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
        logger.info("More info request email sent to vendor: %s", supplier['email'])
    except Exception as e:
        logger.exception("Failed to send more info email: %s", e)
    
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

    # Admin can confirm or correct the expiry date during verification.
    # This becomes the authoritative value tracked for compliance alerts.
    if request.expiry_date is not None:
        update_data["expiry_date"] = request.expiry_date.isoformat()
    
    await db.update_document(document_id, update_data)
    
    # Get supplier info for notification
    supplier = await db.get_supplier_by_id(document["supplier_id"])

    # Keep per-category compliance distribution current after every verification action.
    try:
        await db.recompute_supplier_category_compliance(document["supplier_id"])
    except Exception as compliance_err:
        logger.warning("compliance recompute skipped for %s: %s", document['supplier_id'], compliance_err)
    
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

    # Recompute portfolio status after verification using scoped rules:
    # category-specific gaps affect category compliance, statutory gaps affect supplier status.
    if supplier:
        previous_status = supplier.get("status", "")
        try:
            transition = await db.recompute_supplier_portfolio_status(str(document["supplier_id"]))
            new_status = transition.get("new_status", previous_status)
            if (
                previous_status in (SupplierStatus.SUSPENDED.value, SupplierStatus.COMPLIANCE_REQUIRED.value)
                and new_status == SupplierStatus.APPROVED.value
            ):
                asyncio.create_task(
                    email_service.send_template_email(
                        to_email=supplier["email"],
                        template=EmailTemplate.SUPPLIER_RESTORED,
                        data={
                            "supplier_name": supplier["company_name"],
                            "contact_person": supplier.get("contact_person_name", supplier["company_name"]),
                            "portal_url": settings.FRONTEND_URL,
                        },
                        to_name=supplier.get("contact_person_name"),
                    )
                )
        except Exception as status_err:
            logger.warning("supplier portfolio status recompute skipped: %s", status_err)

    await invalidate_analytics_cache()

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
    for doc in documents:
        try:
            storage_service.delete_file(doc["s3_key"])
            logger.info("Deleted file: %s", doc['s3_key'])
        except Exception as e:
            # Log but don't fail - file might not exist in storage
            logger.warning("Could not delete file %s: %s", doc['s3_key'], e)
    
    # Delete supplier from database (this will cascade delete documents due to foreign key)
    await db.delete_supplier(supplier_id)
    
    # Log the action
    await db.create_audit_log({
        "admin_id": current_admin["id"],
        "user_type": "admin",
        "user_email": current_admin["email"],
        "action": AdminAction.DELETE_SUPPLIER.value,
        "resource_type": "supplier",
        "resource_id": supplier_id,
        "metadata": {"company_name": supplier["company_name"], "email": supplier["email"]},
        "ip_address": get_client_ip(http_request),
    })

    await invalidate_analytics_cache()
    
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
            logger.warning("Bulk action error for %s: %s", supplier_id, e)

    if successful > 0:
        await invalidate_analytics_cache()
    
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
            logger.warning("Bulk document verification error for %s: %s", doc_id, e)

    if successful > 0:
        await invalidate_analytics_cache()
    
    return {
        "successful": successful,
        "failed": failed,
        "total": len(document_ids),
        "errors": errors if errors else None,
        "message": f"Processed {successful} documents successfully. {failed} failed."
    }


# ============== Admin Profile & Dashboard ==============

@router.get(
    "/profile",
    response_model=AdminResponse,
    summary="Get admin profile",
    description="Get the authenticated admin user's profile."
)
async def get_admin_profile(current_admin: dict = Depends(get_current_admin)):
    """Get admin user profile (alias for /me)."""
    return AdminResponse(**current_admin)


@router.get(
    "/dashboard/summary",
    summary="Get dashboard summary",
    description="Get complete dashboard summary with all key metrics."
)
async def get_dashboard_summary_endpoint(
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get comprehensive dashboard summary (proxy to analytics)."""
    from .analytics import get_dashboard_summary
    return await get_dashboard_summary(http_request, current_admin)


@router.get(
    "/dashboard/monthly-trends",
    summary="Get monthly trends",
    description="Get monthly registration, approval, and rejection trends."
)
async def get_monthly_trends_endpoint(
    year: int = Query(default=datetime.now().year, ge=2020, le=2100),
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get monthly trends (proxy to analytics)."""
    from .analytics import get_monthly_trends
    return await get_monthly_trends(year=year, http_request=http_request, current_admin=current_admin)


@router.get(
    "/dashboard/weekly-trends",
    summary="Get weekly trends",
    description="Get weekly registration, approval, and rejection trends."
)
async def get_weekly_trends_endpoint(
    weeks: int = Query(default=12, ge=1, le=52),
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get weekly trends (proxy to analytics)."""
    from .analytics import get_weekly_trends
    return await get_weekly_trends(weeks, http_request, current_admin)


@router.get(
    "/dashboard/location-stats",
    summary="Get location statistics",
    description="Get supplier distribution by location."
)
async def get_location_stats_endpoint(
    group_by: str = Query(default="city", regex="^(city|country)$"),
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get location statistics (proxy to analytics)."""
    from .analytics import get_location_stats
    # Map group_by to level parameter
    return await get_location_stats(level=group_by, http_request=http_request, current_admin=current_admin)


# ============== Messaging Proxy Endpoints ==============

@router.get(
    "/messages/threads",
    summary="Get admin message threads",
    description="Get all message threads for admin (proxy to messages router)."
)
async def get_admin_threads_endpoint(
    is_archived: Optional[bool] = Query(None),
    category_id: Optional[UUID4] = Query(None),
    priority: Optional[str] = Query(None),
    has_unread: Optional[bool] = Query(None),
    supplier_id: Optional[str] = Query(None),  # Accept but ignore - not in messages.get_admin_threads
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get message threads (proxy to messages router)."""
    from .messages import get_admin_threads
    return await get_admin_threads(
        request=http_request,
        is_archived=is_archived,
        category_id=category_id,
        priority=priority,
        has_unread=has_unread,
        page=page,
        page_size=page_size,
        current_admin=current_admin
    )


@router.get(
    "/messages/unread-count",
    summary="Get admin unread message count",
    description="Get count of unread messages for admin (proxy to messages router)."
)
async def get_admin_unread_count_endpoint(
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get unread message count (proxy to messages router)."""
    from .messages import get_admin_unread_count
    return await get_admin_unread_count(request=http_request, current_admin=current_admin)


# ============== Suspended Suppliers ==============

@router.get(
    "/suspended-suppliers",
    summary="List suspended suppliers",
    description="Returns all suppliers currently in SUSPENDED status with the expired documents causing the suspension."
)
async def get_suspended_suppliers(
    current_admin: dict = Depends(get_current_admin)
):
    """Get all suspended suppliers."""
    try:
        result = db.client.rpc("get_suspended_suppliers").execute()
        return {"items": result.data or [], "total": len(result.data or [])}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class AdminSuspendRequest(BaseModel):
    reason: str


@router.post(
    "/suppliers/{supplier_id}/suspend",
    response_model=SuccessResponse,
    summary="Manually suspend a supplier",
    description="Admin can manually suspend any active supplier with a custom reason."
)
async def suspend_supplier(
    supplier_id: str,
    body: AdminSuspendRequest,
    http_request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """Manually suspend a supplier (admin discretion)."""
    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=422, detail="A suspension reason is required.")

    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    current_status = supplier.get("status")
    _suspendable = {SupplierStatus.APPROVED.value, SupplierStatus.COMPLIANCE_REQUIRED.value}
    if current_status == SupplierStatus.SUSPENDED.value:
        raise HTTPException(status_code=400, detail="Supplier is already suspended.")
    if current_status not in _suspendable:
        raise HTTPException(
            status_code=422,
            detail=(
                "Only approved suppliers can be manually suspended. "
                f"This supplier's current status is '{current_status}'. "
                "Complete the approval process before suspending."
            ),
        )

    # Require suspension evidence document before suspending
    has_evidence = await check_suspension_evidence_exists(supplier_id)
    if not has_evidence:
        raise HTTPException(
            status_code=422,
            detail="A suspension evidence document must be uploaded before suspending a supplier."
        )

    admin_email = current_admin.get("email", "admin")
    result = db.client.rpc(
        "admin_suspend_supplier",
        {"p_supplier_id": supplier_id, "p_reason": body.reason.strip(), "p_admin_email": admin_email}
    ).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to suspend supplier")

    # Notify the supplier
    asyncio.create_task(
        email_service.send_template_email(
            to_email=supplier["email"],
            template=EmailTemplate.SUPPLIER_SUSPENDED,
            data={
                "supplier_name": supplier["company_name"],
                "contact_person": supplier.get("contact_person_name", supplier["company_name"]),
                "suspension_reason": body.reason.strip(),
                "portal_url": settings.FRONTEND_URL,
            },
            to_name=supplier.get("contact_person_name"),
        )
    )

    await audit_service.log_vendor_action(
        admin_id=current_admin["id"],
        admin_email=admin_email,
        action=AuditAction.SUPPLIER_STATUS_CHANGED,
        vendor_id=supplier_id,
        vendor_name=supplier.get("company_name", ""),
        details={
            "previous_status": supplier.get("status"),
            "new_status": SupplierStatus.SUSPENDED.value,
            "reason": body.reason.strip(),
            "suspended_by": admin_email,
        },
        ip_address=get_client_ip(http_request)
    )

    await invalidate_analytics_cache()

    return SuccessResponse(success=True, message="Supplier has been suspended.")


@router.post(
    "/suppliers/{supplier_id}/unsuspend",
    response_model=SuccessResponse,
    summary="Manually unsuspend a supplier",
    description="Admin can manually restore a suspended supplier to APPROVED status (override)."
)
async def unsuspend_supplier(
    supplier_id: str,
    http_request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """Manually restore a suspended supplier to APPROVED status."""
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    if supplier.get("status") not in (SupplierStatus.SUSPENDED.value, SupplierStatus.COMPLIANCE_REQUIRED.value):
        raise HTTPException(status_code=400, detail="Supplier is not suspended")

    db.client.table("suppliers").update({
        "status": SupplierStatus.APPROVED.value,
        "suspended_at": None,
        "suspension_reason": None,
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("id", supplier_id).execute()

    # Record in history
    db.client.table("supplier_suspension_history").insert({
        "supplier_id": supplier_id,
        "event": "RESTORED",
        "reason": "Manually restored by admin.",
        "triggered_by": current_admin.get("email", "admin"),
    }).execute()

    # Notify supplier
    asyncio.create_task(
        email_service.send_template_email(
            to_email=supplier["email"],
            template=EmailTemplate.SUPPLIER_RESTORED,
            data={
                "supplier_name": supplier["company_name"],
                "contact_person": supplier.get("contact_person_name", supplier["company_name"]),
                "portal_url": settings.FRONTEND_URL,
            },
            to_name=supplier.get("contact_person_name"),
        )
    )

    await audit_service.log_vendor_action(
        admin_id=current_admin["id"],
        admin_email=current_admin.get("email", "admin"),
        action=AuditAction.SUPPLIER_STATUS_CHANGED,
        vendor_id=supplier_id,
        vendor_name=supplier.get("company_name", ""),
        details={
            "previous_status": supplier.get("status"),
            "new_status": SupplierStatus.APPROVED.value,
            "manual_override": True,
        },
        ip_address=get_client_ip(http_request)
    )

    await invalidate_analytics_cache()

    return SuccessResponse(success=True, message="Supplier restored to Approved status.")


# ============== Profile Changes Proxy Endpoints ==============

@router.get(
    "/profile-changes/pending",
    summary="Get pending profile changes",
    description="Get all pending profile change requests (proxy to profile_changes router)."
)
async def get_pending_profile_changes_endpoint(
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get pending profile changes (proxy to profile_changes router)."""
    from .profile_changes import get_pending_profile_changes
    return await get_pending_profile_changes(request=http_request, current_admin=current_admin)


@router.get(
    "/profile-changes/history",
    summary="Get resolved profile changes",
    description="Get all resolved (non-pending) profile change requests (proxy to profile_changes router)."
)
async def get_profile_changes_history_endpoint(
    status_filter: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get resolved profile changes history (proxy to profile_changes router)."""
    from .profile_changes import get_profile_changes_history
    return await get_profile_changes_history(
        request=http_request,
        status_filter=status_filter,
        limit=limit,
        current_admin=current_admin
    )


@router.get(
    "/profile-changes/{request_id}",
    summary="Get profile change detail",
    description="Get details of a specific profile change request (proxy to profile_changes router)."
)
async def get_profile_change_detail_endpoint(
    request_id: UUID4,
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get profile change detail (proxy to profile_changes router)."""
    from .profile_changes import get_profile_change_detail
    return await get_profile_change_detail(request_id=request_id, request=http_request, current_admin=current_admin)


@router.post(
    "/profile-changes/{request_id}/review",
    summary="Review profile change",
    description="Approve or reject a profile change request (proxy to profile_changes router)."
)
async def review_profile_change_endpoint(
    request_id: UUID4,
    review: ProfileChangeReviewRequest,
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Review profile change (proxy to profile_changes router)."""
    from .profile_changes import review_profile_change
    return await review_profile_change(
        request_id=request_id,
        review=review,
        request=http_request,
        current_admin=current_admin
    )
