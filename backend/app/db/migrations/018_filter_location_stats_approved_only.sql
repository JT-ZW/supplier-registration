-- Migration: Filter location stats to show approved suppliers only
-- Date: 2026-02-10
-- Description: Updates location stats functions to only count approved suppliers, reducing dashboard clutter

-- ============================================================
-- Drop existing functions
-- ============================================================
DROP FUNCTION IF EXISTS get_location_stats();
DROP FUNCTION IF EXISTS get_location_stats_by_country();

-- ============================================================
-- 1. Create function for country-level location statistics (APPROVED ONLY)
-- ============================================================
CREATE OR REPLACE FUNCTION get_location_stats_by_country()
RETURNS TABLE (
    location VARCHAR,
    count BIGINT,
    approved_count BIGINT,
    pending_count BIGINT,
    percentage NUMERIC
) AS $$
DECLARE
    total_count BIGINT;
BEGIN
    -- Count only approved suppliers for percentage calculation
    SELECT COUNT(*) INTO total_count FROM suppliers WHERE status = 'APPROVED';
    
    RETURN QUERY
    SELECT 
        s.country::VARCHAR as location,
        COUNT(*)::BIGINT as count,
        COUNT(*)::BIGINT as approved_count,  -- All are approved since we filter
        0::BIGINT as pending_count,          -- No pending since we only show approved
        ROUND((COUNT(*)::NUMERIC / NULLIF(total_count, 0) * 100), 2) as percentage
    FROM suppliers s
    WHERE s.country IS NOT NULL 
        AND s.country != ''
        AND s.status = 'APPROVED'  -- Only approved suppliers
    GROUP BY s.country
    ORDER BY count DESC
    LIMIT 15;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 2. Update city-level location stats (APPROVED ONLY)
-- ============================================================
CREATE OR REPLACE FUNCTION get_location_stats()
RETURNS TABLE (
    location VARCHAR,
    count BIGINT,
    approved_count BIGINT,
    pending_count BIGINT,
    percentage NUMERIC
) AS $$
DECLARE
    total_count BIGINT;
BEGIN
    -- Count only approved suppliers for percentage calculation
    SELECT COUNT(*) INTO total_count FROM suppliers WHERE status = 'APPROVED';
    
    RETURN QUERY
    SELECT 
        s.city::VARCHAR as location,
        COUNT(*)::BIGINT as count,
        COUNT(*)::BIGINT as approved_count,  -- All are approved since we filter
        0::BIGINT as pending_count,          -- No pending since we only show approved
        ROUND((COUNT(*)::NUMERIC / NULLIF(total_count, 0) * 100), 2) as percentage
    FROM suppliers s
    WHERE s.city IS NOT NULL 
        AND s.city != ''
        AND s.status = 'APPROVED'  -- Only approved suppliers
    GROUP BY s.city
    ORDER BY count DESC
    LIMIT 15;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Verification queries
-- ============================================================
/*
-- Test country-level stats (should only show approved)
SELECT * FROM get_location_stats_by_country();

-- Test city-level stats (should only show approved)
SELECT * FROM get_location_stats();

-- Verify counts match approved suppliers only
SELECT city, COUNT(*) 
FROM suppliers 
WHERE status = 'APPROVED' AND city IS NOT NULL AND city != ''
GROUP BY city
ORDER BY COUNT(*) DESC
LIMIT 5;
*/
