-- ============================================================
-- Migration 043: Add missing notification_type enum values
-- ============================================================
-- The notification_type ENUM in the notifications table is missing
-- 'document_expiry_warning' and 'document_expired', causing every
-- expiry alert notification to fail with:
--   invalid input value for enum notification_type: "document_expiry_warning"
--   invalid input value for enum notification_type: "document_expired"
-- ============================================================

ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'document_expiry_warning';
ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'document_expired';
