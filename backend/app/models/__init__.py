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
    AdminRole,
    MANDATORY_DOCUMENTS,
    CATEGORY_DOCUMENTS,
    get_required_documents,
)

from .audit import (
    AuditAction,
    AuditResourceType,
    AuditLogCreateRequest,
    AuditLogFilterRequest,
    AuditLogResponse,
    AuditLogListResponse,
    AuditLogStatsResponse,
    AUDIT_ACTION_LABELS,
)

from .notification import (
    NotificationType,
    RecipientType,
    NotificationCreate,
    NotificationResponse,
    NotificationUpdate,
    NotificationListResponse,
    NotificationStatsResponse,
    MarkReadRequest,
    BulkNotificationCreate,
    NOTIFICATION_TYPE_LABELS,
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
    WeeklyTrendResponse,
    WeeklyTrendListResponse,
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

from .expiry import (
    DocumentExpiryAlert,
    ExpiringDocument,
    ExpiredDocument,
    SupplierExpiringDocument,
    PendingAlert,
    ExpiryAlertStats,
    CreateAlertsResponse,
    AcknowledgeAlertRequest,
    ExpiryDashboardSummary,
)

from .profile_change import (
    ProfileChangeRequest,
    ProfileChangeResponse,
    ProfileChangeReviewRequest,
    ProfileChangeListItem,
    ProfileChangeHistoryItem,
)

from .user_management import (
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    AdminPasswordResetRequest,
    AdminUserResponse,
    AdminUserListResponse,
    VendorUserUpdateRequest,
    VendorPasswordResetRequest,
    VendorUserResponse,
    VendorUserListResponse,
    UnlockAccountRequest,
)


__all__ = [
    # Enums
    "SupplierStatus",
    "SupplierActivityStatus",
    "BusinessCategory",
    "DocumentType",
    "DocumentVerificationStatus",
    "AdminAction",
    "AdminRole",
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
    "WeeklyTrendResponse",
    "WeeklyTrendListResponse",
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
    
    # Profile change models
    "ProfileChangeRequest",
    "ProfileChangeResponse",
    "ProfileChangeReviewRequest",
    "ProfileChangeListItem",
    "ProfileChangeHistoryItem",
    
    # Expiry models
    "DocumentExpiryAlert",
    "ExpiringDocument",
    "ExpiredDocument",
    "SupplierExpiringDocument",
    "PendingAlert",
    "ExpiryAlertStats",
    "CreateAlertsResponse",
    "AcknowledgeAlertRequest",
    "ExpiryDashboardSummary",
    
    # Audit models
    "AuditAction",
    "AuditResourceType",
    "AuditLogCreateRequest",
    "AuditLogFilterRequest",
    "AuditLogResponse",
    "AuditLogListResponse",
    "AuditLogStatsResponse",
    "AUDIT_ACTION_LABELS",
    
    # Notification models
    "NotificationType",
    "RecipientType",
    "NotificationCreate",
    "NotificationResponse",
    "NotificationUpdate",
    "NotificationListResponse",
    "NotificationStatsResponse",
    "MarkReadRequest",
    "BulkNotificationCreate",
    "NOTIFICATION_TYPE_LABELS",
    
    # User management models
    "AdminUserCreateRequest",
    "AdminUserUpdateRequest",
    "AdminPasswordResetRequest",
    "AdminUserResponse",
    "AdminUserListResponse",
    "VendorUserUpdateRequest",
    "VendorPasswordResetRequest",
    "VendorUserResponse",
    "VendorUserListResponse",
    "UnlockAccountRequest",
]

