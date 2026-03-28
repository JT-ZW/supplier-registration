-- Migration 038: Multi-category support
-- Suppliers can now register under up to 6 business categories.
-- The existing suppliers.business_category column is kept as the *primary*
-- category for backward compatibility.  supplier_categories is the new
-- source of truth for all categories.

CREATE TABLE IF NOT EXISTS supplier_categories (
    id                    UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    supplier_id           UUID        NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    category              VARCHAR(100) NOT NULL,
    -- Compliance level for this specific category
    compliance_status     VARCHAR(20)  CHECK (compliance_status IN (
                                'FULL_COMPLIANCE', 'MEDIUM_RISK', 'HIGH_RISK', 'PENDING', 'EXCLUDED'
                            )) DEFAULT 'PENDING',
    compliance_checked_at TIMESTAMPTZ,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (supplier_id, category)
);

CREATE INDEX IF NOT EXISTS idx_supplier_categories_supplier_id
    ON supplier_categories(supplier_id);
CREATE INDEX IF NOT EXISTS idx_supplier_categories_category
    ON supplier_categories(category);

COMMENT ON TABLE supplier_categories IS
    'Junction table for supplier ↔ business category relationships.  '
    'One supplier may belong to up to 6 categories.';

-- ── Enforce maximum 6 categories per supplier ────────────────────────────────
CREATE OR REPLACE FUNCTION fn_check_max_categories()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF (
        SELECT COUNT(*)
        FROM supplier_categories
        WHERE supplier_id = NEW.supplier_id
    ) >= 6 THEN
        RAISE EXCEPTION 'A supplier cannot register more than 6 business categories';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_check_max_categories ON supplier_categories;
CREATE TRIGGER trg_check_max_categories
    BEFORE INSERT ON supplier_categories
    FOR EACH ROW EXECUTE FUNCTION fn_check_max_categories();

-- ── Backfill: seed supplier_categories from existing business_category values ─
-- Skips legacy category values that are not part of the official RTG list.
INSERT INTO supplier_categories (supplier_id, category)
SELECT id, business_category
FROM suppliers
WHERE business_category IN (
    'CLEANING_EQUIPMENT_SUPPLIERS', 'CONSTRUCTION_CONTRACTORS', 'DAIRY_SUPPLIERS',
    'ELECTRICAL_CONTRACTORS', 'ENERGY_SUPPLIERS', 'FOOD_BEVERAGE_SUPPLIERS',
    'FRUIT_VEGETABLE_SUPPLIERS', 'FURNITURE_SUPPLIERS', 'HOTEL_GUEST_LINEN',
    'HOTEL_GUEST_AMENITIES', 'HOUSEKEEPING_CHEMICALS', 'ICT_TECHNOLOGY',
    'KITCHEN_EQUIPMENT', 'LANDSCAPING_GARDENING', 'LAUNDRY_SERVICES',
    'MEAT_SUPPLIERS', 'PPE_SUPPLIERS', 'PEST_CONTROL', 'PLUMBING_CONTRACTORS',
    'SECURITY_SERVICES', 'TRANSPORT_LOGISTICS', 'WASTE_MANAGEMENT', 'ROPE_ACCESS'
)
ON CONFLICT (supplier_id, category) DO NOTHING;
