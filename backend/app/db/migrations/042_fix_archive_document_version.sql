-- ============================================================
-- Migration 042: Fix archive_old_document_version type mismatch
-- ============================================================
-- The document_type column in the documents table is a PostgreSQL
-- ENUM type. Comparing it directly to a VARCHAR/TEXT parameter
-- produces: "operator does not exist: document_type = character varying"
-- Fix: cast the column to TEXT before comparing so the match works
-- regardless of whether the column is a ENUM or TEXT type.
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
        replaced_by  = p_new_doc_id
    WHERE
        supplier_id            = p_supplier_id
        AND document_type::TEXT = p_document_type
        AND id                 != p_new_doc_id
        AND is_archived         = FALSE;
END;
$$ LANGUAGE plpgsql;
