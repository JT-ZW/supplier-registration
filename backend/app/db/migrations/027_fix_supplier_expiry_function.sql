-- ============================================================
-- Migration 027: Fix get_supplier_expiring_documents return type
-- The document_type column is TEXT in the DB but the function
-- declared it as VARCHAR(100), causing error code 42804.
-- Also aligns the function signature with other expiry functions.
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
        d.id                                    AS document_id,
        d.document_type::TEXT                   AS document_type,
        d.expiry_date,
        (d.expiry_date - CURRENT_DATE)::INTEGER AS days_until_expiry,
        COALESCE(a.reminder_count, 0)::INTEGER  AS alert_count,
        a.last_reminder_at                      AS last_alert_date,
        COALESCE(a.acknowledged, FALSE)         AS acknowledged
    FROM documents d
    LEFT JOIN document_expiry_alerts a
        ON a.document_id = d.id
        AND a.alert_type = CASE
            WHEN (d.expiry_date - CURRENT_DATE) <= 1   THEN '1_day'
            WHEN (d.expiry_date - CURRENT_DATE) <= 7   THEN '7_days'
            WHEN (d.expiry_date - CURRENT_DATE) <= 30  THEN '30_days'
            WHEN (d.expiry_date - CURRENT_DATE) <= 60  THEN '60_days'
            ELSE '90_days'
        END
    WHERE d.supplier_id       = p_supplier_id
      AND d.expiry_date       IS NOT NULL
      AND d.expiry_date       <= CURRENT_DATE + p_days_threshold
      AND d.expiry_date       >= CURRENT_DATE
      AND d.verification_status = 'VERIFIED'
      AND COALESCE(d.is_archived, FALSE) = FALSE
    ORDER BY d.expiry_date ASC;
END;
$$ LANGUAGE plpgsql STABLE;
