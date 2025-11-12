"""
LLM Decision Service for Enhanced Orchestrator

This service implements the LLM-based decision engine described in the
LLM-based orchestrator document, providing intelligent routing and
decision making with caching, fallbacks, and comprehensive monitoring.
"""

import asyncio
import json
import hashlib
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from functools import lru_cache

from src.models.session import (
    SessionState, OrchestratorDecision, Task, TaskType, 
    SessionPhase, TaskStatus, AgentPhase
)
from src.core.config import get_config

logger = logging.getLogger(__name__)


class LLMDecisionService:
    """
    LLM-based decision service for orchestrator intelligence.
    
    Implements the decision engine from the LLM-based orchestrator design,
    with intelligent caching, fallbacks, and comprehensive monitoring.
    """
    
    def __init__(self, llm_client=None):
        """Initialize the LLM decision service."""
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.config = get_config()
        self.decision_cache = {}
        self.cache_ttl = timedelta(hours=1)  # Cache decisions for 1 hour
        self.max_cache_size = 1000
        
        # Metrics tracking
        self.metrics = {
            "total_decisions": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "fallback_used": 0,
            "low_confidence_decisions": 0,
            "decision_errors": 0
        }
        
        # System prompts versioning
        self.system_prompts = {
            "v1.0": self._get_base_system_prompt(),
            "v1.1": self._get_enhanced_system_prompt(),
            "v1.2": self._get_optimized_system_prompt()
        }
        self.current_prompt_version = "v1.2"
    
    async def make_decision(
        self,
        user_message: str,
        session_state: SessionState,
        context: Optional[Dict[str, Any]] = None
    ) -> OrchestratorDecision:
        """
        Make an LLM-based decision for orchestrator routing.
        
        Args:
            user_message: The user's input message
            session_state: Current session state
            context: Additional context (optional)
            
        Returns:
            OrchestratorDecision with routing and action recommendations
        """
        start_time = datetime.now()
        
        try:
            # Check cache first
            cache_key = self._get_cache_key(user_message, session_state)
            cached_decision = self._get_cached_decision(cache_key)
            if cached_decision:
                self.metrics["cache_hits"] += 1
                cached_decision.cache_hit = True
                cached_decision.processing_time_ms = int(
                    (datetime.now() - start_time).total_seconds() * 1000
                )
                return cached_decision
            
            self.metrics["cache_misses"] += 1
            
            # Build comprehensive context
            llm_context = self._build_llm_context(session_state, context)
            
            # Get decision from LLM
            decision = await self._call_llm_decision(user_message, llm_context)
            
            # Validate decision
            validated_decision = self._validate_decision(decision, session_state)
            
            # Cache high-confidence decisions
            if validated_decision.confidence > 0.9:
                self._cache_decision(cache_key, validated_decision)
            
            # Update metrics
            self.metrics["total_decisions"] += 1
            if validated_decision.confidence < 0.7:
                self.metrics["low_confidence_decisions"] += 1
            
            # Add timing
            validated_decision.processing_time_ms = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )
            
            self.logger.info(
                f"LLM decision: {validated_decision.intent_type} → {validated_decision.action} "
                f"(confidence: {validated_decision.confidence:.2f}, "
                f"processing_time: {validated_decision.processing_time_ms}ms)"
            )
            
            return validated_decision
            
        except Exception as e:
            self.logger.error(f"LLM decision error: {str(e)}")
            self.metrics["decision_errors"] += 1
            return self._get_fallback_decision(user_message, session_state)
    
    def _get_cache_key(self, user_message: str, session_state: SessionState) -> str:
        """Generate cache key for decision caching."""
        # Create a normalized context for caching
        context_parts = [
            user_message.lower().strip(),
            str(session_state.current_phase),
            str(len(session_state.conversation_history)),
            "has_active_task" if session_state.active_task else "no_active_task"
        ]
        
        if session_state.active_task:
            context_parts.append(session_state.active_task.task_type)
        
        context_str = "|".join(context_parts)
        return hashlib.md5(context_str.encode()).hexdigest()
    
    def _get_cached_decision(self, cache_key: str) -> Optional[OrchestratorDecision]:
        """Retrieve cached decision if valid."""
        if cache_key not in self.decision_cache:
            return None
        
        cached_item = self.decision_cache[cache_key]
        if datetime.now() - cached_item["timestamp"] > self.cache_ttl:
            # Expired cache entry
            del self.decision_cache[cache_key]
            return None
        
        return cached_item["decision"]
    
    def _cache_decision(self, cache_key: str, decision: OrchestratorDecision):
        """Cache a high-confidence decision."""
        # Clean old entries if cache is full
        if len(self.decision_cache) >= self.max_cache_size:
            self._cleanup_cache()
        
        self.decision_cache[cache_key] = {
            "decision": decision,
            "timestamp": datetime.now()
        }
    
    def _cleanup_cache(self):
        """Remove expired and oldest cache entries."""
        current_time = datetime.now()
        
        # Remove expired entries
        expired_keys = [
            key for key, item in self.decision_cache.items()
            if current_time - item["timestamp"] > self.cache_ttl
        ]
        for key in expired_keys:
            del self.decision_cache[key]
        
        # If still too many entries, remove oldest
        if len(self.decision_cache) >= self.max_cache_size:
            sorted_items = sorted(
                self.decision_cache.items(),
                key=lambda x: x[1]["timestamp"]
            )
            # Remove oldest 20% of entries
            remove_count = max(1, len(sorted_items) // 5)
            for key, _ in sorted_items[:remove_count]:
                del self.decision_cache[key]
    
    def _build_llm_context(
        self, 
        session_state: SessionState, 
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build comprehensive context for LLM decision making."""
        context = {
            "session_id": session_state.session_id,
            "user_id": session_state.user_id,
            "current_phase": session_state.current_phase.value if session_state.current_phase else "idle",
            "has_active_task": session_state.active_task is not None,
            "conversation_turns": len(session_state.conversation_history),
            "conversation_history": session_state.conversation_history[-5:] if session_state.conversation_history else [],
            "user_metadata": session_state.user_metadata,
        }
        
        # Add active task information
        if session_state.active_task:
            task = session_state.active_task
            context["active_task"] = {
                "task_id": task.task_id,
                "task_type": task.task_type.value,
                "status": task.status.value,
                "current_phase": task.current_phase.value,
                "current_agent": task.current_agent,
                "waiting_for": task.waiting_for,
                "last_user_message": task.last_user_message,
                "priority": task.priority,
                "is_critical_phase": task.current_phase in [
                    SessionPhase.VALIDATE, 
                    SessionPhase.FIX
                ],
                "duration_minutes": int(
                    (datetime.now() - task.created_at).total_seconds() / 60
                )
            }
        
        # Add pending tasks count
        if session_state.pending_tasks:
            context["pending_tasks_count"] = len(session_state.pending_tasks)
        
        # Add recent decisions for context
        if session_state.recent_decisions:
            context["recent_decisions"] = [
                {
                    "intent_type": d.intent_type,
                    "action": d.action,
                    "confidence": d.confidence,
                    "reasoning": d.reasoning
                }
                for d in session_state.recent_decisions[-3:]
            ]
        
        # Add additional context if provided
        if additional_context:
            context.update(additional_context)
        
        return context
    
    async def _call_llm_decision(
        self, 
        user_message: str, 
        context: Dict[str, Any]
    ) -> OrchestratorDecision:
        """Call LLM for decision making."""
        if not self.llm_client:
            return self._get_fallback_decision(user_message, None)
        
        # Get system prompt
        system_prompt = self.system_prompts[self.current_prompt_version]
        
        # Build user prompt
        user_prompt = self._build_user_prompt(user_message, context)
        
        # Call LLM with structured output
        response = await self.llm_client.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "orchestrator_decision",
                    "schema": OrchestratorDecision.model_json_schema()
                }
            },
            temperature=0.3,
            max_tokens=800,
            timeout=15  # 15 second timeout
        )
        
        # Parse and validate response
        try:
            decision = OrchestratorDecision.model_validate_json(response)
            return decision
        except Exception as e:
            self.logger.error(f"Invalid LLM response format: {e}")
            return self._get_fallback_decision(user_message, None)
    
    def _build_user_prompt(
        self, 
        user_message: str, 
        context: Dict[str, Any]
    ) -> str:
        """Build user prompt with context."""
        prompt_parts = []
        
        # Current context
        prompt_parts.append("=== CURRENT CONTEXT ===")
        
        if context.get("has_active_task"):
            task_info = context["active_task"]
            prompt_parts.append(f"""
Active Task:
- Task ID: {task_info['task_id']}
- Type: {task_info['task_type']}
- Phase: {task_info['current_phase']}
- Status: {task_info['status']}
- Current Agent: {task_info['current_agent']}
- Waiting For: {task_info['waiting_for']}
- Priority: {task_info['priority']}
- Is Critical Phase: {task_info['is_critical_phase']}
- Duration: {task_info['duration_minutes']} minutes
- Last User Message: "{task_info['last_user_message']}"
""")
        else:
            prompt_parts.append("Active Task: None")
        
        # Pending tasks
        if context.get("pending_tasks_count"):
            prompt_parts.append(f"Pending Tasks: {context['pending_tasks_count']}")
        
        # Recent conversation
        if context.get("recent_messages"):
            prompt_parts.append("\n=== RECENT CONVERSATION ===")
            for msg in context["recent_messages"]:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:200]  # Limit length
                prompt_parts.append(f"{role}: {content}")
        
        # Recent decisions
        if context.get("recent_decisions"):
            prompt_parts.append("\n=== RECENT DECISIONS ===")
            for i, decision in enumerate(context["recent_decisions"], 1):
                prompt_parts.append(
                    f"{i}. {decision['intent_type']} → {decision['action']} "
                    f"(confidence: {decision['confidence']:.2f})"
                )
        
        # New user message
        prompt_parts.append("\n=== NEW USER MESSAGE ===")
        prompt_parts.append(f'User: "{user_message}"')
        
        # Request
        prompt_parts.append("\n=== YOUR TASK ===")
        prompt_parts.append("""
Analyze the user message in context and decide:
1. What is the user's intent? (new_request, continuation, control_command, ambiguous)
2. What action should the orchestrator take?
3. What message (if any) should be shown to user?

Return your decision as JSON following OrchestratorDecision schema.

DECISION RULES:
1. New Request Detection:
   - User reports error → intent_type: "new_request", new_task_type: "error_resolution"
   - User asks how to use feature → intent_type: "new_request", new_task_type: "feature_usage"
   - If NO active task → action: "create_new_task"
   - If HAS active task → check conflict

2. Continuation Detection:
   - Active task exists AND in waiting state → intent_type: "continuation"
   - User provides info/confirmation/selection → action: "forward_to_current_agent"

3. Control Commands:
   - User says cancel/stop → intent_type: "control_command", action: "cancel_task"
   - User says restart → intent_type: "control_command", action: "restart_task"

4. Task Conflict Handling:
   - New request while active task exists:
     * IF active task in CRITICAL phase → action: "ask_task_switch_confirmation"
     * IF active task in EARLY phase → action: "auto_switch_task"

5. Ambiguous Cases:
   - Cannot determine intent → intent_type: "ambiguous", action: "ask_clarification"

Be concise in reasoning (max 50 words). Prioritize user experience.
""")
        
        return "\n".join(prompt_parts)
    
    def _validate_decision(
        self, 
        decision: OrchestratorDecision, 
        session_state: SessionState
    ) -> OrchestratorDecision:
        """Validate and potentially correct the decision."""
        # Fix invalid actions
        if decision.action == "forward_to_current_agent" and not session_state.active_task:
            self.logger.warning("Invalid decision: forward_to_current_agent with no active task")
            decision.action = "ask_clarification"
            decision.user_message = "I'm not sure what you'd like me to help with. Could you please clarify?"
            decision.confidence = 0.5
            decision.reasoning = "Corrected invalid forward action - no active task"
        
        # Fix missing task type for new tasks
        if decision.action == "create_new_task" and not decision.new_task_type:
            # Infer task type from user message or context
            decision.new_task_type = "error_resolution"  # Default assumption
            decision.confidence *= 0.8  # Reduce confidence due to inference
            decision.reasoning += " (task type inferred)"
        
        # Ensure user message for confirmations
        if decision.action == "ask_task_switch_confirmation" and not decision.user_message:
            decision.user_message = (
                "You have an active request in progress. Would you like to:\n"
                "1. Continue with current request\n"
                "2. Switch to new request\n"
                "3. Cancel current request"
            )
            decision.user_options = ["1", "2", "3"]
        
        return decision
    
    def _get_fallback_decision(
        self, 
        user_message: str, 
        session_state: Optional[SessionState]
    ) -> OrchestratorDecision:
        """Get fallback decision when LLM fails."""
        self.metrics["fallback_used"] += 1
        
        # Rule-based fallback logic
        if session_state and session_state.active_task:
            task = session_state.active_task
            
            # If in waiting state, assume continuation
            if task.current_phase.value.startswith("wait_user"):
                return OrchestratorDecision(
                    intent_type="continuation",
                    action="forward_to_current_agent",
                    target_agent=task.current_agent,
                    confidence=0.6,
                    reasoning="Fallback: Active task in waiting state"
                )
            
            # If critical phase, ask for clarification
            if task.current_phase in [SessionPhase.VALIDATE, SessionPhase.FIX]:
                return OrchestratorDecision(
                    intent_type="ambiguous",
                    action="ask_clarification",
                    user_message="I'm not sure how to help. Would you like to continue with the current task or start something new?",
                    confidence=0.5,
                    reasoning="Fallback: Critical phase detected"
                )
        
        # Default fallback - ask for clarification
        return OrchestratorDecision(
            intent_type="ambiguous",
            action="ask_clarification",
            user_message="I'm not sure what you need help with. Could you please provide more details?",
            confidence=0.4,
            reasoning="Fallback: No clear context available"
        )
    
    def _get_base_system_prompt(self) -> str:
        """Base system prompt for decision making."""
        return """You are an Orchestrator Agent for a customer support system.

Your role is to analyze user input in context and decide the next action.

DECISION RULES:
1. New Request Detection: User reports error/asks about feature → new_request
2. Continuation Detection: Active task waiting for input → continuation
3. Control Commands: User says cancel/stop/restart → control_command
4. Task Conflicts: New request during active task → handle appropriately
5. Ambiguous Cases: Cannot determine intent → ask_clarification

Return valid JSON matching OrchestratorDecision schema."""
    
    def _get_enhanced_system_prompt(self) -> str:
        """Enhanced system prompt with better context handling."""
        return """You are an intelligent Orchestrator Agent for a customer support system.

Your role is to analyze user input with full context awareness and make optimal routing decisions.

CORE PRINCIPLES:
- User experience first - minimize disruptions when possible
- Context awareness - consider conversation history and active tasks
- Intelligent routing - direct to the most appropriate agent
- Graceful degradation - ask for clarification when uncertain

DECISION FRAMEWORK:

1. NEW REQUESTS:
   - Error reports → intent_type: "new_request", new_task_type: "error_resolution"
   - Feature questions → intent_type: "new_request", new_task_type: "feature_usage"
   - No active task → action: "create_new_task"
   - Has active task → evaluate conflict

2. CONTINUATIONS:
   - Active task in waiting state → intent_type: "continuation"
   - User provides expected info → action: "forward_to_current_agent"

3. CONFLICT RESOLUTION:
   - Critical phase (validate/fix) → action: "ask_task_switch_confirmation"
   - Early phase (classify) → action: "auto_switch_task"
   - Long wait (>5 min) → action: "auto_switch_task"

4. CONTROL COMMANDS:
   - Cancel/stop → action: "cancel_task"
   - Restart → action: "restart_task"

5. UNCERTAINTY:
   - Low confidence → intent_type: "ambiguous", action: "ask_clarification"

Analyze conversation flow, emotional state, and intent evolution when making decisions.
Return valid JSON matching OrchestratorDecision schema."""
    
    def _get_optimized_system_prompt(self) -> str:
        """Optimized system prompt for token efficiency."""
        return """You are an Orchestrator Agent making routing decisions.

INTENTS:
- new_request: Error report or feature question (no active task)
- continuation: Response for waiting active task
- control_command: cancel/stop/restart
- ambiguous: Unclear intent

ACTIONS:
- create_new_task: Start new workflow
- forward_to_current_agent: Continue active workflow
- ask_task_switch_confirmation: Ask user about switching
- auto_switch_task: Auto-switch if safe
- cancel_task: End current workflow
- restart_task: Reset workflow
- ask_clarification: Request clarification
- escalate: Human intervention

RULES:
1. New request + no active task → create_new_task
2. Waiting active task + user input → forward_to_current_agent
3. New request + critical phase → ask_task_switch_confirmation
4. New request + early phase → auto_switch_task
5. Cancel/stop commands → cancel_task
6. Unclear intent → ask_clarification

Consider context, conversation flow, and user experience.
Return valid OrchestratorDecision JSON."""
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get decision service metrics."""
        cache_hit_rate = 0
        if self.metrics["cache_hits"] + self.metrics["cache_misses"] > 0:
            cache_hit_rate = self.metrics["cache_hits"] / (
                self.metrics["cache_hits"] + self.metrics["cache_misses"]
            )
        
        low_confidence_rate = 0
        if self.metrics["total_decisions"] > 0:
            low_confidence_rate = self.metrics["low_confidence_decisions"] / self.metrics["total_decisions"]
        
        return {
            "total_decisions": self.metrics["total_decisions"],
            "cache_hit_rate": cache_hit_rate,
            "cache_size": len(self.decision_cache),
            "fallback_rate": self.metrics["fallback_used"] / max(1, self.metrics["total_decisions"]),
            "low_confidence_rate": low_confidence_rate,
            "error_rate": self.metrics["decision_errors"] / max(1, self.metrics["total_decisions"]),
            "prompt_version": self.current_prompt_version
        }
    
    def clear_cache(self):
        """Clear the decision cache."""
        self.decision_cache.clear()
        self.logger.info("Decision cache cleared")
    
    def set_prompt_version(self, version: str):
        """Set the system prompt version."""
        if version in self.system_prompts:
            self.current_prompt_version = version
            self.logger.info(f"Switched to prompt version: {version}")
        else:
            raise ValueError(f"Unknown prompt version: {version}")


# Singleton instance for application-wide use
_llm_decision_service = None

def get_llm_decision_service(llm_client=None) -> LLMDecisionService:
    """Get the singleton LLM decision service instance."""
    global _llm_decision_service
    if _llm_decision_service is None:
        _llm_decision_service = LLMDecisionService(llm_client)
    return _llm_decision_service