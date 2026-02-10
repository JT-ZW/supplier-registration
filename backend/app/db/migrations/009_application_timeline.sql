-- Application Timeline Migration
-- Tracks supplier application status changes and history

-- ============================================================
-- Status History Table
-- ============================================================

CREATE TABLE IF NOT EXISTS supplier_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Supplier reference
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    
    -- Status change details
    old_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    
    -- Change metadata
    changed_by_type VARCHAR(20) NOT NULL CHECK (changed_by_type IN ('system', 'admin', 'vendor')),
    changed_by_id UUID,  -- admin_users.id or suppliers.id
    changed_by_name VARCHAR(255),
    
    -- Additional context
    reason TEXT,  -- Why the status changed
    admin_notes TEXT,  -- Admin's notes about this change
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    CONSTRAINT check_status_values CHECK (
        old_status IN ('INCOMPLETE', 'SUBMITTED', 'UNDER_REVIEW', 'NEED_MORE_INFO', 'APPROVED', 'REJECTED', 'SUSPENDED') OR old_status IS NULL
        AND new_status IN ('INCOMPLETE', 'SUBMITTED', 'UNDER_REVIEW', 'NEED_MORE_INFO', 'APPROVED', 'REJECTED', 'SUSPENDED')
    )
);

-- Indexes
CREATE INDEX idx_status_history_supplier ON supplier_status_history(supplier_id, created_at DESC);
CREATE INDEX idx_status_history_status ON supplier_status_history(new_status, created_at DESC);
CREATE INDEX idx_status_history_changed_by ON supplier_status_history(changed_by_type, changed_by_id);

-- ============================================================
-- Document Status History Table
-- ============================================================

CREATE TABLE IF NOT EXISTS document_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Document reference
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    
    -- Status change details
    old_verification_status VARCHAR(50),
    new_verification_status VARCHAR(50) NOT NULL,
    
    -- Change metadata
    changed_by_type VARCHAR(20) NOT NULL CHECK (changed_by_type IN ('system', 'admin', 'vendor')),
    changed_by_id UUID,
    changed_by_name VARCHAR(255),
    
    -- Additional context
    admin_notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT check_doc_status_values CHECK (
        old_verification_status IN ('PENDING', 'APPROVED', 'REJECTED') OR old_verification_status IS NULL
        AND new_verification_status IN ('PENDING', 'APPROVED', 'REJECTED')
    )
);

-- Indexes
CREATE INDEX idx_doc_history_document ON document_status_history(document_id, created_at DESC);
CREATE INDEX idx_doc_history_supplier ON document_status_history(supplier_id, created_at DESC);

-- ============================================================
-- Activity Log Table (for general supplier activities)
-- ============================================================

CREATE TABLE IF NOT EXISTS supplier_activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Supplier reference
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    
    -- Activity details
    activity_type VARCHAR(50) NOT NULL,  -- 'profile_updated', 'document_uploaded', 'message_sent', etc.
    activity_title VARCHAR(255) NOT NULL,
    activity_description TEXT,
    
    -- Actor
    actor_type VARCHAR(20) NOT NULL CHECK (actor_type IN ('system', 'admin', 'vendor')),
    actor_id UUID,
    actor_name VARCHAR(255),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_activity_log_supplier ON supplier_activity_log(supplier_id, created_at DESC);
CREATE INDEX idx_activity_log_type ON supplier_activity_log(activity_type, created_at DESC);
CREATE INDEX idx_activity_log_created ON supplier_activity_log(created_at DESC);

-- ============================================================
-- Triggers to Auto-Track Status Changes
-- ============================================================

-- Trigger to record supplier status changes
CREATE OR REPLACE FUNCTION track_supplier_status_change()
RETURNS TRIGGER AS $$
DECLARE
    v_changed_by_type VARCHAR(20);
    v_changed_by_id UUID;
    v_changed_by_name VARCHAR(255);
