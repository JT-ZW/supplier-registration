"""
Vendor authentication endpoints for supplier portal access.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field, model_validator
from jose import JWTError, jwt as jose_jwt
import secrets

from app.core.security import hash_password, verify_password
from app.core.config import settings
from app.db.supabase import db
from app.core.email import email_service
from app.core.cache_invalidation import invalidate_analytics_cache
from app.services.audit import audit_service
from app.models.audit import AuditAction, AuditResourceType
from app.models import BusinessCategory, Gender, KeyPersonRole, compute_business_size, compute_esg_flags
from app.api.deps import get_current_vendor  # noqa: E402 — imported after router models

router = APIRouter(prefix="/vendor", tags=["vendor-auth"])


# ============== Request/Response Models ==============

class VendorSignupRequest(BaseModel):
    """Vendor signup credentials."""
    email: EmailStr
    password: str


class VendorLoginRequest(BaseModel):
    """Vendor login credentials."""
    email: EmailStr
    password: str


class VendorLoginResponse(BaseModel):
    """Successful login response."""
    access_token: str
    token_type: str = "bearer"
    supplier: dict


class ForgotPasswordRequest(BaseModel):
    """Password reset request."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Password reset with token."""
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    """Change password for logged-in vendor."""
    current_password: str
    new_password: str


class DraftKeyPersonRequest(BaseModel):
    fullName: str = ""
    gender: Gender = Gender.UNSPECIFIED if hasattr(Gender, "UNSPECIFIED") else Gender.MALE
    dateOfBirth: Optional[str] = None
    role: KeyPersonRole = KeyPersonRole.DIRECTOR if hasattr(KeyPersonRole, "DIRECTOR") else KeyPersonRole.CONTACT

class DraftTradeReferenceRequest(BaseModel):
    companyName: str = ""
    contactPersonName: str = ""
    email: str = ""
    phone: str = ""
    relationship: str = ""
    serviceProduct: Optional[str] = None
    contractStartDate: Optional[str] = None
    contractEndDate: Optional[str] = None
    annualSpend: Optional[str] = None
    permissionGranted: bool = False

class VendorRegistrationDraftUpdateRequest(BaseModel):
    companyName: str = ""
    registrationNumber: Optional[str] = None
    taxId: Optional[str] = None
    yearsInBusiness: int = 0
    employeeCount: int = 0
    website: Optional[str] = None
    isSmallScaleFarmer: bool = False
    businessCategories: List[BusinessCategory] = []
    contactPersonName: str = ""
    contactPersonTitle: str = ""
    phone: str = ""
    streetAddress: str = ""
    city: str = ""
    stateProvince: str = ""
    postalCode: Optional[str] = None
    country: str = ""
    keyPersons: List[DraftKeyPersonRequest] = []
    tradeReferences: List[DraftTradeReferenceRequest] = []

