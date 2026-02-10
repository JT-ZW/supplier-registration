-- Performance Optimization Migration
-- Adds composite indexes, optimizes existing queries, and adds caching support

-- ============================================================
-- Enable Required Extensions First
-- ============================================================

-- Enable trigram extension for better text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- Composite Indexes for Common Query Patterns
-- ============================================================

-- Composite index for supplier list filtering (status + created_at)
-- Optimizes queries that filter by status and order by date
CREATE INDEX IF NOT EXISTS idx_suppliers_status_created 
ON suppliers(status, created_at DESC) 
WHERE status IS NOT NULL;

-- Composite index for category filtering with status
-- Optimizes queries that filter by both category and status
CREATE INDEX IF NOT EXISTS idx_suppliers_category_status 
ON suppliers(business_category, status);

-- Composite index for search operations using trigrams
-- Optimizes LIKE queries on company names
CREATE INDEX IF NOT EXISTS idx_suppliers_company_name_trgm 
ON suppliers USING gin (company_name gin_trgm_ops);

-- Composite index for email search using trigrams
CREATE INDEX IF NOT EXISTS idx_suppliers_email_trgm 
ON suppliers USING gin (email gin_trgm_ops);

-- ============================================================
-- Document Performance Indexes
-- ============================================================

-- Composite index for document queries by supplier and status
CREATE INDEX IF NOT EXISTS idx_documents_supplier_status 
ON documents(supplier_id, verification_status);

-- Index for document type queries
CREATE INDEX IF NOT EXISTS idx_documents_type 
ON documents(document_type);

-- ============================================================
-- Audit Log Performance Indexes
-- ============================================================

-- Composite index for admin activity queries
CREATE INDEX IF NOT EXISTS idx_audit_logs_admin_created 
ON audit_logs(admin_id, created_at DESC);

-- Index for resource-based audit queries
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource 
ON audit_logs(resource_type, resource_id);

-- ============================================================
-- Notification Performance Indexes
-- (Already created in 005_notifications.sql, but adding notes)
-- ============================================================

-- Notes: Notification indexes are already optimized with:
-- - idx_notifications_recipient (recipient_id, recipient_type)
-- - idx_notifications_unread (recipient_id, is_read)
-- - idx_notifications_created_at

-- ============================================================
-- Statistics and Materialized Views
-- ============================================================

-- Create materialized view for dashboard statistics
-- This avoids expensive aggregation queries on every dashboard load
CREATE MATERIALIZED VIEW IF NOT EXISTS supplier_statistics AS
SELECT 
    COUNT(*) as total_suppliers,
    COUNT(*) FILTER (WHERE status = 'APPROVED') as approved_count,
    COUNT(*) FILTER (WHERE status = 'UNDER_REVIEW') as under_review_count,
    COUNT(*) FILTER (WHERE status = 'SUBMITTED') as submitted_count,
    COUNT(*) FILTER (WHERE status = 'REJECTED') as rejected_count,
    COUNT(*) FILTER (WHERE status = 'INCOMPLETE') as incomplete_count,
    COUNT(*) FILTER (WHERE status = 'NEED_MORE_INFO') as need_more_info_count,
    MAX(created_at) as last_registration_date
FROM suppliers;

-- Index on the materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_supplier_statistics 
ON supplier_statistics ((1));

-- Function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_supplier_statistics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY supplier_statistics;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Query Optimization Functions
-- ============================================================

-- Optimized function to get supplier count by status
CREATE OR REPLACE FUNCTION get_supplier_count_by_status_optimized()
RETURNS TABLE(status supplier_status, count bigint) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.status,
        COUNT(*)::bigint
    FROM suppliers s
    WHERE s.status IS NOT NULL
    GROUP BY s.status
    ORDER BY s.status;
END;
$$ LANGUAGE plpgsql STABLE;

-- Optimized function to search suppliers
CREATE OR REPLACE FUNCTION search_suppliers(
    search_term TEXT,
    result_limit INTEGER DEFAULT 20
)
RETURNS TABLE(
    id UUID,
    company_name VARCHAR(200),
    email VARCHAR(255),
    status supplier_status,
    similarity REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id,
        s.company_name,
        s.email,
        s.status,
        GREATEST(
            similarity(s.company_name, search_term),
            similarity(s.email, search_term),
            similarity(s.contact_person_name, search_term)
        ) as sim
    FROM suppliers s
    WHERE 
        s.company_name % search_term OR
        s.email % search_term OR
        s.contact_person_name % search_term
    ORDER BY sim DESC
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Vacuum and Analyze Automation
-- ============================================================

-- Add comments for maintenance
COMMENT ON TABLE suppliers IS 'Main supplier table - consider VACUUM ANALYZE weekly';
COMMENT ON TABLE documents IS 'Document storage table - consider VACUUM ANALYZE bi-weekly';
COMMENT ON TABLE audit_logs IS 'Audit log table - grows quickly, consider partitioning';
COMMENT ON TABLE notifications IS 'Notification table - cleanup old records with cleanup_old_notifications()';

-- ============================================================
-- Performance Monitoring Views
-- ============================================================

-- View to monitor slow queries (requires pg_stat_statements extension)
-- CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- View for table sizes
CREATE OR REPLACE VIEW table_sizes AS
SELECT
    t.schemaname,
    t.tablename,
    pg_size_pretty(pg_total_relation_size(quote_ident(t.schemaname)||'.'||quote_ident(t.tablename))) AS size,
    pg_total_relation_size(quote_ident(t.schemaname)||'.'||quote_ident(t.tablename)) AS size_bytes
FROM pg_tables t
WHERE t.schemaname = 'public'
ORDER BY pg_total_relation_size(quote_ident(t.schemaname)||'.'||quote_ident(t.tablename)) DESC;

-- View for index usage
CREATE OR REPLACE VIEW index_usage AS
SELECT
    i.schemaname,
    i.relname as tablename,
    i.indexrelname as indexname,
    i.idx_scan as index_scans,
    i.idx_tup_read as tuples_read,
    i.idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes i
ORDER BY i.idx_scan DESC;

-- ============================================================
-- Connection Pooling Recommendations
-- ============================================================

-- Recommended settings (to be applied in postgresql.conf or connection string):
-- max_connections = 100
-- shared_buffers = 256MB (25% of RAM)
-- effective_cache_size = 1GB (50-75% of RAM)
-- maintenance_work_mem = 64MB
-- checkpoint_completion_target = 0.9
-- wal_buffers = 16MB
-- default_statistics_target = 100
-- random_page_cost = 1.1 (for SSD)
-- effective_io_concurrency = 200 (for SSD)
-- work_mem = 4MB

COMMENT ON SCHEMA public IS 'Performance optimizations applied. See migration 006 for details.';
