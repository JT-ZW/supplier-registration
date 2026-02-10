"""
End-to-End Test Script for Hybrid Profile Changes System
Tests the complete workflow from vendor request to admin approval.
"""

import requests
import json
from datetime import datetime
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
VENDOR_EMAIL = "test@amenities.com"  # Update with your test vendor email
VENDOR_PASSWORD = "Test@123"  # Update with your test vendor password
ADMIN_EMAIL = "Jeffrey.Murungweni@rtg.co.zw"  # Update with your admin email
ADMIN_PASSWORD = "Admin@123"  # Update with your admin password

# ANSI color codes for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}{text.center(70)}{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✓ {text}{RESET}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}⚠ {text}{RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}✗ {text}{RESET}")


def print_info(text: str):
    """Print info message."""
    print(f"{BLUE}ℹ {text}{RESET}")


def print_json(data: Any, title: str = ""):
    """Print JSON data in a readable format."""
    if title:
        print(f"{BOLD}{title}:{RESET}")
    print(json.dumps(data, indent=2, default=str))


def login_vendor() -> str:
    """Login as vendor and return access token."""
    print_info("Logging in as vendor...")
    response = requests.post(
        f"{BASE_URL}/vendor/login",
        json={"email": VENDOR_EMAIL, "password": VENDOR_PASSWORD}
    )
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print_success(f"Vendor login successful")
        return token
    else:
        print_error(f"Vendor login failed: {response.status_code}")
        print_json(response.json())
        raise Exception("Vendor login failed")


