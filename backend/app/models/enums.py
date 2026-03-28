"""
Enum definitions and compliance/ESG business logic for the application.
Using string enums for database compatibility.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional


class AdminRole(str, Enum):
    """Roles for admin users."""
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    PROCUREMENT_MANAGER = "PROCUREMENT_MANAGER"


class SupplierStatus(str, Enum):
    """Status lifecycle for supplier applications."""
    INCOMPLETE = "INCOMPLETE"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    NEED_MORE_INFO = "NEED_MORE_INFO"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLIANCE_REQUIRED = "COMPLIANCE_REQUIRED"  # Approved supplier with expired documents
    SUSPENDED = "SUSPENDED"  # Supplier suspended due to unresolved expired documents


class SupplierActivityStatus(str, Enum):
    """Activity status for approved suppliers."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


# ── New enums ─────────────────────────────────────────────────────────────────

class SupplierType(str, Enum):
    """Derived supplier classification based on country and farmer flag."""
    LOCAL = "LOCAL"                # Zimbabwe-based formal business
    FOREIGN = "FOREIGN"            # Non-Zimbabwe business
    LOCAL_FARMER = "LOCAL_FARMER"  # Zimbabwe-based informal small-scale farmer


class BusinessSize(str, Enum):
    """Business size classification derived from employee count."""
    SMALL = "SMALL"    # < 10 employees
    MEDIUM = "MEDIUM"  # 10-50 employees
    LARGE = "LARGE"    # > 50 employees


class Gender(str, Enum):
    """Gender options for key persons (ESG tracking)."""
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class KeyPersonRole(str, Enum):
    """Role of a key person record."""
    DIRECTOR = "DIRECTOR"  # Up to 3 for formal suppliers
    CONTACT = "CONTACT"    # Exactly 1 for small-scale farmers


class ComplianceLevel(str, Enum):
    """Per-category compliance classification for a supplier."""
    FULL_COMPLIANCE = "FULL_COMPLIANCE"  # All mandatory + all preferred docs uploaded
    MEDIUM_RISK = "MEDIUM_RISK"          # Mandatory docs present; preferred docs missing
    HIGH_RISK = "HIGH_RISK"              # One or more mandatory-upload docs missing
    PENDING = "PENDING"                  # Not yet evaluated
    EXCLUDED = "EXCLUDED"                # Legacy category; not scored


class LandProofType(str, Enum):
    """Type of land proof document for small-scale farmers."""
    OFFER_LETTER = "OFFER_LETTER"
    TITLE_DEEDS = "TITLE_DEEDS"
    VILLAGE_HEAD_LETTER = "VILLAGE_HEAD_LETTER"


class BusinessCategory(str, Enum):
    """Official RTG supplier business categories."""
    CLEANING_EQUIPMENT_SUPPLIERS = "CLEANING_EQUIPMENT_SUPPLIERS"
    CONSTRUCTION_CONTRACTORS = "CONSTRUCTION_CONTRACTORS"
    DAIRY_SUPPLIERS = "DAIRY_SUPPLIERS"
    ELECTRICAL_CONTRACTORS = "ELECTRICAL_CONTRACTORS"
    ENERGY_SUPPLIERS = "ENERGY_SUPPLIERS"
    FOOD_BEVERAGE_SUPPLIERS = "FOOD_BEVERAGE_SUPPLIERS"
    FRUIT_VEGETABLE_SUPPLIERS = "FRUIT_VEGETABLE_SUPPLIERS"
    FURNITURE_SUPPLIERS = "FURNITURE_SUPPLIERS"
    HOTEL_GUEST_LINEN = "HOTEL_GUEST_LINEN"
    HOTEL_GUEST_AMENITIES = "HOTEL_GUEST_AMENITIES"
    HOUSEKEEPING_CHEMICALS = "HOUSEKEEPING_CHEMICALS"
    ICT_TECHNOLOGY = "ICT_TECHNOLOGY"
    KITCHEN_EQUIPMENT = "KITCHEN_EQUIPMENT"
    LANDSCAPING_GARDENING = "LANDSCAPING_GARDENING"
    LAUNDRY_SERVICES = "LAUNDRY_SERVICES"
    MEAT_SUPPLIERS = "MEAT_SUPPLIERS"
    PPE_SUPPLIERS = "PPE_SUPPLIERS"
    PEST_CONTROL = "PEST_CONTROL"
    PLUMBING_CONTRACTORS = "PLUMBING_CONTRACTORS"
    SECURITY_SERVICES = "SECURITY_SERVICES"
    TRANSPORT_LOGISTICS = "TRANSPORT_LOGISTICS"
    WASTE_MANAGEMENT = "WASTE_MANAGEMENT"
    ROPE_ACCESS = "ROPE_ACCESS"
    # Legacy values present in existing database records
    HEALTHCARE = "HEALTHCARE"
    CONSULTING = "CONSULTING"
    GENERAL_SUPPLIES = "GENERAL_SUPPLIES"
    MEAT_PRODUCTS = "MEAT_PRODUCTS"
    CONSTRUCTION = "CONSTRUCTION"
    FOOD_BEVERAGE = "FOOD_BEVERAGE"
    IT_SERVICES = "IT_SERVICES"
    LOGISTICS = "LOGISTICS"
    FRESH_FARM_PRODUCE = "FRESH_FARM_PRODUCE"


