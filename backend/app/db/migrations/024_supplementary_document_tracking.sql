-- Migration: Track supplementary document uploads (added post-approval)
-- Date: 2026-03-02
-- Description:
--   Adds two columns to the documents table to track documents that a
--   supplier uploads AFTER their application has been approved:
--
--   is_supplementary          - TRUE when the document was added post-approval
--   added_post_approval_at    - Timestamp of the post-approval upload
--
--   This allows:
--     • Distinguishing registration documents from supplementary ones in the UI
--     • Including/excluding supplementary docs in sustainability reports
--     • Auditing when suppliers enhance their profile with new certifications

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS is_supplementary       BOOLEAN                  NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS added_post_approval_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN documents.is_supplementary IS
  'TRUE if this document was added by the supplier after their application was approved (i.e. not part of the original registration).';

COMMENT ON COLUMN documents.added_post_approval_at IS
  'The timestamp at which this supplementary document was uploaded post-approval. NULL for registration documents.';

-- Partial index: makes queries for supplementary documents fast
-- (e.g. sustainability reports that want post-approval certifications only)
CREATE INDEX IF NOT EXISTS idx_documents_supplementary
  ON documents (supplier_id, is_supplementary)
  WHERE is_supplementary = TRUE;
