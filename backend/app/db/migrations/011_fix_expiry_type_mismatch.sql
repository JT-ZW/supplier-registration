-- Fix for Document Expiry Type Mismatch Error
-- This migration fixes the PostgreSQL type mismatch where document_type ENUM
-- was being returned as VARCHAR(100) causing error:
-- "structure of query does not match function result type"

-- ============================================================
-- Fix get_expiring_documents function
-- ============================================================

-- Drop existing function first (required to change return type)
DROP FUNCTION IF EXISTS get_expiring_documents(INTEGER);

CREATE OR REPLACE FUNCTION get_expiring_documents(
    p_days_threshold INTEGER DEFAULT 90
)
RETURNS TABLE(
    document_id UUID,
    supplier_id UUID,
    company_name VARCHAR(255),
    email VARCHAR(255),
    document_type TEXT,  -- Changed from VARCHAR(100) to TEXT
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
        d.document_type::TEXT,  -- Cast ENUM to TEXT
        d.expiry_date,
        (d.expiry_date - CURRENT_DATE)::INTEGER as days_until_expiry,
        d.s3_key::TEXT as file_url,  -- Cast VARCHAR(500) to TEXT
        s.status::VARCHAR(50) as supplier_status  -- Cast ENUM to VARCHAR
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

-- ============================================================
-- Fix get_expired_documents function
-- ============================================================

-- Drop existing function first (required to change return type)
DROP FUNCTION IF EXISTS get_expired_documents();

CREATE OR REPLACE FUNCTION get_expired_documents()
RETURNS TABLE(
    document_id UUID,
    supplier_id UUID,
    company_name VARCHAR(255),
    email VARCHAR(255),
    document_type TEXT,  -- Changed from VARCHAR(100) to TEXT
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
        d.document_type::TEXT,  -- Cast ENUM to TEXT
        d.expiry_date,
        (CURRENT_DATE - d.expiry_date)::INTEGER as days_since_expiry,
        d.s3_key::TEXT as file_url,  -- Cast VARCHAR(500) to TEXT
        s.status::VARCHAR(50) as supplier_status  -- Cast ENUM to VARCHAR
    FROM documents d
    INNER JOIN suppliers s ON d.supplier_id = s.id
    WHERE d.expiry_date IS NOT NULL
        AND d.expiry_date < CURRENT_DATE
        AND d.verification_status = 'VERIFIED'
        AND s.status IN ('APPROVED', 'UNDER_REVIEW', 'NEED_MORE_INFO')
    ORDER BY d.expiry_date ASC, s.company_name ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Fix get_supplier_expiring_documents function
-- ============================================================

-- Drop existing function first (required to change return type)
DROP FUNCTION IF EXISTS get_supplier_expiring_documents(UUID, INTEGER);

CREATE OR REPLACE FUNCTION get_supplier_expiring_documents(
    p_supplier_id UUID,
    p_days_threshold INTEGER DEFAULT 90
)
RETURNS TABLE(
    document_id UUID,
    document_type TEXT,  -- Changed from VARCHAR(100) to TEXT
    expiry_date DATE,
    days_until_expiry INTEGER,
    alert_count INTEGER,
    last_alert_date TIMESTAMP WITH TIME ZONE,
    acknowledged BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.id as document_id,
        d.document_type::TEXT,  -- Cast ENUM to TEXT
        d.expiry_date,
        (d.expiry_date - CURRENT_DATE)::INTEGER as days_until_expiry,
        COALESCE(COUNT(dea.id)::INTEGER, 0) as alert_count,
        MAX(dea.created_at) as last_alert_date,
        COALESCE(BOOL_OR(dea.acknowledged), FALSE) as acknowledged
    FROM documents d
    LEFT JOIN document_expiry_alerts dea ON d.id = dea.document_id
    WHERE d.supplier_id = p_supplier_id
        AND d.expiry_date IS NOT NULL
        AND d.expiry_date <= CURRENT_DATE + p_days_threshold
        AND d.expiry_date >= CURRENT_DATE
        AND d.verification_status = 'VERIFIED'
    GROUP BY d.id, d.document_type, d.expiry_date
    ORDER BY d.expiry_date ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Fix get_pending_alerts function
-- ============================================================

-- Drop existing function first (required to change return type)
DROP FUNCTION IF EXISTS get_pending_alerts();

CREATE OR REPLACE FUNCTION get_pending_alerts()
RETURNS TABLE(
    alert_id UUID,
    document_id UUID,
    supplier_id UUID,
    company_name VARCHAR(255),
    email VARCHAR(255),
    document_type TEXT,  -- Changed from VARCHAR(100) to TEXT
    expiry_date DATE,
    alert_type VARCHAR(20),
    days_until_expiry INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        dea.id as alert_id,
        dea.document_id,
        dea.supplier_id,
        s.company_name,
        s.email,
        d.document_type::TEXT,  -- Cast ENUM to TEXT
        dea.expiry_date,
        dea.alert_type,
        (dea.expiry_date - CURRENT_DATE)::INTEGER as days_until_expiry
    FROM document_expiry_alerts dea
    INNER JOIN documents d ON dea.document_id = d.id
    INNER JOIN suppliers s ON dea.supplier_id = s.id
    WHERE dea.email_sent = FALSE
        AND s.status IN ('APPROVED', 'UNDER_REVIEW')
    ORDER BY dea.expiry_date ASC, dea.alert_type ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Verification
-- ============================================================

-- Test the functions to ensure they work
DO $$
BEGIN
    RAISE NOTICE 'Document expiry functions have been fixed successfully!';
    RAISE NOTICE 'The document_type ENUM is now properly cast to TEXT.';
END $$;