async def _build_registration_draft_response(supplier_id: str) -> dict:
    supplier = db._client.table("suppliers").select("*").eq("id", supplier_id).single().execute().data
    categories = await db.get_supplier_categories(supplier_id)
    key_persons = await db.get_key_persons_by_supplier(supplier_id)
    trade_refs = await db.get_trade_references_by_supplier(supplier_id)
    farmer_form = await db.get_farmer_form(supplier_id)

    business_categories = [item["category"] for item in categories] if categories else [supplier.get("business_category")]

    def _strip_placeholder(val, default=""):
        if not val:
            return default
        if isinstance(val, str):
            v_upper = val.upper().strip()
            if v_upper == "PENDING" or v_upper == "PENDING CITY" or v_upper == "ZW":
                return default
            if all(c == '0' for c in v_upper) and len(v_upper) > 0:
                return default
        return val

    return {
        "supplierId": supplier_id,
        "email": supplier.get("email"),
        "status": supplier.get("status"),
        "companyName": _strip_placeholder(supplier.get("company_name")),
        "registrationNumber": _strip_placeholder(supplier.get("registration_number")),
        "taxId": _strip_placeholder(supplier.get("tax_id")),
        "yearsInBusiness": supplier.get("years_in_business") if supplier.get("years_in_business") is not None else 0,
        "employeeCount": supplier.get("employee_count") if supplier.get("employee_count") is not None else 0,
        "website": _strip_placeholder(supplier.get("website")),
        "isSmallScaleFarmer": bool(supplier.get("is_small_scale_farmer")),
        "businessCategories": [cat for cat in business_categories if cat and str(cat).upper() != "SERVICES"],
        "contactPersonName": _strip_placeholder(supplier.get("contact_person_name")),
        "contactPersonTitle": _strip_placeholder(supplier.get("contact_person_title")),
        "phone": _strip_placeholder(supplier.get("phone")),
        "streetAddress": _strip_placeholder(supplier.get("street_address")),
        "city": _strip_placeholder(supplier.get("city")),
        "stateProvince": _strip_placeholder(supplier.get("state_province")),
        "postalCode": _strip_placeholder(supplier.get("postal_code")),
        "country": _strip_placeholder(supplier.get("country")),
        "keyPersons": [
            {
                "fullName": person.get("full_name") or "",
                "gender": person.get("gender") or Gender.MALE.value,
                "dateOfBirth": person.get("date_of_birth"),
                "role": person.get("role") or KeyPersonRole.DIRECTOR.value,
            }
            for person in key_persons
        ],
        "tradeReferences": [
            {
                "companyName": reference.get("company_name") or "",
                "contactPersonName": reference.get("contact_person_name") or "",
                "email": reference.get("email") or "",
                "phone": reference.get("phone") or "",
                "relationship": reference.get("relationship") or "",
                "serviceProduct": reference.get("service_product") or "",
                "contractStartDate": reference.get("contract_start_date"),
                "contractEndDate": reference.get("contract_end_date"),
                "annualSpend": reference.get("annual_spend") or "",
                "permissionGranted": bool(reference.get("permission_granted")),
            }
            for reference in trade_refs
        ],
        "farmerForm": (
            {
                "contactFullName": farmer_form.get("contact_full_name") or "",
                "idNumber": farmer_form.get("id_number") or "",
                "gender": farmer_form.get("gender") or "",
                "dateOfBirth": farmer_form.get("date_of_birth"),
                "farmingActivity": farmer_form.get("farming_activity") or "",
                "produceTypes": farmer_form.get("produce_types") or "",
                "estimatedLandSizeHa": farmer_form.get("estimated_land_size_ha"),
                "yearsFarming": farmer_form.get("years_farming"),
                "landProofType": farmer_form.get("land_proof_type") or "",
                "villageOrFarmName": farmer_form.get("village_or_farm_name") or "",
                "district": farmer_form.get("district") or "",
                "province": farmer_form.get("province") or "",
                "contactPhone": farmer_form.get("contact_phone") or "",
                "hasBankAccount": bool(farmer_form.get("has_bank_account")),
                "bankName": farmer_form.get("bank_name") or "",
            }
            if farmer_form
            else None
        ),
        "updatedAt": supplier.get("updated_at") or supplier.get("created_at"),
    }


# ============== Helper Functions ==============

