-- Migration 002: Hierarchical Issues Structure
-- This migration transforms the flat issues table into a hierarchical structure
-- to support general issues containing detailed issues with iterative resolution

-- Add new columns to existing issues table for hierarchical structure
ALTER TABLE issues ADD COLUMN IF NOT EXISTS issue_type VARCHAR(20) DEFAULT 'detailed';
ALTER TABLE issues ADD COLUMN IF NOT EXISTS parent_issue_id UUID REFERENCES issues(issue_id);
ALTER TABLE issues ADD COLUMN IF NOT EXISTS searchable_content TEXT;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS keywords JSONB DEFAULT '[]';
ALTER TABLE issues ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 0;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS solution_steps JSONB DEFAULT '[]';
ALTER TABLE issues ADD COLUMN IF NOT EXISTS validation_criteria JSONB DEFAULT '[]';
ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_strategy JSONB DEFAULT '{}';
ALTER TABLE issues ADD COLUMN IF NOT EXISTS child_issue_order JSONB DEFAULT '[]';

-- Create indexes for hierarchical queries
CREATE INDEX IF NOT EXISTS idx_issues_parent ON issues(parent_issue_id);
CREATE INDEX IF NOT EXISTS idx_issues_type ON issues(issue_type);
CREATE INDEX IF NOT EXISTS idx_issues_priority ON issues(priority DESC);

-- Create issue relationships table for complex relationships
CREATE TABLE IF NOT EXISTS issue_relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_id UUID NOT NULL REFERENCES issues(issue_id) ON DELETE CASCADE,
    child_id UUID NOT NULL REFERENCES issues(issue_id) ON DELETE CASCADE,
    relationship_type VARCHAR(20) NOT NULL CHECK (relationship_type IN ('contains', 'related_to', 'alternative')),
    priority INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for relationships
CREATE INDEX IF NOT EXISTS idx_issue_relationships_parent ON issue_relationships(parent_id);
CREATE INDEX IF NOT EXISTS idx_issue_relationships_child ON issue_relationships(child_id);
CREATE INDEX IF NOT EXISTS idx_issue_relationships_type ON issue_relationships(relationship_type);

-- Create issue resolution tracking table
CREATE TABLE IF NOT EXISTS issue_resolution_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    issue_id UUID NOT NULL REFERENCES issues(issue_id),
    status VARCHAR(20) NOT NULL CHECK (status IN ('attempted', 'resolved', 'failed', 'skipped', 'partial')),
    user_feedback TEXT,
    execution_time_seconds INTEGER,
    error_details JSONB,
    metadata JSONB DEFAULT '{}',
    attempted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for resolution tracking
CREATE INDEX IF NOT EXISTS idx_resolution_tracking_session ON issue_resolution_tracking(session_id);
CREATE INDEX IF NOT EXISTS idx_resolution_tracking_issue ON issue_resolution_tracking(issue_id);
CREATE INDEX IF NOT EXISTS idx_resolution_tracking_status ON issue_resolution_tracking(status);

-- Create function to build searchable content
CREATE OR REPLACE FUNCTION build_searchable_content(
    p_title TEXT,
    p_description TEXT,
    p_symptoms JSONB,
    p_keywords JSONB,
    p_category TEXT
) RETURNS TEXT AS $$
BEGIN
    RETURN COALESCE(p_title, '') || ' ' ||
           COALESCE(p_description, '') || ' ' ||
           COALESCE(array_to_string(ARRAY(SELECT jsonb_array_elements_text(p_symptoms)), ' '), '') || ' ' ||
           COALESCE(array_to_string(ARRAY(SELECT jsonb_array_elements_text(p_keywords)), ' '), '') || ' ' ||
           COALESCE(p_category, '');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create trigger to auto-update searchable_content
