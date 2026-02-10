"""
Report generation API routes.
These endpoints allow admins to generate and download supplier reports.
"""

from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi import status as http_status
from fastapi.responses import StreamingResponse

from ...db.supabase import db
from ...models import BusinessCategory, SupplierStatus
from ...api.deps import get_current_admin
from ...services.reports import report_service
from ...core.timezone import get_cat_timestamp_str


router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "/suppliers/pdf",
    summary="Download supplier report as PDF",
    description="Generate and download a PDF report of suppliers with optional filters."
)
async def download_supplier_pdf_report(
    start_date: Optional[date] = Query(None, description="Filter from this date"),
    end_date: Optional[date] = Query(None, description="Filter to this date"),
    status: Optional[List[SupplierStatus]] = Query(None, description="Filter by status"),
    category: Optional[List[BusinessCategory]] = Query(None, description="Filter by category"),
    location: Optional[str] = Query(None, description="Filter by location (city or country)"),
    min_years_in_business: Optional[int] = Query(None, ge=0, description="Minimum years in business"),
    max_years_in_business: Optional[int] = Query(None, ge=0, description="Maximum years in business"),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Generate and download a PDF report of suppliers.
    
    The report includes:
    - Filtered list of suppliers with detailed information
    - Summary statistics
    - Status and category distributions
    """
    try:
        # Generate PDF
        pdf_buffer = await report_service.generate_pdf_report(
            start_date=start_date,
            end_date=end_date,
            status=status,
            category=category,
            location=location,
            min_years=min_years_in_business,
            max_years=max_years_in_business,
        )
        
        # Generate filename
        timestamp = get_cat_timestamp_str()
        filename = f"supplier_report_{timestamp}.pdf"
        
        # Return as streaming response
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/pdf",
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF report: {str(e)}"
        )


@router.get(
    "/suppliers/excel",
    summary="Download supplier report as Excel",
    description="Generate and download an Excel report of suppliers with optional filters."
)
async def download_supplier_excel_report(
    start_date: Optional[date] = Query(None, description="Filter from this date"),
    end_date: Optional[date] = Query(None, description="Filter to this date"),
    status: Optional[List[SupplierStatus]] = Query(None, description="Filter by status"),
    category: Optional[List[BusinessCategory]] = Query(None, description="Filter by category"),
    location: Optional[str] = Query(None, description="Filter by location (city or country)"),
    min_years_in_business: Optional[int] = Query(None, ge=0, description="Minimum years in business"),
    max_years_in_business: Optional[int] = Query(None, ge=0, description="Maximum years in business"),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Generate and download an Excel report of suppliers.
    
    The report includes multiple sheets:
    - Supplier Details: Complete supplier information
    - Summary: Statistics and distributions
    """
    try:
        # Generate Excel
        excel_buffer = await report_service.generate_excel_report(
            start_date=start_date,
            end_date=end_date,
            status=status,
            category=category,
            location=location,
            min_years=min_years_in_business,
            max_years=max_years_in_business,
        )
        
        # Generate filename
        timestamp = get_cat_timestamp_str()
        filename = f"supplier_report_{timestamp}.xlsx"
        
        # Return as streaming response
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Excel report: {str(e)}"
        )


@router.get(
    "/suppliers/preview",
    summary="Preview report data",
    description="Get a preview of the filtered supplier data before downloading."
)
async def preview_supplier_report(
    start_date: Optional[date] = Query(None, description="Filter from this date"),
    end_date: Optional[date] = Query(None, description="Filter to this date"),
    status: Optional[List[SupplierStatus]] = Query(None, description="Filter by status"),
    category: Optional[List[BusinessCategory]] = Query(None, description="Filter by category"),
    location: Optional[str] = Query(None, description="Filter by location (city or country)"),
    min_years_in_business: Optional[int] = Query(None, ge=0, description="Minimum years in business"),
    max_years_in_business: Optional[int] = Query(None, ge=0, description="Maximum years in business"),
    limit: int = Query(10, ge=1, le=100, description="Number of records to preview"),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Get a preview of filtered suppliers for the report.
    
    This helps users verify their filters before downloading the full report.
    """
    try:
        # Get filtered data
        suppliers = await report_service.get_filtered_suppliers(
            start_date=start_date,
            end_date=end_date,
            status=status,
            category=category,
            location=location,
            min_years=min_years_in_business,
            max_years=max_years_in_business,
        )
        
        # Calculate statistics
        total_count = len(suppliers)
        
        status_counts = {}
        category_counts = {}
        
        for supplier in suppliers:
            s = supplier.get('status', 'Unknown')
            c = supplier.get('category', 'Unknown')
            
            status_counts[s] = status_counts.get(s, 0) + 1
            category_counts[c] = category_counts.get(c, 0) + 1
        
        return {
            "total_count": total_count,
            "preview": suppliers[:limit],
            "filters_applied": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "status": [s.value for s in status] if status else None,
                "category": [c.value for c in category] if category else None,
                "location": location,
                "min_years_in_business": min_years_in_business,
                "max_years_in_business": max_years_in_business,
            },
            "statistics": {
                "status_distribution": [
                    {"status": k, "count": v, "percentage": round((v/total_count)*100, 1)}
                    for k, v in status_counts.items()
                ],
                "category_distribution": [
                    {"category": k, "count": v, "percentage": round((v/total_count)*100, 1)}
                    for k, v in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
                ],
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview report: {str(e)}"
        )
