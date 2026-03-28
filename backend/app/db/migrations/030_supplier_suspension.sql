-- ============================================================
-- Migration 030: Supplier Suspension for Expired Documents
--
-- Business rule:
--   An APPROVED supplier whose document(s) have been expired for
--   1+ day (i.e. the daily job previously set them to
--   COMPLIANCE_REQUIRED and they still have not fixed it) is
--   automatically moved to SUSPENDED status.
--
--   Once every expired document is replaced AND admin-verified,
--   the supplier is restored to APPROVED.
-- ============================================================

-- ============================================================
-- 1. Add SUSPENDED to the supplier_status enum
-- ============================================================
ALTER TYPE supplier_status ADD VALUE IF NOT EXISTS 'SUSPENDED';

COMMENT ON TYPE supplier_status IS
    'INCOMPLETE | SUBMITTED | UNDER_REVIEW | NEED_MORE_INFO | APPROVED | REJECTED | COMPLIANCE_REQUIRED | SUSPENDED';

-- ============================================================
-- 2. Add suspension tracking columns to suppliers
-- ============================================================
ALTER TABLE suppliers
    ADD COLUMN IF NOT EXISTS suspended_at      TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS suspension_reason TEXT;

COMMENT ON COLUMN suppliers.suspended_at IS
    'Timestamp when the supplier was moved to SUSPENDED status due to expired documents.';
COMMENT ON COLUMN suppliers.suspension_reason IS
    'Human-readable summary of which documents caused the suspension.';

-- ============================================================
-- 3. Suspension history table (audit trail)
-- ============================================================
CREATE TABLE IF NOT EXISTS supplier_suspension_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id     UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    event           VARCHAR(20) NOT NULL CHECK (event IN ('SUSPENDED', 'RESTORED')),
    reason          TEXT,
    triggered_by    VARCHAR(50) DEFAULT 'SYSTEM',  -- 'SYSTEM' or admin email
    documents_info  JSONB,                          -- snapshot of expired doc types at event time
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_suspension_history_supplier
    ON supplier_suspension_history(supplier_id, created_at DESC);

-- ============================================================
-- 4. Function: auto_suspend_expired_suppliers
--    Suspends suppliers that are currently in COMPLIANCE_REQUIRED
--    status and still have at least one verified, non-archived
--    document whose expiry_date < CURRENT_DATE (i.e. already past).
--
--    The logic is:
--      • check_and_flag_expired_documents() runs first in the
--        nightly job and moves APPROVED → COMPLIANCE_REQUIRED.
--      • This function then moves COMPLIANCE_REQUIRED → SUSPENDED
--        for suppliers that haven't fixed their docs.
--      • Net effect: supplier is suspended on the day AFTER the
--        document expires (one grace period of one nightly cycle).
-- ============================================================
CREATE OR REPLACE FUNCTION auto_suspend_expired_suppliers()
RETURNS TABLE(
    supplier_id   UUID,
    company_name  TEXT,
    expired_count INTEGER,
    reason        TEXT
) AS $$
DECLARE
    v_rec RECORD;
    v_expired_docs TEXT;
    v_reason TEXT;
BEGIN
    FOR v_rec IN
        SELECT
            s.id                               AS sup_id,
            s.company_name::TEXT               AS sup_name,
            COUNT(*)::INTEGER                  AS exp_count,
            STRING_AGG(d.document_type::TEXT, ', ' ORDER BY d.document_type::TEXT) AS doc_types
        FROM suppliers s
        JOIN documents d
            ON d.supplier_id         = s.id
            AND d.expiry_date        IS NOT NULL
            AND d.expiry_date        < CURRENT_DATE
            AND d.verification_status = 'VERIFIED'
            AND COALESCE(d.is_archived, FALSE) = FALSE
        WHERE s.status = 'COMPLIANCE_REQUIRED'
        GROUP BY s.id, s.company_name
    LOOP
        v_reason := 'Suspended due to ' || v_rec.exp_count || ' expired document(s): ' || v_rec.doc_types;

        -- Update the supplier row
        UPDATE suppliers
        SET
            status            = 'SUSPENDED',
            suspended_at      = CURRENT_TIMESTAMP,
            suspension_reason = v_reason,
            updated_at        = CURRENT_TIMESTAMP
        WHERE id = v_rec.sup_id;

        -- Record in history
        INSERT INTO supplier_suspension_history
            (supplier_id, event, reason, triggered_by, documents_info)
        VALUES (
            v_rec.sup_id,
            'SUSPENDED',
            v_reason,
            'SYSTEM',
            jsonb_build_object(
                'expired_count', v_rec.exp_count,
                'document_types', v_rec.doc_types,
                'suspended_on', CURRENT_DATE
            )
        );

        -- Return the row
        supplier_id   := v_rec.sup_id;
        company_name  := v_rec.sup_name;
        expired_count := v_rec.exp_count;
        reason        := v_reason;
        RETURN NEXT;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 5. Function: restore_suspended_supplier
