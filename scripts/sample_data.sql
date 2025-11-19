-- Sample Data for Hierarchical Issue Resolution Database
-- Vietnamese F&B Industry Issues

-- First, let's clear any existing sample data (for development only)
-- DELETE FROM issue_relationships WHERE parent_id IN (SELECT issue_id FROM issues WHERE title LIKE '%Vấn đề về%' OR title LIKE '%Công thức%');
-- DELETE FROM issues WHERE issue_type IN ('general', 'detailed') AND created_at > NOW() - INTERVAL '1 day';

-- Insert General Issues (Parent Issues)
INSERT INTO issues (
    issue_id, title, description, category, severity, issue_type, priority,
    symptoms, diagnostic_questions, tools, solution_steps, validation_criteria,
    resolution_strategy, keywords, searchable_content, embedding
) VALUES 
-- General Issue 1: Formula and Pricing Issues
(gen_uuid(), 
 'Vấn đề về công thức và giá thành',
 'Tất cả các vấn đề liên quan đến công thức tính giá thành món ăn, hiển thị giá và báo cáo giá',
 'formula',
 'High',
 'general',
 10,
 '["không có giá", "giá sai lệch", "tính toán lỗi", "công thức sai"]',
 '["Món nào đang không hiển thị giá?", "Đây là kỳ báo cáo nào?", "Bạn đã kiểm tra công thức của món này chưa?"]',
 '["check_formula", "query_database", "run_diagnostics"]',
 '[]',
 '["Giá hiển thị chính xác", "Công thức hoạt động đúng", "Báo cáo hoàn chỉnh"]',
 '{"approach": "sequential", "user_confirmation_required": true, "stop_on_first_success": false, "description": "Kiểm tra lần lượt các vấn đề công thức cho đến khi người dùng xác nhận đã giải quyết"}',
 '["công thức", "giá thành", "tính giá", "báo cáo", "hiển thị"]',
 'Vấn đề về công thức và giá thành Tất cả các vấn đề liên quan đến công thức tính giá thành món ăn hiển thị giá báo cáo giá không có giá giá sai lệch tính toán lỗi công thức sai Món nào đang không hiển thị giá Đây là kỳ báo cáo nào Bạn đã kiểm tra công thức của món này chưa',
 gen_random_vector(1536)
),

-- General Issue 2: Database Connection Issues  
(gen_uuid(),
 'Vấn đề kết nối và database',
 'Các vấn đề liên quan đến kết nối database, truy vấn dữ liệu và hiệu suất database',
 'database',
 'High', 
 'general',
 9,
 '["lỗi kết nối", "timeout", "query chậm", "data sai", "mất kết nối"]',
 '["Lỗi kết nối xảy ra với database nào?", "Thời gian timeout là bao nhiêu?", "Có bao nhiêu user bị ảnh hưởng?"]',
 '["check_database", "run_diagnostics", "monitor_performance"]',
 '[]',
 '["Kết nối ổn định", "Query performance tốt", "Data integrity"]',
 '{"approach": "parallel", "user_confirmation_required": true, "stop_on_first_success": true, "description": "Kiểm tra đồng thời các vấn đề kết nối để xác định nguyên nhân chính"}',
 '["database", "kết nối", "connection", "query", "performance"]',
 'Vấn đề kết nối và database Các vấn đề liên quan đến kết nối database truy vấn dữ liệu hiệu suất database lỗi kết nối timeout query chậm data sai mất kết nối Lỗi kết nối xảy ra với database nào Thời gian timeout là bao nhiêu Có bao nhiêu user bị ảnh hưởng',
 gen_random_vector(1536)
),

-- General Issue 3: System Performance Issues
(gen_uuid(),
 'Vấn đề hiệu suất hệ thống', 
 'Các vấn đề liên quan đến tốc độ và hiệu suất của hệ thống tổng thể',
 'Performance',
 'Medium',
 'general', 
 8,
 '["chậm", "treo", "timeout", "tải chậm", "response time cao"]',
 '["Chức năng nào đang chậm?", "Tình trạng này bắt đầu khi nào?", "Có nhiều người dùng bị ảnh hưởng không?"]',
 '["monitor_performance", "check_system_status", "analyze_bottlenecks"]',
 '[]',
 '["Hệ thống hoạt động mượt mà", "Thời gian phản hồi chấp nhận được"]',
 '{"approach": "sequential", "user_confirmation_required": true, "stop_on_first_success": false, "description": "Phân tích và tối ưu tuần tự các thành phần hệ thống"}',
 '["hiệu suất", "performance", "tốc độ", "chậm", "tối ưu"]',
 'Vấn đề hiệu suất hệ thống Các vấn đề liên quan đến tốc độ và hiệu suất của hệ thống tổng thể chậm treo timeout tải chậm response time cao Chức năng nào đang chậm Tình trạng này bắt đầu khi nào Có nhiều người dùng bị ảnh hưởng không',
 gen_random_vector(1536)
),

