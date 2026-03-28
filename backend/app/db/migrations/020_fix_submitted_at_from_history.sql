-- Migration: Fix submitted_at dates using status history
-- Date: 2026-02-11
-- Description: Accurately sets submitted_at for all suppliers using status history

-- ============================================================
-- Fix submitted_at using actual status history
-- ============================================================

-- Update submitted_at for suppliers using their status history
UPDATE suppliers s
SET submitted_at = subquery.submission_time
FROM (
    SELECT 
        ssh.supplier_id,
        MIN(ssh.created_at) as submission_time
    FROM supplier_status_history ssh
    WHERE ssh.new_status = 'SUBMITTED'
    GROUP BY ssh.supplier_id
) subquery
WHERE s.id = subquery.supplier_id
  AND s.status IN ('SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED')
  AND (s.submitted_at IS NULL OR s.submitted_at > subquery.submission_time);

-- ============================================================
-- Fallback: For suppliers without status history
-- ============================================================

-- For APPROVED or REJECTED suppliers without submitted_at, 
-- use reviewed_at (if exists) or created_at as fallback
UPDATE suppliers
SET submitted_at = COALESCE(reviewed_at, created_at)
WHERE status IN ('APPROVED', 'REJECTED')
  AND submitted_at IS NULL;

-- For SUBMITTED or UNDER_REVIEW suppliers without submitted_at,
-- use created_at as fallback (they must have been submitted at some point)
UPDATE suppliers
SET submitted_at = created_at  
WHERE status IN ('SUBMITTED', 'UNDER_REVIEW')
  AND submitted_at IS NULL;

-- ============================================================
-- Verification Queries
-- ============================================================

-- Check results - all non-INCOMPLETE suppliers should have submitted_at
SELECT 
    status,
    COUNT(*) as total,
    COUNT(submitted_at) as with_submitted_at,
    COUNT(*) - COUNT(submitted_at) as missing_submitted_at
FROM suppliers
WHERE status != 'INCOMPLETE'
GROUP BY status
ORDER BY status;

-- Show suppliers with their submission dates
SELECT 
    company_name,
    status,
    created_at,
    submitted_at,
    reviewed_at,
    CASE 
        WHEN submitted_at IS NOT NULL THEN 
            EXTRACT(DAY FROM (submitted_at - created_at)) || ' days after creation'
        ELSE 'Not submitted'
    END as submission_delay
FROM suppliers
WHERE status IN ('APPROVED', 'REJECTED', 'SUBMITTED', 'UNDER_REVIEW')
ORDER BY submitted_at DESC NULLS LAST
LIMIT 20;

-- Check if submitted_at is before created_at (data quality check)
SELECT 
    id,
    company_name,
    created_at,
    submitted_at,
    status
FROM suppliers
WHERE submitted_at < created_at
ORDER BY company_name;
