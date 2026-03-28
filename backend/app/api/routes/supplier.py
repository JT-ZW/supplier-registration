"""
Supplier registration API routes.
These endpoints are for guest users (suppliers) to register and submit applications.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4
import secrets
import string
import asyncio
from fastapi import APIRouter, HTTPException, status, Query, Request, Depends

from ...db.supabase import db
from ...services.audit import AuditService
from ...models.audit import AuditAction, AuditResourceType
from ...api.deps import get_client_ip, get_current_user
from ...models import (
    SupplierCreateRequest,
    SupplierUpdateRequest,
    SupplierSubmitRequest,
    SupplierResponse,
    SupplierDocumentStatusResponse,
    DocumentUploadStatusResponse,
    RequiredDocumentsResponse,
    SuccessResponse,
    BusinessCategory,
    SupplierStatus,
    DocumentType,
    DocumentVerificationStatus,
    MANDATORY_DOCUMENTS,
    CATEGORY_DOCUMENTS,
    get_required_documents,
    SupplierType,
    get_supplier_type,
    get_statutory_documents,
    compute_business_size,
    compute_esg_flags,
    CERT_GROUPS_BY_CATEGORY,
    LEGACY_CATEGORIES,
)
from ...models.compliance import (
    KeyPersonRequest,
    KeyPersonResponse,
    KeyPersonListResponse,
    FarmerApplicationFormRequest,
    FarmerApplicationFormResponse,
    SupplierCategoryRequest,
    SupplierCategoryResponse,
    SupplierCategoryListResponse,
    CategoryRequirementsResponse,
)
from ...core.email import email_service, EmailTemplate
from ...core.security import hash_password
from ...core.config import settings
from ...core.cache_invalidation import invalidate_analytics_cache


router = APIRouter(prefix="/supplier", tags=["Supplier"])

# Initialize audit service
audit_service = AuditService()


@router.post(
    "/register",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new supplier registration",
    description="Creates a new supplier application with login credentials."
)
async def create_supplier(request: SupplierCreateRequest):
    """
    Create a new supplier registration application with credentials.
    
    The supplier provides login credentials and company details in a single flow.
    The application starts in INCOMPLETE status and remains so until all required
    documents are uploaded and the application is submitted.
    """
    # Check for duplicate email
    existing = await db.get_supplier_by_email(request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A supplier with this email address already exists"
        )

    # Derive supplier type and ESG flags from the request data
    supplier_type = get_supplier_type(request.country, request.is_small_scale_farmer)
    if request.is_small_scale_farmer and len(request.key_persons) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Small-scale farmer registration requires exactly one key person",
        )
    business_size = compute_business_size(request.employee_count)
    key_persons_raw = [kp.model_dump() for kp in request.key_persons]
    esg_flags = compute_esg_flags(key_persons_raw)

    # Farmer registration rules:
    # - Category is always Fresh Farm Produce
    # - registration_number / tax_id are not applicable but DB columns are non-null
    if request.is_small_scale_farmer:
        effective_primary_category = BusinessCategory.FRESH_FARM_PRODUCE
        effective_business_categories = [BusinessCategory.FRESH_FARM_PRODUCE]
        registration_number = (request.registration_number or "N/A").strip() or "N/A"
        tax_id = (request.tax_id or "N/A").strip() or "N/A"
    else:
        if not request.registration_number or not request.registration_number.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Business registration number is required for non-farmer suppliers",
            )
        if not request.tax_id or not request.tax_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tax ID / ZIMRA number is required for non-farmer suppliers",
            )
        effective_primary_category = request.business_category
        effective_business_categories = request.business_categories
        registration_number = request.registration_number.strip()
        tax_id = request.tax_id.strip()

    # Prepare supplier data with password
    supplier_data = {
        "id": str(uuid4()),
        "company_name": request.company_name,
        "business_category": effective_primary_category.value,
        "registration_number": registration_number,
        "tax_id": tax_id,
        "years_in_business": request.years_in_business,
        "website": request.website,
        "employee_count": request.employee_count,
        "is_small_scale_farmer": request.is_small_scale_farmer,
        "business_size": business_size.value if business_size else None,
        "esg_women_owned": esg_flags["esg_women_owned"],
        "esg_youth_owned": esg_flags["esg_youth_owned"],
        "contact_person_name": request.contact_person_name,
        "contact_person_title": request.contact_person_title,
        "email": request.email,
        "phone": request.phone,
        "street_address": request.street_address,
        "city": request.city,
        "state_province": request.state_province,
        "postal_code": request.postal_code,
        "country": request.country,
        "password_hash": hash_password(request.password),
        "status": SupplierStatus.INCOMPLETE.value,
        "created_at": datetime.utcnow().isoformat(),
    }

    # Create supplier in database
    supplier = await db.create_supplier(supplier_data)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create supplier application"
        )

    supplier_id = supplier["id"]

    # Persist key persons
    if request.is_small_scale_farmer:
        farmer_person = request.key_persons[0]
        kp_data = {
            "supplier_id": supplier_id,
            "full_name": request.contact_person_name,
            "gender": farmer_person.gender.value,
            "date_of_birth": farmer_person.date_of_birth.isoformat() if farmer_person.date_of_birth else None,
            "role": "CONTACT",
        }
        await db.create_key_person(kp_data)
    else:
        for kp in request.key_persons:
            kp_data = {
                "supplier_id": supplier_id,
                "full_name": kp.full_name,
                "gender": kp.gender.value,
                "date_of_birth": kp.date_of_birth.isoformat() if kp.date_of_birth else None,
                "role": kp.role.value,
            }
            await db.create_key_person(kp_data)

    # Persist trade references
    for ref in request.trade_references:
        ref_data = {
            "supplier_id": supplier_id,
            "company_name": ref.company_name,
            "contact_person_name": ref.contact_person_name,
            "email": str(ref.email),
            "phone": ref.phone,
            "relationship": ref.relationship,
            "service_product": ref.service_product,
            "contract_start_date": ref.contract_start_date.isoformat() if ref.contract_start_date else None,
            "contract_end_date": ref.contract_end_date.isoformat() if ref.contract_end_date else None,
            "annual_spend": ref.annual_spend,
            "permission_granted": ref.permission_granted,
        }
        await db.create_trade_reference(ref_data)

    # Persist categories
    for cat in effective_business_categories:
        cat_data = {
            "supplier_id": supplier_id,
            "category": cat.value,
            "compliance_status": "PENDING",
        }
        await db.create_supplier_category(cat_data)
    
    # Log supplier creation
    await audit_service.log_action(
        action=AuditAction.SUPPLIER_CREATED,
        resource_type=AuditResourceType.SUPPLIER,
        user_id=supplier["id"],
        user_type="vendor",
        resource_id=supplier["id"],
        resource_name=supplier["company_name"],
        metadata={
            "category": supplier["business_category"],
            "location": f"{supplier['city']}, {supplier['country']}"
        }
    )

    await invalidate_analytics_cache(scope="summary")
    
    # Send admin notification for new registration
    try:
        from app.core.email import email_service, EmailTemplate
        from app.core.config import settings
        
        await email_service.send_template_email(
            to_email=settings.ADMIN_EMAIL,
            template=EmailTemplate.ADMIN_NEW_APPLICATION,
            data={
                "supplier_name": supplier["company_name"],
                "category": supplier.get("business_category", "N/A"),
                "location": f"{supplier.get('city', 'N/A')}, {supplier.get('country', 'N/A')}",
                "contact_person": supplier.get("contact_person_name", "N/A"),
                "supplier_id": supplier["id"],
                "review_link": f"{settings.FRONTEND_URL}/admin/suppliers/{supplier['id']}"
            },
            to_name="Admin Team"
        )
    except Exception as e:
        print(f"Failed to send admin notification: {str(e)}")
    
    return supplier


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
    summary="Get supplier application",
    description="Retrieve supplier application details by ID."
)
async def get_supplier(
    supplier_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get supplier application by ID."""
    if current_user["type"] == "vendor" and current_user["data"]["id"] != supplier_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own application"
        )
        
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    return supplier


