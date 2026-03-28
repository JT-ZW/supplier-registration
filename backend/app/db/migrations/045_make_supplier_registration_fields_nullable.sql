-- ============================================================
-- Migration 045: Allow nullable registration_number and tax_id
-- ============================================================
-- Reason:
-- Small-scale farmer registrations do not always have formal company
-- registration numbers or tax IDs. The API already treats these fields
-- as optional for farmers, but the DB schema still enforces NOT NULL.
--
-- This migration aligns the DB with the farmer registration flow.
-- ============================================================

ALTER TABLE suppliers
    ALTER COLUMN registration_number DROP NOT NULL,
    ALTER COLUMN tax_id DROP NOT NULL;

COMMENT ON COLUMN suppliers.registration_number IS
    'Business registration number. Required by application logic for non-farmer suppliers; optional for small-scale farmers.';

COMMENT ON COLUMN suppliers.tax_id IS
    'Tax ID / ZIMRA number. Required by application logic for non-farmer suppliers; optional for small-scale farmers.';
