"""
Document-related Pydantic models for request/response validation.
"""

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator

from .enums import (
    DocumentType,
    DocumentVerificationStatus,
    EXPIRY_REQUIRED_DOCUMENT_TYPES,
)


EXPIRY_REQUIRED_TYPES = set(EXPIRY_REQUIRED_DOCUMENT_TYPES)


# ============== Request Models ==============

class DocumentUploadRequest(BaseModel):
    """Request model for getting a presigned upload URL."""
    supplier_id: str = Field(..., alias="supplierId", description="Supplier application ID")
    document_type: DocumentType = Field(..., alias="documentType", description="Type of document being uploaded")
    filename: str = Field(..., alias="fileName", min_length=1, max_length=255, description="Original filename")
    content_type: str = Field(..., alias="contentType", description="MIME type of the file")
    file_size: int = Field(..., alias="fileSize", gt=0, description="File size in bytes")
    expiry_date: Optional[date] = Field(None, alias="expiryDate", description="Expiry date as printed on the document (informational only at URL-generation stage).")
    
    model_config = {"populate_by_name": True}  # Accept both snake_case and camelCase
    
    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate and sanitize filename."""
        # Remove any path separators
        v = v.replace("/", "").replace("\\", "")
        # Check for valid extension
        valid_extensions = [".pdf", ".jpg", ".jpeg", ".png"]
        if not any(v.lower().endswith(ext) for ext in valid_extensions):
            raise ValueError(f"File must have one of these extensions: {', '.join(valid_extensions)}")
        return v
    
    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        """Validate content type."""
        allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/jpg"]
        if v not in allowed_types:
            raise ValueError(f"Content type must be one of: {', '.join(allowed_types)}")
        return v

    # NOTE: expiry_date is NOT validated here. The upload-url endpoint only generates
    # a presigned storage URL and does not persist metadata. Expiry date validation
    # is enforced after the file is physically uploaded, in DocumentMetadataCreateRequest.


# Document types where the expiry date field is displayed on the frontend but is not
# mandatory to submit (e.g. ID cards that may or may not carry an expiry date).
_OPTIONAL_EXPIRY_TYPES = {
    DocumentType.ID_PASSPORT_COPY,
}


class DocumentMetadataCreateRequest(BaseModel):
    """Request model for saving document metadata after successful upload."""
    supplier_id: str = Field(..., alias="supplierId", description="Supplier application ID")
    document_type: DocumentType = Field(..., alias="documentType", description="Type of document")
    file_key: Optional[str] = Field(None, alias="fileKey", description="File path in storage")
    filename: str = Field(..., alias="fileName", description="Original filename")
    file_size: int = Field(..., alias="fileSize", gt=0, description="File size in bytes")
    content_type: str = Field(..., alias="contentType", description="MIME type")
    expiry_date: Optional[date] = Field(None, alias="expiryDate", description="Expiry date as printed on the document (supplier-entered; confirmed by admin during verification)")
    
    model_config = {"populate_by_name": True}  # Accept both snake_case and camelCase

    @model_validator(mode="after")
    def validate_expiry_date_required(self):
        """Require expiry date for document types that must be tracked for expiry.

        ID_PASSPORT_COPY is treated as optional-expiry because director ID/passport
        uploads do not collect an expiry date at registration time (the admin can
        record it during document verification).  All other expiry-required document
        types must supply a date.
        """
        if (
            self.document_type in EXPIRY_REQUIRED_TYPES
            and self.document_type not in _OPTIONAL_EXPIRY_TYPES
            and self.expiry_date is None
        ):
            raise ValueError(f"expiryDate is required for document type {self.document_type.value}")
        return self


class DocumentVerifyRequest(BaseModel):
    """Request model for admin to verify/reject a document."""
    status: DocumentVerificationStatus = Field(..., description="New verification status")
    rejection_reason: Optional[str] = Field(None, max_length=500, description="Reason for rejection if applicable")
    expiry_date: Optional[date] = Field(None, description="Admin-confirmed expiry date (admin can correct what the supplier entered)")
    
    @field_validator("rejection_reason")
    @classmethod
    def validate_rejection_reason(cls, v: Optional[str], info) -> Optional[str]:
        """Ensure rejection reason is provided when rejecting."""
        if info.data.get("status") == DocumentVerificationStatus.REJECTED and not v:
            raise ValueError("Rejection reason is required when rejecting a document")
        return v


# ============== Response Models ==============

class PresignedUrlResponse(BaseModel):
    """Response model for presigned URL generation."""
    upload_url: str = Field(..., description="Presigned URL for uploading")
    file_key: str = Field(..., description="File path in storage (file_key for backward compatibility)")
    expires_in: int = Field(..., description="URL expiration time in seconds")
    fields: Optional[str] = Field(None, description="Token or additional fields for upload")


class PresignedDownloadUrlResponse(BaseModel):
    """Response model for presigned download URL."""
    download_url: str = Field(..., description="Presigned URL for downloading/viewing")
    filename: str = Field(..., description="Original filename")
    expires_in: int = Field(..., description="URL expiration time in seconds")


class DocumentResponse(BaseModel):
    """Response model for document data."""
    id: str
    supplier_id: str
    document_type: DocumentType
    file_key: str = Field(..., alias="s3_key")  # Database uses s3_key
    filename: str = Field(..., alias="file_name")  # Database uses file_name
    file_size: int
    content_type: str
    verification_status: DocumentVerificationStatus
    verification_comments: Optional[str] = None
    uploaded_at: datetime
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    expiry_date: Optional[date] = None
    # Archival tracking (for replaced documents)
    is_archived: bool = Field(False, description="True if this document has been replaced by a newer upload")
    archived_at: Optional[datetime] = Field(None, description="Timestamp when document was archived")
    replaced_by: Optional[str] = Field(None, description="ID of the document that replaced this one")
    # Supplementary document tracking
    is_supplementary: bool = Field(False, description="True if uploaded post-approval, not part of original registration")
    added_post_approval_at: Optional[datetime] = Field(None, description="Timestamp of post-approval upload")
    
    model_config = {"from_attributes": True, "populate_by_name": True}


class DocumentListResponse(BaseModel):
    """Response model for list of documents."""
    items: List[DocumentResponse]
    total: int


class DocumentUploadStatusResponse(BaseModel):
    """Response model showing upload status for all required documents."""
    document_type: DocumentType
    document_type_display: str
    is_mandatory: bool
    is_uploaded: bool
    verification_status: Optional[DocumentVerificationStatus] = None
    rejection_reason: Optional[str] = None
    uploaded_at: Optional[datetime] = None


class SupplierDocumentStatusResponse(BaseModel):
    """Response model showing document upload progress for a supplier."""
    supplier_id: str
    category: str
    documents: List[DocumentUploadStatusResponse]
    total_required: int
    total_uploaded: int
    total_verified: int
    is_complete: bool


class AddableDocumentItem(BaseModel):
    """A single document type that an approved supplier can still add."""
    document_type: str = Field(..., description="DocumentType enum value")
    display_name: str = Field(..., description="Human-readable document name")
    category: str = Field(
        ...,
        description="Classification: 'mandatory', 'category_specific', 'sustainability', or 'other'"
    )
    is_sustainability: bool = Field(
        False,
        description="True if this document contributes to sustainability reporting"
    )


class AddableDocumentsResponse(BaseModel):
    """Response model listing all document types an approved supplier has not yet uploaded."""
    supplier_id: str
    addable_documents: List[AddableDocumentItem]
    total_addable: int
