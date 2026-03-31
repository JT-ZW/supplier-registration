"""
Profile change request API endpoints.
Handles vendor profile change requests and admin approvals.
Implements hybrid approach: some fields update directly, others require approval.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from pydantic import UUID4

from app.models.profile_change import (
    ProfileChangeRequest,
    ProfileChangeResponse,
    ProfileChangeReviewRequest,
    ProfileChangeListItem,
    ProfileChangeHistoryItem,
)
from app.models.profile_update import ProfileUpdateResponse
from app.db.supabase import db
from app.api.deps import get_current_admin, get_current_vendor
from app.services.audit import audit_service
from app.models.audit import AuditAction, AuditResourceType
from app.core.profile_permissions import validate_field_permissions
from app.core.email import email_service, EmailTemplate
from app.core.config import settings
from app.core.cache_invalidation import invalidate_analytics_cache
from app.models import compute_esg_flags
import json

router = APIRouter(prefix="/profile-changes", tags=["profile-changes"])


# ============================================================
# Helper Functions
# ============================================================

def parse_json_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse JSON string fields back to dictionaries."""
    if isinstance(data.get("requested_changes"), str):
        data["requested_changes"] = json.loads(data["requested_changes"])
    if isinstance(data.get("current_values"), str):
        data["current_values"] = json.loads(data["current_values"])
    return data


SUPPLIER_PROFILE_FIELDS = {
    "company_name",
    "business_category",
    "registration_number",
    "tax_id",
    "years_in_business",
    "website",
    "contact_person_name",
    "contact_person_title",
    "email",
    "phone",
    "street_address",
    "city",
    "state_province",
    "postal_code",
    "country",
    "employee_count",
    "is_small_scale_farmer",
}