class DocumentType(str, Enum):
    """Types of documents that can be uploaded."""
    # ── Statutory – Local (Zimbabwe) formal suppliers ─────────────────────────
    COMPANY_PROFILE = "COMPANY_PROFILE"
    CERTIFICATE_OF_INCORPORATION = "CERTIFICATE_OF_INCORPORATION"
    CR14_OR_CR6 = "CR14_OR_CR6"             # Lists company directors
    CR5 = "CR5"                             # Proof of business physical address
    VAT_CERTIFICATE = "VAT_CERTIFICATE"
    TAX_CLEARANCE = "TAX_CLEARANCE"
    FDMS_COMPLIANCE = "FDMS_COMPLIANCE"
    ID_PASSPORT_COPY = "ID_PASSPORT_COPY"   # For each key director / contact person

    # ── Statutory – Foreign suppliers ─────────────────────────────────────────
    DIRECTORS_LIST = "DIRECTORS_LIST"           # Any statutory doc listing directors
    PHYSICAL_ADDRESS_PROOF = "PHYSICAL_ADDRESS_PROOF"  # Statutory address proof
    TAX_COMPLIANCE_FOREIGN = "TAX_COMPLIANCE_FOREIGN"  # Foreign tax compliance equiv.

    # ── Statutory – Small-scale farmer ───────────────────────────────────────
    OFFER_LETTER_TITLE_DEEDS = "OFFER_LETTER_TITLE_DEEDS"  # Land / location proof

    # ── Category certification documents ─────────────────────────────────────
    # Food safety
    HACCP = "HACCP"
    ISO_22000 = "ISO_22000"
    FSSC_22000 = "FSSC_22000"
    VETERINARY_HEALTH_CERT = "VETERINARY_HEALTH_CERT"
    GLOBAL_GAP_CERT = "GLOBAL_GAP_CERT"
    # H&S / Occupational
    ISO_45001 = "ISO_45001"
    NSSA_COMPLIANCE = "NSSA_COMPLIANCE"
    SHEQ_POLICY = "SHEQ_POLICY"
    LICENSED_ELECTRICIAN_CERT = "LICENSED_ELECTRICIAN_CERT"
    LICENSED_PLUMBER_CERT = "LICENSED_PLUMBER_CERT"
    # Environmental
    ISO_14000 = "ISO_14000"
    ENVIRONMENTAL_LICENSE = "ENVIRONMENTAL_LICENSE"
    ECO_LANDSCAPING_CERT = "ECO_LANDSCAPING_CERT"
    # Sustainability / energy
    RENEWABLE_ENERGY_CERT = "RENEWABLE_ENERGY_CERT"
    # Product quality / standards
    ISO_9001 = "ISO_9001"
    ISO_9001_PRODUCT_WARRANTY = "ISO_9001_PRODUCT_WARRANTY"
    CE_SABS_CERT = "CE_SABS_CERT"
    PPE_CERTIFICATION = "PPE_CERTIFICATION"
    MATERIAL_SAFETY_DATA_SHEETS = "MATERIAL_SAFETY_DATA_SHEETS"
    # Textile / linen quality
    OEKO_TEX_CERT = "OEKO_TEX_CERT"
    GOTS_BCI_CERT = "GOTS_BCI_CERT"
    # ICT
    ISO_27001 = "ISO_27001"
    # Security / licenced operations
    REGISTERED_SECURITY_LICENSE = "REGISTERED_SECURITY_LICENSE"
    PEST_CONTROL_CHEMICAL_LICENSE = "PEST_CONTROL_CHEMICAL_LICENSE"
    # Transport
    ROADWORTHINESS_CERT = "ROADWORTHINESS_CERT"
    TRANSPORT_OPERATORS_LICENSE = "TRANSPORT_OPERATORS_LICENSE"
    # Rope access
    IRATA_CERT = "IRATA_CERT"
    WORKING_AT_HEIGHTS_CERT = "WORKING_AT_HEIGHTS_CERT"
    PUBLIC_LIABILITY_INSURANCE = "PUBLIC_LIABILITY_INSURANCE"
    # Internal quality
    INTERNAL_QMS = "INTERNAL_QMS"
    # Sustainability add-ons (kept for backward compatibility)
    HEALTH_CERTIFICATE = "HEALTH_CERTIFICATE"
    FOOD_SAFETY_CERTIFICATION = "FOOD_SAFETY_CERTIFICATION"
    GOOD_AGRICULTURAL_PRACTICES = "GOOD_AGRICULTURAL_PRACTICES"
    ISO_45000 = "ISO_45000"
    INDUSTRY_CERTIFICATION = "INDUSTRY_CERTIFICATION"

    # Farmer application form
    APPLICATION_FORM = "APPLICATION_FORM"
    # Rope access safety documents
    SAFETY_METHOD_STATEMENT = "SAFETY_METHOD_STATEMENT"
    RESCUE_PLAN = "RESCUE_PLAN"

    # ── Admin-only ────────────────────────────────────────────────────────────
    EVALUATION_FORM = "EVALUATION_FORM"
    SUSPENSION_EVIDENCE = "SUSPENSION_EVIDENCE"


