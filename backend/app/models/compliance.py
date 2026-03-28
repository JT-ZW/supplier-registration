"""
Pydantic models for key persons, farmer application forms,
supplier category management, and compliance responses.
"""

from __future__ import annotations
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from .enums import (
    Gender,
    KeyPersonRole,
    BusinessCategory,
    ComplianceLevel,
    LandProofType,
    BusinessSize,
    SupplierType,
    CertGroup,
    CERT_GROUPS_BY_CATEGORY,
    compute_compliance_level,
)


# ── Key Persons ───────────────────────────────────────────────────────────────

class KeyPersonRequest(BaseModel):
    """A director (formal supplier) or key contact person (farmer)."""
    full_name: str = Field(..., alias="fullName", min_length=2, max_length=200)
    gender: Gender
    date_of_birth: Optional[date] = Field(None, alias="dateOfBirth")
    role: KeyPersonRole = KeyPersonRole.DIRECTOR

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[date]) -> Optional[date]:
        if v is None:
            return v
        if v >= date.today():
            raise ValueError("Date of birth must be in the past")
        age = (date.today() - v).days // 365
        if age > 120:
            raise ValueError("Date of birth is not realistic")
        return v


class KeyPersonResponse(BaseModel):
    """Response model for a key person record."""
    id: str
    supplier_id: str
    full_name: str
    gender: Gender
    date_of_birth: date
    age: int  # Computed field
    role: KeyPersonRole
    is_youth: bool  # age < 35
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_db(cls, row: dict) -> "KeyPersonResponse":
        dob = row["date_of_birth"]
        if isinstance(dob, str):
            dob = date.fromisoformat(dob)
        age = (date.today() - dob).days // 365
        return cls(
            id=row["id"],
            supplier_id=row["supplier_id"],
            full_name=row["full_name"],
            gender=Gender(row["gender"]),
            date_of_birth=dob,
            age=age,
            role=KeyPersonRole(row.get("role", "DIRECTOR")),
            is_youth=age < 35,
            created_at=row["created_at"],
        )


class KeyPersonListResponse(BaseModel):
    items: List[KeyPersonResponse]
    total: int


# ── Farmer Application Form ───────────────────────────────────────────────────

class FarmerApplicationFormRequest(BaseModel):
    """Inline application form for small-scale farmer registration."""
    supplier_id: str = Field(..., alias="supplierId")

    # Identity
    contact_full_name: str = Field(..., alias="contactFullName", min_length=2, max_length=200)
    id_number: Optional[str] = Field(None, alias="idNumber", max_length=100)
    gender: Gender
    date_of_birth: date = Field(..., alias="dateOfBirth")

    # Farming details
    farming_activity: str = Field(..., alias="farmingActivity", min_length=5, max_length=2000,
                                   description="Description of what is farmed / reared")
    produce_types: str = Field(..., alias="produceTypes", min_length=2, max_length=500,
                                description="Comma-separated list of produce / livestock")
    estimated_land_size_ha: Optional[float] = Field(None, alias="estimatedLandSizeHa", ge=0)
    years_farming: Optional[int] = Field(None, alias="yearsFarming", ge=0, le=100)

    # Land proof
    land_proof_type: Optional[LandProofType] = Field(None, alias="landProofType")
    village_or_farm_name: Optional[str] = Field(None, alias="villageOrFarmName", max_length=200)
    district: Optional[str] = Field(None, max_length=100)
    province: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, alias="contactPhone", max_length=30)

    # Financial / ESG
    has_bank_account: bool = Field(False, alias="hasBankAccount")
    bank_name: Optional[str] = Field(None, alias="bankName", max_length=100)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        if v >= date.today():
            raise ValueError("Date of birth must be in the past")
        return v


class FarmerApplicationFormResponse(BaseModel):
    id: str
    supplier_id: str
    contact_full_name: str
    id_number: Optional[str]
    gender: Gender
    date_of_birth: date
    farming_activity: str
    produce_types: str
    estimated_land_size_ha: Optional[float]
    years_farming: Optional[int]
    land_proof_type: Optional[LandProofType]
    village_or_farm_name: Optional[str]
    district: Optional[str]
    province: Optional[str]
    contact_phone: Optional[str]
    has_bank_account: bool
    bank_name: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True)


# ── Supplier Categories ───────────────────────────────────────────────────────

class SupplierCategoryRequest(BaseModel):
    """Add a business category to a supplier."""
    supplier_id: str = Field(..., alias="supplierId")
    category: BusinessCategory

    model_config = ConfigDict(populate_by_name=True)


class SupplierCategoryResponse(BaseModel):
    id: str
    supplier_id: str
    category: BusinessCategory
    compliance_status: ComplianceLevel
    compliance_checked_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True)


class SupplierCategoryListResponse(BaseModel):
    items: List[SupplierCategoryResponse]
    total: int


# ── Compliance ────────────────────────────────────────────────────────────────

class CertGroupResponse(BaseModel):
    """Serialisable form of CertGroup for API responses."""
    name: str
    description: str
    document_types: List[str]  # DocumentType values
    is_mandatory_upload: bool
    requirement_level: str

    @classmethod
    def from_cert_group(cls, grp: CertGroup) -> "CertGroupResponse":
        return cls(
            name=grp.name,
            description=grp.description,
            document_types=[dt.value for dt in grp.document_types],
            is_mandatory_upload=grp.is_mandatory_upload,
            requirement_level=grp.requirement_level,
        )


class CategoryRequirementsResponse(BaseModel):
    """The full cert group requirements for one business category."""
    category: BusinessCategory
    cert_groups: List[CertGroupResponse]

    @classmethod
    def for_category(cls, category: BusinessCategory) -> "CategoryRequirementsResponse":
        groups = CERT_GROUPS_BY_CATEGORY.get(category, [])
        return cls(
            category=category,
            cert_groups=[CertGroupResponse.from_cert_group(g) for g in groups],
        )


class SupplierComplianceSummary(BaseModel):
    """Compliance summary for one supplier across all their categories."""
    supplier_id: str
    categories: List[SupplierCategoryResponse]
    overall_worst_level: ComplianceLevel  # worst level across non-excluded categories

    model_config = ConfigDict(populate_by_name=True)


# ── ESG Summary ───────────────────────────────────────────────────────────────

class ESGSummaryResponse(BaseModel):
    """ESG classification summary for a supplier."""
    supplier_id: str
    company_name: str
    supplier_type: SupplierType
    business_size: Optional[BusinessSize]
    employee_count: Optional[int]
    is_small_scale_farmer: bool
    esg_women_owned: Optional[bool]
    esg_youth_owned: Optional[bool]
    key_person_count: int
    female_director_count: int
    youth_director_count: int

    model_config = ConfigDict(populate_by_name=True)
