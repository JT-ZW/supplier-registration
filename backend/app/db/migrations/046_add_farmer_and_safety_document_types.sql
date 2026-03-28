-- ============================================================
-- Migration 046: Add missing farmer/safety document_type enum values
-- ============================================================
-- Reason:
-- The application now supports farmer application uploads and rope-access
-- safety supporting documents. If the DB enum is missing these values,
-- document confirmation fails with:
--   invalid input value for enum document_type: "APPLICATION_FORM"
-- ============================================================

ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'APPLICATION_FORM';
ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'SAFETY_METHOD_STATEMENT';
ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'RESCUE_PLAN';
