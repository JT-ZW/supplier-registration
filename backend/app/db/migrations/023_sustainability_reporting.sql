-- Migration: Sustainability & Quality Control Reporting
-- Date: 2026-02-28
-- Description:
--   Adds database-side support for the sustainability reporting feature.
--   1. Creates a view (v_sustainability_submissions) that joins documents
--      with supplier information for all sustainability/QC document types.
--   2. Adds a performance index on documents.document_type so the query
--      that filters by document type runs efficiently as the table grows.
--
-- HOW TO RUN:
--   Paste the contents of this file into the Supabase SQL Editor and
--   click "Run". No rollback required — the view and index are created
--   with IF NOT EXISTS / CREATE OR REPLACE where supported.

-- ============================================================
-- 1. Performance index on documents.document_type
-- ============================================================
-- This makes the sustainability query (which filters by document_type)
-- fast even when the documents table has many rows.
CREATE INDEX IF NOT EXISTS idx_documents_document_type
    ON documents (document_type);

-- ============================================================
-- 2. Sustainability submissions view
-- ============================================================
-- This view surfaces every sustainability/QC document submission
-- alongside the submitting supplier's key details.
-- It is used by the report service as a convenient audit data source
-- and can also be queried directly in the Supabase dashboard.
CREATE OR REPLACE VIEW v_sustainability_submissions AS
SELECT
    d.id                                                         AS document_id,
    d.supplier_id,
    s.company_name,
    s.business_category,
    s.city,
    s.country,
    s.email                                                      AS supplier_email,
    s.contact_person_name,
    s.status                                                     AS supplier_status,
    d.document_type,
    CASE d.document_type
        WHEN 'FOOD_SAFETY_CERTIFICATION'   THEN 'Food Safety Certification'
        WHEN 'GOOD_AGRICULTURAL_PRACTICES' THEN 'Good Agricultural Practices (GAP)'
        WHEN 'ISO_14000'                   THEN 'ISO 14000 (Environmental Management)'
        WHEN 'ISO_45000'                   THEN 'ISO 45000 (Occupational Health & Safety)'
        WHEN 'INDUSTRY_CERTIFICATION'      THEN 'Industry Certification'
        ELSE REPLACE(d.document_type::text, '_', ' ')
    END                                                          AS document_display_name,
    d.verification_status,
    d.uploaded_at                                                AS submitted_at,
    d.verified_at                                                AS last_updated_at
FROM documents d
JOIN suppliers s ON s.id = d.supplier_id
WHERE d.document_type IN (
    'FOOD_SAFETY_CERTIFICATION',
    'GOOD_AGRICULTURAL_PRACTICES',
    'ISO_14000',
    'ISO_45000',
    'INDUSTRY_CERTIFICATION'
)
ORDER BY s.company_name, d.document_type;

-- ============================================================
-- 3. Sustainability participation summary view
-- ============================================================
-- Aggregated per-supplier view — one row per supplier that has
-- submitted at least one sustainability document.  Useful for
-- quickly answering "how many suppliers participated?" and for
-- further drill-down in the Supabase dashboard.
CREATE OR REPLACE VIEW v_sustainability_participation AS
SELECT
    s.id                                                         AS supplier_id,
    s.company_name,
    s.business_category,
    s.city,
    s.country,
    s.status                                                     AS supplier_status,
    COUNT(d.id)                                                  AS documents_submitted,
    COUNT(d.id) FILTER (WHERE d.verification_status = 'VERIFIED')  AS documents_verified,
    COUNT(d.id) FILTER (WHERE d.verification_status = 'PENDING')   AS documents_pending,
    COUNT(d.id) FILTER (WHERE d.verification_status = 'REJECTED')  AS documents_rejected,
    STRING_AGG(
        CASE d.document_type
            WHEN 'FOOD_SAFETY_CERTIFICATION'   THEN 'Food Safety Certification'
            WHEN 'GOOD_AGRICULTURAL_PRACTICES' THEN 'Good Agricultural Practices (GAP)'
            WHEN 'ISO_14000'                   THEN 'ISO 14000 (Environmental Management)'
            WHEN 'ISO_45000'                   THEN 'ISO 45000 (Occupational Health & Safety)'
            WHEN 'INDUSTRY_CERTIFICATION'      THEN 'Industry Certification'
            ELSE REPLACE(d.document_type::text, '_', ' ')
        END,
        ', ' ORDER BY d.document_type
    )                                                            AS document_list,
    MIN(d.uploaded_at)                                           AS first_submission_at,
    MAX(d.uploaded_at)                                           AS latest_submission_at
FROM suppliers s
JOIN documents d ON d.supplier_id = s.id
WHERE d.document_type IN (
    'FOOD_SAFETY_CERTIFICATION',
    'GOOD_AGRICULTURAL_PRACTICES',
    'ISO_14000',
    'ISO_45000',
    'INDUSTRY_CERTIFICATION'
)
GROUP BY
    s.id,
    s.company_name,
    s.business_category,
    s.city,
    s.country,
    s.status
ORDER BY s.company_name;

-- ============================================================
-- Verification: run these SELECT statements to confirm the
-- views are working correctly after applying the migration.
-- ============================================================
-- SELECT COUNT(*) FROM v_sustainability_submissions;
-- SELECT COUNT(*) FROM v_sustainability_participation;
-- SELECT document_type, COUNT(*) AS total
--   FROM v_sustainability_submissions
--   GROUP BY document_type
--   ORDER BY total DESC;
