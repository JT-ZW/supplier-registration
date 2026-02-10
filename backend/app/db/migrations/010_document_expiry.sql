-- Document Expiry Alerts Migration
-- Proactive document compliance and expiry tracking

-- ============================================================
-- Add Expiry Date Column to Documents Table
-- ============================================================

-- Add expiry_date column if it doesn't exist
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS expiry_date DATE;

-- Add index for expiry date queries
CREATE INDEX IF NOT EXISTS idx_documents_expiry_date ON documents(expiry_date) WHERE expiry_date IS NOT NULL;

-- Add comment
COMMENT ON COLUMN documents.expiry_date IS 'Expiration date for the document (e.g., license expiry, certificate expiry)';

-- ============================================================
-- Document Expiry Alerts Table
-- ============================================================

CREATE TABLE IF NOT EXISTS document_expiry_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- References
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    
    -- Alert details
    alert_type VARCHAR(20) NOT NULL CHECK (alert_type IN ('90_days', '60_days', '30_days', '7_days', '1_day', 'expired')),
    alert_date TIMESTAMP WITH TIME ZONE NOT NULL,
    expiry_date DATE NOT NULL,
    
    -- Status tracking
    email_sent BOOLEAN DEFAULT FALSE,
    email_sent_at TIMESTAMP WITH TIME ZONE,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by UUID REFERENCES suppliers(id),
    
    -- Metadata
    reminder_count INTEGER DEFAULT 0,
    last_reminder_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE(document_id, alert_type)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_expiry_alerts_document ON document_expiry_alerts(document_id);
CREATE INDEX IF NOT EXISTS idx_expiry_alerts_supplier ON document_expiry_alerts(supplier_id);
CREATE INDEX IF NOT EXISTS idx_expiry_alerts_type ON document_expiry_alerts(alert_type, email_sent);
CREATE INDEX IF NOT EXISTS idx_expiry_alerts_date ON document_expiry_alerts(alert_date, email_sent);
CREATE INDEX IF NOT EXISTS idx_expiry_alerts_expiry ON document_expiry_alerts(expiry_date);
CREATE INDEX IF NOT EXISTS idx_expiry_alerts_pending ON document_expiry_alerts(email_sent, alert_date) WHERE email_sent = FALSE;

-- ============================================================
-- Functions
-- ============================================================

