-- Migration 034: Add admin-registered supplier tracking columns
-- Run this in the Supabase SQL Editor

ALTER TABLE suppliers
  ADD COLUMN IF NOT EXISTS registered_by_admin BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS registered_by_admin_email TEXT;

COMMENT ON COLUMN suppliers.registered_by_admin IS 'TRUE when an admin registered this supplier on their behalf';
COMMENT ON COLUMN suppliers.registered_by_admin_email IS 'Email of the admin who registered this supplier';
