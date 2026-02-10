-- Quick diagnostic: Check what statuses your suppliers actually have
-- Run this in Supabase SQL Editor to see the real data

SELECT 
    status,
    COUNT(*) as count,
    STRING_AGG(company_name, ', ' ORDER BY created_at DESC) as companies
FROM suppliers
GROUP BY status
ORDER BY count DESC;

-- Also show individual suppliers with their key fields
SELECT 
    company_name,
    status,
    submitted_at,
    reviewed_at,
    created_at
FROM suppliers
ORDER BY created_at DESC;
