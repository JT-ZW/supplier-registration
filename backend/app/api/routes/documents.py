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
from ...api.deps import get_client_ip, get_current_admin
from ...models import (
    DocumentUploadRequest,
    DocumentMetadataCreateRequest,
    PresignedUrlResponse,
    PresignedDownloadUrlResponse,
    DocumentResponse,
    DocumentListResponse,
    SuccessResponse,
    SupplierStatus,
    DocumentVerificationStatus,
)
from ...models.audit import AuditAction, AuditResourceType
from ...core.storage import storage_service
from ...core.config import settings


router = APIRouter(prefix="/documents", tags=["Documents"])

# Initialize audit service
audit_service = AuditService()


@router.post(
    "/upload-url",
    response_model=PresignedUrlResponse,
    summary="Get presigned upload URL",
    description="Generate a presigned URL for uploading a document directly to cloud storage."
)
async def get_upload_url(request: DocumentUploadRequest):
    """
    Generate a presigned URL for direct file upload to S3.
    
    The client will use this URL to upload the file directly to cloud storage,
    bypassing the backend for the actual file transfer.
    """
    # DEBUG: Log incoming request
    print(f"🔍 DEBUG - Upload URL Request:")
    print(f"   supplier_id: {request.supplier_id}")
    print(f"   document_type: {request.document_type}")
    print(f"   filename: {request.filename}")
    print(f"   file_size: {request.file_size}")
    print(f"   content_type: {request.content_type}")
    
    # Validate supplier exists and is in correct status
    supplier = await db.get_supplier_by_id(request.supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    allowed_statuses = [
        SupplierStatus.INCOMPLETE.value,
        SupplierStatus.NEED_MORE_INFO.value
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
    
    # Check if document type already uploaded
    existing_docs = await db.get_documents_by_supplier(request.supplier_id)
    for doc in existing_docs:
        if doc["document_type"] == request.document_type.value:
            # Delete existing document record (will be replaced)
            await db.delete_document(doc["id"])
            break
    
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
async def confirm_upload(request: DocumentMetadataCreateRequest, http_request: Request):
    """
    Confirm document upload and save metadata to database.
    
    This should be called after the client successfully uploads
    the file to the presigned URL.
    """
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
    print(f"🔍 Verifying file exists in storage: {file_key}")
    if not storage_service.file_exists(file_key):
        print(f"❌ File not found in storage: {file_key}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File not found in storage. Please re-upload the document."
        )
    print(f"✅ File verified in storage: {file_key}")
    
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
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    
    document = await db.create_document(document_data)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save document metadata"
        )
    
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
                    title="New Document Uploaded",
                    message=f"{supplier.get('company_name', 'A supplier')} uploaded {doc_type_display}",
                    action_url=f"/admin/suppliers/{request.supplier_id}",
                    action_label="Review Document",
                    resource_type="document",
                    resource_id=UUID(document["id"]),
                    metadata={
                        "document_type": request.document_type.value,
                        "filename": request.filename,
                        "supplier_id": request.supplier_id,
                        "supplier_name": supplier.get("company_name")
                    },
                    send_email=False  # Don't spam admins with emails for every upload
                )
                
                await notification_service.create_bulk_notifications(bulk_notification)
        except Exception as e:
            print(f"Failed to send document upload notifications: {e}")
    
    asyncio.create_task(notify_admins_of_upload())
    
    return document


@router.get(
    "/supplier/{supplier_id}",
    response_model=DocumentListResponse,
    summary="List supplier documents",
    description="Get all documents uploaded by a supplier."
)
async def list_supplier_documents(supplier_id: str):
    """Get all documents for a supplier application."""
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
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
    description="Get details of a specific document."
)
async def get_document(document_id: str):
    """Get document details by ID."""
    document = await db.get_document_by_id(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
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
        print(f"Failed to delete file from S3: {e}")
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