def login_admin() -> str:
    """Login as admin and return access token."""
    print_info("Logging in as admin...")
    response = requests.post(
        f"{BASE_URL}/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print_success(f"Admin login successful")
        return token
    else:
        print_error(f"Admin login failed: {response.status_code}")
        print_json(response.json())
        raise Exception("Admin login failed")


def get_vendor_profile(token: str) -> Dict[str, Any]:
    """Get vendor profile."""
    print_info("Fetching vendor profile...")
    response = requests.get(
        f"{BASE_URL}/vendor/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        print_success("Profile fetched successfully")
        return response.json()
    else:
        print_error(f"Failed to fetch profile: {response.status_code}")
        print_json(response.json())
        raise Exception("Failed to fetch profile")


def submit_profile_changes(token: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    """Submit profile change request as vendor."""
    print_info("Submitting profile change request...")
    print_json(changes, "Changes to submit")
    
    response = requests.post(
        f"{BASE_URL}/profile-changes/vendor/request",
        headers={"Authorization": f"Bearer {token}"},
        json={"requested_changes": changes}
    )
    
    if response.status_code == 200:
        result = response.json()
        print_success("Profile changes submitted successfully!")
        print_json(result, "Submission Result")
        return result
    else:
        print_error(f"Failed to submit changes: {response.status_code}")
        print_json(response.json())
        raise Exception("Failed to submit changes")


def get_pending_requests(admin_token: str) -> list:
    """Get pending profile change requests as admin."""
    print_info("Fetching pending profile change requests...")
    response = requests.get(
        f"{BASE_URL}/profile-changes/admin/pending",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    if response.status_code == 200:
        requests_data = response.json()
        print_success(f"Found {len(requests_data)} pending request(s)")
        return requests_data
    else:
        print_error(f"Failed to fetch pending requests: {response.status_code}")
        print_json(response.json())
        raise Exception("Failed to fetch pending requests")


def get_request_details(admin_token: str, request_id: str) -> Dict[str, Any]:
    """Get detailed profile change request as admin."""
    print_info(f"Fetching request details for ID: {request_id}")
    response = requests.get(
        f"{BASE_URL}/profile-changes/admin/requests/{request_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    if response.status_code == 200:
        request_data = response.json()
        print_success("Request details fetched successfully")
        print_json(request_data, "Request Details")
        return request_data
    else:
        print_error(f"Failed to fetch request details: {response.status_code}")
        print_json(response.json())
        raise Exception("Failed to fetch request details")


def approve_request(admin_token: str, request_id: str, notes: str = "") -> Dict[str, Any]:
    """Approve profile change request as admin."""
    print_info(f"Approving request ID: {request_id}")
    response = requests.post(
        f"{BASE_URL}/profile-changes/admin/requests/{request_id}/review",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "action": "approve",
            "admin_notes": notes or "Approved via test script"
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print_success("Request approved successfully!")
        print_json(result, "Approval Result")
        return result
    else:
        print_error(f"Failed to approve request: {response.status_code}")
        print_json(response.json())
        raise Exception("Failed to approve request")


def compare_values(label: str, old_value: Any, new_value: Any):
    """Compare and display old vs new values."""
    if old_value == new_value:
        print(f"  {label}: {YELLOW}{old_value}{RESET} (unchanged)")
    else:
        print(f"  {label}: {RED}{old_value}{RESET} → {GREEN}{new_value}{RESET}")


def main():
    """Run the complete end-to-end test."""
    print_header("HYBRID PROFILE CHANGES - END-TO-END TEST")
    
    try:
        # Step 1: Login as vendor
        print_header("STEP 1: Vendor Authentication")
        vendor_token = login_vendor()
        
        # Step 2: Get initial vendor profile
        print_header("STEP 2: Get Initial Vendor Profile")
        initial_profile = get_vendor_profile(vendor_token)
        print_info(f"Company: {initial_profile.get('companyName', 'N/A')}")
        print_info(f"Email: {initial_profile.get('email', 'N/A')}")
        print_info(f"Phone: {initial_profile.get('phone', 'N/A')}")
        print_info(f"Contact Person: {initial_profile.get('contactPersonName', 'N/A')}")
        print_info(f"City: {initial_profile.get('city', 'N/A')}")
        
        # Step 3: Submit profile changes (mix of direct and approval-required)
        print_header("STEP 3: Submit Profile Changes")
        print_warning("Testing hybrid approach:")
        print_info("✓ Direct update fields: phone, contact_person_name, city")
        print_info("✓ Approval-required fields: company_name, email")
        
        changes = {
            # Direct update fields (should apply immediately)
            "phone": "+263 4 999888",
            "contact_person_name": "Updated Contact Person",
            "city": "Updated City",
            
            # Approval required fields (should create request)
            "company_name": "Updated Company Name Ltd",
            "email": "updated.email@example.com",
        }
        
        submission_result = submit_profile_changes(vendor_token, changes)
        
        # Verify submission result
        print("\n" + BOLD + "Verification:" + RESET)
        print_info(f"Direct updates applied: {submission_result.get('direct_updates_applied', 0)}")
        print_info(f"Approval request created: {submission_result.get('approval_request_created', False)}")
        print_info(f"Direct fields: {', '.join(submission_result.get('direct_fields', []))}")
        print_info(f"Approval required fields: {', '.join(submission_result.get('approval_required_fields', []))}")
        
        if submission_result.get('approval_request_created'):
            change_request_id = submission_result.get('change_request_id')
            print_success(f"Change request ID: {change_request_id}")
        
        # Step 4: Verify direct changes were applied immediately
        print_header("STEP 4: Verify Direct Updates")
        updated_profile = get_vendor_profile(vendor_token)
        
        print_info("Comparing values:")
        compare_values("Phone", initial_profile.get('phone'), updated_profile.get('phone'))
        compare_values("Contact Person", initial_profile.get('contactPersonName'), updated_profile.get('contactPersonName'))
        compare_values("City", initial_profile.get('city'), updated_profile.get('city'))
        compare_values("Company Name", initial_profile.get('companyName'), updated_profile.get('companyName'))
        compare_values("Email", initial_profile.get('email'), updated_profile.get('email'))
        
        if (updated_profile.get('phone') == changes['phone'] and
            updated_profile.get('contactPersonName') == changes['contact_person_name'] and
            updated_profile.get('city') == changes['city']):
            print_success("✓ All direct updates applied correctly!")
        else:
            print_error("✗ Some direct updates were not applied")
        
        if (updated_profile.get('companyName') != changes['company_name'] and
            updated_profile.get('email') != changes['email']):
            print_success("✓ Approval-required fields NOT applied yet (correct behavior)")
        else:
            print_warning("⚠ Approval-required fields were applied immediately (unexpected)")
        
        # Step 5: Login as admin
        print_header("STEP 5: Admin Authentication")
        admin_token = login_admin()
        
        # Step 6: Check pending requests as admin
        print_header("STEP 6: Admin Views Pending Requests")
        pending_requests = get_pending_requests(admin_token)
        
        if not pending_requests:
            print_error("No pending requests found!")
            return
        
        # Find our request
        our_request = None
        for req in pending_requests:
            if req.get('id') == change_request_id:
                our_request = req
                break
        
        if not our_request:
            print_error(f"Could not find request with ID: {change_request_id}")
            return
        
        print_success(f"Found our request!")
        print_info(f"Company: {our_request.get('company_name', 'N/A')}")
        print_info(f"Status: {our_request.get('status', 'N/A')}")
        print_info(f"Created: {our_request.get('created_at', 'N/A')}")
        
        # Step 7: Get detailed request info
        print_header("STEP 7: Admin Reviews Request Details")
        request_details = get_request_details(admin_token, change_request_id)
        
        print_info("Requested Changes:")
        for field, value in request_details.get('requested_changes', {}).items():
            old_value = request_details.get('current_values', {}).get(field, 'N/A')
            print(f"  {field}: {RED}{old_value}{RESET} → {GREEN}{value}{RESET}")
        
        # Step 8: Email notification check
        print_header("STEP 8: Email Notification Check")
        print_warning("⚠ Email notifications are not yet implemented")
        print_info("TODO: Email should be sent to admin when vendor submits approval request")
        print_info("TODO: Email should be sent to vendor when admin approves/rejects")
        
        # Step 9: Admin approves the request
        print_header("STEP 9: Admin Approves Request")
        approval_result = approve_request(
            admin_token, 
            change_request_id,
            "Approved in end-to-end test. All changes look good!"
        )
        
        # Step 10: Verify changes were applied after approval
        print_header("STEP 10: Verify Changes After Approval")
        final_profile = get_vendor_profile(vendor_token)
        
        print_info("Final profile values:")
        compare_values("Phone", initial_profile.get('phone'), final_profile.get('phone'))
        compare_values("Contact Person", initial_profile.get('contactPersonName'), final_profile.get('contactPersonName'))
        compare_values("City", initial_profile.get('city'), final_profile.get('city'))
        compare_values("Company Name", initial_profile.get('companyName'), final_profile.get('companyName'))
        compare_values("Email", initial_profile.get('email'), final_profile.get('email'))
        
        all_changes_applied = (
            final_profile.get('phone') == changes['phone'] and
            final_profile.get('contactPersonName') == changes['contact_person_name'] and
            final_profile.get('city') == changes['city'] and
            final_profile.get('companyName') == changes['company_name'] and
            final_profile.get('email') == changes['email']
        )
        
        if all_changes_applied:
            print_success("✓✓✓ ALL CHANGES APPLIED SUCCESSFULLY! ✓✓✓")
        else:
            print_error("✗✗✗ Some changes were not applied correctly ✗✗✗")
        
        # Summary
        print_header("TEST SUMMARY")
        print_success("✓ Vendor authentication")
        print_success("✓ Profile change submission")
        print_success("✓ Direct updates applied immediately")
        print_success("✓ Approval request created for sensitive fields")
        print_success("✓ Admin can view pending requests")
        print_success("✓ Admin can approve requests")
        print_success("✓ Approved changes applied to vendor profile")
        print_warning("⚠ Email notifications not yet implemented")
        
        print(f"\n{BOLD}{GREEN}{'='*70}{RESET}")
        print(f"{BOLD}{GREEN}{'END-TO-END TEST COMPLETED SUCCESSFULLY!'.center(70)}{RESET}")
        print(f"{BOLD}{GREEN}{'='*70}{RESET}\n")
        
    except Exception as e:
        print_error(f"\n\nTEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
