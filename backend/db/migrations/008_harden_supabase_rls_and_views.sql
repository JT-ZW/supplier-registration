-- Migration: 008_harden_supabase_rls_and_views.sql
-- Description: Enables RLS on all exposed tables and enforces security_invoker on all views 
--              to resolve Supabase Security Linter warnings.

-- ============================================================================
-- 1. FIX: SECURITY DEFINER VIEWS
-- Action: Change views to run with the permissions of the user querying them
--         (Security Invoker) rather than the view creator (Security Definer).
-- ============================================================================

ALTER VIEW public.vw_business_size_distribution SET (security_invoker = on);
ALTER VIEW public.vw_document_type_stats SET (security_invoker = on);
ALTER VIEW public.vw_category_compliance SET (security_invoker = on);
ALTER VIEW public.v_sustainability_participation SET (security_invoker = on);
ALTER VIEW public.table_sizes SET (security_invoker = on);
ALTER VIEW public.v_sustainability_submissions SET (security_invoker = on);
ALTER VIEW public.thread_summary SET (security_invoker = on);
ALTER VIEW public.index_usage SET (security_invoker = on);
ALTER VIEW public.vw_esg_supplier_summary SET (security_invoker = on);

-- ============================================================================
-- 2. FIX: RLS DISABLED IN PUBLIC SCHEMA
-- Action: Enable Row Level Security (RLS) on all tables exposed to PostgREST.
-- Since the FastAPI backend uses the SERVICE_ROLE_KEY, it automatically bypasses 
-- RLS. Turning this on acts as a "Default Deny" for anyone trying to query
-- the database directly from the frontend using the anon key.
-- ============================================================================

ALTER TABLE public.supplier_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.farmer_application_forms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.supplier_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saved_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.search_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.supplier_trade_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.message_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.message_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.supplier_activity_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_expiry_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.supplier_suspension_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.supplier_key_persons ENABLE ROW LEVEL SECURITY;

-- (Optional) If you haven't enabled it on core tables yet, it's highly recommended:
-- ALTER TABLE public.suppliers ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.admin_users ENABLE ROW LEVEL SECURITY;

