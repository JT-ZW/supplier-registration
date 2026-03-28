-- Migration: Backfill timeline for existing suppliers
-- Date: 2026-02-11
-- Description: Ensures all existing suppliers have timeline entries for their current status

-- ============================================================
-- Backfill function to create timeline entries for existing suppliers
-- ============================================================

CREATE OR REPLACE FUNCTION backfill_supplier_timeline()
RETURNS void AS $$
DECLARE
    supplier_record RECORD;
    initial_event_exists BOOLEAN;
BEGIN
    -- Loop through all suppliers
    FOR supplier_record IN 
        SELECT 
            id,
            status,
            company_name,
            created_at,
            reviewed_by,
            submitted_at,
            reviewed_at
        FROM suppliers
        ORDER BY created_at ASC
    LOOP
        -- Check if supplier has any timeline events
        SELECT EXISTS(
            SELECT 1 FROM supplier_status_history 
            WHERE supplier_id = supplier_record.id
        ) INTO initial_event_exists;
        
        IF NOT initial_event_exists THEN
            -- Create initial "created" event
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
                supplier_record.id,
                'application_created',
                'Application Created',
                'Supplier application was created',
                'vendor',
                supplier_record.id,
                supplier_record.company_name,
                supplier_record.created_at
            );
            
            -- If submitted, add submission event
            IF supplier_record.submitted_at IS NOT NULL THEN
                INSERT INTO supplier_status_history (
                    supplier_id,
                    old_status,
                    new_status,
                    changed_by_type,
                    changed_by_id,
                    changed_by_name,
                    created_at
                ) VALUES (
                    supplier_record.id,
                    'INCOMPLETE',
                    'SUBMITTED',
                    'vendor',
                    supplier_record.id,
                    supplier_record.company_name,
                    supplier_record.submitted_at
                );
                
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
                    supplier_record.id,
                    'application_submitted',
                    'Application Submitted',
                    'Supplier submitted their application for review',
                    'vendor',
                    supplier_record.id,
                    supplier_record.company_name,
                    supplier_record.submitted_at
                );
            END IF;
            
            -- If approved or rejected, add review event
            IF supplier_record.status IN ('APPROVED', 'REJECTED', 'UNDER_REVIEW', 'NEED_MORE_INFO') 
               AND supplier_record.reviewed_at IS NOT NULL THEN
                DECLARE
                    admin_name VARCHAR(255);
                    prev_status VARCHAR(50);
                BEGIN
                    -- Get admin name
                    IF supplier_record.reviewed_by IS NOT NULL THEN
                        SELECT email INTO admin_name 
                        FROM admin_users 
                        WHERE id = supplier_record.reviewed_by;
                    END IF;
                    
                    -- Determine previous status
                    IF supplier_record.status = 'APPROVED' OR supplier_record.status = 'REJECTED' THEN
                        prev_status := 'UNDER_REVIEW';
                    ELSIF supplier_record.status = 'UNDER_REVIEW' THEN
                        prev_status := 'SUBMITTED';
                    ELSE
                        prev_status := 'SUBMITTED';
                    END IF;
                    
                    INSERT INTO supplier_status_history (
                        supplier_id,
                        old_status,
                        new_status,
                        changed_by_type,
                        changed_by_id,
                        changed_by_name,
                        created_at
                    ) VALUES (
                        supplier_record.id,
                        prev_status,
                        supplier_record.status,
                        CASE 
                            WHEN supplier_record.reviewed_by IS NOT NULL THEN 'admin'
                            ELSE 'system'
                        END,
                        supplier_record.reviewed_by,
                        COALESCE(admin_name, 'Admin'),
                        supplier_record.reviewed_at
                    );
                    
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
                        supplier_record.id,
                        CASE 
                            WHEN supplier_record.status = 'APPROVED' THEN 'application_approved'
                            WHEN supplier_record.status = 'REJECTED' THEN 'application_rejected'
                            ELSE 'status_changed'
                        END,
                        CASE 
                            WHEN supplier_record.status = 'APPROVED' THEN 'Application Approved'
                            WHEN supplier_record.status = 'REJECTED' THEN 'Application Rejected'
                            ELSE 'Application Status Updated'
                        END,
                        'Application status changed to ' || supplier_record.status,
                        CASE 
                            WHEN supplier_record.reviewed_by IS NOT NULL THEN 'admin'
                            ELSE 'system'
                        END,
                        supplier_record.reviewed_by,
                        COALESCE(admin_name, 'Admin'),
                        supplier_record.reviewed_at
                    );
                END;
            END IF;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Execute the backfill
-- ============================================================

-- Run the backfill function
SELECT backfill_supplier_timeline();

-- Drop the function (it's only needed for this migration)
DROP FUNCTION backfill_supplier_timeline();

-- ============================================================
-- Verification
-- ============================================================

-- Check timeline counts
-- SELECT 
--     s.company_name,
--     s.status,
--     (SELECT COUNT(*) FROM supplier_status_history WHERE supplier_id = s.id) as status_changes,
--     (SELECT COUNT(*) FROM supplier_activity_log WHERE supplier_id = s.id) as activities
-- FROM suppliers s
-- ORDER BY s.created_at DESC
-- LIMIT 10;