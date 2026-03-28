-- Migration 006: Remove supplier self-declared trade reference performance rating
-- Reason: Performance feedback should come directly from references, not supplier self-declaration.
-- Safe to run multiple times.

ALTER TABLE supplier_trade_references
    DROP COLUMN IF EXISTS performance_rating;