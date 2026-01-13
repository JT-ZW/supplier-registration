-- Add vendor portal authentication fields to suppliers table

-- Add password and authentication fields
ALTER TABLE suppliers 
ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255),
ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(255),
ADD COLUMN IF NOT EXISTS password_reset_expires TIMESTAMP WITH TIME ZONE;

-- Create index on password_reset_token for faster lookups
CREATE INDEX IF NOT EXISTS idx_suppliers_password_reset_token 
ON suppliers(password_reset_token);

-- Create index on email for faster login lookups (if not exists)
CREATE INDEX IF NOT EXISTS idx_suppliers_email 
ON suppliers(email);

-- Add comments for documentation
COMMENT ON COLUMN suppliers.password_hash IS 'Hashed password for vendor portal login';
COMMENT ON COLUMN suppliers.last_login IS 'Timestamp of last successful login';
COMMENT ON COLUMN suppliers.password_reset_token IS 'Token for password reset (24-hour validity)';
COMMENT ON COLUMN suppliers.password_reset_expires IS 'Expiration timestamp for password reset token';