@router.put(
    "/{supplier_id}",
    response_model=SupplierResponse,
    summary="Update supplier application",
    description="Update supplier application details. Only allowed for INCOMPLETE or NEED_MORE_INFO status."
)
async def update_supplier(supplier_id: str, request: SupplierUpdateRequest):
    """
    Update supplier application details.
    
    Updates are only allowed when the application is in INCOMPLETE or NEED_MORE_INFO status.
    """
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    # Check if updates are allowed
    allowed_statuses = [SupplierStatus.INCOMPLETE.value, SupplierStatus.NEED_MORE_INFO.value]
    if supplier["status"] not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot update application with status '{supplier['status']}'"
        )
    
    # If email is being changed, check for duplicates
    if request.email and request.email != supplier["email"]:
        existing = await db.get_supplier_by_email(request.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A supplier with this email address already exists"
            )
    
    # Prepare update data
    update_data = {}
    if request.company_name is not None:
        update_data["company_name"] = request.company_name
    if request.business_category is not None:
        update_data["business_category"] = request.business_category.value
    if request.registration_number is not None:
        update_data["registration_number"] = request.registration_number
    if request.tax_id is not None:
        update_data["tax_id"] = request.tax_id
    if request.years_in_business is not None:
        update_data["years_in_business"] = request.years_in_business
    if request.website is not None:
        update_data["website"] = request.website
    if request.employee_count is not None:
        update_data["employee_count"] = request.employee_count
        new_size = compute_business_size(request.employee_count)
        update_data["business_size"] = new_size.value if new_size else None
    if request.is_small_scale_farmer is not None:
        update_data["is_small_scale_farmer"] = request.is_small_scale_farmer
    if request.contact_person_name is not None:
        update_data["contact_person_name"] = request.contact_person_name
    if request.contact_person_title is not None:
        update_data["contact_person_title"] = request.contact_person_title
    if request.email is not None:
        update_data["email"] = request.email
    if request.phone is not None:
        update_data["phone"] = request.phone
    if request.street_address is not None:
        update_data["street_address"] = request.street_address
    if request.city is not None:
        update_data["city"] = request.city
    if request.state_province is not None:
        update_data["state_province"] = request.state_province
    if request.postal_code is not None:
        update_data["postal_code"] = request.postal_code
    if request.country is not None:
        update_data["country"] = request.country
    
    if not update_data:
        return supplier
    
    update_data["updated_at"] = datetime.utcnow().isoformat()
    
    updated_supplier = await db.update_supplier(supplier_id, update_data)
    if not updated_supplier:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update supplier application"
        )
    
    # Log supplier update with changes
    changes = {field: {"old": supplier.get(field), "new": value} 
               for field, value in update_data.items() 
               if field != "updated_at"}
    
    await audit_service.log_action(
        action=AuditAction.SUPPLIER_UPDATED,
        resource_type=AuditResourceType.SUPPLIER,
        user_id=supplier_id,
        user_type="vendor",
        resource_id=supplier_id,
        resource_name=updated_supplier.get("company_name") or supplier.get("company_name"),
        changes=changes
    )

    await invalidate_analytics_cache()
    
    return updated_supplier


