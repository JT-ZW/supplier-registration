"""
Supplier-related Pydantic models for request/response validation.
"""

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator, ConfigDict
import re

from .enums import (
    SupplierStatus,
    SupplierActivityStatus,
    BusinessCategory,
    SupplierType,
    BusinessSize,
    get_supplier_type,
    compute_business_size,
)
from .compliance import KeyPersonRequest


# ============== Request Models ==============

class TradeReferenceRequest(BaseModel):
    """Trade reference details provided during supplier registration."""
    company_name: str = Field(..., alias="companyName", min_length=2, max_length=200)
    contact_person_name: str = Field(..., alias="contactPersonName", min_length=2, max_length=200)
    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=30)
    relationship: str = Field(..., min_length=2, max_length=100)
    service_product: Optional[str] = Field(None, alias="serviceProduct", max_length=300)
    contract_start_date: Optional[date] = Field(None, alias="contractStartDate")
    contract_end_date: Optional[date] = Field(None, alias="contractEndDate")
    annual_spend: Optional[str] = Field(None, alias="annualSpend", max_length=100)
    permission_granted: bool = Field(..., alias="permissionGranted")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?[0-9]{7,20}$", cleaned):
            raise ValueError("Invalid phone number format")
        return v

    @field_validator("permission_granted")
    @classmethod
    def validate_permission(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Permission to contact trade reference is required")
        return v

    @model_validator(mode="after")
    def validate_contract_dates(self):
        if (
            self.contract_start_date is not None
            and self.contract_end_date is not None
            and self.contract_end_date < self.contract_start_date
        ):
            raise ValueError("Contract end date cannot be before contract start date")
        return self


class SupplierCreateRequest(BaseModel):
    """Request model for creating a new supplier application."""
    # Account Credentials
    password: str = Field(..., min_length=8)

    # Business Information
    company_name: str = Field(..., alias="companyName", min_length=2, max_length=200)
    # Primary category (backward compat); full list in business_categories
    business_category: BusinessCategory = Field(..., alias="businessCategory")
    business_categories: List[BusinessCategory] = Field(
        ..., alias="businessCategories",
        min_length=1, max_length=6,
        description="Up to 6 business categories",
    )
    registration_number: Optional[str] = Field(None, alias="registrationNumber", max_length=100)
    tax_id: Optional[str] = Field(None, alias="taxId", max_length=100)
    years_in_business: int = Field(..., alias="yearsInBusiness", ge=0, le=200)
    website: Optional[str] = Field(None, max_length=500)
    employee_count: Optional[int] = Field(None, alias="employeeCount", ge=0)
    is_small_scale_farmer: bool = Field(False, alias="isSmallScaleFarmer")

    # Key persons (directors or single contact for farmers)
    key_persons: List[KeyPersonRequest] = Field(
        ..., alias="keyPersons",
        min_length=1,
        description="One key person for farmers; one or more directors/contacts for formal suppliers",
    )
    trade_references: List[TradeReferenceRequest] = Field(
        ..., alias="tradeReferences",
        min_length=1, max_length=5,
        description="At least 1 and at most 5 trade references",
    )

    # Contact Information
    contact_person_name: str = Field(..., alias="contactPersonName", min_length=2, max_length=100)
    contact_person_title: str = Field(..., alias="contactPersonTitle", min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=30)

    # Address Information
    street_address: str = Field(..., alias="streetAddress", min_length=5, max_length=300)
    city: str = Field(..., min_length=2, max_length=100)
    state_province: str = Field(..., alias="stateProvince", min_length=2, max_length=100)
    postal_code: Optional[str] = Field(None, alias="postalCode", max_length=20)
    country: str = Field(..., min_length=2, max_length=100)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?[0-9]{7,20}$", cleaned):
            raise ValueError("Invalid phone number format")
        return v

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("business_categories")
    @classmethod
    def validate_categories_unique(cls, v: List[BusinessCategory]) -> List[BusinessCategory]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate categories are not allowed")
        return v


class SupplierUpdateRequest(BaseModel):
    """Request model for updating supplier information."""
    company_name: Optional[str] = Field(None, alias="companyName", min_length=2, max_length=200)
    business_category: Optional[BusinessCategory] = Field(None, alias="businessCategory")
    business_categories: Optional[List[BusinessCategory]] = Field(None, alias="businessCategories", max_length=6)
    registration_number: Optional[str] = Field(None, alias="registrationNumber", min_length=1, max_length=100)
    tax_id: Optional[str] = Field(None, alias="taxId", min_length=1, max_length=100)
    years_in_business: Optional[int] = Field(None, alias="yearsInBusiness", ge=0, le=200)
    website: Optional[str] = Field(None, max_length=500)
    employee_count: Optional[int] = Field(None, alias="employeeCount", ge=0)
    is_small_scale_farmer: Optional[bool] = Field(None, alias="isSmallScaleFarmer")
    contact_person_name: Optional[str] = Field(None, alias="contactPersonName", min_length=2, max_length=100)
    contact_person_title: Optional[str] = Field(None, alias="contactPersonTitle", min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=7, max_length=30)
    street_address: Optional[str] = Field(None, alias="streetAddress", min_length=5, max_length=300)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    state_province: Optional[str] = Field(None, alias="stateProvince", min_length=2, max_length=100)
    postal_code: Optional[str] = Field(None, alias="postalCode", max_length=20)
    country: Optional[str] = Field(None, min_length=2, max_length=100)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("business_categories")
    @classmethod
    def validate_categories_unique(cls, v: Optional[List[BusinessCategory]]) -> Optional[List[BusinessCategory]]:
        if v is not None and len(v) != len(set(v)):
            raise ValueError("Duplicate categories are not allowed")
        return v


class SupplierSubmitRequest(BaseModel):
    """Request model for submitting a supplier application."""
    supplier_id: str = Field(..., alias="supplierId")
    confirm_accuracy: bool = Field(..., alias="confirmAccuracy")
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator("confirm_accuracy")
    @classmethod
    def must_confirm(cls, v: bool) -> bool:
        """Ensure accuracy is confirmed."""
        if not v:
            raise ValueError("You must confirm the accuracy of your information")
        return v


class AdminRegisterSupplierRequest(BaseModel):
    """Request model for admin registering a supplier on their behalf."""
    # Business Information
    company_name: str = Field(..., alias="companyName", min_length=2, max_length=200)
    business_category: BusinessCategory = Field(..., alias="businessCategory")
    business_categories: List[BusinessCategory] = Field(
        ..., alias="businessCategories",
        min_length=1, max_length=6,
        description="Up to 6 business categories",
    )
    registration_number: Optional[str] = Field(None, alias="registrationNumber", max_length=100)
    tax_id: Optional[str] = Field(None, alias="taxId", max_length=100)
    years_in_business: int = Field(..., alias="yearsInBusiness", ge=0, le=200)
    website: Optional[str] = Field(None, max_length=500)
    employee_count: Optional[int] = Field(None, alias="employeeCount", ge=0)
    is_small_scale_farmer: bool = Field(False, alias="isSmallScaleFarmer")

    # Key persons (directors or single contact for farmers)
    key_persons: List[KeyPersonRequest] = Field(
        ..., alias="keyPersons",
        min_length=1,
        description="One key person for farmers; one or more directors/contacts for formal suppliers",
    )
    trade_references: List[TradeReferenceRequest] = Field(
        default_factory=list,
        alias="tradeReferences",
        max_length=5,
        description="Trade references (up to 5).",
    )

    # Contact Information
    contact_person_name: str = Field(..., alias="contactPersonName", min_length=2, max_length=100)
    contact_person_title: str = Field(..., alias="contactPersonTitle", min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=30)

    # Address Information
    street_address: str = Field(..., alias="streetAddress", min_length=5, max_length=300)
    city: str = Field(..., min_length=2, max_length=100)
    state_province: str = Field(..., alias="stateProvince", min_length=2, max_length=100)
    postal_code: Optional[str] = Field(None, alias="postalCode", max_length=20)
    country: str = Field(..., min_length=2, max_length=100)

    # Admin-only: immediately submit after creation (bypasses INCOMPLETE status)
    submit_immediately: bool = Field(False, alias="submitImmediately")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?[0-9]{7,20}$", cleaned):
            raise ValueError("Invalid phone number format")
        return v

    @field_validator("business_categories")
    @classmethod
    def validate_categories_unique(cls, v: List[BusinessCategory]) -> List[BusinessCategory]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate categories are not allowed")
        return v


# ============== Response Models ==============

class TradeReferenceResponse(BaseModel):
    """Response model for a supplier trade reference."""
    id: Optional[str] = None
    supplier_id: Optional[str] = Field(None, serialization_alias="supplierId")
    company_name: str = Field(..., serialization_alias="companyName")
    contact_person_name: str = Field(..., serialization_alias="contactPersonName")
    email: str
    phone: str
    relationship: str
    service_product: Optional[str] = Field(None, serialization_alias="serviceProduct")
    contract_start_date: Optional[date] = Field(None, serialization_alias="contractStartDate")
    contract_end_date: Optional[date] = Field(None, serialization_alias="contractEndDate")
    annual_spend: Optional[str] = Field(None, serialization_alias="annualSpend")
    permission_granted: bool = Field(..., serialization_alias="permissionGranted")
    created_at: Optional[datetime] = Field(None, serialization_alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TradeReferenceListResponse(BaseModel):
    """Response model for supplier trade references list."""
    supplier_id: str = Field(..., serialization_alias="supplierId")
    items: List[TradeReferenceResponse]
    total: int

    model_config = ConfigDict(populate_by_name=True)

class SupplierResponse(BaseModel):
    """Response model for supplier data."""
    id: str
    company_name: str = Field(..., serialization_alias="companyName")
    business_category: str = Field(..., serialization_alias="businessCategory")
    business_categories: Optional[List[str]] = Field(None, serialization_alias="businessCategories")
    registration_number: Optional[str] = Field(None, serialization_alias="registrationNumber")
    tax_id: Optional[str] = Field(None, serialization_alias="taxId")
    years_in_business: int = Field(..., serialization_alias="yearsInBusiness")
    website: Optional[str] = None
    employee_count: Optional[int] = Field(None, serialization_alias="employeeCount")
    is_small_scale_farmer: bool = Field(False, serialization_alias="isSmallScaleFarmer")
    supplier_type: Optional[SupplierType] = Field(None, serialization_alias="supplierType")
    business_size: Optional[BusinessSize] = Field(None, serialization_alias="businessSize")
    esg_women_owned: Optional[bool] = Field(None, serialization_alias="esgWomenOwned")
    esg_youth_owned: Optional[bool] = Field(None, serialization_alias="esgYouthOwned")
    contact_person_name: str = Field(..., serialization_alias="contactPersonName")
    contact_person_title: str = Field(..., serialization_alias="contactPersonTitle")
    email: str
    phone: str
    street_address: str = Field(..., serialization_alias="streetAddress")
    city: str
    state_province: str = Field(..., serialization_alias="stateProvince")
    postal_code: Optional[str] = Field(None, serialization_alias="postalCode")
    country: str
    status: SupplierStatus
    activity_status: Optional[SupplierActivityStatus] = Field(None, serialization_alias="activityStatus")
    admin_notes: Optional[str] = Field(None, serialization_alias="adminNotes")
    rejection_reason: Optional[str] = Field(None, serialization_alias="rejectionReason")
    info_request_message: Optional[str] = Field(None, serialization_alias="infoRequestMessage")
    created_at: datetime = Field(..., serialization_alias="createdAt")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updatedAt")
    submitted_at: Optional[datetime] = Field(None, serialization_alias="submittedAt")
    reviewed_at: Optional[datetime] = Field(None, serialization_alias="reviewedAt")
    reviewed_by: Optional[str] = Field(None, serialization_alias="reviewedBy")
    registered_by_admin: bool = Field(False, serialization_alias="registeredByAdmin")
    registered_by_admin_email: Optional[str] = Field(None, serialization_alias="registeredByAdminEmail")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SupplierListResponse(BaseModel):
    """Response model for paginated supplier list."""
    items: List[SupplierResponse] = Field(..., serialization_alias="suppliers")
    total: int
    page: int
    page_size: int = Field(..., serialization_alias="pageSize")
    total_pages: int = Field(..., serialization_alias="totalPages")
    
    model_config = ConfigDict(populate_by_name=True)


class RequiredDocumentsResponse(BaseModel):
    """Response model listing required documents for a category."""
    supplier_id: str = Field(..., serialization_alias="supplierId")
    business_category: BusinessCategory = Field(..., serialization_alias="businessCategory")
    mandatory_documents: List[str] = Field(..., serialization_alias="mandatoryDocuments")
    category_documents: List[str] = Field(..., serialization_alias="categoryDocuments")
    uploaded_documents: List[str] = Field(..., serialization_alias="uploadedDocuments")
    all_documents_uploaded: bool = Field(..., serialization_alias="allDocumentsUploaded")
    
    model_config = ConfigDict(populate_by_name=True)
