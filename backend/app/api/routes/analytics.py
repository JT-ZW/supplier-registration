"""
Analytics and reporting API routes.
These endpoints provide statistics and insights for the admin dashboard.
"""

from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query

from ...db.supabase import db
from ...models import (
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
    DashboardSummaryResponse,
    MonthlyTrendResponse,
    MonthlyTrendListResponse,
    BusinessCategory,
    SupplierStatus,
)
from ...api.deps import get_current_admin


router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/overview",
    response_model=OverviewStatsResponse,
    summary="Get overview statistics",
    description="Get high-level overview statistics for the dashboard."
)
async def get_overview_stats(current_admin: dict = Depends(get_current_admin)):
    """Get overview statistics."""
    stats = await db.get_overview_stats()
    return OverviewStatsResponse(**stats)


@router.get(
    "/categories",
    response_model=CategoryStatsListResponse,
    summary="Get category statistics",
    description="Get supplier count and breakdown by business category."
)
async def get_category_stats(current_admin: dict = Depends(get_current_admin)):
    """Get statistics grouped by business category."""
    data = await db.get_supplier_count_by_category()
    
    # Calculate total for percentage
    total = sum(item["total_count"] for item in data)
    
    items = []
    for item in data:
        category = BusinessCategory(item["category"])
        items.append(CategoryStatsResponse(
            category=category,
            category_display=category.value.replace("_", " ").title(),
            total_count=item["total_count"],
            approved_count=item["approved_count"],
            pending_count=item["pending_count"],
            rejected_count=item["rejected_count"],
            percentage=round((item["total_count"] / total * 100), 2) if total > 0 else 0.0,
        ))
    
    return CategoryStatsListResponse(
        items=items,
        total_suppliers=total
    )


@router.get(
    "/locations",
    response_model=LocationStatsListResponse,
    summary="Get location statistics",
    description="Get supplier count and breakdown by location."
)
async def get_location_stats(current_admin: dict = Depends(get_current_admin)):
    """Get statistics grouped by location."""
    data = await db.get_location_stats()
    
    # The function returns location, count, percentage already calculated
    items = []
    total_suppliers = 0
    for item in data:
        # get_location_stats returns: location, count, percentage
        # We need to query for approved/pending counts separately or adjust the model
        items.append(LocationStatsResponse(
            location=item["location"],
            total_count=item["count"],
            approved_count=0,  # Not provided by get_location_stats
            pending_count=0,  # Not provided by get_location_stats
            percentage=float(item["percentage"]) if item["percentage"] else 0.0,
        ))
        total_suppliers += item["count"]
    
    return LocationStatsListResponse(
        items=items,
        total_suppliers=total_suppliers
    )


@router.get(
    "/years-in-business",
    response_model=YearsInBusinessListResponse,
    summary="Get years in business distribution",
    description="Get distribution of suppliers by years in business."
)
async def get_years_in_business_stats(current_admin: dict = Depends(get_current_admin)):
    """Get statistics grouped by years in business ranges."""
    # Get all suppliers
    suppliers_result = await db.list_suppliers(
        page=1,
        page_size=10000  # Get all for analysis
    )
    suppliers = suppliers_result["items"]
    
    # Define ranges
    ranges = [
        {"label": "0-2 years", "min": 0, "max": 2},
        {"label": "3-5 years", "min": 3, "max": 5},
        {"label": "6-10 years", "min": 6, "max": 10},
        {"label": "11-20 years", "min": 11, "max": 20},
        {"label": "20+ years", "min": 21, "max": None},
    ]
    
    total = len(suppliers)
    average_years = sum(s["years_in_business"] for s in suppliers) / total if total > 0 else 0
    
    items = []
    for range_def in ranges:
        if range_def["max"] is None:
            count = len([s for s in suppliers if s["years_in_business"] >= range_def["min"]])
        else:
            count = len([
                s for s in suppliers
                if range_def["min"] <= s["years_in_business"] <= range_def["max"]
            ])
        
        items.append(YearsInBusinessStatsResponse(
            range_label=range_def["label"],
            min_years=range_def["min"],
            max_years=range_def["max"],
            count=count,
            percentage=round((count / total * 100), 2) if total > 0 else 0.0,
        ))
    
    return YearsInBusinessListResponse(
        items=items,
        total_suppliers=total,
        average_years=round(average_years, 1)
    )


