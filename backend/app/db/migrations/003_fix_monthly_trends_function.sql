-- Fix get_monthly_trends function - correct GROUP BY clause
CREATE OR REPLACE FUNCTION get_monthly_trends(months_back INTEGER DEFAULT 12)
RETURNS TABLE (
    month VARCHAR,
    year INTEGER,
    submitted BIGINT,
    approved BIGINT,
    rejected BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        TO_CHAR(month_date, 'Mon')::VARCHAR as month,
        EXTRACT(YEAR FROM month_date)::INTEGER as year,
        COUNT(*)::BIGINT as submitted,
        COUNT(*) FILTER (WHERE s.status = 'APPROVED')::BIGINT as approved,
        COUNT(*) FILTER (WHERE s.status = 'REJECTED')::BIGINT as rejected
    FROM (
        SELECT 
            DATE_TRUNC('month', s.created_at) as month_date,
            s.status
        FROM suppliers s
        WHERE s.created_at >= CURRENT_DATE - (months_back || ' months')::INTERVAL
    ) s
    GROUP BY month_date
    ORDER BY month_date;
END;
$$ LANGUAGE plpgsql;
