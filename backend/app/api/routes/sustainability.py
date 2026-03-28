"""
Sustainability & ESG reporting API routes.

Exposes aggregated metrics from the four compliance views:
  - vw_esg_supplier_summary
  - vw_category_compliance
  - vw_business_size_distribution
  - vw_document_type_stats

Also provides filtered supplier list and CSV/Excel downloads.
"""

from io import BytesIO, StringIO
import asyncio
import csv
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from fastapi.responses import StreamingResponse

from ...db.supabase import db
from ...api.deps import get_current_admin
from ...core.timezone import get_cat_timestamp_str
from ...models.enums import SupplierStatus

router = APIRouter(prefix="/sustainability", tags=["Sustainability"])

APPROVED_STATUS_SCOPE = ["APPROVED", "COMPLIANCE_REQUIRED", "SUSPENDED"]
MAINTENANCE_INTERVAL_SECONDS = 300
OVERVIEW_CACHE_TTL_SECONDS = 60

_last_maintenance_run_ts = 0.0
_maintenance_lock = asyncio.Lock()
_overview_cache: dict[str, tuple[float, dict]] = {}
_overview_cache_lock = asyncio.Lock()


# ── helpers ──────────────────────────────────────────────────────────────────

def _safe_pct(part: int, total: int) -> float:
    return round(100 * part / total, 1) if total else 0.0


def _derive_esg_booleans_from_counts(row: dict) -> tuple[bool, bool]:
    """Derive ownership/leadership flags using >50% threshold rules."""
    total_key_persons = row.get("key_person_count") or 0
    female_count = row.get("female_director_count") or 0
    youth_count = row.get("youth_director_count") or 0

    if total_key_persons <= 0:
        return False, False

    return (female_count / total_key_persons) > 0.5, (youth_count / total_key_persons) > 0.5


async def _run_sustainability_maintenance_if_due(
    statuses: list[str],
    force_refresh: bool = False,
) -> None:
    """Throttle heavy maintenance work to avoid slowing every dashboard request."""
    global _last_maintenance_run_ts

    now = time.time()
    if not force_refresh and now - _last_maintenance_run_ts < MAINTENANCE_INTERVAL_SECONDS:
        return

    async with _maintenance_lock:
        # Re-check inside lock so concurrent requests do not duplicate work.
        now = time.time()
        if not force_refresh and now - _last_maintenance_run_ts < MAINTENANCE_INTERVAL_SECONDS:
            return

        try:
            await db.backfill_supplier_categories_from_primary(statuses=statuses)
        except Exception as backfill_err:
            print(f"⚠️  supplier category backfill skipped: {backfill_err}")

        try:
            await db.recompute_category_compliance_for_suppliers(statuses=statuses)
        except Exception as compliance_err:
            print(f"⚠️  category compliance refresh skipped: {compliance_err}")

        _last_maintenance_run_ts = time.time()


def _build_overview_cache_key(
    country: Optional[str],
    business_size: Optional[str],
    status: Optional[str],
) -> str:
    return f"country={country or ''}|business_size={business_size or ''}|status={status or ''}"


async def _get_cached_overview(cache_key: str) -> Optional[dict]:
    async with _overview_cache_lock:
        cached = _overview_cache.get(cache_key)
        if not cached:
            return None

        cached_at, payload = cached
        if time.time() - cached_at > OVERVIEW_CACHE_TTL_SECONDS:
            _overview_cache.pop(cache_key, None)
            return None

        return payload


async def _set_cached_overview(cache_key: str, payload: dict) -> None:
    async with _overview_cache_lock:
        _overview_cache[cache_key] = (time.time(), payload)


# ── 1. Overview (all KPIs in one call) ──────────────────────────────────────