def create_vendor_access_token(supplier_id: str, email: str) -> str:
    """Create a vendor JWT access token using python-jose (same library as admin tokens)."""
    expire = datetime.utcnow() + timedelta(days=settings.VENDOR_JWT_EXPIRE_DAYS)
    payload = {
        "sub": supplier_id,
        "email": email,
        "type": "access",
        "role": "vendor",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jose_jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_vendor_token(token: str) -> dict:
    """Decode and validate a vendor JWT token using python-jose."""
    try:
        payload = jose_jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        # ExpiredSignatureError is a subclass of JWTError in python-jose
        detail = "Token has expired" if "expired" in str(exc).lower() else "Invalid token"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    if payload.get("role") != "vendor":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token role")
    return payload


# ============== Endpoints ==============

@router.post("/signup", response_model=VendorLoginResponse)
async def vendor_signup(request: VendorSignupRequest):
    """
    Vendor signup endpoint - creates initial vendor account.
    
    This creates a minimal vendor record with just email and password.
    The vendor will complete their company registration in the next step.
    """
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Check if email already exists
    existing = db._client.table("suppliers").select("id").eq("email", request.email).execute()
    
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists"
        )
    
    # Create minimal supplier record with placeholders for required fields
    from uuid import uuid4
    from datetime import datetime
    
    supplier_data = {
        "id": str(uuid4()),
        "company_name": f"PENDING_{request.email.split('@')[0].upper()}",  # Placeholder, updated during registration
        "business_category": "OTHER",  # Placeholder, updated during registration
        "registration_number": "PENDING",  # Placeholder, updated during registration
        "tax_id": "PENDING",  # Placeholder, updated during registration
        "years_in_business": 0,  # Placeholder, updated during registration
        "contact_person_name": "Pending",  # Placeholder, updated during registration
        "contact_person_title": "Pending",  # Placeholder, updated during registration
        "phone": "0000000000",  # Placeholder, updated during registration
        "street_address": "Pending",  # Placeholder, updated during registration
        "city": "Pending",  # Placeholder, updated during registration
        "state_province": "Pending",  # Placeholder, updated during registration
        "postal_code": "0000",  # Placeholder, updated during registration
        "country": "Pending",  # Placeholder, updated during registration
        "email": request.email,
        "password_hash": hash_password(request.password),
        "status": "INCOMPLETE",  # Will be updated during registration
        "created_at": datetime.utcnow().isoformat(),
    }
    
    result = db._client.table("suppliers").insert(supplier_data).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create vendor account"
        )
    
    supplier = result.data[0]
    
    # Log account creation audit action
    await audit_service.log_action(
        action=AuditAction.SUPPLIER_CREATED,
        resource_type=AuditResourceType.SUPPLIER,
        user_id=supplier["id"],
        user_type="vendor",
        resource_id=supplier["id"],
        resource_name=supplier.get("company_name", "PENDING_VENDOR"),
        metadata={"email": request.email}
    )

    access_token = create_vendor_access_token(supplier["id"], supplier["email"])

    
    # Remove sensitive data
    supplier.pop("password_hash", None)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "supplier": supplier
    }


