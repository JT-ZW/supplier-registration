"""
Vendor authentication endpoints for supplier portal access.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import secrets
import jwt

from app.core.security import hash_password, verify_password
from app.core.config import settings
from app.db.supabase import db
from app.core.email import email_service
from app.services.audit import audit_service
from app.models.audit import AuditAction, AuditResourceType

router = APIRouter(prefix="/vendor", tags=["vendor-auth"])
security = HTTPBearer()


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


# ============== Helper Functions ==============

def create_vendor_access_token(supplier_id: str, email: str) -> str:
    """Create JWT access token for vendor."""
    payload = {
        "sub": supplier_id,
        "email": email,
        "type": "access",
        "role": "vendor",
        "exp": datetime.utcnow() + timedelta(days=7)  # 7-day expiry
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    return token


def decode_vendor_token(token: str) -> dict:
    """Decode and validate vendor JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "access":
            print(f"Token type mismatch: {payload.get('type')}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        # Verify it's a vendor token
        if payload.get("role") != "vendor":
            print(f"Token role mismatch: {payload.get('role')}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token role"
            )
        return payload
    except jwt.ExpiredSignatureError:
        print("Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Token decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


async def get_current_vendor(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get currently authenticated vendor from token."""
    token = credentials.credentials
    payload = decode_vendor_token(token)
    
    result = db._client.table("suppliers").select("*").eq("id", payload["sub"]).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    supplier = result.data[0]
    # Remove sensitive data
    supplier.pop("password_hash", None)
    supplier.pop("password_reset_token", None)
    supplier.pop("password_reset_expires", None)
    
    return supplier


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
    
    # Create access token
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
    return current_vendor


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
    
    updated_supplier.pop("password_hash", None)
    updated_supplier.pop("password_reset_token", None)
    updated_supplier.pop("password_reset_expires", None)
    
    return updated_supplier


@router.post("/submit-application")
async def submit_application(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Submit vendor application for review.
    Changes status from INCOMPLETE to SUBMITTED and sets submitted_at timestamp.
    """
    vendor = await get_current_vendor(credentials)
    
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