@router.post(
    "/{supplier_id}/submit",
    response_model=SuccessResponse,
    summary="Submit supplier application",
    description="Submit the supplier application for review. All required documents must be uploaded."
)
async def submit_supplier_application(supplier_id: str, request: SupplierSubmitRequest):
    """
    Submit the supplier application for admin review.
    
    This endpoint validates that all required documents have been uploaded
    before allowing submission.
    """
    if request.supplier_id != supplier_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supplier ID mismatch"
        )
    
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    # Check if submission is allowed
    allowed_statuses = [SupplierStatus.INCOMPLETE.value, SupplierStatus.NEED_MORE_INFO.value]
    if supplier["status"] not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit application with status '{supplier['status']}'"
        )
    
    # Fetch all categories for this supplier (multi-category support)
    supplier_category_rows = await db.get_supplier_categories(supplier_id)
    if supplier_category_rows:
        all_categories = [BusinessCategory(row["category"]) for row in supplier_category_rows]
    else:
        # Fall back to the primary category
        all_categories = [BusinessCategory(supplier["business_category"])]

    # Get uploaded document types
    documents = await db.get_documents_by_supplier(supplier_id)
    uploaded_types = {doc["document_type"] for doc in documents}

    # 1. Check statutory mandatory documents
    supplier_type = get_supplier_type(
        supplier.get("country", ""),
        supplier.get("is_small_scale_farmer", False),
    )
    statutory_docs = get_statutory_documents(supplier_type)
    missing_statutory = [
        dt.value for dt in statutory_docs if dt.value not in uploaded_types
    ]

    # 2. Check mandatory cert groups — require at least ONE doc per mandatory group
    missing_groups: list[str] = []
    for cat in all_categories:
        for grp in CERT_GROUPS_BY_CATEGORY.get(cat, []):
            if not grp.is_mandatory_upload:
                continue
            if not any(dt.value in uploaded_types for dt in grp.document_types):
                missing_groups.append(grp.name)

    missing_docs = missing_statutory + missing_groups
    if missing_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Missing required documents",
                "missing_documents": missing_docs,
            },
        )
    
    # Update status to SUBMITTED
    update_data = {
        "status": SupplierStatus.SUBMITTED.value,
        "submitted_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    
    # Generate initial password for vendor portal access
    # Only if not already set
    if not supplier.get("password_hash"):
        # Generate secure random password (12 characters)
        alphabet = string.ascii_letters + string.digits
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))
        update_data["password_hash"] = hash_password(temp_password)
        
        # Store temp password to send in email
        vendor_password = temp_password
    else:
        vendor_password = None
    
    await db.update_supplier(supplier_id, update_data)

    # Compute initial per-category compliance levels from verified uploads.
    try:
        await db.recompute_supplier_category_compliance(supplier_id)
    except Exception as compliance_err:
        print(f"⚠️  compliance recompute skipped for {supplier_id}: {compliance_err}")
    
    # Send email notifications
    try:
        portal_login_url = f"{settings.FRONTEND_URL}/vendor/login"
        
        # Notify supplier with portal access credentials
        if vendor_password:
            # Send email with portal credentials
            await email_service.send_email(
                to_email=supplier["email"],
                subject="Application Submitted - Vendor Portal Access",
                html_content=f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2>Application Submitted Successfully!</h2>
                    <p>Hello {supplier['contact_person_name']},</p>
                    <p>Thank you for submitting your supplier application to Rainbow Tourism Group.</p>
                    
                    <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">Your Vendor Portal Access</h3>
                        <p>You can now track your application status and manage your profile through our vendor portal:</p>
                        <p><strong>Portal URL:</strong> <a href="{portal_login_url}">{portal_login_url}</a></p>
                        <p><strong>Email:</strong> {supplier['email']}</p>
                        <p><strong>Temporary Password:</strong> <code style="background-color: #e5e7eb; padding: 4px 8px; border-radius: 4px;">{vendor_password}</code></p>
                        <p style="color: #dc2626; font-size: 14px; margin-top: 12px;">
                            ⚠️ Please change your password after first login for security.
                        </p>
                    </div>
                    
                    <h3>What's Next?</h3>
                    <ul>
                        <li>Our team will review your application within 3-5 business days</li>
                        <li>You'll receive email updates on your application status</li>
                        <li>Track progress in real-time through the vendor portal</li>
                        <li>We may reach out if additional information is needed</li>
                    </ul>
                    
                    <p>Thank you for your interest in partnering with RTG!</p>
                    
                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e5e5;">
                    <p style="color: #666; font-size: 12px;">
                        Rainbow Tourism Group<br>
                        Supplier Portal<br>
                        Email: procurement@rtg.com<br>
                        Phone: +263 123 456 789
                    </p>
                </div>
                """
            )
        else:
            # Send standard submission confirmation
            await email_service.send_template_email(
                to_email=supplier["email"],
                template=EmailTemplate.SUPPLIER_REGISTRATION_SUBMITTED,
                data={
                    "supplier_name": supplier["company_name"],
                    "contact_person": supplier["contact_person_name"],
                    "supplier_id": supplier_id,
                    "portal_url": portal_login_url,
                },
                to_name=supplier["contact_person_name"]
            )
        
        # Send consolidated admin notification with all application details
        documents_list = "\n".join([
            f"<li><strong>{doc['document_type'].replace('_', ' ').title()}:</strong> {doc['file_name']} (uploaded {doc['uploaded_at']})</li>"
            for doc in documents
        ])
        
        await email_service.send_email(
            to_email=settings.ADMIN_EMAIL,
            subject=f"New Application Submitted - {supplier['company_name']}",
            html_content=f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2>New Supplier Application Submitted</h2>
                <p>A supplier has completed and submitted their application for review.</p>
                
                <div style="background-color: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #1f2937;">Company Information</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; font-weight: 600; color: #4b5563;">Company Name:</td>
                            <td style="padding: 8px 0; color: #1f2937;">{supplier['company_name']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: 600; color: #4b5563;">Registration #:</td>
                            <td style="padding: 8px 0; color: #1f2937;">{supplier.get('registration_number', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: 600; color: #4b5563;">Business Category:</td>
                            <td style="padding: 8px 0; color: #1f2937;">{supplier['business_category'].replace('_', ' ').title()}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: 600; color: #4b5563;">Contact Person:</td>
                            <td style="padding: 8px 0; color: #1f2937;">{supplier['contact_person_name']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: 600; color: #4b5563;">Email:</td>
                            <td style="padding: 8px 0; color: #1f2937;">{supplier['email']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: 600; color: #4b5563;">Phone:</td>
                            <td style="padding: 8px 0; color: #1f2937;">{supplier['phone']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: 600; color: #4b5563;">Location:</td>
                            <td style="padding: 8px 0; color: #1f2937;">{supplier.get('city', 'N/A')}, {supplier.get('country', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: 600; color: #4b5563;">Submitted At:</td>
                            <td style="padding: 8px 0; color: #1f2937;">{update_data['submitted_at']}</td>
                        </tr>
                    </table>
                </div>
                
                <div style="background-color: #eff6ff; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #3b82f6;">
                    <h3 style="margin-top: 0; color: #1e40af;">Uploaded Documents ({len(documents)})</h3>
                    <ul style="margin: 0; padding-left: 20px; color: #1e3a8a;">
                        {documents_list}
                    </ul>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{settings.FRONTEND_URL}/admin/suppliers/{supplier_id}" 
                       style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 32px; 
                              text-decoration: none; border-radius: 6px; font-weight: 600;">
                        Review Application Now
                    </a>
                </div>
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 12px; text-align: center;">
                    Application ID: {supplier_id}<br>
                    Rainbow Tourism Group Procurement System
                </p>
            </div>
            """,
            to_name="Admin Team"
        )
        
    except Exception as e:
        # Log but don't fail the submission
        print(f"Failed to send email notification: {e}")
    
    # Send in-app notification to admins
    from ...services.notifications import NotificationService
    notification_service = NotificationService(db)
    
    try:
        # Get all active admins
        admins = await db.get_all_admins()
        admin_ids = [admin["id"] for admin in admins if admin.get("is_active", True)]
        
        if admin_ids:
            asyncio.create_task(
                notification_service.notify_admins_application_submitted(
                    admin_ids=admin_ids,
                    supplier_id=supplier_id,
                    supplier_name=supplier["company_name"],
                    category=supplier["business_category"],
                    metadata={
                        "contact_person": supplier["contact_person_name"],
                        "email": supplier["email"],
                        "phone": supplier["phone"],
                        "registration_number": supplier.get("registration_number"),
                        "submitted_at": update_data["submitted_at"],
                        "documents_count": len(documents)
                    }
                )
            )
    except Exception as e:
        print(f"Failed to send in-app notifications: {e}")
    
    # Log supplier submission
    await audit_service.log_action(
        action=AuditAction.SUPPLIER_SUBMITTED,
        resource_type=AuditResourceType.SUPPLIER,
        user_id=supplier_id,
        user_type="vendor",
        resource_id=supplier_id,
        resource_name=supplier["company_name"],
        metadata={
            "documents_count": len(documents),
            "submitted_at": update_data["submitted_at"]
        }
    )

    await invalidate_analytics_cache()
    
    return SuccessResponse(
        success=True,
        message="Application submitted successfully. Check your email for vendor portal access credentials."
    )


