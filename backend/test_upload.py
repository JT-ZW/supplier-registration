"""
Test document upload functionality directly.
"""
import requests
import json
import uuid

# Configuration
API_BASE_URL = "http://localhost:8000/v1"

# Generate unique email
unique_email = f"test{str(uuid.uuid4())[:8]}@example.com"

# First, create a supplier
print("1️⃣ Creating test supplier...")
supplier_data = {
    "companyName": "Test Company",
    "businessCategory": "CONSTRUCTION",
    "registrationNumber": "REG123456",
    "taxId": "TAX123456",
    "yearsInBusiness": 5,
    "contactPersonName": "John Doe",
    "contactPersonTitle": "Manager",
    "email": unique_email,
    "phone": "+1234567890",
    "streetAddress": "123 Test St",
    "city": "Test City",
    "stateProvince": "Test State",
    "postalCode": "12345",
    "country": "Test Country"
}

response = requests.post(f"{API_BASE_URL}/supplier/register", json=supplier_data)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:200]}")

if response.status_code != 201:
    print("❌ Failed to create supplier")
    exit(1)

supplier_id = response.json()["id"]
print(f"✅ Supplier created: {supplier_id}")

# Now test getting upload URL
print("\n2️⃣ Testing document upload URL generation...")
upload_request = {
    "supplierId": supplier_id,
    "documentType": "COMPANY_PROFILE",
    "fileName": "test-document.pdf",
    "fileSize": 18021,
    "contentType": "application/pdf"
}

print(f"Request data: {json.dumps(upload_request, indent=2)}")

response = requests.post(f"{API_BASE_URL}/documents/upload-url", json=upload_request)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code == 200:
    print("✅ Upload URL generated successfully!")
    data = response.json()
    print(f"   Upload URL: {data.get('upload_url', 'N/A')[:50]}...")
    print(f"   File path: {data.get('file_key', 'N/A')}")
else:
    print(f"❌ Failed: {response.status_code}")
    print(f"   Error: {response.text}")
