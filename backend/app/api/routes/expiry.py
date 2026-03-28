"""Document Expiry API Routes"""
import csv
import io
from datetime import date as date_type, datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from ...db.supabase import get_db, Database
from ...services.expiry_service import get_expiry_service
from ...models.expiry import (
    ExpiringDocument,
    ExpiredDocument,
    SupplierExpiringDocument,
    PendingAlert,
    ExpiryAlertStats,
    CreateAlertsResponse,
    AcknowledgeAlertRequest,
    ExpiryDashboardSummary,
)
from ..deps import get_current_admin, get_current_vendor

router = APIRouter(prefix="/expiry", tags=["expiry"])


# ============================================================
# Vendor Endpoints
# ============================================================

@router.get("/vendor/dashboard", response_model=ExpiryDashboardSummary)
async def get_vendor_expiry_dashboard(
    vendor: dict = Depends(get_current_vendor),
    db: Database = Depends(get_db),
):
    """
    Get expiry dashboard summary for vendor.
    Returns documents expiring soon with severity classification.
    """
    try:
        vendor_id = vendor["id"]
        # Get expiring documents for this supplier (90 days threshold)
        result = db.client.rpc(
            "get_supplier_expiring_documents",
            {"p_supplier_id": vendor_id, "p_days_threshold": 90}
        ).execute()
        
        documents = result.data if result.data else []
        
        # Classify by severity
        critical = [d for d in documents if d.get("days_until_expiry", 999) <= 7]
        warning = [d for d in documents if 7 < d.get("days_until_expiry", 999) <= 30]
        info = [d for d in documents if 30 < d.get("days_until_expiry", 999) <= 90]
        
        # Get expired documents
        expired_result = db.client.rpc("get_expired_documents").execute()
        expired_data = expired_result.data if expired_result.data else []
        expired = [d for d in expired_data if d.get("supplier_id") == vendor_id]
        
        return ExpiryDashboardSummary(
            critical_count=len(critical),
            warning_count=len(warning),
            info_count=len(info),
            expired_count=len(expired),
            documents=[SupplierExpiringDocument(**d) for d in documents[:10]],  # Top 10
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vendor/expiring", response_model=List[SupplierExpiringDocument])
async def get_vendor_expiring_documents(
    vendor: dict = Depends(get_current_vendor),
    days: int = Query(default=90, ge=1, le=365),
    db: Database = Depends(get_db),
):
    """
    Get all expiring documents for the current vendor.
    """
    try:
        vendor_id = vendor["id"]
        result = db.client.rpc(
            "get_supplier_expiring_documents",
            {"p_supplier_id": vendor_id, "p_days_threshold": days}
        ).execute()
        
        if not result.data:
            return []
        
        return [SupplierExpiringDocument(**doc) for doc in result.data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vendor/acknowledge/{alert_id}")
async def acknowledge_expiry_alert(
    alert_id: UUID,
    vendor: dict = Depends(get_current_vendor),
    db: Database = Depends(get_db),
):
    """
    Acknowledge an expiry alert.
    """
    try:
        vendor_id = vendor["id"]
        result = db.client.rpc(
            "acknowledge_alert",
            {"p_alert_id": str(alert_id), "p_supplier_id": vendor_id}
        ).execute()
        
        if result.data:
            return {"success": True, "message": "Alert acknowledged"}
        else:
            raise HTTPException(status_code=404, detail="Alert not found or already acknowledged")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Admin Endpoints
# ============================================================

@router.get("/admin/expiring", response_model=List[ExpiringDocument])
async def get_all_expiring_documents(
    _: str = Depends(get_current_admin),
    days: int = Query(default=90, ge=1, le=365),
    db: Database = Depends(get_db),
):
    """
    Get all expiring documents across all suppliers (admin only).
    """
    try:
        result = db.client.rpc(
            "get_expiring_documents",
            {"p_days_threshold": days}
        ).execute()
        
        if not result.data:
            return []
        
        return [ExpiringDocument(**doc) for doc in result.data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/expired", response_model=List[ExpiredDocument])
async def get_all_expired_documents(
    _: str = Depends(get_current_admin),
    db: Database = Depends(get_db),
):
    """
    Get all expired documents across all suppliers (admin only).
    """
    try:
        result = db.client.rpc("get_expired_documents").execute()
        
        if not result.data:
            return []
        
        return [ExpiredDocument(**doc) for doc in result.data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/pending-alerts", response_model=List[PendingAlert])
async def get_pending_alerts(
    _: str = Depends(get_current_admin),
    db: Database = Depends(get_db),
):
    """
    Get all pending alerts that need email notifications (admin only).
    """
    try:
        result = db.client.rpc("get_pending_alerts").execute()
        
        if not result.data:
            return []
        
        return [PendingAlert(**alert) for alert in result.data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/stats", response_model=ExpiryAlertStats)
async def get_expiry_stats(
    _: str = Depends(get_current_admin),
    db: Database = Depends(get_db),
):
    """
    Get statistics on document expiry alerts (admin only).
    """
    try:
        result = db.client.rpc("get_expiry_alert_stats").execute()
        
        if not result.data or len(result.data) == 0:
            return ExpiryAlertStats(
                total_alerts=0,
                pending_alerts=0,
                sent_alerts=0,
                acknowledged_alerts=0,
                expired_documents=0,
                critical_alerts=0,
                warning_alerts=0,
            )
        
        return ExpiryAlertStats(**result.data[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/create-alerts", response_model=CreateAlertsResponse)
async def create_expiry_alerts(
    _: str = Depends(get_current_admin),
    db: Database = Depends(get_db),
):
    """
    Manually trigger alert creation for all expiring documents (admin only).
    Useful for testing or manual runs.
    """
    try:
        result = db.client.rpc("create_expiry_alerts").execute()
        
        if not result.data or len(result.data) == 0:
            return CreateAlertsResponse(alerts_created=0, documents_processed=0)
        
        return CreateAlertsResponse(**result.data[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/mark-sent/{alert_id}")
async def mark_alert_email_sent(
    alert_id: UUID,
    _: str = Depends(get_current_admin),
    db: Database = Depends(get_db),
):
    """
    Mark an alert email as sent (admin only).
    Used by email sending service.
    """
    try:
        result = db.client.rpc(
            "mark_alert_sent",
            {"p_alert_id": str(alert_id)}
        ).execute()
        
        if result.data:
            return {"success": True, "message": "Alert marked as sent"}
        else:
            raise HTTPException(status_code=404, detail="Alert not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/run-job")
async def trigger_expiry_job(
    _: str = Depends(get_current_admin),
    db: Database = Depends(get_db),
):
    """
    Manually trigger the daily expiry alert job (admin only).
    Flags expired documents, processes pending alerts, and sends notifications.
    """
    try:
        service = get_expiry_service(db)
        summary = await service.run_daily_expiry_job()
        return {"success": True, **summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/supplier/{supplier_id}", response_model=List[SupplierExpiringDocument])
async def get_supplier_expiring_documents_admin(
    supplier_id: UUID,
    _: str = Depends(get_current_admin),
    days: int = Query(default=90, ge=1, le=365),
    db: Database = Depends(get_db),
):
    """
    Get expiring documents for a specific supplier (admin only).
    """
    try:
        result = db.client.rpc(
            "get_supplier_expiring_documents",
            {"p_supplier_id": str(supplier_id), "p_days_threshold": days}
        ).execute()
        
        if not result.data:
            return []
        
        return [SupplierExpiringDocument(**doc) for doc in result.data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Report Endpoints (CSV + PDF)
# ============================================================

def _fetch_report_data(
    days: int,
    include_expired: bool,
    db: Database,
    supplier_status_filter: Optional[str] = None,
):
    """Shared data-fetch helper for CSV and PDF reports.

    supplier_status_filter values:
      • None / "ALL"   – return everything
      • "APPROVED"     – only APPROVED + COMPLIANCE_REQUIRED + SUSPENDED (post-approval)
      • "NOT_APPROVED" – only SUBMITTED + UNDER_REVIEW + NEED_MORE_INFO
    """
    expiring_result = db.client.rpc(
        "get_expiring_documents",
        {"p_days_threshold": days}
    ).execute()
    expiring_docs = expiring_result.data or []

    expired_docs: list = []
    if include_expired:
        expired_result = db.client.rpc("get_expired_documents").execute()
        expired_docs = expired_result.data or []

    # Apply status filter in Python so we don't need DB-side changes per-call
    if supplier_status_filter and supplier_status_filter.upper() not in ("ALL", ""):
        f = supplier_status_filter.upper()
        _approved_set = {"APPROVED", "COMPLIANCE_REQUIRED", "SUSPENDED"}
        _not_approved_set = {"SUBMITTED", "UNDER_REVIEW", "NEED_MORE_INFO"}
        if f == "APPROVED":
            expiring_docs = [d for d in expiring_docs if d.get("supplier_status", "").upper() in _approved_set]
            expired_docs = [d for d in expired_docs if d.get("supplier_status", "").upper() in _approved_set]
        elif f == "NOT_APPROVED":
            expiring_docs = [d for d in expiring_docs if d.get("supplier_status", "").upper() in _not_approved_set]
            expired_docs = [d for d in expired_docs if d.get("supplier_status", "").upper() in _not_approved_set]

    return expiring_docs, expired_docs


@router.get("/admin/report/csv", summary="Download expiry report as CSV")
async def download_expiry_report_csv(
    days: int = Query(default=90, ge=1, le=365, description="Window in days"),
    include_expired: bool = Query(default=True, description="Include already-expired documents"),
    supplier_status: Optional[str] = Query(
        default=None,
        description="Filter by approval status group: ALL, APPROVED, or NOT_APPROVED",
    ),
    _: str = Depends(get_current_admin),
    db: Database = Depends(get_db),
):
    """Download a CSV of all documents expiring within `days` days."""
    try:
        expiring_docs, expired_docs = _fetch_report_data(days, include_expired, db, supplier_status)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Status", "Company", "Email", "Document Type",
            "Expiry Date", "Days Until/Since Expiry", "Severity", "Supplier Status",
        ])

        for doc in expiring_docs:
            d = doc.get("days_until_expiry", 0)
            severity = "Critical" if d <= 7 else "Warning" if d <= 30 else "Info"
            writer.writerow([
                "Expiring",
                doc.get("company_name", ""),
                doc.get("email", ""),
                doc.get("document_type", "").replace("_", " ").title(),
                doc.get("expiry_date", ""),
                d, severity,
                doc.get("supplier_status", "").replace("_", " ").title(),
            ])

        for doc in expired_docs:
            writer.writerow([
                "Expired",
                doc.get("company_name", ""),
                doc.get("email", ""),
                doc.get("document_type", "").replace("_", " ").title(),
                doc.get("expiry_date", ""),
                f"-{doc.get('days_since_expiry', 0)}",
                "Expired",
                doc.get("supplier_status", "").replace("_", " ").title(),
            ])

        output.seek(0)
        status_suffix = f"_{supplier_status.lower()}" if supplier_status and supplier_status.upper() != "ALL" else ""
        filename = f"expiry_report_{date_type.today().isoformat()}_next{days}days{status_suffix}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/report/pdf", summary="Download expiry report as PDF")
async def download_expiry_report_pdf(
    days: int = Query(default=90, ge=1, le=365, description="Window in days"),
    include_expired: bool = Query(default=True, description="Include already-expired documents"),
    supplier_status: Optional[str] = Query(
        default=None,
        description="Filter by approval status group: ALL, APPROVED, or NOT_APPROVED",
    ),
    _: str = Depends(get_current_admin),
    db: Database = Depends(get_db),
):
    """Download a branded PDF of all documents expiring within `days` days."""
    try:
        expiring_docs, expired_docs = _fetch_report_data(days, include_expired, db, supplier_status)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontSize=16,
            textColor=colors.HexColor("#1e3a5f"),
            spaceAfter=2 * mm,
        )
        subtitle_style = ParagraphStyle(
            "Subtitle",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#6b7280"),
            spaceAfter=6 * mm,
        )
        section_style = ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontSize=11,
            textColor=colors.HexColor("#374151"),
            spaceBefore=6 * mm,
            spaceAfter=3 * mm,
        )
        cell_style = ParagraphStyle(
            "Cell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
        )

        def severity_color(d: int):
            if d <= 7:  return colors.HexColor("#b91c1c")
            if d <= 14: return colors.HexColor("#c2410c")
            if d <= 30: return colors.HexColor("#b45309")
            return colors.HexColor("#0369a1")

        def severity_label(d: int):
            if d <= 7:  return "Critical"
            if d <= 14: return "High"
            if d <= 30: return "Warning"
            return "Info"

        # ── bucket summary ──────────────────────────────────────────────────
        buckets = [
            ("1–3 d",   1,  3),
            ("4–7 d",   4,  7),
            ("8–14 d",  8,  14),
            ("15–30 d", 15, 30),
            ("31–60 d", 31, 60),
            ("61–90 d", 61, 90),
        ]
        active_buckets = [(lbl, lo, hi) for lbl, lo, hi in buckets if lo <= days]
        bucket_counts = [
            sum(1 for d in expiring_docs
                if lo <= d.get("days_until_expiry", 0) <= min(hi, days))
            for _, lo, hi in active_buckets
        ]

        bold_cell = ParagraphStyle("BCount", parent=cell_style, fontSize=11, fontName="Helvetica-Bold")
        red_bold = ParagraphStyle("RedBold", parent=cell_style, fontSize=11, fontName="Helvetica-Bold",
                                   textColor=colors.HexColor("#b91c1c"))

        summary_header = [Paragraph(b[0], cell_style) for b in active_buckets]
        summary_header.append(Paragraph("Expired", cell_style))
        summary_counts = [Paragraph(str(c), bold_cell) for c in bucket_counts]
        summary_counts.append(Paragraph(str(len(expired_docs)), red_bold))

        n_cols = len(active_buckets) + 1
        summary_col_w = 240 / n_cols
        summary_table = Table(
            [summary_header, summary_counts],
            colWidths=[summary_col_w * mm] * n_cols,
            rowHeights=[6 * mm, 9 * mm],
        )
        summary_table.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE",    (0, 0), (-1, 0),  8),
            ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
            ("TOPPADDING",  (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))

        # ── expiring table ──────────────────────────────────────────────────
        COL_W = [55*mm, 42*mm, 50*mm, 22*mm, 18*mm, 22*mm, 40*mm]
        HDR = ["Company", "Email", "Document Type", "Expiry Date", "Days Left", "Severity", "Supplier Status"]

        exp_rows = [HDR]
        for d in expiring_docs:
            dval = d.get("days_until_expiry", 0)
            exp_rows.append([
                Paragraph(d.get("company_name", ""), cell_style),
                Paragraph(d.get("email", ""), cell_style),
                Paragraph(d.get("document_type", "").replace("_", " ").title(), cell_style),
                str(d.get("expiry_date", "")),
                Paragraph(str(dval), ParagraphStyle("DC", parent=cell_style,
                          textColor=severity_color(dval), fontName="Helvetica-Bold")),
                severity_label(dval),
                d.get("supplier_status", "").replace("_", " ").title(),
            ])

        exp_table = Table(exp_rows, colWidths=COL_W, repeatRows=1)
        exp_table.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR",      (0, 0), (-1, 0), colors.white),
            ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, 0), 9),
            ("ALIGN",          (0, 0), (-1, 0), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ("FONTNAME",       (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",       (0, 1), (-1, -1), 8),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("GRID",           (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
            ("TOPPADDING",     (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 3),
            ("LEFTPADDING",    (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
        ]))

        # ── expired table ───────────────────────────────────────────────────
        EXP_COL_W = [55*mm, 42*mm, 56*mm, 22*mm, 24*mm, 50*mm]
        EXP_HDR = ["Company", "Email", "Document Type", "Expiry Date", "Days Since", "Supplier Status"]

        expired_rows = [EXP_HDR]
        for d in expired_docs:
            expired_rows.append([
                Paragraph(d.get("company_name", ""), cell_style),
                Paragraph(d.get("email", ""), cell_style),
                Paragraph(d.get("document_type", "").replace("_", " ").title(), cell_style),
                Paragraph(str(d.get("expiry_date", "")),
                          ParagraphStyle("RC", parent=cell_style, textColor=colors.HexColor("#b91c1c"))),
                Paragraph(str(d.get("days_since_expiry", "")),
                          ParagraphStyle("RB", parent=cell_style,
                                         textColor=colors.HexColor("#b91c1c"), fontName="Helvetica-Bold")),
                d.get("supplier_status", "").replace("_", " ").title(),
            ])

        expired_table = Table(expired_rows, colWidths=EXP_COL_W, repeatRows=1)
        expired_table.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0), colors.HexColor("#7f1d1d")),
            ("TEXTCOLOR",      (0, 0), (-1, 0), colors.white),
            ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, 0), 9),
            ("ALIGN",          (0, 0), (-1, 0), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff1f2")]),
            ("FONTNAME",       (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",       (0, 1), (-1, -1), 8),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("GRID",           (0, 0), (-1, -1), 0.4, colors.HexColor("#fca5a5")),
            ("TOPPADDING",     (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 3),
            ("LEFTPADDING",    (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
        ]))

        # ── assemble ────────────────────────────────────────────────────────
        generated_at = datetime.now().strftime("%d %B %Y at %H:%M")
        _status_label = {
            "APPROVED": "Approved Suppliers",
            "NOT_APPROVED": "Applicants Under Review",
        }.get((supplier_status or "").upper(), "All Suppliers")
        story = [
            Paragraph("Rainbow Tourism Group", title_style),
            Paragraph(
                f"Document Expiry Report — Next {days} Days &nbsp;&nbsp;|"
                f"&nbsp;&nbsp;{_status_label} &nbsp;&nbsp;|"
                f"&nbsp;&nbsp;Generated: {generated_at}",
                subtitle_style,
            ),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1e3a5f"), spaceAfter=4 * mm),
            Paragraph("Summary by Expiry Window", section_style),
            summary_table,
            Spacer(1, 4 * mm),
            Paragraph(f"Expiring Documents ({len(expiring_docs)} total)", section_style),
        ]
        if expiring_docs:
            story.append(exp_table)
        else:
            story.append(Paragraph("No documents expiring within this window.", cell_style))

        if include_expired:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph(f"Already Expired ({len(expired_docs)} total)", section_style))
            if expired_docs:
                story.append(expired_table)
            else:
                story.append(Paragraph("No expired documents found.", cell_style))

        doc.build(story)
        buf.seek(0)

        status_suffix = f"_{supplier_status.lower()}" if supplier_status and supplier_status.upper() != "ALL" else ""
        filename = f"expiry_report_{date_type.today().isoformat()}_next{days}days{status_suffix}.pdf"
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
