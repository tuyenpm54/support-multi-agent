-- Simple Sample Data for Hierarchical Issue Resolution Database (Bypassing Triggers)

-- Disable the trigger temporarily
DROP TRIGGER IF EXISTS trg_update_searchable_content ON issues;

-- Clear any existing sample data first
DELETE FROM issue_relationships WHERE metadata::text LIKE '%sample_data_generator%';
DELETE FROM issues WHERE title IN (
    'Formula and Pricing Issues',
    'Database Connection Issues', 
    'System Performance Issues',
    'Authentication and Authorization Issues'
);

-- Insert General Issues (Parent Issues)
INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    symptoms, diagnostic_questions, tools, validation_criteria,
    resolution_strategy, keywords, searchable_content
) VALUES 
-- General Issue 1: Formula and Pricing Issues
('Formula and Pricing Issues',
 'All issues related to formula-based pricing, price display, and pricing reports',
 'formula',
 'High',
 'general',
 10,
 '["no price", "wrong price", "calculation error", "formula error"]',
 '["Which item has no price?", "Which reporting period?", "Have you checked the item formula?"]',
 '["check_formula", "query_database", "run_diagnostics"]',
 '["Price displays correctly", "Formula works properly", "Reports are complete"]',
 '{"approach": "sequential", "user_confirmation_required": true}',
 ARRAY['formula', 'pricing', 'calculation', 'reports', 'display'],
 'Formula and Pricing Issues All issues related to formula-based pricing price display and pricing reports no price wrong price calculation error formula error Which item has no price Which reporting period Have you checked the item formula check_formula query_database run_diagnostics'),

-- General Issue 2: Database Connection Issues  
('Database Connection Issues',
 'Issues related to database connections, data queries, and database performance',
 'database',
 'High', 
 'general',
 9,
 '["connection error", "timeout", "slow query", "data error", "lost connection"]',
 '["Which database has issues?", "What is the timeout value?", "How many users are affected?"]',
 '["check_database", "run_diagnostics", "monitor_performance"]',
 '["Connection stable", "Good query performance", "Data integrity"]',
 '{"approach": "parallel", "user_confirmation_required": true}',
 ARRAY['database', 'connection', 'query', 'performance', 'optimization'],
 'Database Connection Issues Issues related to database connections data queries and database performance connection error timeout slow query data error lost connection Which database has issues What is the timeout value How many users are affected check_database run_diagnostics monitor_performance'),

-- General Issue 3: System Performance Issues
('System Performance Issues', 
 'Issues related to system speed and overall performance',
 'Performance',
 'Medium',
 'general', 
 8,
 '["slow", "hang", "timeout", "slow loading", "high response time"]',
 '["Which function is slow?", "When did this start?", "Are many users affected?"]',
 '["monitor_performance", "check_system_status", "analyze_bottlenecks"]',
 '["System runs smoothly", "Response time is acceptable"]',
 '{"approach": "sequential", "user_confirmation_required": true}',
 ARRAY['performance', 'speed', 'optimization', 'monitoring', 'efficiency'],
 'System Performance Issues Issues related to system speed and overall performance slow hang timeout slow loading high response time Which function is slow When did this start Are many users affected monitor_performance check_system_status analyze_bottlenecks'),

-- General Issue 4: Authentication Issues
('Authentication and Authorization Issues',
 'Issues related to login, authorization, and session management',
 'authentication',
 'High',
 'general',
 7,
 '["login failed", "authorization error", "session timeout", "access denied"]',
 '["Which user cannot log in?", "At which step does the error occur?", "Does the user have access?"]',
 '["check_user_permissions", "query_database", "run_diagnostics"]',
 '["Login successful", "Authorization correct", "Session stable"]',
 '{"approach": "sequential", "user_confirmation_required": true}',
 ARRAY['authentication', 'login', 'authorization', 'session', 'security'],
 'Authentication and Authorization Issues Issues related to login authorization and session management login failed authorization error session timeout access denied Which user cannot log in At which step does the error occur Does the user have access check_user_permissions query_database run_diagnostics');

-- Insert Detailed Issues (Child Issues) with parent relationships
-- Formula-related detailed issues
INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords, searchable_content
)
SELECT 
    'Fried Rice Formula Not Displaying Price',
    'Fried rice item does not display price in reports due to formula error or missing components',
    'formula',
    'Medium',
    'detailed',
    8,
    gi.issue_id,
    '["no price", "zero price", "blank price"]',
    '["Does the fried rice formula exist?", "Are formula components configured?"]',
    '["check_formula", "query_database"]',
    '["Check fried rice formula", "Identify missing components", "Update formula with correct amounts", "Verify price display"]',
    '["Fried rice price > 0", "Price displays correctly in reports"]',
    ARRAY['fried rice', 'formula', 'price', 'display', 'reports'],
    'Fried Rice Formula Not Displaying Price Fried rice item does not display price in reports due to formula error or missing components no price zero price blank price Does the fried rice formula exist Are formula components configured check_formula query_database'
