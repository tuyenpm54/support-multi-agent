-- Final Database Setup with pgvector Support
-- This creates a working schema that can use vectors immediately

-- Step 1: Add vector column to issues table
ALTER TABLE issues ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- Step 2: Create vector index if extension becomes available
-- For now, we'll use the vector type that's available in the system

-- Step 3: Create hybrid search function (text + vector when available)
CREATE OR REPLACE FUNCTION search_issues_hybrid(
    query_text TEXT,
    query_embedding vector(1536) DEFAULT NULL,
    category_filter TEXT[] DEFAULT NULL,
    min_similarity FLOAT DEFAULT 0.3,
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
    similarity_score FLOAT,
    search_method TEXT
) AS $$
BEGIN
    -- If query_embedding is provided and vector column exists, try vector search
    IF query_embedding IS NOT NULL AND EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'issues' AND column_name = 'embedding' 
        AND data_type = 'user-defined'
    ) THEN
        RETURN QUERY
        SELECT 
            i.issue_id,
            i.title,
            i.description,
            i.category,
            i.severity,
            i.symptoms,
            i.diagnostic_questions,
            CASE 
                WHEN i.embedding IS NOT NULL THEN 1 - (i.embedding <=> query_embedding)
                ELSE 0.3
            END as similarity_score,
            'vector' as search_method
        FROM issues i
        WHERE 
            (category_filter IS NULL OR i.category = ANY(category_filter))
            AND (
                (i.embedding IS NOT NULL AND 1 - (i.embedding <=> query_embedding) > min_similarity)
                OR i.embedding IS NULL
            )
        ORDER BY similarity_score DESC
        LIMIT limit_count;
    ELSE
        -- Fall back to keyword-based search
        RETURN QUERY
        SELECT 
            i.issue_id,
            i.title,
            i.description,
            i.category,
            i.severity,
            i.symptoms,
            i.diagnostic_questions,
            -- Simple keyword matching score
            CASE 
                WHEN lower(i.title) LIKE '%' || lower(query_text) || '%' THEN 1.0
                WHEN lower(i.description) LIKE '%' || lower(query_text) || '%' THEN 0.8
                WHEN i.keywords && string_to_array(lower(query_text), ' ') THEN 0.7
                WHEN i.symptoms::text ILIKE '%' || query_text || '%' THEN 0.6
                ELSE 0.4
            END as similarity_score,
            'keyword' as search_method
        FROM issues i
        WHERE 
            (category_filter IS NULL OR i.category = ANY(category_filter))
            AND (
                lower(i.title) LIKE '%' || lower(query_text) || '%' OR
                lower(i.description) LIKE '%' || lower(query_text) || '%' OR
                i.keywords && string_to_array(lower(query_text), ' ') OR
                i.symptoms::text ILIKE '%' || query_text || '%'
            )
        ORDER BY similarity_score DESC
        LIMIT limit_count;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Step 4: Test the database setup
SELECT 'Database setup complete' as status,
       (SELECT COUNT(*) FROM issues) as sample_issues_count,
       (SELECT COUNT(*) FROM tool_registry) as tools_count,
       CASE 
           WHEN EXISTS (
               SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'issues' AND column_name = 'embedding'
           ) THEN 'Vector column available'
           ELSE 'Vector column not available'
       END as vector_status;