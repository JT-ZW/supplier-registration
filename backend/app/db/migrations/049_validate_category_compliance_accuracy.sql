-- Validation script: Category compliance accuracy checks
--
-- Run after applying migration 048 and reloading the sustainability overview.

-- 1) Approved suppliers by primary category (source table)
SELECT
    s.business_category AS category,
    COUNT(*) AS approved_suppliers
FROM suppliers s
WHERE s.status = 'APPROVED'
GROUP BY s.business_category
ORDER BY approved_suppliers DESC, category;

-- 2) Approved suppliers missing ANY supplier_categories rows (should be 0)
SELECT
    COUNT(*) AS approved_without_categories
FROM suppliers s
WHERE s.status = 'APPROVED'
  AND NOT EXISTS (
      SELECT 1
      FROM supplier_categories sc
      WHERE sc.supplier_id = s.id
  );

-- 3) Approved suppliers missing their PRIMARY category row (should be 0)
SELECT
    COUNT(*) AS approved_missing_primary_category_row
FROM suppliers s
WHERE s.status = 'APPROVED'
  AND s.business_category IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM supplier_categories sc
      WHERE sc.supplier_id = s.id
                AND sc.category = s.business_category::TEXT
  );

-- 4) Raw category compliance counts from supplier_categories (approved scope)
SELECT
    sc.category,
    COUNT(*) AS total_suppliers,
    COUNT(*) FILTER (WHERE sc.compliance_status = 'FULL_COMPLIANCE') AS full_compliance_count,
    COUNT(*) FILTER (WHERE sc.compliance_status = 'MEDIUM_RISK') AS medium_risk_count,
    COUNT(*) FILTER (WHERE sc.compliance_status = 'HIGH_RISK') AS high_risk_count,
    COUNT(*) FILTER (WHERE sc.compliance_status = 'PENDING') AS pending_count,
    COUNT(*) FILTER (WHERE sc.compliance_status = 'EXCLUDED') AS excluded_count
FROM supplier_categories sc
JOIN suppliers s ON s.id = sc.supplier_id
WHERE s.status = 'APPROVED'
GROUP BY sc.category
ORDER BY total_suppliers DESC, sc.category;

-- 5) Compare view output directly to expected raw counts (should match row-by-row)
WITH expected AS (
    SELECT
        sc.category,
        COUNT(*) AS total_suppliers,
        COUNT(*) FILTER (WHERE sc.compliance_status = 'FULL_COMPLIANCE') AS full_compliance_count,
        COUNT(*) FILTER (WHERE sc.compliance_status = 'MEDIUM_RISK') AS medium_risk_count,
        COUNT(*) FILTER (WHERE sc.compliance_status = 'HIGH_RISK') AS high_risk_count,
        COUNT(*) FILTER (WHERE sc.compliance_status = 'PENDING') AS pending_count,
        COUNT(*) FILTER (WHERE sc.compliance_status = 'EXCLUDED') AS excluded_count
    FROM supplier_categories sc
    JOIN suppliers s ON s.id = sc.supplier_id
    WHERE s.status = 'APPROVED'
    GROUP BY sc.category
)
SELECT
    COALESCE(e.category, v.category) AS category,
    e.total_suppliers AS expected_total,
    v.total_suppliers AS view_total,
    e.full_compliance_count AS expected_full,
    v.full_compliance_count AS view_full,
    e.medium_risk_count AS expected_medium,
    v.medium_risk_count AS view_medium,
    e.high_risk_count AS expected_high,
    v.high_risk_count AS view_high,
    e.pending_count AS expected_pending,
    v.pending_count AS view_pending,
    e.excluded_count AS expected_excluded,
    v.excluded_count AS view_excluded
FROM expected e
FULL OUTER JOIN vw_category_compliance v
  ON v.category = e.category
ORDER BY category;