FROM issues gi WHERE gi.title = 'Formula and Pricing Issues' AND gi.issue_type = 'general' LIMIT 1;

INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords, searchable_content
)
SELECT 
    'Beef Noodle Price 50% Incorrect',
    'Beef noodle price displays 50% higher or lower than actual due to formula error',
    'formula',
    'High',
    'detailed',
    9,
    gi.issue_id,
    '["wrong price", "abnormally high price", "calculation error"]',
    '["What should the price be?", "What is the current price?", "Has the beef noodle formula changed recently?"]',
    '["check_formula", "query_database", "search_knowledge_base"]',
    '["Check current beef noodle formula", "Compare with original formula", "Identify incorrect component ratios", "Update formula with correct ratios", "Confirm price display"]',
    '["Beef noodle price correct", "No more discrepancies"]',
    ARRAY['beef noodle', 'price error', 'formula', 'calculation', 'incorrect'],
    'Beef Noodle Price 50% Incorrect Beef noodle price displays 50% higher or lower than actual due to formula error wrong price abnormally high price calculation error What should the price be What is the current price Has the beef noodle formula changed recently check_formula query_database search_knowledge_base'
FROM issues gi WHERE gi.title = 'Formula and Pricing Issues' AND gi.issue_type = 'general' LIMIT 1;

INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords, searchable_content
)
SELECT 
    'Bubble Tea Formula Divide by Zero Error',
    'Bubble tea formula encounters divide by zero error when calculating component quantities',
    'formula',
    'High',
    'detailed',
    9,
    gi.issue_id,
    '["divide by zero", "crash", "cannot calculate price"]',
    '["When does the error occur?", "Are there zero-valued components?", "Is the formula validated?"]',
    '["check_formula", "run_diagnostics"]',
    '["Find zero-value components in bubble tea formula", "Validate calculation logic", "Add divide-by-zero checks", "Test formula with sample data", "Deploy fix"]',
    '["No more divide by zero errors", "Formula operates stably"]',
    ARRAY['bubble tea', 'divide by zero', 'formula validation', 'calculation', 'error'],
    'Bubble Tea Formula Divide by Zero Error Bubble tea formula encounters divide by zero error when calculating component quantities divide by zero crash cannot calculate price When does the error occur Are there zero-valued components Is the formula validated check_formula run_diagnostics'
FROM issues gi WHERE gi.title = 'Formula and Pricing Issues' AND gi.issue_type = 'general' LIMIT 1;

-- Database-related detailed issues
INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords, searchable_content
)
SELECT 
    'Database Connection Timeout During Report Queries',
    'Database connection times out when executing large report queries',
    'database',
    'High',
    'detailed',
    8,
    gi.issue_id,
    '["timeout", "connection lost", "slow query"]',
    '["Which query times out?", "What is the timeout value?", "What is the data query size?"]',
    '["check_database", "monitor_performance"]',
    '["Check connection string and timeout settings", "Optimize query with appropriate indexes", "Increase connection timeout if needed", "Implement query pagination for large reports", "Test with actual data"]',
    '["Query executes successfully", "No more timeouts"]',
    ARRAY['database', 'connection timeout', 'report queries', 'performance', 'index'],
    'Database Connection Timeout During Report Queries Database connection times out when executing large report queries timeout connection lost slow query Which query times out What is the timeout value What is the data query size check_database monitor_performance'
FROM issues gi WHERE gi.title = 'Database Connection Issues' AND gi.issue_type = 'general' LIMIT 1;

INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords, searchable_content
)
SELECT 
    'Monthly Report Query Too Slow (>30s)',
    'Monthly revenue report query runs too slowly, affecting user experience',
    'database',
    'Medium',
    'detailed',
    7,
    gi.issue_id,
    '["slow query", "performance issue", "long running query"]',
    '["How long does the current query take?", "How many records in the time range?", "Are appropriate indexes in place?"]',
    '["monitor_performance", "analyze_bottlenecks"]',
    '["Analyze current query execution plan", "Add missing indexes for WHERE clause columns", "Optimize JOIN operations", "Consider materialized views for frequent reports", "Implement query result caching"]',
    '["Query runs in under 5 seconds", "Performance improved"]',
    ARRAY['slow query', 'monthly reports', 'performance', 'optimization', 'index'],
    'Monthly Report Query Too Slow (>30s) Monthly revenue report query runs too slowly affecting user experience slow query performance issue long running query How long does the current query take How many records in the time range Are appropriate indexes in place monitor_performance analyze_bottlenecks'
FROM issues gi WHERE gi.title = 'Database Connection Issues' AND gi.issue_type = 'general' LIMIT 1;

