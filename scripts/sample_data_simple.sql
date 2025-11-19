-- Simplified Sample Data for Hierarchical Issue Resolution Database
-- Vietnamese F&B Industry Issues

-- Insert General Issues (Parent Issues)
INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    symptoms, diagnostic_questions, tools, validation_criteria,
    resolution_strategy, keywords, priority_override
) VALUES 
-- General Issue 1: Formula and Pricing Issues
('Vấn đề về công thức và giá thành',
 'Tất cả các vấn đề liên quan đến công thức tính giá thành món ăn, hiển thị giá và báo cáo giá',
 'formula',
 'High',
 'general',
 10,
 ARRAY['không có giá', 'giá sai lệch', 'tính toán lỗi', 'công thức sai'],
 ARRAY['Món nào đang không hiển thị giá?', 'Đây là kỳ báo cáo nào?', 'Bạn đã kiểm tra công thức của món này chưa?'],
 ARRAY['check_formula', 'query_database', 'run_diagnostics'],
 ARRAY['Giá hiển thị chính xác', 'Công thức hoạt động đúng', 'Báo cáo hoàn chỉnh'],
 '{"approach": "sequential", "user_confirmation_required": true}',
 ARRAY['công thức', 'giá thành', 'tính giá', 'báo cáo', 'hiển thị'],
 10),

-- General Issue 2: Database Connection Issues  
('Vấn đề kết nối và database',
 'Các vấn đề liên quan đến kết nối database, truy vấn dữ liệu và hiệu suất database',
 'database',
 'High', 
 'general',
 9,
 ARRAY['lỗi kết nối', 'timeout', 'query chậm', 'data sai', 'mất kết nối'],
 ARRAY['Lỗi kết nối xảy ra với database nào?', 'Thời gian timeout là bao nhiêu?', 'Có bao nhiêu user bị ảnh hưởng?'],
 ARRAY['check_database', 'run_diagnostics', 'monitor_performance'],
 ARRAY['Kết nối ổn định', 'Query performance tốt', 'Data integrity'],
 '{"approach": "parallel", "user_confirmation_required": true}',
 ARRAY['database', 'kết nối', 'connection', 'query', 'performance'],
 9),

-- General Issue 3: System Performance Issues
('Vấn đề hiệu suất hệ thống', 
 'Các vấn đề liên quan đến tốc độ và hiệu suất của hệ thống tổng thể',
 'Performance',
 'Medium',
 'general', 
 8,
 ARRAY['chậm', 'treo', 'timeout', 'tải chậm', 'response time cao'],
 ARRAY['Chức năng nào đang chậm?', 'Tình trạng này bắt đầu khi nào?', 'Có nhiều người dùng bị ảnh hưởng không?'],
 ARRAY['monitor_performance', 'check_system_status', 'analyze_bottlenecks'],
 ARRAY['Hệ thống hoạt động mượt mà', 'Thời gian phản hồi chấp nhận được'],
 '{"approach": "sequential", "user_confirmation_required": true}',
 ARRAY['hiệu suất', 'performance', 'tốc độ', 'chậm', 'tối ưu'],
 8),

-- General Issue 4: Authentication Issues
('Vấn đề xác thực và phân quyền',
 'Các vấn đề liên quan đến đăng nhập, phân quyền và quản lý phiên làm việc',
 'authentication',
 'High',
 'general',
 7,
 ARRAY['đăng nhập lỗi', 'phân quyền sai', 'session timeout', 'truy cập bị từ chối'],
 ARRAY['User nào không thể đăng nhập?', 'Lỗi xảy ra ở bước nào?', 'User có quyền truy cập không?'],
 ARRAY['check_user_permissions', 'query_database', 'run_diagnostics'],
 ARRAY['Đăng nhập thành công', 'Phân quyền đúng', 'Phiên ổn định'],
 '{"approach": "sequential", "user_confirmation_required": true}',
 ARRAY['xác thực', 'đăng nhập', 'phân quyền', 'authentication', 'session'],
 7);

-- Get the general issue IDs we just inserted
-- Then insert Detailed Issues (Child Issues) with parent relationships

