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
from src.core.vector_search import get_vector_search_service, VectorSearchService
from src.core.embeddings import get_embedding_service, EmbeddingService


class ClassifierAgent(BaseAgent):
    """Agent responsible for classifying user issues and initial analysis."""
    
    def __init__(self):
        super().__init__("ClassifierAgent")
        self.logger = logging.getLogger(__name__)
        self.vector_search_service: Optional[VectorSearchService] = None
        self.embedding_service: Optional[EmbeddingService] = None
        
        # Classification thresholds
        self.high_confidence_threshold = 0.85
        self.medium_confidence_threshold = 0.70
        self.low_confidence_threshold = 0.55
        
        # Entity extraction patterns
        self.entity_patterns = {
            'dish_name': r'món\s+([^\s,]+(?:\s+[^\s,]+)*)',
            'warehouse': r'kho\s+([^\s,]+)',
            'date_period': r'(tháng\s+\d{1,2}[\/]\d{4}|ky\s+\d{1,2}[\/]\d{4}|\d{1,2}\/\d{4})',
            'error_message': r'(lỗi|error|failed|failed to|cannot|không thể).*',
            'system_component': r'(login|đăng nhập|đăng xuất|báo cáo|report|dashboard)',
            'urgency_indicators': r'(khẩn|gấp|urgent|emergency|nghiêm trọng)',
            'affect_multiple_users': r'(mọi người|tất cả|all users|người khác)'
        }
        
        # Common issue patterns
        self.issue_patterns = {
            'no_price_display': [
                'không có giá', 'không hiển thị giá', 'giá = 0', 'blank', 'trống',
                'not showing price', 'no price', 'price is zero', 'empty'
            ],
            'incorrect_price': [
                'giá sai', 'giá lệch', 'giá cao bất thường', 'giá thấp bất thường',
                'wrong price', 'incorrect price', 'price is wrong'
            ],
            'performance_slow': [
                'chậm', 'mất thời gian', 'treo', 'đơ', 'slow', 'hang', 'freeze',
                'tải chậm', 'load chậm'
            ],
            'login_issues': [
                'không đăng nhập được', 'đăng nhập thất bại', 'lỗi đăng nhập',
                'cannot login', 'login failed', 'authentication error'
            ],
            'data_not_showing': [
                'không có dữ liệu', 'dữ liệu không hiển thị', 'trống',
                'no data', 'data not showing', 'empty data'
            ],
            'integration_errors': [
                'đồng bộ thất bại', 'không đồng bộ được', 'lỗi kết nối',
                'sync failed', 'connection error', 'integration failed'
            ]
        }
    
    async def initialize(self):
        """Initialize classifier agent dependencies."""
        try:
            self.vector_search_service = await get_vector_search_service()
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
            # Step 1: Extract entities and context
            entities = await self._extract_entities(user_input)
            
            # Step 2: Identify issue patterns
            detected_patterns = await self._detect_issue_patterns(user_input)
            
            # Step 3: Perform semantic search for similar issues
            search_results = await self._perform_semantic_search(
                user_input, entities, detected_patterns
            )
            
            # Step 4: Generate classification candidates
            candidates = await self._generate_classification_candidates(
                search_results, entities, detected_patterns
            )
            
            # Step 5: Select best candidate and create classification result
            classification_result = await self._create_classification_result(
                candidates, user_input, entities, detected_patterns
            )
            
            # Step 6: Generate context-aware diagnostic questions
            diagnostic_questions = await self._generate_diagnostic_questions(
                classification_result, entities, detected_patterns
            )
            
            result = {
                "success": True,
                "classification": classification_result,
                "entities": entities,
                "detected_patterns": detected_patterns,
                "all_candidates": candidates,
                "diagnostic_questions": diagnostic_questions,
                "processing_time": datetime.now().isoformat()
            }
            
            self.logger.info(f"Classification completed: {classification_result.suggested_category} "
                           f"(confidence: {classification_result.confidence:.2f})")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Classification failed: {str(e)}")
            return await self.handle_error(e, session_state)
    
    async def _extract_entities(self, user_input: str) -> Dict[str, Any]:
        """Extract entities from user input using patterns and context."""
        entities = {
            'dish_name': None,
            'warehouse': None,
            'date_period': None,
            'error_detected': False,
            'urgency_level': 'normal',
            'affects_multiple_users': False,
            'system_components': [],
            'keywords': []
        }
        
        # Extract entities using regex patterns
        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, user_input, re.IGNORECASE)
            if matches:
                if entity_type == 'system_component':
                    entities['system_components'] = matches
                elif entity_type == 'urgency_indicators':
                    entities['urgency_level'] = 'high'
                elif entity_type == 'affect_multiple_users':
                    entities['affects_multiple_users'] = True
                elif entity_type == 'error_message':
                    entities['error_detected'] = True
                else:
                    entities[entity_type] = matches[0] if matches else None
        
        # Extract keywords
        words = re.findall(r'\b\w+\b', user_input.lower())
        entities['keywords'] = list(set(words))
        
        return entities
    
    async def _detect_issue_patterns(self, user_input: str) -> Dict[str, Any]:
        """Detect common issue patterns in user input."""
        detected_patterns = {
            'primary_issue_type': None,
            'confidence_scores': {},
            'matched_patterns': []
        }
        
        user_input_lower = user_input.lower()
        
        # Check each pattern type
        for pattern_type, keywords in self.issue_patterns.items():
            matches = [kw for kw in keywords if kw in user_input_lower]
            if matches:
                confidence = len(matches) / len(keywords)
                detected_patterns['confidence_scores'][pattern_type] = confidence
                detected_patterns['matched_patterns'].extend(matches)
        
        # Find primary issue type (highest confidence)
        if detected_patterns['confidence_scores']:
            primary_type = max(detected_patterns['confidence_scores'].items(), 
                             key=lambda x: x[1])
            detected_patterns['primary_issue_type'] = primary_type[0]
        
        return detected_patterns
    
    async def _perform_semantic_search(self, 
                                     user_input: str,
                                     entities: Dict[str, Any],
                                     patterns: Dict[str, Any]) -> List[Any]:
        """Perform semantic search for similar issues."""
        try:
            # Build enhanced search query
            search_query = user_input
            
            # Add entities to search query
            if entities['dish_name']:
                search_query += f" món {entities['dish_name']}"
            if entities['warehouse']:
                search_query += f" kho {entities['warehouse']}"
            
            # Add primary pattern if detected
            if patterns['primary_issue_type']:
                pattern_keywords = self.issue_patterns.get(patterns['primary_issue_type'], [])
                search_query += " " + " ".join(pattern_keywords[:3])  # Add top 3 keywords
            
            # Perform search with category filtering if we have a strong pattern match
            category_filter = None
            if patterns['confidence_scores']:
                top_confidence = max(patterns['confidence_scores'].values())
                if top_confidence > 0.7:
                    # Map pattern types to categories
                    category_mapping = {
                        'no_price_display': ['formula', 'data_sync'],
                        'incorrect_price': ['formula', 'data_quality'],
                        'performance_slow': ['Performance'],
                        'login_issues': ['Authentication'],
                        'data_not_showing': ['Data'],
                        'integration_errors': ['Integration']
                    }
                    primary_type = patterns['primary_issue_type']
                    category_filter = category_mapping.get(primary_type)
            
            # Execute search
            results = await self.vector_search_service.search_similar_issues(
                query_text=search_query,
                similarity_threshold=0.3,
                max_results=10,
                category_filter=category_filter
            )
            
            self.logger.info(f"Semantic search found {len(results)} similar issues")
            return results
            
        except Exception as e:
            self.logger.error(f"Semantic search failed: {str(e)}")
            return []
    
    async def _generate_classification_candidates(self,
                                                search_results: List[Any],
                                                entities: Dict[str, Any],
                                                patterns: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate ranked classification candidates from search results."""
        candidates = []
        
        # Process semantic search results
        for i, result in enumerate(search_results):
            # Calculate composite confidence score
            base_confidence = result.confidence_score
            
            # Boost confidence based on pattern matching
            pattern_boost = 0.0
            if patterns['primary_issue_type']:
                pattern_confidence = patterns['confidence_scores'].get(patterns['primary_issue_type'], 0)
                pattern_boost = pattern_confidence * 0.2
            
            # Boost confidence based on entity matching
            entity_boost = 0.0
            if entities['dish_name'] and entities['dish_name'].lower() in result.title.lower():
                entity_boost += 0.1
            if entities['warehouse'] and 'kho' in result.title.lower():
                entity_boost += 0.1
            
            # Calculate final confidence
            final_confidence = base_confidence + pattern_boost + entity_boost
            final_confidence = min(1.0, final_confidence)  # Cap at 1.0
            
            candidate = {
                'rank': i + 1,
                'issue_id': result.issue_id,
                'title': result.title,
                'category': result.category,
                'severity': result.severity,
                'confidence': final_confidence,
                'similarity_score': result.similarity_score,
                'diagnostic_questions': result.diagnostic_questions or [],
                'tools': result.tools or [],
                'match_reasons': []
            }
            
            # Add match reasons
            if pattern_boost > 0:
                candidate['match_reasons'].append(f"Pattern match: {patterns['primary_issue_type']}")
            if entity_boost > 0:
                candidate['match_reasons'].append("Entity match detected")
            if final_confidence >= self.high_confidence_threshold:
                candidate['match_reasons'].append("High confidence match")
            
            candidates.append(candidate)
        
        # If no semantic results, create pattern-based candidates
        if not candidates and patterns['primary_issue_type']:
            candidate = {
                'rank': 1,
                'issue_id': None,
                'title': f"Detected {patterns['primary_issue_type'].replace('_', ' ')}",
                'category': self._map_pattern_to_category(patterns['primary_issue_type']),
                'severity': 'Medium',
                'confidence': patterns['confidence_scores'].get(patterns['primary_issue_type'], 0.5),
                'similarity_score': 0.0,
                'diagnostic_questions': await self._get_default_questions_for_pattern(patterns['primary_issue_type']),
                'tools': await self._get_default_tools_for_pattern(patterns['primary_issue_type']),
                'match_reasons': [f"Pattern detection: {patterns['primary_issue_type']}"]
            }
            candidates.append(candidate)
        
        # Sort candidates by confidence
        candidates.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Update ranks after sorting
        for i, candidate in enumerate(candidates):
            candidate['rank'] = i + 1
        
        return candidates[:5]  # Return top 5 candidates
    
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
    
    async def _generate_diagnostic_questions(self,
                                           classification_result: ClassificationResult,
                                           entities: Dict[str, Any],
                                           patterns: Dict[str, Any]) -> List[str]:
        """Generate context-aware diagnostic questions."""
        questions = []
        
        # Start with questions from classification result
        if classification_result.diagnostic_questions:
            questions.extend(classification_result.diagnostic_questions[:2])  # Take first 2
        
        # Add entity-specific questions
        if not entities['dish_name'] and 'formula' in classification_result.suggested_category:
            questions.append("Bạn đang gặp vấn đề với món ăn nào?")
        
        if not entities['warehouse']:
            questions.append("Vấn đề này xảy ra ở kho nào?")
        
        if not entities['date_period']:
            questions.append("Lỗi này xảy ra trong kỳ báo cáo nào?")
        
        # Add pattern-specific questions
        if patterns['primary_issue_type'] == 'no_price_display':
            questions.append("Bạn có thấy giá thành bằng 0 hay hoàn toàn không có giá không?")
        elif patterns['primary_issue_type'] == 'incorrect_price':
            questions.append("Giá bị sai lệch nhiều so với mong đợi không?")
        elif patterns['primary_issue_type'] == 'performance_slow':
            questions.append("Tình trạng chậm xảy ra khi nào và trong điều kiện nào?")
        
        # Add general clarifying questions if needed
        if len(questions) < 3:
            questions.extend([
                "Bạn có thể mô tả chi tiết hơn về vấn đề không?",
                "Điều gì đã xảy ra ngay trước khi vấn đề này xuất hiện?"
            ])
        
        # Return top 5 unique questions
        unique_questions = list(dict.fromkeys(questions))  # Remove duplicates while preserving order
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
            "entities": {},
            "detected_patterns": {},
            "all_candidates": [],
            "diagnostic_questions": fallback_result.diagnostic_questions,
            "processing_time": datetime.now().isoformat()
        }


# Global classifier agent instance
classifier_agent = ClassifierAgent()


async def get_classifier_agent() -> ClassifierAgent:
    """Get the global classifier agent instance."""
    if not classifier_agent.vector_search_service:
        await classifier_agent.initialize()
    return classifier_agent