@router.get(
    "/status-distribution",
    response_model=StatusDistributionListResponse,
    summary="Get status distribution",
    description="Get count of suppliers by application status."
)
async def get_status_distribution(current_admin: dict = Depends(get_current_admin)):
    """Get distribution of suppliers by status."""
    data = await db.get_status_distribution()
    
    total = sum(item["count"] for item in data)
    
    items = []
    for item in data:
        status_enum = SupplierStatus(item["status"])
        items.append(StatusDistributionResponse(
            status=status_enum,
            status_display=status_enum.value.replace("_", " ").title(),
            count=item["count"],
            percentage=round((item["count"] / total * 100), 2) if total > 0 else 0.0,
        ))
    
    return StatusDistributionListResponse(
        items=items,
        total=total
    )


@router.get(
    "/monthly-trends",
    response_model=MonthlyTrendListResponse,
    summary="Get monthly trends",
    description="Get monthly registration, approval, and rejection trends."
)
async def get_monthly_trends(
    year: int = Query(default=datetime.now().year, ge=2020, le=2100),
    current_admin: dict = Depends(get_current_admin)
):
    """Get monthly trends for a specific year."""
    # get_monthly_trends uses months_back parameter, not year
    # Calculate months back from current date to the start of the requested year
    current_date = datetime.now()
    months_back = (current_date.year - year) * 12 + current_date.month
    months_back = max(12, months_back)  # At least 12 months
    
    data = await db.get_monthly_trends(months_back)
    
    # Filter to only include the requested year
    items = []
    for item in data:
        if item["year"] == year:
            items.append(MonthlyTrendResponse(
                month=item["month"].strip(),
                year=item["year"],
                registrations=item["submitted"],
                approvals=item["approved"],
                rejections=item["rejected"],
            ))
    
    return MonthlyTrendListResponse(
        items=items,
        period_months=len(items)
    )


@router.get(
    "/dashboard-summary",
    response_model=DashboardSummaryResponse,
    summary="Get complete dashboard summary",
    description="Get all key metrics for the admin dashboard in one call."
)
async def get_dashboard_summary(current_admin: dict = Depends(get_current_admin)):
    """Get comprehensive dashboard summary with all key metrics."""
    # Get overview stats
    overview_data = await db.get_overview_stats()
    overview = OverviewStatsResponse(**overview_data)
    
    # Get category distribution
    category_data = await db.get_supplier_count_by_category()
    total_suppliers = sum(item["total_count"] for item in category_data)
    category_distribution = [
        CategoryStatsResponse(
            category=BusinessCategory(item["category"]),
            category_display=item["category"].replace("_", " ").title(),
            total_count=item["total_count"],
            approved_count=item["approved_count"],
            pending_count=item["pending_count"],
            rejected_count=item["rejected_count"],
            percentage=round((item["total_count"] / total_suppliers * 100), 2) if total_suppliers > 0 else 0.0,
        )
        for item in category_data[:5]  # Top 5 categories
    ]
    
    # Get location distribution
    location_data = await db.get_location_stats()
    location_distribution = [
        LocationStatsResponse(
            location=item["location"],
            total_count=item["count"],
            approved_count=0,  # Not provided by get_location_stats
            pending_count=0,  # Not provided by get_location_stats
            percentage=float(item["percentage"]) if item["percentage"] else 0.0,
        )
        for item in location_data[:5]  # Top 5 locations
    ]
    
    # Get status distribution
    status_data = await db.get_status_distribution()
    total = sum(item["count"] for item in status_data)
    status_distribution = [
        StatusDistributionResponse(
            status=SupplierStatus(item["status"]),
            status_display=item["status"].replace("_", " ").title(),
            count=item["count"],
            percentage=round((item["count"] / total * 100), 2) if total > 0 else 0.0,
        )
        for item in status_data
    ]
    
    # Count pending reviews
    pending_reviews = sum(
        item["count"] for item in status_data
        if item["status"] in ["SUBMITTED", "UNDER_REVIEW"]
    )
    
    # Get recent applications (last 10, ordered by created_at or submitted_at)
    recent_apps_result = await db.list_suppliers(
        status=None,  # All statuses
        category=None,
        page=1,
        page_size=10,
    )
    
    # Format recent applications for frontend
    recent_applications = [
        {
            "id": app["id"],
            "companyName": app["company_name"],
            "email": app["email"],
            "status": app["status"],
            "createdAt": app["created_at"],
            "submittedAt": app.get("submitted_at"),
        }
        for app in recent_apps_result.get("items", [])[:10]
    ]
    
    return DashboardSummaryResponse(
        overview=overview,
        category_distribution=category_distribution,
        location_distribution=location_distribution,
        status_distribution=status_distribution,
        recent_applications=recent_applications,
        recent_registrations=overview_data["applications_this_month"],
        pending_reviews=pending_reviews,
        last_updated=datetime.utcnow(),
    )
