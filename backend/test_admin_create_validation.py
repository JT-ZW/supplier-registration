"""
Test script to validate admin user creation data.
This helps diagnose the 422 validation error.
"""

from pydantic import ValidationError
from app.models.user_management import AdminUserCreateRequest
from app.models.enums import AdminRole
import json

# Test data matching the frontend formData structure
test_data = {
    "email": "test@example.com",
    "password": "TestPass123",  # Meets all requirements
    "full_name": "Test User",
    "role": "PROCUREMENT_MANAGER",
    "phone": "",
    "department": "",
    "position": "",
    "must_change_password": True,
}

print("=" * 60)
print("Testing Admin User Creation Validation")
print("=" * 60)
print(f"\nTest Data:\n{json.dumps(test_data, indent=2)}\n")

try:
    # Try to create the model
    request = AdminUserCreateRequest(**test_data)
    print("✅ Validation PASSED!")
    print(f"\nValidated model:\n{request.model_dump_json(indent=2)}")
except ValidationError as e:
    print("❌ Validation FAILED!")
    print(f"\nValidation Errors:")
    for error in e.errors():
        print(f"  - Field: {error['loc']}")
        print(f"    Type: {error['type']}")
        print(f"    Message: {error['msg']}")
        if 'input' in error:
            print(f"    Input: {error['input']}")
        print()

print("\n" + "=" * 60)
print("Testing with empty optional fields removed")
print("=" * 60)

# Try without empty strings
test_data_2 = {
    "email": "test@example.com",
    "password": "TestPass123",
    "full_name": "Test User",
    "role": "PROCUREMENT_MANAGER",
    "must_change_password": True,
}

print(f"\nTest Data:\n{json.dumps(test_data_2, indent=2)}\n")

try:
    request = AdminUserCreateRequest(**test_data_2)
    print("✅ Validation PASSED!")
    print(f"\nValidated model:\n{request.model_dump_json(indent=2)}")
except ValidationError as e:
    print("❌ Validation FAILED!")
    print(f"\nValidation Errors:")
    for error in e.errors():
        print(f"  - Field: {error['loc']}")
        print(f"    Type: {error['type']}")
        print(f"    Message: {error['msg']}")
        if 'input' in error:
            print(f"    Input: {error['input']}")
        print()
