-- ============================================================
-- CLEAR ALL SUPPLIER TEST DATA
-- Keep admin accounts, category definitions, document type
-- definitions — remove all supplier registrations and related data.
--
-- Run this in the Supabase SQL Editor (supabase.com → your project
-- → SQL Editor → New query → paste → Run).
-- ============================================================

BEGIN;

-- 1. Clear all audit logs (no FK constraint, so not auto-cascaded)
DELETE FROM audit_logs;

-- 2. Delete all suppliers.
--    All child tables cascade automatically via ON DELETE CASCADE:
--      • documents
--      • document_expiry_alerts
--      • document_status_history
--      • profile_change_requests
--      • supplier_status_history
--      • supplier_activity_log
--      • supplier_suspension_history
--      • supplier_key_persons
--      • supplier_categories
--      • farmer_application_forms
--      • message_threads (and their messages)
DELETE FROM suppliers;

COMMIT;

-- Verify: these should all return 0 rows
SELECT 'suppliers'                  AS tbl, COUNT(*) FROM suppliers
UNION ALL
SELECT 'documents',                         COUNT(*) FROM documents
UNION ALL
SELECT 'profile_change_requests',           COUNT(*) FROM profile_change_requests
UNION ALL
SELECT 'supplier_categories',               COUNT(*) FROM supplier_categories
UNION ALL
SELECT 'supplier_key_persons',              COUNT(*) FROM supplier_key_persons
UNION ALL
SELECT 'supplier_status_history',           COUNT(*) FROM supplier_status_history
UNION ALL
SELECT 'supplier_suspension_history',       COUNT(*) FROM supplier_suspension_history
UNION ALL
SELECT 'farmer_application_forms',          COUNT(*) FROM farmer_application_forms
UNION ALL
SELECT 'audit_logs (all)',                  COUNT(*) FROM audit_logs;
