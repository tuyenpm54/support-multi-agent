-- Create proper pgvector schema with vector indexing
-- Neon has the 'vector' extension installed (not 'pgvector')

-- Step 1: Verify vector extension is available
SELECT extname as extension_name, extversion as version 
FROM pg_extension 
WHERE extname = 'vector';

-- Step 2: Create vector index on issues table if not already exists
-- First, add the embedding column if it doesn't exist
ALTER TABLE issues ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- Step 3: Create the proper vector index using ivfflat
CREATE INDEX IF NOT EXISTS issues_embedding_idx ON issues 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Step 4: Create vector similarity search function
CREATE OR REPLACE FUNCTION search_similar_issues_vector(
    query_embedding vector(1536),
    similarity_threshold DOUBLE PRECISION DEFAULT 0.7,
    limit_count INT DEFAULT 5,
    category_filter TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    issue_id UUID,
    title TEXT,
    description TEXT,
    category TEXT,
    severity TEXT,
    symptoms JSONB,
    diagnostic_questions JSONB,
    tools JSONB,
    similarity DOUBLE PRECISION,
    confidence_score DOUBLE PRECISION,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        i.issue_id,
        i.title,
        i.description,
        i.category,
        i.severity,
        i.symptoms,
        i.diagnostic_questions,
        i.tools,
        1 - (i.embedding <=> query_embedding) as similarity,
        -- Calculate confidence based on similarity and recency
        CASE 
            WHEN 1 - (i.embedding <=> query_embedding) > 0.9 THEN 
                1 - (i.embedding <=> query_embedding) * 1.2  -- Very high similarity boost
            WHEN 1 - (i.embedding <=> query_embedding) > 0.8 THEN 
                1 - (i.embedding <=> query_embedding) * 1.1  -- High similarity boost
            ELSE 
                1 - (i.embedding <=> query_embedding)
        END as confidence_score,
        i.created_at,
        i.updated_at
    FROM issues i
    WHERE 
        1 - (i.embedding <=> query_embedding) > similarity_threshold
        AND (category_filter IS NULL OR i.category = ANY(category_filter))
        AND i.embedding IS NOT NULL
    ORDER BY similarity DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Step 5: Create hybrid search that combines vector and text search
CREATE OR REPLACE FUNCTION search_issues_hybrid(
    query_text TEXT,
    query_embedding vector(1536) DEFAULT NULL,
    similarity_threshold DOUBLE PRECISION DEFAULT 0.6,
    limit_count INT DEFAULT 5,
    category_filter TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    issue_id UUID,
    title TEXT,
    description TEXT,
    category TEXT,
    severity TEXT,
    symptoms JSONB,
    diagnostic_questions JSONB,
    tools JSONB,
    similarity DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    search_method TEXT,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    -- If query_embedding is provided, use vector search first
    IF query_embedding IS NOT NULL THEN
        RETURN QUERY
        SELECT * FROM search_similar_issues_vector(
            query_embedding, 
            similarity_threshold, 
            limit_count, 
            category_filter
        );
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
            i.tools,
            -- Calculate keyword-based similarity
            CASE 
                WHEN lower(i.title) LIKE '%' || lower(query_text) || '%' THEN 0.9
                WHEN lower(i.description) LIKE '%' || lower(query_text) || '%' THEN 0.7
                WHEN i.keywords && string_to_array(lower(query_text), ' ') THEN 0.8
                WHEN i.symptoms::text ILIKE '%' || query_text || '%' THEN 0.6
                ELSE 0.4
            END as similarity,
            -- Keyword confidence (generally lower than vector search)
            CASE 
                WHEN lower(i.title) LIKE '%' || lower(query_text) || '%' THEN 0.8
                WHEN i.description LIKE '%' || query_text || '%' THEN 0.6
                ELSE 0.5
            END as confidence,
            'keyword' as search_method,
            i.created_at
        FROM issues i
        WHERE 
            (category_filter IS NULL OR i.category = ANY(category_filter))
            AND (
                lower(i.title) LIKE '%' || lower(query_text) || '%' OR
                lower(i.description) LIKE '%' || lower(query_text) || '%' OR
                i.keywords && string_to_array(lower(query_text), ' ') OR
                i.symptoms::text ILIKE '%' || query_text || '%'
            )
        ORDER BY similarity DESC, confidence DESC
        LIMIT limit_count;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Step 6: Add sample embeddings for existing issues
-- For now, we'll add dummy embeddings, but in production you'd generate these with the LLM
UPDATE issues 
SET embedding = array_fill(0.1::double precision, ARRAY[1536])::vector 
WHERE embedding IS NULL AND title = 'Login Issues';

UPDATE issues 
SET embedding = array_fill(0.2::double precision, ARRAY[1536])::vector 
WHERE embedding IS NULL AND title = 'Performance Slow';

UPDATE issues 
SET embedding = array_fill(0.3::double precision, ARRAY[1536])::vector 
WHERE embedding IS NULL AND title = 'Data Not Showing';

UPDATE issues 
SET embedding = array_fill(0.4::double precision, ARRAY[1536])::vector 
WHERE embedding IS NULL AND title = 'Integration Errors';

UPDATE issues 
SET embedding = array_fill(0.5::double precision, ARRAY[1536])::vector 
WHERE embedding IS NULL AND title = 'User Access Denied';

-- Step 7: Test the setup
SELECT 'Vector search setup complete' as status,
       (SELECT COUNT(*) FROM issues WHERE embedding IS NOT NULL) as issues_with_embeddings,
       (SELECT COUNT(*) FROM issues) as total_issues,
       (SELECT COUNT(*) FROM pg_indexes WHERE indexname = 'issues_embedding_idx') as vector_index_exists;