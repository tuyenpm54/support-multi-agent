"""
Orchestrator Preprocessing Module

This module provides intelligent preprocessing for the orchestrator agent,
using LLM analysis to determine the best next action based on user input,
conversation context, and current state.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class UserIntent(Enum):
    """Possible user intents identified by LLM preprocessing."""
    
    # Primary intents (initial messages)
    DIRECT_RESPONSE = "direct_response"        # Simple questions, LLM can respond immediately
    ISSUE_REPORT = "issue_report"            # Technical problem that needs workflow
    PRODUCT_INFO = "product_info"            # Product/feature information request
    HELP_GUIDANCE = "help_guidance"          # User needs help using system
    CONVERSATIONAL = "conversational"        # Casual conversation, greetings, thanks
    UNCLEAR = "unclear"                     # Intent not clear, needs clarification
    
    # Follow-up intents (ongoing conversations)
    PROVIDE_INFO = "provide_info"           # User providing missing information
    UPDATE_ISSUE = "update_issue"           # User updating/changing issue description
    CONFIRM_SOLUTION = "confirm_solution"    # User confirming suggested fix/approach
    REQUEST_FEEDBACK = "request_feedback"    # User asking for status/progress update
    CORRECTION = "correction"              # User correcting previous response/suggestion
    SATISFACTION = "satisfaction"           # User expressing satisfaction or frustration
    ESCALATION = "escalation"              # User wants to escalate to human agent
    
    # Response intents (feedback on system actions)
    CONFIRM_UNDERSTANDING = "confirm_understanding"  # "Yes, that's correct"
    DISAGREE_SUGGESTION = "disagree_suggestion"        # "No, that's not right"
    REQUEST_ALTERNATIVE = "request_alternative"      # "Can you try something else?"
    PROVIDE_DETAILS = "provide_details"          # "Let me add more context"
    REQUEST_CLARIFICATION = "request_clarification"  # "What do you mean by X?"
    
    # Completion intents
    ISSUE_RESOLVED = "issue_resolved"        # Problem fixed, thanking system
    NEED_MORE_HELP = "need_more_help"          # Still need assistance
    END_CONVERSATION = "end_conversation"       # Goodbye, closing session

class OrchestratorAction(Enum):
    """Actions the orchestrator should take based on LLM analysis."""
    RESPOND_IMMEDIATELY = "respond_immediately"
    START_CLASSIFICATION = "start_classification"
    GET_MORE_INFO = "get_more_info"
    GUIDE_USER = "guide_user"
    ESCALATE = "escalate"
    CONTINUE_WORKFLOW = "continue_workflow"      # Continue with current agent
    MODIFY_CLASSIFICATION = "modify_classification"   # Update classification with new info
    REQUEST_AGENT_SWITCH = "request_agent_switch"    # Switch to different agent type
    FOLLOW_UP_CLARIFICATION = "follow_up_clarification"  # Ask clarification on previous response
    VALIDATE_SOLUTION = "validate_solution"      # Confirm solution with user
    CLOSE_CASE = "close_case"                  # Case resolved, close conversation

@dataclass
class PreprocessingResult:
    """Result from LLM preprocessing analysis."""
    success: bool
    user_intent: UserIntent
    orchestrator_action: OrchestratorAction
    confidence: float
    immediate_response: Optional[str] = None
    extracted_entities: Dict[str, Any] = None
    context_analysis: Dict[str, Any] = None
    suggested_next_steps: List[str] = None
    error: Optional[str] = None
    processing_time: Optional[datetime] = None

class OrchestratorPreprocessor:
    """Intelligent preprocessor for orchestrator using LLM analysis."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._llm_manager = None
    
    @property
    def llm_manager(self):
        """Lazy loading of LLM manager."""
        return self._llm_manager
    
    async def initialize(self):
        """Initialize the LLM manager."""
        try:
            from src.core.llm import get_llm_manager
            self._llm_manager = None  # Will be initialized async
            self.logger.info("Orchestrator preprocessor initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM manager: {str(e)}")
            self._llm_manager = None
    
    async def preprocess_user_input(
        self,
        user_input: str,
        current_state: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        session_context: Optional[Dict[str, Any]] = None
    ) -> PreprocessingResult:
        """
        Analyze user input and determine the best orchestrator action.
        
        Args:
            user_input: The user's message
            current_state: Current session state and phase information
            conversation_history: Recent conversation turns
            session_context: Additional session context
            
        Returns:
            PreprocessingResult with LLM analysis and recommendations
        """
        
        start_time = datetime.now()
        
        try:
            if not self.llm_manager:
                await self.initialize()
            
            if not self.llm_manager:
                # Fallback to basic analysis if LLM unavailable
                return await self._fallback_analysis(user_input, current_state, start_time)
            
            # Build comprehensive analysis prompt
            analysis_prompt = await self._build_analysis_prompt(
                user_input, current_state, conversation_history, session_context
            )
            
            # Get LLM analysis
            llm_response = await self.llm_manager.generate_text(
                analysis_prompt,
                temperature=0.1,  # Low temperature for consistent analysis
                max_tokens=1500
            )
            
            # Parse LLM response
            parsed_result = await self._parse_llm_response(llm_response.content, start_time)
            
            self.logger.info(f"Preprocessing completed: {parsed_result.user_intent.value} "
                           f"→ {parsed_result.orchestrator_action.value} "
                           f"(confidence: {parsed_result.confidence:.2f})")
            
            return parsed_result
            
        except Exception as e:
            self.logger.error(f"Preprocessing failed: {str(e)}")
            return PreprocessingResult(
                success=False,
                user_intent=UserIntent.UNCLEAR,
                orchestrator_action=OrchestratorAction.GET_MORE_INFO,
                confidence=0.0,
                error=str(e),
                processing_time=datetime.now(),
                extracted_entities={},
                context_analysis={'emotional_state': 'neutral'},
                suggested_next_steps=[]
            )
    
    async def _build_analysis_prompt(
        self,
        user_input: str,
        current_state: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]],
        session_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build comprehensive analysis prompt for LLM."""
        
        # Extract key information from current state
        current_phase = current_state.get('current_phase', 'init')
        session_id = current_state.get('session_id', 'unknown')
        
        # Build conversation context
        history_text = ""
        if conversation_history:
            recent_history = conversation_history[-3:]  # Last 3 turns
            history_text = "\nRecent conversation:\n"
            for turn in recent_history:
                role = turn.get('role', 'unknown')
                content = turn.get('content', '')[:100]  # Limit length
                history_text += f"{role}: {content}\n"
        
        # Build session context
        context_text = ""
        if session_context:
            context_text = f"\nSession context:\n{json.dumps(session_context, indent=2)}\n"
        
        prompt = f"""Analyze user input and determine intent and action.

