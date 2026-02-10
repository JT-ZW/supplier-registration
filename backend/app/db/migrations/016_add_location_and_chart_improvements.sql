-- Migration: Add country-level location stats and improve dashboard charts
-- Date: 2026-02-09
-- Description: Adds function for country-level supplier distribution

-- ============================================================
-- Drop existing functions (required when changing return types)
-- ============================================================
DROP FUNCTION IF EXISTS get_location_stats();
DROP FUNCTION IF EXISTS get_location_stats_by_country();

-- ============================================================
-- 1. Create function for country-level location statistics
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
    SELECT COUNT(*) INTO total_count FROM suppliers;
    
    RETURN QUERY
    SELECT 
        s.country::VARCHAR as location,
        COUNT(*)::BIGINT as count,
        COUNT(*) FILTER (WHERE s.status = 'APPROVED')::BIGINT as approved_count,
        COUNT(*) FILTER (WHERE s.status IN ('INCOMPLETE', 'SUBMITTED', 'UNDER_REVIEW', 'NEED_MORE_INFO'))::BIGINT as pending_count,
        ROUND((COUNT(*)::NUMERIC / NULLIF(total_count, 0) * 100), 2) as percentage
    FROM suppliers s
    WHERE s.country IS NOT NULL AND s.country != ''
    GROUP BY s.country
    ORDER BY count DESC
    LIMIT 15;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 2. Improve existing city-level location stats (add status breakdown)
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
    SELECT COUNT(*) INTO total_count FROM suppliers;
    
    RETURN QUERY
    SELECT 
        s.city::VARCHAR as location,
        COUNT(*)::BIGINT as count,
        COUNT(*) FILTER (WHERE s.status = 'APPROVED')::BIGINT as approved_count,
        COUNT(*) FILTER (WHERE s.status IN ('INCOMPLETE', 'SUBMITTED', 'UNDER_REVIEW', 'NEED_MORE_INFO'))::BIGINT as pending_count,
        ROUND((COUNT(*)::NUMERIC / NULLIF(total_count, 0) * 100), 2) as percentage
    FROM suppliers s
    WHERE s.city IS NOT NULL AND s.city != ''
    GROUP BY s.city
    ORDER BY count DESC
    LIMIT 15;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Verification queries
-- ============================================================
/*
-- Test country-level stats
SELECT * FROM get_location_stats_by_country();

-- Test city-level stats (updated)
SELECT * FROM get_location_stats();

-- Verify both return location, count, approved_count, pending_count, percentage
*/
