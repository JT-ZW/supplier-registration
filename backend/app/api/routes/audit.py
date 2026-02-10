"""Audit log API routes."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from datetime import datetime, timedelta
import io
import csv
import os
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER

from app.core.timezone import get_cat_now, format_cat_datetime, get_cat_date_str

from ...api.deps import get_current_admin
from ...db.supabase import get_db, Database
from ...models.audit import (
    AuditLogFilterRequest,
    AuditLogResponse,
    AuditLogListResponse,
    AuditLogStatsResponse,
    AuditAction,
    AuditResourceType
)

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    admin_id: Optional[str] = Query(None, description="Filter by admin ID"),
    supplier_id: Optional[str] = Query(None, description="Filter by supplier/vendor ID"),
    user_type: Optional[str] = Query(None, description="Filter by user type (admin/vendor/system)"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(50, ge=1, le=100, description="Number of results per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db)
):
    """
    Get audit logs with filtering and pagination.
    Admin only.
    """
    result = await db.get_audit_logs(
        admin_id=admin_id,
        supplier_id=supplier_id,
        user_type=user_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )
    
    return AuditLogListResponse(
        items=[AuditLogResponse(**item) for item in result["items"]],
        total=result["total"],
        limit=limit,
        offset=offset
    )


@router.get("/logs/{resource_type}/{resource_id}", response_model=AuditLogListResponse)
async def get_resource_audit_trail(
    resource_type: str,
    resource_id: str,
    limit: int = Query(100, ge=1, le=500, description="Number of results"),
    current_admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db)
):
    """
    Get audit trail for a specific resource.
    Admin only.
    """
    items = await db.get_resource_audit_trail(
        resource_type=resource_type,
        resource_id=resource_id,
        limit=limit
    )
    
    return AuditLogListResponse(
        items=[AuditLogResponse(**item) for item in items],
        total=len(items),
        limit=limit,
        offset=0
    )


@router.get("/recent-activity")
async def get_recent_activity(
    days: int = Query(7, ge=1, le=30, description="Number of days to look back"),
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    current_admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db)
):
    """
    Get recent system activity.
    Admin only.
    """
    items = await db.get_recent_activity(days=days, limit=limit)
    
    return {
        "items": [AuditLogResponse(**item) for item in items],
        "days": days,
        "count": len(items)
    }


@router.get("/statistics", response_model=AuditLogStatsResponse)
async def get_audit_statistics(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    current_admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db)
):
    """
    Get audit log statistics.
    Admin only.
    """
    # Default to last 30 days if no dates provided
    if not start_date:
        start_date = (get_cat_now() - timedelta(days=30)).isoformat()
    if not end_date:
        end_date = get_cat_now().isoformat()
    
    stats = await db.get_audit_statistics(
        start_date=start_date,
        end_date=end_date
    )
    
    # If stats is a list (from RPC function), get the first item
    if isinstance(stats, list) and len(stats) > 0:
        stats = stats[0]
    
    return AuditLogStatsResponse(
        total_actions=stats.get("total_actions", 0),
        actions_by_type=stats.get("actions_by_type", {}),
        actions_by_resource=stats.get("actions_by_resource", {}),
        actions_by_user=stats.get("actions_by_user", {}),
        start_date=start_date,
        end_date=end_date
    )


@router.get("/actions")
async def get_available_actions(
    current_admin: dict = Depends(get_current_admin)
):
    """
    Get list of all available audit actions.
    Admin only.
    """
    from ...models.audit import AUDIT_ACTION_LABELS
    
    return {
        "actions": [
            {
                "value": action.value,
                "label": AUDIT_ACTION_LABELS.get(action, action.value)
            }
            for action in AuditAction
        ]
    }


@router.get("/resource-types")
async def get_available_resource_types(
    current_admin: dict = Depends(get_current_admin)
):
    """
    Get list of all available resource types.
    Admin only.
    """
    return {
        "resource_types": [
            {
                "value": rt.value,
                "label": rt.value.replace("_", " ").title()
            }
            for rt in AuditResourceType
        ]
    }


@router.get("/export")
async def export_audit_logs(
    format: str = Query("excel", description="Export format: excel or pdf"),
    admin_id: Optional[str] = Query(None),
    supplier_id: Optional[str] = Query(None),
    user_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db)
):
    """
    Export audit logs to Excel (CSV) or PDF format with active filters.
    Admin only.
    """
    # Fetch all matching logs (no pagination for export)
    result = await db.get_audit_logs(
        admin_id=admin_id,
        supplier_id=supplier_id,
        user_type=user_type,
        action=action,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        limit=10000,  # High limit for export
        offset=0
    )
    
    logs = result["items"]
    
    if format.lower() == "pdf":
        # Generate PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Add logo
        logo_path = os.path.join(os.path.dirname(__file__), '..', '..', 'core', 'rtg-logo.png')
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=2*inch, height=0.6*inch, kind='proportional')
            elements.append(logo)
            elements.append(Spacer(1, 0.2*inch))
        
        # Title with RTG branding
        title_style = ParagraphStyle(
            'RTGTitle',
            parent=styles['Title'],
            textColor=colors.HexColor('#0066cc'),
            fontSize=20,
            alignment=TA_CENTER,
        )
        title = Paragraph("<b>Rainbow Tourism Group</b><br/>Audit Logs Report", title_style)
        elements.append(title)
        elements.append(Spacer(1, 0.2*inch))
        
        # Metadata
        meta_text = f"Generated: {get_cat_now().strftime('%Y-%m-%d %H:%M:%S CAT')}<br/>"
        meta_text += f"Total Records: {len(logs)}<br/>"
        if start_date:
            meta_text += f"From: {start_date}<br/>"
        if end_date:
            meta_text += f"To: {end_date}<br/>"
        meta = Paragraph(meta_text, styles['Normal'])
        elements.append(meta)
        elements.append(Spacer(1, 0.3*inch))
        
        # Table data
        data = [['Timestamp', 'User', 'Action', 'Resource', 'IP Address']]
        for log in logs:
            user_email = log.get('user_email') or 'System'
            resource_name = log.get('resource_name') or 'N/A'
            ip_address = log.get('ip_address') or 'N/A'
            
            data.append([
                format_cat_datetime(log['created_at'], '%Y-%m-%d %H:%M'),
                user_email[:30],
                log['action'].replace('_', ' ')[:30],
                f"{log['resource_type']}: {resource_name}"[:40],
                ip_address[:15]
            ])
        
        # Create table with RTG branding
        table = Table(data, colWidths=[1.2*inch, 1.5*inch, 1.5*inch, 2*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066cc')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f7ff')]),
        ]))
        elements.append(table)
        
        doc.build(elements)
        buffer.seek(0)
        
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=audit-logs-{get_cat_date_str()}.pdf"}
        )
    
    else:  # Excel (CSV format)
        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Timestamp', 'User Type', 'User Email', 'User Name', 'Action', 'Resource Type', 'Resource Name', 'IP Address', 'Description'])
        
        # Data rows
        for log in logs:
            writer.writerow([
                log['created_at'],
                log.get('user_type', ''),
                log.get('user_email', ''),
                log.get('user_name', ''),
                log['action'],
                log['resource_type'],
                log.get('resource_name', ''),
                log.get('ip_address', ''),
                log.get('action_description', '')
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=audit-logs-{get_cat_date_str()}.csv"}
        )
