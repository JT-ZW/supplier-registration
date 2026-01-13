-- ============================================================
-- Supplier Registration & Approval System
-- Database Schema Migration
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- ENUM Types
-- ============================================================

-- Supplier application status
CREATE TYPE supplier_status AS ENUM (
    'INCOMPLETE',
    'SUBMITTED',
    'UNDER_REVIEW',
    'NEED_MORE_INFO',
    'APPROVED',
    'REJECTED'
);

-- Supplier activity status
CREATE TYPE activity_status AS ENUM (
    'ACTIVE',
    'INACTIVE'
);

-- Business categories
CREATE TYPE business_category AS ENUM (
    'CONSTRUCTION',
    'MANUFACTURING',
    'FOOD_BEVERAGE',
    'HEALTHCARE',
    'IT_SERVICES',
    'LOGISTICS',
    'CONSULTING',
    'CLEANING_SERVICES',
    'SECURITY_SERVICES',
    'GENERAL_SUPPLIES',
    'OTHER'
);

-- Document types
CREATE TYPE document_type AS ENUM (
    'COMPANY_PROFILE',
    'CERTIFICATE_OF_INCORPORATION',
    'CR14_OR_CR6',
    'VAT_CERTIFICATE',
    'TAX_CLEARANCE',
    'FDMS_COMPLIANCE',
    'HEALTH_CERTIFICATE',
    'ISO_9001',
    'ISO_45001',
    'ISO_14000',
    'INTERNAL_QMS',
    'SHEQ_POLICY'
);

-- Document verification status
CREATE TYPE verification_status AS ENUM (
    'PENDING',
    'VERIFIED',
    'REJECTED'
);

-- Admin action types for audit logging
CREATE TYPE admin_action AS ENUM (
    'LOGIN',
    'LOGOUT',
    'VIEW_APPLICATION',
    'APPROVE_DOCUMENT',
    'REJECT_DOCUMENT',
    'APPROVE_APPLICATION',
    'REJECT_APPLICATION',
    'REQUEST_MORE_INFO',
    'EXPORT_REPORT',
    'UPDATE_SUPPLIER_STATUS'
);

-- ============================================================
-- Tables
-- ============================================================

-- Suppliers table (aligned with frontend schema)
CREATE TABLE suppliers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Business Information
    company_name VARCHAR(200) NOT NULL,
    business_category business_category NOT NULL,
    registration_number VARCHAR(100) NOT NULL,
    tax_id VARCHAR(100) NOT NULL,
    years_in_business INTEGER NOT NULL CHECK (years_in_business >= 0),
    website VARCHAR(500),
    
    -- Contact Information
    contact_person_name VARCHAR(100) NOT NULL,
    contact_person_title VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    
    -- Address Information
    street_address VARCHAR(300) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state_province VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    country VARCHAR(100) NOT NULL,
    
    -- Status & Review
    status supplier_status NOT NULL DEFAULT 'INCOMPLETE',
    activity_status activity_status DEFAULT 'ACTIVE',
    admin_notes TEXT,
    rejection_reason TEXT,
    info_request_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP WITH TIME ZONE,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by UUID,
    
    CONSTRAINT unique_supplier_email UNIQUE (email)
);

-- Indexes for suppliers
CREATE INDEX idx_suppliers_email ON suppliers(email);
CREATE INDEX idx_suppliers_status ON suppliers(status);
CREATE INDEX idx_suppliers_category ON suppliers(business_category);
CREATE INDEX idx_suppliers_created_at ON suppliers(created_at DESC);
CREATE INDEX idx_suppliers_company_name ON suppliers(company_name);


-- Documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    document_type document_type NOT NULL,
    s3_key VARCHAR(500) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL CHECK (file_size > 0),
    content_type VARCHAR(100) NOT NULL,
    verification_status verification_status NOT NULL DEFAULT 'PENDING',
    verification_comments TEXT,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    verified_at TIMESTAMP WITH TIME ZONE,
    verified_by UUID,
    
    CONSTRAINT unique_document_per_supplier UNIQUE (supplier_id, document_type)
);

CREATE INDEX idx_documents_supplier_id ON documents(supplier_id);
CREATE INDEX idx_documents_verification_status ON documents(verification_status);


-- Admin users table
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'admin',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_admin_users_email ON admin_users(email);


-- Audit logs table
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id UUID NOT NULL REFERENCES admin_users(id),
    admin_email VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_admin_id ON audit_logs(admin_id);
CREATE INDEX idx_audit_logs_target_id ON audit_logs(target_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);


-- ============================================================
-- Triggers
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_suppliers_updated_at
    BEFORE UPDATE ON suppliers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- Analytics Functions
-- ============================================================

-- Get overview statistics
CREATE OR REPLACE FUNCTION get_overview_stats()
RETURNS TABLE (
    total_suppliers BIGINT,
    total_approved BIGINT,
    total_pending BIGINT,
    total_rejected BIGINT,
    total_active BIGINT,
    total_inactive BIGINT,
    applications_this_month BIGINT,
    approvals_this_month BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM suppliers)::BIGINT,
        (SELECT COUNT(*) FROM suppliers WHERE status = 'APPROVED')::BIGINT,
        (SELECT COUNT(*) FROM suppliers WHERE status IN ('SUBMITTED', 'UNDER_REVIEW', 'NEED_MORE_INFO'))::BIGINT,
        (SELECT COUNT(*) FROM suppliers WHERE status = 'REJECTED')::BIGINT,
        (SELECT COUNT(*) FROM suppliers WHERE activity_status = 'ACTIVE' AND status = 'APPROVED')::BIGINT,
        (SELECT COUNT(*) FROM suppliers WHERE activity_status = 'INACTIVE' AND status = 'APPROVED')::BIGINT,
        (SELECT COUNT(*) FROM suppliers WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE))::BIGINT,
        (SELECT COUNT(*) FROM suppliers WHERE status = 'APPROVED' AND reviewed_at >= DATE_TRUNC('month', CURRENT_DATE))::BIGINT;
