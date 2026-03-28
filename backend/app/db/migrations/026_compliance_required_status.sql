-- ============================================================
-- Migration 026: Compliance Required Status & Document Archiving
-- Adds COMPLIANCE_REQUIRED supplier status and document archiving
-- to support the full document expiry tracking lifecycle.
-- ============================================================

-- ============================================================
-- 1. Add COMPLIANCE_REQUIRED to the suppliers status column
--    The status column uses a PostgreSQL enum type (supplier_status).
--    ADD VALUE IF NOT EXISTS is safe to run multiple times.
-- ============================================================

ALTER TYPE supplier_status ADD VALUE IF NOT EXISTS 'COMPLIANCE_REQUIRED';

COMMENT ON COLUMN suppliers.status IS
    'Application and compliance lifecycle status. COMPLIANCE_REQUIRED indicates an approved supplier with at least one expired verified document.';


-- ============================================================
-- 2. Add archiving columns to the documents table
--    (Tracks when a document is superseded by a replacement upload)
-- ============================================================

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS is_archived  BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS archived_at  TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS replaced_by  UUID REFERENCES documents(id) ON DELETE SET NULL;

-- Index for quickly filtering active (non-archived) documents
CREATE INDEX IF NOT EXISTS idx_documents_not_archived
    ON documents(supplier_id, document_type)
    WHERE is_archived = FALSE;

COMMENT ON COLUMN documents.is_archived IS
    'TRUE when this document has been superseded by a newer upload of the same type.';
COMMENT ON COLUMN documents.archived_at IS
    'Timestamp when the document was archived (i.e., replaced).';
COMMENT ON COLUMN documents.replaced_by IS
    'ID of the document record that replaced this one.';


-- ============================================================
-- 3. Function: archive_old_document_version
--    Called when a supplier re-uploads a document type they already have.
--    Archives the previous record and links it to the new one.
-- ============================================================

CREATE OR REPLACE FUNCTION archive_old_document_version(
    p_supplier_id   UUID,
    p_document_type VARCHAR(100),
    p_new_doc_id    UUID
)
RETURNS VOID AS $$
BEGIN
    UPDATE documents
    SET
        is_archived  = TRUE,
        archived_at  = CURRENT_TIMESTAMP,
        replaced_by  = p_new_doc_id,
        updated_at   = CURRENT_TIMESTAMP
    WHERE
        supplier_id   = p_supplier_id
        AND document_type = p_document_type
        AND id        != p_new_doc_id
        AND is_archived = FALSE;
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- 4. Function: check_and_flag_expired_documents
--    Sets a supplier's status to COMPLIANCE_REQUIRED when any of
--    their verified, non-archived documents have passed their expiry_date.
--    Called nightly by the scheduler.
-- ============================================================