@router.post("/login", response_model=VendorLoginResponse)
async def vendor_login(credentials: VendorLoginRequest):
    """
    Vendor login endpoint.
    
    Returns JWT access token for authenticated vendors.
    """
    # Get supplier by email
    result = db._client.table("suppliers").select("*").eq("email", credentials.email).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    supplier = result.data[0]
    
    # Check if password is set
    if not supplier.get("password_hash"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password not set. Please use the password reset link sent to your email."
        )
    
    # Verify password
    if not verify_password(credentials.password, supplier["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Update last login
    db._client.table("suppliers").update({
        "last_login": datetime.utcnow().isoformat()
    }).eq("id", supplier["id"]).execute()
    
    # Create access token
    access_token = create_vendor_access_token(supplier["id"], supplier["email"])
    
    # Remove sensitive data
    supplier.pop("password_hash", None)
    supplier.pop("password_reset_token", None)
    supplier.pop("password_reset_expires", None)
    
    # Log vendor login
    await audit_service.log_action(
        action=AuditAction.VENDOR_LOGIN,
        resource_type=AuditResourceType.SUPPLIER,
        user_id=supplier["id"],
        user_type="vendor",
        resource_id=supplier["id"],
        resource_name=supplier.get("company_name"),
        metadata={"login_at": datetime.utcnow().isoformat()}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "supplier": supplier
    }


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """
    Request password reset email.
    
    Sends reset link to vendor's email if account exists.
    Always returns success to prevent email enumeration.
    """
    result = db._client.table("suppliers").select("id, email, company_name").eq("email", request.email).execute()
    
    if result.data:
        supplier = result.data[0]
        
        # Generate reset token (32 bytes = 43 characters in base64)
        reset_token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=24)
        
        # Save token to database
        db._client.table("suppliers").update({
            "password_reset_token": reset_token,
            "password_reset_expires": expires.isoformat()
        }).eq("id", supplier["id"]).execute()
        
        # Send reset email
        reset_link = f"{settings.FRONTEND_URL}/vendor/reset-password?token={reset_token}"
        
        await email_service.send_email(
            to_email=supplier["email"],
            subject="Reset Your Vendor Portal Password",
            html_content=f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2>Password Reset Request</h2>
                <p>Hello {supplier['company_name']},</p>
                <p>We received a request to reset your password for the RTG Vendor Portal.</p>
                <p>Click the link below to reset your password:</p>
                <p style="margin: 20px 0;">
                    <a href="{reset_link}" style="background-color: #4F46E5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                        Reset Password
                    </a>
                </p>
                <p>This link will expire in 24 hours.</p>
                <p>If you didn't request this, please ignore this email.</p>
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e5e5;">
                <p style="color: #666; font-size: 12px;">
                    Rainbow Tourism Group<br>
                    Supplier Portal
                </p>
            </div>
            """,
            to_name=supplier['company_name']
        )
    
    # Always return success to prevent email enumeration
    return {
        "message": "If an account exists with that email, a password reset link has been sent."
    }


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """
    Reset password using token from email.
    """
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Find supplier with valid reset token
    result = db._client.table("suppliers").select("*").eq("password_reset_token", request.token).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    supplier = result.data[0]
    
    # Check if token is expired
    if supplier.get("password_reset_expires"):
        expires = datetime.fromisoformat(supplier["password_reset_expires"].replace("Z", "+00:00"))
        if datetime.utcnow().replace(tzinfo=expires.tzinfo) > expires:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired. Please request a new one."
            )
    
    # Hash new password
    password_hash = hash_password(request.new_password)
    
    # Update password and clear reset token
    db._client.table("suppliers").update({
        "password_hash": password_hash,
        "password_reset_token": None,
        "password_reset_expires": None,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", supplier["id"]).execute()
    
    return {"message": "Password has been reset successfully. You can now login."}


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_vendor: dict = Depends(get_current_vendor)
):
    """
    Change password for currently logged-in vendor.
    """
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Get current password hash
    result = db._client.table("suppliers").select("password_hash").eq("id", current_vendor["id"]).execute()
    
    if not result.data or not result.data[0].get("password_hash"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No password set for this account"
        )
    
    # Verify current password
    if not verify_password(request.current_password, result.data[0]["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Hash new password
    new_password_hash = hash_password(request.new_password)
    
    # Update password
    db._client.table("suppliers").update({
        "password_hash": new_password_hash,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", current_vendor["id"]).execute()
    
    # Log password change
    await audit_service.log_action(
        action=AuditAction.VENDOR_PASSWORD_CHANGED,
        resource_type=AuditResourceType.SUPPLIER,
        user_id=current_vendor["id"],
        user_type="vendor",
        resource_id=current_vendor["id"],
        resource_name=current_vendor.get("company_name"),
        metadata={"changed_at": datetime.utcnow().isoformat()}
    )
    
    return {"message": "Password changed successfully"}


@router.get("/me")
async def get_vendor_profile(current_vendor: dict = Depends(get_current_vendor)):
    """
    Get current vendor's profile information.
    """
    vendor_data = current_vendor.copy()
    vendor_data.pop("password_hash", None)
    vendor_data.pop("password_reset_token", None)
    return vendor_data


@router.get("/profile")
async def get_vendor_profile_alias(current_vendor: dict = Depends(get_current_vendor)):
    """
    Get current vendor's profile information (alias for /me).
    """
    vendor_data = current_vendor.copy()
    vendor_data.pop("password_hash", None)
    vendor_data.pop("password_reset_token", None)
    return vendor_data


@router.get("/registration-draft")
async def get_registration_draft(current_vendor: dict = Depends(get_current_vendor)):
    """Get the authenticated vendor's registration draft for autosave/resume."""
    return await _build_registration_draft_response(current_vendor["id"])


@router.put("/registration-draft")
async def save_registration_draft(
    request: VendorRegistrationDraftUpdateRequest,
    current_vendor: dict = Depends(get_current_vendor),
):
    """Save the authenticated vendor's registration draft data."""
    if current_vendor["status"] not in ["INCOMPLETE", "NEED_MORE_INFO"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration draft cannot be updated in current status",
        )

    supplier_id = current_vendor["id"]

    if request.isSmallScaleFarmer:
        effective_categories = [BusinessCategory.FRESH_FARM_PRODUCE]
        registration_number = (request.registrationNumber or "N/A").strip() or "N/A"
        tax_id = (request.taxId or "N/A").strip() or "N/A"
    else:
        effective_categories = request.businessCategories or []
        registration_number = (request.registrationNumber or "").strip()
        tax_id = (request.taxId or "").strip()

    key_persons_payload = [
        {
            "full_name": request.contactPersonName if request.isSmallScaleFarmer else person.fullName,
            "gender": person.gender.value if hasattr(person.gender, "value") else person.gender,
            "date_of_birth": person.dateOfBirth,
            "role": KeyPersonRole.CONTACT.value if request.isSmallScaleFarmer else (person.role.value if hasattr(person.role, "value") else person.role),
        }
        for person in request.keyPersons
    ]

    # Draft saves happen while users are still typing. Persist only valid records to avoid DB constraint failures.
    persistable_key_persons = [
        person
        for person in key_persons_payload
        if (person.get("full_name") or "").strip()
        and person.get("date_of_birth")
    ]

    esg_flags = compute_esg_flags(persistable_key_persons)
    business_size = compute_business_size(request.employeeCount)

    supplier_update = {
        "company_name": request.companyName or current_vendor.get("company_name", ""),
        "business_category": effective_categories[0].value if effective_categories else current_vendor.get("business_category", "Services"),
        "registration_number": registration_number or current_vendor.get("registration_number", ""),
        "tax_id": tax_id or current_vendor.get("tax_id", ""),
        "years_in_business": request.yearsInBusiness or current_vendor.get("years_in_business", 0),
        "employee_count": request.employeeCount or current_vendor.get("employee_count", 0),
        "website": request.website or "",
        "is_small_scale_farmer": request.isSmallScaleFarmer,
        "contact_person_name": request.contactPersonName or current_vendor.get("contact_person_name", ""),
        "contact_person_title": request.contactPersonTitle or current_vendor.get("contact_person_title", ""),
        "phone": request.phone or current_vendor.get("phone", ""),
        "street_address": request.streetAddress or current_vendor.get("street_address", ""),
        "city": request.city or current_vendor.get("city", ""),
        "state_province": request.stateProvince or current_vendor.get("state_province", ""),
        "postal_code": request.postalCode or "",
        "country": request.country or current_vendor.get("country", ""),
        "business_size": business_size.value if business_size else current_vendor.get("business_size"),
        "esg_women_owned": esg_flags["esg_women_owned"],
        "esg_youth_owned": esg_flags["esg_youth_owned"],
        "updated_at": datetime.utcnow().isoformat(),
    }

    if current_vendor["status"] == "NEED_MORE_INFO":
        supplier_update["status"] = "INCOMPLETE"
        supplier_update["info_request_message"] = None

    updated_supplier = db._client.table("suppliers").update(supplier_update).eq("id", supplier_id).execute()
    if not updated_supplier.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save registration draft",
        )

    await db.delete_key_persons_by_supplier(supplier_id)
    for person in persistable_key_persons:
        await db.create_key_person(
            {
                "supplier_id": supplier_id,
                "full_name": person["full_name"],
                "gender": person["gender"],
                "date_of_birth": person["date_of_birth"],
                "role": person["role"],
            }
        )

    await db.delete_trade_references_by_supplier(supplier_id)
    for reference in request.tradeReferences:
        company_name = (reference.companyName or "").strip()
        contact_person_name = (reference.contactPersonName or "").strip()
        email = (str(reference.email) if reference.email is not None else "").strip()
        phone = (reference.phone or "").strip()
        relationship = (reference.relationship or "").strip()
        has_minimum_reference_data = (
            len(company_name) >= 2
            and len(contact_person_name) >= 2
            and len(email) > 0
            and len(phone) >= 7
            and len(relationship) >= 2
            and bool(reference.permissionGranted)
        )

        if not has_minimum_reference_data:
            continue

        await db.create_trade_reference(
            {
                "supplier_id": supplier_id,
                "company_name": company_name,
                "contact_person_name": contact_person_name,
                "email": email,
                "phone": phone,
                "relationship": relationship,
                "service_product": reference.serviceProduct,
                "contract_start_date": reference.contractStartDate,
                "contract_end_date": reference.contractEndDate,
                "annual_spend": reference.annualSpend,
                "permission_granted": reference.permissionGranted,
            }
        )

    await db.delete_supplier_categories(supplier_id)
    for category in effective_categories:
        await db.create_supplier_category(
            {
                "supplier_id": supplier_id,
                "category": category.value,
                "compliance_status": "PENDING",
            }
        )

    await invalidate_analytics_cache(scope="summary")

    return await _build_registration_draft_response(supplier_id)


@router.put("/me")
async def update_vendor_profile(update_data: dict, current_vendor: dict = Depends(get_current_vendor)):
    """
    Update current vendor's profile information.
    Allows vendors to update their info when status is NEED_MORE_INFO.
    """
    from app.models.supplier import SupplierUpdateRequest
    
    # Only allow updates if status is INCOMPLETE or NEED_MORE_INFO
    if current_vendor["status"] not in ["INCOMPLETE", "NEED_MORE_INFO"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Profile cannot be edited in current status"
        )
    
    # Validate update data
    try:
        validated_data = SupplierUpdateRequest(**update_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid data: {str(e)}"
        )
    
    # Prepare update dict (exclude None values) - use by_alias=False for database snake_case columns
    update_dict = {k: v for k, v in validated_data.model_dump(by_alias=False, exclude_none=True).items()}
    update_dict["updated_at"] = datetime.utcnow().isoformat()
    
    # If status was NEED_MORE_INFO, reset to INCOMPLETE so admin can review again
    if current_vendor["status"] == "NEED_MORE_INFO":
        update_dict["status"] = "INCOMPLETE"
        update_dict["info_request_message"] = None
    
    # Update supplier
    result = db._client.table("suppliers").update(update_dict).eq("id", current_vendor["id"]).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )
    
    updated_supplier = result.data[0]
    
    # Send admin notification for profile updates if in certain statuses
    if updated_supplier["status"] in ["NEED_MORE_INFO", "UNDER_REVIEW", "SUBMITTED"]:
        try:
            from app.core.email import email_service, EmailTemplate
            from app.core.config import settings
            
            await email_service.send_template_email(
                to_email=settings.ADMIN_EMAIL,
                template=EmailTemplate.ADMIN_PROFILE_UPDATED,
                data={
                    "supplier_name": updated_supplier["company_name"],
                    "registration_number": updated_supplier.get("registration_number", "N/A"),
                    "status": updated_supplier["status"],
                    "updated_at": updated_supplier["updated_at"],
                    "supplier_id": updated_supplier["id"],
                    "affected_statuses": "NEED_MORE_INFO, UNDER_REVIEW, or SUBMITTED",
                    "review_link": f"{settings.FRONTEND_URL}/admin/suppliers/{updated_supplier['id']}"
                },
                to_name="Admin Team"
            )
        except Exception as e:
            print(f"Failed to send admin notification: {str(e)}")

    await invalidate_analytics_cache(scope="summary")
    
    updated_supplier.pop("password_hash", None)
    updated_supplier.pop("password_reset_token", None)
    updated_supplier.pop("password_reset_expires", None)
    
    return updated_supplier


