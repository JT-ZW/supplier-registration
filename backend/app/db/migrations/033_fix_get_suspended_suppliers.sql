-- ============================================================
-- Migration 033: Fix get_suspended_suppliers to include
--                COMPLIANCE_REQUIRED suppliers
--
-- Changes:
--   • get_suspended_suppliers() now returns both 'SUSPENDED'
--     and 'COMPLIANCE_REQUIRED' approved suppliers so the
--     Suspended Suppliers admin page lists everyone who is
--     no longer in good standing.
--
--   • Adds a current_status column to the return set so the
--     frontend can distinguish between the two states and
--     show the appropriate badge (amber = Compliance Required,
--     red = Suspended).
--
--   • For COMPLIANCE_REQUIRED suppliers that have not yet had
--     suspended_at set, falls back to updated_at so the
--     "days since" column is always populated.
--
--   • For COMPLIANCE_REQUIRED suppliers without a
--     suspension_reason, auto-generates a reason from the
--     expired document list.
-- ============================================================

-- Must DROP first because the return type gained a new column.
DROP FUNCTION IF EXISTS get_suspended_suppliers();

CREATE OR REPLACE FUNCTION get_suspended_suppliers()
RETURNS TABLE(
    supplier_id              UUID,
    company_name             TEXT,
    email                    TEXT,
    contact_person_name      TEXT,
    phone                    TEXT,
    business_category        TEXT,
    city                     TEXT,
    country                  TEXT,
    suspended_at             TIMESTAMP WITH TIME ZONE,
    suspension_reason        TEXT,
    suspension_triggered_by  TEXT,
    expired_doc_count        INTEGER,
    expired_doc_types        TEXT,
    current_status           TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id                                                              AS supplier_id,
        s.company_name::TEXT                                              AS company_name,
        s.email::TEXT                                                     AS email,
        s.contact_person_name::TEXT                                       AS contact_person_name,
        s.phone::TEXT                                                     AS phone,
        s.business_category::TEXT                                         AS business_category,
        s.city::TEXT                                                      AS city,
        s.country::TEXT                                                   AS country,
        -- For COMPLIANCE_REQUIRED suppliers suspended_at may be NULL;
        -- fall back to updated_at so the "days since" column is useful.
        COALESCE(s.suspended_at, s.updated_at)                           AS suspended_at,
        -- Generate a reason for COMPLIANCE_REQUIRED rows that don't have one.
        COALESCE(
            s.suspension_reason,
            CASE
                WHEN COALESCE(ed.expired_doc_count, 0) > 0 THEN
                    'Compliance required: ' || ed.expired_doc_count ||
                    ' expired document(s): ' || ed.expired_doc_types
                ELSE
                    'Flagged as compliance required due to expired documents.'
            END
        )::TEXT                                                           AS suspension_reason,
        COALESCE(s.suspension_triggered_by, 'SYSTEM')::TEXT               AS suspension_triggered_by,
        COALESCE(ed.expired_doc_count, 0)::INTEGER                        AS expired_doc_count,
        COALESCE(ed.expired_doc_types, 'None')::TEXT                      AS expired_doc_types,
        s.status::TEXT                                                    AS current_status
    FROM suppliers s
    LEFT JOIN (
        SELECT
            d.supplier_id,
            COUNT(*)::INTEGER                                             AS expired_doc_count,
            STRING_AGG(
                d.document_type::TEXT, ', '
                ORDER BY d.document_type::TEXT
            )                                                             AS expired_doc_types
        FROM documents d
        WHERE d.expiry_date       IS NOT NULL
          AND d.expiry_date        < CURRENT_DATE
          AND d.verification_status = 'VERIFIED'
          AND COALESCE(d.is_archived, FALSE) = FALSE
        GROUP BY d.supplier_id
    ) ed ON ed.supplier_id = s.id
    WHERE s.status IN ('SUSPENDED', 'COMPLIANCE_REQUIRED')
    ORDER BY
        -- SUSPENDED comes first (more severe), then COMPLIANCE_REQUIRED
        CASE s.status WHEN 'SUSPENDED' THEN 0 ELSE 1 END,
        COALESCE(s.suspended_at, s.updated_at) DESC NULLS LAST;
END;
$$ LANGUAGE plpgsql STABLE;
