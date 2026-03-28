-- ============================================================
-- Migration 031: Admin Manual Suspension + Triggered-By Tracking
--
-- Adds:
--   • suspension_triggered_by column on suppliers (stores 'SYSTEM'
--     for auto-suspensions or the admin email for manual ones)
--   • Updated auto_suspend_expired_suppliers() – sets triggered_by
--   • Updated restore_suspended_supplier() – clears triggered_by
--   • New function admin_suspend_supplier() for manual admin-initiated
--     suspensions on any APPROVED/COMPLIANCE_REQUIRED supplier
--   • Updated get_suspended_suppliers() – returns triggered_by
-- ============================================================

-- ============================================================
-- 1. Add triggered_by tracking column to suppliers
-- ============================================================
ALTER TABLE suppliers
    ADD COLUMN IF NOT EXISTS suspension_triggered_by TEXT;

COMMENT ON COLUMN suppliers.suspension_triggered_by IS
    'Who initiated the suspension: ''SYSTEM'' for automatic suspensions, or the admin email for manual ones.';

-- ============================================================
-- 2. Re-create auto_suspend_expired_suppliers with triggered_by
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
            ON d.supplier_id          = s.id
            AND d.expiry_date         IS NOT NULL
            AND d.expiry_date         < CURRENT_DATE
            AND d.verification_status  = 'VERIFIED'
            AND COALESCE(d.is_archived, FALSE) = FALSE
        WHERE s.status = 'COMPLIANCE_REQUIRED'
        GROUP BY s.id, s.company_name
    LOOP
        v_reason := 'Suspended due to ' || v_rec.exp_count || ' expired document(s): ' || v_rec.doc_types;

        UPDATE suppliers
        SET
            status                    = 'SUSPENDED',
            suspended_at              = CURRENT_TIMESTAMP,
            suspension_reason         = v_reason,
            suspension_triggered_by   = 'SYSTEM',
            updated_at                = CURRENT_TIMESTAMP
        WHERE id = v_rec.sup_id;

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

        supplier_id   := v_rec.sup_id;
        company_name  := v_rec.sup_name;
        expired_count := v_rec.exp_count;
        reason        := v_reason;
        RETURN NEXT;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 3. Re-create restore_suspended_supplier to clear triggered_by
-- ============================================================
CREATE OR REPLACE FUNCTION restore_suspended_supplier(
    p_supplier_id   UUID,
    p_triggered_by  TEXT DEFAULT 'SYSTEM'
)
RETURNS BOOLEAN AS $$
DECLARE
    v_has_expired    BOOLEAN;
    v_current_status TEXT;
BEGIN
    SELECT status::TEXT INTO v_current_status
    FROM suppliers
    WHERE id = p_supplier_id;

    IF v_current_status NOT IN ('SUSPENDED', 'COMPLIANCE_REQUIRED') THEN
        RETURN FALSE;
    END IF;

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
            status                    = 'APPROVED',
            suspended_at              = NULL,
            suspension_reason         = NULL,
            suspension_triggered_by   = NULL,
            updated_at                = CURRENT_TIMESTAMP
        WHERE id = p_supplier_id;

        INSERT INTO supplier_suspension_history
            (supplier_id, event, reason, triggered_by)
        VALUES (
            p_supplier_id,
            'RESTORED',
            'All expired documents have been replaced and verified.',
            p_triggered_by
        );

        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 4. New function: admin_suspend_supplier
--    Allows an admin to manually suspend any APPROVED (or
--    COMPLIANCE_REQUIRED) supplier with a custom reason.
--    Unlike auto-suspension, this does NOT check for expired
--    documents – it acts on the admin's discretion.
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

    -- Already suspended – no-op (return false to signal no change)
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
-- 5. Re-create get_suspended_suppliers to include triggered_by
--    Must DROP first because the return type (new column) changed.
-- ============================================================
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
    expired_doc_types        TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id                                                          AS supplier_id,
        s.company_name::TEXT                                          AS company_name,
        s.email::TEXT                                                 AS email,
        s.contact_person_name::TEXT                                   AS contact_person_name,
        s.phone::TEXT                                                 AS phone,
        s.business_category::TEXT                                     AS business_category,
        s.city::TEXT                                                  AS city,
        s.country::TEXT                                               AS country,
        s.suspended_at,
        s.suspension_reason::TEXT                                     AS suspension_reason,
        COALESCE(s.suspension_triggered_by, 'SYSTEM')::TEXT           AS suspension_triggered_by,
        COALESCE(ed.expired_doc_count, 0)::INTEGER                    AS expired_doc_count,
        COALESCE(ed.expired_doc_types, 'None')::TEXT                  AS expired_doc_types
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
