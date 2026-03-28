-- Migration 050: Sustainability reporting performance indexes
--
-- Goal:
-- Speed up the sustainability dashboard read paths by indexing the
-- most frequently joined and filtered columns used by:
--   - vw_esg_supplier_summary
--   - vw_category_compliance
--   - vw_document_type_stats
--   - vw_business_size_distribution

-- Suppliers: fast status filtering for approved-scope reads.
CREATE INDEX IF NOT EXISTS idx_suppliers_status
ON suppliers (status);

-- Suppliers: helps status + business size filters used by overview/supplier list.
CREATE INDEX IF NOT EXISTS idx_suppliers_status_business_size
ON suppliers (status, business_size);

-- Supplier key persons: improves join and grouped counts per supplier.
CREATE INDEX IF NOT EXISTS idx_supplier_key_persons_supplier_id
ON supplier_key_persons (supplier_id);

-- Supplier categories: improves joins and category compliance aggregation.
CREATE INDEX IF NOT EXISTS idx_supplier_categories_supplier_id
ON supplier_categories (supplier_id);

CREATE INDEX IF NOT EXISTS idx_supplier_categories_category_status
ON supplier_categories (category, compliance_status);

-- Documents: improves approved-scope document compliance stats joins.
CREATE INDEX IF NOT EXISTS idx_documents_supplier_verification_archived_type
ON documents (supplier_id, verification_status, is_archived, document_type);
