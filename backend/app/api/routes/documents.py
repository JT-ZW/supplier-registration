"""
Document management API routes.
Handles document uploads and presigned URL generation.
"""

from datetime import datetime
from uuid import uuid4
import asyncio
from fastapi import APIRouter, HTTPException, status, Request, Depends

from ...db.supabase import db
from ...services.audit import AuditService
from ...api.deps import get_client_ip, get_current_admin, get_current_user
from ...models import (
    DocumentUploadRequest,
    DocumentMetadataCreateRequest,
    PresignedUrlResponse,
    PresignedDownloadUrlResponse,
    DocumentResponse,
    DocumentListResponse,
    AddableDocumentItem,
    AddableDocumentsResponse,
    SuccessResponse,
    SupplierStatus,
    DocumentType,
    DocumentVerificationStatus,
)
from ...models.audit import AuditAction, AuditResourceType
from ...core.storage import storage_service
from ...core.config import settings
from ...core.logger import logger


router = APIRouter(prefix="/documents", tags=["Documents"])

# Initialize audit service
audit_service = AuditService()


@router.post(
    "/upload-url",
    response_model=PresignedUrlResponse,
    summary="Get presigned upload URL",
    description="Generate a presigned URL for uploading a document directly to cloud storage."
)
async def get_upload_url(
    request: DocumentUploadRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate a presigned URL for direct file upload to S3.

    The client will use this URL to upload the file directly to cloud storage,
    bypassing the backend for the actual file transfer.
    """
    # Authorization logic
    if current_user["type"] == "vendor" and current_user["data"]["id"] != request.supplier_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only upload documents for your own application"
        )
    # Validate supplier exists and is in correct status
    supplier = await db.get_supplier_by_id(request.supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    allowed_statuses = [
        SupplierStatus.INCOMPLETE.value,
        SupplierStatus.SUBMITTED.value,       # Vendor may replace a document noticed as wrong before review completes
        SupplierStatus.UNDER_REVIEW.value,    # Admin can still request info; vendor should be able to replace
        SupplierStatus.NEED_MORE_INFO.value,
        SupplierStatus.APPROVED.value,        # Approved suppliers may add supplementary documents
        SupplierStatus.COMPLIANCE_REQUIRED.value,  # Suppliers resolving expired-document compliance flags
        SupplierStatus.SUSPENDED.value,       # Suspended suppliers must be able to upload renewals
    ]
    if supplier["status"] not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upload documents for this application status"
        )
    
    # Validate file size
    if request.file_size > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed ({settings.MAX_FILE_SIZE_MB}MB)"
        )
    
    # Keep existing records until upload is confirmed so failed uploads do not lose history.
    
    try:
        # Generate presigned URL
        presigned_data = storage_service.generate_presigned_upload_url(
            supplier_id=request.supplier_id,
            document_type=request.document_type.value,
            filename=request.filename,
            content_type=request.content_type,
            file_size=request.file_size,
        )
        
        return PresignedUrlResponse(
            upload_url=presigned_data["upload_url"],
            file_key=presigned_data["file_path"],  # Changed from file_key to file_path
            expires_in=presigned_data["expires_in"],
            fields=presigned_data.get("token"),  # Supabase uses token instead of fields
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
    "/confirm-upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm document upload",
    description="Confirm that a document was successfully uploaded and save its metadata."
)
async def confirm_upload(
    request: DocumentMetadataCreateRequest,
    http_request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Confirm document upload and save metadata to database.

    This should be called after the client successfully uploads
    the file to the presigned URL.
    """
    if current_user["type"] == "vendor" and current_user["data"]["id"] != request.supplier_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only confirm documents for your own application"
        )
    # Validate supplier exists
    supplier = await db.get_supplier_by_id(request.supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    # If file_key is missing, reconstruct it
    # (This happens when browser cache has old JavaScript)
    file_key = request.file_key
    if not file_key:
        # Find the most recent document for this supplier and document type
        existing_docs = await db.get_documents_by_supplier(request.supplier_id)
        for doc in reversed(existing_docs):  # Most recent first
            if doc["document_type"] == request.document_type.value:
                file_key = doc.get("s3_key")  # Database uses s3_key column
                break
        
        # If still no file_key, generate one based on the current document
        if not file_key:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            safe_filename = "".join(c for c in request.filename if c.isalnum() or c in "._-")
            file_key = f"suppliers/{request.supplier_id}/{request.document_type.value}/{timestamp}_{unique_id}_{safe_filename}"
    
    # Optionally verify file exists in Storage
    # (This adds latency but ensures data integrity)
    if not storage_service.file_exists(file_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File not found in storage. Please re-upload the document."
        )
    
    # Determine if this is a supplementary upload (added after the application was approved)
    is_supplementary = supplier["status"] == SupplierStatus.APPROVED.value
    now_utc = datetime.utcnow()
    
    # Create document record
    document_data = {
        "id": str(uuid4()),
        "supplier_id": request.supplier_id,
        "document_type": request.document_type.value,
        "s3_key": file_key,  # Database column is s3_key
        "file_name": request.filename,
        "file_size": request.file_size,
        "content_type": request.content_type,
        "verification_status": DocumentVerificationStatus.PENDING.value,
        "uploaded_at": now_utc.isoformat(),
        "is_supplementary": is_supplementary,
        "added_post_approval_at": now_utc.isoformat() if is_supplementary else None,
        # Supplier-entered expiry date — considered provisional until admin confirms during verification
        "expiry_date": request.expiry_date.isoformat() if request.expiry_date else None,
    }

    # Try inserting with supplementary columns first; if the migration hasn't been
    # applied yet those columns won't exist — fall back gracefully so uploads still work.
    document = None
    reused_existing_document = False
    try:
        document = await db.create_document(document_data)
    except Exception as e:
        err_text = str(e).lower()
        enum_error = (
            "invalid input value for enum document_type" in err_text
            or ("enum" in err_text and "document_type" in err_text)
        )
        if enum_error:
            if request.document_type == DocumentType.SUSPENSION_EVIDENCE:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "Database enum document_type is missing 'SUSPENSION_EVIDENCE'. "
                        "Run migration 044_add_suspension_evidence_document_type.sql and retry."
                    ),
                )
            if request.document_type in {
                DocumentType.APPLICATION_FORM,
                DocumentType.SAFETY_METHOD_STATEMENT,
                DocumentType.RESCUE_PLAN,
            }:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        f"Database enum document_type is missing '{request.document_type.value}'. "
                        "Run migration 046_add_farmer_and_safety_document_types.sql and retry."
                    ),
                )

        duplicate_error = (
            "unique_document_per_supplier" in err_text
            or (
                "duplicate key value" in err_text
                and "(supplier_id, document_type)" in err_text
            )
        )
        if duplicate_error:
            # Backward-compatibility path for databases that still enforce
            # one row per (supplier_id, document_type).
            existing_docs = await db.get_documents_by_supplier(request.supplier_id)
            existing_doc = next(
                (doc for doc in existing_docs if doc.get("document_type") == request.document_type.value),
                None,
            )
            if not existing_doc:
                raise

            replacement_data = {
                "s3_key": file_key,
                "file_name": request.filename,
                "file_size": request.file_size,
                "content_type": request.content_type,
                "verification_status": DocumentVerificationStatus.PENDING.value,
                "uploaded_at": now_utc.isoformat(),
                "expiry_date": request.expiry_date.isoformat() if request.expiry_date else None,
                "is_supplementary": is_supplementary,
                "added_post_approval_at": now_utc.isoformat() if is_supplementary else None,
            }

            try:
                document = await db.update_document(existing_doc["id"], replacement_data)
            except Exception as update_err:
                update_err_text = str(update_err).lower()
                update_col_error = any(
                    kw in update_err_text for kw in ("is_supplementary", "added_post_approval_at", "column")
                )
                if update_col_error:
                    fallback_update_data = {
                        k: v
                        for k, v in replacement_data.items()
                        if k not in ("is_supplementary", "added_post_approval_at")
                    }
                    document = await db.update_document(existing_doc["id"], fallback_update_data)
                else:
                    raise

            reused_existing_document = True
        col_error = any(kw in str(e).lower() for kw in ("is_supplementary", "added_post_approval_at", "column"))
        if col_error and not reused_existing_document:
            logger.warning("Supplementary columns not found in DB — falling back to base insert. Run migration 024. Error: %s", e)
            fallback_data = {k: v for k, v in document_data.items() if k not in ("is_supplementary", "added_post_approval_at")}
            document = await db.create_document(fallback_data)
        elif not reused_existing_document:
            raise

    if not document:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save document metadata"
        )

    # Archive any previous (non-archived) documents of the same type for this supplier.
    # This replaces the old hard-delete and keeps a full audit trail.
    if not reused_existing_document:
        try:
            db.client.rpc(
                "archive_old_document_version",
                {
                    "p_supplier_id": str(request.supplier_id),
                    "p_document_type": request.document_type.value,
                    "p_new_doc_id": document["id"],
                }
            ).execute()
        except Exception as _archive_err:
            # Non-fatal: log but don't fail the request (old records stay active until
            # the migration is applied).
            logger.warning("archive_old_document_version skipped: %s", _archive_err)

    # Do not auto-restore here. Restoration should occur only after admin verifies
    # the replacement document (handled in admin document verification flow).

    # Log document upload to audit trail
    asyncio.create_task(
        audit_service.log_action_from_request(
            request=http_request,
            action=AuditAction.DOCUMENT_UPLOADED,
            resource_type=AuditResourceType.DOCUMENT,
            resource_id=document["id"],
            resource_name=request.filename,
            metadata={
                "document_type": request.document_type.value,
                "filename": request.filename,
                "file_size": request.file_size,
                "supplier_id": request.supplier_id,
                "supplier_name": supplier.get("company_name")
            }
        )
    )
    
    # Send real-time in-app notification to admins
    from ...services.notifications import NotificationService
    from ...models.notification import RecipientType, NotificationType
    notification_service = NotificationService(db)
    
    async def notify_admins_of_upload():
        try:
            # Get all active admins
            admins = await db.get_all_admins()
            admin_ids = [admin["id"] for admin in admins if admin.get("is_active", True)]
            
            if admin_ids:
                from ...models.notification import BulkNotificationCreate
                from uuid import UUID
                
                doc_type_display = request.document_type.value.replace('_', ' ').title()
                
                bulk_notification = BulkNotificationCreate(
                    recipient_ids=[UUID(admin_id) for admin_id in admin_ids],
                    recipient_type=RecipientType.ADMIN,
                    type=NotificationType.DOCUMENT_UPLOADED,
                    title="New Document Uploaded" if not is_supplementary else "Supplementary Document Added",
                    message=(
                        f"{supplier.get('company_name', 'A supplier')} uploaded {doc_type_display}"
                        if not is_supplementary
                        else f"{supplier.get('company_name', 'An approved supplier')} added a supplementary document: {doc_type_display}"
                    ),
                    action_url=f"/admin/suppliers/{request.supplier_id}",
                    action_label="Review Document",
                    resource_type="document",
                    resource_id=UUID(document["id"]),
                    metadata={
                        "document_type": request.document_type.value,
                        "filename": request.filename,
                        "supplier_id": request.supplier_id,
                        "supplier_name": supplier.get("company_name"),
                        "is_supplementary": is_supplementary,
                    },
                    send_email=False  # Don't spam admins with emails for every upload
                )
                
                await notification_service.create_bulk_notifications(bulk_notification)
        except Exception as e:
            logger.warning("Failed to send document upload notifications: %s", e)
    
    asyncio.create_task(notify_admins_of_upload())
    
    return document