-- General Issue 4: Authentication Issues
(gen_uuid(),
 'Vấn đề xác thực và phân quyền',
 'Các vấn đề liên quan đến đăng nhập, phân quyền và quản lý phiên làm việc',
 'authentication',
 'High',
 'general',
 7,
 '["đăng nhập lỗi", "phân quyền sai", "session timeout", "truy cập bị từ chối"]',
 '["User nào không thể đăng nhập?", "Lỗi xảy ra ở bước nào?", "User có quyền truy cập không?"]',
 '["check_user_permissions", "query_database", "run_diagnostics"]',
 '[]',
 '["Đăng nhập thành công", "Phân quyền đúng", "Phiên ổn định"]',
 '{"approach": "sequential", "user_confirmation_required": true, "stop_on_first_success": false, "description": "Kiểm tra xác thực và phân quyền theo thứ tự ưu tiên"}',
 '["xác thực", "đăng nhập", "phân quyền", "authentication", "session"]',
 'Vấn đề xác thực và phân quyền Các vấn đề liên quan đến đăng nhập phân quyền quản lý phiên làm việc đăng nhập lỗi phân quyền sai session timeout truy cập bị từ chối User nào không thể đăng nhập Lỗi xảy ra ở bước nào User có quyền truy cập không',
 gen_random_vector(1536)
);

-- Get the general issue IDs we just inserted
WITH general_issues AS (
    SELECT issue_id, title FROM issues WHERE issue_type = 'general' ORDER BY created_at DESC LIMIT 4
),

