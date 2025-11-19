#!/usr/bin/env python3
"""
Sample Data Generator for Hierarchical Issue Resolution Database

This script creates realistic Vietnamese F&B industry issues with hierarchical structure
for testing and demonstrating the new resolution architecture.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json
import random

# Database connection
import asyncpg
from src.core.config import get_settings

settings = get_settings()

class SampleDataGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.conn = None
        
        # Sample data for Vietnamese F&B industry
        self.general_issues = [
            {
                "title": "Vấn đề về công thức và giá thành",
                "description": "Tất cả các vấn đề liên quan đến công thức tính giá thành món ăn, hiển thị giá và báo cáo giá",
                "category": "formula",
                "severity": "High",
                "priority": 10,
                "symptoms": ["không có giá", "giá sai lệch", "tính toán lỗi", "công thức sai"],
                "diagnostic_questions": [
                    "Món nào đang không hiển thị giá?",
                    "Đây là kỳ báo cáo nào?",
                    "Bạn đã kiểm tra công thức của món này chưa?",
                    "Lỗi xảy ra khi nào?"
                ],
                "tools": ["check_formula", "query_database", "run_diagnostics"],
                "resolution_strategy": {
                    "approach": "sequential",
                    "user_confirmation_required": True,
                    "stop_on_first_success": False,
                    "description": "Kiểm tra lần lượt các vấn đề công thức cho đến khi người dùng xác nhận đã giải quyết"
                },
                "validation_criteria": ["Giá hiển thị chính xác", "Công thức hoạt động đúng", "Báo cáo hoàn chỉnh"],
                "keywords": ["công thức", "giá thành", "tính giá", "báo cáo", "hiển thị"]
            },
            {
                "title": "Vấn đề kết nối và database",
                "description": "Các vấn đề liên quan đến kết nối database, truy vấn dữ liệu và hiệu suất database",
                "category": "database",
                "severity": "High",
                "priority": 9,
                "symptoms": ["lỗi kết nối", "timeout", "query chậm", "data sai", "mất kết nối"],
                "diagnostic_questions": [
                    "Lỗi kết nối xảy ra với database nào?",
                    "Thời gian timeout là bao nhiêu?",
                    "Có bao nhiêu user bị ảnh hưởng?",
                    "Lỗi xảy ra khi thực hiện thao tác nào?"
                ],
                "tools": ["check_database", "run_diagnostics", "monitor_performance"],
                "resolution_strategy": {
                    "approach": "parallel",
                    "user_confirmation_required": True,
                    "stop_on_first_success": True,
                    "description": "Kiểm tra đồng thời các vấn đề kết nối để xác định nguyên nhân chính"
                },
                "validation_criteria": ["Kết nối ổn định", "Query performance tốt", "Data integrity"],
                "keywords": ["database", "kết nối", "connection", "query", "performance"]
            },
            {
                "title": "Vấn đề hiệu suất hệ thống",
                "description": "Các vấn đề liên quan đến tốc độ và hiệu suất của hệ thống tổng thể",
                "category": "Performance",
                "severity": "Medium",
                "priority": 8,
                "symptoms": ["chậm", "treo", "timeout", "tải chậm", "response time cao"],
                "diagnostic_questions": [
                    "Chức năng nào đang chậm?",
                    "Tình trạng này bắt đầu khi nào?",
                    "Có nhiều người dùng bị ảnh hưởng không?",
                    "Response time hiện tại là bao nhiêu?"
                ],
                "tools": ["monitor_performance", "check_system_status", "analyze_bottlenecks"],
                "resolution_strategy": {
                    "approach": "sequential",
                    "user_confirmation_required": True,
                    "stop_on_first_success": False,
                    "description": "Phân tích và tối ưu tuần tự các thành phần hệ thống"
                },
                "validation_criteria": ["Hệ thống hoạt động mượt mà", "Thời gian phản hồi chấp nhận được"],
                "keywords": ["hiệu suất", "performance", "tốc độ", "chậm", "tối ưu"]
            },
            {
                "title": "Vấn đề xác thực và phân quyền",
                "description": "Các vấn đề liên quan đến đăng nhập, phân quyền và quản lý phiên làm việc",
                "category": "authentication",
                "severity": "High",
                "priority": 7,
                "symptoms": ["đăng nhập lỗi", "phân quyền sai", "session timeout", "truy cập bị từ chối"],
                "diagnostic_questions": [
                    "User nào không thể đăng nhập?",
                    "Lỗi xảy ra ở bước nào?",
                    "User có quyền truy cập không?",
                    "Phiên làm việc còn hiệu lực không?"
                ],
                "tools": ["check_user_permissions", "query_database", "run_diagnostics"],
                "resolution_strategy": {
                    "approach": "sequential",
                    "user_confirmation_required": True,
                    "stop_on_first_success": False,
                    "description": "Kiểm tra xác thực và phân quyền theo thứ tự ưu tiên"
                },
                "validation_criteria": ["Đăng nhập thành công", "Phân quyền đúng", "Phiên ổn định"],
                "keywords": ["xác thực", "đăng nhập", "phân quyền", "authentication", "session"]
            }
        ]
        
        self.detailed_issues = [
            # Formula-related detailed issues
            {
                "title": "Công thức fried rice không hiển thị giá",
                "description": "Món fried rice không hiển thị giá trong báo cáo do công thức tính giá bị lỗi hoặc thiếu thành phần",
                "category": "formula",
                "severity": "Medium",
                "priority": 8,
                "symptoms": ["không có giá", "giá bằng 0", "giá blank"],
                "diagnostic_questions": [
                    "Công thức fried rice có tồn tại không?",
                    "Các thành phần trong công thức đã được cấu hình chưa?",
                    "Đơn giá nguyên liệu đã được nhập chưa?"
                ],
                "tools": ["check_formula", "query_database"],
                "solution_steps": [
                    "Kiểm tra công thức tính giá món fried rice",
                    "Xác định thành phần bị thiếu hoặc lỗi",
                    "Cập nhật lại công thức với định lượng chính xác",
                    "Kiểm tra lại giá hiển thị trong báo cáo"
                ],
                "validation_criteria": ["Giá fried rice > 0", "Giá hiển thị đúng trong báo cáo"],
                "parent_general": "Vấn đề về công thức và giá thành"
            },
            {
                "title": "Giá phở bo bị sai lệch 50%",
                "description": "Giá phở bo hiển thị cao hơn hoặc thấp hơn 50% so với giá thực tế do lỗi công thức",
                "category": "formula", 
                "severity": "High",
                "priority": 9,
                "symptoms": ["giá sai", "giá cao bất thường", "tính toán sai"],
                "diagnostic_questions": [
                    "Giá mong muốn là bao nhiêu?",
                    "Giá hiện tại hiển thị là bao nhiêu?",
                    "Công thức phở bo có thay đổi gần đây không?"
                ],
                "tools": ["check_formula", "query_database", "search_knowledge_base"],
                "solution_steps": [
                    "Kiểm tra công thức tính giá phở bo hiện tại",
                    "So sánh với công thức gốc hoặc mẫu",
                    "Xác định thành phần bị sai tỷ lệ",
                    "Cập nhật lại công thức với tỷ lệ đúng",
                    "Xác nhận giá hiển thị đúng"
                ],
                "validation_criteria": ["Giá phở bo chính xác", "Không còn sai lệch"],
                "parent_general": "Vấn đề về công thức và giá thành"
            },
            {
                "title": "Công thức trà sữa bị lỗi divide by zero",
                "description": "Công thức trà sữa gặp lỗi chia cho không khi tính toán thành phần định lượng",
                "category": "formula",
                "severity": "High",
                "priority": 9,
                "symptoms": ["lỗi chia cho không", "crash", "không tính được giá"],
                "diagnostic_questions": [
                    "Lỗi xảy ra khi nào?",
                    "Có thành phần nào có giá trị 0 không?",
                    "Công thức có được validate không?"
                ],
                "tools": ["check_formula", "run_diagnostics"],
                "solution_steps": [
                    "Kiểm tra công thức trà sữa tìm thành phần có giá trị 0",
                    "Validate logic tính toán trong công thức",
                    "Thêm điều kiện kiểm tra chia cho không",
                    "Test lại công thức với dữ liệu mẫu",
                    "Deploy bản sửa lỗi"
                ],
                "validation_criteria": ["Không còn lỗi divide by zero", "Công thức hoạt động ổn định"],
                "parent_general": "Vấn đề về công thức và giá thành"
            },
            
            # Database-related detailed issues
            {
                "title": "Database connection timeout khi query báo cáo",
                "description": "Connection đến database bị timeout khi thực hiện query báo cáo doanh thu lớn",
                "category": "database",
                "severity": "High",
                "priority": 8,
                "symptoms": ["timeout", "connection lost", "query chậm"],
                "diagnostic_questions": [
                    "Query nào bị timeout?",
                    "Thời gian timeout là bao nhiêu?",
                    "Kích thước dữ liệu query là bao nhiêu?"
                ],
                "tools": ["check_database", "monitor_performance"],
                "solution_steps": [
                    "Kiểm tra connection string và timeout settings",
                    "Optimize query với index phù hợp",
                    "Tăng connection timeout nếu cần thiết",
                    "Implement query pagination cho reports lớn",
                    "Test lại với dữ liệu thực tế"
                ],
                "validation_criteria": ["Query chạy thành công", "Không còn timeout"],
                "parent_general": "Vấn đề kết nối và database"
            },
            {
                "title": "Query báo cáo tháng chạy quá chậm (>30s)",
                "description": "Query báo cáo doanh thu tháng chạy quá chậm, ảnh hưởng đến trải nghiệm người dùng",
                "category": "database",
                "severity": "Medium",
                "priority": 7,
                "symptoms": ["query chậm", "performance issue", "long running query"],
                "diagnostic_questions": [
                    "Query hiện tại mất bao lâu?",
                    "Số lượng records trong khoảng thời gian?",
                    "Đã có index phù hợp chưa?"
                ],
                "tools": ["monitor_performance", "analyze_bottlenecks"],
                "solution_steps": [
                    "Analyze execution plan của query hiện tại",
                    "Thêm missing indexes cho columns trong WHERE clause",
                    "Optimize JOIN operations",
                    "Consider materialized views cho reports thường xuyên",
                    "Implement caching cho query results"
                ],
                "validation_criteria": ["Query chạy < 5 giây", "Performance cải thiện"],
                "parent_general": "Vấn đề kết nối và database"
            },
            {
                "title": "Locking issue khi nhiều user concurrently access",
                "description": "Database locking xảy ra khi nhiều user truy cập đồng thời vào cùng data",
                "category": "database",
                "severity": "Medium",
                "priority": 6,
                "symptoms": ["deadlock", "lock timeout", "concurrency issue"],
                "diagnostic_questions": [
                    "Bao nhiêu user bị ảnh hưởng?",
                    "Thao tác nào gây locking?",
                    "Tần suất xảy ra như thế nào?"
                ],
                "tools": ["check_database", "run_diagnostics"],
                "solution_steps": [
                    "Identify queries causing locking",
                    "Implement proper transaction isolation levels",
                    "Add query timeouts and retry logic",
                    "Consider optimistic locking patterns",
                    "Monitor and alert on locking issues"
                ],
                "validation_criteria": ["Không còn deadlock", "Concurrent access tốt"],
                "parent_general": "Vấn đề kết nối và database"
            },
            
            # Performance-related detailed issues
            {
                "title": "API response time > 5 seconds",
                "description": "Các API endpoints phản hồi quá chậm, ảnh hưởng đến trải nghiệm người dùng",
                "category": "Performance",
                "severity": "Medium",
                "priority": 7,
                "symptoms": ["response time cao", "API chậm", "user experience kém"],
                "diagnostic_questions": [
                    "API nào bị chậm?",
                    "Response time trung bình là bao nhiêu?",
                    "Load hiện tại của server?"
                ],
                "tools": ["monitor_performance", "analyze_bottlenecks"],
                "solution_steps": [
                    "Profile API endpoints để identify bottlenecks",
                    "Optimize database queries trong API",
                    "Implement caching cho frequently accessed data",
                    "Add compression cho responses",
                    "Consider async processing cho long operations"
                ],
                "validation_criteria": ["API response < 2s", "Performance cải thiện"],
                "parent_general": "Vấn đề hiệu suất hệ thống"
            },
            {
                "title": "Memory leak trong background jobs",
                "description": "Background jobs tiêu thụ memory ngày càng tăng, gây ảnh hưởng hệ thống",
                "category": "Performance",
                "severity": "High",
                "priority": 8,
                "symptoms": ["memory tăng", "system slow", "out of memory"],
                "diagnostic_questions": [
                    "Job nào bị leak memory?",
                    "Memory tăng bao nhiêu sau mỗi run?",
                    "Frequency của job?"
                ],
                "tools": ["monitor_performance", "check_system_status"],
                "solution_steps": [
                    "Profile memory usage của background jobs",
                    "Identify objects not being garbage collected",
                    "Fix memory leaks (circular references, unclosed resources)",
                    "Implement memory monitoring and alerts",
                    "Add automatic restart mechanism cho jobs"
                ],
                "validation_criteria": ["Memory ổn định", "Không còn leak"],
                "parent_general": "Vấn đề hiệu suất hệ thống"
            },
            
            # Authentication-related detailed issues
            {
                "title": "User không thể đăng nhập sau 15 phút",
                "description": "User bị logout và không thể đăng nhập lại sau 15 phút sử dụng hệ thống",
                "category": "authentication",
                "severity": "High",
                "priority": 8,
                "symptoms": ["login failed", "session expired", "authentication error"],
                "diagnostic_questions": [
                    "Error message khi đăng nhập?",
                    "JWT token expiration time?",
                    "Server time synchronization?"
                ],
                "tools": ["check_user_permissions", "run_diagnostics"],
                "solution_steps": [
                    "Kiểm tra JWT token configuration và expiration",
                    "Verify server time synchronization",
                    "Check session store connectivity",
                    "Implement refresh token mechanism",
                    "Add proper error handling cho expired tokens"
                ],
                "validation_criteria": ["User đăng nhập thành công", "Session ổn định"],
                "parent_general": "Vấn đề xác thực và phân quyền"
            },
            {
                "title": "Permission denied khi truy cập báo cáo",
                "description": "User có quyền truy cập nhưng vẫn bị permission denied khi xem báo cáo",
                "category": "authentication",
                "severity": "Medium",
                "priority": 6,
                "symptoms": ["permission denied", "access denied", "authorization error"],
                "diagnostic_questions": [
                    "User có role gì?",
                    "Permission được config đúng chưa?",
                    "Endpoint bị bảo vệ không?"
                ],
                "tools": ["check_user_permissions", "query_database"],
                "solution_steps": [
                    "Verify user role và permissions trong database",
                    "Check authorization middleware configuration",
                    "Validate permission mapping cho báo cáo endpoints",
                    "Test với different user roles",
                    "Update permission documentation"
                ],
                "validation_criteria": ["Truy cập thành công", "Permission đúng"],
                "parent_general": "Vấn đề xác thực và phân quyền"
            }
        ]
    
    async def connect(self):
        """Connect to database."""
        try:
            self.conn = await asyncpg.connect(settings.database_url)
            self.logger.info("Connected to database successfully")
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {str(e)}")
            raise
    
    async def disconnect(self):
        """Close database connection."""
        if self.conn:
            await self.conn.close()
            self.logger.info("Database connection closed")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate a mock embedding vector for the given text."""
        # Simple mock embedding based on text hash
        # In production, this would use a real embedding service
        import hashlib
        
        text_bytes = text.encode('utf-8')
        hash_obj = hashlib.sha256(text_bytes)
        hash_hex = hash_obj.hexdigest()
        
        # Convert hash to 1536-dimensional vector (OpenAI default)
        embedding = []
        for i in range(1536):
            # Use different parts of hash for different dimensions
            start_idx = (i * 4) % len(hash_hex)
            end_idx = start_idx + 4
            chunk = hash_hex[start_idx:end_idx]
            
            # Convert hex chunk to float between -1 and 1
            val = int(chunk, 16) / 65535.0 * 2 - 1
            embedding.append(val)
        
        return embedding
    
    async def insert_general_issues(self) -> List[str]:
        """Insert general issues and return their IDs."""
        general_issue_ids = []
        
        for issue in self.general_issues:
            issue_id = str(uuid.uuid4())
            embedding = self.generate_embedding(
                f"{issue['title']} {issue['description']} {' '.join(issue['symptoms'])}"
            )
            
            query = """
                INSERT INTO issues (
                    issue_id, title, description, category, severity, issue_type,
                    priority, symptoms, diagnostic_questions, tools, solution_steps,
                    validation_criteria, resolution_strategy, keywords, searchable_content,
                    embedding
                ) VALUES ($1, $2, $3, $4, $5, 'general', $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15)
            """
            
            await self.conn.execute(
                query,
                issue_id,
                issue['title'],
                issue['description'], 
                issue['category'],
                issue['severity'],
                issue['priority'],
                json.dumps(issue['symptoms']),
                json.dumps(issue['diagnostic_questions']),
                json.dumps(issue['tools']),
                json.dumps([]),  # solution_steps will be populated by detailed issues
                json.dumps(issue['validation_criteria']),
                json.dumps(issue['resolution_strategy']),
                json.dumps(issue['keywords']),
                f"{issue['title']} {issue['description']} {' '.join(issue['symptoms'])} {' '.join(issue['diagnostic_questions'])} {' '.join(issue['keywords'])}",
                embedding
            )
            
            general_issue_ids.append(issue_id)
            self.logger.info(f"Inserted general issue: {issue['title']}")
        
        return general_issue_ids
    
    async def insert_detailed_issues(self, general_issue_ids: List[str]) -> List[str]:
        """Insert detailed issues with parent relationships."""
        detailed_issue_ids = []
        
        # Create mapping of general issue titles to IDs
        general_title_to_id = {}
        for i, issue in enumerate(self.general_issues):
            general_title_to_id[issue['title']] = general_issue_ids[i]
        
        for issue in self.detailed_issues:
            issue_id = str(uuid.uuid4())
            embedding = self.generate_embedding(
                f"{issue['title']} {issue['description']} {' '.join(issue['symptoms'])}"
            )
            
            # Get parent issue ID
            parent_id = general_title_to_id.get(issue['parent_general'])
            if not parent_id:
                self.logger.warning(f"Parent issue not found for: {issue['title']}")
                continue
            
            query = """
                INSERT INTO issues (
                    issue_id, title, description, category, severity, issue_type,
                    priority, parent_issue_id, symptoms, diagnostic_questions, tools,
                    solution_steps, validation_criteria, keywords, searchable_content,
                    embedding
                ) VALUES ($1, $2, $3, $4, $5, 'detailed', $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15)
            """
            
            await self.conn.execute(
                query,
                issue_id,
                issue['title'],
                issue['description'],
                issue['category'],
                issue['severity'],
                issue['priority'],
                parent_id,
                json.dumps(issue['symptoms']),
                json.dumps(issue['diagnostic_questions']),
                json.dumps(issue['tools']),
                json.dumps(issue['solution_steps']),
                json.dumps(issue['validation_criteria']),
                json.dumps(issue['keywords']),
                f"{issue['title']} {issue['description']} {' '.join(issue['symptoms'])} {' '.join(issue['diagnostic_questions'])}",
                embedding
            )
            
            detailed_issue_ids.append(issue_id)
            self.logger.info(f"Inserted detailed issue: {issue['title']} (parent: {issue['parent_general']})")
        
        return detailed_issue_ids
    
    async def create_issue_relationships(self, general_issue_ids: List[str], detailed_issue_ids: List[str]):
        """Create explicit relationships between issues."""
        
        # Create mapping of general issue titles to IDs
        general_title_to_id = {}
        for i, issue in enumerate(self.general_issues):
            general_title_to_id[issue['title']] = general_issue_ids[i]
        
        # Create relationships
        for issue in self.detailed_issues:
            parent_id = general_title_to_id.get(issue['parent_general'])
            if not parent_id:
                continue
            
            # Find the detailed issue ID
            detailed_id = None
            for i, detailed_issue in enumerate(self.detailed_issues):
                if detailed_issue['title'] == issue['title']:
                    detailed_id = detailed_issue_ids[i]
                    break
            
            if detailed_id:
                query = """
                    INSERT INTO issue_relationships (
                        parent_id, child_id, relationship_type, priority, metadata
                    ) VALUES ($1, $2, 'contains', $3, $4)
                """
                
                await self.conn.execute(
                    query,
                    parent_id,
                    detailed_id,
                    issue['priority'],
                    json.dumps({
                        "created_by": "sample_data_generator",
                        "confidence": 0.95,
                        "relationship_strength": "strong"
                    })
                )
    
    async def insert_sample_sessions(self):
        """Insert sample session data for testing."""
        sessions = [
            {
                "session_id": str(uuid.uuid4()),
                "user_id": "user_001",
                "issue_type": "formula_issue",
                "status": "resolved",
                "created_at": datetime.now() - timedelta(hours=2),
                "completed_at": datetime.now() - timedelta(hours=1)
            },
            {
                "session_id": str(uuid.uuid4()),
                "user_id": "user_002", 
                "issue_type": "database_issue",
                "status": "in_progress",
                "created_at": datetime.now() - timedelta(minutes=30),
                "completed_at": None
            },
            {
                "session_id": str(uuid.uuid4()),
                "user_id": "user_003",
                "issue_type": "performance_issue", 
                "status": "escalated",
                "created_at": datetime.now() - timedelta(days=1),
                "completed_at": datetime.now() - timedelta(hours=12)
            }
        ]
        
        for session in sessions:
            query = """
                INSERT INTO sessions (
                    session_id, user_id, issue_type, status, created_at, completed_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
            """
            
            await self.conn.execute(
                query,
                session['session_id'],
                session['user_id'],
                session['issue_type'],
                session['status'],
                session['created_at'],
                session['completed_at']
            )
    
    async def validate_data(self):
        """Validate the inserted data."""
        self.logger.info("Validating inserted data...")
        
        # Check general issues
        general_count = await self.conn.fetchval(
            "SELECT COUNT(*) FROM issues WHERE issue_type = 'general'"
        )
        self.logger.info(f"General issues: {general_count}")
        
        # Check detailed issues
        detailed_count = await self.conn.fetchval(
            "SELECT COUNT(*) FROM issues WHERE issue_type = 'detailed'"
        )
        self.logger.info(f"Detailed issues: {detailed_count}")
        
        # Check relationships
        relationship_count = await self.conn.fetchval(
            "SELECT COUNT(*) FROM issue_relationships"
        )
        self.logger.info(f"Issue relationships: {relationship_count}")
        
        # Check for orphaned detailed issues
        orphaned_count = await self.conn.fetchval("""
            SELECT COUNT(*) FROM issues 
            WHERE issue_type = 'detailed' AND parent_issue_id IS NULL
        """)
        self.logger.info(f"Orphaned detailed issues: {orphaned_count}")
        
        # Test semantic search function
        test_query = "fried rice không hiển thị giá"
        search_results = await self.conn.fetch("""
            SELECT title, similarity_score 
            FROM search_similar_issues($1::vector, 0.6, 5)
        """, self.generate_embedding(test_query))
        
        self.logger.info(f"Semantic search test - Found {len(search_results)} results for: '{test_query}'")
        for result in search_results[:2]:
            self.logger.info(f"  - {result['title']} (similarity: {result['similarity_score']:.3f})")
    
    async def generate_all_data(self):
        """Generate all sample data."""
        try:
            await self.connect()
            
            self.logger.info("Starting sample data generation...")
            
            # Insert general issues
            general_issue_ids = await self.insert_general_issues()
            
            # Insert detailed issues
            detailed_issue_ids = await self.insert_detailed_issues(general_issue_ids)
            
            # Create relationships
            await self.create_issue_relationships(general_issue_ids, detailed_issue_ids)
            
            # Insert sample sessions
            await self.insert_sample_sessions()
            
            # Validate data
            await self.validate_data()
            
            self.logger.info("✅ Sample data generation completed successfully!")
            
        except Exception as e:
            self.logger.error(f"❌ Error generating sample data: {str(e)}")
            raise
        finally:
            await self.disconnect()


async def main():
    """Main function to generate sample data."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    generator = SampleDataGenerator()
    await generator.generate_all_data()


if __name__ == "__main__":
    asyncio.run(main())