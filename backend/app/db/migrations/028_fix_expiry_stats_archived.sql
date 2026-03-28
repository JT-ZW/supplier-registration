-- ============================================================
-- Migration 028: Fix expiry stats and alert tracking for archived documents
--
-- Problems fixed:
--   1. get_expiry_alert_stats counted alerts belonging to archived documents,
--      causing Total Alerts to exceed the visible expiring-documents list.
--   2. The auto_create_expiry_alert trigger did not delete alerts when a
--      document was archived (is_archived set to TRUE), so stale alert rows
--      remained after a supplier replaced an expiring document.
--   3. One-time cleanup of all existing stale alerts for archived documents.
-- ============================================================

-- ============================================================
-- 1. Fix get_expiry_alert_stats to exclude archived documents
-- ============================================================

CREATE OR REPLACE FUNCTION get_expiry_alert_stats()
RETURNS TABLE(
    total_alerts        INTEGER,
    pending_alerts      INTEGER,
    sent_alerts         INTEGER,
    acknowledged_alerts INTEGER,
    expired_documents   INTEGER,
    critical_alerts     INTEGER,
    warning_alerts      INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(a.id)::INTEGER                                                          AS total_alerts,
        COUNT(a.id) FILTER (WHERE a.email_sent = FALSE)::INTEGER                     AS pending_alerts,
        COUNT(a.id) FILTER (WHERE a.email_sent = TRUE)::INTEGER                      AS sent_alerts,
        COUNT(a.id) FILTER (WHERE a.acknowledged = TRUE)::INTEGER                    AS acknowledged_alerts,
        COUNT(a.id) FILTER (WHERE a.alert_type = 'expired')::INTEGER                 AS expired_documents,
        COUNT(a.id) FILTER (WHERE a.alert_type IN ('1_day', '7_days', 'expired'))::INTEGER AS critical_alerts,
        COUNT(a.id) FILTER (WHERE a.alert_type IN ('30_days', '60_days', '90_days'))::INTEGER AS warning_alerts
    FROM document_expiry_alerts a
    INNER JOIN documents d ON d.id = a.document_id
    WHERE COALESCE(d.is_archived, FALSE) = FALSE;
END;
$$ LANGUAGE plpgsql STABLE;


-- ============================================================
-- 2. Update trigger function to delete alerts when is_archived → TRUE
-- ============================================================

CREATE OR REPLACE FUNCTION auto_create_expiry_alert()
RETURNS TRIGGER AS $$
DECLARE
    v_days_until_expiry INTEGER;
    v_alert_type        VARCHAR(20);
BEGIN
    -- When a document is archived, remove all its pending expiry alerts.
    IF TG_OP = 'UPDATE' AND NEW.is_archived = TRUE AND COALESCE(OLD.is_archived, FALSE) = FALSE THEN
        DELETE FROM document_expiry_alerts
        WHERE document_id = NEW.id;
        RETURN NEW;
    END IF;

    -- Only create/update alerts for non-archived, verified documents with an expiry date.
    IF NEW.expiry_date IS NOT NULL
       AND NEW.verification_status = 'VERIFIED'
       AND COALESCE(NEW.is_archived, FALSE) = FALSE
    THEN
        v_days_until_expiry := NEW.expiry_date - CURRENT_DATE;

        -- Determine alert tier
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

        -- Activity log
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
                'document_id',        NEW.id,
                'document_type',      NEW.document_type,
                'expiry_date',        NEW.expiry_date,
                'alert_type',         v_alert_type,
                'days_until_expiry',  v_days_until_expiry
            )
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Recreate the trigger so it also fires on is_archived changes
DROP TRIGGER IF EXISTS trigger_auto_create_expiry_alert ON documents;
CREATE TRIGGER trigger_auto_create_expiry_alert
    AFTER INSERT OR UPDATE OF expiry_date, verification_status, is_archived ON documents
    FOR EACH ROW
    EXECUTE FUNCTION auto_create_expiry_alert();


-- ============================================================
-- 3. One-time cleanup: delete stale alerts for archived documents
-- ============================================================

DELETE FROM document_expiry_alerts
WHERE document_id IN (
    SELECT id FROM documents WHERE COALESCE(is_archived, FALSE) = TRUE
);
