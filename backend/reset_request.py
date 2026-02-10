"""Reset the test request back to PENDING so user can test approval again."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import db

request_id = "382e3324-7eeb-4042-828b-185c4a3e5191"

# Reset to PENDING
result = db.client.table("profile_change_requests")\
    .update({
        "status": "PENDING",
        "reviewed_by": None,
        "reviewed_at": None,
        "review_notes": None
    })\
    .eq("id", request_id)\
    .execute()

print("✅ Profile change request reset to PENDING")
print(f"   Request ID: {request_id}")
print("\nYou can now:")
print("1. Run the SQL fix in Supabase SQL Editor (see SQL_FIX_TO_RUN.txt)")
print("2. Try approving the request again in the admin UI")
print("3. The business_category should change from CLEANING_SERVICES to GENERAL_SUPPLIES")