@router.patch("/profile")
async def update_vendor_profile_alias(update_data: dict, current_vendor: dict = Depends(get_current_vendor)):
    """
    Update current vendor's profile information (alias for PUT /me).
    Allows vendors to update their info when status is NEED_MORE_INFO.
    """
    from app.models.supplier import SupplierUpdateRequest
    
    # Only allow updates if status is INCOMPLETE or NEED_MORE_INFO
    if current_vendor["status"] not in ["INCOMPLETE", "NEED_MORE_INFO"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Profile cannot be edited in current status"
        )
    
    # Validate update data
    try:
        validated_data = SupplierUpdateRequest(**update_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid data: {str(e)}"
        )
    
    # Prepare update dict (exclude None values) - use by_alias=False for database snake_case columns
    update_dict = {k: v for k, v in validated_data.model_dump(by_alias=False, exclude_none=True).items()}
    update_dict["updated_at"] = datetime.utcnow().isoformat()
    
    # If status was NEED_MORE_INFO, reset to INCOMPLETE so admin can review again
    if current_vendor["status"] == "NEED_MORE_INFO":
        update_dict["status"] = "INCOMPLETE"
        update_dict["info_request_message"] = None
    
    # Update supplier
    result = db._client.table("suppliers").update(update_dict).eq("id", current_vendor["id"]).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )
    
    updated_supplier = result.data[0]
    
    # Send admin notification for profile updates if in certain statuses
    if updated_supplier["status"] in ["NEED_MORE_INFO", "UNDER_REVIEW", "SUBMITTED"]:
        try:
            from app.core.email import email_service, EmailTemplate
            from app.core.config import settings
            
            await email_service.send_template_email(
                to_email=settings.ADMIN_EMAIL,
                template=EmailTemplate.ADMIN_PROFILE_UPDATED,
                data={
                    "supplier_name": updated_supplier["company_name"],
                    "registration_number": updated_supplier.get("registration_number", "N/A"),
                    "status": updated_supplier["status"],
                    "updated_at": updated_supplier["updated_at"],
                    "supplier_id": updated_supplier["id"],
                    "affected_statuses": "NEED_MORE_INFO, UNDER_REVIEW, or SUBMITTED",
                    "review_link": f"{settings.FRONTEND_URL}/admin/suppliers/{updated_supplier['id']}"
                },
                to_name="Admin Team"
            )
        except Exception as e:
            print(f"Failed to send admin notification: {str(e)}")

    await invalidate_analytics_cache(scope="summary")
    
    updated_supplier.pop("password_hash", None)
    updated_supplier.pop("password_reset_token", None)
    updated_supplier.pop("password_reset_expires", None)
    
    return updated_supplier


