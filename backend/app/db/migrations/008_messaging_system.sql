-- Messaging System Migration
-- Enables admin-vendor communication with threaded conversations

-- ============================================================
-- Message Threads
-- ============================================================

CREATE TABLE IF NOT EXISTS message_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Thread subject/topic
    subject VARCHAR(200) NOT NULL,
    
    -- Related entities
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    
    -- Thread metadata
    is_archived BOOLEAN DEFAULT FALSE,
    priority VARCHAR(20) DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    
    -- Latest message tracking
    last_message_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_message_by VARCHAR(10), -- 'admin' or 'vendor'
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_threads_supplier ON message_threads(supplier_id, last_message_at DESC);
CREATE INDEX idx_threads_archived ON message_threads(is_archived, last_message_at DESC);
CREATE INDEX idx_threads_priority ON message_threads(priority, last_message_at DESC) WHERE is_archived = FALSE;

-- ============================================================
-- Messages
-- ============================================================

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Thread association
    thread_id UUID NOT NULL REFERENCES message_threads(id) ON DELETE CASCADE,
    
    -- Sender information
    sender_type VARCHAR(10) NOT NULL CHECK (sender_type IN ('admin', 'vendor')),
    sender_id UUID NOT NULL, -- admin_users.id or suppliers.id
    sender_name VARCHAR(255) NOT NULL,
    
    -- Message content
    message_text TEXT NOT NULL,
    
    -- Attachments (optional - for future enhancement)
    attachments JSONB DEFAULT '[]', -- Array of {name, url, size, type}
    
    -- Read tracking
    read_by_admin BOOLEAN DEFAULT FALSE,
    read_by_vendor BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT check_sender_read_consistency CHECK (
        (sender_type = 'admin' AND read_by_admin = TRUE) OR
        (sender_type = 'vendor' AND read_by_vendor = TRUE) OR
        (sender_type = 'admin' AND read_by_admin = FALSE AND read_by_vendor IN (TRUE, FALSE)) OR
        (sender_type = 'vendor' AND read_by_vendor = FALSE AND read_by_admin IN (TRUE, FALSE))
    )
);

-- Indexes
CREATE INDEX idx_messages_thread ON messages(thread_id, created_at DESC);
CREATE INDEX idx_messages_sender ON messages(sender_type, sender_id);
CREATE INDEX idx_messages_unread_admin ON messages(thread_id) WHERE read_by_admin = FALSE AND sender_type = 'vendor';
CREATE INDEX idx_messages_unread_vendor ON messages(thread_id) WHERE read_by_vendor = FALSE AND sender_type = 'admin';

-- ============================================================
-- Message Categories (for filtering/organizing)
-- ============================================================

CREATE TABLE IF NOT EXISTS message_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    color VARCHAR(50) DEFAULT 'blue',
    icon VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert default categories
INSERT INTO message_categories (name, description, color, icon) VALUES
    ('General Inquiry', 'General questions and information requests', 'blue', 'mail'),
    ('Document Issue', 'Document-related questions or problems', 'yellow', 'file-text'),
    ('Application Status', 'Questions about application status', 'purple', 'clipboard'),
    ('Technical Support', 'Technical issues with the portal', 'red', 'tool'),
    ('Payment/Banking', 'Payment and banking related queries', 'green', 'dollar-sign'),
    ('Compliance', 'Compliance and regulatory questions', 'orange', 'shield')
ON CONFLICT (name) DO NOTHING;

