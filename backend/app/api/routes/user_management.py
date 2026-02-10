"""
User Management API routes for System Administrators.
Manage admin users and vendor users with full CRUD operations.
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request

from ...db.supabase import db
from ...services.audit_service import audit_service, AuditAction
from ...api.deps import get_current_admin, require_system_admin, get_client_ip
from ...models import (
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    AdminPasswordResetRequest,
    AdminUserResponse,
    AdminUserListResponse,
    VendorUserUpdateRequest,
    VendorPasswordResetRequest,
    VendorUserResponse,
    VendorUserListResponse,
    UnlockAccountRequest,
    SuccessResponse,
    AdminRole,
)
from ...core.security import hash_password
from ...core.email import email_service, EmailTemplate
from ...core.timezone import get_cat_now, format_cat_datetime


router = APIRouter(prefix="/admin/users", tags=["User Management"])


# ============== Admin User Management ==============

@router.get("/admin-users", response_model=AdminUserListResponse)
async def list_admin_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    current_admin: dict = Depends(require_system_admin),
):
    """
    List all admin users with pagination and filtering.
    Only accessible by System Administrators.
    """
    offset = (page - 1) * page_size
    
    # Build query
    query = db.client.table("admin_users").select("*", count="exact")
    
    # Apply filters
    if role:
        query = query.eq("role", role)
    if is_active is not None:
        query = query.eq("is_active", is_active)
    if search:
        query = query.or_(
            f"full_name.ilike.%{search}%,"
            f"email.ilike.%{search}%,"
            f"department.ilike.%{search}%,"
            f"position.ilike.%{search}%"
        )
    
    # Get total count
    count_response = query
    
    # Apply pagination
    query = query.range(offset, offset + page_size - 1).order("created_at", desc=True)
    
    response = query.execute()
    
    if not response.data:
        return AdminUserListResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0
        )
    
    total = len(response.data) if not hasattr(response, 'count') else response.count
    total_pages = (total + page_size - 1) // page_size
    
    items = [
        AdminUserResponse(
            id=str(user["id"]),
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            phone=user.get("phone"),
            department=user.get("department"),
            position=user.get("position"),
            is_active=user["is_active"],
            must_change_password=user.get("must_change_password", False),
            last_login=user.get("last_login"),
            last_password_change=user.get("last_password_change"),
            failed_login_attempts=user.get("failed_login_attempts", 0),
            account_locked_until=user.get("account_locked_until"),
            created_at=user["created_at"],
            created_by=str(user["created_by"]) if user.get("created_by") else None,
            updated_at=user.get("updated_at"),
            updated_by=str(user["updated_by"]) if user.get("updated_by") else None,
        )
        for user in response.data
    ]
    
    return AdminUserListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.post("/admin-users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    request: AdminUserCreateRequest,
    current_admin: dict = Depends(require_system_admin),
    http_request: Request = None,
):
    """
    Create a new admin user.
    Only accessible by System Administrators.
    """
    # Check if email already exists
    existing = db.client.table("admin_users").select("id").eq("email", request.email).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An admin user with this email already exists"
        )
    
    # Hash password
    password_hash = hash_password(request.password)
    
    # Create user
    user_data = {
        "id": str(uuid4()),
        "email": request.email,
        "password_hash": password_hash,
        "full_name": request.full_name,
        "role": request.role.value,
        "phone": request.phone,
        "department": request.department,
        "position": request.position,
        "is_active": True,
        "must_change_password": request.must_change_password,
        "failed_login_attempts": 0,
        "created_at": get_cat_now().isoformat(),
        "created_by": current_admin["id"],
        "last_password_change": get_cat_now().isoformat(),
    }
    
    response = db.client.table("admin_users").insert(user_data).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create admin user"
        )
    
    created_user = response.data[0]
    
    # Log user creation
    audit_service.log_user_management(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=AuditAction.USER_CREATED,
        target_user_id=created_user["id"],
        target_user_email=created_user["email"],
        details={
            "full_name": created_user["full_name"],
            "role": created_user["role"],
            "department": created_user.get("department"),
        },
        ip_address=get_client_ip(http_request) if http_request else None
    )
    
    # Send welcome email
    try:
        await email_service.send_email(
            to_email=request.email,
            template=EmailTemplate.ADMIN_WELCOME,
            context={
                "full_name": request.full_name,
                "email": request.email,
                "temporary_password": request.password,
                "role": request.role.value.replace("_", " ").title(),
                "must_change_password": request.must_change_password,
            }
        )
    except Exception as e:
        print(f"Failed to send welcome email: {str(e)}")
    
    return AdminUserResponse(
        id=str(created_user["id"]),
        email=created_user["email"],
        full_name=created_user["full_name"],
        role=created_user["role"],
        phone=created_user.get("phone"),
        department=created_user.get("department"),
        position=created_user.get("position"),
        is_active=created_user["is_active"],
        must_change_password=created_user.get("must_change_password", False),
        last_login=created_user.get("last_login"),
        last_password_change=created_user.get("last_password_change"),
        failed_login_attempts=created_user.get("failed_login_attempts", 0),
        account_locked_until=created_user.get("account_locked_until"),
        created_at=created_user["created_at"],
        created_by=str(created_user["created_by"]) if created_user.get("created_by") else None,
        updated_at=created_user.get("updated_at"),
        updated_by=str(created_user["updated_by"]) if created_user.get("updated_by") else None,
    )


@router.get("/admin-users/{user_id}", response_model=AdminUserResponse)
async def get_admin_user(
    user_id: str,
    current_admin: dict = Depends(require_system_admin),
):
    """
    Get details of a specific admin user.
    Only accessible by System Administrators.
    """
    response = db.client.table("admin_users").select("*").eq("id", user_id).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found"
        )
    
    user = response.data[0]
    
    return AdminUserResponse(
        id=str(user["id"]),
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        phone=user.get("phone"),
        department=user.get("department"),
        position=user.get("position"),
        is_active=user["is_active"],
        must_change_password=user.get("must_change_password", False),
        last_login=user.get("last_login"),
        last_password_change=user.get("last_password_change"),
        failed_login_attempts=user.get("failed_login_attempts", 0),
        account_locked_until=user.get("account_locked_until"),
        created_at=user["created_at"],
        created_by=str(user["created_by"]) if user.get("created_by") else None,
        updated_at=user.get("updated_at"),
        updated_by=str(user["updated_by"]) if user.get("updated_by") else None,
    )


@router.put("/admin-users/{user_id}", response_model=AdminUserResponse)
async def update_admin_user(
    user_id: str,
    request: AdminUserUpdateRequest,
    current_admin: dict = Depends(require_system_admin),
    http_request: Request = None,
):
    """
    Update an admin user's information.
    Only accessible by System Administrators.
    """
    # Check if user exists
    existing = db.client.table("admin_users").select("*").eq("id", user_id).execute()
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found"
        )
    
    # Prevent self-deactivation
    if user_id == current_admin["id"] and request.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account"
        )
    
    # Build update data
    update_data = {"updated_by": current_admin["id"], "updated_at": get_cat_now().isoformat()}
    updated_fields = []
    
    if request.full_name is not None:
        update_data["full_name"] = request.full_name
        updated_fields.append("full_name")
    if request.role is not None:
        update_data["role"] = request.role.value
        updated_fields.append("role")
    if request.phone is not None:
        update_data["phone"] = request.phone
        updated_fields.append("phone")
    if request.department is not None:
        update_data["department"] = request.department
        updated_fields.append("department")
    if request.position is not None:
        update_data["position"] = request.position
        updated_fields.append("position")
    if request.is_active is not None:
        update_data["is_active"] = request.is_active
        updated_fields.append("is_active")
    
    response = db.client.table("admin_users").update(update_data).eq("id", user_id).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update admin user"
        )
    
    user = response.data[0]
    
    # Log user update
    action = AuditAction.USER_DEACTIVATED if (request.is_active is False and existing.data[0].get("is_active")) else \
             AuditAction.USER_ACTIVATED if (request.is_active is True and not existing.data[0].get("is_active")) else \
             AuditAction.USER_UPDATED
    
    audit_service.log_user_management(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=action,
        target_user_id=user_id,
        target_user_email=user["email"],
        details={
            "full_name": user["full_name"],
            "updated_fields": updated_fields,
            "new_role": user.get("role") if "role" in updated_fields else None,
        },
        ip_address=get_client_ip(http_request) if http_request else None
    )
    
    return AdminUserResponse(
        id=str(user["id"]),
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        phone=user.get("phone"),
        department=user.get("department"),
        position=user.get("position"),
        is_active=user["is_active"],
        must_change_password=user.get("must_change_password", False),
        last_login=user.get("last_login"),
        last_password_change=user.get("last_password_change"),
        failed_login_attempts=user.get("failed_login_attempts", 0),
        account_locked_until=user.get("account_locked_until"),
        created_at=user["created_at"],
        created_by=str(user["created_by"]) if user.get("created_by") else None,
        updated_at=user.get("updated_at"),
        updated_by=str(user["updated_by"]) if user.get("updated_by") else None,
    )


@router.delete("/admin-users/{user_id}", response_model=SuccessResponse)
async def delete_admin_user(
    user_id: str,
    current_admin: dict = Depends(require_system_admin),
):
    """
    Delete an admin user (soft delete by deactivating).
    Only accessible by System Administrators.
    """
    # Prevent self-deletion
    if user_id == current_admin["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account"
        )
    
    # Check if user exists
    existing = db.client.table("admin_users").select("id").eq("id", user_id).execute()
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found"
        )
    
    # Soft delete by deactivating
    update_data = {
        "is_active": False,
        "updated_by": current_admin["id"],
        "updated_at": get_cat_now().isoformat()
    }
    
    db.client.table("admin_users").update(update_data).eq("id", user_id).execute()
    
    return SuccessResponse(
        success=True,
        message="Admin user deactivated successfully"
    )


@router.post("/admin-users/{user_id}/reset-password", response_model=SuccessResponse)
async def reset_admin_password(
    user_id: str,
    request: AdminPasswordResetRequest,
    http_request: Request = None,
    current_admin: dict = Depends(require_system_admin),
):
    """
    Reset an admin user's password.
    Only accessible by System Administrators.
    """
    # Prevent self password reset (use change password instead)
    if user_id == current_admin["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use the change password endpoint to update your own password"
        )
    
    # Check if user exists
    existing = db.client.table("admin_users").select("email", "full_name").eq("id", user_id).execute()
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found"
        )
    
    user = existing.data[0]
    
    # Hash new password
    password_hash = hash_password(request.new_password)
    
    # Update password
    update_data = {
        "password_hash": password_hash,
        "must_change_password": request.must_change_password,
        "failed_login_attempts": 0,
        "account_locked_until": None,
        "last_password_change": get_cat_now().isoformat(),
        "updated_by": current_admin["id"],
        "updated_at": get_cat_now().isoformat()
    }
    
    db.client.table("admin_users").update(update_data).eq("id", user_id).execute()
    
    # Log password reset
    await audit_service.log_user_management(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=AuditAction.PASSWORD_RESET,
        target_user_id=user_id,
        target_user_email=user["email"],
        details={
            "full_name": user["full_name"],
            "must_change_password": request.must_change_password,
            "reset_by_admin": True
        },
        ip_address=get_client_ip(http_request) if http_request else None
    )
    
    # Send password reset notification
    try:
        await email_service.send_email(
            to_email=user["email"],
            template=EmailTemplate.PASSWORD_RESET,
            context={
                "full_name": user["full_name"],
                "new_password": request.new_password,
                "must_change_password": request.must_change_password,
            }
        )
    except Exception as e:
        print(f"Failed to send password reset email: {str(e)}")
    
    return SuccessResponse(
        success=True,
        message="Password reset successfully"
    )


@router.post("/admin-users/{user_id}/unlock", response_model=SuccessResponse)
async def unlock_admin_account(
    user_id: str,
    request: UnlockAccountRequest,
    http_request: Request = None,
    current_admin: dict = Depends(require_system_admin),
):
    """
    Unlock a locked admin account.
    Only accessible by System Administrators.
    """
    # Check if user exists
    existing = db.client.table("admin_users").select("email", "full_name").eq("id", user_id).execute()
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found"
        )
    
    user = existing.data[0]
    
    # Unlock account
    update_data = {
        "account_locked_until": None,
        "updated_by": current_admin["id"],
        "updated_at": get_cat_now().isoformat()
    }
    
    if request.reset_failed_attempts:
        update_data["failed_login_attempts"] = 0
    
    db.client.table("admin_users").update(update_data).eq("id", user_id).execute()
    
    # Log account unlock
    await audit_service.log_user_management(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=AuditAction.ACCOUNT_UNLOCKED,
        target_user_id=user_id,
        target_user_email=user["email"],
        details={
            "full_name": user["full_name"],
            "reset_failed_attempts": request.reset_failed_attempts
        },
        ip_address=get_client_ip(http_request) if http_request else None
    )
    
    return SuccessResponse(
        success=True,
        message="Account unlocked successfully"
    )


# ============== Vendor User Management ==============

@router.get("/vendors", response_model=VendorUserListResponse)
async def list_vendor_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin),
):
    """
    List all vendor users with pagination and filtering.
    Accessible by all authenticated admins.
    """
    offset = (page - 1) * page_size
    
    # Build query
    query = db.client.table("suppliers").select(
        "id, company_name, contact_person_name, email, phone, business_category, "
        "status, activity_status, created_at, last_login, submitted_at, reviewed_at",
        count="exact"
    )
    
    # Apply filters
    if status:
        query = query.eq("status", status)
    if category:
        query = query.eq("business_category", category)
    if is_active is not None:
        query = query.eq("is_active", is_active)
    if search:
        query = query.or_(
            f"company_name.ilike.%{search}%,"
            f"contact_person_name.ilike.%{search}%,"
            f"email.ilike.%{search}%"
        )
    
    # Apply pagination
    query = query.range(offset, offset + page_size - 1).order("created_at", desc=True)
    
    response = query.execute()
    
    if not response.data:
        return VendorUserListResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0
        )
    
    total = len(response.data) if not hasattr(response, 'count') else response.count
    total_pages = (total + page_size - 1) // page_size
    
    # Get document counts for each vendor
    vendor_ids = [v["id"] for v in response.data]
    doc_counts = {}
    
    if vendor_ids:
        docs_response = db.client.table("documents").select(
            "supplier_id, verification_status"
        ).in_("supplier_id", vendor_ids).execute()
        
        for doc in docs_response.data:
            sid = doc["supplier_id"]
            if sid not in doc_counts:
                doc_counts[sid] = {"total": 0, "verified": 0}
            doc_counts[sid]["total"] += 1
            if doc["verification_status"] == "VERIFIED":
                doc_counts[sid]["verified"] += 1
    
    items = [
        VendorUserResponse(
            id=str(vendor["id"]),
            company_name=vendor["company_name"],
            contact_person=vendor["contact_person_name"],
            email=vendor["email"],
            phone=vendor["phone"],
            business_category=vendor["business_category"],
            status=vendor["status"],
            is_active=vendor.get("activity_status") == "ACTIVE",
            created_at=vendor["created_at"],
            last_login=vendor.get("last_login"),
            submitted_at=vendor.get("submitted_at"),
            reviewed_at=vendor.get("reviewed_at"),
            total_documents=doc_counts.get(vendor["id"], {}).get("total", 0),
            verified_documents=doc_counts.get(vendor["id"], {}).get("verified", 0),
            documents_complete=(
                doc_counts.get(vendor["id"], {}).get("total", 0) > 0 and
                doc_counts.get(vendor["id"], {}).get("total", 0) == doc_counts.get(vendor["id"], {}).get("verified", 0)
            ),
        )
        for vendor in response.data
    ]
    
    return VendorUserListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.put("/vendors/{vendor_id}", response_model=VendorUserResponse)
async def update_vendor_user(
    vendor_id: str,
    request: VendorUserUpdateRequest,
    http_request: Request = None,
    current_admin: dict = Depends(require_system_admin),
):
    """
    Update vendor user information.
    Only accessible by System Administrators.
    """
    # Check if vendor exists
    existing = db.client.table("suppliers").select("*").eq("id", vendor_id).execute()
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )
    
    old_vendor = existing.data[0]
    
    # Build update data and track changes
    update_data = {"updated_at": get_cat_now().isoformat()}
    updated_fields = []
    
    if request.company_name is not None:
        update_data["company_name"] = request.company_name
        updated_fields.append("company_name")
    if request.contact_person is not None:
        update_data["contact_person_name"] = request.contact_person
        updated_fields.append("contact_person")
    if request.email is not None:
        # Check if email is already in use
        email_check = db.client.table("suppliers").select("id").eq("email", request.email).neq("id", vendor_id).execute()
        if email_check.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use by another vendor"
            )
        update_data["email"] = request.email
        updated_fields.append("email")
    if request.phone is not None:
        update_data["phone"] = request.phone
        updated_fields.append("phone")
    if request.is_active is not None:
        update_data["activity_status"] = "ACTIVE" if request.is_active else "INACTIVE"
        updated_fields.append("is_active")
    
    response = db.client.table("suppliers").update(update_data).eq("id", vendor_id).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update vendor"
        )
    
    vendor = response.data[0]
    
    # Log vendor update
    await audit_service.log_vendor_action(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=AuditAction.VENDOR_UPDATED,
        vendor_id=vendor_id,
        vendor_name=vendor["company_name"],
        details={
            "updated_fields": updated_fields,
            "old_company_name": old_vendor.get("company_name"),
            "new_company_name": vendor.get("company_name")
        },
        ip_address=get_client_ip(http_request) if http_request else None
    )
    
    vendor = response.data[0]
    
    # Get document count
    docs = db.client.table("documents").select("verification_status").eq("supplier_id", vendor_id).execute()
    total_docs = len(docs.data)
    verified_docs = sum(1 for d in docs.data if d["verification_status"] == "VERIFIED")
    
    return VendorUserResponse(
        id=str(vendor["id"]),
        company_name=vendor["company_name"],
        contact_person=vendor["contact_person_name"],
        email=vendor["email"],
        phone=vendor["phone"],
        business_category=vendor["business_category"],
        status=vendor["status"],
        is_active=vendor.get("activity_status") == "ACTIVE",
        created_at=vendor["created_at"],
        last_login=vendor.get("last_login"),
        submitted_at=vendor.get("submitted_at"),
        reviewed_at=vendor.get("reviewed_at"),
        total_documents=total_docs,
        verified_documents=verified_docs,
        documents_complete=(total_docs > 0 and total_docs == verified_docs),
    )


@router.post("/vendors/{vendor_id}/reset-password", response_model=SuccessResponse)
async def reset_vendor_password(
    vendor_id: str,
    request: VendorPasswordResetRequest,
    http_request: Request = None,
    current_admin: dict = Depends(require_system_admin),
):
    """
    Reset a vendor's password.
    Only accessible by System Administrators.
    """
    # Check if vendor exists
    existing = db.client.table("suppliers").select("email", "company_name", "contact_person").eq("id", vendor_id).execute()
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )
    
    vendor = existing.data[0]
    
    # Hash new password
    password_hash = hash_password(request.new_password)
    
    # Update password
    update_data = {
        "password_hash": password_hash,
        "failed_login_attempts": 0,
        "account_locked_until": None,
        "last_password_change": get_cat_now().isoformat(),
        "updated_at": get_cat_now().isoformat()
    }
    
    db.client.table("suppliers").update(update_data).eq("id", vendor_id).execute()
    
    # Log password reset
    await audit_service.log_vendor_action(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=AuditAction.PASSWORD_RESET,
        vendor_id=vendor_id,
        vendor_name=vendor["company_name"],
        details={
            "reset_by_admin": True,
            "notify_vendor": request.notify_vendor
        },
        ip_address=get_client_ip(http_request) if http_request else None
    )
    
    # Send notification if requested
    if request.notify_vendor:
        try:
            await email_service.send_email(
                to_email=vendor["email"],
                template=EmailTemplate.VENDOR_PASSWORD_RESET,
                context={
                    "company_name": vendor["company_name"],
                    "contact_person": vendor["contact_person"],
                    "new_password": request.new_password,
                    "support_email": "support@rainbowtourism.co.zw",
                }
            )
        except Exception as e:
            print(f"Failed to send password reset email to vendor: {str(e)}")
    
    return SuccessResponse(
        success=True,
        message="Vendor password reset successfully"
    )


@router.post("/vendors/{vendor_id}/toggle-active", response_model=SuccessResponse)
async def toggle_vendor_active_status(
    vendor_id: str,
    http_request: Request = None,
    current_admin: dict = Depends(require_system_admin),
):
    """
    Toggle vendor active/inactive status.
    Only accessible by System Administrators.
    """
    # Check if vendor exists
    existing = db.client.table("suppliers").select("activity_status", "company_name", "email").eq("id", vendor_id).execute()
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )
    
    vendor = existing.data[0]
    current_status = vendor.get("activity_status", "ACTIVE")
    new_status = "INACTIVE" if current_status == "ACTIVE" else "ACTIVE"
    
    # Update status
    db.client.table("suppliers").update({
        "activity_status": new_status,
        "updated_at": get_cat_now().isoformat()
    }).eq("id", vendor_id).execute()
    
    # Log activation/deactivation
    action = AuditAction.VENDOR_ACTIVATED if new_status == "ACTIVE" else AuditAction.VENDOR_DEACTIVATED
    await audit_service.log_vendor_action(
        admin_id=current_admin["id"],
        admin_email=current_admin["email"],
        action=action,
        vendor_id=vendor_id,
        vendor_name=vendor["company_name"],
        details={
            "old_status": current_status,
            "new_status": new_status
        },
        ip_address=get_client_ip(http_request) if http_request else None
    )
    
    return SuccessResponse(
        success=True,
        message=f"Vendor {'activated' if new_status == 'ACTIVE' else 'deactivated'} successfully"
    )
