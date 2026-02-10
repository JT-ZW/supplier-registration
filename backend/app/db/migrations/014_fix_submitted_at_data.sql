-- Migration: Fix submitted_at and ensure data consistency
-- Date: 2026-02-09
-- Description: Backfills submitted_at for submitted suppliers and adds trigger

-- ============================================================
-- 1. Backfill submitted_at for suppliers with SUBMITTED status
-- ============================================================
-- Set submitted_at to created_at for suppliers that are SUBMITTED but don't have submitted_at
UPDATE suppliers
SET submitted_at = created_at
WHERE status IN ('SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED')
  AND submitted_at IS NULL;

-- ============================================================
-- 2. Create trigger to automatically set submitted_at
-- ============================================================
CREATE OR REPLACE FUNCTION set_submitted_at_on_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- When status changes TO SUBMITTED (from INCOMPLETE or NEED_MORE_INFO)
    -- and submitted_at is not yet set
    IF NEW.status = 'SUBMITTED' 
       AND OLD.status IN ('INCOMPLETE', 'NEED_MORE_INFO')
       AND NEW.submitted_at IS NULL THEN
        NEW.submitted_at = CURRENT_TIMESTAMP;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing trigger if it exists
DROP TRIGGER IF EXISTS trigger_set_submitted_at ON suppliers;

-- Create the trigger
CREATE TRIGGER trigger_set_submitted_at
    BEFORE UPDATE ON suppliers
    FOR EACH ROW
    EXECUTE FUNCTION set_submitted_at_on_status_change();

-- ============================================================
-- 3. Set reviewed_at for approved/rejected suppliers without it
-- ============================================================
UPDATE suppliers
SET reviewed_at = COALESCE(updated_at, created_at)
WHERE status IN ('APPROVED', 'REJECTED')
  AND reviewed_at IS NULL;

-- ============================================================
-- 4. Update dashboard to show INCOMPLETE as pending review
-- ============================================================
CREATE OR REPLACE FUNCTION get_overview_stats()
RETURNS TABLE (
    total_suppliers BIGINT,
    total_approved BIGINT,
    total_pending BIGINT,
    total_rejected BIGINT,
    total_active BIGINT,
    total_inactive BIGINT,
    applications_this_month BIGINT,
    approvals_this_month BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM suppliers)::BIGINT,
        (SELECT COUNT(*) FROM suppliers WHERE status = 'APPROVED')::BIGINT,
        -- UPDATED: Include INCOMPLETE suppliers in pending review count
        (SELECT COUNT(*) FROM suppliers WHERE status IN ('INCOMPLETE', 'SUBMITTED', 'UNDER_REVIEW', 'NEED_MORE_INFO'))::BIGINT,
        (SELECT COUNT(*) FROM suppliers WHERE status = 'REJECTED')::BIGINT,
        (SELECT COUNT(*) FROM suppliers WHERE activity_status = 'ACTIVE' AND status = 'APPROVED')::BIGINT,
        (SELECT COUNT(*) FROM suppliers WHERE activity_status = 'INACTIVE' AND status = 'APPROVED')::BIGINT,
        (SELECT COUNT(*) FROM suppliers WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE))::BIGINT,
        (SELECT COUNT(*) FROM suppliers WHERE status = 'APPROVED' AND reviewed_at >= DATE_TRUNC('month', CURRENT_DATE))::BIGINT;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Verification queries (run these to check the fix)
-- ============================================================
/*
-- Check suppliers with SUBMITTED status
SELECT id, company_name, status, submitted_at, created_at
FROM suppliers
WHERE status = 'SUBMITTED'
ORDER BY created_at DESC;

-- Check dashboard stats (should now include INCOMPLETE as pending)
SELECT * FROM get_overview_stats();

-- Check suppliers pending review (INCOMPLETE + SUBMITTED + UNDER_REVIEW + NEED_MORE_INFO)
SELECT COUNT(*) as pending_reviews
FROM suppliers
WHERE status IN ('INCOMPLETE', 'SUBMITTED', 'UNDER_REVIEW', 'NEED_MORE_INFO');
*/