-- Link categories to threads
ALTER TABLE message_threads ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES message_categories(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_threads_category ON message_threads(category_id, last_message_at DESC);

-- ============================================================
-- Notification Preferences
-- ============================================================

-- Add message notification preferences to suppliers table
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS notify_on_message BOOLEAN DEFAULT TRUE;
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS notify_on_status_change BOOLEAN DEFAULT TRUE;
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS notify_on_document_expiry BOOLEAN DEFAULT TRUE;

-- Add to admin users
ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS notify_on_vendor_message BOOLEAN DEFAULT TRUE;

-- ============================================================
-- Functions
-- ============================================================

-- Function to get unread message count for a thread
CREATE OR REPLACE FUNCTION get_unread_count_for_thread(
    p_thread_id UUID,
    p_user_type VARCHAR(10)
)
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    IF p_user_type = 'admin' THEN
        SELECT COUNT(*)::INTEGER INTO v_count
        FROM messages
        WHERE thread_id = p_thread_id
        AND sender_type = 'vendor'
        AND read_by_admin = FALSE;
    ELSIF p_user_type = 'vendor' THEN
        SELECT COUNT(*)::INTEGER INTO v_count
        FROM messages
        WHERE thread_id = p_thread_id
        AND sender_type = 'admin'
        AND read_by_vendor = FALSE;
    ELSE
        v_count := 0;
    END IF;
    
    RETURN v_count;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get total unread messages for a user
CREATE OR REPLACE FUNCTION get_total_unread_messages(
    p_user_id UUID,
    p_user_type VARCHAR(10)
)
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    IF p_user_type = 'admin' THEN
        SELECT COUNT(*)::INTEGER INTO v_count
        FROM messages m
        WHERE m.sender_type = 'vendor'
        AND m.read_by_admin = FALSE;
    ELSIF p_user_type = 'vendor' THEN
        SELECT COUNT(*)::INTEGER INTO v_count
        FROM messages m
        INNER JOIN message_threads t ON m.thread_id = t.id
        WHERE t.supplier_id = p_user_id
        AND m.sender_type = 'admin'
        AND m.read_by_vendor = FALSE;
    ELSE
        v_count := 0;
    END IF;
    
    RETURN v_count;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to mark messages as read
CREATE OR REPLACE FUNCTION mark_messages_as_read(
    p_thread_id UUID,
    p_user_type VARCHAR(10)
)
RETURNS INTEGER AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    IF p_user_type = 'admin' THEN
        UPDATE messages
        SET 
            read_by_admin = TRUE,
            read_at = CURRENT_TIMESTAMP
        WHERE thread_id = p_thread_id
        AND sender_type = 'vendor'
        AND read_by_admin = FALSE;
    ELSIF p_user_type = 'vendor' THEN
        UPDATE messages
        SET 
            read_by_vendor = TRUE,
            read_at = CURRENT_TIMESTAMP
        WHERE thread_id = p_thread_id
        AND sender_type = 'admin'
        AND read_by_vendor = FALSE;
    END IF;
    
    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated;
END;
$$ LANGUAGE plpgsql;

-- Function to create a new thread with first message
CREATE OR REPLACE FUNCTION create_message_thread(
    p_subject VARCHAR(200),
    p_supplier_id UUID,
    p_category_id UUID,
    p_priority VARCHAR(20),
    p_sender_type VARCHAR(10),
    p_sender_id UUID,
    p_sender_name VARCHAR(255),
    p_message_text TEXT
)
RETURNS UUID AS $$
DECLARE
    v_thread_id UUID;
    v_message_id UUID;
BEGIN
    -- Create thread
    INSERT INTO message_threads (
        subject,
        supplier_id,
        category_id,
        priority,
        last_message_by
    ) VALUES (
        p_subject,
        p_supplier_id,
        p_category_id,
        p_priority,
        p_sender_type
    )
    RETURNING id INTO v_thread_id;
    
    -- Create first message
    INSERT INTO messages (
        thread_id,
        sender_type,
        sender_id,
        sender_name,
        message_text,
        read_by_admin,
        read_by_vendor
    ) VALUES (
        v_thread_id,
        p_sender_type,
        p_sender_id,
        p_sender_name,
        p_message_text,
        CASE WHEN p_sender_type = 'admin' THEN TRUE ELSE FALSE END,
        CASE WHEN p_sender_type = 'vendor' THEN TRUE ELSE FALSE END
    )
    RETURNING id INTO v_message_id;
    
    RETURN v_thread_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Triggers
-- ============================================================

-- Update thread timestamp when new message is added
CREATE OR REPLACE FUNCTION update_thread_on_new_message()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE message_threads
    SET 
        last_message_at = NEW.created_at,
        last_message_by = NEW.sender_type,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.thread_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_thread_on_message
    AFTER INSERT ON messages
    FOR EACH ROW
    EXECUTE FUNCTION update_thread_on_new_message();

-- Auto-mark sender's messages as read
CREATE OR REPLACE FUNCTION auto_mark_sender_read()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.sender_type = 'admin' THEN
        NEW.read_by_admin = TRUE;
    ELSIF NEW.sender_type = 'vendor' THEN
        NEW.read_by_vendor = TRUE;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auto_mark_sender_read
    BEFORE INSERT ON messages
    FOR EACH ROW
    EXECUTE FUNCTION auto_mark_sender_read();

-- ============================================================
-- Views for Convenience
-- ============================================================

-- View for thread summary with unread counts
CREATE OR REPLACE VIEW thread_summary AS
SELECT 
    t.id,
    t.subject,
    t.supplier_id,
    s.company_name as supplier_name,
    t.category_id,
    mc.name as category_name,
    mc.color as category_color,
    t.priority,
    t.is_archived,
    t.last_message_at,
    t.last_message_by,
    t.created_at,
    -- Get last message preview
    (SELECT message_text FROM messages WHERE thread_id = t.id ORDER BY created_at DESC LIMIT 1) as last_message,
    -- Count unread for admin
    (SELECT COUNT(*) FROM messages WHERE thread_id = t.id AND sender_type = 'vendor' AND read_by_admin = FALSE)::INTEGER as unread_by_admin,
    -- Count unread for vendor
    (SELECT COUNT(*) FROM messages WHERE thread_id = t.id AND sender_type = 'admin' AND read_by_vendor = FALSE)::INTEGER as unread_by_vendor,
    -- Total message count
    (SELECT COUNT(*) FROM messages WHERE thread_id = t.id)::INTEGER as message_count
FROM message_threads t
INNER JOIN suppliers s ON t.supplier_id = s.id
LEFT JOIN message_categories mc ON t.category_id = mc.id;

-- ============================================================
-- Comments
-- ============================================================

COMMENT ON TABLE message_threads IS 'Conversation threads between admin and vendors';
COMMENT ON TABLE messages IS 'Individual messages within threads';
COMMENT ON TABLE message_categories IS 'Categories for organizing message threads';
COMMENT ON FUNCTION get_unread_count_for_thread IS 'Get unread message count for a specific thread';
COMMENT ON FUNCTION get_total_unread_messages IS 'Get total unread messages for a user across all threads';
COMMENT ON FUNCTION mark_messages_as_read IS 'Mark all unread messages in a thread as read for a user';
COMMENT ON FUNCTION create_message_thread IS 'Create a new message thread with initial message';
COMMENT ON VIEW thread_summary IS 'Convenient view with thread details and unread counts';
