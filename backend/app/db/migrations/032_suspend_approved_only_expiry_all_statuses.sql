-- ============================================================
-- Migration 032: Suspension Guard + Expiry Scope Expansion
--
-- Changes:
--   • admin_suspend_supplier() now rejects any supplier whose
--     status is NOT 'APPROVED' or 'COMPLIANCE_REQUIRED'.
--     Unapproved suppliers (SUBMITTED, UNDER_REVIEW, etc.) cannot
--     be manually suspended — they must first complete the
--     approval process.
--
--   • get_expiring_documents() and get_expired_documents() now
--     include ALL non-INCOMPLETE, non-REJECTED supplier statuses
--     (adds SUBMITTED, NEED_MORE_INFO, SUSPENDED to the existing
--     APPROVED / UNDER_REVIEW / COMPLIANCE_REQUIRED set).
--     This allows the Document Expiry page to surface expiring
--     docs for applicants still under review so they can be
--     flagged — without being auto-suspended.
-- ============================================================


-- ============================================================
-- 1. Update admin_suspend_supplier — APPROVED/COMPLIANCE_REQUIRED
--    guard.  Any other status raises an exception so the backend
--    can surface a clear error message.
-- ============================================================
CREATE OR REPLACE FUNCTION admin_suspend_supplier(
    p_supplier_id  UUID,
    p_reason       TEXT,
    p_admin_email  TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    v_current_status TEXT;
BEGIN
    SELECT status::TEXT INTO v_current_status
    FROM suppliers
    WHERE id = p_supplier_id;

    IF v_current_status IS NULL THEN
        RAISE EXCEPTION 'Supplier not found';
    END IF;

    -- Only APPROVED or COMPLIANCE_REQUIRED suppliers can be suspended.
    -- Unapproved applicants (SUBMITTED, UNDER_REVIEW, NEED_MORE_INFO …)
    -- must not be suspended; flag them on the Expiry page instead.
    IF v_current_status NOT IN ('APPROVED', 'COMPLIANCE_REQUIRED') THEN
        RAISE EXCEPTION
            'Cannot suspend supplier: current status is %. Only APPROVED or COMPLIANCE_REQUIRED suppliers can be suspended.',
            v_current_status;
    END IF;

    -- Already suspended – no-op
    IF v_current_status = 'SUSPENDED' THEN
        RETURN FALSE;
    END IF;

    UPDATE suppliers
    SET
        status                    = 'SUSPENDED',
        suspended_at              = CURRENT_TIMESTAMP,
        suspension_reason         = p_reason,
        suspension_triggered_by   = p_admin_email,
        updated_at                = CURRENT_TIMESTAMP
    WHERE id = p_supplier_id;

    INSERT INTO supplier_suspension_history
        (supplier_id, event, reason, triggered_by)
    VALUES (
        p_supplier_id,
        'SUSPENDED',
        p_reason,
        p_admin_email
    );

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- 2. Expand get_expiring_documents to include all in-process
--    supplier statuses so the Document Expiry page can flag
--    applicants that still have docs about to expire.
-- ============================================================
DROP FUNCTION IF EXISTS get_expiring_documents(integer);

CREATE OR REPLACE FUNCTION get_expiring_documents(
    p_days_threshold INTEGER DEFAULT 90
)
RETURNS TABLE(
    document_id       UUID,
    supplier_id       UUID,
    company_name      TEXT,
    email             TEXT,
    document_type     TEXT,
    expiry_date       DATE,
    days_until_expiry INTEGER,
    file_url          TEXT,
    supplier_status   TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id                                            AS document_id,
        d.supplier_id,
        s.company_name::TEXT,
        s.email::TEXT,
        d.document_type::TEXT                           AS document_type,
        d.expiry_date,
        (d.expiry_date - CURRENT_DATE)::INTEGER         AS days_until_expiry,
        d.s3_key::TEXT                                  AS file_url,
        s.status::TEXT                                  AS supplier_status
    FROM documents d
    INNER JOIN suppliers s ON d.supplier_id = s.id
    WHERE d.expiry_date IS NOT NULL
      AND d.expiry_date <= CURRENT_DATE + p_days_threshold
      AND d.expiry_date >= CURRENT_DATE
      AND d.verification_status = 'VERIFIED'
      AND d.is_archived = FALSE
      -- Include all active/in-process statuses (exclude INCOMPLETE and REJECTED)
      AND s.status::TEXT NOT IN ('INCOMPLETE', 'REJECTED')
    ORDER BY d.expiry_date ASC, s.company_name ASC;
END;
$$ LANGUAGE plpgsql STABLE;


-- ============================================================
-- 3. Expand get_expired_documents with the same scope.
-- ============================================================
DROP FUNCTION IF EXISTS get_expired_documents();

CREATE OR REPLACE FUNCTION get_expired_documents()
RETURNS TABLE(
    document_id       UUID,
    supplier_id       UUID,
    company_name      TEXT,
    email             TEXT,
    document_type     TEXT,
    expiry_date       DATE,
    days_since_expiry INTEGER,
    file_url          TEXT,
    supplier_status   TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id                                            AS document_id,
        d.supplier_id,
        s.company_name::TEXT,
        s.email::TEXT,
        d.document_type::TEXT                           AS document_type,
        d.expiry_date,
        (CURRENT_DATE - d.expiry_date)::INTEGER         AS days_since_expiry,
        d.s3_key::TEXT                                  AS file_url,
        s.status::TEXT                                  AS supplier_status
    FROM documents d
    INNER JOIN suppliers s ON d.supplier_id = s.id
    WHERE d.expiry_date IS NOT NULL
      AND d.expiry_date < CURRENT_DATE
      AND d.verification_status = 'VERIFIED'
      AND d.is_archived = FALSE
      -- Include all active/in-process statuses (exclude INCOMPLETE and REJECTED)
      AND s.status::TEXT NOT IN ('INCOMPLETE', 'REJECTED')
    ORDER BY d.expiry_date ASC, s.company_name ASC;
END;
$$ LANGUAGE plpgsql STABLE;
