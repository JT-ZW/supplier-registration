"""
Pydantic models for request/response validation.
"""

from .enums import (
    SupplierStatus,
    SupplierActivityStatus,
    BusinessCategory,
    DocumentType,
    DocumentVerificationStatus,
    AdminAction,
    MANDATORY_DOCUMENTS,
    CATEGORY_DOCUMENTS,
    get_required_documents,
)

from .supplier import (
    SupplierCreateRequest,
    SupplierUpdateRequest,
    SupplierSubmitRequest,
    SupplierResponse,
    SupplierListResponse,
    RequiredDocumentsResponse,
)

from .document import (
    DocumentUploadRequest,
    DocumentMetadataCreateRequest,
    DocumentVerifyRequest,
    PresignedUrlResponse,
    PresignedDownloadUrlResponse,
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadStatusResponse,
    SupplierDocumentStatusResponse,
)

from .admin import (
    AdminLoginRequest,
    AdminCreateRequest,
    AdminPasswordChangeRequest,
    ApplicationReviewRequest,
    RequestMoreInfoRequest,
    RefreshTokenRequest,
    TokenResponse,
    AdminResponse,
    AdminProfileResponse,
    AuditLogResponse,
    AuditLogListResponse,
    ReviewHistoryResponse,
)

from .analytics import (
    DateRangeRequest,
    ExportReportRequest,
    OverviewStatsResponse,
    CategoryStatsResponse,
    CategoryStatsListResponse,
    LocationStatsResponse,
    LocationStatsListResponse,
    YearsInBusinessStatsResponse,
    YearsInBusinessListResponse,
    ActivityStatsResponse,
    ActivityStatsListResponse,
    StatusDistributionResponse,
    StatusDistributionListResponse,
    TopSuppliersResponse,
    TopSuppliersListResponse,
    MonthlyTrendResponse,
    MonthlyTrendListResponse,
    DashboardSummaryResponse,
)

from .common import (
    SuccessResponse,
    ErrorResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
    PaginatedResponse,
    PaginationParams,
    SortParams,
    FilterParams,
    HealthCheckResponse,
    NotificationPayload,
    FileUploadMetadata,
)


__all__ = [
    # Enums
    "SupplierStatus",
    "SupplierActivityStatus",
    "BusinessCategory",
    "DocumentType",
    "DocumentVerificationStatus",
    "AdminAction",
    "MANDATORY_DOCUMENTS",
    "CATEGORY_DOCUMENTS",
    "get_required_documents",
    
    # Supplier models
    "SupplierCreateRequest",
    "SupplierUpdateRequest",
    "SupplierSubmitRequest",
    "SupplierResponse",
    "SupplierListResponse",
    "RequiredDocumentsResponse",
    
    # Document models
    "DocumentUploadRequest",
    "DocumentMetadataCreateRequest",
    "DocumentVerifyRequest",
    "PresignedUrlResponse",
    "PresignedDownloadUrlResponse",
    "DocumentResponse",
    "DocumentListResponse",
    "DocumentUploadStatusResponse",
    "SupplierDocumentStatusResponse",
    
    # Admin models
    "AdminLoginRequest",
    "AdminCreateRequest",
    "AdminPasswordChangeRequest",
    "ApplicationReviewRequest",
    "RequestMoreInfoRequest",
    "RefreshTokenRequest",
    "TokenResponse",
    "AdminResponse",
    "AdminProfileResponse",
    "AuditLogResponse",
    "AuditLogListResponse",
    "ReviewHistoryResponse",
    
    # Analytics models
    "DateRangeRequest",
    "ExportReportRequest",
    "OverviewStatsResponse",
    "CategoryStatsResponse",
    "CategoryStatsListResponse",
    "LocationStatsResponse",
    "LocationStatsListResponse",
    "YearsInBusinessStatsResponse",
    "YearsInBusinessListResponse",
    "ActivityStatsResponse",
    "ActivityStatsListResponse",
    "StatusDistributionResponse",
    "StatusDistributionListResponse",
    "TopSuppliersResponse",
    "TopSuppliersListResponse",
    "MonthlyTrendResponse",
    "MonthlyTrendListResponse",
    "DashboardSummaryResponse",
    
    # Common models
    "SuccessResponse",
    "ErrorResponse",
    "ValidationErrorDetail",
    "ValidationErrorResponse",
    "PaginatedResponse",
    "PaginationParams",
    "SortParams",
    "FilterParams",
    "HealthCheckResponse",
    "NotificationPayload",
    "FileUploadMetadata",
]
