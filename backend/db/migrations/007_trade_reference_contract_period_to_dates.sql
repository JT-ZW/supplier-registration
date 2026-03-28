-- Migration 007: Convert trade reference contract period from free text to date fields
-- Reason: enforce uniformity and data integrity with typed date columns.
-- Safe to run multiple times.

ALTER TABLE supplier_trade_references
    ADD COLUMN IF NOT EXISTS contract_start_date DATE,
    ADD COLUMN IF NOT EXISTS contract_end_date DATE;

ALTER TABLE supplier_trade_references
    DROP CONSTRAINT IF EXISTS chk_trade_reference_contract_dates;

ALTER TABLE supplier_trade_references
    ADD CONSTRAINT chk_trade_reference_contract_dates CHECK (
        contract_end_date IS NULL
        OR contract_start_date IS NULL
        OR contract_end_date >= contract_start_date
    );

ALTER TABLE supplier_trade_references
    DROP COLUMN IF EXISTS contract_period;

COMMENT ON COLUMN supplier_trade_references.contract_start_date IS 'Contract start date with trade reference';
COMMENT ON COLUMN supplier_trade_references.contract_end_date IS 'Contract end date with trade reference';