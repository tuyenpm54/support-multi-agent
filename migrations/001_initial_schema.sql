-- Multi-Agent Support System Initial Schema
-- This file contains the complete database schema for the system

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- Agent Phases Enum
CREATE TYPE agent_phase AS ENUM (
    'CLASSIFY',
    'REQUIRED_INFO', 
    'VALIDATE',
    'FIX',
    'COMPLETE',
    'ESCALATE'
);

-- Issues Table - Stores known issues and their solutions
CREATE TABLE issues (
    issue_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
    symptoms JSONB NOT NULL,
    diagnostic_questions JSONB,
    tools JSONB,
    embedding vector(1536),
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

-- Create vector index for semantic search
CREATE INDEX issues_embedding_idx ON issues 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Create performance indexes
CREATE INDEX conversation_archive_session_idx ON conversation_archive(session_id);
CREATE INDEX conversation_archive_user_idx ON conversation_archive(user_id);
CREATE INDEX conversation_archive_created_idx ON conversation_archive(created_at);
CREATE INDEX rollback_tokens_session_idx ON rollback_tokens(session_id);
CREATE INDEX rollback_tokens_expires_idx ON rollback_tokens(expires_at);
CREATE INDEX rollback_tokens_used_idx ON rollback_tokens(used) WHERE used = FALSE;

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

-- Insert sample issues with embeddings (placeholder values - real embeddings would be generated)
INSERT INTO issues (title, description, category, severity, symptoms, diagnostic_questions, embedding) VALUES
('Login Issues', 'User cannot login to the application due to authentication problems', 'Authentication', 'Medium', 
 '{"symptom": "Login failed", "error_messages": ["Invalid credentials", "Account locked"], "frequency": "Always"}',
 ['What error message do you see?', 'When did this start?', 'Have you tried resetting your password?'],
 '[0.1, 0.2, 0.3, ...]'),  -- This would be a real 1536-dimensional vector

('Performance Slow', 'Application is running slowly and experiencing high response times', 'Performance', 'High',
 '{"symptom": "Slow response times", "affected_pages": ["dashboard", "reports"], "average_load_time": "5-10 seconds"}',
 ['Which pages are slow?', 'How long does it take to load?', 'Is this during specific times?'],
 '[0.2, 0.3, 0.4, ...]'),

('Data Not Showing', 'Expected data is not displaying in reports or dashboards', 'Data', 'Medium',
 '{"symptom": "Missing data", "data_type": "Reports", "time_range": "Last 30 days"}',
 ['What data should be showing?', 'Is this a recent issue?', 'Can other users see the data?'],
 '[0.3, 0.4, 0.5, ...]'),

('Integration Errors', 'Third-party integrations are failing or returning errors', 'Integration', 'High',
 '{"symptom": "API errors", "services": ["payment_gateway", "email_service"], "error_rate": "15%"}',
 ['Which integrations are failing?', 'What error messages are you seeing?', 'When did this start?'],
 '[0.4, 0.5, 0.6, ...]'),

('User Access Denied', 'Users are getting access denied errors for resources they should have access to', 'Authorization', 'Medium',
 '{"symptom": "Access denied", "resources": ["reports", "admin_panel"], "user_roles": ["manager", "analyst"]}',
 ['What resource are you trying to access?', 'What is your user role?', 'Can other users with the same role access it?'],
 '[0.5, 0.6, 0.7, ...]')
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

-- Create a function for semantic similarity search
CREATE OR REPLACE FUNCTION search_similar_issues(
    query_embedding vector(1532),
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