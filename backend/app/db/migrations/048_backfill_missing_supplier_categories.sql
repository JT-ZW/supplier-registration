-- Migration 048: Backfill missing supplier_categories for approved-scope suppliers
--
-- Problem:
-- Some suppliers may exist without supplier_categories rows (legacy records or
-- partial writes). Those suppliers are excluded from vw_category_compliance,
-- causing inaccurate category distribution totals.
--
-- Fix:
-- Ensure each approved-scope supplier has at least their primary
-- suppliers.business_category represented in supplier_categories.

INSERT INTO supplier_categories (supplier_id, category, compliance_status)
SELECT
    s.id,
    s.business_category::TEXT,
    'PENDING'
FROM suppliers s
WHERE s.business_category IS NOT NULL
  AND s.status IN ('APPROVED', 'COMPLIANCE_REQUIRED', 'SUSPENDED')
  AND NOT EXISTS (
      SELECT 1
      FROM supplier_categories sc
      WHERE sc.supplier_id = s.id
        AND sc.category = s.business_category::TEXT
  )
ON CONFLICT (supplier_id, category) DO NOTHING;

-- Optional validation queries:
-- 1) Suppliers in scope still missing any category rows
-- SELECT COUNT(*)
-- FROM suppliers s
-- WHERE s.status IN ('APPROVED', 'COMPLIANCE_REQUIRED', 'SUSPENDED')
--   AND NOT EXISTS (SELECT 1 FROM supplier_categories sc WHERE sc.supplier_id = s.id);
--
-- 2) Category coverage after backfill
-- SELECT category, COUNT(*) AS rows
-- FROM supplier_categories
-- GROUP BY category
-- ORDER BY rows DESC;