BEGIN
    -- Only track if status actually changed
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        -- Determine who made the change
        IF NEW.reviewed_by IS NOT NULL AND NEW.reviewed_by != OLD.reviewed_by THEN
            -- Changed by admin
            v_changed_by_type := 'admin';
            v_changed_by_id := NEW.reviewed_by;
            SELECT email INTO v_changed_by_name FROM admin_users WHERE id = NEW.reviewed_by;
        ELSIF NEW.status = 'SUBMITTED' AND OLD.status = 'INCOMPLETE' THEN
            -- Vendor submitted
            v_changed_by_type := 'vendor';
            v_changed_by_id := NEW.id;
            v_changed_by_name := NEW.company_name;
        ELSE
            -- System change
            v_changed_by_type := 'system';
            v_changed_by_id := NULL;
            v_changed_by_name := 'System';
        END IF;
        
        -- Record the status change
        INSERT INTO supplier_status_history (
            supplier_id,
            old_status,
            new_status,
            changed_by_type,
            changed_by_id,
            changed_by_name,
            admin_notes
        ) VALUES (
            NEW.id,
            OLD.status,
            NEW.status,
            v_changed_by_type,
            v_changed_by_id,
            v_changed_by_name,
            NEW.notes
        );
        
        -- Also log as activity
        INSERT INTO supplier_activity_log (
            supplier_id,
            activity_type,
            activity_title,
            activity_description,
            actor_type,
            actor_id,
            actor_name
        ) VALUES (
            NEW.id,
            'status_changed',
            'Application Status Updated',
            'Status changed from ' || COALESCE(OLD.status, 'NEW') || ' to ' || NEW.status,
            v_changed_by_type,
            v_changed_by_id,
            v_changed_by_name
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_track_supplier_status
    AFTER UPDATE ON suppliers
    FOR EACH ROW
    EXECUTE FUNCTION track_supplier_status_change();

-- Trigger to record document status changes
CREATE OR REPLACE FUNCTION track_document_status_change()
RETURNS TRIGGER AS $$
DECLARE
    v_changed_by_type VARCHAR(20);
    v_changed_by_id UUID;
    v_changed_by_name VARCHAR(255);
BEGIN
    -- Only track if verification status actually changed
    IF OLD.verification_status IS DISTINCT FROM NEW.verification_status THEN
        -- Determine who made the change
        IF NEW.verified_by IS NOT NULL AND NEW.verified_by != OLD.verified_by THEN
            -- Changed by admin
            v_changed_by_type := 'admin';
            v_changed_by_id := NEW.verified_by;
            SELECT email INTO v_changed_by_name FROM admin_users WHERE id = NEW.verified_by;
        ELSE
            -- System or vendor change
            v_changed_by_type := 'system';
            v_changed_by_id := NULL;
            v_changed_by_name := 'System';
        END IF;
        
        -- Record the status change
        INSERT INTO document_status_history (
            document_id,
            supplier_id,
            old_verification_status,
            new_verification_status,
            changed_by_type,
            changed_by_id,
            changed_by_name,
            admin_notes
        ) VALUES (
            NEW.id,
            NEW.supplier_id,
            OLD.verification_status,
            NEW.verification_status,
            v_changed_by_type,
            v_changed_by_id,
            v_changed_by_name,
            NEW.admin_notes
        );
        
        -- Also log as activity
        INSERT INTO supplier_activity_log (
            supplier_id,
            activity_type,
            activity_title,
            activity_description,
            actor_type,
            actor_id,
            actor_name,
            metadata
        ) VALUES (
            NEW.supplier_id,
            'document_status_changed',
            'Document Status Updated',
            'Document ' || NEW.document_type || ' status changed to ' || NEW.verification_status,
            v_changed_by_type,
            v_changed_by_id,
            v_changed_by_name,
            jsonb_build_object('document_id', NEW.id, 'document_type', NEW.document_type)
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_track_document_status
    AFTER UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION track_document_status_change();

-- Trigger to log document uploads
CREATE OR REPLACE FUNCTION track_document_upload()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO supplier_activity_log (
        supplier_id,
        activity_type,
        activity_title,
        activity_description,
        actor_type,
        actor_id,
        actor_name,
        metadata
    ) VALUES (
        NEW.supplier_id,
        'document_uploaded',
        'Document Uploaded',
        'Uploaded ' || NEW.document_type,
        'vendor',
        NEW.supplier_id,
        (SELECT company_name FROM suppliers WHERE id = NEW.supplier_id),
        jsonb_build_object('document_id', NEW.id, 'document_type', NEW.document_type)
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_track_document_upload
    AFTER INSERT ON documents
    FOR EACH ROW
    EXECUTE FUNCTION track_document_upload();

-- ============================================================
-- Functions
-- ============================================================

-- Function to get complete timeline for a supplier
CREATE OR REPLACE FUNCTION get_supplier_timeline(
    p_supplier_id UUID,
    p_limit INTEGER DEFAULT 50
)
RETURNS TABLE(
    id UUID,
    event_type VARCHAR(50),
    event_title VARCHAR(255),
    event_description TEXT,
    actor_type VARCHAR(20),
    actor_name VARCHAR(255),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    WITH combined_events AS (
        -- Status changes
        SELECT 
            ssh.id,
            'status_change'::VARCHAR(50) as event_type,
            'Status Changed'::VARCHAR(255) as event_title,
            ('Status changed from ' || COALESCE(ssh.old_status, 'NEW') || ' to ' || ssh.new_status || 
             CASE WHEN ssh.admin_notes IS NOT NULL THEN E'\nNotes: ' || ssh.admin_notes ELSE '' END)::TEXT as event_description,
            ssh.changed_by_type as actor_type,
            ssh.changed_by_name as actor_name,
            jsonb_build_object(
                'old_status', ssh.old_status,
                'new_status', ssh.new_status,
                'reason', ssh.reason,
                'admin_notes', ssh.admin_notes
            ) as metadata,
            ssh.created_at
        FROM supplier_status_history ssh
        WHERE ssh.supplier_id = p_supplier_id
        
        UNION ALL
        
        -- Document status changes
        SELECT 
            dsh.id,
            'document_status_change'::VARCHAR(50) as event_type,
            'Document Status Updated'::VARCHAR(255) as event_title,
            ('Document status changed to ' || dsh.new_verification_status ||
             CASE WHEN dsh.admin_notes IS NOT NULL THEN E'\nNotes: ' || dsh.admin_notes ELSE '' END)::TEXT as event_description,
            dsh.changed_by_type as actor_type,
            dsh.changed_by_name as actor_name,
            jsonb_build_object(
                'document_id', dsh.document_id,
                'old_status', dsh.old_verification_status,
                'new_status', dsh.new_verification_status,
                'admin_notes', dsh.admin_notes
            ) as metadata,
            dsh.created_at
        FROM document_status_history dsh
        WHERE dsh.supplier_id = p_supplier_id
        
        UNION ALL
        
        -- General activities
        SELECT 
            sal.id,
            sal.activity_type,
            sal.activity_title,
            sal.activity_description,
            sal.actor_type,
            sal.actor_name,
            sal.metadata,
            sal.created_at
        FROM supplier_activity_log sal
        WHERE sal.supplier_id = p_supplier_id
    )
    SELECT 
        ce.id,
        ce.event_type,
        ce.event_title,
        ce.event_description,
        ce.actor_type,
        ce.actor_name,
        ce.metadata,
        ce.created_at
    FROM combined_events ce
    ORDER BY ce.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get status history for a supplier
CREATE OR REPLACE FUNCTION get_supplier_status_history(
    p_supplier_id UUID
)
RETURNS TABLE(
    id UUID,
    old_status VARCHAR(50),
    new_status VARCHAR(50),
    changed_by_type VARCHAR(20),
    changed_by_name VARCHAR(255),
    reason TEXT,
    admin_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ssh.id,
        ssh.old_status,
        ssh.new_status,
        ssh.changed_by_type,
        ssh.changed_by_name,
        ssh.reason,
        ssh.admin_notes,
        ssh.created_at
    FROM supplier_status_history ssh
    WHERE ssh.supplier_id = p_supplier_id
    ORDER BY ssh.created_at DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to log custom activity
CREATE OR REPLACE FUNCTION log_supplier_activity(
    p_supplier_id UUID,
    p_activity_type VARCHAR(50),
    p_activity_title VARCHAR(255),
    p_activity_description TEXT,
    p_actor_type VARCHAR(20),
    p_actor_id UUID,
    p_actor_name VARCHAR(255),
    p_metadata JSONB DEFAULT '{}'
)
RETURNS UUID AS $$
DECLARE
    v_activity_id UUID;
BEGIN
    INSERT INTO supplier_activity_log (
        supplier_id,
        activity_type,
        activity_title,
        activity_description,
        actor_type,
        actor_id,
        actor_name,
        metadata
    ) VALUES (
        p_supplier_id,
        p_activity_type,
        p_activity_title,
        p_activity_description,
        p_actor_type,
        p_actor_id,
        p_actor_name,
        p_metadata
    )
    RETURNING id INTO v_activity_id;
    
    RETURN v_activity_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Backfill Historical Data
-- ============================================================

-- Create initial status history entries for existing suppliers
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT id, status, created_at, company_name FROM suppliers LOOP
        -- Insert creation record
        INSERT INTO supplier_status_history (
            supplier_id,
            old_status,
            new_status,
            changed_by_type,
            changed_by_id,
            changed_by_name,
            created_at
        ) VALUES (
            r.id,
            NULL,
            'INCOMPLETE',
            'system',
            NULL,
            'System',
            r.created_at
        );
        
        -- If status is not INCOMPLETE, add another entry
        IF r.status != 'INCOMPLETE' THEN
            INSERT INTO supplier_status_history (
                supplier_id,
                old_status,
                new_status,
                changed_by_type,
                changed_by_id,
                changed_by_name,
                created_at
            ) VALUES (
                r.id,
                'INCOMPLETE',
                r.status,
                'system',
                NULL,
                'System',
                r.created_at + INTERVAL '1 second'
            );
        END IF;
        
        -- Log creation activity
        INSERT INTO supplier_activity_log (
            supplier_id,
            activity_type,
            activity_title,
            activity_description,
            actor_type,
            actor_id,
            actor_name,
            created_at
        ) VALUES (
            r.id,
            'supplier_registered',
            'Supplier Registered',
            'New supplier registration: ' || r.company_name,
            'vendor',
            r.id,
            r.company_name,
            r.created_at
        );
    END LOOP;
END $$;

-- ============================================================
-- Comments
-- ============================================================

COMMENT ON TABLE supplier_status_history IS 'Tracks all supplier application status changes';
COMMENT ON TABLE document_status_history IS 'Tracks all document verification status changes';
COMMENT ON TABLE supplier_activity_log IS 'General activity log for supplier actions and events';
COMMENT ON FUNCTION get_supplier_timeline IS 'Retrieve complete timeline of events for a supplier';
COMMENT ON FUNCTION get_supplier_status_history IS 'Get status change history for a supplier';
COMMENT ON FUNCTION log_supplier_activity IS 'Manually log a supplier activity event';