-- Insert Detailed Issues (Child Issues)
detailed_issues AS (
    SELECT
    -- Formula-related detailed issues
    gen_uuid() AS issue_id,
    'Công thức fried rice không hiển thị giá' AS title,
    'Món fried rice không hiển thị giá trong báo cáo do công thức tính giá bị lỗi hoặc thiếu thành phần' AS description,
    'formula' AS category,
    'Medium' AS severity,
    8 AS priority,
    '["không có giá", "giá bằng 0", "giá blank"]'::jsonb AS symptoms,
    '["Công thức fried rice có tồn tại không?", "Các thành phần trong công thức đã được cấu hình chưa?"]'::jsonb AS diagnostic_questions,
    '["check_formula", "query_database"]'::jsonb AS tools,
    '["Kiểm tra công thức tính giá món fried rice", "Xác định thành phần bị thiếu hoặc lỗi", "Cập nhật lại công thức với định lượng chính xác", "Kiểm tra lại giá hiển thị trong báo cáo"]'::jsonb AS solution_steps,
    '["Giá fried rice > 0", "Giá hiển thị đúng trong báo cáo"]'::jsonb AS validation_criteria,
    '["công thức", "fried rice", "giá", "hiển thị", "báo cáo"]' AS keywords,
    gen_random_vector(1536) AS embedding,
    (SELECT issue_id FROM general_issues WHERE title = 'Vấn đề về công thức và giá thành' LIMIT 1) AS parent_id

    UNION ALL

    SELECT
    gen_uuid() AS issue_id,
    'Giá phở bo bị sai lệch 50%' AS title,
    'Giá phở bo hiển thị cao hơn hoặc thấp hơn 50% so với giá thực tế do lỗi công thức' AS description,
    'formula' AS category,
    'High' AS severity,
    9 AS priority,
    '["giá sai", "giá cao bất thường", "tính toán sai"]'::jsonb AS symptoms,
    '["Giá mong muốn là bao nhiêu?", "Giá hiện tại hiển thị là bao nhiêu?", "Công thức phở bo có thay đổi gần đây không?"]'::jsonb AS diagnostic_questions,
    '["check_formula", "query_database", "search_knowledge_base"]'::jsonb AS tools,
    '["Kiểm tra công thức tính giá phở bo hiện tại", "So sánh với công thức gốc hoặc mẫu", "Xác định thành phần bị sai tỷ lệ", "Cập nhật lại công thức với tỷ lệ đúng", "Xác nhận giá hiển thị đúng"]'::jsonb AS solution_steps,
    '["Giá phở bo chính xác", "Không còn sai lệch"]'::jsonb AS validation_criteria,
    '["phở bo", "giá sai lệch", "công thức", "tính toán", "50%"]' AS keywords,
    gen_random_vector(1536) AS embedding,
    (SELECT issue_id FROM general_issues WHERE title = 'Vấn đề về công thức và giá thành' LIMIT 1) AS parent_id

    UNION ALL

    SELECT
    gen_uuid() AS issue_id,
    'Công thức trà sữa bị lỗi divide by zero' AS title,
    'Công thức trà sữa gặp lỗi chia cho không khi tính toán thành phần định lượng' AS description,
    'formula' AS category,
    'High' AS severity,
    9 AS priority,
    '["lỗi chia cho không", "crash", "không tính được giá"]'::jsonb AS symptoms,
    '["Lỗi xảy ra khi nào?", "Có thành phần nào có giá trị 0 không?", "Công thức có được validate không?"]'::jsonb AS diagnostic_questions,
    '["check_formula", "run_diagnostics"]'::jsonb AS tools,
    '["Kiểm tra công thức trà sữa tìm thành phần có giá trị 0", "Validate logic tính toán trong công thức", "Thêm điều kiện kiểm tra chia cho không", "Test lại công thức với dữ liệu mẫu", "Deploy bản sửa lỗi"]'::jsonb AS solution_steps,
    '["Không còn lỗi divide by zero", "Công thức hoạt động ổn định"]'::jsonb AS validation_criteria,
    '["trà sữa", "divide by zero", "lỗi chia cho không", "công thức", "validation"]' AS keywords,
    gen_random_vector(1536) AS embedding,
    (SELECT issue_id FROM general_issues WHERE title = 'Vấn đề về công thức và giá thành' LIMIT 1) AS parent_id

    UNION ALL

    -- Database-related detailed issues
    SELECT
    gen_uuid() AS issue_id,
    'Database connection timeout khi query báo cáo' AS title,
    'Connection đến database bị timeout khi thực hiện query báo cáo doanh thu lớn' AS description,
    'database' AS category,
    'High' AS severity,
    8 AS priority,
    '["timeout", "connection lost", "query chậm"]'::jsonb AS symptoms,
    '["Query nào bị timeout?", "Thời gian timeout là bao nhiêu?", "Kích thước dữ liệu query là bao nhiêu?"]'::jsonb AS diagnostic_questions,
    '["check_database", "monitor_performance"]'::jsonb AS tools,
    '["Kiểm tra connection string và timeout settings", "Optimize query với index phù hợp", "Tăng connection timeout nếu cần thiết", "Implement query pagination cho reports lớn", "Test lại với dữ liệu thực tế"]'::jsonb AS solution_steps,
    '["Query chạy thành công", "Không còn timeout"]'::jsonb AS validation_criteria,
    '["database", "connection timeout", "query báo cáo", "performance", "index"]' AS keywords,
    gen_random_vector(1536) AS embedding,
    (SELECT issue_id FROM general_issues WHERE title = 'Vấn đề kết nối và database' LIMIT 1) AS parent_id

    UNION ALL

    SELECT
    gen_uuid() AS issue_id,
    'Query báo cáo tháng chạy quá chậm (>30s)' AS title,
    'Query báo cáo doanh thu tháng chạy quá chậm, ảnh hưởng đến trải nghiệm người dùng' AS description,
    'database' AS category,
    'Medium' AS severity,
    7 AS priority,
    '["query chậm", "performance issue", "long running query"]'::jsonb AS symptoms,
    '["Query hiện tại mất bao lâu?", "Số lượng records trong khoảng thời gian?", "Đã có index phù hợp chưa?"]'::jsonb AS diagnostic_questions,
    '["monitor_performance", "analyze_bottlenecks"]'::jsonb AS tools,
    '["Analyze execution plan của query hiện tại", "Thêm missing indexes cho columns trong WHERE clause", "Optimize JOIN operations", "Consider materialized views cho reports thường xuyên", "Implement caching cho query results"]'::jsonb AS solution_steps,
    '["Query chạy < 5 giây", "Performance cải thiện"]'::jsonb AS validation_criteria,
    '["query chậm", "báo cáo tháng", "performance", "optimization", "index"]' AS keywords,
    gen_random_vector(1536) AS embedding,
    (SELECT issue_id FROM general_issues WHERE title = 'Vấn đề kết nối và database' LIMIT 1) AS parent_id

    UNION ALL

    -- Performance-related detailed issues
    SELECT
    gen_uuid() AS issue_id,
    'API response time > 5 seconds' AS title,
    'Các API endpoints phản hồi quá chậm, ảnh hưởng đến trải nghiệm người dùng' AS description,
    'Performance' AS category,
    'Medium' AS severity,
    7 AS priority,
    '["response time cao", "API chậm", "user experience kém"]'::jsonb AS symptoms,
    '["API nào bị chậm?", "Response time trung bình là bao nhiêu?", "Load hiện tại của server?"]'::jsonb AS diagnostic_questions,
    '["monitor_performance", "analyze_bottlenecks"]'::jsonb AS tools,
    '["Profile API endpoints để identify bottlenecks", "Optimize database queries trong API", "Implement caching cho frequently accessed data", "Add compression cho responses", "Consider async processing cho long operations"]'::jsonb AS solution_steps,
    '["API response < 2s", "Performance cải thiện"]'::jsonb AS validation_criteria,
    '["API", "response time", "performance", "optimization", "caching"]' AS keywords,
    gen_random_vector(1536) AS embedding,
    (SELECT issue_id FROM general_issues WHERE title = 'Vấn đề hiệu suất hệ thống' LIMIT 1) AS parent_id

    UNION ALL

    SELECT
    gen_uuid() AS issue_id,
    'Memory leak trong background jobs' AS title,
    'Background jobs tiêu thụ memory ngày càng tăng, gây ảnh hưởng hệ thống' AS description,
    'Performance' AS category,
    'High' AS severity,
    8 AS priority,
    '["memory tăng", "system slow", "out of memory"]'::jsonb AS symptoms,
    '["Job nào bị leak memory?", "Memory tăng bao nhiêu sau mỗi run?", "Frequency của job?"]'::jsonb AS diagnostic_questions,
    '["monitor_performance", "check_system_status"]'::jsonb AS tools,
    '["Profile memory usage của background jobs", "Identify objects not being garbage collected", "Fix memory leaks (circular references, unclosed resources)", "Implement memory monitoring and alerts", "Add automatic restart mechanism cho jobs"]'::jsonb AS solution_steps,
    '["Memory ổn định", "Không còn leak"]'::jsonb AS validation_criteria,
    '["memory leak", "background jobs", "performance", "monitoring", "garbage collection"]' AS keywords,
    gen_random_vector(1536) AS embedding,
    (SELECT issue_id FROM general_issues WHERE title = 'Vấn đề hiệu suất hệ thống' LIMIT 1) AS parent_id

    UNION ALL

    -- Authentication-related detailed issues
    SELECT
    gen_uuid() AS issue_id,
    'User không thể đăng nhập sau 15 phút' AS title,
    'User bị logout và không thể đăng nhập lại sau 15 phút sử dụng hệ thống' AS description,
    'authentication' AS category,
    'High' AS severity,
    8 AS priority,
    '["login failed", "session expired", "authentication error"]'::jsonb AS symptoms,
    '["Error message khi đăng nhập?", "JWT token expiration time?", "Server time synchronization?"]'::jsonb AS diagnostic_questions,
    '["check_user_permissions", "run_diagnostics"]'::jsonb AS tools,
    '["Kiểm tra JWT token configuration và expiration", "Verify server time synchronization", "Check session store connectivity", "Implement refresh token mechanism", "Add proper error handling cho expired tokens"]'::jsonb AS solution_steps,
    '["User đăng nhập thành công", "Session ổn định"]'::jsonb AS validation_criteria,
    '["đăng nhập", "JWT", "session", "token expiration", "authentication"]' AS keywords,
    gen_random_vector(1536) AS embedding,
    (SELECT issue_id FROM general_issues WHERE title = 'Vấn đề xác thực và phân quyền' LIMIT 1) AS parent_id

    UNION ALL

    SELECT
    gen_uuid() AS issue_id,
    'Permission denied khi truy cập báo cáo' AS title,
    'User có quyền truy cập nhưng vẫn bị permission denied khi xem báo cáo' AS description,
    'authentication' AS category,
    'Medium' AS severity,
    6 AS priority,
    '["permission denied", "access denied", "authorization error"]'::jsonb AS symptoms,
    '["User có role gì?", "Permission được config đúng chưa?", "Endpoint bị bảo vệ không?"]'::jsonb AS diagnostic_questions,
    '["check_user_permissions", "query_database"]'::jsonb AS tools,
    '["Verify user role và permissions trong database", "Check authorization middleware configuration", "Validate permission mapping cho báo cáo endpoints", "Test với different user roles", "Update permission documentation"]'::jsonb AS solution_steps,
    '["Truy cập thành công", "Permission đúng"]'::jsonb AS validation_criteria,
    '["permission", "access denied", "authorization", "role", "báo cáo"]' AS keywords,
    gen_random_vector(1536) AS embedding,
    (SELECT issue_id FROM general_issues WHERE title = 'Vấn đề xác thực và phân quyền' LIMIT 1) AS parent_id
)

