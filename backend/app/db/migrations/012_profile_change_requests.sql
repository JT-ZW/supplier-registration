-- Profile Change Approval Workflow Migration
-- Allows vendors to request profile changes that require admin approval

-- ============================================================
-- Profile Change Requests Table
-- ============================================================

CREATE TABLE IF NOT EXISTS profile_change_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- References
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    
    -- Change data (stored as JSONB for flexibility)
    requested_changes JSONB NOT NULL,  -- New values vendor wants to change to
    current_values JSONB NOT NULL,     -- Current values at time of request
    
    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')),
    
    -- Review details
    reviewed_by UUID REFERENCES admin_users(id),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    review_notes TEXT,  -- Admin's notes/reason for approval/rejection
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT valid_status_transition CHECK (
        (status = 'PENDING' AND reviewed_by IS NULL AND reviewed_at IS NULL) OR
        (status IN ('APPROVED', 'REJECTED') AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL) OR
        (status = 'CANCELLED')
    )
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_profile_changes_supplier ON profile_change_requests(supplier_id);
CREATE INDEX IF NOT EXISTS idx_profile_changes_status ON profile_change_requests(status);
CREATE INDEX IF NOT EXISTS idx_profile_changes_created ON profile_change_requests(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_profile_changes_pending ON profile_change_requests(supplier_id, status) WHERE status = 'PENDING';

-- Comments
COMMENT ON TABLE profile_change_requests IS 'Tracks vendor profile change requests requiring admin approval';
COMMENT ON COLUMN profile_change_requests.requested_changes IS 'JSONB object containing fields vendor wants to change';
COMMENT ON COLUMN profile_change_requests.current_values IS 'JSONB snapshot of current values at request time';
COMMENT ON COLUMN profile_change_requests.status IS 'PENDING, APPROVED, REJECTED, or CANCELLED';

-- ============================================================
-- Functions
-- ============================================================

-- Function to get pending profile change requests
CREATE OR REPLACE FUNCTION get_pending_profile_changes(
    p_supplier_id UUID DEFAULT NULL
)
RETURNS TABLE(
    id UUID,
    supplier_id UUID,
    company_name VARCHAR(255),
    email VARCHAR(255),
    requested_changes JSONB,
    current_values JSONB,
    status VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE,
    days_pending INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pcr.id,
        pcr.supplier_id,
        s.company_name,
        s.email,
        pcr.requested_changes,
        pcr.current_values,
        pcr.status,
        pcr.created_at,
        (CURRENT_DATE - pcr.created_at::DATE)::INTEGER as days_pending
    FROM profile_change_requests pcr
    INNER JOIN suppliers s ON pcr.supplier_id = s.id
    WHERE pcr.status = 'PENDING'
        AND (p_supplier_id IS NULL OR pcr.supplier_id = p_supplier_id)
    ORDER BY pcr.created_at ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get profile change history for a supplier
CREATE OR REPLACE FUNCTION get_profile_change_history(
    p_supplier_id UUID,
    p_limit INTEGER DEFAULT 50
)
RETURNS TABLE(
    id UUID,
    requested_changes JSONB,
    current_values JSONB,
    status VARCHAR(20),
    reviewed_by_name VARCHAR(100),
    review_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    reviewed_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pcr.id,
        pcr.requested_changes,
        pcr.current_values,
        pcr.status,
        au.full_name as reviewed_by_name,
        pcr.review_notes,
        pcr.created_at,
        pcr.reviewed_at
    FROM profile_change_requests pcr
    LEFT JOIN admin_users au ON pcr.reviewed_by = au.id
    WHERE pcr.supplier_id = p_supplier_id
    ORDER BY pcr.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to cancel pending requests when a new one is submitted
CREATE OR REPLACE FUNCTION cancel_pending_profile_changes(
    p_supplier_id UUID
)
RETURNS INTEGER AS $$
DECLARE
    v_cancelled_count INTEGER;
BEGIN
    WITH cancelled AS (
        UPDATE profile_change_requests
        SET 
            status = 'CANCELLED',
            updated_at = CURRENT_TIMESTAMP
        WHERE supplier_id = p_supplier_id
            AND status = 'PENDING'
        RETURNING id
    )
    SELECT COUNT(*) INTO v_cancelled_count FROM cancelled;
    
    RETURN v_cancelled_count;
END;
$$ LANGUAGE plpgsql;

-- Function to apply approved profile changes
CREATE OR REPLACE FUNCTION apply_profile_changes(
    p_request_id UUID
)
RETURNS BOOLEAN AS $$
DECLARE
    v_supplier_id UUID;
    v_changes JSONB;
    v_status VARCHAR(20);
BEGIN
    -- Get request details
    SELECT supplier_id, requested_changes, status
    INTO v_supplier_id, v_changes, v_status
    FROM profile_change_requests
    WHERE id = p_request_id;
    
    -- Verify request exists and is approved
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Profile change request not found';
    END IF;
    
    IF v_status != 'APPROVED' THEN
        RAISE EXCEPTION 'Can only apply approved changes';
    END IF;
    
    -- Apply changes to supplier record
    UPDATE suppliers
    SET
        company_name = COALESCE((v_changes->>'company_name')::VARCHAR(200), company_name),
        business_category = COALESCE((v_changes->>'business_category')::business_category, business_category),
        registration_number = COALESCE((v_changes->>'registration_number')::VARCHAR(100), registration_number),
        tax_id = COALESCE((v_changes->>'tax_id')::VARCHAR(100), tax_id),
        years_in_business = COALESCE((v_changes->>'years_in_business')::INTEGER, years_in_business),
        website = COALESCE((v_changes->>'website')::VARCHAR(500), website),
        contact_person_name = COALESCE((v_changes->>'contact_person_name')::VARCHAR(100), contact_person_name),
        contact_person_title = COALESCE((v_changes->>'contact_person_title')::VARCHAR(100), contact_person_title),
        email = COALESCE((v_changes->>'email')::VARCHAR(255), email),
        phone = COALESCE((v_changes->>'phone')::VARCHAR(30), phone),
        street_address = COALESCE((v_changes->>'street_address')::VARCHAR(300), street_address),
        city = COALESCE((v_changes->>'city')::VARCHAR(100), city),
        state_province = COALESCE((v_changes->>'state_province')::VARCHAR(100), state_province),
        postal_code = COALESCE((v_changes->>'postal_code')::VARCHAR(20), postal_code),
        country = COALESCE((v_changes->>'country')::VARCHAR(100), country),
        updated_at = CURRENT_TIMESTAMP
    WHERE id = v_supplier_id;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Triggers
-- ============================================================

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_profile_change_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_profile_change_timestamp ON profile_change_requests;
CREATE TRIGGER trigger_update_profile_change_timestamp
    BEFORE UPDATE ON profile_change_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_profile_change_timestamp();

-- Trigger to log activity when profile change is reviewed
CREATE OR REPLACE FUNCTION log_profile_change_review()
RETURNS TRIGGER AS $$
BEGIN
    -- Only log when status changes to APPROVED or REJECTED
    IF NEW.status IN ('APPROVED', 'REJECTED') AND OLD.status = 'PENDING' THEN
        INSERT INTO supplier_activity_log (
            supplier_id,
            activity_type,
            activity_title,
            activity_description,
            actor_type,
            actor_id,
            actor_name,
            metadata
        )
        VALUES (
            NEW.supplier_id,
            'profile_change_' || LOWER(NEW.status),
            'Profile Change ' || INITCAP(NEW.status),
            CASE 
                WHEN NEW.status = 'APPROVED' THEN 'Profile changes have been approved and applied'
                ELSE 'Profile change request was rejected: ' || COALESCE(NEW.review_notes, 'No reason provided')
            END,
            'admin',
            NEW.reviewed_by,
            (SELECT full_name FROM admin_users WHERE id = NEW.reviewed_by),
            jsonb_build_object(
                'request_id', NEW.id,
                'changes', NEW.requested_changes,
                'review_notes', NEW.review_notes
            )
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_log_profile_change_review ON profile_change_requests;
CREATE TRIGGER trigger_log_profile_change_review
    AFTER UPDATE ON profile_change_requests
    FOR EACH ROW
    EXECUTE FUNCTION log_profile_change_review();

-- ============================================================
-- Row Level Security (Optional)
-- ============================================================

ALTER TABLE profile_change_requests ENABLE ROW LEVEL SECURITY;

-- Vendors can view their own requests
DROP POLICY IF EXISTS "Vendors can view own profile change requests" ON profile_change_requests;
CREATE POLICY "Vendors can view own profile change requests" ON profile_change_requests
    FOR SELECT
    USING (supplier_id = current_setting('app.current_supplier_id', true)::UUID);

-- Admins can view all requests (handled via service role)

-- ============================================================
-- Comments
-- ============================================================

COMMENT ON FUNCTION get_pending_profile_changes IS 'Get all pending profile change requests, optionally filtered by supplier';
COMMENT ON FUNCTION get_profile_change_history IS 'Get profile change request history for a supplier';
COMMENT ON FUNCTION cancel_pending_profile_changes IS 'Cancel all pending requests for a supplier (used when submitting new request)';
COMMENT ON FUNCTION apply_profile_changes IS 'Apply approved profile changes to supplier record';