@router.get("/overview", summary="Full sustainability KPI snapshot")
async def get_sustainability_overview(
    country: Optional[str] = Query(None),
    business_size: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Supplier status filter"),
    refresh_stats: bool = Query(
        False,
        description="Force a one-time maintenance refresh before reading stats",
    ),
    current_admin: dict = Depends(get_current_admin),
):
    """
    Returns all sustainability metrics needed to render the dashboard:
      - ESG headline numbers
      - Business-size breakdown
      - Category compliance distribution
      - Document type upload stats
    """
    approved_scope = ["APPROVED", "COMPLIANCE_REQUIRED", "SUSPENDED"]
    maintenance_statuses = [
        SupplierStatus.INCOMPLETE.value,
        SupplierStatus.SUBMITTED.value,
        SupplierStatus.UNDER_REVIEW.value,
        SupplierStatus.NEED_MORE_INFO.value,
        SupplierStatus.APPROVED.value,
        SupplierStatus.COMPLIANCE_REQUIRED.value,
        SupplierStatus.SUSPENDED.value,
    ]
    status_filter = status if status else None
    cache_key = _build_overview_cache_key(country, business_size, status_filter)

    if refresh_stats:
        # Manual override: block and force fresh maintenance + fresh stats payload.
        await _run_sustainability_maintenance_if_due(
            statuses=maintenance_statuses,
            force_refresh=True,
        )
    else:
        # Keep category-compliance stats fresh without forcing a heavy recompute on every hit.
        await _run_sustainability_maintenance_if_due(
            statuses=maintenance_statuses,
            force_refresh=False,
        )
        # Keep reads strictly read-only by default; maintenance is opt-in via refresh_stats.
        cached_payload = await _get_cached_overview(cache_key)
        if cached_payload is not None:
            return cached_payload

    esg_task = db.get_esg_summary(
        country=country,
        business_size=business_size,
        status=status_filter,
        columns="status,is_small_scale_farmer,key_person_count,female_director_count,youth_director_count",
    )
    size_task = db.get_business_size_distribution()
    cat_task = db.get_category_compliance_stats(
        country=country,
        business_size=business_size,
        status=status_filter,
    )
    doc_task = db.get_document_type_stats()

    esg_rows, size_rows, cat_rows, doc_rows = await asyncio.gather(
        esg_task,
        size_task,
        cat_task,
        doc_task,
    )
    if status_filter is None:
        esg_rows = [r for r in esg_rows if (r.get("status") or "") in APPROVED_STATUS_SCOPE]

    total = len(esg_rows)
    status_breakdown = {
        "approved": sum(1 for r in esg_rows if (r.get("status") or "") == "APPROVED"),
        "compliance_required": sum(1 for r in esg_rows if (r.get("status") or "") == "COMPLIANCE_REQUIRED"),
        "suspended": sum(1 for r in esg_rows if (r.get("status") or "") == "SUSPENDED"),
    }
    # Use key-person counts as source-of-truth for ownership/leadership metrics.
    derived_flags = [_derive_esg_booleans_from_counts(r) for r in esg_rows]
    women_owned = sum(1 for women_owned_flag, _ in derived_flags if women_owned_flag)
    youth_owned = sum(1 for _, youth_owned_flag in derived_flags if youth_owned_flag)
    farmers = sum(1 for r in esg_rows if r.get("is_small_scale_farmer"))
    female_directors = sum(r.get("female_director_count") or 0 for r in esg_rows)
    youth_directors = sum(r.get("youth_director_count") or 0 for r in esg_rows)
    total_directors = sum(r.get("key_person_count") or 0 for r in esg_rows)

    payload = {
        "total_suppliers": total,
        "supplier_status_breakdown": status_breakdown,
        "esg": {
            "women_owned_count": women_owned,
            "women_owned_pct": _safe_pct(women_owned, total),
            "youth_owned_count": youth_owned,
            "youth_owned_pct": _safe_pct(youth_owned, total),
            "small_scale_farmer_count": farmers,
            "small_scale_farmer_pct": _safe_pct(farmers, total),
            "female_directors": female_directors,
            "youth_directors": youth_directors,
            "total_directors": total_directors,
            "female_director_pct": _safe_pct(female_directors, total_directors),
            "youth_director_pct": _safe_pct(youth_directors, total_directors),
        },
        "business_size_distribution": size_rows,
        "category_compliance": cat_rows,
        "document_type_stats": doc_rows,
    }

    await _set_cached_overview(cache_key, payload)
    return payload