@router.post("/submit-application")
async def submit_application(vendor: dict = Depends(get_current_vendor)):
    """
    Submit vendor application for review.
    Changes status from INCOMPLETE to SUBMITTED and sets submitted_at timestamp.
    """
    # Check if already submitted
    if vendor["status"] != "INCOMPLETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application already submitted or being processed"
        )
    
    # Validate that profile is complete (basic check)
    required_fields = ["company_name", "registration_number", "contact_person_name", "email", "phone", "business_category"]
    missing_fields = [field for field in required_fields if not vendor.get(field)]
    
    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Please complete required fields: {', '.join(missing_fields)}"
        )
    
    # Check if documents are uploaded
    docs_result = db._client.table("documents").select("*").eq("supplier_id", vendor["id"]).execute()
    if not docs_result.data or len(docs_result.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload at least one document before submitting"
        )
    
    # Update status to SUBMITTED and set submitted_at
    # Note: Remove admin_notes from this update - it's for admin use only
    result = db._client.table("suppliers").update({
        "status": "SUBMITTED",
        "submitted_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "info_request_message": None  # Clear any previous admin requests
    }).eq("id", vendor["id"]).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit application"
        )

    updated_supplier = result.data[0]

    # Log submission audit
    await audit_service.log_action(
        action=AuditAction.SUPPLIER_SUBMITTED,
        resource_type=AuditResourceType.SUPPLIER,
        user_id=vendor["id"],
        user_type="vendor",
        resource_id=vendor["id"],
        resource_name=updated_supplier.get("company_name", vendor.get("company_name")),
        changes={"status": {"old": vendor["status"], "new": "SUBMITTED"}}
    )

    # Send admin notification email
    try:
        from app.core.email import email_service, EmailTemplate
        from app.core.config import settings
        
        await email_service.send_template_email(
            to_email=settings.ADMIN_EMAIL,
            template=EmailTemplate.ADMIN_APPLICATION_SUBMITTED,
            data={
                "supplier_name": updated_supplier["company_name"],
                "registration_number": updated_supplier.get("registration_number", "N/A"),
                "category": updated_supplier.get("business_category", "N/A"),
                "contact_person": updated_supplier.get("contact_person_name", "N/A"),
                "email": updated_supplier["email"],
                "phone": updated_supplier.get("phone_number", "N/A"),
                "submitted_at": updated_supplier["submitted_at"],
                "supplier_id": updated_supplier["id"],
                "review_link": f"{settings.FRONTEND_URL}/admin/suppliers/{updated_supplier['id']}"
            },
            to_name="Admin Team"
        )
    except Exception as e:
        print(f"Failed to send admin notification: {str(e)}")
    
    # Send confirmation email to vendor
    try:
        await email_service.send_template_email(
            to_email=updated_supplier["email"],
            template=EmailTemplate.SUPPLIER_REGISTRATION_SUBMITTED,
            data={
                "supplier_name": updated_supplier["company_name"],
                "contact_person": updated_supplier.get("contact_person_name", "Vendor"),
                "supplier_id": updated_supplier["id"]
            },
            to_name=updated_supplier.get("contact_person_name", "Vendor")
        )
        print(f"Confirmation email sent to vendor: {updated_supplier['email']}")
    except Exception as e:
        print(f"Failed to send vendor confirmation email: {str(e)}")

    await invalidate_analytics_cache()

    # Compute initial per-category compliance levels now that docs are attached.
    try:
        from app.db.supabase import db as _db
        await _db.recompute_supplier_category_compliance(vendor["id"])
    except Exception as _ce:
        print(f"⚠️  compliance recompute skipped on submission for {vendor['id']}: {_ce}")

    updated_supplier.pop("password_hash", None)
    updated_supplier.pop("password_reset_token", None)
    updated_supplier.pop("password_reset_expires", None)
    
    return {
        "message": "Application submitted successfully",
        "supplier": updated_supplier
    }


@router.post("/set-initial-password")
async def set_initial_password(email: EmailStr, password: str):
    """
    Set initial password for a newly registered supplier.
    This would typically be called during registration or sent via email.
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Check if supplier exists
    result = db._client.table("suppliers").select("id, password_hash").eq("email", email).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    supplier = result.data[0]
    
    # Check if password already set
    if supplier.get("password_hash"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password already set. Use forgot password to reset."
        )
    
    # Hash and save password
    password_hash = hash_password(password)
    
    db._client.table("suppliers").update({
        "password_hash": password_hash,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", supplier["id"]).execute()
    
    return {"message": "Password set successfully. You can now login."}