@router.get(
    "/supplier/{supplier_id}",
    response_model=DocumentListResponse,
    summary="List supplier documents",
    description="Get all documents uploaded by a supplier."
)
async def list_supplier_documents(
    supplier_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all documents for a supplier application."""
    if current_user["type"] == "vendor" and current_user["data"]["id"] != supplier_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view documents for your own application"
        )
    
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    documents = await db.get_documents_by_supplier(supplier_id)
    
    return DocumentListResponse(
        items=documents,
        total=len(documents)
    )


@router.get(
    "/addable/{supplier_id}",
    response_model=AddableDocumentsResponse,
    summary="Get addable document types",
    description=(
        "Returns document types that an approved supplier has not yet uploaded. "
        "Results are categorised as mandatory, category-specific, sustainability, or other "
        "so the frontend can group them meaningfully."
    )
)
async def get_addable_documents(supplier_id: str):
    """
    List document types the supplier can still add post-approval.

    Only works for APPROVED suppliers.  The endpoint subtracts already-uploaded
    types from the full set of uploadable types and categorises what remains.
    """
    from ...models.enums import (
        DocumentType as DocTypeEnum,
        MANDATORY_DOCUMENTS,
        CATEGORY_DOCUMENTS,
        SUSTAINABILITY_DOC_TYPES,
        BusinessCategory,
    )

    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    # Document types that only admins can upload — never presented to suppliers
    admin_only_types = {DocTypeEnum.EVALUATION_FORM.value}

    # Types the supplier has already uploaded
    existing_docs = await db.get_documents_by_supplier(supplier_id)
    uploaded_types = {doc["document_type"] for doc in existing_docs}

    # Build category lookup sets for this supplier's business category
    try:
        category = BusinessCategory(supplier["business_category"])
    except (ValueError, KeyError):
        category = None

    mandatory_set = {dt.value for dt in MANDATORY_DOCUMENTS}
    category_docs_set = {dt.value for dt in (CATEGORY_DOCUMENTS.get(category, []) if category else [])}
    sustainability_set = {dt.value for dt in SUSTAINABILITY_DOC_TYPES}

    items: list[AddableDocumentItem] = []
    for dt in DocTypeEnum:
        if dt.value in admin_only_types:
            continue
        if dt.value in uploaded_types:
            continue

        if dt.value in mandatory_set:
            cat = "mandatory"
        elif dt.value in category_docs_set:
            cat = "category_specific"
        elif dt.value in sustainability_set:
            cat = "sustainability"
        else:
            cat = "other"

        items.append(AddableDocumentItem(
            document_type=dt.value,
            display_name=dt.value.replace("_", " ").title(),
            category=cat,
            is_sustainability=dt.value in sustainability_set,
        ))

    # Sort: sustainability first, then mandatory, category-specific, other
    sort_order = {"sustainability": 0, "mandatory": 1, "category_specific": 2, "other": 3}
    items.sort(key=lambda x: sort_order.get(x.category, 99))

    return AddableDocumentsResponse(
        supplier_id=supplier_id,
        addable_documents=items,
        total_addable=len(items),
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
    description="Get details of a specific document."
)
async def get_document(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get document details by ID."""
    document = await db.get_document_by_id(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    if current_user["type"] == "vendor" and current_user["data"]["id"] != document["supplier_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own documents"
        )
    return document


@router.get(
    "/{document_id}/download-url",
    response_model=PresignedDownloadUrlResponse,
    summary="Get download URL",
    description="Get a presigned URL to download a document."
)
async def get_download_url(
    document_id: str,
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Generate a presigned URL for downloading a document."""
    document = await db.get_document_by_id(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Get supplier info for audit log
    supplier = await db.get_supplier_by_id(document["supplier_id"])
    
    try:
        download_data = storage_service.generate_presigned_download_url(
            file_path=document["s3_key"],
            expires_in=3600,
        )
        
        # Log document download
        await audit_service.log_action(
            action=AuditAction.DOCUMENT_DOWNLOADED,
            resource_type=AuditResourceType.DOCUMENT,
            user_id=current_admin["id"],
            user_type="admin",
            resource_id=document_id,
            resource_name=document["file_name"],
            metadata={
                "document_type": document["document_type"],
                "file_name": document["file_name"],
                "content_type": document["content_type"],
                "supplier_id": document["supplier_id"],
                "supplier_name": supplier.get("company_name") if supplier else None
            },
            ip_address=get_client_ip(http_request) if http_request else None
        )
        
        return PresignedDownloadUrlResponse(
            download_url=download_data["download_url"],
            filename=document["file_name"],
            expires_in=download_data["expires_in"],
        )
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/{document_id}/view-url",
    response_model=dict,
    summary="Get view URL",
    description="Get a presigned URL to view a document inline (e.g., PDF in browser)."
)
async def get_view_url(
    document_id: str,
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Generate a presigned URL for viewing a document inline."""
    document = await db.get_document_by_id(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Get supplier info for audit log
    supplier = await db.get_supplier_by_id(document["supplier_id"])
    
    try:
        # Use the same download URL for viewing
        view_data = storage_service.generate_presigned_download_url(
            file_path=document["s3_key"],
            expires_in=3600,
        )
        
        # Log document view
        await audit_service.log_action(
            action=AuditAction.DOCUMENT_VIEWED,
            resource_type=AuditResourceType.DOCUMENT,
            user_id=current_admin["id"],
            user_type="admin",
            resource_id=document_id,
            resource_name=document["file_name"],
            metadata={
                "document_type": document["document_type"],
                "file_name": document["file_name"],
                "content_type": document["content_type"],
                "supplier_id": document["supplier_id"],
                "supplier_name": supplier.get("company_name") if supplier else None
            },
            ip_address=get_client_ip(http_request) if http_request else None
        )
        
        return {
            "view_url": view_data["download_url"],
            "content_type": document["content_type"],
            "filename": document["file_name"],
            "expires_in": view_data["expires_in"],
        }
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete(
    "/{document_id}",
    response_model=SuccessResponse,
    summary="Delete document",
    description="Delete a document. Only allowed for applications in INCOMPLETE or NEED_MORE_INFO status."
)
async def delete_document(
    document_id: str,
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Delete a document from the application.
    
    Only allowed when the supplier application is in INCOMPLETE or NEED_MORE_INFO status.
    """
    document = await db.get_document_by_id(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check supplier status
    supplier = await db.get_supplier_by_id(document["supplier_id"])
    allowed_statuses = [
        SupplierStatus.INCOMPLETE.value,
        SupplierStatus.NEED_MORE_INFO.value
    ]
    if supplier["status"] not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete documents for this application status"
        )
    
    # Delete from S3
    try:
        storage_service.delete_file(document["s3_key"])
    except Exception as e:
        logger.warning("Failed to delete file from S3: %s", e)
        # Continue anyway to clean up database
    
    # Delete from database
    await db.delete_document(document_id)
    
    # Log document deletion with new audit service
    await audit_service.log_action(
        action=AuditAction.DOCUMENT_DELETED,
        resource_type=AuditResourceType.DOCUMENT,
        user_id=current_admin["id"],
        user_type="admin",
        resource_id=document_id,
        resource_name=document.get("file_name"),
        metadata={
            "document_type": document["document_type"],
            "file_name": document.get("file_name"),
            "supplier_id": document["supplier_id"],
            "supplier_name": supplier.get("company_name"),
            "deleted_by_admin": True
        },
        ip_address=get_client_ip(http_request) if http_request else None
    )
    
    return SuccessResponse(
        success=True,
        message="Document deleted successfully"
    )