@router.get(
    "/{supplier_id}/documents/status",
    response_model=SupplierDocumentStatusResponse,
    summary="Get document upload status",
    description="Get the upload status for all required documents."
)
async def get_document_upload_status(supplier_id: str, current_user: dict = Depends(get_current_user)):

    if current_user["type"] == "vendor" and current_user["data"]["id"] != supplier_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own application")

    """
    Get the document upload status for a supplier application.
    
    Shows which documents are required, which have been uploaded,
    and their verification status.
    """
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    category = BusinessCategory(supplier["business_category"])
    required_docs = get_required_documents(category)
    
    # Get uploaded documents
    documents = await db.get_documents_by_supplier(supplier_id)
    docs_by_type = {doc["document_type"]: doc for doc in documents}
    
    # Build status for each required document
    doc_statuses = []
    for doc_type in required_docs:
        is_mandatory = doc_type in MANDATORY_DOCUMENTS
        uploaded_doc = docs_by_type.get(doc_type.value)
        
        doc_status = DocumentUploadStatusResponse(
            document_type=doc_type,
            document_type_display=doc_type.value.replace("_", " ").title(),
            is_mandatory=is_mandatory,
            is_uploaded=uploaded_doc is not None,
            verification_status=DocumentVerificationStatus(uploaded_doc["verification_status"]) if uploaded_doc else None,
            rejection_reason=uploaded_doc.get("rejection_reason") if uploaded_doc else None,
            uploaded_at=uploaded_doc.get("uploaded_at") if uploaded_doc else None,
        )
        doc_statuses.append(doc_status)
    
    # Calculate totals
    total_required = len(required_docs)
    total_uploaded = sum(1 for s in doc_statuses if s.is_uploaded)
    total_verified = sum(1 for s in doc_statuses if s.verification_status == DocumentVerificationStatus.VERIFIED)
    
    return SupplierDocumentStatusResponse(
        supplier_id=supplier_id,
        category=supplier["business_category"],
        documents=doc_statuses,
        total_required=total_required,
        total_uploaded=total_uploaded,
        total_verified=total_verified,
        is_complete=total_uploaded == total_required,
    )