class DocumentVerificationStatus(str, Enum):
    """Verification status for uploaded documents."""
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class AdminAction(str, Enum):
    """Actions that admins can perform (for audit logging)."""
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    VIEW_APPLICATION = "VIEW_APPLICATION"
    APPROVE_DOCUMENT = "APPROVE_DOCUMENT"
    REJECT_DOCUMENT = "REJECT_DOCUMENT"
    APPROVE_APPLICATION = "APPROVE_APPLICATION"
    REJECT_APPLICATION = "REJECT_APPLICATION"
    REQUEST_MORE_INFO = "REQUEST_MORE_INFO"
    EXPORT_REPORT = "EXPORT_REPORT"
    UPDATE_SUPPLIER_STATUS = "UPDATE_SUPPLIER_STATUS"
    DELETE_SUPPLIER = "DELETE_SUPPLIER"


# ── Statutory document lists by supplier type ────────────────────────────────

# Backward-compatible alias – still used by existing routes / tests
MANDATORY_DOCUMENTS = [
    DocumentType.COMPANY_PROFILE,
    DocumentType.CERTIFICATE_OF_INCORPORATION,
    DocumentType.CR14_OR_CR6,
    DocumentType.VAT_CERTIFICATE,
    DocumentType.TAX_CLEARANCE,
    DocumentType.FDMS_COMPLIANCE,
]

