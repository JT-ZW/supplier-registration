"""
Common/shared Pydantic models used across the application.
"""

from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel, Field


T = TypeVar("T")


class SuccessResponse(BaseModel):
    """Standard success response."""
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    error: str
    error_code: Optional[str] = None
    details: Optional[dict] = None


class ValidationErrorDetail(BaseModel):
    """Validation error detail."""
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    """Validation error response."""
    success: bool = False
    error: str = "Validation Error"
    errors: List[ValidationErrorDetail]


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size


class SortParams(BaseModel):
    """Sorting parameters."""
    sort_by: str = Field(default="created_at", description="Field to sort by")
    sort_order: str = Field(default="desc", description="Sort order (asc or desc)")
    
    @property
    def is_descending(self) -> bool:
        """Check if sort order is descending."""
        return self.sort_order.lower() == "desc"


class FilterParams(BaseModel):
    """Common filter parameters."""
    search: Optional[str] = Field(None, description="Search query")
    status: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    environment: str
    database: str = "connected"
    storage: str = "connected"


class NotificationPayload(BaseModel):
    """Notification payload for email/push notifications."""
    recipient_email: str
    recipient_name: Optional[str] = None
    subject: str
    template: str
    data: dict = Field(default_factory=dict)


class FileUploadMetadata(BaseModel):
    """Metadata for file uploads."""
    filename: str
    content_type: str
    file_size: int
    checksum: Optional[str] = None
