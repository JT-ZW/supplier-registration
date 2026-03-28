-- Migration 035: Fix supplier_status_history check constraint
-- Run this in the Supabase SQL Editor
--
-- Problem: The check_status_values constraint was created in migration 009,
-- before COMPLIANCE_REQUIRED (added in 026) and SUSPENDED (added in 030)
-- were introduced as valid statuses. Any transition that involves
-- COMPLIANCE_REQUIRED as old_status or new_status causes a 23514 constraint
-- violation, breaking:
--   • Auto-restore via restore_suspended_supplier RPC
--   • Manual approve via /review endpoint
--   • Manual unsuspend via /unsuspend endpoint
--
-- The original constraint also had an AND/OR precedence bug:
--   old_status IN (...) OR old_status IS NULL AND new_status IN (...)
-- parses as:
--   old_status IN (...) OR (old_status IS NULL AND new_status IN (...))
-- which accidentally allows ANY old_status value (the OR short-circuits).
-- The corrected form properly parenthesises both branches.

-- Step 1: Drop the broken constraint.
ALTER TABLE supplier_status_history
    DROP CONSTRAINT IF EXISTS check_status_values;

-- Step 2: Recreate with COMPLIANCE_REQUIRED included and correct parentheses.
ALTER TABLE supplier_status_history
    ADD CONSTRAINT check_status_values CHECK (
        (
            old_status IS NULL
            OR old_status IN (
                'INCOMPLETE',
                'SUBMITTED',
                'UNDER_REVIEW',
                'NEED_MORE_INFO',
                'APPROVED',
                'REJECTED',
                'SUSPENDED',
                'COMPLIANCE_REQUIRED'
            )
        )
        AND new_status IN (
            'INCOMPLETE',
            'SUBMITTED',
            'UNDER_REVIEW',
            'NEED_MORE_INFO',
            'APPROVED',
            'REJECTED',
            'SUSPENDED',
            'COMPLIANCE_REQUIRED'
        )
    );
