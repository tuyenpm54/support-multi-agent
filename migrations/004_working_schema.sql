-- Working Database Schema (without pgvector initially)
-- This creates a functional database that works immediately
-- pgvector support can be added later

-- Step 1: Create basic tables and functions

-- Agent Phases Enum
CREATE TYPE IF NOT EXISTS agent_phase AS ENUM (
    'CLASSIFY',
    'REQUIRED_INFO', 
    'VALIDATE',
    'FIX',
    'COMPLETE',
    'ESCALATE'
);

-- Issues Table - Without vector column initially
CREATE TABLE IF NOT EXISTS issues (
    issue_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
    symptoms JSONB NOT NULL,
    diagnostic_questions JSONB,
    tools JSONB,
    keywords TEXT[],  -- Store keywords for text-based search
    embedding_text TEXT,  -- Store text that will be embedded later
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tool Registry Table
CREATE TABLE IF NOT EXISTS tool_registry (
    tool_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    category TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    permissions JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Conversation Archive Table
CREATE TABLE IF NOT EXISTS conversation_archive (
    conversation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    messages JSONB NOT NULL,
    summary TEXT,
    sentiment_score FLOAT,
    resolution_status TEXT,
    issue_id UUID REFERENCES issues(issue_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Rollback Tokens Table
CREATE TABLE IF NOT EXISTS rollback_tokens (
    token_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    actions JSONB NOT NULL,
    rollback_data JSONB NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Step 2: Create indexes for text-based search
CREATE INDEX IF NOT EXISTS issues_title_gin_idx ON issues USING gin(to_tsvector('english', title));
CREATE INDEX IF NOT EXISTS issues_description_gin_idx ON issues USING gin(to_tsvector('english', description));
CREATE INDEX IF NOT EXISTS issues_keywords_gin_idx ON issues USING gin(keywords);
CREATE INDEX IF NOT EXISTS issues_category_idx ON issues(category);
CREATE INDEX IF NOT EXISTS issues_severity_idx ON issues(severity);
CREATE INDEX IF NOT EXISTS issues_created_idx ON issues(created_at);

-- Performance indexes
CREATE INDEX IF NOT EXISTS conversation_archive_session_idx ON conversation_archive(session_id);
CREATE INDEX IF NOT EXISTS conversation_archive_user_idx ON conversation_archive(user_id);
CREATE INDEX IF NOT EXISTS conversation_archive_created_idx ON conversation_archive(created_at);
CREATE INDEX IF NOT EXISTS rollback_tokens_session_idx ON rollback_tokens(session_id);
CREATE INDEX IF NOT EXISTS rollback_tokens_expires_idx ON rollback_tokens(expires_at);
CREATE INDEX IF NOT EXISTS rollback_tokens_used_idx ON rollback_tokens(used) WHERE used = FALSE;

-- Step 3: Insert sample tools
INSERT INTO tool_registry (name, description, category, config) VALUES
('search_knowledge_base', 'Search knowledge base for relevant articles', 'database', '{"index": "support_articles", "limit": 10}'),
('check_user_permissions', 'Check user permissions and access rights', 'auth', '{"require_admin": false, "cache_ttl": 300}'),
('run_diagnostics', 'Run system diagnostics and health checks', 'system', '{"timeout_seconds": 30, "parallel": true}'),
('create_ticket', 'Create support ticket in external system', 'external', '{"endpoint": "/api/tickets", "priority": "normal"}'),
('escalate_to_human', 'Escalate to human agent', 'workflow', '{"priority": "high", "notification": true}'),
('query_database', 'Execute database queries for issue investigation', 'database', '{"readonly": true, "timeout": 10}'),
('check_system_status', 'Check overall system health and service status', 'monitoring', '{"services": ["api", "database", "redis"]}')
ON CONFLICT (name) DO NOTHING;

-- Step 4: Insert sample issues with keywords and text for embedding
INSERT INTO issues (title, description, category, severity, symptoms, diagnostic_questions, keywords, embedding_text) VALUES
('Login Issues', 'User cannot login to the application due to authentication problems', 'Authentication', 'Medium', 
 '{"symptom": "Login failed", "error_messages": ["Invalid credentials", "Account locked"], "frequency": "Always"}',
 '{"questions": ["What error message do you see?", "When did this start?", "Have you tried resetting your password?"]}',
 ARRAY['login', 'authentication', 'password', 'credentials', 'account', 'sign-in'],
 'Login Issues User cannot login to the application due to authentication problems Invalid credentials Account locked'),

('Performance Slow', 'Application is running slowly and experiencing high response times', 'Performance', 'High',
 '{"symptom": "Slow response times", "affected_pages": ["dashboard", "reports"], "average_load_time": "5-10 seconds"}',
 '{"questions": ["Which pages are slow?", "How long does it take to load?", "Is this during specific times?"]}',
 ARRAY['performance', 'slow', 'response time', 'loading', 'dashboard', 'reports', 'speed'],
 'Performance Slow Application running slowly experiencing high response times dashboard reports loading speed'),

('Data Not Showing', 'Expected data is not displaying in reports or dashboards', 'Data', 'Medium',
 '{"symptom": "Missing data", "data_type": "Reports", "time_range": "Last 30 days"}',
 '{"questions": ["What data should be showing?", "Is this a recent issue?", "Can other users see the data?"]}',
 ARRAY['data', 'missing', 'reports', 'dashboard', 'display', 'show', 'not appearing'],
 'Data Not Showing Expected data not displaying in reports dashboards missing data display issues'),

('Integration Errors', 'Third-party integrations are failing or returning errors', 'Integration', 'High',
 '{"symptom": "API errors", "services": ["payment_gateway", "email_service"], "error_rate": "15%"}',
 '{"questions": ["Which integrations are failing?", "What error messages are you seeing?", "When did this start?"]}',
 ARRAY['integration', 'api', 'error', 'third-party', 'external', 'payment', 'email'],
 'Integration Errors Third-party integrations failing returning errors API errors payment gateway email service'),

('User Access Denied', 'Users are getting access denied errors for resources they should have access to', 'Authorization', 'Medium',
 '{"symptom": "Access denied", "resources": ["reports", "admin_panel"], "user_roles": ["manager", "analyst"]}',
 '{"questions": ["What resource are you trying to access?", "What is your user role?", "Can other users with the same role access it?"]}',
 ARRAY['access', 'denied', 'permissions', 'authorization', 'roles', 'security', 'user'],
 'User Access Denied Users access denied errors resources permissions authorization roles security')
ON CONFLICT DO NOTHING;

-- Step 5: Create functions for text-based similarity search
CREATE OR REPLACE FUNCTION search_similar_issues_text(
    query_text TEXT,
    category_filter TEXT[] DEFAULT NULL,
    limit_count INT DEFAULT 5
)
RETURNS TABLE (
    issue_id UUID,
    title TEXT,
    description TEXT,
    category TEXT,
    severity TEXT,
    symptoms JSONB,
    diagnostic_questions JSONB,
    similarity_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    WITH query_ts AS (
        SELECT to_tsvector('english', query_text) as q_ts
    ),
    scored_issues AS (
        SELECT 
            i.issue_id,
            i.title,
            i.description,
            i.category,
            i.severity,
            i.symptoms,
            i.diagnostic_questions,
            -- Calculate similarity score based on multiple factors
            GREATEST(
                -- Title similarity
                CASE WHEN to_tsvector('english', i.title) @@ (SELECT q_ts FROM query_ts) 
                     THEN ts_rank(to_tsvector('english', i.title), (SELECT q_ts FROM query_ts)) 
                     ELSE 0 END * 1.5,
                -- Description similarity  
                CASE WHEN to_tsvector('english', i.description) @@ (SELECT q_ts FROM query_ts)
                     THEN ts_rank(to_tsvector('english', i.description), (SELECT q_ts FROM query_ts))
                     ELSE 0 END,
                -- Keywords match
                CASE WHEN i.keywords && string_to_array(lower(query_text), ' ')
                     THEN 0.8 ELSE 0 END,
                -- Symptom text match
                CASE WHEN i.symptoms::text ILIKE '%' || query_text || '%'
                     THEN 0.6 ELSE 0 END
            ) as similarity_score
        FROM issues i
        WHERE 
            (category_filter IS NULL OR i.category = ANY(category_filter))
            AND (
                to_tsvector('english', i.title) @@ (SELECT q_ts FROM query_ts)
                OR to_tsvector('english', i.description) @@ (SELECT q_ts FROM query_ts)
                OR i.keywords && string_to_array(lower(query_text), ' ')
                OR i.symptoms::text ILIKE '%' || query_text || '%'
            )
    )
    SELECT 
        issue_id, title, description, category, severity, symptoms, diagnostic_questions,
        -- Normalize score to 0-1 range and cap at 1.0
        LEAST(similarity_score, 1.0) as similarity_score
    FROM scored_issues
    WHERE similarity_score > 0.1  -- Minimum similarity threshold
    ORDER BY similarity_score DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Function to search by keywords
CREATE OR REPLACE FUNCTION search_issues_by_keywords(
    keywords TEXT[],
    category_filter TEXT[] DEFAULT NULL,
    limit_count INT DEFAULT 5
)
RETURNS TABLE (
    issue_id UUID,
    title TEXT,
    description TEXT,
    category TEXT,
    severity TEXT,
    match_count INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        i.issue_id,
        i.title,
        i.description,
        i.category,
        i.severity,
        -- Count how many keywords match
        array_length(
            array(
                SELECT k
                FROM unnest(keywords) k
                WHERE k = ANY(i.keywords)
                OR lower(i.title) LIKE '%' || lower(k) || '%'
                OR lower(i.description) LIKE '%' || lower(k) || '%'
            ),
            1
        ) as match_count
    FROM issues i
    WHERE 
        (category_filter IS NULL OR i.category = ANY(category_filter))
        AND (
            i.keywords && keywords
            OR EXISTS (
                SELECT 1 FROM unnest(keywords) k 
                WHERE lower(i.title) LIKE '%' || lower(k) || '%'
                OR lower(i.description) LIKE '%' || lower(k) || '%'
            )
        )
        AND array_length(
            array(
                SELECT k
                FROM unnest(keywords) k
                WHERE k = ANY(i.keywords)
                OR lower(i.title) LIKE '%' || lower(k) || '%'
                OR lower(i.description) LIKE '%' || lower(k) || '%'
            ),
            1
        ) > 0
    ORDER BY match_count DESC, i.created_at DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Step 6: Create trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers
DROP TRIGGER IF EXISTS update_issues_updated_at ON issues;
CREATE TRIGGER update_issues_updated_at BEFORE UPDATE ON issues
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_tool_registry_updated_at ON tool_registry;
CREATE TRIGGER update_tool_registry_updated_at BEFORE UPDATE ON tool_registry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_conversation_archive_updated_at ON conversation_archive;
CREATE TRIGGER update_conversation_archive_updated_at BEFORE UPDATE ON conversation_archive
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Step 7: Create views
CREATE OR REPLACE VIEW active_issues AS
SELECT 
    issue_id,
    title,
    description,
    category,
    severity,
    symptoms,
    keywords,
    created_at,
    updated_at
FROM issues 
WHERE created_at > NOW() - INTERVAL '30 days'
ORDER BY created_at DESC;

CREATE OR REPLACE VIEW database_status AS
SELECT 
    'database' as component,
    'connected' as status,
    NOW() as checked_at,
    'schema_created' as schema_status,
    'text_search_enabled' as vector_support,
    (SELECT COUNT(*) FROM issues) as issues_count,
    (SELECT COUNT(*) FROM tool_registry) as tools_count;

COMMENT ON VIEW database_status IS 'Shows current database connection and setup status';

-- Step 8: Verify setup
SELECT 'Database schema created successfully' as status,
       (SELECT COUNT(*) FROM issues) as sample_issues_loaded,
       (SELECT COUNT(*) FROM tool_registry) as tools_loaded;