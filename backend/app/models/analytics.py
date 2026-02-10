"""
Analytics-related Pydantic models for request/response validation.
"""

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field

from .enums import BusinessCategory, SupplierStatus, SupplierActivityStatus


# ============== Request Models ==============

class DateRangeRequest(BaseModel):
    """Request model for date range filtering."""
    start_date: Optional[date] = Field(None, description="Start date for the report")
    end_date: Optional[date] = Field(None, description="End date for the report")


class SupplierReportFilterRequest(BaseModel):
    """Request model for supplier report filters."""
    start_date: Optional[date] = Field(None, description="Start date filter")
    end_date: Optional[date] = Field(None, description="End date filter")
    status: Optional[List[SupplierStatus]] = Field(None, description="Filter by supplier status")
    category: Optional[List[BusinessCategory]] = Field(None, description="Filter by business category")
    location: Optional[str] = Field(None, description="Filter by location (city or country)")
    min_years_in_business: Optional[int] = Field(None, description="Minimum years in business")
    max_years_in_business: Optional[int] = Field(None, description="Maximum years in business")


class ExportReportRequest(BaseModel):
    """Request model for exporting reports."""
    report_type: str = Field(..., description="Type of report to export")
    format: str = Field(default="csv", description="Export format (csv or xlsx)")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    filters: Optional[dict] = None


# ============== Response Models ==============

class OverviewStatsResponse(BaseModel):
    """Response model for overview analytics."""
    total_suppliers: int
    total_approved: int
    total_pending: int
    total_rejected: int
    total_active: int
    total_inactive: int
    applications_this_month: int
    approvals_this_month: int


class CategoryStatsResponse(BaseModel):
    """Response model for category-based statistics."""
    category: BusinessCategory
    category_display: str
    total_count: int
    approved_count: int
    pending_count: int
    rejected_count: int
    percentage: float


class CategoryStatsListResponse(BaseModel):
    """Response model for list of category statistics."""
    items: List[CategoryStatsResponse]
    total_suppliers: int


class LocationStatsResponse(BaseModel):
    """Response model for location-based statistics."""
    location: str
    total_count: int
    approved_count: int
    pending_count: int
    percentage: float


class LocationStatsListResponse(BaseModel):
    """Response model for list of location statistics."""
    items: List[LocationStatsResponse]
    total_suppliers: int


class YearsInBusinessStatsResponse(BaseModel):
    """Response model for years in business ranking."""
    range_label: str  # e.g., "0-5 years", "5-10 years", "10+ years"
    min_years: int
    max_years: Optional[int]
    count: int
    percentage: float


class YearsInBusinessListResponse(BaseModel):
    """Response model for years in business distribution."""
    items: List[YearsInBusinessStatsResponse]
    total_suppliers: int
    average_years: float


class ActivityStatsResponse(BaseModel):
    """Response model for supplier activity statistics."""
    year: int
    month: Optional[int] = None
    month_name: Optional[str] = None
    active_count: int
    inactive_count: int
    new_registrations: int
    new_approvals: int


class ActivityStatsListResponse(BaseModel):
    """Response model for activity statistics over time."""
    items: List[ActivityStatsResponse]
    period: str  # "monthly" or "yearly"


class StatusDistributionResponse(BaseModel):
    """Response model for status distribution."""
    status: SupplierStatus
    status_display: str
    count: int
    percentage: float


class StatusDistributionListResponse(BaseModel):
    """Response model for status distribution list."""
    items: List[StatusDistributionResponse]
    total: int


class TopSuppliersResponse(BaseModel):
    """Response model for top suppliers ranking."""
    id: str
    name: str
    location: str
    category: BusinessCategory
    years_in_business: int
    status: SupplierStatus
    created_at: datetime


class TopSuppliersListResponse(BaseModel):
    """Response model for top suppliers list."""
    items: List[TopSuppliersResponse]
    ranking_criteria: str


class MonthlyTrendResponse(BaseModel):
    """Response model for monthly trend data."""
    month: str
    year: int
    registrations: int
    approvals: int
    rejections: int


class MonthlyTrendListResponse(BaseModel):
    """Response model for monthly trends."""
    items: List[MonthlyTrendResponse]
    period_months: int


class WeeklyTrendResponse(BaseModel):
    """Response model for weekly trend data."""
    week_label: str
    year: int
    week_number: int
    week_start: date
    registrations: int
    approvals: int
    rejections: int


class WeeklyTrendListResponse(BaseModel):
    """Response model for weekly trends."""
    items: List[WeeklyTrendResponse]
    period_weeks: int


class DashboardSummaryResponse(BaseModel):
    """Comprehensive dashboard summary response."""
    overview: OverviewStatsResponse
    category_distribution: List[CategoryStatsResponse]
    location_distribution: List[LocationStatsResponse]
    status_distribution: List[StatusDistributionResponse]
    recent_applications: List[dict]  # List of recent supplier applications
    recent_registrations: int
    pending_reviews: int
    last_updated: datetime
