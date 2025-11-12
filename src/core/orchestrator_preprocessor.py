"""
Clean Orchestrator Preprocessing Module

This module provides intelligent preprocessing for the orchestrator agent
using the LLM-based decision engine with comprehensive context analysis
and structured decision making.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

from src.models.session import OrchestratorDecision, SessionState
from src.services.llm_decision import get_llm_decision_service


class OrchestratorPreprocessor:
    """Clean preprocessor for orchestrator using LLM-based decision engine."""
    
    def __init__(self, enable_llm_decisions: bool = True):
        self.logger = logging.getLogger(__name__)
        self.enable_llm_decisions = enable_llm_decisions
        self._llm_decision_service = None
    
    async def initialize(self):
        """Initialize the preprocessor components."""
        try:
            if self.enable_llm_decisions:
                self._llm_decision_service = get_llm_decision_service()
            self.logger.info("Orchestrator preprocessor initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize preprocessor: {str(e)}")
            self._llm_decision_service = None
    
    async def preprocess_user_input(
        self,
        user_input: str,
        session_state: SessionState,
        session_context: Optional[Dict[str, Any]] = None
    ) -> OrchestratorDecision:
        """
        Clean user input analysis using LLM-based decision engine.
        
        Args:
            user_input: The user's message
            session_state: Current session state (structured)
            session_context: Additional session context
            
        Returns:
            OrchestratorDecision with structured decision
        """
        
        try:
            # Use LLM decision service if available
            if self.enable_llm_decisions and self._llm_decision_service:
                decision = await self._llm_decision_service.make_decision(
                    user_input, session_state, session_context
                )
                
                self.logger.info(
                    f"LLM preprocessing completed: {decision.intent_type} → {decision.action} "
                    f"(confidence: {decision.confidence:.2f}, cache_hit: {decision.cache_hit})"
                )
                
                return decision
            
            # Fallback to rule-based decision
            return await self._fallback_decision(user_input, session_state)
            
        except Exception as e:
            self.logger.error(f"Preprocessing failed: {str(e)}")
            return self._emergency_fallback(user_input)
    
    async def _fallback_decision(self, user_input: str, session_state: SessionState) -> OrchestratorDecision:
        """Fallback decision making when LLM service is unavailable."""
        
        input_lower = user_input.lower().strip()
        
        # Simple keyword-based analysis
        if any(greeting in input_lower for greeting in ['hello', 'hi', 'chào', 'xin chào']):
            return OrchestratorDecision(
                intent_type="new_request",
                action="forward_to_current_agent",
                new_task_type="general_inquiry",
                confidence=0.7,
                reasoning="Greeting detected - friendly response",
                user_message="Hello! How can I help you today? Please describe any issues you're experiencing.",
                extracted_entities={'greeting': True},
                conversation_flow="smooth",
                emotional_state="neutral"
            )
        
        elif any(word in input_lower for word in ['help', 'hướng dẫn', 'tôi cần giúp']):
            return OrchestratorDecision(
                intent_type="new_request",
                action="create_new_task",
                new_task_type="feature_usage",
                confidence=0.6,
                reasoning="Help request detected - create guidance task",
                extracted_entities={'help_request': True},
                conversation_flow="smooth",
                emotional_state="neutral"
            )
        
        else:
            # Default to classification workflow
            return OrchestratorDecision(
                intent_type="new_request",
                action="create_new_task",
                new_task_type="error_resolution",
                confidence=0.4,
                reasoning="Default workflow - start classification",
                extracted_entities={},
                conversation_flow="smooth",
                emotional_state="neutral"
            )
    
    def _emergency_fallback(self, user_input: str) -> OrchestratorDecision:
        """Emergency fallback when everything else fails."""
        return OrchestratorDecision(
            intent_type="ambiguous",
            action="ask_clarification",
            confidence=0.1,
            reasoning="Emergency fallback - system needs clarification",
            user_message="I'm having trouble understanding. Could you please rephrase your request?",
            extracted_entities={},
            conversation_flow="interrupted",
            emotional_state="neutral"
        )

# Global preprocessor instance
_orchestrator_preprocessor = None

async def get_orchestrator_preprocessor(enable_llm_decisions: bool = True):
    """Get the global orchestrator preprocessor instance.
    
    Args:
        enable_llm_decisions: Whether to enable LLM-based decisions
        
    Returns:
        OrchestratorPreprocessor instance
    """
    global _orchestrator_preprocessor
    
    if _orchestrator_preprocessor is None:
        _orchestrator_preprocessor = OrchestratorPreprocessor(
            enable_llm_decisions=enable_llm_decisions
        )
        await _orchestrator_preprocessor.initialize()
    
    return _orchestrator_preprocessor