Phase: {current_phase}
Input: "{user_input}"
{history_text}

INTENTS:
Primary: direct_response, issue_report, product_info, help_guidance, conversational, unclear
Follow-up: provide_info, update_issue, confirm_solution, request_feedback, correction, satisfaction, escalation  
Response: confirm_understanding, disagree_suggestion, request_alternative, provide_details, request_clarification
Completion: issue_resolved, need_more_help, end_conversation

ACTIONS:
respond_immediately, start_classification, get_more_info, guide_user, escalate, continue_workflow, modify_classification, request_agent_switch, follow_up_clarification, validate_solution, close_case

EMOTIONAL STATES:
neutral, frustrated, pleased, confused

Return JSON:
{{
    "user_intent": "intent_category",
    "orchestrator_action": "recommended_action", 
    "confidence": 0.85,
    "immediate_response": "Response if action is respond_immediately",
    "emotional_state": "neutral/frustrated/pleased/confused"
}}

JSON only:"""

        return prompt
    
    async def _parse_llm_response(self, llm_content: str, start_time: datetime) -> PreprocessingResult:
        """Parse LLM response into structured result."""
        
        try:
            # Extract JSON from response (LLM might include explanation before/after JSON)
            json_start = llm_content.find('{')
            json_end = llm_content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in LLM response")
            
            json_str = llm_content[json_start:json_end]
            parsed = json.loads(json_str)
            
            # Map intent and action strings to enums
            user_intent = UserIntent(parsed.get('user_intent', 'unclear'))
            orchestrator_action = OrchestratorAction(parsed.get('orchestrator_action', 'get_more_info'))
            
            return PreprocessingResult(
                success=True,
                user_intent=user_intent,
                orchestrator_action=orchestrator_action,
                confidence=float(parsed.get('confidence', 0.5)),
                immediate_response=parsed.get('immediate_response'),
                extracted_entities={},
                context_analysis={'emotional_state': parsed.get('emotional_state', 'neutral')},
                suggested_next_steps=[],
                processing_time=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {str(e)}")
            self.logger.debug(f"LLM response content: {llm_content}")
            
            # Fallback to conservative action
            return PreprocessingResult(
                success=False,
                user_intent=UserIntent.UNCLEAR,
                orchestrator_action=OrchestratorAction.GET_MORE_INFO,
                confidence=0.0,
                error=f"Response parsing failed: {str(e)}",
                processing_time=datetime.now(),
                extracted_entities={},
                context_analysis={'emotional_state': 'neutral'},
                suggested_next_steps=[]
            )
    
    async def _fallback_analysis(
        self,
        user_input: str,
        current_state: Dict[str, Any],
        start_time: datetime
    ) -> PreprocessingResult:
        """Fallback analysis when LLM is unavailable."""
        
        input_lower = user_input.lower().strip()
        
        # Simple keyword-based analysis
        if any(greeting in input_lower for greeting in ['hello', 'hi', 'chào', 'xin chào']):
            return PreprocessingResult(
                success=True,
                user_intent=UserIntent.CONVERSATIONAL,
                orchestrator_action=OrchestratorAction.RESPOND_IMMEDIATELY,
                confidence=0.7,
                immediate_response="Hello! How can I help you today? Please describe any issues you're experiencing.",
                processing_time=datetime.now(),
                extracted_entities={'greeting': True},
                context_analysis={'requires_immediate_attention': False},
                suggested_next_steps=[]
            )
        
        elif any(word in input_lower for word in ['help', 'hướng dẫn', 'tôi cần giúp']):
            return PreprocessingResult(
                success=True,
                user_intent=UserIntent.HELP_GUIDANCE,
                orchestrator_action=OrchestratorAction.GUIDE_USER,
                confidence=0.6,
                processing_time=datetime.now(),
                extracted_entities={'help_request': True},
                context_analysis={'user_experience': 'beginner'},
                suggested_next_steps=["Provide system overview", "Explain available features"]
            )
        
        else:
            # Default to classification workflow
            return PreprocessingResult(
                success=True,
                user_intent=UserIntent.ISSUE_REPORT,
                orchestrator_action=OrchestratorAction.START_CLASSIFICATION,
                confidence=0.4,
                processing_time=datetime.now(),
                extracted_entities={},
                context_analysis={'requires_immediate_attention': True},
                suggested_next_steps=["Begin classification process"]
            )

# Global preprocessor instance
_orchestrator_preprocessor = OrchestratorPreprocessor()

async def get_orchestrator_preprocessor():
    """Get the global orchestrator preprocessor instance."""
    if not _orchestrator_preprocessor.llm_manager:
        await _orchestrator_preprocessor.initialize()
    return _orchestrator_preprocessor