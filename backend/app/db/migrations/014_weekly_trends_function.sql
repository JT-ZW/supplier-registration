-- Add get_weekly_trends function for weekly trend analysis
CREATE OR REPLACE FUNCTION get_weekly_trends(weeks_back INTEGER DEFAULT 12)
RETURNS TABLE (
    week_label VARCHAR,
    year INTEGER,
    week_number INTEGER,
    week_start DATE,
    submitted BIGINT,
    approved BIGINT,
    rejected BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        TO_CHAR(week_start_date, 'Mon DD')::VARCHAR as week_label,
        EXTRACT(YEAR FROM week_start_date)::INTEGER as year,
        EXTRACT(WEEK FROM week_start_date)::INTEGER as week_number,
        week_start_date::DATE as week_start,
        COUNT(*)::BIGINT as submitted,
        COUNT(*) FILTER (WHERE s.status = 'APPROVED')::BIGINT as approved,
        COUNT(*) FILTER (WHERE s.status = 'REJECTED')::BIGINT as rejected
    FROM (
        SELECT 
            DATE_TRUNC('week', s.created_at)::DATE as week_start_date,
            s.status
        FROM suppliers s
        WHERE s.created_at >= CURRENT_DATE - (weeks_back || ' weeks')::INTERVAL
    ) s
    GROUP BY week_start_date
    ORDER BY week_start_date;
END;
$$ LANGUAGE plpgsql;