END;
$$ LANGUAGE plpgsql;


-- Get supplier count by category
CREATE OR REPLACE FUNCTION get_supplier_count_by_category()
RETURNS TABLE (
    category business_category,
    total_count BIGINT,
    approved_count BIGINT,
    pending_count BIGINT,
    rejected_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.business_category,
        COUNT(*)::BIGINT as total_count,
        COUNT(*) FILTER (WHERE s.status = 'APPROVED')::BIGINT as approved_count,
        COUNT(*) FILTER (WHERE s.status IN ('SUBMITTED', 'UNDER_REVIEW', 'NEED_MORE_INFO'))::BIGINT as pending_count,
        COUNT(*) FILTER (WHERE s.status = 'REJECTED')::BIGINT as rejected_count
    FROM suppliers s
    GROUP BY s.business_category
    ORDER BY total_count DESC;
END;
$$ LANGUAGE plpgsql;


-- Get monthly trends
CREATE OR REPLACE FUNCTION get_monthly_trends(months_back INTEGER DEFAULT 12)
RETURNS TABLE (
    month VARCHAR,
    year INTEGER,
    submitted BIGINT,
    approved BIGINT,
    rejected BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        TO_CHAR(DATE_TRUNC('month', s.created_at), 'Mon')::VARCHAR as month,
        EXTRACT(YEAR FROM s.created_at)::INTEGER as year,
        COUNT(*)::BIGINT as submitted,
        COUNT(*) FILTER (WHERE s.status = 'APPROVED')::BIGINT as approved,
        COUNT(*) FILTER (WHERE s.status = 'REJECTED')::BIGINT as rejected
    FROM suppliers s
    WHERE s.created_at >= CURRENT_DATE - (months_back || ' months')::INTERVAL
    GROUP BY DATE_TRUNC('month', s.created_at)
    ORDER BY DATE_TRUNC('month', s.created_at);
END;
$$ LANGUAGE plpgsql;


-- Get location statistics
CREATE OR REPLACE FUNCTION get_location_stats()
RETURNS TABLE (
    location VARCHAR,
    count BIGINT,
    percentage NUMERIC
) AS $$
DECLARE
    total_count BIGINT;
BEGIN
    SELECT COUNT(*) INTO total_count FROM suppliers;
    
    RETURN QUERY
    SELECT 
        s.city::VARCHAR as location,
        COUNT(*)::BIGINT as count,
        ROUND((COUNT(*)::NUMERIC / NULLIF(total_count, 0) * 100), 2) as percentage
    FROM suppliers s
    GROUP BY s.city
    ORDER BY count DESC
    LIMIT 10;
END;
$$ LANGUAGE plpgsql;


-- Get status distribution
CREATE OR REPLACE FUNCTION get_status_distribution()
RETURNS TABLE (
    status supplier_status,
    count BIGINT,
    percentage NUMERIC
) AS $$
DECLARE
    total_count BIGINT;
BEGIN
    SELECT COUNT(*) INTO total_count FROM suppliers;
    
    RETURN QUERY
    SELECT 
        s.status,
        COUNT(*)::BIGINT as count,
        ROUND((COUNT(*)::NUMERIC / NULLIF(total_count, 0) * 100), 2) as percentage
    FROM suppliers s
    GROUP BY s.status
    ORDER BY count DESC;
END;
$$ LANGUAGE plpgsql;


-- Cleanup rejected applications
CREATE OR REPLACE FUNCTION cleanup_rejected_applications(retention_days INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    WITH deleted AS (
        DELETE FROM suppliers
        WHERE status = 'REJECTED'
        AND reviewed_at < CURRENT_TIMESTAMP - (retention_days || ' days')::INTERVAL
        RETURNING id
    )
    SELECT COUNT(*) INTO deleted_count FROM deleted;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- Row Level Security (RLS) Policies
-- ============================================================

ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Public can create suppliers
CREATE POLICY "Allow public to create suppliers" ON suppliers
    FOR INSERT TO anon
    WITH CHECK (true);

-- Public can view suppliers
CREATE POLICY "Allow public to view suppliers" ON suppliers
    FOR SELECT TO anon
    USING (true);

-- Public can update incomplete suppliers
CREATE POLICY "Allow public to update incomplete suppliers" ON suppliers
    FOR UPDATE TO anon
    USING (status IN ('INCOMPLETE', 'NEED_MORE_INFO'))
    WITH CHECK (status IN ('INCOMPLETE', 'NEED_MORE_INFO', 'SUBMITTED'));

-- Public can manage documents
CREATE POLICY "Allow public to create documents" ON documents
    FOR INSERT TO anon
    WITH CHECK (true);

CREATE POLICY "Allow public to view documents" ON documents
    FOR SELECT TO anon
    USING (true);

CREATE POLICY "Allow public to delete own documents" ON documents
    FOR DELETE TO anon
    USING (
        EXISTS (
            SELECT 1 FROM suppliers s 
            WHERE s.id = supplier_id 
            AND s.status IN ('INCOMPLETE', 'NEED_MORE_INFO')
        )
    );
