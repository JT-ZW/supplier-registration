-- Migration: Add new business categories and document types
-- Date: 2026-02-27
-- Description:
--   1. Adds MEAT_PRODUCTS, FRESH_FARM_PRODUCE, ROPE_ACCESS to business_category enum
--   2. Adds FOOD_SAFETY_CERTIFICATION, GOOD_AGRICULTURAL_PRACTICES, ISO_45000,
--      INDUSTRY_CERTIFICATION to document_type enum

-- ============================================================
-- 1. Add new business category enum values
-- ============================================================
ALTER TYPE business_category ADD VALUE IF NOT EXISTS 'MEAT_PRODUCTS';
ALTER TYPE business_category ADD VALUE IF NOT EXISTS 'FRESH_FARM_PRODUCE';
ALTER TYPE business_category ADD VALUE IF NOT EXISTS 'ROPE_ACCESS';

-- ============================================================
-- 2. Add new document type enum values
-- ============================================================
ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'FOOD_SAFETY_CERTIFICATION';
ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'GOOD_AGRICULTURAL_PRACTICES';
ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'ISO_45000';
ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'INDUSTRY_CERTIFICATION';
