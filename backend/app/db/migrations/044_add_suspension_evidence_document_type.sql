-- ============================================================
-- Migration 044: Add SUSPENSION_EVIDENCE document type
-- ============================================================
-- Admin suspension evidence uploads store documents with:
--   document_type = 'SUSPENSION_EVIDENCE'
--
-- Without this enum value, confirmation fails with:
--   invalid input value for enum document_type: "SUSPENSION_EVIDENCE"
-- ============================================================

ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'SUSPENSION_EVIDENCE';