@router.get(
    "/categories/documents",
    response_model=RequiredDocumentsResponse,
    summary="Get required documents for a category",
    description="Get the list of required documents for a specific business category."
)
async def get_required_documents_for_category(
    category: BusinessCategory = Query(..., description="Business category")
):
    """Get the list of required documents for a business category."""
    required_docs = get_required_documents(category)
    category_specific = CATEGORY_DOCUMENTS.get(category, [])
    
    return RequiredDocumentsResponse(
        category=category,
        mandatory_documents=[doc.value for doc in MANDATORY_DOCUMENTS],
        category_specific_documents=[doc.value for doc in category_specific],
        all_required_documents=[doc.value for doc in required_docs],
    )


@router.get(
    "/check-email/{email}",
    response_model=dict,
    summary="Check if email exists",
    description="Check if a supplier with the given email already exists."
)
async def check_email_exists(email: str):
    """Check if a supplier with the given email already exists."""
    existing = await db.get_supplier_by_email(email)
    return {
        "exists": existing is not None,
        "message": "Email already registered" if existing else "Email available"
    }


# ============== Category Requirements ==============

@router.get(
    "/category/{category}/requirements",
    response_model=CategoryRequirementsResponse,
    summary="Get cert groups for a business category",
    description="Returns all certification groups with their required documents for a given category."
)
async def get_category_requirements(category: BusinessCategory):
    """Return cert groups (pick-at-least-one sets) for the given category."""
    return CategoryRequirementsResponse.for_category(category)