LOCAL_MANDATORY_DOCUMENTS: List[DocumentType] = [
    DocumentType.COMPANY_PROFILE,
    DocumentType.CERTIFICATE_OF_INCORPORATION,
    DocumentType.CR14_OR_CR6,       # Directors
    DocumentType.CR5,               # Physical address
    DocumentType.VAT_CERTIFICATE,
    DocumentType.TAX_CLEARANCE,
    DocumentType.FDMS_COMPLIANCE,
    DocumentType.ID_PASSPORT_COPY,  # For each of the up-to-3 directors
]

FOREIGN_MANDATORY_DOCUMENTS: List[DocumentType] = [
    DocumentType.COMPANY_PROFILE,
    DocumentType.CERTIFICATE_OF_INCORPORATION,  # or equivalent proof of registration
    DocumentType.DIRECTORS_LIST,                # Any statutory doc listing directors
    DocumentType.PHYSICAL_ADDRESS_PROOF,
    DocumentType.TAX_COMPLIANCE_FOREIGN,
    DocumentType.ID_PASSPORT_COPY,              # For each of the up-to-3 directors
]

FARMER_MANDATORY_DOCUMENTS: List[DocumentType] = [
    # Farmers register via the inline FarmerApplicationForm (no statutory corp docs).
    # Land proof + ID + the downloadable application form are required.
    DocumentType.ID_PASSPORT_COPY,
    DocumentType.OFFER_LETTER_TITLE_DEEDS,
    DocumentType.APPLICATION_FORM,
]

# Set of document types that never carry an expiry date
NO_EXPIRY_DOCUMENT_TYPES: set = {
    DocumentType.COMPANY_PROFILE,
    DocumentType.CERTIFICATE_OF_INCORPORATION,
    DocumentType.CR14_OR_CR6,
    DocumentType.CR5,
    DocumentType.DIRECTORS_LIST,
    DocumentType.PHYSICAL_ADDRESS_PROOF,
    DocumentType.OFFER_LETTER_TITLE_DEEDS,
    DocumentType.EVALUATION_FORM,
    DocumentType.SHEQ_POLICY,
    DocumentType.INTERNAL_QMS,
    DocumentType.MATERIAL_SAFETY_DATA_SHEETS,
    DocumentType.GOTS_BCI_CERT,
    DocumentType.OEKO_TEX_CERT,
    DocumentType.APPLICATION_FORM,
    DocumentType.SAFETY_METHOD_STATEMENT,
    DocumentType.RESCUE_PLAN,
}

EXPIRY_REQUIRED_DOCUMENT_TYPES: List[DocumentType] = [
    dt for dt in DocumentType if dt not in NO_EXPIRY_DOCUMENT_TYPES
]


# ── CertGroup: the core unit of category compliance ───────────────────────────

@dataclass
class CertGroup:
    """
    A named certification requirement for a business category.

    A supplier satisfies this group by uploading **at least one** of the
    listed document_types.  Uploading more than one is supported and tracked.

    Attributes:
        name:                 Short name shown in the UI.
        description:          Human-readable description of what is required.
        document_types:       Acceptable documents; supplier must upload ≥ 1.
        is_mandatory_upload:  True → system blocks submission without this group.
                              False → preferred/optional; absence = MEDIUM_RISK.
        requirement_level:    Source classification from the RTG compliance schedule.
    """
    name: str
    description: str
    document_types: List[DocumentType]
    is_mandatory_upload: bool
    requirement_level: str  # 'MANDATORY_COMPLIANCE' | 'PREFERRED_CERTIFICATION' | 'FUTURE_SUSTAINABILITY'


# ── Cert groups per category ──────────────────────────────────────────────────
# Source: RTG Supplier Compliance Requirements Schedule
# Each entry is a list of CertGroup objects.  Order is display order in the UI.

