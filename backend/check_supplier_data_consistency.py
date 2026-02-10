"""
Script to check and fix supplier data consistency issues.
Identifies problems with submitted_at, status, and dashboard stats.
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import db

print("=" * 80)
print("SUPPLIER DATA CONSISTENCY CHECK")
print("=" * 80)

# 1. Check suppliers by status
print("\n1. SUPPLIERS BY STATUS")
print("-" * 80)

suppliers = db.client.table("suppliers")\
    .select("id, company_name, status, submitted_at, reviewed_at, created_at")\
    .order("created_at", desc=True)\
    .execute()

status_counts = {}
for supplier in suppliers.data:
    status = supplier["status"]
    status_counts[status] = status_counts.get(status, 0) + 1
    
for status, count in sorted(status_counts.items()):
    print(f"   {status:20s}: {count:3d} suppliers")

# 2. Check submitted suppliers without submitted_at
print("\n2. DATA QUALITY ISSUES")
print("-" * 80)

submitted_no_date = [s for s in suppliers.data 
                      if s["status"] in ("SUBMITTED", "UNDER_REVIEW", "APPROVED", "REJECTED") 
                      and not s.get("submitted_at")]

if submitted_no_date:
    print(f"   ⚠️  {len(submitted_no_date)} suppliers with status {', '.join(set(s['status'] for s in submitted_no_date))} but NO submitted_at:")
    for s in submitted_no_date[:5]:  # Show first 5
        print(f"       - {s['company_name']} (ID: {s['id'][:8]}..., Status: {s['status']})")
    if len(submitted_no_date) > 5:
        print(f"       ... and {len(submitted_no_date) - 5} more")
else:
    print("   ✅ All submitted suppliers have submitted_at timestamps")

# 3. Check dashboard stats
print("\n3. DASHBOARD STATISTICS")
print("-" * 80)

try:
    stats = db.client.rpc("get_overview_stats").execute()
    if stats.data:
        stat = stats.data[0]
        print(f"   Total Suppliers:       {stat['total_suppliers']}")
        print(f"   Approved:              {stat['total_approved']}")
        print(f"   Pending Review:        {stat['total_pending']}")
        print(f"   Rejected:              {stat['total_rejected']}")
        print(f"   Active:                {stat['total_active']}")
        print(f"   Inactive:              {stat['total_inactive']}")
        print(f"   Applications this mo:  {stat['applications_this_month']}")
        print(f"   Approvals this month:  {stat['approvals_this_month']}")
except Exception as e:
    print(f"   ❌ Error getting stats: {str(e)}")

# 4. Manually count pending reviews
pending_statuses = ['SUBMITTED', 'UNDER_REVIEW', 'NEED_MORE_INFO']
pending_count = sum(1 for s in suppliers.data if s['status'] in pending_statuses)
print(f"\n   Manual count of pending reviews: {pending_count}")

# 5. Show suppliers that should be "pending" on dashboard
if pending_count > 0:
    print(f"\n   Pending suppliers (should show on dashboard):")
    for s in suppliers.data:
        if s['status'] in pending_statuses:
            submitted_str = s['submitted_at'] if s.get('submitted_at') else 'NOT SET'
            print(f"       - {s['company_name'][:30]:30s} | Status: {s['status']:15s} | Submitted: {submitted_str}")

print("\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)

if submitted_no_date:
    print("\n   🔧 Run the migration SQL to fix submitted_at:")
    print("      File: backend/app/db/migrations/014_fix_submitted_at_data.sql")
    print("      This will backfill submitted_at for all affected suppliers")
else:
    print("\n   ✅ No data fixes needed")

if pending_count > 0:
    print(f"\n   ✅ Dashboard should show {pending_count} pending review(s)")
    print("      If it shows 0, try refreshing the page or check browser console for errors")
else:
    print("\n   ℹ️  No suppliers pending review")

print("\n" + "=" * 80)
