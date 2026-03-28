-- Migration 047: Fix ESG summary age threshold precision
--
-- Purpose:
-- 1. Make youth calculation exact (<35 years) using AGE(), not year subtraction.
-- 2. Keep ESG counts tied to leadership records (DIRECTOR/CONTACT roles).
--
-- Notes:
-- - This migration updates only vw_esg_supplier_summary.
-- - API routes derive women/youth-owned from these counts using >50% thresholds.

CREATE OR REPLACE VIEW vw_esg_supplier_summary AS
SELECT
    s.id,
    s.company_name,
    s.country,
    s.status,
    s.business_size,
    s.employee_count,
    s.is_small_scale_farmer,
    s.esg_women_owned,
    s.esg_youth_owned,
    COUNT(kp.id) FILTER (
        WHERE kp.role IN ('DIRECTOR', 'CONTACT')
    ) AS key_person_count,
    COUNT(kp.id) FILTER (
        WHERE kp.role IN ('DIRECTOR', 'CONTACT')
          AND kp.gender = 'FEMALE'
    ) AS female_director_count,
    COUNT(kp.id) FILTER (
        WHERE kp.role IN ('DIRECTOR', 'CONTACT')
          AND kp.date_of_birth IS NOT NULL
          AND AGE(CURRENT_DATE, kp.date_of_birth) < INTERVAL '35 years'
    ) AS youth_director_count
FROM suppliers s
LEFT JOIN supplier_key_persons kp ON kp.supplier_id = s.id
GROUP BY
    s.id,
    s.company_name,
    s.country,
    s.status,
    s.business_size,
    s.employee_count,
    s.is_small_scale_farmer,
    s.esg_women_owned,
    s.esg_youth_owned;