CERT_GROUPS_BY_CATEGORY: dict = {

    BusinessCategory.CLEANING_EQUIPMENT_SUPPLIERS: [
        CertGroup(
            name="Quality Assurance",
            description="Equipment quality compliance – ISO 9001 or manufacturer certification",
            document_types=[DocumentType.ISO_9001],
            is_mandatory_upload=False,
            requirement_level="PREFERRED_CERTIFICATION",
        ),
    ],

    BusinessCategory.CONSTRUCTION_CONTRACTORS: [
        CertGroup(
            name="Health & Safety Management",
            description="Occupational Health & Safety Management System – ISO 45001 or NSSA Compliance",
            document_types=[DocumentType.ISO_45001, DocumentType.NSSA_COMPLIANCE],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],

    BusinessCategory.DAIRY_SUPPLIERS: [
        CertGroup(
            name="Food Safety – Dairy",
            description="Dairy processing hygiene compliance – HACCP or ISO 22000",
            document_types=[DocumentType.HACCP, DocumentType.ISO_22000],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],

    BusinessCategory.ELECTRICAL_CONTRACTORS: [
        CertGroup(
            name="Electrical Safety Certification",
            description="Electrical safety certification – Licensed Electrician Cert or Safety Compliance",
            document_types=[DocumentType.LICENSED_ELECTRICIAN_CERT],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],

    BusinessCategory.ENERGY_SUPPLIERS: [
        CertGroup(
            name="Renewable Energy Certification",
            description="Renewable energy or carbon reduction initiatives – Renewable Energy Certification",
            document_types=[DocumentType.RENEWABLE_ENERGY_CERT],
            is_mandatory_upload=False,
            requirement_level="FUTURE_SUSTAINABILITY",
        ),
    ],

    BusinessCategory.FOOD_BEVERAGE_SUPPLIERS: [
        CertGroup(
            name="Food Safety Management",
            description="Food Safety Management System – HACCP, ISO 22000, or FSSC 22000",
            document_types=[
                DocumentType.HACCP,
                DocumentType.ISO_22000,
                DocumentType.FSSC_22000,
            ],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],

    BusinessCategory.FRUIT_VEGETABLE_SUPPLIERS: [
        CertGroup(
            name="Good Agricultural Practices",
            description="Agricultural sustainability – Global GAP Certification",
            document_types=[DocumentType.GLOBAL_GAP_CERT],
            is_mandatory_upload=False,
            requirement_level="PREFERRED_CERTIFICATION",
        ),
    ],

    BusinessCategory.FURNITURE_SUPPLIERS: [
        CertGroup(
            name="Product Quality",
            description="Furniture quality and durability standards – ISO 9001 or Product Warranty",
            document_types=[DocumentType.ISO_9001, DocumentType.ISO_9001_PRODUCT_WARRANTY],
            is_mandatory_upload=False,
            requirement_level="PREFERRED_CERTIFICATION",
        ),
    ],

    BusinessCategory.HOTEL_GUEST_LINEN: [
        CertGroup(
            name="Textile Quality",
            description="Quality and durability standards – OEKO-TEX Standard 100, GOTS/BCI, or ISO 9001",
            document_types=[
                DocumentType.OEKO_TEX_CERT,
                DocumentType.GOTS_BCI_CERT,
                DocumentType.ISO_9001,
            ],
            is_mandatory_upload=True,
            requirement_level="PREFERRED_CERTIFICATION",
        ),
    ],

    BusinessCategory.HOTEL_GUEST_AMENITIES: [
        CertGroup(
            name="Product Quality Assurance",
            description="Product safety & quality assurance – ISO 9001 or Product Quality Certification",
            document_types=[DocumentType.ISO_9001, DocumentType.ISO_9001_PRODUCT_WARRANTY],
            is_mandatory_upload=True,
            requirement_level="PREFERRED_CERTIFICATION",
        ),
    ],

    BusinessCategory.HOUSEKEEPING_CHEMICALS: [
        CertGroup(
            name="Chemical Safety",
            description="Safe chemical handling and labeling – Material Safety Data Sheets (MSDS)",
            document_types=[DocumentType.MATERIAL_SAFETY_DATA_SHEETS],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],

    BusinessCategory.ICT_TECHNOLOGY: [
        CertGroup(
            name="Information Security",
            description="Information security management – ISO 27001 or other Industry Certification",
            document_types=[DocumentType.ISO_27001, DocumentType.INDUSTRY_CERTIFICATION],
            is_mandatory_upload=False,
            requirement_level="PREFERRED_CERTIFICATION",
        ),
    ],

    BusinessCategory.KITCHEN_EQUIPMENT: [
        CertGroup(
            name="Kitchen Equipment Safety",
            description="Commercial kitchen equipment safety – CE or SABS Certification",
            document_types=[DocumentType.CE_SABS_CERT],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],

    BusinessCategory.LANDSCAPING_GARDENING: [
        CertGroup(
            name="Environmental Sustainability",
            description="Sustainable landscaping practices – Environmental Policy or Eco Landscaping Cert",
            document_types=[DocumentType.ENVIRONMENTAL_LICENSE, DocumentType.ECO_LANDSCAPING_CERT],
            is_mandatory_upload=False,
            requirement_level="PREFERRED_CERTIFICATION",
        ),
    ],

    BusinessCategory.LAUNDRY_SERVICES: [
        CertGroup(
            name="Environmental Management",
            description="Water and chemical management systems – ISO 14001 or Environmental Policy",
            document_types=[DocumentType.ISO_14000, DocumentType.ENVIRONMENTAL_LICENSE],
            is_mandatory_upload=True,
            requirement_level="PREFERRED_CERTIFICATION",
        ),
    ],

    BusinessCategory.MEAT_SUPPLIERS: [
        CertGroup(
            name="Meat Inspection & Hygiene",
            description="Meat inspection & hygiene compliance – Veterinary Health Certificate or HACCP",
            document_types=[DocumentType.VETERINARY_HEALTH_CERT, DocumentType.HACCP],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],

    BusinessCategory.PPE_SUPPLIERS: [
        CertGroup(
            name="PPE Safety Standards",
            description="PPE safety compliance – ISO 9001:2015 or PPE Certification",
            document_types=[DocumentType.ISO_9001, DocumentType.PPE_CERTIFICATION],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],

    BusinessCategory.PEST_CONTROL: [
        CertGroup(
            name="Pest Control Licensing",
            description="Safe pest control chemical use – Pest Control License or Chemical Handling Cert",
            document_types=[
                DocumentType.PEST_CONTROL_CHEMICAL_LICENSE,
            ],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],

    BusinessCategory.PLUMBING_CONTRACTORS: [
        CertGroup(
            name="Plumbing Compliance",
            description="Water and plumbing compliance – Licensed Plumber Certification",
            document_types=[DocumentType.LICENSED_PLUMBER_CERT],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],

    BusinessCategory.SECURITY_SERVICES: [
        CertGroup(
            name="Security Operations Compliance",
            description="Security operations compliance – Registered Security Company License",
            document_types=[DocumentType.REGISTERED_SECURITY_LICENSE],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],

    BusinessCategory.TRANSPORT_LOGISTICS: [
        CertGroup(
            name="Vehicle & Driver Safety",
            description="Vehicle and driver safety compliance – Roadworthiness Certificate or Transport Operators License",
            document_types=[
                DocumentType.ROADWORTHINESS_CERT,
                DocumentType.TRANSPORT_OPERATORS_LICENSE,
            ],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],

    BusinessCategory.WASTE_MANAGEMENT: [
        CertGroup(
            name="Waste Disposal & Recycling",
            description="Waste disposal and recycling compliance – Environmental License or ISO 14001",
            document_types=[DocumentType.ENVIRONMENTAL_LICENSE, DocumentType.ISO_14000],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],

    BusinessCategory.ROPE_ACCESS: [
        CertGroup(
            name="Rope Access & Working at Height",
            description=(
                "Safe work-at-height – pick at least one: IRATA Cert; "
                "Working at Heights Cert; Public Liability Insurance; "
                "Safety Method Statement; or Rescue Plan"
            ),
            document_types=[
                DocumentType.IRATA_CERT,
                DocumentType.WORKING_AT_HEIGHTS_CERT,
                DocumentType.PUBLIC_LIABILITY_INSURANCE,
                DocumentType.SAFETY_METHOD_STATEMENT,
                DocumentType.RESCUE_PLAN,
            ],
            is_mandatory_upload=True,
            requirement_level="MANDATORY_COMPLIANCE",
        ),
    ],
}

# Legacy categories – not scored for compliance
LEGACY_CATEGORIES: set = {
    BusinessCategory.HEALTHCARE,
    BusinessCategory.CONSULTING,
    BusinessCategory.GENERAL_SUPPLIES,
    BusinessCategory.MEAT_PRODUCTS,
    BusinessCategory.CONSTRUCTION,
    BusinessCategory.FOOD_BEVERAGE,
}

# Kept for backward compatibility with existing routes
CATEGORY_DOCUMENTS: dict = {
    cat: [dt for grp in groups for dt in grp.document_types]
    for cat, groups in CERT_GROUPS_BY_CATEGORY.items()
}

SUSTAINABILITY_DOCUMENTS: dict = {
    BusinessCategory.MEAT_SUPPLIERS: [DocumentType.FOOD_SAFETY_CERTIFICATION],
    BusinessCategory.DAIRY_SUPPLIERS: [DocumentType.FOOD_SAFETY_CERTIFICATION, DocumentType.GOOD_AGRICULTURAL_PRACTICES],
    BusinessCategory.FRUIT_VEGETABLE_SUPPLIERS: [DocumentType.GOOD_AGRICULTURAL_PRACTICES],
    BusinessCategory.FOOD_BEVERAGE_SUPPLIERS: [DocumentType.FOOD_SAFETY_CERTIFICATION],
    BusinessCategory.CONSTRUCTION_CONTRACTORS: [DocumentType.ISO_14000, DocumentType.ISO_45000],
    BusinessCategory.ELECTRICAL_CONTRACTORS: [DocumentType.ISO_14000, DocumentType.ISO_45000],
    BusinessCategory.PLUMBING_CONTRACTORS: [DocumentType.ISO_14000],
    BusinessCategory.WASTE_MANAGEMENT: [DocumentType.ISO_45000],
    BusinessCategory.ROPE_ACCESS: [DocumentType.INDUSTRY_CERTIFICATION],
}


# ── Helper functions ──────────────────────────────────────────────────────────

def get_supplier_type(country: str, is_small_scale_farmer: bool) -> SupplierType:
    """Derive SupplierType from country name and farmer flag."""
    if country.strip().upper() == "ZIMBABWE":
        return SupplierType.LOCAL_FARMER if is_small_scale_farmer else SupplierType.LOCAL
    return SupplierType.FOREIGN


def get_statutory_documents(supplier_type: SupplierType) -> List[DocumentType]:
    """Return the list of statutory documents required for the given supplier type."""
    if supplier_type == SupplierType.LOCAL:
        return LOCAL_MANDATORY_DOCUMENTS
    if supplier_type == SupplierType.FOREIGN:
        return FOREIGN_MANDATORY_DOCUMENTS
    return FARMER_MANDATORY_DOCUMENTS  # LOCAL_FARMER


def compute_business_size(employee_count: Optional[int]) -> Optional[BusinessSize]:
    """Classify a supplier by number of employees."""
    if employee_count is None:
        return None
    if employee_count < 10:
        return BusinessSize.SMALL
    if employee_count <= 50:
        return BusinessSize.MEDIUM
    return BusinessSize.LARGE


def compute_esg_flags(key_persons: list) -> dict:
    """
    Compute ESG flags from a list of key person dicts.

    Each dict must have:
        gender        (str) – 'MALE' | 'FEMALE' | 'OTHER'
        date_of_birth (date | str) – used to compute age

    Returns:
        { 'esg_women_owned': bool, 'esg_youth_owned': bool }

    Classification rules:
        women_owned  → > 50 % of key persons are female
        youth_owned  → > 50 % of key persons are under 35 years old
    """
    if not key_persons:
        return {"esg_women_owned": False, "esg_youth_owned": False}

    total = len(key_persons)
    today = date.today()

    female_count = sum(
        1 for p in key_persons
        if str(p.get("gender", "")).upper() == "FEMALE"
    )

    youth_count = 0
    for p in key_persons:
        dob = p.get("date_of_birth")
        if dob:
            if isinstance(dob, str):
                try:
                    dob = date.fromisoformat(dob)
                except ValueError:
                    continue
            age = (today - dob).days // 365
            if age < 35:
                youth_count += 1

    return {
        "esg_women_owned": (female_count / total) > 0.5,
        "esg_youth_owned": (youth_count / total) > 0.5,
    }


def compute_compliance_level(
    category: BusinessCategory,
    uploaded_doc_types: set,
) -> ComplianceLevel:
    """
    Determine the compliance level for a supplier in a given category.

    Args:
        category:            The business category being assessed.
        uploaded_doc_types:  Set of DocumentType values the supplier has uploaded
                             (only VERIFIED documents should be included by callers).

    Returns:
        ComplianceLevel
    """
    if category in LEGACY_CATEGORIES:
        return ComplianceLevel.EXCLUDED

    groups = CERT_GROUPS_BY_CATEGORY.get(category, [])
    if not groups:
        # Category requires no category-specific docs → full compliance if statutory docs present
        return ComplianceLevel.FULL_COMPLIANCE

    mandatory_satisfied = True
    preferred_satisfied = True

    for grp in groups:
        group_satisfied = any(dt in uploaded_doc_types for dt in grp.document_types)
        if not group_satisfied:
            if grp.is_mandatory_upload:
                mandatory_satisfied = False
            elif grp.requirement_level != "FUTURE_SUSTAINABILITY":
                preferred_satisfied = False

    if not mandatory_satisfied:
        return ComplianceLevel.HIGH_RISK
    if not preferred_satisfied:
        return ComplianceLevel.MEDIUM_RISK
    return ComplianceLevel.FULL_COMPLIANCE


def get_required_documents(category: BusinessCategory) -> List[DocumentType]:
    """
    Backward-compatible helper: returns all cert-group document types for a category.
    (Does not include statutory documents – callers must add those separately.)
    """
    return CATEGORY_DOCUMENTS.get(category, [])


def get_sustainability_documents(category: BusinessCategory) -> List[DocumentType]:
    """Return optional sustainability documents for a category."""
    return SUSTAINABILITY_DOCUMENTS.get(category, [])



def get_sustainability_documents(category: BusinessCategory) -> list[DocumentType]:
    """
    Get optional sustainability documents for a given business category.
    These documents are not mandatory but improve an application's strength.
    """
    return SUSTAINABILITY_DOCUMENTS.get(category, [])


# Flat, deduplicated list of all sustainability/QC document types across all categories.
# Used for database queries and report generation.
SUSTAINABILITY_DOC_TYPES: list[DocumentType] = list({
    doc_type
    for doc_types in SUSTAINABILITY_DOCUMENTS.values()
    for doc_type in doc_types
})

# Document types that carry an expiry date printed on the physical document.
# All document types are included EXCEPT formation/company documents that don't expire.
# Used to enforce expiry date capture during upload and enable compliance tracking.
NO_EXPIRY_DOCUMENT_TYPES: set[DocumentType] = {
    DocumentType.COMPANY_PROFILE,
    DocumentType.CERTIFICATE_OF_INCORPORATION,
    DocumentType.CR14_OR_CR6,
    DocumentType.EVALUATION_FORM,
}

EXPIRY_REQUIRED_DOCUMENT_TYPES: list[DocumentType] = [
    dt for dt in DocumentType if dt not in NO_EXPIRY_DOCUMENT_TYPES
]

# Human-readable display names for sustainability/QC document types.
SUSTAINABILITY_DOC_DISPLAY_NAMES: dict[DocumentType, str] = {
    DocumentType.FOOD_SAFETY_CERTIFICATION: "Food Safety Certification",
    DocumentType.GOOD_AGRICULTURAL_PRACTICES: "Good Agricultural Practices (GAP)",
    DocumentType.ISO_14000: "ISO 14000 (Environmental Management)",
    DocumentType.ISO_45000: "ISO 45000 (Occupational Health & Safety)",
    DocumentType.INDUSTRY_CERTIFICATION: "Industry Certification",
}