# ── 2. ESG supplier detail list ───────────────────────────────────────────────

@router.get("/suppliers", summary="Filtered supplier list for ESG reporting")
async def get_sustainability_suppliers(
    country: Optional[str] = Query(None),
    business_size: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    esg_women_owned: Optional[bool] = Query(None),
    esg_youth_owned: Optional[bool] = Query(None),
    is_small_scale_farmer: Optional[bool] = Query(None),
    current_admin: dict = Depends(get_current_admin),
):
    rows = await db.get_sustainability_supplier_list(
        country=country,
        business_size=business_size,
        status=status,
        esg_women_owned=esg_women_owned,
        esg_youth_owned=esg_youth_owned,
        is_small_scale_farmer=is_small_scale_farmer,
    )
    return {"suppliers": rows, "total": len(rows)}


@router.get("/compliance-audit", summary="Supplier-by-supplier category compliance audit")
async def get_compliance_audit(
    country: Optional[str] = Query(None),
    business_size: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    supplier_id: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    refresh_stats: bool = Query(
        False,
        description="Force a maintenance refresh before generating audit rows",
    ),
    current_admin: dict = Depends(get_current_admin),
):
    """Return per-supplier category compliance details for diagnostics and reconciliation."""
    maintenance_statuses = [
        SupplierStatus.INCOMPLETE.value,
        SupplierStatus.SUBMITTED.value,
        SupplierStatus.UNDER_REVIEW.value,
        SupplierStatus.NEED_MORE_INFO.value,
        SupplierStatus.APPROVED.value,
        SupplierStatus.COMPLIANCE_REQUIRED.value,
        SupplierStatus.SUSPENDED.value,
    ]

    await _run_sustainability_maintenance_if_due(
        statuses=maintenance_statuses,
        force_refresh=refresh_stats,
    )

    supplier_query = db.client.table("suppliers").select(
        "id,company_name,status,business_category,country,business_size"
    )
    if supplier_id:
        supplier_query = supplier_query.eq("id", supplier_id)
    if country:
        supplier_query = supplier_query.ilike("country", f"%{country}%")
    if business_size:
        supplier_query = supplier_query.eq("business_size", business_size)
    if status:
        supplier_query = supplier_query.eq("status", status)

    suppliers_result = supplier_query.limit(limit).execute()
    suppliers = suppliers_result.data or []
    supplier_ids = [row.get("id") for row in suppliers if row.get("id")]

    categories_by_supplier: dict[str, list[dict]] = {}
    if supplier_ids:
        category_rows_result = (
            db.client.table("supplier_categories")
            .select("supplier_id,category,compliance_status,compliance_checked_at")
            .in_("supplier_id", supplier_ids)
            .execute()
        )
        for row in (category_rows_result.data or []):
            sid = row.get("supplier_id")
            if not sid:
                continue
            categories_by_supplier.setdefault(sid, []).append(row)

    audit_rows = []
    summary = {
        "suppliers": len(suppliers),
        "fully_compliant": 0,
        "partial": 0,
        "non_compliant": 0,
        "missing_categories": 0,
    }

    for supplier in suppliers:
        sid = supplier.get("id")
        category_rows = categories_by_supplier.get(sid, [])

        full_count = sum(1 for row in category_rows if (row.get("compliance_status") or "").upper() == "FULL_COMPLIANCE")
        medium_count = sum(1 for row in category_rows if (row.get("compliance_status") or "").upper() == "MEDIUM_RISK")
        high_count = sum(1 for row in category_rows if (row.get("compliance_status") or "").upper() == "HIGH_RISK")
        pending_count = sum(1 for row in category_rows if (row.get("compliance_status") or "").upper() == "PENDING")
        excluded_count = sum(1 for row in category_rows if (row.get("compliance_status") or "").upper() == "EXCLUDED")

        mandatory_met = full_count + medium_count
        mandatory_missing = high_count + pending_count
        non_excluded_total = len(category_rows) - excluded_count
        allowed_categories = sorted(
            [
                (row.get("category") or "")
                for row in category_rows
                if (row.get("compliance_status") or "").upper() in ("FULL_COMPLIANCE", "MEDIUM_RISK")
                and (row.get("category") or "")
            ]
        )
        blocked_categories = sorted(
            [
                (row.get("category") or "")
                for row in category_rows
                if (row.get("compliance_status") or "").upper() in ("HIGH_RISK", "PENDING")
                and (row.get("category") or "")
            ]
        )

        if len(category_rows) == 0:
            portfolio_status = "NO_CATEGORY_ASSIGNMENT"
            summary["missing_categories"] += 1
        elif mandatory_missing == 0 and full_count == non_excluded_total:
            portfolio_status = "FULLY_COMPLIANT"
            summary["fully_compliant"] += 1
        elif mandatory_missing == 0:
            portfolio_status = "MANDATORY_MET_PENDING_PREFERRED"
            summary["fully_compliant"] += 1
        elif mandatory_met > 0:
            portfolio_status = "PARTIALLY_COMPLIANT"
            summary["partial"] += 1
        else:
            portfolio_status = "NON_COMPLIANT"
            summary["non_compliant"] += 1

        audit_rows.append(
            {
                "supplier_id": sid,
                "company_name": supplier.get("company_name"),
                "supplier_status": supplier.get("status"),
                "primary_category": supplier.get("business_category"),
                "country": supplier.get("country"),
                "business_size": supplier.get("business_size"),
                "category_count": len(category_rows),
                "mandatory_met_categories": mandatory_met,
                "mandatory_missing_categories": mandatory_missing,
                "allowed_categories": allowed_categories,
                "blocked_categories": blocked_categories,
                "full_compliance_categories": full_count,
                "medium_risk_categories": medium_count,
                "high_risk_categories": high_count,
                "pending_categories": pending_count,
                "excluded_categories": excluded_count,
                "portfolio_status": portfolio_status,
                "categories": sorted(
                    [
                        {
                            "category": row.get("category"),
                            "compliance_status": row.get("compliance_status"),
                            "compliance_checked_at": row.get("compliance_checked_at"),
                        }
                        for row in category_rows
                    ],
                    key=lambda item: item.get("category") or "",
                ),
            }
        )

    return {
        "summary": summary,
        "rows": audit_rows,
        "total": len(audit_rows),
    }