-- Function to get expiring documents within a threshold
CREATE OR REPLACE FUNCTION get_expiring_documents(
    p_days_threshold INTEGER DEFAULT 90
)
RETURNS TABLE(
    document_id UUID,
    supplier_id UUID,
    company_name VARCHAR(255),
    email VARCHAR(255),
    document_type VARCHAR(100),
    expiry_date DATE,
    days_until_expiry INTEGER,
    file_url TEXT,
    supplier_status VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.id as document_id,
        d.supplier_id,
        s.company_name,
        s.email,
        d.document_type,
        d.expiry_date,
        (d.expiry_date - CURRENT_DATE)::INTEGER as days_until_expiry,
        d.s3_key as file_url,
        s.status as supplier_status
    FROM documents d
    INNER JOIN suppliers s ON d.supplier_id = s.id
    WHERE d.expiry_date IS NOT NULL
        AND d.expiry_date <= CURRENT_DATE + p_days_threshold
        AND d.expiry_date >= CURRENT_DATE
        AND d.verification_status = 'VERIFIED'
        AND s.status IN ('APPROVED', 'UNDER_REVIEW')
    ORDER BY d.expiry_date ASC, s.company_name ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get expired documents
CREATE OR REPLACE FUNCTION get_expired_documents()
RETURNS TABLE(
    document_id UUID,
    supplier_id UUID,
    company_name VARCHAR(255),
    email VARCHAR(255),
    document_type VARCHAR(100),
    expiry_date DATE,
    days_since_expiry INTEGER,
    file_url TEXT,
    supplier_status VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.id as document_id,
        d.supplier_id,
        s.company_name,
        s.email,
        d.document_type,
        d.expiry_date,
        (CURRENT_DATE - d.expiry_date)::INTEGER as days_since_expiry,
        d.s3_key as file_url,
        s.status as supplier_status
    FROM documents d
    INNER JOIN suppliers s ON d.supplier_id = s.id
    WHERE d.expiry_date IS NOT NULL
        AND d.expiry_date < CURRENT_DATE
        AND d.verification_status = 'VERIFIED'
        AND s.status IN ('APPROVED', 'UNDER_REVIEW', 'NEED_MORE_INFO')
    ORDER BY d.expiry_date ASC, s.company_name ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get expiring documents for a specific supplier
CREATE OR REPLACE FUNCTION get_supplier_expiring_documents(
    p_supplier_id UUID,
    p_days_threshold INTEGER DEFAULT 90
)
RETURNS TABLE(
    document_id UUID,
    document_type VARCHAR(100),
    expiry_date DATE,
    days_until_expiry INTEGER,
    alert_count INTEGER,
    last_alert_date TIMESTAMP WITH TIME ZONE,
    acknowledged BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.id as document_id,
        d.document_type,
        d.expiry_date,
        (d.expiry_date - CURRENT_DATE)::INTEGER as days_until_expiry,
        COALESCE(COUNT(dea.id)::INTEGER, 0) as alert_count,
        MAX(dea.created_at) as last_alert_date,
        COALESCE(BOOL_OR(dea.acknowledged), FALSE) as acknowledged
    FROM documents d
    LEFT JOIN document_expiry_alerts dea ON d.id = dea.document_id
    WHERE d.supplier_id = p_supplier_id
        AND d.expiry_date IS NOT NULL
        AND d.expiry_date <= CURRENT_DATE + p_days_threshold
        AND d.expiry_date >= CURRENT_DATE
        AND d.verification_status = 'VERIFIED'
    GROUP BY d.id, d.document_type, d.expiry_date
    ORDER BY d.expiry_date ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to create alerts for expiring documents
CREATE OR REPLACE FUNCTION create_expiry_alerts()
RETURNS TABLE(
    alerts_created INTEGER,
    documents_processed INTEGER
) AS $$
DECLARE
    v_alerts_created INTEGER := 0;
    v_documents_processed INTEGER := 0;
    v_doc RECORD;
    v_days_until_expiry INTEGER;
    v_alert_type VARCHAR(20);
BEGIN
    -- Loop through all documents with expiry dates
    FOR v_doc IN 
        SELECT d.id, d.supplier_id, d.expiry_date, d.document_type
        FROM documents d
        INNER JOIN suppliers s ON d.supplier_id = s.id
        WHERE d.expiry_date IS NOT NULL
            AND d.verification_status = 'VERIFIED'
            AND s.status IN ('APPROVED', 'UNDER_REVIEW')
    LOOP
        v_documents_processed := v_documents_processed + 1;
        v_days_until_expiry := v_doc.expiry_date - CURRENT_DATE;
        
        -- Determine alert type and create if needed
        IF v_days_until_expiry <= 0 THEN
            v_alert_type := 'expired';
        ELSIF v_days_until_expiry <= 1 THEN
            v_alert_type := '1_day';
        ELSIF v_days_until_expiry <= 7 THEN
            v_alert_type := '7_days';
        ELSIF v_days_until_expiry <= 30 THEN
            v_alert_type := '30_days';
        ELSIF v_days_until_expiry <= 60 THEN
            v_alert_type := '60_days';
        ELSIF v_days_until_expiry <= 90 THEN
            v_alert_type := '90_days';
        ELSE
            CONTINUE;
        END IF;
        
        -- Create alert if it doesn't exist
        INSERT INTO document_expiry_alerts (
            document_id,
            supplier_id,
            alert_type,
            alert_date,
            expiry_date
        )
        VALUES (
            v_doc.id,
            v_doc.supplier_id,
            v_alert_type,
            CURRENT_TIMESTAMP,
            v_doc.expiry_date
        )
        ON CONFLICT (document_id, alert_type) DO NOTHING;
        
        IF FOUND THEN
            v_alerts_created := v_alerts_created + 1;
        END IF;
    END LOOP;
    
    RETURN QUERY SELECT v_alerts_created, v_documents_processed;
END;
$$ LANGUAGE plpgsql;

-- Function to get pending alerts (emails not sent)
CREATE OR REPLACE FUNCTION get_pending_alerts()
RETURNS TABLE(
    alert_id UUID,
    document_id UUID,
    supplier_id UUID,
    company_name VARCHAR(255),
    email VARCHAR(255),
    document_type VARCHAR(100),
    expiry_date DATE,
    alert_type VARCHAR(20),
    days_until_expiry INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        dea.id as alert_id,
        dea.document_id,
        dea.supplier_id,
        s.company_name,
        s.email,
        d.document_type,
        dea.expiry_date,
        dea.alert_type,
        (dea.expiry_date - CURRENT_DATE)::INTEGER as days_until_expiry
    FROM document_expiry_alerts dea
    INNER JOIN documents d ON dea.document_id = d.id
    INNER JOIN suppliers s ON dea.supplier_id = s.id
    WHERE dea.email_sent = FALSE
        AND s.status IN ('APPROVED', 'UNDER_REVIEW')
    ORDER BY dea.expiry_date ASC, dea.alert_type ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to mark alert email as sent
CREATE OR REPLACE FUNCTION mark_alert_sent(
    p_alert_id UUID
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE document_expiry_alerts
    SET 
        email_sent = TRUE,
        email_sent_at = CURRENT_TIMESTAMP,
        reminder_count = reminder_count + 1,
        last_reminder_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_alert_id;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Function to acknowledge alert
CREATE OR REPLACE FUNCTION acknowledge_alert(
    p_alert_id UUID,
    p_supplier_id UUID
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE document_expiry_alerts
    SET 
        acknowledged = TRUE,
        acknowledged_at = CURRENT_TIMESTAMP,
        acknowledged_by = p_supplier_id,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_alert_id
        AND supplier_id = p_supplier_id;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Function to get alert statistics
CREATE OR REPLACE FUNCTION get_expiry_alert_stats()
RETURNS TABLE(
    total_alerts INTEGER,
    pending_alerts INTEGER,
    sent_alerts INTEGER,
    acknowledged_alerts INTEGER,
    expired_documents INTEGER,
    critical_alerts INTEGER,
    warning_alerts INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::INTEGER as total_alerts,
        COUNT(*) FILTER (WHERE email_sent = FALSE)::INTEGER as pending_alerts,
        COUNT(*) FILTER (WHERE email_sent = TRUE)::INTEGER as sent_alerts,
        COUNT(*) FILTER (WHERE acknowledged = TRUE)::INTEGER as acknowledged_alerts,
        COUNT(*) FILTER (WHERE alert_type = 'expired')::INTEGER as expired_documents,
        COUNT(*) FILTER (WHERE alert_type IN ('1_day', '7_days', 'expired'))::INTEGER as critical_alerts,
        COUNT(*) FILTER (WHERE alert_type IN ('30_days', '60_days', '90_days'))::INTEGER as warning_alerts
    FROM document_expiry_alerts;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Triggers
-- ============================================================

-- Trigger to auto-create alerts when document expiry date is set/updated
CREATE OR REPLACE FUNCTION auto_create_expiry_alert()
RETURNS TRIGGER AS $$
DECLARE
    v_days_until_expiry INTEGER;
    v_alert_type VARCHAR(20);
BEGIN
    -- Only process if expiry_date exists and document is approved
    IF NEW.expiry_date IS NOT NULL AND NEW.verification_status = 'VERIFIED' THEN
        v_days_until_expiry := NEW.expiry_date - CURRENT_DATE;
        
        -- Determine initial alert type
        IF v_days_until_expiry <= 0 THEN
            v_alert_type := 'expired';
        ELSIF v_days_until_expiry <= 1 THEN
            v_alert_type := '1_day';
        ELSIF v_days_until_expiry <= 7 THEN
            v_alert_type := '7_days';
        ELSIF v_days_until_expiry <= 30 THEN
            v_alert_type := '30_days';
        ELSIF v_days_until_expiry <= 60 THEN
            v_alert_type := '60_days';
        ELSIF v_days_until_expiry <= 90 THEN
            v_alert_type := '90_days';
        ELSE
            RETURN NEW;
        END IF;
        
        -- Create alert
        INSERT INTO document_expiry_alerts (
            document_id,
            supplier_id,
            alert_type,
            alert_date,
            expiry_date
        )
        VALUES (
            NEW.id,
            NEW.supplier_id,
            v_alert_type,
            CURRENT_TIMESTAMP,
            NEW.expiry_date
        )
        ON CONFLICT (document_id, alert_type) DO NOTHING;
        
        -- Log activity
        INSERT INTO supplier_activity_log (
            supplier_id,
            activity_type,
            activity_title,
            activity_description,
            actor_type,
            actor_id,
            actor_name,
            metadata
        )
        VALUES (
            NEW.supplier_id,
            'document_expiry_alert',
            'Document Expiry Alert Created',
            'Alert created for ' || NEW.document_type || ' expiring in ' || v_days_until_expiry || ' days',
            'system',
            NULL,
            'System',
            jsonb_build_object(
                'document_id', NEW.id,
                'document_type', NEW.document_type,
                'expiry_date', NEW.expiry_date,
                'alert_type', v_alert_type,
                'days_until_expiry', v_days_until_expiry
            )
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_auto_create_expiry_alert ON documents;
CREATE TRIGGER trigger_auto_create_expiry_alert
    AFTER INSERT OR UPDATE OF expiry_date, verification_status ON documents
    FOR EACH ROW
    EXECUTE FUNCTION auto_create_expiry_alert();

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_expiry_alert_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_expiry_alert_timestamp ON document_expiry_alerts;
CREATE TRIGGER trigger_update_expiry_alert_timestamp
    BEFORE UPDATE ON document_expiry_alerts
    FOR EACH ROW
    EXECUTE FUNCTION update_expiry_alert_timestamp();

-- ============================================================
-- Backfill Alerts for Existing Documents
-- ============================================================

-- Create alerts for all existing documents with expiry dates
DO $$
DECLARE
    v_result RECORD;
BEGIN
    SELECT * INTO v_result FROM create_expiry_alerts();
    RAISE NOTICE 'Backfill complete: % alerts created for % documents', 
        v_result.alerts_created, v_result.documents_processed;
END $$;

-- ============================================================
-- Comments
-- ============================================================

COMMENT ON TABLE document_expiry_alerts IS 'Tracks document expiry alerts and notifications';
COMMENT ON FUNCTION get_expiring_documents IS 'Get all documents expiring within threshold days';
COMMENT ON FUNCTION get_expired_documents IS 'Get all expired documents';
COMMENT ON FUNCTION get_supplier_expiring_documents IS 'Get expiring documents for a specific supplier';
COMMENT ON FUNCTION create_expiry_alerts IS 'Batch create alerts for all expiring documents';
COMMENT ON FUNCTION get_pending_alerts IS 'Get alerts that need email notifications sent';
COMMENT ON FUNCTION mark_alert_sent IS 'Mark an alert email as sent';
COMMENT ON FUNCTION acknowledge_alert IS 'Mark an alert as acknowledged by supplier';
COMMENT ON FUNCTION get_expiry_alert_stats IS 'Get statistics on document expiry alerts';

-- ============================================================
-- Scheduled Job Notes
-- ============================================================

-- To run this with pg_cron (if available):
-- SELECT cron.schedule('create-expiry-alerts', '0 2 * * *', 'SELECT create_expiry_alerts();');

-- Or use external scheduler to call: SELECT create_expiry_alerts();
-- Recommended: Run daily at 2 AM to create new alerts as documents approach expiry