# ============== Key Persons ==============

@router.get(
    "/{supplier_id}/key-persons",
    response_model=KeyPersonListResponse,
    summary="List key persons for a supplier",
)
async def list_key_persons(supplier_id: str, current_user: dict = Depends(get_current_user)):

    if current_user["type"] == "vendor" and current_user["data"]["id"] != supplier_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own application")

    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    persons = await db.get_key_persons_by_supplier(supplier_id)
    return KeyPersonListResponse(key_persons=[KeyPersonResponse(**p) for p in persons])


@router.post(
    "/{supplier_id}/key-persons",
    response_model=KeyPersonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a key person to a supplier",
)
async def add_key_person(supplier_id: str, request: KeyPersonRequest, current_user: dict = Depends(get_current_user)):

    if current_user["type"] == "vendor" and current_user["data"]["id"] != supplier_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own application")

    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    existing = await db.get_key_persons_by_supplier(supplier_id)
    if len(existing) >= 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 3 key persons allowed")

    kp_data = {
        "supplier_id": supplier_id,
        "full_name": request.full_name,
        "gender": request.gender.value,
        "date_of_birth": request.date_of_birth.isoformat() if request.date_of_birth else None,
        "role": request.role.value,
    }
    created = await db.create_key_person(kp_data)
    if not created:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add key person")

    # Recompute ESG flags
    all_persons = await db.get_key_persons_by_supplier(supplier_id)
    esg_flags = compute_esg_flags(all_persons)
    await db.update_supplier(supplier_id, {**esg_flags, "updated_at": datetime.utcnow().isoformat()})

    await invalidate_analytics_cache(scope="summary")

    return KeyPersonResponse(**created)


