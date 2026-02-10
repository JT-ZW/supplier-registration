"""Document Expiry Models"""
from datetime import date, datetime
from typing import Optional, Literal
from uuid import UUID
from pydantic import BaseModel, Field


class DocumentExpiryAlert(BaseModel):
    """Document expiry alert model"""
    id: UUID
    document_id: UUID
    supplier_id: UUID
    alert_type: Literal["90_days", "60_days", "30_days", "7_days", "1_day", "expired"]
    alert_date: datetime
    expiry_date: date
    email_sent: bool
    email_sent_at: Optional[datetime] = None
    acknowledged: bool
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[UUID] = None
    reminder_count: int
    last_reminder_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExpiringDocument(BaseModel):
    """Expiring document details"""
    document_id: UUID
    supplier_id: UUID
    company_name: str
    email: str
    document_type: str
    expiry_date: date
    days_until_expiry: int
    file_url: Optional[str] = None
    supplier_status: str

    class Config:
        from_attributes = True


class ExpiredDocument(BaseModel):
    """Expired document details"""
    document_id: UUID
    supplier_id: UUID
    company_name: str
    email: str
    document_type: str
    expiry_date: date
    days_since_expiry: int
    file_url: Optional[str] = None
    supplier_status: str

    class Config:
        from_attributes = True


class SupplierExpiringDocument(BaseModel):
    """Expiring document for a specific supplier"""
    document_id: UUID
    document_type: str
    expiry_date: date
    days_until_expiry: int
    alert_count: int
    last_alert_date: Optional[datetime] = None
    acknowledged: bool

    class Config:
        from_attributes = True


class PendingAlert(BaseModel):
    """Pending alert needing notification"""
    alert_id: UUID
    document_id: UUID
    supplier_id: UUID
    company_name: str
    email: str
    document_type: str
    expiry_date: date
    alert_type: str
    days_until_expiry: int

    class Config:
        from_attributes = True


class ExpiryAlertStats(BaseModel):
    """Statistics for document expiry alerts"""
    total_alerts: int
    pending_alerts: int
    sent_alerts: int
    acknowledged_alerts: int
    expired_documents: int
    critical_alerts: int
    warning_alerts: int

    class Config:
        from_attributes = True


class CreateAlertsResponse(BaseModel):
    """Response from creating alerts"""
    alerts_created: int
    documents_processed: int


class AcknowledgeAlertRequest(BaseModel):
    """Request to acknowledge an alert"""
    alert_id: UUID


class ExpiryDashboardSummary(BaseModel):
    """Summary for expiry dashboard widget"""
    critical_count: int  # Expiring in 7 days or less
    warning_count: int   # Expiring in 30 days or less
    info_count: int      # Expiring in 90 days or less
    expired_count: int   # Already expired
    documents: list[SupplierExpiringDocument] = Field(default_factory=list)
