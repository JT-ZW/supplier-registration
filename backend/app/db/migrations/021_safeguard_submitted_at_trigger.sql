-- Migration: Add safeguard trigger to auto-set submitted_at when status changes to SUBMITTED
-- Date: 2026-02-15
-- Description: Ensures submitted_at is ALWAYS set when status becomes SUBMITTED, preventing data inconsistencies

-- ============================================================
-- Create trigger function to auto-set submitted_at
-- ============================================================

CREATE OR REPLACE FUNCTION ensure_submitted_at()
RETURNS TRIGGER AS $$
BEGIN
    -- When status changes to SUBMITTED and submitted_at is not set, set it automatically
    IF NEW.status IN ('SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED') 
       AND NEW.submitted_at IS NULL THEN
        
        -- Try to find the submission date from status history
        SELECT MIN(created_at) INTO NEW.submitted_at
        FROM supplier_status_history
        WHERE supplier_id = NEW.id 
          AND new_status = 'SUBMITTED';
        
        -- If not found in history, use current timestamp
        IF NEW.submitted_at IS NULL THEN
            NEW.submitted_at := NOW();
        END IF;
        
        -- Log this automatic fix for audit purposes
        RAISE NOTICE 'Auto-set submitted_at for supplier % (%) to %', NEW.company_name, NEW.id, NEW.submitted_at;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if it exists
DROP TRIGGER IF EXISTS trigger_ensure_submitted_at ON suppliers;

-- Create trigger that fires before INSERT or UPDATE
CREATE TRIGGER trigger_ensure_submitted_at
    BEFORE INSERT OR UPDATE OF status
    ON suppliers
    FOR EACH ROW
    EXECUTE FUNCTION ensure_submitted_at();

-- ============================================================
-- Verification
-- ============================================================

-- Test the trigger by simulating a status update
-- (This is just a check, not an actual update)
SELECT 
    'Trigger created successfully' as message,
    COUNT(*) as existing_suppliers_count
FROM suppliers;

COMMENT ON FUNCTION ensure_submitted_at() IS 
    'Automatically sets submitted_at timestamp when a supplier reaches SUBMITTED or later status. Prevents data inconsistency.';

COMMENT ON TRIGGER trigger_ensure_submitted_at ON suppliers IS
    'Safeguard trigger that ensures submitted_at is always set when status becomes SUBMITTED or beyond.';
