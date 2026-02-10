-- Migration: Fix trigger field name mismatches
-- Date: 2026-02-06
-- Description: Fixes triggers that reference incorrect field names

-- ============================================================
-- Fix Supplier Status Change Trigger
-- ============================================================
-- The trigger was trying to access NEW.notes but the suppliers 
-- table actually has admin_notes field

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
        -- FIXED: Changed NEW.notes to NEW.admin_notes
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
            NEW.admin_notes  -- FIXED: was NEW.notes
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
            'Status changed from ' || COALESCE(OLD.status::text, 'NEW') || ' to ' || NEW.status::text,
            v_changed_by_type,
            v_changed_by_id,
            v_changed_by_name
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Fix Document Status Change Trigger  
-- ============================================================
-- The trigger was trying to access NEW.admin_notes but the documents
-- table actually has verification_comments field

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
        -- FIXED: Changed NEW.admin_notes to NEW.verification_comments
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
            NEW.verification_comments  -- FIXED: was NEW.admin_notes
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
