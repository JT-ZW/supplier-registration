-- ============================================================
-- Admin Roles & User Management Enhancement
-- Migration: 013_admin_roles.sql
-- ============================================================

-- Create admin role enum
CREATE TYPE admin_role AS ENUM (
    'SYSTEM_ADMIN',
    'PROCUREMENT_MANAGER'
);

-- Update existing role values to match new enum
UPDATE admin_users 
SET role = 'SYSTEM_ADMIN' 
WHERE role = 'admin' OR role IS NULL;

-- Drop existing default constraint
ALTER TABLE admin_users 
    ALTER COLUMN role DROP DEFAULT;

-- Change column type to enum
ALTER TABLE admin_users 
    ALTER COLUMN role TYPE admin_role USING 
    CASE 
        WHEN role = 'SYSTEM_ADMIN' THEN 'SYSTEM_ADMIN'::admin_role
        WHEN role = 'PROCUREMENT_MANAGER' THEN 'PROCUREMENT_MANAGER'::admin_role
        ELSE 'SYSTEM_ADMIN'::admin_role
    END;

-- Set new default for new records
ALTER TABLE admin_users 
    ALTER COLUMN role SET DEFAULT 'SYSTEM_ADMIN'::admin_role;

-- Add additional columns for better user management
ALTER TABLE admin_users 
    ADD COLUMN IF NOT EXISTS phone VARCHAR(30),
    ADD COLUMN IF NOT EXISTS department VARCHAR(100),
    ADD COLUMN IF NOT EXISTS position VARCHAR(100),
    ADD COLUMN IF NOT EXISTS last_password_change TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS account_locked_until TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES admin_users(id),
    ADD COLUMN IF NOT EXISTS updated_by UUID REFERENCES admin_users(id),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Create index for role
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role);

-- Create index for active status
CREATE INDEX IF NOT EXISTS idx_admin_users_is_active ON admin_users(is_active);

-- Add triggers for updated_at
CREATE OR REPLACE FUNCTION update_admin_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_admin_users_updated_at
    BEFORE UPDATE ON admin_users
    FOR EACH ROW
    EXECUTE FUNCTION update_admin_users_updated_at();

-- Add audit log entries for user management
COMMENT ON TABLE admin_users IS 'Admin and procurement team users with role-based access control';
