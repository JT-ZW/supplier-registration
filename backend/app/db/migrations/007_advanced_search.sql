-- Advanced Search Features Migration
-- Adds saved searches and search history for admin users

-- ============================================================
-- Saved Search Filters
-- ============================================================

CREATE TABLE IF NOT EXISTS saved_searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Owner
    admin_id UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    
    -- Search details
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Filter parameters (stored as JSONB for flexibility)
    filters JSONB NOT NULL DEFAULT '{}',
    
    -- Metadata
    is_default BOOLEAN DEFAULT FALSE,
    use_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT unique_saved_search_name_per_admin UNIQUE (admin_id, name)
);

-- Indexes
CREATE INDEX idx_saved_searches_admin ON saved_searches(admin_id);
CREATE INDEX idx_saved_searches_default ON saved_searches(admin_id, is_default) WHERE is_default = TRUE;
CREATE INDEX idx_saved_searches_used ON saved_searches(admin_id, last_used_at DESC);

-- ============================================================
-- Search History
-- ============================================================

CREATE TABLE IF NOT EXISTS search_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- User
    admin_id UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    
    -- Search parameters
    search_params JSONB NOT NULL DEFAULT '{}',
    
    -- Results
    result_count INTEGER,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Optional: Link to saved search if this history entry was from a saved search
    saved_search_id UUID REFERENCES saved_searches(id) ON DELETE SET NULL
);

-- Indexes
CREATE INDEX idx_search_history_admin ON search_history(admin_id, created_at DESC);
CREATE INDEX idx_search_history_saved_search ON search_history(saved_search_id);

-- Simple index for cleanup queries (without WHERE clause)
CREATE INDEX idx_search_history_created_at ON search_history(created_at);

-- ============================================================
-- Functions
-- ============================================================

-- Function to record search in history
CREATE OR REPLACE FUNCTION record_search(
    p_admin_id UUID,
    p_search_params JSONB,
    p_result_count INTEGER,
    p_saved_search_id UUID DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_history_id UUID;
BEGIN
    -- Insert search history
    INSERT INTO search_history (
        admin_id,
        search_params,
        result_count,
        saved_search_id
    ) VALUES (
        p_admin_id,
        p_search_params,
        p_result_count,
        p_saved_search_id
    )
    RETURNING id INTO v_history_id;
    
    -- Update saved search usage if applicable
    IF p_saved_search_id IS NOT NULL THEN
        UPDATE saved_searches
        SET 
            use_count = use_count + 1,
            last_used_at = CURRENT_TIMESTAMP
        WHERE id = p_saved_search_id;
    END IF;
    
    RETURN v_history_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get popular searches for an admin
CREATE OR REPLACE FUNCTION get_popular_searches(
    p_admin_id UUID,
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE(
    search_params JSONB,
    usage_count BIGINT,
    last_used TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sh.search_params,
        COUNT(*)::BIGINT as usage_count,
        MAX(sh.created_at) as last_used
    FROM search_history sh
    WHERE sh.admin_id = p_admin_id
    AND sh.created_at > CURRENT_TIMESTAMP - INTERVAL '30 days'
    GROUP BY sh.search_params
    ORDER BY usage_count DESC, last_used DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to cleanup old search history
CREATE OR REPLACE FUNCTION cleanup_old_search_history(
    p_days_to_keep INTEGER DEFAULT 90
)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM search_history
    WHERE created_at < CURRENT_TIMESTAMP - (p_days_to_keep || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Triggers
-- ============================================================

-- Update timestamp on saved search update
CREATE OR REPLACE FUNCTION update_saved_search_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_saved_search_timestamp
    BEFORE UPDATE ON saved_searches
    FOR EACH ROW
    EXECUTE FUNCTION update_saved_search_timestamp();

-- ============================================================
-- Comments
-- ============================================================

COMMENT ON TABLE saved_searches IS 'Admin user saved search filter combinations';
COMMENT ON TABLE search_history IS 'Track search queries for analytics and quick re-run';
COMMENT ON FUNCTION record_search IS 'Records a search execution and updates saved search statistics';
COMMENT ON FUNCTION get_popular_searches IS 'Returns most frequently used searches for an admin';
COMMENT ON FUNCTION cleanup_old_search_history IS 'Removes search history older than specified days';