@router.delete(
    "/{supplier_id}/key-persons/{key_person_id}",
    response_model=SuccessResponse,
    summary="Remove a key person from a supplier",
)
async def remove_key_person(supplier_id: str, key_person_id: str, current_user: dict = Depends(get_current_user)):

    if current_user["type"] == "vendor" and current_user["data"]["id"] != supplier_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own application")

    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    await db.delete_key_person(key_person_id)

    # Recompute ESG flags
    all_persons = await db.get_key_persons_by_supplier(supplier_id)
    esg_flags = compute_esg_flags(all_persons)
    await db.update_supplier(supplier_id, {**esg_flags, "updated_at": datetime.utcnow().isoformat()})

    await invalidate_analytics_cache(scope="summary")

    return SuccessResponse(success=True, message="Key person removed")


# ============== Supplier Categories ==============

@router.get(
    "/{supplier_id}/categories",
    response_model=SupplierCategoryListResponse,
    summary="List categories for a supplier",
)
async def list_supplier_categories(supplier_id: str, current_user: dict = Depends(get_current_user)):

    if current_user["type"] == "vendor" and current_user["data"]["id"] != supplier_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own application")

    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    cats = await db.get_supplier_categories(supplier_id)
    return SupplierCategoryListResponse(categories=[SupplierCategoryResponse(**c) for c in cats])