# ── 3. CSV download ──────────────────────────────────────────────────────────

@router.get("/export/csv", summary="Download ESG supplier list as CSV")
async def export_sustainability_csv(
    country: Optional[str] = Query(None),
    business_size: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    esg_women_owned: Optional[bool] = Query(None),
    esg_youth_owned: Optional[bool] = Query(None),
    is_small_scale_farmer: Optional[bool] = Query(None),
    current_admin: dict = Depends(get_current_admin),
):
    rows = await db.get_sustainability_supplier_list(
        country=country,
        business_size=business_size,
        status=status,
        esg_women_owned=esg_women_owned,
        esg_youth_owned=esg_youth_owned,
        is_small_scale_farmer=is_small_scale_farmer,
    )

    output = StringIO()
    fieldnames = [
        "company_name", "country", "status", "supplier_type",
        "business_size", "employee_count", "is_small_scale_farmer",
        "esg_women_owned", "esg_youth_owned",
        "business_categories", "years_in_business", "created_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        # Flatten list fields
        if isinstance(row.get("business_categories"), list):
            row["business_categories"] = ", ".join(row["business_categories"])
        writer.writerow(row)

    filename = f"rtg_sustainability_report_{get_cat_timestamp_str()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── 4. Excel download ────────────────────────────────────────────────────────

@router.get("/export/excel", summary="Download ESG supplier list as Excel")
async def export_sustainability_excel(
    country: Optional[str] = Query(None),
    business_size: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    esg_women_owned: Optional[bool] = Query(None),
    esg_youth_owned: Optional[bool] = Query(None),
    is_small_scale_farmer: Optional[bool] = Query(None),
    current_admin: dict = Depends(get_current_admin),
):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openpyxl is required for Excel export. Run: pip install openpyxl",
        )

    rows = await db.get_sustainability_supplier_list(
        country=country,
        business_size=business_size,
        status=status,
        esg_women_owned=esg_women_owned,
        esg_youth_owned=esg_youth_owned,
        is_small_scale_farmer=is_small_scale_farmer,
    )

    status_filter = status if status else None
    esg_rows = await db.get_esg_summary(country=country, business_size=business_size, status=status_filter)
    if status_filter is None:
        esg_rows = [r for r in esg_rows if (r.get("status") or "") in APPROVED_STATUS_SCOPE]

    total = len(esg_rows)
    derived_flags = [_derive_esg_booleans_from_counts(r) for r in esg_rows]
    women_owned = sum(1 for women_owned_flag, _ in derived_flags if women_owned_flag)
    youth_owned = sum(1 for _, youth_owned_flag in derived_flags if youth_owned_flag)
    farmers = sum(1 for r in esg_rows if r.get("is_small_scale_farmer"))

    wb = openpyxl.Workbook()

    # ── Sheet 1: KPI Summary ──
    ws_kpi = wb.active
    ws_kpi.title = "ESG Summary"
    header_fill = PatternFill("solid", fgColor="1E3A5F")
    header_font = Font(color="FFFFFF", bold=True)

    kpi_data = [
        ("KPI", "Value", "% of Total"),
        ("Total Suppliers", total, "100%"),
        ("Women-Owned", women_owned, f"{_safe_pct(women_owned, total)}%"),
        ("Youth-Owned", youth_owned, f"{_safe_pct(youth_owned, total)}%"),
        ("Small-Scale Farmers", farmers, f"{_safe_pct(farmers, total)}%"),
    ]
    for r_idx, row_data in enumerate(kpi_data, 1):
        for c_idx, val in enumerate(row_data, 1):
            cell = ws_kpi.cell(row=r_idx, column=c_idx, value=val)
            if r_idx == 1:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
    ws_kpi.column_dimensions["A"].width = 28
    ws_kpi.column_dimensions["B"].width = 14
    ws_kpi.column_dimensions["C"].width = 16

    # ── Sheet 2: Supplier list ──
    ws = wb.create_sheet("Supplier List")
    columns = [
        ("Company Name", "company_name"),
        ("Country", "country"),
        ("Status", "status"),
        ("Supplier Type", "supplier_type"),
        ("Business Size", "business_size"),
        ("Employees", "employee_count"),
        ("Small-Scale Farmer", "is_small_scale_farmer"),
        ("Women-Owned", "esg_women_owned"),
        ("Youth-Owned", "esg_youth_owned"),
        ("Categories", "business_categories"),
        ("Years in Business", "years_in_business"),
        ("Registered", "created_at"),
    ]
    for c_idx, (header, _) in enumerate(columns, 1):
        cell = ws.cell(row=1, column=c_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for r_idx, row in enumerate(rows, 2):
        for c_idx, (_, key) in enumerate(columns, 1):
            val = row.get(key)
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            elif isinstance(val, bool):
                val = "Yes" if val else "No"
            ws.cell(row=r_idx, column=c_idx, value=val)

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = max(
            len(str(col[0].value or "")), 12
        ) + 4

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"rtg_sustainability_report_{get_cat_timestamp_str()}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
