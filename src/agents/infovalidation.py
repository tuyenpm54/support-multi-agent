"""
Info Validation Agent - Information Gathering and Missing Information Collection

This agent handles information gathering and validation for general issues that require
additional context before attempting fixes. It bridges the gap between classification
and fix execution by ensuring all necessary information is collected.

Key Responsibilities:
1. Analyze general issues for missing information requirements
2. Generate contextual diagnostic questions
3. Collect structured responses from users
4. Validate completeness of gathered information
5. Prepare enriched context for FixAgent
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from src.agents.base import BaseAgent
from src.models.session import SessionState, InfoValidationResult
from src.core.information_collector import get_information_collector
from src.core.hierarchical_semantic_search import get_hierarchical_search_service


class InformationStatus(Enum):
    """Status of information collection for general issues."""
    PENDING = "pending"
    COLLECTING = "collecting"
    COMPLETE = "complete"
    INSUFFICIENT = "insufficient"
    FAILED = "failed"


class InfoValidationAgent(BaseAgent):
    """
    Agent for information gathering and validation before fix execution.
    
    This agent ensures that general issues have sufficient information
    before passing them to the FixAgent for resolution.
    """
    
    def __init__(self):
        super().__init__("InfoValidationAgent")
        self.logger = logging.getLogger(__name__)
        self.semantic_search_service = None
        self.information_collector = None
        
        # Configuration
        self.max_information_attempts = 3
        self.question_timeout = 300  # 5 minutes per question
        self.validation_timeout = 600  # 10 minutes for validation
        
        # Information collection state
        self.current_issue_id = None
        self.collected_information = {}
        self.asked_questions = []
        self.validation_results = []
    
    async def initialize(self):
        """Initialize the info validation agent."""
        try:
            self.semantic_search_service = await get_hierarchical_search_service()
            self.information_collector = get_information_collector()
            self.logger.info("Info validation agent initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize info validation agent: {str(e)}")
            raise
    
    async def execute(self, session_state: SessionState, **kwargs) -> Dict[str, Any]:
        """
        Execute information gathering and validation for general issues.
        
        Args:
            session_state: Current session state
            **kwargs: Additional parameters (issue_id, user_input, etc.)
            
        Returns:
            Information validation result with enriched context
        """
        issue_id = kwargs.get('issue_id')
        user_input = kwargs.get('user_input', '')
        
        if not issue_id:
            raise ValueError("issue_id is required for info validation agent")
        
        self.logger.info(f"Starting information validation for issue: {issue_id}")
        
        try:
            # Step 1: Get issue details and analyze information requirements
            issue_details = await self._get_issue_details(issue_id)
            
            # Step 2: Determine what information is missing
            information_gap = await self._analyze_information_gap(issue_details, session_state)
            
            # Step 3: Generate and ask questions to fill gaps
            if information_gap['has_gaps']:
                collection_result = await self._collect_missing_information(
                    issue_details, information_gap, session_state, user_input
                )
            else:
                collection_result = {
                    "success": True,
                    "collected_information": {},
                    "questions_asked": [],
                    "status": InformationStatus.COMPLETE.value
                }
            
            # Step 4: Validate information completeness
            validation_result = await self._validate_information_completeness(
                issue_details, collection_result, session_state
            )
            
            # Step 5: Prepare enriched context for FixAgent
            enriched_context = await self._prepare_enriched_context(
                issue_details, collection_result, validation_result, session_state
            )
            
            return {
                "success": validation_result['sufficient'],
                "issue_id": issue_id,
                "issue_type": issue_details['issue_type'],
                "information_gap": information_gap,
                "collection_result": collection_result,
                "validation_result": validation_result,
                "enriched_context": enriched_context,
                "processing_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Info validation failed: {str(e)}")
            return await self.handle_error(e, session_state)
    
    async def _get_issue_details(self, issue_id: str) -> Dict[str, Any]:
        """Get detailed information about an issue including information requirements."""
        try:
            async with self.semantic_search_service._connection_pool.acquire() as conn:
                # Get issue details
                issue = await conn.fetchrow("""
                    SELECT i.*, 
                           COALESCE(child_count.child_count, 0) as child_count,
                           COALESCE(parent_info.parent_title, NULL) as parent_title
                    FROM issues i
                    LEFT JOIN (
                        SELECT parent_issue_id, COUNT(*) as child_count
                        FROM issues
                        WHERE parent_issue_id IS NOT NULL
                        GROUP BY parent_issue_id
                    ) child_count ON i.issue_id = child_count.parent_issue_id
                    LEFT JOIN (
                        SELECT issue_id, title as parent_title
                        FROM issues
                    ) parent_info ON i.parent_issue_id = parent_info.issue_id
                    WHERE i.issue_id = $1
                """, issue_id)
                
                if not issue:
                    raise ValueError(f"Issue not found: {issue_id}")
                
                issue_details = dict(issue)
                
                # Get information requirements for general issues
                if issue_details['issue_type'] == 'general':
                    # For now, use basic requirements - in production, this would query a schema
                    issue_details['information_requirements'] = [
                        {
                            "information_category": "symptoms",
                            "required": True,
                            "description": "Specific symptoms and error messages",
                            "example_questions": [
                                "What specific error messages are you seeing?",
                                "When did this issue start occurring?",
                                "How frequently does this issue happen?"
                            ]
                        },
                        {
                            "information_category": "environment",
                            "required": False,
                            "description": "Environment and system details",
                            "example_questions": [
                                "What environment are you working in (production/staging)?",
                                "What browser or system are you using?"
                            ]
                        },
                        {
                            "information_category": "impact",
                            "required": True,
                            "description": "Business impact and affected users",
                            "example_questions": [
                                "How many users are affected by this issue?",
                                "What business processes are impacted?"
                            ]
                        }
                    ]
                else:
                    issue_details['information_requirements'] = []
                
                # Get detailed children for general issues
                if issue_details['issue_type'] == 'general' and issue_details['child_count'] > 0:
                    children = await conn.fetch("""
                        SELECT * FROM get_child_issues_ordered($1)
                        ORDER BY order_index
                    """, issue_id)
                    
                    issue_details['detailed_issues'] = [dict(child) for child in children]
                else:
                    issue_details['detailed_issues'] = []
                
                return issue_details
                
        except Exception as e:
            self.logger.error(f"Failed to get issue details: {str(e)}")
            raise
    
    async def _analyze_information_gap(
        self, issue_details: Dict[str, Any], session_state: SessionState
    ) -> Dict[str, Any]:
        """Analyze what information is missing for the issue."""
        try:
            self.logger.info("Analyzing information gap for general issue")
            
            missing_categories = []
            available_information = {}
            
            # Get information requirements
            info_requirements = issue_details.get('information_requirements', [])
            
            # Check each required information category
            for requirement in info_requirements:
                category = requirement['information_category']
                is_required = requirement['required']
                description = requirement['description']
                
                # Check if we have information for this category
                category_info = await self._extract_category_information(
                    category, issue_details, session_state
                )
                
                if category_info:
                    available_information[category] = {
                        "data": category_info,
                        "source": "existing",
                        "confidence": 0.8
                    }
                elif is_required:
                    missing_categories.append({
                        "category": category,
                        "description": description,
                        "priority": "high",
                        "example_questions": requirement.get('example_questions', [])
                    })
                else:
                    missing_categories.append({
                        "category": category,
                        "description": description,
                        "priority": "medium",
                        "example_questions": requirement.get('example_questions', [])
                    })
            
            has_gaps = len(missing_categories) > 0
            
            return {
                "has_gaps": has_gaps,
                "missing_categories": missing_categories,
                "available_information": available_information,
                "completeness_score": len(available_information) / (len(info_requirements) or 1)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to analyze information gap: {str(e)}")
            return {
                "has_gaps": True,
                "missing_categories": [],
                "available_information": {},
                "completeness_score": 0.0,
                "error": str(e)
            }
    
    async def _collect_missing_information(
        self,
        issue_details: Dict[str, Any],
        information_gap: Dict[str, Any],
        session_state: SessionState,
        user_input: str
    ) -> Dict[str, Any]:
        """Collect missing information through user questions."""
        try:
            self.logger.info("Collecting missing information from user")
            
            missing_categories = information_gap['missing_categories']
            collected_information = {}
            questions_asked = []
            
            # Sort by priority
            high_priority = [cat for cat in missing_categories if cat['priority'] == 'high']
            medium_priority = [cat for cat in missing_categories if cat['priority'] == 'medium']
            
            # Process high priority categories first
            for category in high_priority + medium_priority:
                category_name = category['category']
                
                try:
                    # Generate questions for this category
                    questions = await self._generate_category_questions(
                        category, issue_details, session_state
                    )
                    
                    category_responses = {}
                    
                    for question in questions:
                        question_text = question['question']
                        question_key = question['key']
                        
                        # Ask the question
                        response = await self._ask_question(
                            question_text, session_state, question_key
                        )
                        
                        category_responses[question_key] = response
                        questions_asked.append({
                            "category": category_name,
                            "question": question_text,
                            "response": response,
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    # Process responses for this category
                    processed_info = await self._process_category_responses(
                        category_name, category_responses, question
                    )
                    
                    if processed_info:
                        collected_information[category_name] = {
                            "data": processed_info,
                            "source": "user_response",
                            "confidence": 0.9,
                            "responses": category_responses
                        }
                    
                except Exception as e:
                    self.logger.error(f"Failed to collect information for category {category_name}: {str(e)}")
                    continue
            
            success = len(collected_information) > 0
            
            return {
                "success": success,
                "collected_information": collected_information,
                "questions_asked": questions_asked,
                "status": InformationStatus.COMPLETE.value if success else InformationStatus.INSUFFICIENT.value
            }
            
        except Exception as e:
            self.logger.error(f"Failed to collect missing information: {str(e)}")
            return {
                "success": False,
                "collected_information": {},
                "questions_asked": [],
                "status": InformationStatus.FAILED.value,
                "error": str(e)
            }
    
    async def _validate_information_completeness(
        self,
        issue_details: Dict[str, Any],
        collection_result: Dict[str, Any],
        session_state: SessionState
    ) -> Dict[str, Any]:
        """Validate if collected information is sufficient for fix execution."""
        try:
            self.logger.info("Validating information completeness")
            
            # Combine existing and newly collected information
            available_info = collection_result.get('collected_information', {})
            
            # Check if we have sufficient information for each required category
            info_requirements = issue_details.get('information_requirements', [])
            
            completeness_scores = {}
            total_score = 0
            max_score = 0
            
            for requirement in info_requirements:
                category = requirement['information_category']
                is_required = requirement['required']
                
                max_score += 1.0 if is_required else 0.5
                
                if category in available_info:
                    # Calculate completeness score for this category
                    category_score = await self._calculate_category_completeness(
                        category, available_info[category], requirement
                    )
                    completeness_scores[category] = category_score
                    total_score += category_score
                elif is_required:
                    completeness_scores[category] = 0.0
                else:
                    completeness_scores[category] = 0.5  # Partial credit for optional
            
            overall_score = total_score / max_score if max_score > 0 else 0.0
            sufficient = overall_score >= 0.7  # 70% completeness threshold
            
            return {
                "sufficient": sufficient,
                "overall_score": overall_score,
                "completeness_scores": completeness_scores,
                "missing_critical": [
                    cat for cat, score in completeness_scores.items()
                    if score < 0.5 and any(req['information_category'] == cat and req['required'] 
                                          for req in info_requirements)
                ],
                "recommendation": "Proceed to fix" if sufficient else "Collect more information"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to validate information completeness: {str(e)}")
            return {
                "sufficient": False,
                "overall_score": 0.0,
                "completeness_scores": {},
                "missing_critical": [],
                "recommendation": "Retry validation",
                "error": str(e)
            }
    
    async def _prepare_enriched_context(
        self,
        issue_details: Dict[str, Any],
        collection_result: Dict[str, Any],
        validation_result: Dict[str, Any],
        session_state: SessionState
    ) -> Dict[str, Any]:
        """Prepare enriched context for FixAgent."""
        try:
            self.logger.info("Preparing enriched context for FixAgent")
            
            # Combine all information sources
            enriched_context = {
                "issue_details": issue_details,
                "collected_information": collection_result.get('collected_information', {}),
                "information_completeness": validation_result,
                "session_context": {
                    "user_id": session_state.user_id,
                    "conversation_history": session_state.conversation_history[-5:],  # Last 5 messages
                    "classification_result": session_state.classification.dict() if session_state.classification else None
                },
                "metadata": {
                    "prepared_at": datetime.now().isoformat(),
                    "validation_score": validation_result.get('overall_score', 0.0),
                    "questions_asked": len(collection_result.get('questions_asked', [])),
                    "information_categories": list(collection_result.get('collected_information', {}).keys())
                }
            }
            
            # Add tool recommendations based on collected information
            tool_recommendations = await self._generate_tool_recommendations(
                issue_details, enriched_context
            )
            
            enriched_context["tool_recommendations"] = tool_recommendations
            
            return enriched_context
            
        except Exception as e:
            self.logger.error(f"Failed to prepare enriched context: {str(e)}")
            return {
                "issue_details": issue_details,
                "error": str(e),
                "prepared_at": datetime.now().isoformat()
            }
    
    # Helper methods for information collection and validation
    
    async def _extract_category_information(
        self, category: str, issue_details: Dict[str, Any], session_state: SessionState
    ) -> Optional[Dict[str, Any]]:
        """Extract existing information for a specific category."""
        try:
            # Check issue details
            if category == 'symptoms':
                return issue_details.get('symptoms') or issue_details.get('description')
            
            elif category == 'environment':
                return {
                    'system_info': issue_details.get('system_info'),
                    'category': issue_details.get('category'),
                    'severity': issue_details.get('severity')
                }
            
            elif category == 'user_context':
                return session_state.user_metadata
            
            elif category == 'timeline':
                # Extract timeline from conversation history
                recent_events = session_state.conversation_history[-3:]
                return {
                    'recent_messages': recent_events,
                    'session_duration': (datetime.now() - session_state.created_at).total_seconds()
                }
            
            # Add more category-specific extraction logic as needed
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to extract {category} information: {str(e)}")
            return None
    
    async def _generate_category_questions(
        self, category: Dict[str, Any], issue_details: Dict[str, Any], session_state: SessionState
    ) -> List[Dict[str, Any]]:
        """Generate questions for a specific information category."""
        try:
            category_name = category['category']
            example_questions = category.get('example_questions', [])
            
            questions = []
            
            if example_questions:
                # Use provided example questions
                for i, question_text in enumerate(example_questions):
                    questions.append({
                        "key": f"{category_name}_{i}",
                        "question": question_text,
                        "type": "open_ended",
                        "required": True
                    })
            else:
                # Generate default questions based on category
                if category_name == 'symptoms':
                    questions.append({
                        "key": "symptoms_description",
                        "question": f"Can you describe the specific symptoms you're experiencing with '{issue_details['title']}'?",
                        "type": "open_ended",
                        "required": True
                    })
                
                elif category_name == 'environment':
                    questions.append({
                        "key": "environment_details",
                        "question": "What environment or system details should we know about to resolve this issue?",
                        "type": "open_ended",
                        "required": False
                    })
                
                elif category_name == 'reproduction_steps':
                    questions.append({
                        "key": "reproduction_steps",
                        "question": "What steps can reproduce this issue? Please provide as much detail as possible.",
                        "type": "open_ended",
                        "required": True
                    })
                
                else:
                    # Generic question
                    questions.append({
                        "key": f"{category_name}_info",
                        "question": f"Can you provide more information about {category['description']}?",
                        "type": "open_ended",
                        "required": category.get('priority') == 'high'
                    })
            
            return questions
            
        except Exception as e:
            self.logger.error(f"Failed to generate questions for {category['category']}: {str(e)}")
            return []
    
    async def _ask_question(
        self, question_text: str, session_state: SessionState, question_key: str
    ) -> str:
        """Ask a question and get user response."""
        try:
            # In production, this would integrate with the chat interface
            # For now, simulate user responses for testing
            
            self.logger.info(f"Asking question: {question_text}")
            
            # Simulate user response based on question type
            if "symptoms" in question_key:
                return "The system is running slowly and users are experiencing timeouts when trying to access the dashboard."
            elif "environment" in question_key:
                return "Production environment on AWS, using PostgreSQL database, Redis cache, and FastAPI backend."
            elif "reproduction" in question_key:
                return "1. Login to system 2. Navigate to dashboard 3. Wait for page to load 4. Observe timeout error."
            elif "error" in question_key:
                return "Error message: 'Connection timeout after 30 seconds'"
            elif "impact" in question_key:
                return "Around 50 users affected, mainly sales team cannot generate reports"
            else:
                return f"Response to: {question_text} - This is a simulated user response for testing."
            
        except Exception as e:
            self.logger.error(f"Failed to ask question {question_key}: {str(e)}")
            return ""
    
    async def _process_category_responses(
        self, category_name: str, responses: Dict[str, str], question_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process responses for a specific information category."""
        try:
            if not responses:
                return {}
            
            # Combine and structure the responses
            processed_data = {
                "category": category_name,
                "responses": responses,
                "timestamp": datetime.now().isoformat()
            }
            
            # Category-specific processing
            if category_name == 'symptoms':
                # Extract structured symptom information
                all_text = " ".join(responses.values())
                processed_data["structured_symptoms"] = {
                    "description": all_text,
                    "keywords": self._extract_keywords(all_text),
                    "severity_indicators": self._extract_severity_indicators(all_text)
                }
            
            elif category_name == 'environment':
                # Parse environment details
                all_text = " ".join(responses.values())
                processed_data["structured_environment"] = {
                    "description": all_text,
                    "technologies": self._extract_technologies(all_text),
                    "infrastructure": self._extract_infrastructure(all_text)
                }
            
            elif category_name == 'reproduction_steps':
                # Parse reproduction steps
                all_text = " ".join(responses.values())
                steps = self._parse_reproduction_steps(all_text)
                processed_data["structured_steps"] = steps
            
            return processed_data
            
        except Exception as e:
            self.logger.error(f"Failed to process category responses for {category_name}: {str(e)}")
            return {"category": category_name, "responses": responses, "error": str(e)}
    
    async def _calculate_category_completeness(
        self, category: str, category_info: Dict[str, Any], requirement: Dict[str, Any]
    ) -> float:
        """Calculate completeness score for a specific information category."""
        try:
            data = category_info.get('data', {})
            
            if not data:
                return 0.0
            
            # Base score based on having data
            base_score = 0.5
            
            # Additional score based on data quality
            if isinstance(data, dict) and data.get('structured_symptoms'):
                base_score += 0.3  # Has structured data
            
            if len(str(data)) > 50:  # Has sufficient detail
                base_score += 0.2
            
            return min(1.0, base_score)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate completeness for {category}: {str(e)}")
            return 0.0
    
    async def _generate_tool_recommendations(
        self, issue_details: Dict[str, Any], enriched_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate tool recommendations based on collected information."""
        try:
            recommendations = []
            
            category = issue_details.get('category', 'general')
            collected_info = enriched_context.get('collected_information', {})
            
            # Base recommendations on category
            if category == 'performance':
                recommendations.extend([
                    {"tool": "system_monitor", "confidence": 0.8, "reason": "Performance issues detected"},
                    {"tool": "log_analyzer", "confidence": 0.7, "reason": "Need to analyze performance logs"}
                ])
            
            elif category == 'authentication':
                recommendations.extend([
                    {"tool": "user_validator", "confidence": 0.9, "reason": "Authentication related issue"},
                    {"tool": "session_checker", "confidence": 0.8, "reason": "Check session validity"}
                ])
            
            elif category == 'database':
                recommendations.extend([
                    {"tool": "db_connection_test", "confidence": 0.9, "reason": "Database connectivity issue"},
                    {"tool": "query_analyzer", "confidence": 0.7, "reason": "Analyze query performance"}
                ])
            
            # Add recommendations based on collected information
            if 'environment' in collected_info:
                env_info = collected_info['environment'].get('data', {})
                if 'AWS' in str(env_info):
                    recommendations.append({"tool": "aws_health_check", "confidence": 0.7, "reason": "AWS environment detected"})
            
            if 'symptoms' in collected_info:
                symptom_info = collected_info['symptoms'].get('data', {})
                if 'timeout' in str(symptom_info).lower():
                    recommendations.append({"tool": "timeout_analyzer", "confidence": 0.8, "reason": "Timeout symptoms detected"})
            
            return recommendations[:5]  # Limit to top 5 recommendations
            
        except Exception as e:
            self.logger.error(f"Failed to generate tool recommendations: {str(e)}")
            return []
    
    # Utility methods for text processing
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Simple keyword extraction - in production, use NLP
        import re
        words = re.findall(r'\b\w+\b', text.lower())
        # Filter out common words and return important ones
        stop_words = {'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but', 'in', 'with', 'to', 'for', 'of', 'as', 'by', 'it', 'this', 'that', 'are', 'be', 'have', 'has', 'had', 'was', 'were', 'will', 'would', 'could', 'should'}
        return [word for word in words if len(word) > 3 and word not in stop_words][:10]
    
    def _extract_severity_indicators(self, text: str) -> List[str]:
        """Extract severity indicators from text."""
        severity_keywords = ['critical', 'urgent', 'severe', 'major', 'blocker', 'timeout', 'crash', 'error', 'failed']
        return [word for word in severity_keywords if word in text.lower()]
    
    def _extract_technologies(self, text: str) -> List[str]:
        """Extract technology mentions from text."""
        tech_keywords = ['aws', 'azure', 'gcp', 'postgresql', 'mysql', 'redis', 'mongodb', 'docker', 'kubernetes', 'fastapi', 'django', 'flask', 'react', 'vue', 'angular']
        return [tech for tech in tech_keywords if tech in text.lower()]
    
    def _extract_infrastructure(self, text: str) -> List[str]:
        """Extract infrastructure mentions from text."""
        infra_keywords = ['production', 'staging', 'development', 'server', 'database', 'cache', 'load balancer', 'cdn', 'api gateway']
        return [infra for infra in infra_keywords if infra in text.lower()]
    
    def _parse_reproduction_steps(self, text: str) -> List[str]:
        """Parse reproduction steps from text."""
        # Simple parsing - look for numbered steps or step indicators
        import re
        
        # Try to extract numbered steps
        numbered_steps = re.findall(r'\d+\.\s*([^.!?]+[.!?]?)', text)
        if numbered_steps:
            return numbered_steps[:5]  # Limit to first 5 steps
        
        # Try to extract step indicators
        step_indicators = re.findall(r'(?:step|first|then|next|finally)\s*[:.]?\s*([^.!?]+[.!?]?)', text, re.IGNORECASE)
        if step_indicators:
            return step_indicators[:5]
        
        # Return as single step if no clear structure
        return [text] if text.strip() else []
    
    async def validate_input(self, session_state: SessionState, **kwargs) -> bool:
        """Validate input for info validation agent."""
        return kwargs.get('issue_id') is not None
    
    async def handle_error(self, error: Exception, session_state: SessionState) -> Dict[str, Any]:
        """Handle info validation agent errors with fallback behavior."""
        self.logger.error(f"Info validation agent error: {str(error)}")
        
        return {
            "success": False,
            "error": str(error),
            "error_type": "info_validation_error",
            "processing_time": datetime.now().isoformat(),
            "fallback_message": "I encountered an error while gathering information. Would you like to try a different approach?"
        }


# Global info validation agent instance
info_validation_agent = InfoValidationAgent()


async def get_info_validation_agent() -> InfoValidationAgent:
    """Get the global info validation agent instance."""
    return info_validation_agent