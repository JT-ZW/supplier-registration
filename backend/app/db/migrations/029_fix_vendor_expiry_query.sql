-- ============================================================
-- Migration 029: Fix get_supplier_expiring_documents (stable)
--
-- Migration 027 introduced a CASE-based LEFT JOIN to match a
-- single alert row per document. That JOIN is overly narrow and
-- causes errors for day thresholds other than 90.  This migration
-- replaces the function with the proven GROUP BY + COUNT approach
-- from migration 011, adding the TEXT cast and is_archived filter.
-- ============================================================

DROP FUNCTION IF EXISTS get_supplier_expiring_documents(uuid, integer);

CREATE OR REPLACE FUNCTION get_supplier_expiring_documents(
    p_supplier_id    UUID,
    p_days_threshold INTEGER DEFAULT 90
)
RETURNS TABLE(
    document_id       UUID,
    document_type     TEXT,
    expiry_date       DATE,
    days_until_expiry INTEGER,
    alert_count       INTEGER,
    last_alert_date   TIMESTAMP WITH TIME ZONE,
    acknowledged      BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id                                        AS document_id,
        d.document_type::TEXT                       AS document_type,
        d.expiry_date,
        (d.expiry_date - CURRENT_DATE)::INTEGER     AS days_until_expiry,
        COALESCE(COUNT(dea.id)::INTEGER, 0)         AS alert_count,
        MAX(dea.created_at)                         AS last_alert_date,
        COALESCE(BOOL_OR(dea.acknowledged), FALSE)  AS acknowledged
    FROM documents d
    LEFT JOIN document_expiry_alerts dea ON dea.document_id = d.id
    WHERE d.supplier_id = p_supplier_id
      AND d.expiry_date IS NOT NULL
      AND d.expiry_date <= CURRENT_DATE + p_days_threshold
      AND d.expiry_date >= CURRENT_DATE
      AND d.verification_status = 'VERIFIED'
      AND COALESCE(d.is_archived, FALSE) = FALSE
    GROUP BY d.id, d.document_type, d.expiry_date
    ORDER BY d.expiry_date ASC;
END;
$$ LANGUAGE plpgsql STABLE;