CREATE OR REPLACE FUNCTION check_and_flag_expired_documents()
RETURNS TABLE(
    supplier_id   UUID,
    company_name  VARCHAR(255),
    expired_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH expired AS (
        SELECT
            d.supplier_id,
            COUNT(*)::INTEGER AS expired_count
        FROM documents d
        WHERE d.expiry_date IS NOT NULL
          AND d.expiry_date < CURRENT_DATE
          AND d.verification_status = 'VERIFIED'
          AND d.is_archived = FALSE
        GROUP BY d.supplier_id
    ),
    updated AS (
        UPDATE suppliers s
        SET
            status     = 'COMPLIANCE_REQUIRED',
            updated_at = CURRENT_TIMESTAMP
        FROM expired e
        WHERE s.id     = e.supplier_id
          AND s.status = 'APPROVED'   -- Only flag currently-approved suppliers
        RETURNING s.id, s.company_name, e.expired_count
    )
    SELECT u.id, u.company_name, u.expired_count
    FROM updated u;
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- 5. Function: resolve_compliance_status
--    Restores a supplier from COMPLIANCE_REQUIRED back to APPROVED
--    when all their verified documents are within their expiry dates.
--    Called after a supplier successfully re-uploads and admin verifies.
-- ============================================================

CREATE OR REPLACE FUNCTION resolve_compliance_status(
    p_supplier_id UUID
)
RETURNS BOOLEAN AS $$
DECLARE
    v_has_expired BOOLEAN;
BEGIN
    -- Check whether any active, verified document is still expired
    SELECT EXISTS (
        SELECT 1
        FROM documents
        WHERE supplier_id       = p_supplier_id
          AND expiry_date       IS NOT NULL
          AND expiry_date       < CURRENT_DATE
          AND verification_status = 'VERIFIED'
          AND is_archived       = FALSE
    ) INTO v_has_expired;

    IF NOT v_has_expired THEN
        UPDATE suppliers
        SET
            status     = 'APPROVED',
            updated_at = CURRENT_TIMESTAMP
        WHERE id     = p_supplier_id
          AND status = 'COMPLIANCE_REQUIRED';

        RETURN TRUE;  -- Status restored
    END IF;

    RETURN FALSE;  -- Still has expired documents
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- 6. Update get_expiring_documents to exclude archived documents
-- ============================================================

DROP FUNCTION IF EXISTS get_expiring_documents(integer);

CREATE OR REPLACE FUNCTION get_expiring_documents(
    p_days_threshold INTEGER DEFAULT 90
)
RETURNS TABLE(
    document_id      UUID,
    supplier_id      UUID,
    company_name     TEXT,
    email            TEXT,
    document_type    TEXT,
    expiry_date      DATE,
    days_until_expiry INTEGER,
    file_url         TEXT,
    supplier_status  TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id               AS document_id,
        d.supplier_id,
        s.company_name::TEXT,
        s.email::TEXT,
        d.document_type::TEXT AS document_type,
        d.expiry_date,
        (d.expiry_date - CURRENT_DATE)::INTEGER AS days_until_expiry,
        d.s3_key::TEXT     AS file_url,
        s.status::TEXT     AS supplier_status
    FROM documents d
    INNER JOIN suppliers s ON d.supplier_id = s.id
    WHERE d.expiry_date IS NOT NULL
      AND d.expiry_date <= CURRENT_DATE + p_days_threshold
      AND d.expiry_date >= CURRENT_DATE
      AND d.verification_status = 'VERIFIED'
      AND d.is_archived = FALSE
      AND s.status::TEXT IN ('APPROVED', 'UNDER_REVIEW', 'COMPLIANCE_REQUIRED')
    ORDER BY d.expiry_date ASC, s.company_name ASC;
END;
$$ LANGUAGE plpgsql STABLE;


-- ============================================================
-- 7. Update get_expired_documents to exclude archived documents
-- ============================================================

DROP FUNCTION IF EXISTS get_expired_documents();

CREATE OR REPLACE FUNCTION get_expired_documents()
RETURNS TABLE(
    document_id      UUID,
    supplier_id      UUID,
    company_name     TEXT,
    email            TEXT,
    document_type    TEXT,
    expiry_date      DATE,
    days_since_expiry INTEGER,
    file_url         TEXT,
    supplier_status  TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id               AS document_id,
        d.supplier_id,
        s.company_name::TEXT,
        s.email::TEXT,
        d.document_type::TEXT AS document_type,
        d.expiry_date,
        (CURRENT_DATE - d.expiry_date)::INTEGER AS days_since_expiry,
        d.s3_key::TEXT     AS file_url,
        s.status::TEXT     AS supplier_status
    FROM documents d
    INNER JOIN suppliers s ON d.supplier_id = s.id
    WHERE d.expiry_date IS NOT NULL
      AND d.expiry_date < CURRENT_DATE
      AND d.verification_status = 'VERIFIED'
      AND d.is_archived = FALSE
      AND s.status::TEXT IN ('APPROVED', 'UNDER_REVIEW', 'COMPLIANCE_REQUIRED')
    ORDER BY d.expiry_date ASC, s.company_name ASC;
END;
$$ LANGUAGE plpgsql STABLE;


-- ============================================================
-- 8. Update get_supplier_expiring_documents to exclude archived
-- ============================================================

DROP FUNCTION IF EXISTS get_supplier_expiring_documents(uuid, integer);

CREATE OR REPLACE FUNCTION get_supplier_expiring_documents(
    p_supplier_id    UUID,
    p_days_threshold INTEGER DEFAULT 90
)
RETURNS TABLE(
    document_id       UUID,
    document_type     VARCHAR(100),
    expiry_date       DATE,
    days_until_expiry INTEGER,
    alert_count       INTEGER,
    last_alert_date   TIMESTAMP WITH TIME ZONE,
    acknowledged      BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id                        AS document_id,
        d.document_type,
        d.expiry_date,
        (d.expiry_date - CURRENT_DATE)::INTEGER AS days_until_expiry,
        COALESCE(a.reminder_count, 0)::INTEGER  AS alert_count,
        a.last_reminder_at          AS last_alert_date,
        COALESCE(a.acknowledged, FALSE)         AS acknowledged
    FROM documents d
    LEFT JOIN document_expiry_alerts a
        ON a.document_id = d.id
        AND a.alert_type = CASE
            WHEN (d.expiry_date - CURRENT_DATE) <= 7   THEN '7_days'
            WHEN (d.expiry_date - CURRENT_DATE) <= 30  THEN '30_days'
            WHEN (d.expiry_date - CURRENT_DATE) <= 60  THEN '60_days'
            ELSE '90_days'
        END
    WHERE d.supplier_id    = p_supplier_id
      AND d.expiry_date    IS NOT NULL
      AND d.expiry_date    <= CURRENT_DATE + p_days_threshold
      AND d.expiry_date    >= CURRENT_DATE
      AND d.verification_status = 'VERIFIED'
      AND d.is_archived    = FALSE
    ORDER BY d.expiry_date ASC;
END;
$$ LANGUAGE plpgsql STABLE;


-- ============================================================
-- 9. STATUS_LABELS update note
--    Remember to add COMPLIANCE_REQUIRED to frontend STATUS_LABELS
--    in constants/index.ts:
--    COMPLIANCE_REQUIRED: "Compliance Required"
-- ============================================================
