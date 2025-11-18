#!/usr/bin/env python3
"""
Knowledge Base Population Script

This script populates the knowledge base with sample known issues and generates embeddings.
It creates realistic sample data for the Vietnamese F&B cost management system.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
import uuid

from src.db import get_db_connection_pool
from src.core.embeddings import get_embedding_service


# Sample known issues for Vietnamese F&B Cost Management System
SAMPLE_ISSUES = [
    {
        "title": "Công thức không hiển thị giá thành món Bún đậu mắm tôm",
        "description": "Khi xem báo cáo giá thành, món Bún đậu mắm tôm hiển thị giá = 0 hoặc để trống. Đã kiểm tra công thức và thấy nguyên vật liệu đã được nhập đúng. Vấn đề xảy ra trên cả web và mobile app.",
        "category": "formula",
        "severity": "High",
        "symptoms": [
            "giá thành hiển thị = 0",
            "giá thành để trống",
            "không tính được giá vốn",
            "báo cáo sai lệch"
        ],
        "diagnostic_questions": [
            "Bạn đã kiểm tra công thức của món Bún đậu mắm tôm chưa?",
            "Tất cả nguyên vật liệu trong công thức đã có giá nhập chưa?",
            "Vấn đề này xảy ra cho kỳ báo cáo nào?",
            "Các món khác trong cùng nhóm có bị ảnh hưởng không?"
        ],
        "tools": ["check_formula", "query_database", "search_knowledge_base", "run_diagnostics"]
    },
    {
        "title": "Đồng bộ dữ liệu từ kho Hà Nội thất bại",
        "description": "Hệ thống không đồng bộ được dữ liệu từ kho Hà Nội. Hiện thị lỗi 'Connection timeout' khi cố gắng đồng bộ. Đã thử lại nhiều lần nhưng vẫn thất bại. Kho Hà Nội đang dùng phần mềm cũ.",
        "category": "data_sync",
        "severity": "Medium",
        "symptoms": [
            "lỗi connection timeout",
            "không đồng bộ được",
            "dữ liệu cũ",
            "báo cáo thiếu dữ liệu kho Hà Nội"
        ],
        "diagnostic_questions": [
            "Kho Hà Nội đang dùng phiên bản phần mềm nào?",
            "Kết nối mạng đến kho Hà Nội có ổn định không?",
            "Bạn có thể kiểm tra kết nối thủ công không?",
            "Các kho khác có đồng bộ bình thường không?"
        ],
        "tools": ["check_system_status", "test_connections", "query_database", "run_diagnostics"]
    },
    {
        "title": "Báo cáo tổng hợp tải rất chậm",
        "description": "Báo cáo tổng hợp tháng 12/2024 mất hơn 5 phút để tải. Các báo cáo khác tải bình thường. Vấn đề chỉ xảy ra với báo cáo có dữ liệu lớn (>10,000 dòng).",
        "category": "Performance",
        "severity": "Medium",
        "symptoms": [
            "tải báo cáo chậm",
            "timeout",
            "dữ liệu lớn",
            "browser không phản hồi"
        ],
        "diagnostic_questions": [
            "Báo cáo có bao nhiêu dòng dữ liệu?",
            "Tốc độ mạng của bạn có ổn định không?",
            "Vấn đề có xảy ra trên các thiết bị khác không?",
            "Bạn đã thử xóa cache chưa?"
        ],
        "tools": ["monitor_performance", "check_system_status", "query_database", "run_diagnostics"]
    },
    {
        "title": "Không đăng nhập được vào hệ thống",
        "description": "Nhập đúng tài khoản và mật khẩu nhưng hệ thống báo 'Sai tài khoản hoặc mật khẩu'. Đã thử reset mật khẩu nhưng vẫn không được. Tài khoản khác đăng nhập bình thường.",
        "category": "Authentication",
        "severity": "High",
        "symptoms": [
            "đăng nhập thất bại",
            "lỗi xác thực",
            "sai mật khẩu",
            "không truy cập được"
        ],
        "diagnostic_questions": [
            "Tài khoản của bạn có bị khóa không?",
            "Bạn có vừa thay đổi mật khẩu gần đây không?",
            "Bạn có thể đăng nhập vào tài khoản khác không?",
            "Bạn đã thử reset mật khẩu chưa?"
        ],
        "tools": ["check_user_permissions", "query_database", "run_diagnostics", "search_knowledge_base"]
    },
    {
        "title": "Dữ liệu nguyên vật liệu không hiển thị",
        "description": "Khi xem danh mục nguyên vật liệu, một số item không hiển thị dữ liệu giá nhập và tồn kho. Trình bày như trống dù đã kiểm tra trong database thấy có dữ liệu.",
        "category": "Data",
        "severity": "Medium",
        "symptoms": [
            "không hiển thị giá nhập",
            "tồn kho trống",
            "dữ liệu ẩn",
            "UI không load data"
        ],
        "diagnostic_questions": [
            "Những nguyên vật liệu nào bị ảnh hưởng?",
            "Vấn đề có xảy ra trên cả mobile app không?",
            "Bạn đã thử refresh trang chưa?",
            "Có bao nhiêu item bị ảnh hưởng?"
        ],
        "tools": ["query_database", "check_data_integrity", "search_knowledge_base", "run_diagnostics"]
    },
    {
        "title": "Giá thành món phở bò sai lệch nghiêm trọng",
        "description": "Giá thành món phở bò hiển thị cao bất thường (gấp 3 lần bình thường). Đã kiểm tra công thức và thấy giá thịt bò bị nhập sai. Cần sửa giá nhập và tính lại giá thành.",
        "category": "data_quality",
        "severity": "High",
        "symptoms": [
            "giá thành sai lệch",
            "giá cao bất thường",
            "báo cáo không chính xác",
            "lợi nhuận tính sai"
        ],
        "diagnostic_questions": [
            "Giá thành đúng của món phở bò là bao nhiêu?",
            "Bạn có vừa nhập giá nguyên vật liệu mới không?",
            "Giá thịt bò hiện tại là bao nhiêu?",
            "Cần tính lại giá thành cho kỳ nào?"
        ],
        "tools": ["check_data_quality", "query_database", "run_diagnostics", "search_knowledge_base"]
    },
    {
        "title": "Lỗi integration với hệ thống kế toán",
        "description": "Hệ thống không push được dữ liệu sang phần mềm kế toán MISA. Hiện lỗi 'Invalid API key'. Đã kiểm tra và thấy key vẫn còn hạn sử dụng.",
        "category": "Integration",
        "severity": "Critical",
        "symptoms": [
            "lỗi API key",
            "không push được data",
            "đồng bộ thất bại",
            "hệ thống kế toán không nhận data"
        ],
        "diagnostic_questions": [
            "API key có được renew gần đây không?",
            "Bạn có thể test kết nối đến MISA không?",
            "Lỗi có xảy ra với tất cả dữ liệu hay chỉ một số?",
            "Bạn đã liên hệ hỗ trợ MISA chưa?"
        ],
        "tools": ["check_system_status", "test_connections", "run_diagnostics", "search_knowledge_base"]
    },
    {
        "title": "Công thức món gà nướng không tính đúng tỷ lệ",
        "description": "Công thức gà nướng có tỷ lệ nguyên vật liệu không đúng thực tế. Khi nhập 1kg gà, hệ thống tính tỷ lệ 0.8kg thay vì 0.7kg như thực tế. Làm giá thành bị sai.",
        "category": "formula",
        "severity": "Medium",
        "symptoms": [
            "tỷ lệ công thức sai",
            "giá thành không chính xác",
            "tính toán sai",
            "dữ liệu không khớp thực tế"
        ],
        "diagnostic_questions": [
            "Tỷ lệ đúng của công thức là bao nhiêu?",
            "Bạn có vừa thay đổi công thức không?",
            "Vấn đề có xảy ra với các món khác không?",
            "Cần sửa công thức cho kỳ nào?"
        ],
        "tools": ["check_formula", "query_database", "run_diagnostics", "search_knowledge_base"]
    },
    {
        "title": "Hệ thống treo khi xuất báo cáo Excel",
        "description": "Khi xuất báo cáo ra file Excel với dữ liệu lớn (>5000 dòng), hệ thống treo và không phản hồi. Browser bị crash. Phải refresh lại trang.",
        "category": "Performance",
        "severity": "Low",
        "symptoms": [
            "hệ thống treo",
            "browser crash",
            "xuất Excel lỗi",
            "dữ liệu lớn"
        ],
        "diagnostic_questions": [
            "Báo cáo có bao nhiêu dòng dữ liệu?",
            "Browser bạn đang dùng là gì?",
            "Vấn đề có xảy ra với file PDF không?",
            "Bạn đã thử giảm dữ liệu chưa?"
        ],
        "tools": ["monitor_performance", "check_system_status", "run_diagnostics"]
    },
    {
        "title": "Không xem được lịch sử thay đổi công thức",
        "description": "Khi xem lịch sử thay đổi công thức món cơm chiên, hệ thống báo 'Không có dữ liệu'. Món này chắc chắn đã được thay đổi nhiều lần trước đây.",
        "category": "Data",
        "severity": "Low",
        "symptoms": [
            "không có lịch sử",
            "dữ liệu bị mất",
            "không track được thay đổi",
            "audit log trống"
        ],
        "diagnostic_questions": [
            "Món nào bị ảnh hưởng?",
            "Bạn có chắc là đã thay đổi công thức này không?",
            "Lịch sử có bị xóa gần đây không?",
            "Các món khác có lịch sử bình thường không?"
        ],
        "tools": ["query_database", "check_data_integrity", "search_knowledge_base"]
    }
]

# Sample tools for the tool registry
SAMPLE_TOOLS = [
    {
        "name": "check_formula",
        "description": "Check formula configuration and calculations",
        "category": "diagnostic",
        "config": {
            "timeout": 30,
            "requires_db": True,
            "formula_validation": True
        },
        "permissions": ["read_formulas", "read_ingredients"]
    },
    {
        "name": "query_database",
        "description": "Query database for data verification",
        "category": "database",
        "config": {
            "timeout": 60,
            "max_rows": 10000,
            "read_only": True
        },
        "permissions": ["read_database"]
    },
    {
        "name": "search_knowledge_base",
        "description": "Search knowledge base for similar issues",
        "category": "search",
        "config": {
            "max_results": 10,
            "similarity_threshold": 0.7
        },
        "permissions": ["read_knowledge_base"]
    },
    {
        "name": "run_diagnostics",
        "description": "Run comprehensive system diagnostics",
        "category": "system",
        "config": {
            "full_scan": True,
            "timeout": 120
        },
        "permissions": ["read_system", "read_database"]
    },
    {
        "name": "check_system_status",
        "description": "Check overall system health and performance",
        "category": "monitoring",
        "config": {
            "check_services": True,
            "check_database": True,
            "check_external_apis": True
        },
        "permissions": ["read_system", "read_monitoring"]
    },
    {
        "name": "test_connections",
        "description": "Test connections to external systems and APIs",
        "category": "integration",
        "config": {
            "timeout": 30,
            "retry_count": 3
        },
        "permissions": ["test_connections", "read_system"]
    },
    {
        "name": "check_data_quality",
        "description": "Validate data quality and consistency",
        "category": "validation",
        "config": {
            "validate_prices": True,
            "validate_formulas": True,
            "validate_inventory": True
        },
        "permissions": ["read_database", "read_formulas"]
    },
    {
        "name": "monitor_performance",
        "description": "Monitor system performance metrics",
        "category": "performance",
        "config": {
            "collect_metrics": True,
            "analyze_slow_queries": True,
            "timeout": 60
        },
        "permissions": ["read_monitoring", "read_system"]
    },
    {
        "name": "check_user_permissions",
        "description": "Check and validate user permissions and access",
        "category": "security",
        "config": {
            "validate_roles": True,
            "check_active_status": True
        },
        "permissions": ["read_users", "read_permissions"]
    },
    {
        "name": "check_data_integrity",
        "description": "Perform data integrity checks",
        "category": "validation",
        "config": {
            "check_foreign_keys": True,
            "check_constraints": True,
            "validate_references": True
        },
        "permissions": ["read_database", "analyze_data"]
    }
]


class KnowledgeBasePopulator:
    """Populates the knowledge base with sample issues and tools."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.embedding_service = None
        
    async def initialize(self):
        """Initialize the populator."""
        try:
            self.embedding_service = await get_embedding_service()
            self.logger.info("Knowledge base populator initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize populator: {str(e)}")
            raise
    
    async def populate_issues(self) -> int:
        """Populate issues table with sample data."""
        count = 0
        pool = await get_db_connection_pool()
        
        async with pool.acquire() as conn:
            # Check if issues already exist
            existing_count = await conn.fetchval("SELECT COUNT(*) FROM issues")
            if existing_count > 0:
                self.logger.info(f"Found {existing_count} existing issues, skipping population")
                return existing_count
            
            # Insert sample issues
            for issue_data in SAMPLE_ISSUES:
                try:
                    # Generate embedding for the issue
                    embedding_text = f"{issue_data['title']} {issue_data['description']} {' '.join(issue_data['symptoms'])}"
                    embedding = await self.embedding_service.generate_embedding(embedding_text)
                    
                    # Insert issue
                    await conn.execute("""
                        INSERT INTO issues (
                            issue_id, title, description, category, severity,
                            symptoms, diagnostic_questions, tools, embedding
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """, 
                        uuid.uuid4(),
                        issue_data['title'],
                        issue_data['description'],
                        issue_data['category'],
                        issue_data['severity'],
                        json.dumps(issue_data['symptoms']),
                        json.dumps(issue_data['diagnostic_questions']),
                        json.dumps(issue_data['tools']),
                        embedding
                    )
                    
                    count += 1
                    self.logger.info(f"Added issue: {issue_data['title']}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to add issue {issue_data['title']}: {str(e)}")
                    continue
            
            self.logger.info(f"Successfully populated {count} issues")
            return count
    
    async def populate_tools(self) -> int:
        """Populate tool registry with sample tools."""
        count = 0
        pool = await get_db_connection_pool()
        
        async with pool.acquire() as conn:
            # Check if tools already exist
            existing_count = await conn.fetchval("SELECT COUNT(*) FROM tool_registry")
            if existing_count > 0:
                self.logger.info(f"Found {existing_count} existing tools, skipping population")
                return existing_count
            
            # Insert sample tools
            for tool_data in SAMPLE_TOOLS:
                try:
                    await conn.execute("""
                        INSERT INTO tool_registry (
                            tool_id, name, description, category, config, permissions
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                    """, 
                        uuid.uuid4(),
                        tool_data['name'],
                        tool_data['description'],
                        tool_data['category'],
                        json.dumps(tool_data['config']),
                        json.dumps(tool_data['permissions'])
                    )
                    
                    count += 1
                    self.logger.info(f"Added tool: {tool_data['name']}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to add tool {tool_data['name']}: {str(e)}")
                    continue
            
            self.logger.info(f"Successfully populated {count} tools")
            return count
    
    async def create_vector_index(self):
        """Create vector index for efficient similarity search."""
        pool = await get_db_connection_pool()
        
        async with pool.acquire() as conn:
            try:
                # Create IVFFlat index for embeddings
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS issues_embedding_idx 
                    ON issues USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """)
                
                self.logger.info("Created vector index for issues")
                
            except Exception as e:
                self.logger.error(f"Failed to create vector index: {str(e)}")
                raise
    
    async def populate_all(self):
        """Populate all knowledge base data."""
        try:
            await self.initialize()
            
            # Populate issues
            issue_count = await self.populate_issues()
            
            # Populate tools
            tool_count = await self.populate_tools()
            
            # Create vector index
            await self.create_vector_index()
            
            self.logger.info(f"Knowledge base population completed: {issue_count} issues, {tool_count} tools")
            
            return {
                "issues": issue_count,
                "tools": tool_count,
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"Knowledge base population failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


async def main():
    """Main function to run the knowledge base population."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    populator = KnowledgeBasePopulator()
    result = await populator.populate_all()
    
    if result["success"]:
        print(f"✅ Knowledge base populated successfully!")
        print(f"   Issues: {result['issues']}")
        print(f"   Tools: {result['tools']}")
    else:
        print(f"❌ Failed to populate knowledge base: {result['error']}")


if __name__ == "__main__":
    asyncio.run(main())