-- Migration 004: Audit Logs System
-- Creates tables for tracking all system activities
-- Run Date: 2026-01-26

-- ============================================
-- Drop existing table if needed (for clean migration)
-- ============================================
DROP TABLE IF EXISTS audit_logs CASCADE;

-- ============================================
-- Audit Logs Table
-- ============================================
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- User information (separate columns for admin vs supplier)
    admin_id UUID NULL,  -- References admin_users(id)
    supplier_id UUID NULL,  -- References suppliers(id)
    user_type VARCHAR(20) NOT NULL CHECK (user_type IN ('admin', 'vendor', 'system')),
    user_email VARCHAR(255) NULL,  -- Denormalized for quick access
    user_name VARCHAR(255) NULL,   -- Denormalized for quick access
    
    -- Action information
    action VARCHAR(100) NOT NULL,
    action_description TEXT NULL,
    
    -- Resource information
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID NULL,
    resource_name VARCHAR(255) NULL,  -- Denormalized (e.g., company name)
    
    -- Change tracking
    changes JSONB NULL,  -- { "field": { "old": "value", "new": "value" } }
    metadata JSONB NULL,  -- Additional context
    
    -- Request information
    ip_address INET NULL,
    user_agent TEXT NULL,
    request_path VARCHAR(500) NULL,
    request_method VARCHAR(10) NULL,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- Indexes for Performance
-- ============================================

-- Index for user activity lookups
CREATE INDEX idx_audit_logs_admin_id ON audit_logs(admin_id);
CREATE INDEX idx_audit_logs_supplier_id ON audit_logs(supplier_id);
CREATE INDEX idx_audit_logs_user_type ON audit_logs(user_type);

-- Index for resource tracking
CREATE INDEX idx_audit_logs_resource_type ON audit_logs(resource_type);
CREATE INDEX idx_audit_logs_resource_id ON audit_logs(resource_id);
CREATE INDEX idx_audit_logs_resource_type_id ON audit_logs(resource_type, resource_id);

-- Index for action filtering
CREATE INDEX idx_audit_logs_action ON audit_logs(action);

-- Index for time-based queries (most common)
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- Composite indexes for common query patterns
CREATE INDEX idx_audit_logs_admin_created ON audit_logs(admin_id, created_at DESC);
CREATE INDEX idx_audit_logs_supplier_created ON audit_logs(supplier_id, created_at DESC);
CREATE INDEX idx_audit_logs_resource_created ON audit_logs(resource_type, resource_id, created_at DESC);

-- GIN index for JSONB columns (for searching within changes/metadata)
CREATE INDEX idx_audit_logs_changes ON audit_logs USING GIN (changes);
CREATE INDEX idx_audit_logs_metadata ON audit_logs USING GIN (metadata);

-- ============================================
-- Helper Functions
-- ============================================

