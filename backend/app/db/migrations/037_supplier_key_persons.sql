-- Migration 037: Key persons table
-- Stores directors (formal suppliers, up to 3) or the single contact person
-- (small-scale farmers).  Used for ESG reporting: women-owned and youth-owned
-- classification, director gender/age tracking.

CREATE TABLE IF NOT EXISTS supplier_key_persons (
    id           UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    supplier_id  UUID        NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    full_name    VARCHAR(200) NOT NULL,
    gender       VARCHAR(10)  NOT NULL CHECK (gender IN ('MALE', 'FEMALE', 'OTHER')),
    date_of_birth DATE        NOT NULL,
    -- 'DIRECTOR' for formal suppliers; 'CONTACT' for small-scale farmers
    role         VARCHAR(20)  NOT NULL DEFAULT 'DIRECTOR' CHECK (role IN ('DIRECTOR', 'CONTACT')),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_key_persons_supplier_id
    ON supplier_key_persons(supplier_id);

COMMENT ON TABLE supplier_key_persons IS
    'Key persons per supplier.  Formal suppliers: up to 3 directors.  '
    'Small-scale farmers: exactly 1 contact person.';

-- ── Enforce max 3 directors per formal supplier ──────────────────────────────
CREATE OR REPLACE FUNCTION fn_check_max_directors()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.role = 'DIRECTOR' THEN
        IF (
            SELECT COUNT(*)
            FROM supplier_key_persons
            WHERE supplier_id = NEW.supplier_id
              AND role = 'DIRECTOR'
        ) >= 3 THEN
            RAISE EXCEPTION 'A supplier cannot have more than 3 directors';
        END IF;
    END IF;
    IF NEW.role = 'CONTACT' THEN
        IF (
            SELECT COUNT(*)
            FROM supplier_key_persons
            WHERE supplier_id = NEW.supplier_id
              AND role = 'CONTACT'
        ) >= 1 THEN
            RAISE EXCEPTION 'A farmer supplier can only have one contact person';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_check_max_directors ON supplier_key_persons;
CREATE TRIGGER trg_check_max_directors
    BEFORE INSERT ON supplier_key_persons
    FOR EACH ROW EXECUTE FUNCTION fn_check_max_directors();

-- ── Auto-update updated_at ────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_key_persons_updated_at ON supplier_key_persons;
CREATE TRIGGER trg_key_persons_updated_at
    BEFORE UPDATE ON supplier_key_persons
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
