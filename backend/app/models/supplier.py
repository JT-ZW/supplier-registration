"""
Supplier-related Pydantic models for request/response validation.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
import re

from .enums import SupplierStatus, SupplierActivityStatus, BusinessCategory


# ============== Request Models ==============

class SupplierCreateRequest(BaseModel):
    """Request model for creating a new supplier application."""
    # Account Credentials
    password: str = Field(..., min_length=8)
    
    # Business Information
    company_name: str = Field(..., alias="companyName", min_length=2, max_length=200)
    business_category: BusinessCategory = Field(..., alias="businessCategory")
    registration_number: str = Field(..., alias="registrationNumber", min_length=1, max_length=100)
    tax_id: str = Field(..., alias="taxId", min_length=1, max_length=100)
    years_in_business: int = Field(..., alias="yearsInBusiness", ge=0, le=200)
    website: Optional[str] = Field(None, max_length=500)
    
    # Contact Information
    contact_person_name: str = Field(..., alias="contactPersonName", min_length=2, max_length=100)
    contact_person_title: str = Field(..., alias="contactPersonTitle", min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=30)
    
    # Address Information
    street_address: str = Field(..., alias="streetAddress", min_length=5, max_length=300)
    city: str = Field(..., min_length=2, max_length=100)
    state_province: str = Field(..., alias="stateProvince", min_length=2, max_length=100)
    postal_code: str = Field(..., alias="postalCode", min_length=3, max_length=20)
    country: str = Field(..., min_length=2, max_length=100)
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number format."""
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?[0-9]{7,20}$", cleaned):
            raise ValueError("Invalid phone number format")
        return v
    
    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, v: str) -> str:
        """Validate and clean company name."""
        return v.strip()


class SupplierUpdateRequest(BaseModel):
    """Request model for updating supplier information."""
    company_name: Optional[str] = Field(None, alias="companyName", min_length=2, max_length=200)
    business_category: Optional[BusinessCategory] = Field(None, alias="businessCategory")
    registration_number: Optional[str] = Field(None, alias="registrationNumber", min_length=1, max_length=100)
    tax_id: Optional[str] = Field(None, alias="taxId", min_length=1, max_length=100)
    years_in_business: Optional[int] = Field(None, alias="yearsInBusiness", ge=0, le=200)
    website: Optional[str] = Field(None, max_length=500)
    contact_person_name: Optional[str] = Field(None, alias="contactPersonName", min_length=2, max_length=100)
    contact_person_title: Optional[str] = Field(None, alias="contactPersonTitle", min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=7, max_length=30)
    street_address: Optional[str] = Field(None, alias="streetAddress", min_length=5, max_length=300)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    state_province: Optional[str] = Field(None, alias="stateProvince", min_length=2, max_length=100)
    postal_code: Optional[str] = Field(None, alias="postalCode", min_length=3, max_length=20)
    country: Optional[str] = Field(None, min_length=2, max_length=100)
    
    model_config = ConfigDict(populate_by_name=True)


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


# ============== Response Models ==============

class SupplierResponse(BaseModel):
    """Response model for supplier data."""
    id: str
    company_name: str = Field(..., serialization_alias="companyName")
    business_category: BusinessCategory = Field(..., serialization_alias="businessCategory")
    registration_number: str = Field(..., serialization_alias="registrationNumber")
    tax_id: str = Field(..., serialization_alias="taxId")
    years_in_business: int = Field(..., serialization_alias="yearsInBusiness")
    website: Optional[str] = None
    contact_person_name: str = Field(..., serialization_alias="contactPersonName")
    contact_person_title: str = Field(..., serialization_alias="contactPersonTitle")
    email: str
    phone: str
    street_address: str = Field(..., serialization_alias="streetAddress")
    city: str
    state_province: str = Field(..., serialization_alias="stateProvince")
    postal_code: str = Field(..., serialization_alias="postalCode")
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
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SupplierListResponse(BaseModel):
    """Response model for paginated supplier list."""
    items: List[SupplierResponse]
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
