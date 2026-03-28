-- Migration 041: Compliance & sustainability reporting views
-- Provides ready-made views for:
--   1. Document type upload counts across approved suppliers (sustainability KPIs)
--   2. Per-supplier ESG summary (women-owned, youth-owned, business size)
--   3. Category-level compliance distribution

-- ── 1. Document upload stats ─────────────────────────────────────────────────
-- Counts how many distinct approved suppliers have uploaded each document type.
-- Excludes archived documents.  Used for sustainability & KPI reporting.
CREATE OR REPLACE VIEW vw_document_type_stats AS
SELECT
    d.document_type,
    COUNT(DISTINCT d.supplier_id)                                           AS supplier_count,
    COUNT(*)                                                                 AS total_uploads,
    COUNT(*) FILTER (WHERE d.verification_status = 'VERIFIED')              AS verified_count,
    COUNT(*) FILTER (WHERE d.verification_status = 'PENDING')               AS pending_count,
    COUNT(*) FILTER (WHERE d.verification_status = 'REJECTED')              AS rejected_count
FROM documents d
JOIN suppliers s ON s.id = d.supplier_id
WHERE s.status IN ('APPROVED', 'COMPLIANCE_REQUIRED', 'SUSPENDED')
  AND (d.is_archived IS NULL OR d.is_archived = FALSE)
GROUP BY d.document_type
ORDER BY d.document_type;

-- ── 2. ESG supplier summary ───────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_esg_supplier_summary AS
SELECT
    s.id,
    s.company_name,
    s.country,
    s.status,
    s.business_size,
    s.employee_count,
    s.is_small_scale_farmer,
    s.esg_women_owned,
    s.esg_youth_owned,
    -- Key person counts
    COUNT(kp.id)                                                            AS key_person_count,
    COUNT(kp.id) FILTER (WHERE kp.gender = 'FEMALE')                       AS female_director_count,
    COUNT(kp.id) FILTER (
        WHERE (EXTRACT(YEAR FROM NOW()) - EXTRACT(YEAR FROM kp.date_of_birth)) < 35
    )                                                                        AS youth_director_count
FROM suppliers s
LEFT JOIN supplier_key_persons kp ON kp.supplier_id = s.id
GROUP BY
    s.id, s.company_name, s.country, s.status,
    s.business_size, s.employee_count, s.is_small_scale_farmer,
    s.esg_women_owned, s.esg_youth_owned;

-- ── 3. Category compliance distribution ──────────────────────────────────────
CREATE OR REPLACE VIEW vw_category_compliance AS
SELECT
    sc.category,
    COUNT(*)                                                                AS total_suppliers,
    COUNT(*) FILTER (WHERE sc.compliance_status = 'FULL_COMPLIANCE')       AS full_compliance_count,
    COUNT(*) FILTER (WHERE sc.compliance_status = 'MEDIUM_RISK')           AS medium_risk_count,
    COUNT(*) FILTER (WHERE sc.compliance_status = 'HIGH_RISK')             AS high_risk_count,
    COUNT(*) FILTER (WHERE sc.compliance_status = 'PENDING')               AS pending_count,
    COUNT(*) FILTER (WHERE sc.compliance_status = 'EXCLUDED')              AS excluded_count,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE sc.compliance_status = 'FULL_COMPLIANCE')
        / NULLIF(COUNT(*) FILTER (WHERE sc.compliance_status != 'EXCLUDED'), 0),
        1
    )                                                                       AS full_compliance_pct
FROM supplier_categories sc
JOIN suppliers s ON s.id = sc.supplier_id
WHERE s.status = 'APPROVED'
GROUP BY sc.category
ORDER BY sc.category;

-- ── 4. Business size distribution (for SME reporting) ────────────────────────
CREATE OR REPLACE VIEW vw_business_size_distribution AS
SELECT
    COALESCE(s.business_size, 'UNKNOWN') AS business_size,
    COUNT(*)                              AS supplier_count,
    COUNT(*) FILTER (WHERE s.status = 'APPROVED') AS approved_count
FROM suppliers s
GROUP BY s.business_size
ORDER BY
    CASE COALESCE(s.business_size, 'UNKNOWN')
        WHEN 'SMALL'   THEN 1
        WHEN 'MEDIUM'  THEN 2
        WHEN 'LARGE'   THEN 3
        ELSE 4
    END;
