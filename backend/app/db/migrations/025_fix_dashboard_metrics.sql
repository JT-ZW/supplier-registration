-- Migration: Fix dashboard Pending Review / Under Review metrics
-- Date: 2026-03-03
--
-- Description:
--   Aligns the get_overview_stats() RPC with the new workflow:
--
--     Pending Review  = SUBMITTED only
--                       (supplier submitted; no admin has opened the application yet)
--
--     Under Review    = UNDER_REVIEW only
--                       (admin opened the application — review is in progress)
--
--   Previously total_pending included INCOMPLETE, SUBMITTED, UNDER_REVIEW and
--   NEED_MORE_INFO, which caused the two dashboard cards to overlap and be
--   misleading.
--
--   The total_pending column is reused for "Under Review" to avoid a schema
--   change; its semantics now mirror UNDER_REVIEW status exactly.

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
        -- All registered suppliers
        (SELECT COUNT(*) FROM suppliers)::BIGINT,

        -- Fully approved
        (SELECT COUNT(*) FROM suppliers WHERE status = 'APPROVED')::BIGINT,

        -- Under Review: admin has opened the application; review is actively in progress
        (SELECT COUNT(*) FROM suppliers WHERE status = 'UNDER_REVIEW')::BIGINT,

        -- Rejected
        (SELECT COUNT(*) FROM suppliers WHERE status = 'REJECTED')::BIGINT,

        -- Active approved suppliers
        (SELECT COUNT(*) FROM suppliers
         WHERE activity_status = 'ACTIVE' AND status = 'APPROVED')::BIGINT,

        -- Inactive approved suppliers
        (SELECT COUNT(*) FROM suppliers
         WHERE activity_status = 'INACTIVE' AND status = 'APPROVED')::BIGINT,

        -- New registrations this calendar month
        (SELECT COUNT(*) FROM suppliers
         WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE))::BIGINT,

        -- Approvals this calendar month
        (SELECT COUNT(*) FROM suppliers
         WHERE status = 'APPROVED'
           AND reviewed_at >= DATE_TRUNC('month', CURRENT_DATE))::BIGINT;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Verification queries (run these after applying the migration)
-- ============================================================
/*
-- Pending Review: submitted but not yet opened by an admin
SELECT COUNT(*) AS pending_review
FROM suppliers
WHERE status = 'SUBMITTED';

-- Under Review: admin has opened / is actively reviewing
SELECT COUNT(*) AS under_review
FROM suppliers
WHERE status = 'UNDER_REVIEW';

-- Full overview check
SELECT * FROM get_overview_stats();
*/
