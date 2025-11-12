-- Fix the hybrid search function with proper type casting
DROP FUNCTION IF EXISTS search_issues_hybrid(text,vector,double precision,integer,text[]);

CREATE OR REPLACE FUNCTION search_issues_hybrid(
    query_text TEXT,
    query_embedding vector(1536) DEFAULT NULL,
    min_similarity DOUBLE PRECISION DEFAULT 0.6,
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
        SELECT 
            i.issue_id,
            i.title,
            i.description,
            i.category,
            i.severity,
            i.symptoms,
            i.diagnostic_questions,
            i.tools,
            CAST(1 - (i.embedding <=> query_embedding) AS DOUBLE PRECISION) as similarity,
            CAST(1 - (i.embedding <=> query_embedding) AS DOUBLE PRECISION) as confidence,
            'vector' as search_method,
            i.created_at
        FROM issues i
        WHERE 
            1 - (i.embedding <=> query_embedding) > min_similarity
            AND (category_filter IS NULL OR i.category = ANY(category_filter))
            AND i.embedding IS NOT NULL
        ORDER BY similarity DESC
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
            i.tools,
            -- Calculate keyword-based similarity
            CAST(
                CASE 
                    WHEN lower(i.title) LIKE '%' || lower(query_text) || '%' THEN 0.9
                    WHEN lower(i.description) LIKE '%' || lower(query_text) || '%' THEN 0.7
                    WHEN i.keywords && string_to_array(lower(query_text), ' ') THEN 0.8
                    WHEN i.symptoms::text ILIKE '%' || query_text || '%' THEN 0.6
                    ELSE 0.4
                END AS DOUBLE PRECISION
            ) as similarity,
            -- Keyword confidence (generally lower than vector search)
            CAST(
                CASE 
                    WHEN lower(i.title) LIKE '%' || lower(query_text) || '%' THEN 0.8
                    WHEN i.description LIKE '%' || query_text || '%' THEN 0.6
                    ELSE 0.5
                END AS DOUBLE PRECISION
            ) as confidence,
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

-- Test the functions
SELECT 'Database vector search functions created successfully' as status,
       (SELECT COUNT(*) FROM issues WHERE embedding IS NOT NULL) as issues_with_embeddings,
       (SELECT COUNT(*) FROM issues) as total_issues;