-- Function to get audit trail for a specific supplier
CREATE OR REPLACE FUNCTION get_supplier_audit_trail(supplier_uuid UUID)
RETURNS TABLE (
    id UUID,
    user_name VARCHAR(255),
    action VARCHAR(100),
    action_description TEXT,
    changes JSONB,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        al.id,
        al.user_name,
        al.action,
        al.action_description,
        al.changes,
        al.created_at
    FROM audit_logs al
    WHERE al.resource_type = 'supplier' 
      AND al.resource_id = supplier_uuid
    ORDER BY al.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get recent activity (for dashboard)
CREATE OR REPLACE FUNCTION get_recent_activity(days_back INTEGER DEFAULT 7, limit_count INTEGER DEFAULT 50)
RETURNS TABLE (
    id UUID,
    user_name VARCHAR(255),
    user_type VARCHAR(20),
    action VARCHAR(100),
    resource_type VARCHAR(50),
    resource_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        al.id,
        al.user_name,
        al.user_type,
        al.action,
        al.resource_type,
        al.resource_name,
        al.created_at
    FROM audit_logs al
    WHERE al.created_at >= NOW() - (days_back || ' days')::INTERVAL
    ORDER BY al.created_at DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get action statistics
CREATE OR REPLACE FUNCTION get_audit_statistics(
    start_date TIMESTAMP WITH TIME ZONE DEFAULT NOW() - INTERVAL '30 days',
    end_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
)
RETURNS TABLE (
    action VARCHAR(100),
    count BIGINT,
    last_occurrence TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        al.action,
        COUNT(*) as count,
        MAX(al.created_at) as last_occurrence
    FROM audit_logs al
    WHERE al.created_at BETWEEN start_date AND end_date
    GROUP BY al.action
    ORDER BY count DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Data Retention Policy (Optional)
-- ============================================

-- Function to archive old audit logs (run via cron/scheduler)
CREATE OR REPLACE FUNCTION archive_old_audit_logs(months_to_keep INTEGER DEFAULT 24)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- In production, you might want to move to archive table instead of delete
    DELETE FROM audit_logs
    WHERE created_at < NOW() - (months_to_keep || ' months')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Triggers for Auto-population
-- ============================================

-- Trigger to automatically populate user details from admin_users
CREATE OR REPLACE FUNCTION populate_audit_user_details()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.user_type = 'admin' AND NEW.admin_id IS NOT NULL THEN
        SELECT email, full_name INTO NEW.user_email, NEW.user_name
        FROM admin_users
        WHERE id = NEW.admin_id;
    ELSIF NEW.user_type = 'vendor' AND NEW.supplier_id IS NOT NULL THEN
        SELECT email, contact_person_name INTO NEW.user_email, NEW.user_name
        FROM suppliers
        WHERE id = NEW.supplier_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_populate_audit_user_details
    BEFORE INSERT ON audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION populate_audit_user_details();

-- ============================================
-- Comments for Documentation
-- ============================================

COMMENT ON TABLE audit_logs IS 'Comprehensive audit trail of all system activities';
COMMENT ON COLUMN audit_logs.admin_id IS 'ID of admin user who performed the action (NULL if not admin)';
COMMENT ON COLUMN audit_logs.supplier_id IS 'ID of supplier/vendor who performed the action (NULL if not vendor)';
COMMENT ON COLUMN audit_logs.user_type IS 'Type of user: admin, vendor, or system';
COMMENT ON COLUMN audit_logs.action IS 'Action performed (e.g., supplier_approved, document_uploaded)';
COMMENT ON COLUMN audit_logs.resource_type IS 'Type of resource affected (e.g., supplier, document, admin)';
COMMENT ON COLUMN audit_logs.resource_id IS 'ID of the affected resource';
COMMENT ON COLUMN audit_logs.changes IS 'JSON object tracking before/after values for updates';
COMMENT ON COLUMN audit_logs.metadata IS 'Additional context about the action';
COMMENT ON COLUMN audit_logs.ip_address IS 'IP address of the request';
COMMENT ON COLUMN audit_logs.user_agent IS 'Browser/client user agent string';

-- ============================================
-- Sample Query Examples (for reference)
-- ============================================

-- Get all actions on a specific supplier
-- SELECT * FROM get_supplier_audit_trail('supplier-uuid-here');

-- Get recent activity for dashboard
-- SELECT * FROM get_recent_activity(7, 50);

-- Get action statistics for last 30 days
-- SELECT * FROM get_audit_statistics();

-- Find all document approvals
-- SELECT * FROM audit_logs WHERE action = 'document_verified' ORDER BY created_at DESC;

-- Find all actions by specific admin
-- SELECT * FROM audit_logs WHERE admin_id = 'admin-uuid' ORDER BY created_at DESC;

-- Find all actions by specific supplier/vendor
-- SELECT * FROM audit_logs WHERE supplier_id = 'supplier-uuid' ORDER BY created_at DESC;

-- Search for specific changes
-- SELECT * FROM audit_logs WHERE changes @> '{"status": {"new": "approved"}}';

-- Get most active users
-- SELECT user_name, COUNT(*) as action_count 
-- FROM audit_logs 
-- WHERE created_at >= NOW() - INTERVAL '30 days'
-- GROUP BY user_name 
-- ORDER BY action_count DESC 
-- LIMIT 10;
