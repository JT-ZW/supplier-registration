-- Migration: Add uploaded_by column to documents table and EVALUATION_FORM enum value
-- Date: 2026-02-09
-- Description: Adds uploaded_by column to track which admin user uploaded evaluation forms
--              and adds EVALUATION_FORM to document_type enum

-- ============================================================
-- 1. Add EVALUATION_FORM to document_type enum
-- ============================================================
ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'EVALUATION_FORM';

-- ============================================================
-- 2. Add uploaded_by column to documents table
-- ============================================================
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS uploaded_by UUID;

-- ============================================================
-- 3. Add foreign key constraint (optional but recommended)
-- ============================================================
-- Link uploaded_by to admin_users table (only if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'fk_documents_uploaded_by'
    ) THEN
        ALTER TABLE documents 
        ADD CONSTRAINT fk_documents_uploaded_by 
        FOREIGN KEY (uploaded_by) 
        REFERENCES admin_users(id) 
        ON DELETE SET NULL;
    END IF;
END $$;

-- ============================================================
-- 4. Add index for performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by 
ON documents(uploaded_by);

-- ============================================================
-- 5. Add comments for documentation
-- ============================================================
COMMENT ON COLUMN documents.uploaded_by IS 'Admin user who uploaded the document (for admin-uploaded evaluation forms)';
