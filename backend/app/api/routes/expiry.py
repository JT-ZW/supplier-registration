"""Document Expiry API Routes"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from ...db.supabase import get_db, Database
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


@router.post("/expiry/admin/create-alerts", response_model=CreateAlertsResponse)
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


@router.post("/expiry/admin/mark-sent/{alert_id}")
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


@router.get("/expiry/admin/supplier/{supplier_id}", response_model=List[SupplierExpiringDocument])
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