def _normalize_requested_changes(raw_changes: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize incoming changes so permission checks can handle complex entities."""
    normalized = dict(raw_changes)

    key_persons = normalized.pop("key_persons", None)
    if key_persons is None:
        key_persons = normalized.pop("keyPersons", None)

    if isinstance(key_persons, list):
        directors: List[Dict[str, Any]] = []
        contacts: List[Dict[str, Any]] = []
        for person in key_persons:
            role = str(person.get("role") or "").upper()
            if role == "DIRECTOR":
                directors.append(person)
            else:
                contacts.append(person)
        if directors:
            normalized["key_persons_directors"] = directors
        if contacts:
            normalized["key_persons_contacts"] = contacts

    trade_references = normalized.pop("tradeReferences", None)
    if trade_references is None:
        trade_references = normalized.get("trade_references")
    if isinstance(trade_references, list):
        normalized["trade_references"] = trade_references

    business_categories = normalized.pop("businessCategories", None)
    if business_categories is None:
        business_categories = normalized.get("business_categories")
    if isinstance(business_categories, list):
        normalized["business_categories"] = business_categories

    farmer_form = normalized.pop("farmerForm", None)
    if farmer_form is None:
        farmer_form = normalized.get("farmer_form")
    if isinstance(farmer_form, dict):
        normalized["farmer_form"] = farmer_form

    return normalized


def _map_key_person_payload(person: Dict[str, Any], role_override: Optional[str] = None) -> Dict[str, Any]:
    role = role_override or person.get("role") or "DIRECTOR"
    return {
        "full_name": person.get("full_name") or person.get("fullName") or "",
        "gender": person.get("gender") or "OTHER",
        "date_of_birth": person.get("date_of_birth") or person.get("dateOfBirth"),
        "role": str(role).upper(),
    }


def _map_trade_reference_payload(reference: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "company_name": reference.get("company_name") or reference.get("companyName") or "",
        "contact_person_name": reference.get("contact_person_name") or reference.get("contactPersonName") or "",
        "email": reference.get("email") or "",
        "phone": reference.get("phone") or "",
        "relationship": reference.get("relationship") or "",
        "service_product": reference.get("service_product") or reference.get("serviceProduct"),
        "contract_start_date": reference.get("contract_start_date") or reference.get("contractStartDate"),
        "contract_end_date": reference.get("contract_end_date") or reference.get("contractEndDate"),
        "annual_spend": reference.get("annual_spend") or reference.get("annualSpend"),
        "permission_granted": bool(reference.get("permission_granted") if reference.get("permission_granted") is not None else reference.get("permissionGranted", False)),
    }


def _map_farmer_form_payload(payload: Dict[str, Any], supplier_id: str) -> Dict[str, Any]:
    return {
        "supplier_id": supplier_id,
        "contact_full_name": payload.get("contact_full_name") or payload.get("contactFullName") or "",
        "id_number": payload.get("id_number") or payload.get("idNumber"),
        "gender": payload.get("gender") or "OTHER",
        "date_of_birth": payload.get("date_of_birth") or payload.get("dateOfBirth"),
        "farming_activity": payload.get("farming_activity") or payload.get("farmingActivity") or "",
        "produce_types": payload.get("produce_types") or payload.get("produceTypes") or "",
        "estimated_land_size_ha": payload.get("estimated_land_size_ha") if payload.get("estimated_land_size_ha") is not None else payload.get("estimatedLandSizeHa"),
        "years_farming": payload.get("years_farming") if payload.get("years_farming") is not None else payload.get("yearsFarming"),
        "land_proof_type": payload.get("land_proof_type") or payload.get("landProofType"),
        "village_or_farm_name": payload.get("village_or_farm_name") or payload.get("villageOrFarmName"),
        "district": payload.get("district"),
        "province": payload.get("province"),
        "contact_phone": payload.get("contact_phone") or payload.get("contactPhone"),
        "has_bank_account": bool(payload.get("has_bank_account") if payload.get("has_bank_account") is not None else payload.get("hasBankAccount", False)),
        "bank_name": payload.get("bank_name") or payload.get("bankName"),
    }


async def _build_current_values_snapshot(supplier_id: str, current_supplier: Dict[str, Any], approval_changes: Dict[str, Any]) -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {}
    for field in approval_changes.keys():
        if field in current_supplier:
            snapshot[field] = current_supplier[field]
            continue

        if field == "business_categories":
            categories = await db.get_supplier_categories(supplier_id)
            snapshot[field] = [row.get("category") for row in categories if row.get("category")]
        elif field == "key_persons_directors":
            key_persons = await db.get_key_persons_by_supplier(supplier_id)
            snapshot[field] = [
                {
                    "fullName": person.get("full_name") or "",
                    "gender": person.get("gender") or "OTHER",
                    "dateOfBirth": person.get("date_of_birth"),
                    "role": person.get("role") or "DIRECTOR",
                }
                for person in key_persons
                if str(person.get("role") or "").upper() == "DIRECTOR"
            ]
        elif field == "farmer_form":
            snapshot[field] = await db.get_farmer_form(supplier_id)

    return snapshot


async def _apply_trade_references(supplier_id: str, trade_references: List[Dict[str, Any]]) -> None:
    await db.delete_trade_references_by_supplier(supplier_id)
    for reference in trade_references:
        mapped = _map_trade_reference_payload(reference)
        await db.create_trade_reference({"supplier_id": supplier_id, **mapped})


async def _replace_key_persons_with_split(
    supplier_id: str,
    directors: Optional[List[Dict[str, Any]]] = None,
    contacts: Optional[List[Dict[str, Any]]] = None,
) -> None:
    existing = await db.get_key_persons_by_supplier(supplier_id)
    existing_directors = [
        _map_key_person_payload(person, role_override="DIRECTOR")
        for person in existing
        if str(person.get("role") or "").upper() == "DIRECTOR"
    ]
    existing_contacts = [
        _map_key_person_payload(person, role_override="CONTACT")
        for person in existing
        if str(person.get("role") or "").upper() == "CONTACT"
    ]

    final_directors = [_map_key_person_payload(person, role_override="DIRECTOR") for person in directors] if directors is not None else existing_directors
    final_contacts = [_map_key_person_payload(person, role_override="CONTACT") for person in contacts] if contacts is not None else existing_contacts

    await db.delete_key_persons_by_supplier(supplier_id)

    for person in final_directors + final_contacts:
        await db.create_key_person(
            {
                "supplier_id": supplier_id,
                "full_name": person["full_name"],
                "gender": person["gender"],
                "date_of_birth": person["date_of_birth"],
                "role": person["role"],
            }
        )


async def _refresh_esg_flags_from_key_persons(supplier_id: str) -> None:
    key_persons = await db.get_key_persons_by_supplier(supplier_id)
    if not key_persons:
        return

    payload = [
        {
            "full_name": person.get("full_name"),
            "gender": person.get("gender"),
            "date_of_birth": person.get("date_of_birth"),
            "role": person.get("role"),
        }
        for person in key_persons
    ]
    flags = compute_esg_flags(payload)
    await db.update_supplier(
        supplier_id,
        {
            "esg_women_owned": flags.get("esg_women_owned"),
            "esg_youth_owned": flags.get("esg_youth_owned"),
        },
    )


async def _apply_direct_structured_changes(supplier_id: str, direct_changes: Dict[str, Any]) -> List[str]:
    applied_fields: List[str] = []

    if isinstance(direct_changes.get("trade_references"), list):
        await _apply_trade_references(supplier_id, direct_changes["trade_references"])
        applied_fields.append("trade_references")

    if isinstance(direct_changes.get("key_persons_contacts"), list):
        await _replace_key_persons_with_split(
            supplier_id=supplier_id,
            directors=None,
            contacts=direct_changes["key_persons_contacts"],
        )
        await _refresh_esg_flags_from_key_persons(supplier_id)
        applied_fields.append("key_persons_contacts")

    return applied_fields


async def _apply_approved_structured_changes(supplier_id: str, approved_changes: Dict[str, Any]) -> List[str]:
    applied_fields: List[str] = []

    if isinstance(approved_changes.get("business_categories"), list):
        await db.delete_supplier_categories(supplier_id)
        for category in approved_changes["business_categories"]:
            if not category:
                continue
            await db.create_supplier_category(
                {
                    "supplier_id": supplier_id,
                    "category": str(category),
                    "compliance_status": "PENDING",
                }
            )
        applied_fields.append("business_categories")

    if isinstance(approved_changes.get("key_persons_directors"), list):
        await _replace_key_persons_with_split(
            supplier_id=supplier_id,
            directors=approved_changes["key_persons_directors"],
            contacts=None,
        )
        await _refresh_esg_flags_from_key_persons(supplier_id)
        applied_fields.append("key_persons_directors")

    if "farmer_form" in approved_changes:
        farmer_payload = approved_changes.get("farmer_form")
        if isinstance(farmer_payload, dict):
            await db.create_farmer_form(_map_farmer_form_payload(farmer_payload, supplier_id))
            applied_fields.append("farmer_form")
        elif farmer_payload is None:
            await db.delete_farmer_form(supplier_id)
            applied_fields.append("farmer_form")

    return applied_fields


# ============================================================
# Vendor Endpoints
# ============================================================

@router.post("/vendor/request", response_model=ProfileUpdateResponse)
async def submit_profile_change_request(
    request: Request,
    change_request: ProfileChangeRequest,
    current_vendor: dict = Depends(get_current_vendor)
):
    """
    Submit profile changes as a vendor.
    Implements hybrid approach:
    - Direct update fields: applied immediately
    - Approval-required fields: create change request for admin review
    - Read-only fields: rejected with error
    
    Returns information about which changes were applied and which require approval.
    """
    try:
        supplier_id = current_vendor["id"]
        
        normalized_changes = _normalize_requested_changes(change_request.requested_changes)

        # Validate field permissions
        is_valid, error_msg, categorized = validate_field_permissions(
            normalized_changes
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Get current supplier data
        current_supplier = await db.get_supplier_by_id(supplier_id)
        if not current_supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found"
            )
        
        # Initialize response data
        direct_updates_applied = 0
        approval_request_created = False
        change_request_id = None
        approval_request_data = None
        
        # Apply direct updates immediately
        if categorized["direct"]:
            direct_supplier_changes = {
                field: value
                for field, value in categorized["direct"].items()
                if field in SUPPLIER_PROFILE_FIELDS
            }
            direct_structured_changes = {
                field: value
                for field, value in categorized["direct"].items()
                if field not in SUPPLIER_PROFILE_FIELDS
            }

            direct_fields_applied: List[str] = []
            if direct_supplier_changes:
                update_result = await db.update_supplier(supplier_id, direct_supplier_changes)
                if update_result:
                    direct_fields_applied.extend(list(direct_supplier_changes.keys()))

            direct_fields_applied.extend(
                await _apply_direct_structured_changes(supplier_id, direct_structured_changes)
            )

            direct_updates_applied = len(direct_fields_applied)

            if direct_fields_applied:
                await audit_service.log_action_from_request(
                    request=request,
                    action=AuditAction.SUPPLIER_UPDATED,
                    resource_type=AuditResourceType.SUPPLIER,
                    resource_id=supplier_id,
                    resource_name=current_supplier.get("company_name", ""),
                    current_user=current_vendor,
                    metadata={
                        "update_type": "direct",
                        "fields_updated": direct_fields_applied,
                        "changes": categorized["direct"],
                    }
                )
        
        # Create approval request for sensitive fields
        if categorized["approval_required"]:
            # Build current values snapshot
            current_values = await _build_current_values_snapshot(
                supplier_id=supplier_id,
                current_supplier=current_supplier,
                approval_changes=categorized["approval_required"],
            )
            
            # Cancel any pending requests for approval-required changes
            db.client.rpc("cancel_pending_profile_changes", {
                "p_supplier_id": supplier_id
            }).execute()
            
            # Create new approval request
            insert_result = db.client.table("profile_change_requests").insert({
                "supplier_id": supplier_id,
                "requested_changes": categorized["approval_required"],
                "current_values": current_values,
                "status": "PENDING"
            }).execute()
            
            if insert_result.data and len(insert_result.data) > 0:
                # Get the inserted record ID
                inserted_id = insert_result.data[0]["id"]
                
                # Fetch the complete record
                result = db.client.table("profile_change_requests")\
                    .select("*")\
                    .eq("id", inserted_id)\
                    .single()\
                    .execute()
                
                # Parse JSON fields before using
                parsed_data = parse_json_fields(result.data)
                approval_request_created = True
                change_request_id = parsed_data["id"]
                approval_request_data = parsed_data
                
                # Log approval request
                await audit_service.log_action_from_request(
                    request=request,
                    action=AuditAction.SUPPLIER_UPDATED,
                    resource_type=AuditResourceType.SUPPLIER,
                    resource_id=supplier_id,
                    resource_name=current_supplier.get("company_name", ""),
                    current_user=current_vendor,
                    metadata={
                        "update_type": "approval_request",
                        "change_request_id": str(parsed_data["id"]),
                        "fields_requested": list(categorized["approval_required"].keys()),
                        "requested_changes": categorized["approval_required"]
                    }
                )
                
                # Send email notification to admins
                try:
                    admin_emails = await db.get_active_admin_emails()
                    if admin_emails:
                        # Build field list HTML
                        field_list_html = "".join([
                            f"<li><strong>{field}</strong></li>"
                            for field in categorized["approval_required"].keys()
                        ])
                        
                        # Prepare email data
                        email_data = {
                            "supplier_name": current_supplier.get("company_name", "Unknown"),
                            "registration_number": current_supplier.get("registration_number", "N/A"),
                            "status": current_supplier.get("status", "PENDING"),
                            "submitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                            "supplier_id": supplier_id,
                            "field_list": field_list_html,
                            "review_link": f"{settings.FRONTEND_URL}/admin/supplier/{supplier_id}"
                        }
                        
                        # Send email to all active admins
                        print(f"Sending profile change notification to {len(admin_emails)} admin(s)...")
                        results = await email_service.send_bulk_emails(
                            recipients=admin_emails,
                            template=EmailTemplate.ADMIN_PROFILE_CHANGE_REQUEST,
                            common_data=email_data
                        )
                        
                        success_count = sum(1 for s in results.values() if s)
                        print(f"Profile change emails sent: {success_count}/{len(results)} successful")
                    else:
                        print("Warning: No active admin emails found for profile change notification")
                except Exception as email_error:
                    # Log email error but don't fail the request
                    import traceback
                    print(f"Failed to send profile change notification emails: {str(email_error)}")
                    print(f"Traceback: {traceback.format_exc()}")
        
        # Build success message
        message_parts = []
        if direct_updates_applied > 0:
            message_parts.append(f"{direct_updates_applied} field(s) updated immediately")
        if approval_request_created:
            message_parts.append(f"{len(categorized['approval_required'])} field(s) pending admin approval")
        
        message = "Profile update processed. " + ". ".join(message_parts) + "."
        
        return ProfileUpdateResponse(
            success=True,
            message=message,
            direct_updates_applied=direct_updates_applied,
            approval_request_created=approval_request_created,
            change_request_id=change_request_id,
            direct_fields=list(categorized["direct"].keys()),
            approval_required_fields=list(categorized["approval_required"].keys()),
            approval_request=approval_request_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process profile changes: {str(e)}"
        )


@router.get("/vendor/my-requests", response_model=List[ProfileChangeHistoryItem])
async def get_vendor_change_requests(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    current_vendor: dict = Depends(get_current_vendor)
):
    """Get all profile change requests for the current vendor."""
    try:
        result = db.client.rpc("get_profile_change_history", {
            "p_supplier_id": current_vendor["id"],
            "p_limit": limit
        }).execute()
        
        if not result.data:
            return []
        
        # Parse JSON fields in each item
        parsed_items = [parse_json_fields(item) for item in result.data]
        return [ProfileChangeHistoryItem(**item) for item in parsed_items]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch change requests: {str(e)}"
        )


@router.get("/vendor/pending", response_model=Optional[ProfileChangeResponse])
async def get_vendor_pending_request(
    request: Request,
    current_vendor: dict = Depends(get_current_vendor)
):
    """Get the current pending profile change request for the vendor."""
    try:
        result = db.client.table("profile_change_requests")\
            .select("*")\
            .eq("supplier_id", current_vendor["id"])\
            .eq("status", "PENDING")\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        
        if result.data:
            parsed_data = parse_json_fields(result.data[0])
            return ProfileChangeResponse(**parsed_data)
        return None
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending request: {str(e)}"
        )


# ============================================================
# Admin Endpoints
# ============================================================

@router.get("/admin/pending", response_model=List[ProfileChangeListItem])
async def get_pending_profile_changes(
    request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """Get all pending profile change requests (admin view)."""
    try:
        result = db.client.rpc("get_pending_profile_changes").execute()
        
        if not result.data:
            return []
        
        # Parse JSON fields in each item
        parsed_items = [parse_json_fields(item) for item in result.data]
        return [ProfileChangeListItem(**item) for item in parsed_items]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending changes: {str(e)}"
        )


@router.get("/admin/all", response_model=List[ProfileChangeResponse])
async def get_all_profile_changes(
    request: Request,
    status_filter: Optional[str] = Query(None, pattern="^(PENDING|APPROVED|REJECTED|CANCELLED)$"),
    supplier_id: Optional[UUID4] = None,
    limit: int = Query(100, ge=1, le=500),
    current_admin: dict = Depends(get_current_admin)
):
    """Get all profile change requests with optional filters."""
    try:
        query = db.client.table("profile_change_requests").select("*")
        
        if status_filter:
            query = query.eq("status", status_filter)
        if supplier_id:
            query = query.eq("supplier_id", str(supplier_id))
        
        result = query.order("created_at", desc=True).limit(limit).execute()
        
        return [ProfileChangeResponse(**parse_json_fields(item)) for item in result.data] if result.data else []
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile changes: {str(e)}"
        )


@router.get("/admin/history", response_model=List[ProfileChangeListItem])
async def get_profile_changes_history(
    request: Request,
    status_filter: Optional[str] = Query(None, pattern="^(APPROVED|REJECTED|CANCELLED)$"),
    limit: int = Query(100, ge=1, le=500),
    current_admin: dict = Depends(get_current_admin)
):
    """Get resolved (non-pending) profile change requests with supplier info (admin view)."""
    try:
        query = db.client.table("profile_change_requests")\
            .select("*, suppliers:supplier_id(company_name, email)")\
            .neq("status", "PENDING")\
            .order("updated_at", desc=True)\
            .limit(limit)

        if status_filter:
            query = query.eq("status", status_filter)

        result = query.execute()

        if not result.data:
            return []

        items = []
        for item in result.data:
            parsed = parse_json_fields(item)
            supplier_info = parsed.pop("suppliers", None) or {}
            items.append(ProfileChangeListItem(
                id=parsed["id"],
                supplier_id=parsed["supplier_id"],
                company_name=supplier_info.get("company_name", "Unknown Vendor"),
                email=supplier_info.get("email", ""),
                requested_changes=parsed.get("requested_changes", {}),
                current_values=parsed.get("current_values", {}),
                status=parsed["status"],
                created_at=parsed["created_at"],
                reviewed_at=parsed.get("reviewed_at"),
                review_notes=parsed.get("review_notes"),
                days_pending=None,
            ))

        return items

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile change history: {str(e)}"
        )


@router.get("/admin/{request_id}", response_model=ProfileChangeResponse)
async def get_profile_change_detail(
    request: Request,
    request_id: UUID4,
    current_admin: dict = Depends(get_current_admin)
):
    """Get detailed information about a specific profile change request."""
    try:
        result = db.client.table("profile_change_requests")\
            .select("*")\
            .eq("id", str(request_id))\
            .single()\
            .execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile change request not found"
            )
        
        parsed_data = parse_json_fields(result.data)

        # Resolve reviewer name
        if parsed_data.get("reviewed_by"):
            reviewer = await db.get_admin_by_id(str(parsed_data["reviewed_by"]))
            if reviewer:
                parsed_data["reviewed_by_name"] = reviewer.get("full_name") or reviewer.get("name") or reviewer.get("email")

        return ProfileChangeResponse(**parsed_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile change: {str(e)}"
        )


@router.post("/admin/{request_id}/review", response_model=ProfileChangeResponse)
async def review_profile_change(
    request: Request,
    request_id: UUID4,
    review: ProfileChangeReviewRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Approve or reject a profile change request.
    If approved, automatically applies changes to supplier record.
    Sends email notification to vendor.
    """
    try:
        # Get the change request
        change_request = db.client.table("profile_change_requests")\
            .select("*")\
            .eq("id", str(request_id))\
            .single()\
            .execute()
        
        if not change_request.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile change request not found"
            )
        
        if change_request.data["status"] != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot review request with status: {change_request.data['status']}"
            )
        
        # Update request status
        new_status = "APPROVED" if review.action == "approve" else "REJECTED"
        
        db.client.table("profile_change_requests").update({
            "status": new_status,
            "reviewed_by": current_admin["id"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "review_notes": review.review_notes
        }).eq("id", str(request_id)).execute()
        
        # Fetch the updated record
        update_result = db.client.table("profile_change_requests")\
            .select("*")\
            .eq("id", str(request_id))\
            .single()\
            .execute()
        
        if not update_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update request status"
            )
        
        # If approved, apply changes
        if review.action == "approve":
            try:
                db.client.rpc("apply_profile_changes", {
                    "p_request_id": str(request_id)
                }).execute()

                requested_changes = parse_json_fields(dict(change_request.data)).get("requested_changes", {})
                await _apply_approved_structured_changes(
                    supplier_id=change_request.data["supplier_id"],
                    approved_changes=requested_changes,
                )
            except Exception as e:
                # Rollback status change if apply fails
                db.client.table("profile_change_requests").update({
                    "status": "PENDING",
                    "reviewed_by": None,
                    "reviewed_at": None,
                    "review_notes": None
                }).eq("id", str(request_id)).execute()
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to apply profile changes: {str(e)}"
                )

            await invalidate_analytics_cache()
        
        # Get supplier info for email
        supplier = await db.get_supplier_by_id(change_request.data["supplier_id"])
        
        # TODO: Send email notification
        # This will be implemented when we add email service
        # For now, we'll log it in the activity
        
        # Log audit action
        await audit_service.log_action_from_request(
            request=request,
            action=AuditAction.SUPPLIER_UPDATED if review.action == "approve" else AuditAction.SUPPLIER_REJECTED,
            resource_type=AuditResourceType.SUPPLIER,
            resource_id=change_request.data["supplier_id"],
            resource_name=supplier.get("company_name", "") if supplier else "",
            current_user=current_admin,
            metadata={
                "change_request_id": str(request_id),
                "action": review.action,
                "review_notes": review.review_notes,
                "requested_changes": change_request.data["requested_changes"]
            }
        )
        
        # Parse JSON fields if they're strings
        response_data = dict(update_result.data)
        if isinstance(response_data.get("requested_changes"), str):
            response_data["requested_changes"] = json.loads(response_data["requested_changes"])
        if isinstance(response_data.get("current_values"), str):
            response_data["current_values"] = json.loads(response_data["current_values"])
        
        return ProfileChangeResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to review profile change: {str(e)}"
        )


@router.get("/admin/supplier/{supplier_id}/history", response_model=List[ProfileChangeHistoryItem])
async def get_supplier_change_history(
    request: Request,
    supplier_id: UUID4,
    limit: int = Query(50, ge=1, le=100),
    current_admin: dict = Depends(get_current_admin)
):
    """Get profile change history for a specific supplier."""
    try:
        result = db.client.rpc("get_profile_change_history", {
            "p_supplier_id": str(supplier_id),
            "p_limit": limit
        }).execute()
        
        if not result.data:
            return []
        
        # Parse JSON fields in each item
        parsed_items = [parse_json_fields(item) for item in result.data]
        return [ProfileChangeHistoryItem(**item) for item in parsed_items]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch change history: {str(e)}"
        )