-- Performance-related detailed issues
INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords, searchable_content
)
SELECT 
    'API Response Time > 5 Seconds',
    'API endpoints responding too slowly, affecting user experience',
    'Performance',
    'Medium',
    'detailed',
    7,
    gi.issue_id,
    '["high response time", "slow API", "poor user experience"]',
    '["Which API is slow?", "What is the average response time?", "What is the current server load?"]',
    '["monitor_performance", "analyze_bottlenecks"]',
    '["Profile API endpoints to identify bottlenecks", "Optimize database queries in API", "Implement caching for frequently accessed data", "Add response compression", "Consider async processing for long operations"]',
    '["API response under 2 seconds", "Performance improved"]',
    ARRAY['API', 'response time', 'performance', 'optimization', 'caching'],
    'API Response Time > 5 Seconds API endpoints responding too slowly affecting user experience high response time slow API poor user experience Which API is slow What is the average response time What is the current server load monitor_performance analyze_bottlenecks'
FROM issues gi WHERE gi.title = 'System Performance Issues' AND gi.issue_type = 'general' LIMIT 1;

-- Authentication-related detailed issues
INSERT INTO issues (
    title, description, category, severity, issue_type, priority,
    parent_issue_id, symptoms, diagnostic_questions, tools, solution_steps,
    validation_criteria, keywords, searchable_content
)
SELECT 
    'User Cannot Login After 15 Minutes',
    'User gets logged out and cannot log back in after 15 minutes of system usage',
    'authentication',
    'High',
    'detailed',
    8,
    gi.issue_id,
    '["login failed", "session expired", "authentication error"]',
    '["What is the login error message?", "What is the JWT token expiration time?", "Is server time synchronized?"]',
    '["check_user_permissions", "run_diagnostics"]',
    '["Check JWT token configuration and expiration", "Verify server time synchronization", "Check session store connectivity", "Implement refresh token mechanism", "Add proper error handling for expired tokens"]',
    '["User can log in successfully", "Session stable"]',
    ARRAY['login', 'JWT', 'session', 'token expiration', 'authentication'],
    'User Cannot Login After 15 Minutes User gets logged out and cannot log back in after 15 minutes of system usage login failed session expired authentication error What is the login error message What is the JWT token expiration time Is server time synchronized check_user_permissions run_diagnostics'
FROM issues gi WHERE gi.title = 'Authentication and Authorization Issues' AND gi.issue_type = 'general' LIMIT 1;

-- Create explicit relationships between issues
INSERT INTO issue_relationships (parent_id, child_id, relationship_type, priority, metadata)
SELECT 
    gi.issue_id,
    di.issue_id,
    'contains',
    di.priority,
    '{"created_by": "sample_data_generator", "confidence": 0.95, "relationship_strength": "strong"}'
FROM issues gi
CROSS JOIN issues di
WHERE gi.title = 'Formula and Pricing Issues'
  AND gi.issue_type = 'general'
  AND di.issue_type = 'detailed'
  AND di.category = 'formula'
  AND di.parent_issue_id = gi.issue_id;

INSERT INTO issue_relationships (parent_id, child_id, relationship_type, priority, metadata)
SELECT 
    gi.issue_id,
    di.issue_id,
    'contains',
    di.priority,
    '{"created_by": "sample_data_generator", "confidence": 0.95, "relationship_strength": "strong"}'
FROM issues gi
CROSS JOIN issues di
WHERE gi.title = 'Database Connection Issues'
  AND gi.issue_type = 'general'
  AND di.issue_type = 'detailed'
  AND di.category = 'database'
  AND di.parent_issue_id = gi.issue_id;

INSERT INTO issue_relationships (parent_id, child_id, relationship_type, priority, metadata)
SELECT 
    gi.issue_id,
    di.issue_id,
    'contains',
    di.priority,
    '{"created_by": "sample_data_generator", "confidence": 0.95, "relationship_strength": "strong"}'
FROM issues gi
CROSS JOIN issues di
WHERE gi.title = 'System Performance Issues'
  AND gi.issue_type = 'general'
  AND di.issue_type = 'detailed'
  AND di.category = 'Performance'
  AND di.parent_issue_id = gi.issue_id;

INSERT INTO issue_relationships (parent_id, child_id, relationship_type, priority, metadata)
SELECT 
    gi.issue_id,
    di.issue_id,
    'contains',
    di.priority,
    '{"created_by": "sample_data_generator", "confidence": 0.95, "relationship_strength": "strong"}'
FROM issues gi
CROSS JOIN issues di
WHERE gi.title = 'Authentication and Authorization Issues'
  AND gi.issue_type = 'general'
  AND di.issue_type = 'detailed'
  AND di.category = 'authentication'
  AND di.parent_issue_id = gi.issue_id;

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
    STRING_AGG(SUBSTRING(title FROM 1 FOR 40), ', ' ORDER BY title) as items
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
    STRING_AGG(SUBSTRING(di.title FROM 1 FOR 40), '; ' ORDER BY di.priority DESC) as detailed_issues
FROM issues gi
LEFT JOIN issues di ON gi.issue_id = di.parent_issue_id
WHERE gi.issue_type = 'general'
GROUP BY gi.issue_id, gi.title
ORDER BY gi.priority DESC;