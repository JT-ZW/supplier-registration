-- ============================================================
-- Migration 051: Fix pending-alert scope and archived-document filtering
--
-- Purpose:
-- 1) Ensure get_pending_alerts() does not include archived documents.
-- 2) Align pending alert visibility with the expanded expiry scope from migration 032
--    (all non-INCOMPLETE, non-REJECTED supplier statuses).
-- ============================================================

DROP FUNCTION IF EXISTS get_pending_alerts();

CREATE OR REPLACE FUNCTION get_pending_alerts()
RETURNS TABLE(
    alert_id UUID,
    document_id UUID,
    supplier_id UUID,
    company_name TEXT,
    email TEXT,
    document_type TEXT,
    expiry_date DATE,
    alert_type VARCHAR(20),
    days_until_expiry INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dea.id AS alert_id,
        dea.document_id,
        dea.supplier_id,
        s.company_name::TEXT,
        s.email::TEXT,
        d.document_type::TEXT,
        dea.expiry_date,
        dea.alert_type,
        (dea.expiry_date - CURRENT_DATE)::INTEGER AS days_until_expiry
    FROM document_expiry_alerts dea
    INNER JOIN documents d ON dea.document_id = d.id
    INNER JOIN suppliers s ON dea.supplier_id = s.id
    WHERE dea.email_sent = FALSE
      AND COALESCE(d.is_archived, FALSE) = FALSE
      AND s.status::TEXT NOT IN ('INCOMPLETE', 'REJECTED')
    ORDER BY dea.expiry_date ASC, dea.alert_type ASC;
END;
$$ LANGUAGE plpgsql STABLE;
