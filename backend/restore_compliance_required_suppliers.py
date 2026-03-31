"""
Re-evaluate all COMPLIANCE_REQUIRED (and SUSPENDED) suppliers under the updated
suspension policy:

  OLD policy:  expired category docs   => COMPLIANCE_REQUIRED  (knocked off approved list)
  NEW policy:  expired category docs   => APPROVED             (stay on approved list)
              expired STATUTORY docs  => SUSPENDED
              missing/unverified statutory docs => COMPLIANCE_REQUIRED

This script re-runs recompute_supplier_portfolio_status for every supplier
currently in COMPLIANCE_REQUIRED or SUSPENDED so the DB reflects the new rules.

Run from the backend directory:
    cd backend
    python restore_compliance_required_suppliers.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import Database


async def main() -> None:
    db = Database()

    # Fetch all suppliers currently in COMPLIANCE_REQUIRED or SUSPENDED
    result = (
        db._client.table("suppliers")
        .select("id, company_name, email, status")
        .in_("status", ["COMPLIANCE_REQUIRED", "SUSPENDED"])
        .execute()
    )
    suppliers = result.data or []

    print(f"\n{'=' * 70}")
    print("RE-EVALUATE COMPLIANCE_REQUIRED / SUSPENDED SUPPLIERS")
    print(f"{'=' * 70}")
    print(f"Found {len(suppliers)} supplier(s) to re-evaluate...\n")

    promoted_to_approved = []
    stayed_compliance = []
    stayed_suspended = []
    legitimately_suspended = []
    errors = []

    for s in suppliers:
        sid = s["id"]
        name = s.get("company_name", sid)
        old_status = s.get("status", "")
        try:
            result = await db.recompute_supplier_portfolio_status(sid)
            new_status = result.get("new_status", old_status)
            reason = result.get("reason", "")

            if new_status == "APPROVED" and old_status != "APPROVED":
                promoted_to_approved.append((name, old_status, reason))
                print(f"  ✅ PROMOTED  {name}  {old_status} → APPROVED  ({reason})")
            elif new_status == "SUSPENDED" and old_status != "SUSPENDED":
                legitimately_suspended.append((name, reason))
                print(f"  🚫 SUSPENDED {name}  → SUSPENDED  ({reason})")
            elif new_status == "COMPLIANCE_REQUIRED":
                stayed_compliance.append((name, reason))
                print(f"  ⚠️  UNCHANGED {name}  → COMPLIANCE_REQUIRED  ({reason})")
            elif new_status == "SUSPENDED":
                stayed_suspended.append((name, reason))
                print(f"  🚫 UNCHANGED {name}  → SUSPENDED  ({reason})")
            else:
                print(f"  — {name}  {old_status} → {new_status}  ({reason})")
        except Exception as e:
            errors.append((name, str(e)))
            print(f"  ❌ ERROR     {name}  — {e}")

    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Promoted to APPROVED:      {len(promoted_to_approved)}")
    print(f"  Remain COMPLIANCE_REQUIRED:{len(stayed_compliance)}")
    print(f"  Remain SUSPENDED:          {len(stayed_suspended)}")
    print(f"  Newly SUSPENDED (legit):   {len(legitimately_suspended)}")
    print(f"  Errors:                    {len(errors)}")
    print(f"{'=' * 70}\n")

    if errors:
        print("Errors detail:")
        for name, err in errors:
            print(f"  {name}: {err}")


if __name__ == "__main__":
    asyncio.run(main())
