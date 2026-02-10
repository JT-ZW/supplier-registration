"""
Profile field permissions and validation for vendor profile changes.
Defines which fields can be updated directly vs requiring admin approval.
"""

from typing import Set, Dict, Any
from enum import Enum


class FieldPermissionLevel(str, Enum):
    """Permission levels for profile fields."""
    DIRECT = "direct"  # Vendor can update directly
    APPROVAL_REQUIRED = "approval_required"  # Requires admin approval
    READ_ONLY = "read_only"  # Cannot be changed


# Fields that vendors can update directly (immediate effect)
# These are low-risk fields that don't affect company identity or financials
DIRECT_UPDATE_FIELDS: Set[str] = {
    "contact_person_name",
    "contact_person_title",
    "phone",
    "website",
    "street_address",
    "city",
    "state_province",
    "postal_code",
    "country",
}

# Fields that require admin approval before changes take effect
# These are high-risk fields that affect company identity, legal info, or financials
APPROVAL_REQUIRED_FIELDS: Set[str] = {
    "company_name",
    "email",
    "tax_id",
    "registration_number",
    "business_category",
    "years_in_business",
}

# Fields that cannot be changed by vendors
# These are system-managed fields
READ_ONLY_FIELDS: Set[str] = {
    "id",
    "status",
    "activity_status",
    "created_at",
    "updated_at",
    "submitted_at",
    "reviewed_at",
    "reviewed_by",
    "admin_notes",
    "rejection_reason",
    "info_request_message",
}


def get_field_permission(field_name: str) -> FieldPermissionLevel:
    """
    Get the permission level for a specific field.
    
    Args:
        field_name: Name of the field
        
    Returns:
        FieldPermissionLevel enum value
    """
    if field_name in DIRECT_UPDATE_FIELDS:
        return FieldPermissionLevel.DIRECT
    elif field_name in APPROVAL_REQUIRED_FIELDS:
        return FieldPermissionLevel.APPROVAL_REQUIRED
    else:
        return FieldPermissionLevel.READ_ONLY


def separate_changes_by_permission(
    requested_changes: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Separate requested changes into direct updates and approval-required changes.
    
    Args:
        requested_changes: Dictionary of field names to new values
        
    Returns:
        Dictionary with 'direct', 'approval_required', and 'rejected' keys
    """
    result = {
        "direct": {},
        "approval_required": {},
        "rejected": {},
    }
    
    for field, value in requested_changes.items():
        permission = get_field_permission(field)
        
        if permission == FieldPermissionLevel.DIRECT:
            result["direct"][field] = value
        elif permission == FieldPermissionLevel.APPROVAL_REQUIRED:
            result["approval_required"][field] = value
        else:  # READ_ONLY
            result["rejected"][field] = value
    
    return result


def validate_field_permissions(
    requested_changes: Dict[str, Any]
) -> tuple[bool, str, Dict[str, Any]]:
    """
    Validate that all requested changes are allowed.
    
    Args:
        requested_changes: Dictionary of field names to new values
        
    Returns:
        Tuple of (is_valid, error_message, categorized_changes)
    """
    categorized = separate_changes_by_permission(requested_changes)
    
    # Check if any read-only fields were requested
    if categorized["rejected"]:
        rejected_fields = ", ".join(categorized["rejected"].keys())
        return False, f"Cannot modify read-only fields: {rejected_fields}", categorized
    
    # Check if there are any valid changes
    if not categorized["direct"] and not categorized["approval_required"]:
        return False, "No valid fields to update", categorized
    
    return True, "", categorized
