-- Migration: 010_fix_extensions_and_find_policies.sql
-- Description: Moves extensions out of the public schema into a dedicated 'extensions' 
--              schema, and provides a query to find the remaining unsecured RLS policies.

-- ============================================================================
-- 1. FIX: EXTENSIONS IN PUBLIC SCHEMA
-- Action: Create an 'extensions' schema and move all public extensions into it.
--         We also update the database search_path so things like uuid_generate_v4()
--         continue to work globally without breaking your existing queries.
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS extensions;

-- Ensure the public role can use the extensions schema
GRANT USAGE ON SCHEMA extensions TO public;

-- Alter the database to include 'extensions' in the default search path
ALTER DATABASE postgres SET search_path TO "$user", public, extensions;

DO $DO$
DECLARE
    ext record;
BEGIN
    FOR ext IN 
        SELECT extname 
        FROM pg_extension e 
        JOIN pg_namespace n ON e.extnamespace = n.oid 
        WHERE n.nspname = 'public' 
          AND e.extname != 'plpgsql'
    LOOP
        BEGIN
            EXECUTE format('ALTER EXTENSION %I SET SCHEMA extensions;', ext.extname);
            RAISE NOTICE 'Successfully moved extension % to extensions schema.', ext.extname;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Could not move extension %: %', ext.extname, SQLERRM;
        END;
    END LOOP;
END
$DO$;

-- ============================================================================
-- 2. DIAGNOSE: RLS POLICY ALWAYS TRUE
-- Action: Identify which exact tables have overly permissive INSERT/UPDATE/DELETE 
--         policies so we can safely secure them (the screenshot shows 2 remaining).
-- ============================================================================
-- PLEASE RUN THIS SELECT QUERY AND SHARE THE RESULTS:

SELECT tablename, policyname, cmd, qual, with_check 
FROM pg_policies 
WHERE schemaname = 'public' 
  AND (qual = 'true' OR with_check = 'true') 
  AND cmd IN ('INSERT', 'UPDATE', 'DELETE');