-- Formula-related detailed issues
INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords
)
SELECT 
    'Công thức fried rice không hiển thị giá',
    'Món fried rice không hiển thị giá trong báo cáo do công thức tính giá bị lỗi hoặc thiếu thành phần',
    'formula',
    'Medium',
    'detailed',
    8,
    gi.issue_id,
    ARRAY['không có giá', 'giá bằng 0', 'giá blank'],
    ARRAY['Công thức fried rice có tồn tại không?', 'Các thành phần trong công thức đã được cấu hình chưa?'],
    ARRAY['check_formula', 'query_database'],
    ARRAY['Kiểm tra công thức tính giá món fried rice', 'Xác định thành phần bị thiếu hoặc lỗi', 'Cập nhật lại công thức với định lượng chính xác', 'Kiểm tra lại giá hiển thị trong báo cáo'],
    ARRAY['Giá fried rice > 0', 'Giá hiển thị đúng trong báo cáo'],
    ARRAY['công thức', 'fried rice', 'giá', 'hiển thị', 'báo cáo']
FROM issues gi WHERE gi.title = 'Vấn đề về công thức và giá thành' AND gi.issue_type = 'general' LIMIT 1;

INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords
)
SELECT 
    'Giá phở bo bị sai lệch 50%',
    'Giá phở bo hiển thị cao hơn hoặc thấp hơn 50% so với giá thực tế do lỗi công thức',
    'formula',
    'High',
    'detailed',
    9,
    gi.issue_id,
    ARRAY['giá sai', 'giá cao bất thường', 'tính toán sai'],
    ARRAY['Giá mong muốn là bao nhiêu?', 'Giá hiện tại hiển thị là bao nhiêu?', 'Công thức phở bo có thay đổi gần đây không?'],
    ARRAY['check_formula', 'query_database', 'search_knowledge_base'],
    ARRAY['Kiểm tra công thức tính giá phở bo hiện tại', 'So sánh với công thức gốc hoặc mẫu', 'Xác định thành phần bị sai tỷ lệ', 'Cập nhật lại công thức với tỷ lệ đúng', 'Xác nhận giá hiển thị đúng'],
    ARRAY['Giá phở bo chính xác', 'Không còn sai lệch'],
    ARRAY['phở bo', 'giá sai lệch', 'công thức', 'tính toán', '50%']
FROM issues gi WHERE gi.title = 'Vấn đề về công thức và giá thành' AND gi.issue_type = 'general' LIMIT 1;

INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords
)
SELECT 
    'Công thức trà sữa bị lỗi divide by zero',
    'Công thức trà sữa gặp lỗi chia cho không khi tính toán thành phần định lượng',
    'formula',
    'High',
    'detailed',
    9,
    gi.issue_id,
    ARRAY['lỗi chia cho không', 'crash', 'không tính được giá'],
    ARRAY['Lỗi xảy ra khi nào?', 'Có thành phần nào có giá trị 0 không?', 'Công thức có được validate không?'],
    ARRAY['check_formula', 'run_diagnostics'],
    ARRAY['Kiểm tra công thức trà sữa tìm thành phần có giá trị 0', 'Validate logic tính toán trong công thức', 'Thêm điều kiện kiểm tra chia cho không', 'Test lại công thức với dữ liệu mẫu', 'Deploy bản sửa lỗi'],
    ARRAY['Không còn lỗi divide by zero', 'Công thức hoạt động ổn định'],
    ARRAY['trà sữa', 'divide by zero', 'lỗi chia cho không', 'công thức', 'validation']
FROM issues gi WHERE gi.title = 'Vấn đề về công thức và giá thành' AND gi.issue_type = 'general' LIMIT 1;

-- Database-related detailed issues
INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords
)
SELECT 
    'Database connection timeout khi query báo cáo',
    'Connection đến database bị timeout khi thực hiện query báo cáo doanh thu lớn',
    'database',
    'High',
    'detailed',
    8,
    gi.issue_id,
    ARRAY['timeout', 'connection lost', 'query chậm'],
    ARRAY['Query nào bị timeout?', 'Thời gian timeout là bao nhiêu?', 'Kích thước dữ liệu query là bao nhiêu?'],
    ARRAY['check_database', 'monitor_performance'],
    ARRAY['Kiểm tra connection string và timeout settings', 'Optimize query với index phù hợp', 'Tăng connection timeout nếu cần thiết', 'Implement query pagination cho reports lớn', 'Test lại với dữ liệu thực tế'],
    ARRAY['Query chạy thành công', 'Không còn timeout'],
    ARRAY['database', 'connection timeout', 'query báo cáo', 'performance', 'index']
FROM issues gi WHERE gi.title = 'Vấn đề kết nối và database' AND gi.issue_type = 'general' LIMIT 1;

INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords
)
SELECT 
    'Query báo cáo tháng chạy quá chậm (>30s)',
    'Query báo cáo doanh thu tháng chạy quá chậm, ảnh hưởng đến trải nghiệm người dùng',
    'database',
    'Medium',
    'detailed',
    7,
    gi.issue_id,
    ARRAY['query chậm', 'performance issue', 'long running query'],
    ARRAY['Query hiện tại mất bao lâu?', 'Số lượng records trong khoảng thời gian?', 'Đã có index phù hợp chưa?'],
    ARRAY['monitor_performance', 'analyze_bottlenecks'],
    ARRAY['Analyze execution plan của query hiện tại', 'Thêm missing indexes cho columns trong WHERE clause', 'Optimize JOIN operations', 'Consider materialized views cho reports thường xuyên', 'Implement caching cho query results'],
    ARRAY['Query chạy < 5 giây', 'Performance cải thiện'],
    ARRAY['query chậm', 'báo cáo tháng', 'performance', 'optimization', 'index']
FROM issues gi WHERE gi.title = 'Vấn đề kết nối và database' AND gi.issue_type = 'general' LIMIT 1;

-- Performance-related detailed issues
INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords
)
SELECT 
    'API response time > 5 seconds',
    'Các API endpoints phản hồi quá chậm, ảnh hưởng đến trải nghiệm người dùng',
    'Performance',
    'Medium',
    'detailed',
    7,
    gi.issue_id,
    ARRAY['response time cao', 'API chậm', 'user experience kém'],
    ARRAY['API nào bị chậm?', 'Response time trung bình là bao nhiêu?', 'Load hiện tại của server?'],
    ARRAY['monitor_performance', 'analyze_bottlenecks'],
    ARRAY['Profile API endpoints để identify bottlenecks', 'Optimize database queries trong API', 'Implement caching cho frequently accessed data', 'Add compression cho responses', 'Consider async processing cho long operations'],
    ARRAY['API response < 2s', 'Performance cải thiện'],
    ARRAY['API', 'response time', 'performance', 'optimization', 'caching']
FROM issues gi WHERE gi.title = 'Vấn đề hiệu suất hệ thống' AND gi.issue_type = 'general' LIMIT 1;

-- Authentication-related detailed issues
INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords
)
SELECT 
    'User không thể đăng nhập sau 15 phút',
    'User bị logout và không thể đăng nhập lại sau 15 phút sử dụng hệ thống',
    'authentication',
    'High',
    'detailed',
    8,
    gi.issue_id,
    ARRAY['login failed', 'session expired', 'authentication error'],
    ARRAY['Error message khi đăng nhập?', 'JWT token expiration time?', 'Server time synchronization?'],
    ARRAY['check_user_permissions', 'run_diagnostics'],
    ARRAY['Kiểm tra JWT token configuration và expiration', 'Verify server time synchronization', 'Check session store connectivity', 'Implement refresh token mechanism', 'Add proper error handling cho expired tokens'],
    ARRAY['User đăng nhập thành công', 'Session ổn định'],
    ARRAY['đăng nhập', 'JWT', 'session', 'token expiration', 'authentication']
FROM issues gi WHERE gi.title = 'Vấn đề xác thực và phân quyền' AND gi.issue_type = 'general' LIMIT 1;

-- Create explicit relationships between issues
INSERT INTO issue_relationships (parent_id, child_id, relationship_type, priority, metadata)
SELECT 
    gi.issue_id as parent_id,
    di.issue_id as child_id,
    'contains' as relationship_type,
    di.priority,
    '{"created_by": "sample_data_generator", "confidence": 0.95, "relationship_strength": "strong"}'::jsonb
FROM issues gi
JOIN issues di ON gi.title = 'Vấn đề về công thức và giá thành' 
    AND gi.issue_type = 'general'
    AND di.issue_type = 'detailed'
    AND di.category = 'formula'
WHERE gi.title = 'Vấn đề về công thức và giá thành' AND gi.issue_type = 'general'
LIMIT 1;

INSERT INTO issue_relationships (parent_id, child_id, relationship_type, priority, metadata)
SELECT 
    gi.issue_id as parent_id,
    di.issue_id as child_id,
    'contains' as relationship_type,
    di.priority,
    '{"created_by": "sample_data_generator", "confidence": 0.95, "relationship_strength": "strong"}'::jsonb
FROM issues gi
JOIN issues di ON gi.title = 'Vấn đề kết nối và database'
    AND gi.issue_type = 'general'
    AND di.issue_type = 'detailed'
    AND di.category = 'database'
WHERE gi.title = 'Vấn đề kết nối và database' AND gi.issue_type = 'general'
LIMIT 1;

-- Show summary of inserted data
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
FROM issue_relationships;

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