--    Restores a SUSPENDED (or COMPLIANCE_REQUIRED) supplier to
--    APPROVED when they have NO active expired verified docs.
--    Called after admin verifies a replacement document.
-- ============================================================
CREATE OR REPLACE FUNCTION restore_suspended_supplier(
    p_supplier_id UUID
)
RETURNS BOOLEAN AS $$
DECLARE
    v_has_expired BOOLEAN;
    v_current_status TEXT;
BEGIN
    SELECT status::TEXT INTO v_current_status
    FROM suppliers
    WHERE id = p_supplier_id;

    -- Only act on suspended or compliance-required suppliers
    IF v_current_status NOT IN ('SUSPENDED', 'COMPLIANCE_REQUIRED') THEN
        RETURN FALSE;
    END IF;

    -- Check for any still-expired active verified document
    SELECT EXISTS (
        SELECT 1
        FROM documents
        WHERE supplier_id        = p_supplier_id
          AND expiry_date        IS NOT NULL
          AND expiry_date        < CURRENT_DATE
          AND verification_status = 'VERIFIED'
          AND COALESCE(is_archived, FALSE) = FALSE
    ) INTO v_has_expired;

    IF NOT v_has_expired THEN
        UPDATE suppliers
        SET
            status            = 'APPROVED',
            suspended_at      = NULL,
            suspension_reason = NULL,
            updated_at        = CURRENT_TIMESTAMP
        WHERE id = p_supplier_id;

        INSERT INTO supplier_suspension_history
            (supplier_id, event, reason, triggered_by)
        VALUES (
            p_supplier_id,
            'RESTORED',
            'All expired documents have been replaced and verified.',
            'SYSTEM'
        );

        RETURN TRUE;   -- Restored
    END IF;

    RETURN FALSE;  -- Still has expired documents
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 6. Function: get_suspended_suppliers
--    Returns the list of currently suspended suppliers with
--    details about which documents are causing the suspension.
-- ============================================================
CREATE OR REPLACE FUNCTION get_suspended_suppliers()
RETURNS TABLE(
    supplier_id            UUID,
    company_name           TEXT,
    email                  TEXT,
    contact_person_name    TEXT,
    phone                  TEXT,
    business_category      TEXT,
    city                   TEXT,
    country                TEXT,
    suspended_at           TIMESTAMP WITH TIME ZONE,
    suspension_reason      TEXT,
    expired_doc_count      INTEGER,
    expired_doc_types      TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id                                                        AS supplier_id,
        s.company_name::TEXT                                        AS company_name,
        s.email::TEXT                                               AS email,
        s.contact_person_name::TEXT                                 AS contact_person_name,
        s.phone::TEXT                                               AS phone,
        s.business_category::TEXT                                   AS business_category,
        s.city::TEXT                                                AS city,
        s.country::TEXT                                             AS country,
        s.suspended_at,
        s.suspension_reason::TEXT                                   AS suspension_reason,
        COALESCE(ed.expired_doc_count, 0)::INTEGER                  AS expired_doc_count,
        COALESCE(ed.expired_doc_types, 'None')::TEXT                AS expired_doc_types
    FROM suppliers s
    LEFT JOIN (
        SELECT
            d.supplier_id,
            COUNT(*)::INTEGER AS expired_doc_count,
            STRING_AGG(d.document_type::TEXT, ', ' ORDER BY d.document_type::TEXT) AS expired_doc_types
        FROM documents d
        WHERE d.expiry_date IS NOT NULL
          AND d.expiry_date < CURRENT_DATE
          AND d.verification_status = 'VERIFIED'
          AND COALESCE(d.is_archived, FALSE) = FALSE
        GROUP BY d.supplier_id
    ) ed ON ed.supplier_id = s.id
    WHERE s.status = 'SUSPENDED'
    ORDER BY s.suspended_at DESC NULLS LAST;
END;
$$ LANGUAGE plpgsql STABLE;
