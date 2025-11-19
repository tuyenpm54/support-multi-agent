"""
Classifier Agent - Issue Classification and Initial Analysis

This agent is responsible for:
1. Classifying user issues using semantic search
2. Generating initial diagnostic questions
3. Providing confidence scoring and multiple candidate ranking
4. Extracting key entities and context from user input
"""

import asyncio
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from src.agents.base import BaseAgent
from src.models.session import SessionState, ClassificationResult
from src.core.hierarchical_semantic_search import get_hierarchical_search_service
from src.core.embeddings import get_embedding_service, EmbeddingService


class ClassifierAgent(BaseAgent):
    """Agent responsible for classifying user issues and initial analysis."""
    
    def __init__(self):
        super().__init__("ClassifierAgent")
        self.logger = logging.getLogger(__name__)
        self.semantic_search_service = None
        self.embedding_service: Optional[EmbeddingService] = None
        
        # Semantic search configuration
        self.min_confidence_threshold = 0.6
        self.max_search_results = 10
        self.prefer_detailed_issues = True  # Prefer detailed issues over general
    
    async def initialize(self):
        """Initialize classifier agent dependencies."""
        try:
            self.semantic_search_service = await get_hierarchical_search_service()
            self.embedding_service = await get_embedding_service()
            self.logger.info("Classifier agent initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize classifier agent: {str(e)}")
            raise
    
    async def execute(self, session_state: SessionState, **kwargs) -> Dict[str, Any]:
        """
        Execute classification on user input.
        
        Args:
            session_state: Current session state
            **kwargs: Additional parameters (user_input, context, etc.)
            
        Returns:
            Classification result with multiple candidates and analysis
        """
        user_input = kwargs.get('user_input', '')
        if not user_input:
            raise ValueError("User input is required for classification")
        
        self.logger.info(f"Classifying user input: {user_input[:100]}...")
        
        try:
            # Step 1: Perform optimized semantic search
            search_results = await self._perform_hierarchical_semantic_search(user_input)
            
            # Step 2: Create classification result from search results
            classification_result = await self._create_classification_result(search_results, user_input)
            
            # Step 3: Generate follow-up questions based on issue type
            diagnostic_questions = await self._generate_follow_up_questions(classification_result, user_input)
            
            result = {
                "success": True,
                "classification": classification_result,
                "search_results": search_results,
                "diagnostic_questions": diagnostic_questions,
                "processing_time": datetime.now().isoformat()
            }
            
            self.logger.info(f"Classification completed: {classification_result.suggested_category} "
                           f"(confidence: {classification_result.confidence:.2f})")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Classification failed: {str(e)}")
            return await self.handle_error(e, session_state)
    
    
    async def _perform_hierarchical_semantic_search(self, user_input: str) -> List[Dict[str, Any]]:
        """Perform optimized hierarchical semantic search."""
        try:
            # Use the new hierarchical semantic search service
            search_results = await self.semantic_search_service.search_issues(
                query_text=user_input,
                max_results=self.max_search_results,
                similarity_threshold=self.min_confidence_threshold
            )
            
            # Prefer detailed issues if configured
            if self.prefer_detailed_issues:
                detailed_issues = [r for r in search_results if r.get('issue_type') == 'detailed']
                general_issues = [r for r in search_results if r.get('issue_type') == 'general']
                
                # Mix: prioritize detailed issues but keep some general issues
                search_results = detailed_issues[:7] + general_issues[:3]
            
            self.logger.info(f"Hierarchical semantic search found {len(search_results)} results")
            return search_results
            
        except Exception as e:
            self.logger.error(f"Hierarchical semantic search failed: {str(e)}")
            return []
    
    async def _create_classification_result(self,
                                         search_results: List[Dict[str, Any]],
                                         user_input: str) -> ClassificationResult:
        """Create classification result from semantic search results."""
        
        if not search_results:
            # No results found - create default classification
            return ClassificationResult(
                classified=False,
                confidence=0.0,
                suggested_category="Unknown",
                suggested_severity="Medium",
                matched_issue_id=None,
                diagnostic_questions=[
                    "Could you provide more details about the issue you're experiencing?",
                    "When did this issue start occurring?",
                    "Is this affecting multiple users or just you?"
                ],
                potential_causes=[],
                recommended_tools=["search_knowledge_base", "query_database"],
                created_at=datetime.now()
            )
        
        # Get best match (highest composite score)
        best_match = search_results[0]
        
        # Determine if classification is confident enough
        is_classified = best_match.get('composite_score', 0) >= self.min_confidence_threshold
        
        # Determine severity based on both search result and urgency indicators
        severity = best_match.get('severity', 'Medium')
        if 'khẩn' in user_input.lower() or 'gấp' in user_input.lower():
            if severity == 'Low':
                severity = 'Medium'
            elif severity == 'Medium':
                severity = 'High'
        
        # Create classification result with hierarchical context
        result = ClassificationResult(
            classified=is_classified,
            confidence=best_match.get('composite_score', best_match.get('similarity_score', 0)),
            suggested_category=best_match.get('category', 'Unknown'),
            suggested_severity=severity,
            matched_issue_id=best_match.get('issue_id'),
            matched_title=best_match.get('title'),
            similarity_score=best_match.get('similarity_score', 0),
            diagnostic_questions=best_match.get('diagnostic_questions', []),
            potential_causes=[best_match.get('title')] if best_match.get('title') else [],
            recommended_tools=best_match.get('tools', []),
            issue_type=best_match.get('issue_type'),  # Set issue type for routing
            created_at=datetime.now()
        )
        
        # Add hierarchical information to the result
        if best_match.get('issue_type') == 'general':
            result.has_diagnostic_question = True  # General issues need detailed analysis
        
        return result
    
    async def _create_classification_result(self,
                                         candidates: List[Dict[str, Any]],
                                         user_input: str,
                                         entities: Dict[str, Any],
                                         patterns: Dict[str, Any]) -> ClassificationResult:
        """Create final classification result from best candidate."""
        
        if not candidates:
            # No candidates found - create default classification
            return ClassificationResult(
                classified=False,
                confidence=0.0,
                suggested_category="Unknown",
                suggested_severity="Medium",
                matched_issue_id=None,
                diagnostic_questions=[
                    "Could you provide more details about the issue you're experiencing?",
                    "When did this issue start occurring?",
                    "Is this affecting multiple users or just you?"
                ],
                potential_causes=[],
                recommended_tools=["search_knowledge_base", "query_database"],
                created_at=datetime.now()
            )
        
        # Get best candidate
        best_candidate = candidates[0]
        
        # Determine if classification is confident enough
        is_classified = best_candidate['confidence'] >= self.low_confidence_threshold
        
        # Adjust severity based on entities
        severity = best_candidate['severity']
        if entities['urgency_level'] == 'high':
            if severity == 'Low':
                severity = 'Medium'
            elif severity == 'Medium':
                severity = 'High'
        
        # Create classification result
        result = ClassificationResult(
            classified=is_classified,
            confidence=best_candidate['confidence'],
            suggested_category=best_candidate['category'],
            suggested_severity=severity,
            matched_issue_id=best_candidate['issue_id'],
            matched_title=best_candidate['title'],
            similarity_score=best_candidate['similarity_score'],
            diagnostic_questions=best_candidate['diagnostic_questions'],
            potential_causes=[best_candidate['title']] if best_candidate['title'] else [],
            recommended_tools=best_candidate['tools'],
            created_at=datetime.now()
        )
        
        return result
    
    async def _generate_follow_up_questions(
        self,
        classification_result: ClassificationResult,
        user_input: str
    ) -> List[str]:
        """Generate follow-up questions based on classification result and issue type."""
        questions = []
        
        # Start with questions from classification result
        if classification_result.diagnostic_questions:
            questions.extend(classification_result.diagnostic_questions[:3])
        
        # Add general clarifying questions
        if len(questions) < 4:
            questions.extend([
                "Bạn có thể mô tả chi tiết hơn về vấn đề không?",
                "Điều gì đã xảy ra ngay trước khi vấn đề này xuất hiện?",
                "Vấn đề này có ảnh hưởng đến nhiều người dùng không?"
            ])
        
        # Return top 5 unique questions
        unique_questions = list(dict.fromkeys(questions))
        return unique_questions[:5]
    
    def _map_pattern_to_category(self, pattern_type: str) -> str:
        """Map issue pattern to category."""
        category_mapping = {
            'no_price_display': 'formula',
            'incorrect_price': 'data_quality',
            'performance_slow': 'Performance',
            'login_issues': 'Authentication',
            'data_not_showing': 'Data',
            'integration_errors': 'Integration'
        }
        return category_mapping.get(pattern_type, 'Unknown')
    
    async def _get_default_questions_for_pattern(self, pattern_type: str) -> List[str]:
        """Get default diagnostic questions for a pattern type."""
        questions_mapping = {
            'no_price_display': [
                "Món nào đang không hiển thị giá?",
                "Đây là kỳ báo cáo nào?",
                "Bạn đã kiểm tra công thức của món này chưa?"
            ],
            'incorrect_price': [
                "Giá bị sai lệch như thế nào?",
                "Món nào bị ảnh hưởng?",
                "Bạn có vừa thay đổi công thức gần đây không?"
            ],
            'performance_slow': [
                "Chức năng nào đang chậm?",
                "Tình trạng này bắt đầu khi nào?",
                "Có nhiều người dùng bị ảnh hưởng không?"
            ]
        }
        return questions_mapping.get(pattern_type, [
            "Bạn có thể cung cấp thêm chi tiết không?",
            "Khi nào vấn đề này bắt đầu?"
        ])
    
    async def _get_default_tools_for_pattern(self, pattern_type: str) -> List[str]:
        """Get default tools for a pattern type."""
        tools_mapping = {
            'no_price_display': ['check_formula', 'query_database', 'search_knowledge_base'],
            'incorrect_price': ['check_data_quality', 'query_database', 'run_diagnostics'],
            'performance_slow': ['run_diagnostics', 'check_system_status', 'monitor_performance'],
            'login_issues': ['check_user_permissions', 'query_database', 'run_diagnostics'],
            'data_not_showing': ['query_database', 'check_data_integrity', 'search_knowledge_base'],
            'integration_errors': ['check_system_status', 'run_diagnostics', 'test_connections']
        }
        return tools_mapping.get(pattern_type, ['search_knowledge_base', 'query_database'])
    
    async def validate_input(self, session_state: SessionState, **kwargs) -> bool:
        """Validate input for classification."""
        user_input = kwargs.get('user_input', '')
        if not user_input or len(user_input.strip()) < 3:
            return False
        return True
    
    async def handle_error(self, error: Exception, session_state: SessionState) -> Dict[str, Any]:
        """Handle classification errors with fallback behavior."""
        self.logger.error(f"Classification error: {str(error)}")
        
        # Return a basic classification result
        fallback_result = ClassificationResult(
            classified=False,
            confidence=0.0,
            suggested_category="Unknown",
            suggested_severity="Medium",
            matched_issue_id=None,
            diagnostic_questions=[
                "I'm having trouble understanding your issue. Could you please rephrase it?",
                "What specific problem are you experiencing?"
            ],
            potential_causes=[],
            recommended_tools=["search_knowledge_base"],
            created_at=datetime.now()
        )
        
        return {
            "success": False,
            "error": str(error),
            "classification": fallback_result,
            "search_results": [],
            "diagnostic_questions": fallback_result.diagnostic_questions,
            "processing_time": datetime.now().isoformat()
        }


# Global classifier agent instance
classifier_agent = ClassifierAgent()


async def get_classifier_agent() -> ClassifierAgent:
    """Get the global classifier agent instance."""
    if not classifier_agent.semantic_search_service:
        await classifier_agent.initialize()
    return classifier_agent