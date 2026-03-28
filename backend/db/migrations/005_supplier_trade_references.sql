-- Migration 005: Supplier Trade References
-- Stores trade reference contacts provided during supplier registration
-- Run Date: 2026-03-26

CREATE TABLE IF NOT EXISTS supplier_trade_references (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,

    company_name VARCHAR(200) NOT NULL,
    contact_person_name VARCHAR(200) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    relationship VARCHAR(100) NOT NULL,

    service_product VARCHAR(300) NULL,
    contract_start_date DATE NULL,
    contract_end_date DATE NULL,
    annual_spend VARCHAR(100) NULL,

    permission_granted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_supplier_trade_reference_permission CHECK (permission_granted = TRUE),
    CONSTRAINT chk_trade_reference_contract_dates CHECK (
        contract_end_date IS NULL
        OR contract_start_date IS NULL
        OR contract_end_date >= contract_start_date
    )
);

CREATE INDEX IF NOT EXISTS idx_supplier_trade_references_supplier_id
    ON supplier_trade_references (supplier_id);

CREATE INDEX IF NOT EXISTS idx_supplier_trade_references_created_at
    ON supplier_trade_references (created_at DESC);

COMMENT ON TABLE supplier_trade_references IS 'Trade references captured during supplier registration';
COMMENT ON COLUMN supplier_trade_references.permission_granted IS 'Must be true to indicate supplier consent for RTG to contact reference';
COMMENT ON COLUMN supplier_trade_references.contract_start_date IS 'Contract start date with trade reference';
COMMENT ON COLUMN supplier_trade_references.contract_end_date IS 'Contract end date with trade reference';
