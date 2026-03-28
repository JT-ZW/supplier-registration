-- Migration: 009_fix_function_search_paths_and_vulnerabilities.sql
-- Description: Sets search_path for all public schema functions, secures the 
--              materialized view, and tightens document RLS.

-- ============================================================================
-- 1. FIX: FUNCTION SEARCH PATH MUTABLE
-- Action: Apply SET search_path = public, pg_temp to all functions in the 
--         public schema dynamically utilizing a DO block.
-- ============================================================================
DO $DO$
DECLARE
    func_rec record;
BEGIN
    FOR func_rec IN 
        SELECT p.oid::regprocedure AS func_signature
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' 
          -- Only target regular functions and procedures (exclude aggregates/windows)
          AND p.prokind IN ('f', 'p')
    LOOP
        BEGIN
            EXECUTE format('ALTER FUNCTION %s SET search_path = public, pg_temp;', func_rec.func_signature);
        EXCEPTION WHEN insufficient_privilege THEN
            RAISE NOTICE 'Skipping function % due to insufficient privileges.', func_rec.func_signature;
        END;
    END LOOP;
END
$DO$;

-- ============================================================================
-- 2. FIX: MATERIALIZED VIEW IN API
-- Action: Revoke select access from the PostgREST internet-facing roles 
--         (anon and authenticated) to ensure the view cannot be accessed directly.
-- ============================================================================
REVOKE SELECT ON public.supplier_statistics FROM anon;
REVOKE SELECT ON public.supplier_statistics FROM authenticated;

-- ============================================================================
-- 3. FIX: RLS POLICY ALWAYS TRUE (Documents)
-- Action: Drop the overly permissive insert policy and replace it with a tighter 
--         authenticated-only policy (assuming your backend Service Role key handles 
--         the deep validation itself).
-- ============================================================================
DROP POLICY IF EXISTS "Allow public to create documents" ON public.documents;

-- Create an alternative that still prevents completely anonymous internet agents 
-- from sending unauthenticated POST requests to the table.
CREATE POLICY "Allow authenticated inserts for documents" 
    ON public.documents 
    FOR INSERT 
    TO authenticated 
    WITH CHECK (true);
