#!/usr/bin/env python3
"""
Database initialization script for the Multi-Agent Support System.

This script sets up the necessary database schema and initial data.
"""

import asyncio
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import create_engine, text
from src.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database():
    """Initialize the database schema."""
    try:
        # Create database engine
        engine = create_engine(settings.database_url)
        logger.info(f"Connecting to database: {settings.database_url}")
        
        # Read schema file
        schema_file = os.path.join(
            os.path.dirname(__file__), 
            '..', 
            'migrations', 
            '001_initial_schema.sql'
        )
        
        if not os.path.exists(schema_file):
            logger.warning("Schema file not found. Creating basic schema...")
            await create_basic_schema(engine)
        else:
            with open(schema_file, 'r') as f:
                schema_sql = f.read()
            
            # Execute schema
            with engine.begin() as conn:
                conn.execute(text(schema_sql))
            
            logger.info("Database schema initialized from migration file")
        
        # Verify tables were created
        await verify_schema(engine)
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        sys.exit(1)


async def create_basic_schema(engine):
    """Create basic database schema."""
    schema_sql = """
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
    
    -- Issues Table
    CREATE TABLE issues (
        issue_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        severity TEXT NOT NULL,
        symptoms JSONB NOT NULL,
        diagnostic_questions JSONB,
        tools JSONB,
        embedding vector(1536),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Create vector index for similarity search
    CREATE INDEX issues_embedding_idx ON issues 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    
    -- Tool Registry Table
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
    
    -- Conversation Archive Table
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
    
    -- Rollback Tokens Table
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
    
    -- Create indexes
    CREATE INDEX conversation_archive_session_idx ON conversation_archive(session_id);
    CREATE INDEX conversation_archive_user_idx ON conversation_archive(user_id);
    CREATE INDEX rollback_tokens_session_idx ON rollback_tokens(session_id);
    CREATE INDEX rollback_tokens_expires_idx ON rollback_tokens(expires_at);
    
    -- Insert sample tools
    INSERT INTO tool_registry (name, description, category, config) VALUES
    ('search_knowledge_base', 'Search knowledge base for relevant articles', 'database', '{"index": "support_articles"}'),
    ('check_user_permissions', 'Check user permissions and access rights', 'auth', '{"require_admin": false}'),
    ('run_diagnostics', 'Run system diagnostics', 'system', '{"timeout_seconds": 30}'),
    ('create_ticket', 'Create support ticket in external system', 'external', '{"endpoint": "/api/tickets"}'),
    ('escalate_to_human', 'Escalate to human agent', 'workflow', '{"priority": "high"}')
    ON CONFLICT (name) DO NOTHING;
    
    -- Insert sample issues
    INSERT INTO issues (title, description, category, severity, symptoms, diagnostic_questions) VALUES
    ('Login Issues', 'User cannot login to the application', 'Authentication', 'Medium', 
     '{"symptom": "Login failed", "frequency": "Always"}',
     ['What error message do you see?', 'When did this start?']),
    ('Performance Slow', 'Application is running slowly', 'Performance', 'High',
     '{"symptom": "Slow response times", "affected_pages": ["dashboard", "reports"]}',
     ['Which pages are slow?', 'How long does it take to load?']),
    ('Data Not Showing', 'Expected data is not displaying', 'Data', 'Medium',
     '{"symptom": "Missing data", "data_type": "Reports"}',
     ['What data should be showing?', 'Is this a recent issue?'])
    ON CONFLICT DO NOTHING;
    """
    
    with engine.begin() as conn:
        conn.execute(text(schema_sql))
    
    logger.info("Basic database schema created")


async def verify_schema(engine):
    """Verify that the schema was created correctly."""
    expected_tables = ['issues', 'tool_registry', 'conversation_archive', 'rollback_tokens']
    
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """))
        existing_tables = [row[0] for row in result]
    
    missing_tables = [table for table in expected_tables if table not in existing_tables]
    
    if missing_tables:
        raise Exception(f"Missing tables: {missing_tables}")
    
    logger.info(f"All expected tables created: {expected_tables}")


if __name__ == "__main__":
    asyncio.run(init_database())