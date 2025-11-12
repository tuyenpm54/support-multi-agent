-- Modified Database Schema for Neon PostgreSQL (without pgvector initially)
-- This file creates the basic schema that can work without pgvector extension
-- pgvector can be added later when available

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Agent Phases Enum
CREATE TYPE agent_phase AS ENUM (
    'CLASSIFY',
    'REQUIRED_INFO', 
    'VALIDATE',
    'FIX',
    'COMPLETE',
    'ESCALATE'
);

-- Issues Table - Stores known issues and their solutions (without vector initially)
CREATE TABLE issues (
    issue_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
    symptoms JSONB NOT NULL,
    diagnostic_questions JSONB,
    tools JSONB,
    embedding VECTOR(1536),  -- Will work once pgvector is installed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tool Registry Table - Available tools for agents
CREATE TABLE tool_registry (
    tool_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    category TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    permissions JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Conversation Archive Table - Historical conversations for learning
CREATE TABLE conversation_archive (
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

-- Rollback Tokens Table - Transaction rollback capabilities
CREATE TABLE rollback_tokens (
    token_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    actions JSONB NOT NULL,
    rollback_data JSONB NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create performance indexes (without vector index initially)
CREATE INDEX conversation_archive_session_idx ON conversation_archive(session_id);
CREATE INDEX conversation_archive_user_idx ON conversation_archive(user_id);
CREATE INDEX conversation_archive_created_idx ON conversation_archive(created_at);
CREATE INDEX rollback_tokens_session_idx ON rollback_tokens(session_id);
CREATE INDEX rollback_tokens_expires_idx ON rollback_tokens(expires_at);
CREATE INDEX rollback_tokens_used_idx ON rollback_tokens(used) WHERE used = FALSE;

-- Create category and severity indexes for issues
CREATE INDEX issues_category_idx ON issues(category);
CREATE INDEX issues_severity_idx ON issues(severity);
CREATE INDEX issues_created_idx ON issues(created_at);

-- Insert sample tools
INSERT INTO tool_registry (name, description, category, config) VALUES
('search_knowledge_base', 'Search knowledge base for relevant articles', 'database', '{"index": "support_articles", "limit": 10}'),
('check_user_permissions', 'Check user permissions and access rights', 'auth', '{"require_admin": false, "cache_ttl": 300}'),
('run_diagnostics', 'Run system diagnostics and health checks', 'system', '{"timeout_seconds": 30, "parallel": true}'),
('create_ticket', 'Create support ticket in external system', 'external', '{"endpoint": "/api/tickets", "priority": "normal"}'),
('escalate_to_human', 'Escalate to human agent', 'workflow', '{"priority": "high", "notification": true}'),
('query_database', 'Execute database queries for issue investigation', 'database', '{"readonly": true, "timeout": 10}'),
('check_system_status', 'Check overall system health and service status', 'monitoring', '{"services": ["api", "database", "redis"]}')
ON CONFLICT (name) DO NOTHING;

-- Insert sample issues without embeddings initially
INSERT INTO issues (title, description, category, severity, symptoms, diagnostic_questions) VALUES
('Login Issues', 'User cannot login to the application due to authentication problems', 'Authentication', 'Medium', 
 '{"symptom": "Login failed", "error_messages": ["Invalid credentials", "Account locked"], "frequency": "Always"}',
 '{"questions": ["What error message do you see?", "When did this start?", "Have you tried resetting your password?"]}'),

('Performance Slow', 'Application is running slowly and experiencing high response times', 'Performance', 'High',
 '{"symptom": "Slow response times", "affected_pages": ["dashboard", "reports"], "average_load_time": "5-10 seconds"}',
 '{"questions": ["Which pages are slow?", "How long does it take to load?", "Is this during specific times?"]}'),

('Data Not Showing', 'Expected data is not displaying in reports or dashboards', 'Data', 'Medium',
 '{"symptom": "Missing data", "data_type": "Reports", "time_range": "Last 30 days"}',
 '{"questions": ["What data should be showing?", "Is this a recent issue?", "Can other users see the data?"]}'),

('Integration Errors', 'Third-party integrations are failing or returning errors', 'Integration', 'High',
 '{"symptom": "API errors", "services": ["payment_gateway", "email_service"], "error_rate": "15%"}',
 '{"questions": ["Which integrations are failing?", "What error messages are you seeing?", "When did this start?"]}'),

('User Access Denied', 'Users are getting access denied errors for resources they should have access to', 'Authorization', 'Medium',
 '{"symptom": "Access denied", "resources": ["reports", "admin_panel"], "user_roles": ["manager", "analyst"]}',
 '{"questions": ["What resource are you trying to access?", "What is your user role?", "Can other users with the same role access it?"]}')
ON CONFLICT DO NOTHING;

-- Create a function to automatically update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers for updated_at
CREATE TRIGGER update_issues_updated_at BEFORE UPDATE ON issues
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tool_registry_updated_at BEFORE UPDATE ON tool_registry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_conversation_archive_updated_at BEFORE UPDATE ON conversation_archive
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create a view for active issues (not escalated, recent)
CREATE VIEW active_issues AS
SELECT 
    issue_id,
    title,
    description,
    category,
    severity,
    symptoms,
    created_at
FROM issues 
WHERE created_at > NOW() - INTERVAL '30 days'
ORDER BY created_at DESC;

-- Create a temporary function for text-based similarity search (until pgvector is available)
CREATE OR REPLACE FUNCTION search_similar_issues_text(
    query_text TEXT,
    limit_count INT DEFAULT 5
)
RETURNS TABLE (
    issue_id UUID,
    title TEXT,
    description TEXT,
    category TEXT,
    severity TEXT,
    similarity_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        i.issue_id,
        i.title,
        i.description,
        i.category,
        i.severity,
        -- Simple text similarity based on keyword matching for now
        CASE 
            WHEN LOWER(i.title) LIKE LOWER('%' || query_text || '%') THEN 1.0
            WHEN LOWER(i.description) LIKE LOWER('%' || query_text || '%') THEN 0.8
            WHEN EXISTS (SELECT 1 FROM jsonb_array_elements_text(i.symptoms) as sym WHERE LOWER(sym) LIKE LOWER('%' || query_text || '%')) THEN 0.6
            ELSE 0.3
        END as similarity_score
    FROM issues i
    WHERE 
        LOWER(i.title) LIKE LOWER('%' || query_text || '%') OR
        LOWER(i.description) LIKE LOWER('%' || query_text || '%') OR
        EXISTS (SELECT 1 FROM jsonb_array_elements_text(i.symptoms) as sym WHERE LOWER(sym) LIKE LOWER('%' || query_text || '%'))
    ORDER BY similarity_score DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Create a function to check and enable pgvector when available
CREATE OR REPLACE FUNCTION enable_pgvector_if_available()
RETURNS BOOLEAN AS $$
BEGIN
    -- Try to create the extension, but don't fail if it's not available
    BEGIN
        EXECUTE 'CREATE EXTENSION IF NOT EXISTS pgvector';
        
        -- If successful, add vector column and index
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'issues' AND column_name = 'embedding') THEN
            EXECUTE 'ALTER TABLE issues ADD COLUMN embedding vector(1536)';
            EXECUTE 'CREATE INDEX issues_embedding_idx ON issues USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)';
        END IF;
        
        -- Replace text search function with vector search
        DROP FUNCTION IF EXISTS search_similar_issues_text(TEXT, INT);
        
        CREATE OR REPLACE FUNCTION search_similar_issues(
            query_embedding vector(1536),
            similarity_threshold FLOAT DEFAULT 0.7,
            limit_count INT DEFAULT 5
        )
        RETURNS TABLE (
            issue_id UUID,
            title TEXT,
            description TEXT,
            category TEXT,
            severity TEXT,
            similarity FLOAT
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT 
                i.issue_id,
                i.title,
                i.description,
                i.category,
                i.severity,
                1 - (i.embedding <=> query_embedding) as similarity
            FROM issues i
            WHERE 1 - (i.embedding <=> query_embedding) > similarity_threshold
            ORDER BY similarity DESC
            LIMIT limit_count;
        END;
        $$ LANGUAGE plpgsql;
        
        RETURN TRUE;
        
    EXCEPTION WHEN OTHERS THEN
        -- pgvector not available, continue with text-based search
        RETURN FALSE;
    END;
END;
$$ LANGUAGE plpgsql;

-- Create a view for database status
CREATE VIEW database_status AS
SELECT 
    'database' as component,
    'connected' as status,
    NOW() as checked_at,
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'issues') THEN 'schema_created'
        ELSE 'schema_needed'
    END as schema_status,
    CASE 
        WHEN EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgvector') THEN 'pgvector_available'
        ELSE 'pgvector_missing'
    END as vector_support,
    (SELECT COUNT(*) FROM issues) as issues_count,
    (SELECT COUNT(*) FROM tool_registry) as tools_count;

COMMENT ON VIEW database_status IS 'Shows current database connection and setup status';