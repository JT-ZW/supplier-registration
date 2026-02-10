-- Migration: Fix apply_profile_changes function - add missing business_category field
-- Date: 2026-02-09
-- Description: Adds business_category field update to apply_profile_changes RPC function

-- ============================================================
-- Fix apply_profile_changes Function
-- ============================================================
-- The function was missing business_category field which is in
-- APPROVAL_REQUIRED_FIELDS but wasn't being applied when approved

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
    -- FIXED: Added business_category field with proper ENUM casting
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
