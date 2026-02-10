-- Notification system schema
-- Supports in-app notifications with read/unread status and action links

-- Create notification types enum
CREATE TYPE notification_type AS ENUM (
    'supplier_status_change',
    'document_verification',
    'document_uploaded',
    'profile_update_requested',
    'application_submitted',
    'new_message',
    'system_announcement'
);

-- Create notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Recipient information
    recipient_id UUID NOT NULL,
    recipient_type VARCHAR(20) NOT NULL CHECK (recipient_type IN ('admin', 'vendor', 'supplier')),
    
    -- Notification content
    type notification_type NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    
    -- Optional action link
    action_url VARCHAR(500),
    action_label VARCHAR(100),
    
    -- Related resource information
    resource_type VARCHAR(50),
    resource_id UUID,
    
    -- Additional context
    metadata JSONB DEFAULT '{}',
    
    -- Status tracking
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP WITH TIME ZONE,
    
    -- Delivery preferences
    send_email BOOLEAN DEFAULT FALSE,
    email_sent BOOLEAN DEFAULT FALSE,
    email_sent_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Soft delete
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for efficient querying
CREATE INDEX idx_notifications_recipient ON notifications(recipient_id, recipient_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_notifications_unread ON notifications(recipient_id, is_read) WHERE deleted_at IS NULL AND is_read = FALSE;
CREATE INDEX idx_notifications_type ON notifications(type) WHERE deleted_at IS NULL;
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_notifications_resource ON notifications(resource_type, resource_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_notifications_expires ON notifications(expires_at) WHERE expires_at IS NOT NULL AND deleted_at IS NULL;

-- Create function to auto-expire old notifications
CREATE OR REPLACE FUNCTION expire_old_notifications()
RETURNS void AS $$
BEGIN
    UPDATE notifications
    SET deleted_at = CURRENT_TIMESTAMP
    WHERE expires_at IS NOT NULL
    AND expires_at < CURRENT_TIMESTAMP
    AND deleted_at IS NULL;
END;
$$ LANGUAGE plpgsql;

-- Create function to get unread notification count
CREATE OR REPLACE FUNCTION get_unread_count(
    p_recipient_id UUID,
    p_recipient_type VARCHAR(20)
)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(*)::INTEGER
        FROM notifications
        WHERE recipient_id = p_recipient_id
        AND recipient_type = p_recipient_type
        AND is_read = FALSE
        AND deleted_at IS NULL
        AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
    );
END;
$$ LANGUAGE plpgsql;

-- Create function to mark notifications as read
CREATE OR REPLACE FUNCTION mark_notifications_read(
    p_notification_ids UUID[]
)
RETURNS INTEGER AS $$
DECLARE
    affected_count INTEGER;
BEGIN
    UPDATE notifications
    SET is_read = TRUE,
        read_at = CURRENT_TIMESTAMP
    WHERE id = ANY(p_notification_ids)
    AND is_read = FALSE
    AND deleted_at IS NULL;
    
    GET DIAGNOSTICS affected_count = ROW_COUNT;
    RETURN affected_count;
END;
$$ LANGUAGE plpgsql;

-- Create function to mark all notifications as read for a user
CREATE OR REPLACE FUNCTION mark_all_read(
    p_recipient_id UUID,
    p_recipient_type VARCHAR(20)
)
RETURNS INTEGER AS $$
DECLARE
    affected_count INTEGER;
BEGIN
    UPDATE notifications
    SET is_read = TRUE,
        read_at = CURRENT_TIMESTAMP
    WHERE recipient_id = p_recipient_id
    AND recipient_type = p_recipient_type
    AND is_read = FALSE
    AND deleted_at IS NULL;
    
    GET DIAGNOSTICS affected_count = ROW_COUNT;
    RETURN affected_count;
END;
$$ LANGUAGE plpgsql;

-- Create function to delete old read notifications
CREATE OR REPLACE FUNCTION cleanup_old_notifications(
    p_days_to_keep INTEGER DEFAULT 90
)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    UPDATE notifications
    SET deleted_at = CURRENT_TIMESTAMP
    WHERE is_read = TRUE
    AND read_at < CURRENT_TIMESTAMP - (p_days_to_keep || ' days')::INTERVAL
    AND deleted_at IS NULL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Add helpful comments
COMMENT ON TABLE notifications IS 'In-app notification system for admins and vendors';
COMMENT ON COLUMN notifications.recipient_type IS 'Type of user receiving notification: admin, vendor, or supplier';
COMMENT ON COLUMN notifications.send_email IS 'Whether to also send this notification via email';
COMMENT ON COLUMN notifications.metadata IS 'Additional context data in JSON format';
COMMENT ON COLUMN notifications.expires_at IS 'Optional expiration date for time-sensitive notifications';
