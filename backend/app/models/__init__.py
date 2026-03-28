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
    # New enums
    SupplierType,
    BusinessSize,
    Gender,
    KeyPersonRole,
    ComplianceLevel,
    LandProofType,
    # Document lists
    MANDATORY_DOCUMENTS,
    LOCAL_MANDATORY_DOCUMENTS,
    FOREIGN_MANDATORY_DOCUMENTS,
    FARMER_MANDATORY_DOCUMENTS,
    CATEGORY_DOCUMENTS,
    SUSTAINABILITY_DOCUMENTS,
    EXPIRY_REQUIRED_DOCUMENT_TYPES,
    NO_EXPIRY_DOCUMENT_TYPES,
    LEGACY_CATEGORIES,
    # Cert group structure
    CertGroup,
    CERT_GROUPS_BY_CATEGORY,
    # Helpers
    get_required_documents,
    get_sustainability_documents,
    get_supplier_type,
    get_statutory_documents,
    compute_business_size,
    compute_esg_flags,
    compute_compliance_level,
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
    AdminRegisterSupplierRequest,
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
    AddableDocumentItem,
    AddableDocumentsResponse,
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
    "SUSTAINABILITY_DOCUMENTS",
    "get_required_documents",
    "get_sustainability_documents",
    
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
    "AddableDocumentItem",
    "AddableDocumentsResponse",
    
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

