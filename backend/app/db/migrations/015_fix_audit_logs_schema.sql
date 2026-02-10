-- Migration 015: Fix audit_logs table schema
-- Ensures audit_logs table has all required columns for proper logging
-- Run Date: 2026-02-05

-- Check if admin_email column exists, if not add it
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'audit_logs' 
        AND column_name = 'admin_email'
    ) THEN
        ALTER TABLE audit_logs ADD COLUMN admin_email VARCHAR(255);
        COMMENT ON COLUMN audit_logs.admin_email IS 'Email of the admin user who performed the action';
    END IF;
END $$;

-- Ensure the table matches the expected structure
-- If the table was created with the 004 migration structure, update it to match our needs
DO $$
BEGIN
    -- Check if we have the old structure (user_type, user_email columns)
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'audit_logs' 
        AND column_name = 'user_type'
    ) THEN
        -- This is the 004 migration structure, we need to adapt it
        
        -- Add admin_email if it doesn't exist (from user_email for admin users)
        IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'audit_logs' 
            AND column_name = 'admin_email'
        ) THEN
            ALTER TABLE audit_logs ADD COLUMN admin_email VARCHAR(255);
            
            -- Populate admin_email from existing user_email where user_type is 'admin'
            UPDATE audit_logs 
            SET admin_email = user_email 
            WHERE user_type = 'admin' AND admin_email IS NULL;
        END IF;
        
        -- Ensure target_type column exists (mapping from resource_type)
        IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'audit_logs' 
            AND column_name = 'target_type'
        ) THEN
            ALTER TABLE audit_logs ADD COLUMN target_type VARCHAR(50);
            
            -- Map resource_type to target_type
            UPDATE audit_logs 
            SET target_type = resource_type 
            WHERE target_type IS NULL;
        END IF;
        
        -- Ensure target_id column exists (mapping from resource_id)
        IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'audit_logs' 
            AND column_name = 'target_id'
        ) THEN
            ALTER TABLE audit_logs ADD COLUMN target_id UUID;
            
            -- Map resource_id to target_id
            UPDATE audit_logs 
            SET target_id = resource_id 
            WHERE target_id IS NULL;
        END IF;
        
    ELSE
        -- This is likely the 001 migration structure
        -- Ensure all required columns exist
        
        IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'audit_logs' 
            AND column_name = 'admin_email'
        ) THEN
            ALTER TABLE audit_logs ADD COLUMN admin_email VARCHAR(255);
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'audit_logs' 
            AND column_name = 'action'
        ) THEN
            ALTER TABLE audit_logs ADD COLUMN action VARCHAR(100) NOT NULL DEFAULT 'UNKNOWN';
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'audit_logs' 
            AND column_name = 'target_type'
        ) THEN
            ALTER TABLE audit_logs ADD COLUMN target_type VARCHAR(50) NOT NULL DEFAULT 'SYSTEM';
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'audit_logs' 
            AND column_name = 'target_id'
        ) THEN
            ALTER TABLE audit_logs ADD COLUMN target_id UUID;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'audit_logs' 
            AND column_name = 'details'
        ) THEN
            ALTER TABLE audit_logs ADD COLUMN details JSONB;
        END IF;
        
        IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'audit_logs' 
            AND column_name = 'ip_address'
        ) THEN
            ALTER TABLE audit_logs ADD COLUMN ip_address INET;
        END IF;
    END IF;
END $$;

-- Ensure admin_email can be NULL (for system actions or when email is unavailable)
ALTER TABLE audit_logs ALTER COLUMN admin_email DROP NOT NULL;

-- Add index on admin_email for faster lookups if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE tablename = 'audit_logs'
        AND indexname = 'idx_audit_logs_admin_email'
    ) THEN
        CREATE INDEX idx_audit_logs_admin_email ON audit_logs(admin_email);
    END IF;
END $$;

-- Ensure created_at has a default value
ALTER TABLE audit_logs ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;

COMMENT ON TABLE audit_logs IS 'Comprehensive audit log for all system actions';
COMMENT ON COLUMN audit_logs.admin_email IS 'Email of the admin user (denormalized for quick access and reporting)';
