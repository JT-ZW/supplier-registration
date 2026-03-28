-- Migration 040: Farmer application form table
-- Replaces the PDF-download farmer application form with an inline
-- online form submitted during registration.

CREATE TABLE IF NOT EXISTS farmer_application_forms (
    id                       UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    supplier_id              UUID          NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,

    -- Identity of the key contact person
    contact_full_name        VARCHAR(200)  NOT NULL,
    id_number                VARCHAR(100),                          -- National ID or passport number
    gender                   VARCHAR(10)   NOT NULL CHECK (gender IN ('MALE', 'FEMALE', 'OTHER')),
    date_of_birth            DATE          NOT NULL,

    -- Farming details
    farming_activity         TEXT          NOT NULL,               -- Description of what they grow / rear
    produce_types            TEXT          NOT NULL,               -- Comma-separated list of produce
    estimated_land_size_ha   NUMERIC(10, 2),                       -- Hectares (optional)
    years_farming            INTEGER       CHECK (years_farming >= 0),

    -- Land / location proof type (maps to the uploaded OFFER_LETTER_TITLE_DEEDS doc)
    land_proof_type          VARCHAR(30)   CHECK (land_proof_type IN (
                                 'OFFER_LETTER', 'TITLE_DEEDS', 'VILLAGE_HEAD_LETTER'
                             )),
    village_or_farm_name     VARCHAR(200),
    district                 VARCHAR(100),
    province                 VARCHAR(100),

    -- Financial / ESG
    has_bank_account         BOOLEAN       NOT NULL DEFAULT FALSE,
    bank_name                VARCHAR(100),                         -- If has_bank_account = TRUE

    created_at               TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    -- One form per farmer supplier
    UNIQUE (supplier_id)
);

CREATE INDEX IF NOT EXISTS idx_farmer_forms_supplier_id
    ON farmer_application_forms(supplier_id);

COMMENT ON TABLE farmer_application_forms IS
    'Online application form for small-scale farmer suppliers.  '
    'Replaces the paper form previously issued by the Procurement department.';

DROP TRIGGER IF EXISTS trg_farmer_forms_updated_at ON farmer_application_forms;
CREATE TRIGGER trg_farmer_forms_updated_at
    BEFORE UPDATE ON farmer_application_forms
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