CREATE OR REPLACE FUNCTION update_searchable_content()
RETURNS TRIGGER AS $$
BEGIN
    NEW.searchable_content = build_searchable_content(
        NEW.title,
        NEW.description,
        NEW.symptoms,
        NEW.keywords,
        NEW.category
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_searchable_content
    BEFORE INSERT OR UPDATE ON issues
    FOR EACH ROW
    EXECUTE FUNCTION update_searchable_content();

-- Create function to get child issues with proper ordering
CREATE OR REPLACE FUNCTION get_child_issues_ordered(
    p_parent_id UUID
) RETURNS TABLE (
    issue_id UUID,
    title TEXT,
    issue_type VARCHAR(20),
    priority INTEGER,
    order_index INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH ordered_children AS (
        SELECT 
            i.issue_id,
            i.title,
            i.issue_type,
            i.priority,
            ROW_NUMBER() OVER (
                ORDER BY 
                    CASE 
                        WHEN i.priority > 0 THEN i.priority * -1
                        ELSE 0
                    END,
                    i.title
            ) as row_num
        FROM issues i
        WHERE i.parent_issue_id = p_parent_id
    )
    SELECT 
        oc.issue_id,
        oc.title,
        oc.issue_type,
        oc.priority,
        oc.row_num - 1 as order_index
    FROM ordered_children oc
    ORDER BY oc.row_num;
END;
$$ LANGUAGE plpgsql;

-- Create function to check if issue has unresolved children
CREATE OR REPLACE FUNCTION has_unresolved_children(
    p_session_id TEXT,
    p_issue_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    unresolved_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO unresolved_count
    FROM issue_resolution_tracking irt
    JOIN issues i ON i.issue_id = irt.issue_id
    WHERE irt.session_id = p_session_id
      AND i.parent_issue_id = p_issue_id
      AND irt.status NOT IN ('resolved', 'skipped');
    
    RETURN unresolved_count > 0;
END;
$$ LANGUAGE plpgsql;

-- Create view for hierarchical issue queries
CREATE OR REPLACE VIEW issue_hierarchy AS
WITH RECURSIVE issue_tree AS (
    -- Base case: root issues (no parent)
    SELECT 
        i.issue_id,
        i.title,
        i.description,
        i.issue_type,
        i.parent_issue_id,
        i.category,
        i.severity,
        i.solution_steps,
        i.validation_criteria,
        i.resolution_strategy,
        i.priority,
        1 as level,
        ARRAY[i.issue_id] as path,
        ARRAY[i.title] as breadcrumb
    FROM issues i
    WHERE i.parent_issue_id IS NULL
    
    UNION ALL
    
    -- Recursive case: child issues
    SELECT 
        i.issue_id,
        i.title,
        i.description,
        i.issue_type,
        i.parent_issue_id,
        i.category,
        i.severity,
        i.solution_steps,
        i.validation_criteria,
        i.resolution_strategy,
        i.priority,
        it.level + 1,
        it.path || i.issue_id,
        it.breadcrumb || i.title
    FROM issues i
    JOIN issue_tree it ON i.parent_issue_id = it.issue_id
)
SELECT * FROM issue_tree
ORDER BY path;

-- Create index for the hierarchical view
CREATE INDEX IF NOT EXISTS idx_issue_hierarchy_path ON issue_hierarchy USING GIN (path);

-- Update existing issues to have hierarchical structure
-- First, create some sample general issues
INSERT INTO issues (
    title, 
    description, 
    category, 
    severity, 
    issue_type, 
    priority,
    resolution_strategy,
    validation_criteria,
    symptoms
) VALUES 
(
    'Vấn đề về công thức và giá thành',
    'Tất cả các vấn đề liên quan đến công thức tính giá thành món ăn',
    'formula',
    'High',
    'general',
    10,
    '{
        "approach": "sequential",
        "user_confirmation_required": true,
        "stop_on_first_success": false,
        "description": "Kiểm tra lần lượt các vấn đề công thức cho đến khi người dùng xác nhận đã giải quyết"
    }',
    '["Người dùng xác nhận vấn đề đã được giải quyết", "Tất cả các chi tiết vấn đề được xử lý"]',
    '["không có giá", "giá sai lệch", "tính toán lỗi", "công thức sai"]'
),
(
    'Vấn đề hiệu suất hệ thống',
    'Các vấn đề liên quan đến tốc độ và hiệu suất của hệ thống',
    'Performance',
    'Medium',
    'general',
    8,
    '{
        "approach": "parallel",
        "user_confirmation_required": true,
        "stop_on_first_success": false,
        "description": "Kiểm tra đồng thời các vấn đề hiệu suất để xác định nguyên nhân chính"
    }',
    '["Hệ thống hoạt động mượt mà", "Thời gian phản hồi chấp nhận được"]',
    '["chậm", "treo", "timeout", "tải chậm"]'
),
(
    'Vấn đề kết nối và đồng bộ dữ liệu',
    'Các vấn đề liên quan đến kết nối mạng và đồng bộ dữ liệu giữa các kho',
    'Integration',
    'High',
    'general',
    9,
    '{
        "approach": "sequential",
        "user_confirmation_required": true,
        "stop_on_first_success": false,
        "description": "Kiểm tra kết nối và đồng bộ theo thứ tự ưu tiên"
    }',
    '["Dữ liệu đồng bộ thành công", "Không có lỗi kết nối"]',
    '["đồng bộ thất bại", "lỗi kết nối", "timeout", "mất kết nối"]'
);

-- Create function to automatically generate embeddings for new content
CREATE OR REPLACE FUNCTION generate_embedding_for_text(text_content TEXT)
RETURNS vector(1536) AS $$
DECLARE
    -- This is a placeholder - in actual implementation, this would call the embedding service
    embedding_vector vector(1536);
BEGIN
    -- For now, return a zero vector - actual embedding generation happens in application layer
    embedding_vector := '[0,0,0,0]'::vector(1536);
    RETURN embedding_vector;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Add comments for documentation
COMMENT ON TABLE issues IS 'Enhanced issues table with hierarchical structure supporting general and detailed issue types';
COMMENT ON TABLE issue_relationships IS 'Defines relationships between issues (contains, related_to, alternative)';
COMMENT ON TABLE issue_resolution_tracking IS 'Tracks resolution attempts for issues across sessions';
COMMENT ON VIEW issue_hierarchy IS 'Hierarchical view of all issues with parent-child relationships';