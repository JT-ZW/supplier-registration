-- Update Document Expiry Functions
-- This script only updates the functions to use s3_key instead of file_url
-- Run this in Supabase SQL Editor after the initial migration

-- Function to get expiring documents within a threshold
CREATE OR REPLACE FUNCTION get_expiring_documents(
    p_days_threshold INTEGER DEFAULT 90
)
RETURNS TABLE(
    document_id UUID,
    supplier_id UUID,
    company_name VARCHAR(255),
    email VARCHAR(255),
    document_type VARCHAR(100),
    expiry_date DATE,
    days_until_expiry INTEGER,
    file_url TEXT,
    supplier_status VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.id as document_id,
        d.supplier_id,
        s.company_name,
        s.email,
        d.document_type,
        d.expiry_date,
        (d.expiry_date - CURRENT_DATE)::INTEGER as days_until_expiry,
        d.s3_key as file_url,
        s.status as supplier_status
    FROM documents d
    INNER JOIN suppliers s ON d.supplier_id = s.id
    WHERE d.expiry_date IS NOT NULL
        AND d.expiry_date <= CURRENT_DATE + p_days_threshold
        AND d.expiry_date >= CURRENT_DATE
        AND d.verification_status = 'VERIFIED'
        AND s.status IN ('APPROVED', 'UNDER_REVIEW')
    ORDER BY d.expiry_date ASC, s.company_name ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get expired documents
CREATE OR REPLACE FUNCTION get_expired_documents()
RETURNS TABLE(
    document_id UUID,
    supplier_id UUID,
    company_name VARCHAR(255),
    email VARCHAR(255),
    document_type VARCHAR(100),
    expiry_date DATE,
    days_since_expiry INTEGER,
    file_url TEXT,
    supplier_status VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.id as document_id,
        d.supplier_id,
        s.company_name,
        s.email,
        d.document_type,
        d.expiry_date,
        (CURRENT_DATE - d.expiry_date)::INTEGER as days_since_expiry,
        d.s3_key as file_url,
        s.status as supplier_status
    FROM documents d
    INNER JOIN suppliers s ON d.supplier_id = s.id
    WHERE d.expiry_date IS NOT NULL
        AND d.expiry_date < CURRENT_DATE
        AND d.verification_status = 'VERIFIED'
        AND s.status IN ('APPROVED', 'UNDER_REVIEW', 'NEED_MORE_INFO')
    ORDER BY d.expiry_date ASC, s.company_name ASC;
END;
$$ LANGUAGE plpgsql STABLE;
