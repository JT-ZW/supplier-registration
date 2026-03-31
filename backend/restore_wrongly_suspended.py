"""
Restore suppliers that were incorrectly auto-suspended by the sustainability
maintenance bug (recompute_category_compliance_for_suppliers was calling
recompute_supplier_portfolio_status, suspending suppliers whose docs were
merely unverified/pending rather than expired).

With the fixed logic:
  - No expired statutory docs  => COMPLIANCE_REQUIRED (not SUSPENDED)
  - Has expired statutory docs  => stays SUSPENDED (legitimate)
  - All statutory docs verified => restored to APPROVED

Run AFTER deploying the supabase.py fix:
    cd backend
    python restore_wrongly_suspended.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.db.supabase import Database


async def main() -> None:
    db = Database()

    # Find all currently SUSPENDED suppliers
    result = db._client.table("suppliers").select(
        "id, company_name, email, status, suspension_reason, suspended_at"
    ).eq("status", "SUSPENDED").execute()

    suspended = result.data or []
    print(f"\n{'=' * 70}")
    print(f"RESTORE WRONGLY-SUSPENDED SUPPLIERS")
    print(f"{'=' * 70}")
    print(f"Found {len(suspended)} SUSPENDED supplier(s). Re-evaluating...\n")

    restored_to_approved = []
    restored_to_compliance = []
    remained_suspended = []
    errors = []

    for supplier in suspended:
        supplier_id = supplier["id"]
        company = supplier.get("company_name", supplier.get("email", supplier_id))
        try:
            result = await db.recompute_supplier_portfolio_status(supplier_id)
            new_status = result.get("new_status", "UNKNOWN")
            changed = result.get("changed", False)
            reason = result.get("reason", "")

            if not changed:
                remained_suspended.append((company, reason))
                print(f"  [SUSPENDED]          {company} — {reason}")
            elif new_status == "APPROVED":
                restored_to_approved.append(company)
                print(f"  [RESTORED → APPROVED]          {company}")
            elif new_status == "COMPLIANCE_REQUIRED":
                restored_to_compliance.append(company)
                print(f"  [RESTORED → COMPLIANCE_REQUIRED] {company} — {reason}")
            else:
                remained_suspended.append((company, reason))
                print(f"  [SUSPENDED → {new_status}]  {company} — {reason}")
        except Exception as exc:
            errors.append((company, str(exc)))
            print(f"  [ERROR] {company} — {exc}")

    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Restored to APPROVED:            {len(restored_to_approved)}")
    print(f"  Restored to COMPLIANCE_REQUIRED: {len(restored_to_compliance)}")
    print(f"  Legitimately remained SUSPENDED: {len(remained_suspended)}")
    print(f"  Errors:                          {len(errors)}")
    print(f"{'=' * 70}\n")

    if errors:
        print("Errors encountered:")
        for company, msg in errors:
            print(f"  - {company}: {msg}")


if __name__ == "__main__":
    asyncio.run(main())
