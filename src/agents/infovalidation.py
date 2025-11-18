"""
InfoValidation Agent - Unified Information Gathering and Validation

This agent combines the functionality of both RequiredInfo and Validation agents
as specified in the Phase 2 plan.md architecture.

Responsibilities:
1. Information gathering through conversational dialogue
2. Diagnostic question generation and context management  
3. Validation execution using diagnostic tools
4. Result analysis and confidence scoring
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from src.agents.base import BaseAgent
from src.models.session import SessionState, RequiredInfoResult, ValidationResult


class InfoValidationAgent(BaseAgent):
    """
    Unified agent for information gathering and validation.
    
    Combines the capabilities of RequiredInfo and Validation agents
    for more efficient workflow in Phase 2 architecture.
    """
    
    def __init__(self):
        super().__init__("InfoValidationAgent")
        self.logger = logging.getLogger(__name__)
        
        # Configuration thresholds
        self.max_conversation_turns = 4
        self.validation_confidence_threshold = 0.8
        self.information_completeness_threshold = 0.7
        
        # Tool execution configuration
        self.tool_timeout = 60
        self.max_parallel_tools = 3
        
        # Conversation state tracking
        self.conversation_state = {
            'turn_count': 0,
            'collected_info': {},
            'asked_questions': set(),
            'validation_results': [],
            'confidence_score': 0.0
        }
    
    async def initialize(self):
        """Initialize InfoValidation agent dependencies."""
        try:
            self.logger.info("InfoValidation agent initialized successfully")
            # Will be extended with tool registry and database connections
        except Exception as e:
            self.logger.error(f"Failed to initialize InfoValidation agent: {str(e)}")
            raise
    
    async def execute(self, session_state: SessionState, **kwargs) -> Dict[str, Any]:
        """
        Execute unified information gathering and validation workflow.
        
        Args:
            session_state: Current session state with classification results
            **kwargs: Additional parameters (user_input, context, etc.)
            
        Returns:
            Unified result with information completeness and validation status
        """
        user_input = kwargs.get('user_input', '')
        retry_count = kwargs.get('retry_count', 0)
        
        self.logger.info(f"Executing InfoValidation agent: {user_input[:100]}...")
        
        try:
            # Reset conversation state for new execution
            if retry_count == 0:
                self.conversation_state = {
                    'turn_count': 1,
                    'collected_info': {},
                    'asked_questions': set(),
                    'validation_results': [],
                    'confidence_score': 0.0
                }
            
            # Step 1: Analyze classification result to understand required information
            required_info = await self._analyze_information_requirements(session_state)
            
            # Step 2: Process user input and extract information
            extracted_info = await self._extract_information(user_input, required_info)
            
            # Step 3: Check information completeness
            information_complete = await self._assess_information_completeness(
                required_info, extracted_info
            )
            
            # Step 4: If information is complete, perform validation
            validation_results = []
            validation_confirmed = False
            
            if information_complete:
                validation_results = await self._perform_validation(
                    required_info, extracted_info, session_state
                )
                validation_confirmed = await self._assess_validation_confidence(
                    validation_results
                )
            
            # Step 5: Generate next questions if needed
            next_questions = []
            if not information_complete or not validation_confirmed:
                next_questions = await self._generate_next_questions(
                    required_info, extracted_info, validation_results
                )
            
            # Step 6: Create unified result
            result = {
                "success": True,
                "information_complete": information_complete,
                "validation_confirmed": validation_confirmed,
                "collected_information": extracted_info,
                "validation_results": validation_results,
                "next_questions": next_questions,
                "turn_count": self.conversation_state['turn_count'],
                "confidence_score": self.conversation_state['confidence_score'],
                "processing_time": datetime.now().isoformat()
            }
            
            self.logger.info(f"InfoValidation completed: Info={information_complete}, "
                           f"Validation={validation_confirmed}, "
                           f"Turn={self.conversation_state['turn_count']}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"InfoValidation execution failed: {str(e)}")
            return await self.handle_error(e, session_state)
    
    async def _analyze_information_requirements(self, session_state: SessionState) -> Dict[str, Any]:
        """Analyze classification result to determine required information."""
        classification = session_state.classification
        
        if not classification:
            return {"required_fields": ["issue_description"], "priority": "high"}
        
        # Extract required information based on classification
        requirements = {
            "required_fields": [],
            "optional_fields": [],
            "priority": "medium",
            "diagnostic_tools": classification.recommended_tools or []
        }
        
        # Category-specific requirements
        if "formula" in classification.suggested_category.lower():
            requirements["required_fields"].extend([
                "dish_name", "warehouse", "period", "formula_details"
            ])
        elif "data_sync" in classification.suggested_category.lower():
            requirements["required_fields"].extend([
                "warehouse", "sync_direction", "error_messages", "connection_status"
            ])
        elif "performance" in classification.suggested_category.lower():
            requirements["required_fields"].extend([
                "slow_operations", "timing_details", "browser_info", "data_size"
            ])
        
        # Add diagnostic questions from classification
        if classification.diagnostic_questions:
            requirements["diagnostic_questions"] = classification.diagnostic_questions
        
        self.logger.info(f"Analyzed information requirements: {len(requirements['required_fields'])} fields")
        return requirements
    
    async def _extract_information(self, user_input: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured information from user input."""
        extracted = {}
        
        # Simple extraction logic - will be enhanced with NLP
        if "kho" in user_input.lower():
            parts = user_input.lower().split("kho")
            if len(parts) > 1:
                extracted["warehouse"] = parts[1].strip().split()[0]
        
        # Extract period information
        import re
        period_patterns = [
            r"tháng\s+(\d{1,2})[/]?(\d{4})?",
            r"ky\s+(\d{1,2})[/]?(\d{4})?",
            r"(\d{1,2})[/](\d{4})"
        ]
        
        for pattern in period_patterns:
            match = re.search(pattern, user_input.lower())
            if match:
                month = match.group(1)
                year = match.group(2) if match.group(2) else "2024"
                extracted["period"] = f"{month}/{year}"
                break
        
        # Extract dish names
        dish_patterns = [
            r"món\s+([^\s,\.]+(?:\s+[^\s,\.]+)*)",
            r"([^,\s]+(?:\s+[^,\s]+)*)\s*(?:bị|gặp|mất)"
        ]
        
        for pattern in dish_patterns:
            match = re.search(pattern, user_input.lower())
            if match and len(match.group(1)) > 2:
                extracted["dish_name"] = match.group(1).strip()
                break
        
        # Store full user input as context
        extracted["user_input"] = user_input
        extracted["timestamp"] = datetime.now().isoformat()
        
        # Update conversation state
        self.conversation_state['collected_info'].update(extracted)
        
        self.logger.info(f"Extracted {len(extracted)} pieces of information")
        return extracted
    
    async def _assess_information_completeness(self, requirements: Dict[str, Any], 
                                             extracted_info: Dict[str, Any]) -> bool:
        """Assess if required information is complete."""
        required_fields = requirements.get("required_fields", [])
        
        if not required_fields:
            return True  # No specific requirements
        
        completed_fields = 0
        for field in required_fields:
            if field in extracted_info and extracted_info[field]:
                completed_fields += 1
        
        completeness_ratio = completed_fields / len(required_fields)
        is_complete = completeness_ratio >= self.information_completeness_threshold
        
        # Update conversation state confidence
        self.conversation_state['confidence_score'] = completeness_ratio
        
        self.logger.info(f"Information completeness: {completeness_ratio:.2f} ({is_complete})")
        return is_complete
    
    async def _perform_validation(self, requirements: Dict[str, Any], 
                                extracted_info: Dict[str, Any], 
                                session_state: SessionState) -> List[Dict[str, Any]]:
        """Perform validation using diagnostic tools."""
        validation_results = []
        
        # Placeholder for actual tool execution
        # In Phase 2 implementation, this will use the Tool Management system
        
        # Simulate tool execution based on category
        tools = requirements.get("diagnostic_tools", [])
        
        for tool in tools[:self.max_parallel_tools]:  # Limit parallel tools
            try:
                result = await self._execute_diagnostic_tool(tool, extracted_info)
                validation_results.append(result)
                
            except Exception as e:
                self.logger.error(f"Diagnostic tool {tool} failed: {str(e)}")
                validation_results.append({
                    "tool": tool,
                    "status": "failed",
                    "error": str(e)
                })
        
        # Store results in conversation state
        self.conversation_state['validation_results'] = validation_results
        
        self.logger.info(f"Executed {len(validation_results)} validation tools")
        return validation_results
    
    async def _execute_diagnostic_tool(self, tool_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single diagnostic tool."""
        # Placeholder implementation
        # In actual Phase 2, this will use the Tool Management & Infrastructure
        
        await asyncio.sleep(0.1)  # Simulate tool execution time
        
        # Simulate different tool results
        if tool_name == "check_formula":
            return {
                "tool": tool_name,
                "status": "success",
                "result": "Formula structure appears valid",
                "confidence": 0.8,
                "issues_found": []
            }
        elif tool_name == "query_database":
            return {
                "tool": tool_name,
                "status": "success", 
                "result": "Database query completed",
                "confidence": 0.9,
                "data_found": True
            }
        else:
            return {
                "tool": tool_name,
                "status": "success",
                "result": f"{tool_name} executed successfully",
                "confidence": 0.7
            }
    
    async def _assess_validation_confidence(self, validation_results: List[Dict[str, Any]]) -> bool:
        """Assess overall validation confidence."""
        if not validation_results:
            return False
        
        # Calculate average confidence from successful validations
        successful_results = [r for r in validation_results if r.get("status") == "success"]
        
        if not successful_results:
            return False
        
        avg_confidence = sum(r.get("confidence", 0) for r in successful_results) / len(successful_results)
        
        # Check for critical issues
        critical_issues = []
        for result in validation_results:
            if result.get("status") == "failed" or result.get("error"):
                critical_issues.append(result.get("tool", "unknown"))
        
        # Validation is confirmed if confidence is high and no critical issues
        validation_confirmed = (
            avg_confidence >= self.validation_confidence_threshold and
            len(critical_issues) == 0
        )
        
        # Update conversation state
        self.conversation_state['confidence_score'] = max(
            self.conversation_state['confidence_score'],
            avg_confidence
        )
        
        self.logger.info(f"Validation confidence: {avg_confidence:.2f} ({validation_confirmed})")
        return validation_confirmed
    
    async def _generate_next_questions(self, requirements: Dict[str, Any], 
                                     extracted_info: Dict[str, Any],
                                     validation_results: List[Dict[str, Any]]) -> List[str]:
        """Generate next questions for information gathering or clarification."""
        questions = []
        
        # Check missing required information
        required_fields = requirements.get("required_fields", [])
        for field in required_fields:
            if field not in extracted_info or not extracted_info[field]:
                question = self._generate_field_question(field, extracted_info)
                if question and question not in self.conversation_state['asked_questions']:
                    questions.append(question)
                    self.conversation_state['asked_questions'].add(question)
        
        # Add diagnostic questions from requirements
        diagnostic_questions = requirements.get("diagnostic_questions", [])
        for question in diagnostic_questions:
            if question not in self.conversation_state['asked_questions']:
                questions.append(question)
                self.conversation_state['asked_questions'].add(question)
        
        # Add clarification questions based on validation failures
        for result in validation_results:
            if result.get("status") == "failed":
                tool = result.get("tool", "diagnostic tool")
                questions.append(f"Could you provide more details about the {tool.replace('_', ' ')} issue?")
        
        # Add general follow-up questions if needed
        if len(questions) < 2 and self.conversation_state['turn_count'] < self.max_conversation_turns:
            questions.extend([
                "Bạn có thể cung cấp thêm chi tiết về vấn đề không?",
                "Điều gì đã xảy ra ngay trước khi vấn đề này xuất hiện?"
            ])
        
        # Increment turn counter
        self.conversation_state['turn_count'] += 1
        
        self.logger.info(f"Generated {len(questions)} next questions")
        return questions[:3]  # Return top 3 questions
    
    def _generate_field_question(self, field: str, extracted_info: Dict[str, Any]) -> Optional[str]:
        """Generate a question for a specific missing field."""
        question_mapping = {
            "dish_name": "Vấn đề này xảy ra với món ăn nào?",
            "warehouse": "Vấn đề này xảy ra ở kho nào?",
            "period": "Đây là kỳ báo cáo nào (tháng/năm)?",
            "formula_details": "Bạn có thể cung cấp chi tiết về công thức không?",
            "error_messages": "Bạn có thấy thông báo lỗi cụ thể nào không?",
            "connection_status": "Kết nối mạng/internet có ổn định không?",
            "slow_operations": "Chức năng nào đang chạy chậm?",
            "timing_details": "Vấn đề này xảy ra vào thời gian nào?",
            "browser_info": "Bạn đang dùng trình duyệt nào?"
        }
        
        return question_mapping.get(field)
    
    async def validate_input(self, session_state: SessionState, **kwargs) -> bool:
        """Validate input for InfoValidation agent."""
        # InfoValidation can work with minimal input, but requires classification
        return session_state.classification is not None
    
    async def handle_error(self, error: Exception, session_state: SessionState) -> Dict[str, Any]:
        """Handle InfoValidation errors with graceful degradation."""
        self.logger.error(f"InfoValidation error: {str(error)}")
        
        return {
            "success": False,
            "error": str(error),
            "error_type": "infovalidation_error",
            "information_complete": False,
            "validation_confirmed": False,
            "collected_information": self.conversation_state.get('collected_info', {}),
            "validation_results": [],
            "next_questions": [
                "Xin lỗi, tôi gặp sự cố khi xử lý. Bạn có thể thử lại không?",
                "Bạn có thể mô tả lại vấn đề một cách khác không?"
            ],
            "turn_count": self.conversation_state.get('turn_count', 0),
            "retry_count": 0,
            "processing_time": datetime.now().isoformat()
        }


# Global InfoValidation agent instance
infovalidation_agent = InfoValidationAgent()


async def get_infovalidation_agent() -> InfoValidationAgent:
    """Get the global InfoValidation agent instance."""
    return infovalidation_agent