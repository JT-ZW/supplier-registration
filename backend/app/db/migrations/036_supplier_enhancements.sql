-- Migration 036: Supplier ESG & size enhancements
-- Adds employee_count, business_size classification, small-scale farmer flag,
-- and ESG boolean flags (women-owned, youth-owned) to the suppliers table.
-- All columns are nullable / have defaults so existing rows are unaffected.

ALTER TABLE suppliers
    ADD COLUMN IF NOT EXISTS employee_count       INTEGER CHECK (employee_count >= 0),
    ADD COLUMN IF NOT EXISTS business_size        VARCHAR(10) CHECK (business_size IN ('SMALL', 'MEDIUM', 'LARGE')),
    ADD COLUMN IF NOT EXISTS is_small_scale_farmer BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS esg_women_owned      BOOLEAN,
    ADD COLUMN IF NOT EXISTS esg_youth_owned      BOOLEAN;

COMMENT ON COLUMN suppliers.employee_count        IS 'Number of full-time employees; drives business_size classification';
COMMENT ON COLUMN suppliers.business_size         IS 'SMALL (<10), MEDIUM (10-50), LARGE (>50) – computed from employee_count';
COMMENT ON COLUMN suppliers.is_small_scale_farmer IS 'TRUE for Zimbabwe-based informal / small-scale farmers; activates the farmer registration sub-flow';
COMMENT ON COLUMN suppliers.esg_women_owned       IS 'TRUE when >50% of key persons are female; computed from supplier_key_persons';
COMMENT ON COLUMN suppliers.esg_youth_owned       IS 'TRUE when >50% of key persons are under 35; computed from supplier_key_persons';