@router.get(
    "/{supplier_id}/category-access",
    summary="Get allowed and blocked business categories for a supplier",
)
async def get_supplier_category_access(
    supplier_id: str,
    category: Optional[BusinessCategory] = Query(
        None,
        description="Optional category to evaluate directly for participation eligibility",
    ),
    current_user: dict = Depends(get_current_user),
):
    """Return category-level participation eligibility for Phase 2B enforcement."""
    if current_user["type"] == "vendor" and current_user["data"]["id"] != supplier_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own application")

    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    access_summary = await db.get_supplier_category_access_summary(supplier_id)
    supplier_status = (supplier.get("status") or "").upper()

    globally_blocked = (
        supplier_status == SupplierStatus.SUSPENDED.value
        or not bool(access_summary.get("mandatory_statutory_met"))
    )
    allowed_categories = list(access_summary.get("allowed_categories") or [])
    blocked_categories = list(access_summary.get("blocked_categories") or [])

    category_value = category.value if category else None
    category_allowed: Optional[bool] = None
    if category_value:
        category_allowed = category_value in allowed_categories and category_value not in blocked_categories

    can_participate = (not globally_blocked) and len(allowed_categories) > 0
    if category_allowed is not None:
        can_participate = can_participate and category_allowed

    return {
        "supplier_id": supplier_id,
        "supplier_status": supplier_status,
        "mandatory_statutory_met": bool(access_summary.get("mandatory_statutory_met")),
        "allowed_categories": allowed_categories,
        "blocked_categories": blocked_categories,
        "excluded_categories": list(access_summary.get("excluded_categories") or []),
        "mandatory_met_categories": int(access_summary.get("mandatory_met_categories", 0) or 0),
        "mandatory_missing_categories": int(access_summary.get("mandatory_missing_categories", 0) or 0),
        "non_excluded_categories": int(access_summary.get("non_excluded_categories", 0) or 0),
        "requested_category": category_value,
        "requested_category_allowed": category_allowed,
        "globally_blocked": globally_blocked,
        "can_participate": can_participate,
    }


@router.post(
    "/{supplier_id}/categories",
    response_model=SupplierCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a category to a supplier",
)
async def add_supplier_category(supplier_id: str, request: SupplierCategoryRequest, current_user: dict = Depends(get_current_user)):

    if current_user["type"] == "vendor" and current_user["data"]["id"] != supplier_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own application")

    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    existing = await db.get_supplier_categories(supplier_id)
    if len(existing) >= 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 6 categories allowed")
    if any(c["category"] == request.category.value for c in existing):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category already assigned")

    cat_data = {
        "supplier_id": supplier_id,
        "category": request.category.value,
        "compliance_status": "PENDING",
    }
    created = await db.create_supplier_category(cat_data)
    if not created:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add category")

    await invalidate_analytics_cache(scope="summary")

    return SupplierCategoryResponse(**created)


@router.delete(
    "/{supplier_id}/categories/{category}",
    response_model=SuccessResponse,
    summary="Remove a category from a supplier",
)
async def remove_supplier_category(supplier_id: str, category: BusinessCategory, current_user: dict = Depends(get_current_user)):

    if current_user["type"] == "vendor" and current_user["data"]["id"] != supplier_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own application")

    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    await db.delete_supplier_category(supplier_id, category.value)

    await invalidate_analytics_cache(scope="summary")

    return SuccessResponse(success=True, message="Category removed")


# ============== Farmer Application Form ==============

@router.get(
    "/{supplier_id}/farmer-form",
    response_model=FarmerApplicationFormResponse,
    summary="Get farmer application form for a supplier",
)
async def get_farmer_form(supplier_id: str, current_user: dict = Depends(get_current_user)):

    if current_user["type"] == "vendor" and current_user["data"]["id"] != supplier_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own application")

    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    form = await db.get_farmer_form(supplier_id)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farmer form not found")
    return FarmerApplicationFormResponse(**form)


@router.post(
    "/{supplier_id}/farmer-form",
    response_model=FarmerApplicationFormResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update farmer application form",
)
async def upsert_farmer_form(supplier_id: str, request: FarmerApplicationFormRequest, current_user: dict = Depends(get_current_user)):

    if current_user["type"] == "vendor" and current_user["data"]["id"] != supplier_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own application")

    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    if not supplier.get("is_small_scale_farmer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Farmer form is only for small-scale farmer suppliers"
        )

    form_data = {
        "supplier_id": supplier_id,
        **request.model_dump(exclude_none=True),
        "updated_at": datetime.utcnow().isoformat(),
    }
    saved = await db.create_farmer_form(form_data)
    if not saved:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save farmer form")
    return FarmerApplicationFormResponse(**saved)




