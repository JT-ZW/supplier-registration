-- Migration: 011_fix_remaining_rls_policies.sql
-- Description: Removes the remaining overly permissive INSERT policies.
--              Since the FastAPI backend handles inserts using the SERVICE_ROLE_KEY 
--              (which bypasses RLS), we can safely revoke direct PostgREST insert 
--              access from the frontend to completely secure these tables.

-- ============================================================================
-- 1. FIX: DOCUMENTS RLS POLICY
-- Action: Drop the "Allow authenticated inserts for documents" policy.
-- ============================================================================
DROP POLICY IF EXISTS "Allow authenticated inserts for documents" ON public.documents;

-- ============================================================================
-- 2. FIX: SUPPLIERS RLS POLICY
-- Action: Drop the "Allow public to create suppliers" policy.
-- ============================================================================
DROP POLICY IF EXISTS "Allow public to create suppliers" ON public.suppliers;