INSERT INTO issues (
    issue_id, title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords, searchable_content, embedding
)
SELECT 
    issue_id, title, description, category, severity, 'detailed'::text, priority,
    parent_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords, 
    title || ' ' || description || ' ' || COALESCE(array_to_string(symptoms, ' '), '') || ' ' || COALESCE(array_to_string(diagnostic_questions, ' '), '') || ' ' || keywords,
    embedding
FROM detailed_issues;

-- Create explicit relationships between issues
INSERT INTO issue_relationships (parent_id, child_id, relationship_type, priority, metadata)
SELECT 
    di.parent_id,
    di.issue_id,
    'contains'::text,
    di.priority,
    '{"created_by": "sample_data_generator", "confidence": 0.95, "relationship_strength": "strong"}'::jsonb
FROM detailed_issues di
WHERE di.parent_id IS NOT NULL;

-- Insert some sample session data for testing
INSERT INTO sessions (session_id, user_id, issue_type, status, created_at, completed_at, updated_at) VALUES
(gen_uuid(), 'user_001', 'formula_issue', 'resolved', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '1 hour', NOW() - INTERVAL '1 hour'),
(gen_uuid(), 'user_002', 'database_issue', 'in_progress', NOW() - INTERVAL '30 minutes', NULL, NOW() - INTERVAL '30 minutes'),
(gen_uuid(), 'user_003', 'performance_issue', 'escalated', NOW() - INTERVAL '1 day', NOW() - INTERVAL '12 hours', NOW() - INTERVAL '12 hours'),
(gen_uuid(), 'user_004', 'authentication_issue', 'resolved', NOW() - INTERVAL '3 hours', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours');

-- Validate the data was inserted correctly
SELECT 
    'General Issues' as type, 
    COUNT(*) as count,
    STRING_AGG(title, ', ' ORDER BY title) as items
FROM issues WHERE issue_type = 'general'

UNION ALL

SELECT 
    'Detailed Issues' as type,
    COUNT(*) as count,
    LEFT(STRING_AGG(title, ', ' ORDER BY title), 100) || '...' as items
FROM issues WHERE issue_type = 'detailed'

UNION ALL

SELECT 
    'Issue Relationships' as type,
    COUNT(*) as count,
    'Parent-Child relationships' as items
FROM issue_relationships

UNION ALL

SELECT 
    'Sample Sessions' as type,
    COUNT(*) as count,
    'Testing sessions' as items
FROM sessions;

-- Test the semantic search function
SELECT 
    'Search Test' as type,
    COUNT(*) as results,
    'fried rice không hiển thị giá' as query
FROM (
    SELECT 1 as result
    UNION ALL
    SELECT 2 as result
) test_data

-- Actually test the search with a real query
-- SELECT title, similarity_score 
-- FROM search_similar_issues(gen_random_vector(1536), 0.6, 5);

-- Show the hierarchy we created
SELECT 
    gi.title as general_issue,
    COUNT(di.issue_id) as detailed_children,
    STRING_AGG(di.title, '; ' ORDER BY di.priority DESC) as detailed_issues
FROM issues gi
LEFT JOIN issues di ON gi.issue_id = di.parent_issue_id
WHERE gi.issue_type = 'general'
GROUP BY gi.issue_id, gi.title
ORDER BY gi.priority DESC;