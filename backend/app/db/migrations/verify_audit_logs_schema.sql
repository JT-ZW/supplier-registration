-- Quick Audit Logs Schema Verification Script
-- Run this in Supabase SQL Editor to check current state

-- 1. Check if audit_logs table exists
SELECT 
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_logs')
        THEN '✓ audit_logs table exists'
        ELSE '✗ audit_logs table NOT FOUND'
    END as table_status;

-- 2. List all columns in audit_logs table
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'audit_logs'
ORDER BY ordinal_position;

-- 3. Check specifically for admin_email column
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'audit_logs' 
            AND column_name = 'admin_email'
        )
        THEN '✓ admin_email column EXISTS'
        ELSE '✗ admin_email column MISSING - Need to run migration 015'
    END as admin_email_status;

-- 4. Check for required columns
SELECT 
    'admin_id' as required_column,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'admin_id')
    THEN '✓' ELSE '✗' END as exists
UNION ALL
SELECT 
    'admin_email',
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'admin_email')
    THEN '✓' ELSE '✗ MISSING!' END
UNION ALL
SELECT 
    'action',
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'action')
    THEN '✓' ELSE '✗' END
UNION ALL
SELECT 
    'target_type',
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'target_type')
    THEN '✓' ELSE '✗' END
UNION ALL
SELECT 
    'target_id',
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'target_id')
    THEN '✓' ELSE '✗' END
UNION ALL
SELECT 
    'details',
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'details')
    THEN '✓' ELSE '✗' END
UNION ALL
SELECT 
    'ip_address',
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'ip_address')
    THEN '✓' ELSE '✗' END
UNION ALL
SELECT 
    'created_at',
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'created_at')
    THEN '✓' ELSE '✗' END;

-- 5. Count existing audit logs
SELECT 
    COUNT(*) as total_audit_logs,
    COUNT(CASE WHEN admin_email IS NULL THEN 1 END) as missing_admin_email,
    MIN(created_at) as oldest_log,
    MAX(created_at) as newest_log
FROM audit_logs;

-- 6. Show sample of recent audit logs (if any exist)
SELECT 
    id,
    admin_id,
    admin_email,
    action,
    target_type,
    created_at
FROM audit_logs
ORDER BY created_at DESC
LIMIT 5;

-- 7. Check indexes
SELECT 
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'audit_logs'
ORDER BY indexname;
