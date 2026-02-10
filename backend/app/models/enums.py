"""
Enum definitions for the application.
Using string enums for database compatibility.
"""

from enum import Enum


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


class SupplierActivityStatus(str, Enum):
    """Activity status for approved suppliers."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class BusinessCategory(str, Enum):
    """Business categories for suppliers."""
    CONSTRUCTION = "CONSTRUCTION"
    MANUFACTURING = "MANUFACTURING"
    FOOD_BEVERAGE = "FOOD_BEVERAGE"
    HEALTHCARE = "HEALTHCARE"
    IT_SERVICES = "IT_SERVICES"
    LOGISTICS = "LOGISTICS"
    CONSULTING = "CONSULTING"
    CLEANING_SERVICES = "CLEANING_SERVICES"
    SECURITY_SERVICES = "SECURITY_SERVICES"
    GENERAL_SUPPLIES = "GENERAL_SUPPLIES"
    OTHER = "OTHER"


class DocumentType(str, Enum):
    """Types of documents that can be uploaded."""
    # Mandatory documents
    COMPANY_PROFILE = "COMPANY_PROFILE"
    CERTIFICATE_OF_INCORPORATION = "CERTIFICATE_OF_INCORPORATION"
    CR14_OR_CR6 = "CR14_OR_CR6"
    VAT_CERTIFICATE = "VAT_CERTIFICATE"
    TAX_CLEARANCE = "TAX_CLEARANCE"
    FDMS_COMPLIANCE = "FDMS_COMPLIANCE"
    
    # Category-specific documents
    HEALTH_CERTIFICATE = "HEALTH_CERTIFICATE"
    ISO_9001 = "ISO_9001"
    ISO_45001 = "ISO_45001"
    ISO_14000 = "ISO_14000"
    INTERNAL_QMS = "INTERNAL_QMS"
    SHEQ_POLICY = "SHEQ_POLICY"
    
    # Admin-uploaded documents
    EVALUATION_FORM = "EVALUATION_FORM"  # Supplier evaluation form uploaded by admin


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


# Define which documents are mandatory for all suppliers
MANDATORY_DOCUMENTS = [
    DocumentType.COMPANY_PROFILE,
    DocumentType.CERTIFICATE_OF_INCORPORATION,
    DocumentType.CR14_OR_CR6,
    DocumentType.VAT_CERTIFICATE,
    DocumentType.TAX_CLEARANCE,
    DocumentType.FDMS_COMPLIANCE,
]

# Define category-specific document requirements
CATEGORY_DOCUMENTS = {
    BusinessCategory.FOOD_BEVERAGE: [
        DocumentType.HEALTH_CERTIFICATE,
        DocumentType.ISO_9001,
    ],
    BusinessCategory.HEALTHCARE: [
        DocumentType.HEALTH_CERTIFICATE,
        DocumentType.ISO_9001,
        DocumentType.ISO_45001,
    ],
    BusinessCategory.MANUFACTURING: [
        DocumentType.ISO_9001,
        DocumentType.ISO_14000,
        DocumentType.ISO_45001,
    ],
    BusinessCategory.CONSTRUCTION: [
        DocumentType.ISO_45001,
        DocumentType.ISO_14000,
        DocumentType.SHEQ_POLICY,
    ],
    BusinessCategory.CLEANING_SERVICES: [
        DocumentType.HEALTH_CERTIFICATE,
        DocumentType.SHEQ_POLICY,
    ],
    BusinessCategory.SECURITY_SERVICES: [
        DocumentType.INTERNAL_QMS,
    ],
    # Categories with only mandatory documents
    BusinessCategory.IT_SERVICES: [],
    BusinessCategory.LOGISTICS: [],
    BusinessCategory.CONSULTING: [],
    BusinessCategory.GENERAL_SUPPLIES: [],
    BusinessCategory.OTHER: [],
}


def get_required_documents(category: BusinessCategory) -> list[DocumentType]:
    """
    Get all required documents for a given business category.
    Returns mandatory documents plus category-specific documents.
    """
    category_specific = CATEGORY_DOCUMENTS.get(category, [])
    return MANDATORY_DOCUMENTS + category_specific
