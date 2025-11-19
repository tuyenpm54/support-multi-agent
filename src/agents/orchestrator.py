import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from enum import Enum

from src.agents.base import BaseAgent
from src.models.session import (
    SessionState, AgentPhase, ClassificationResult, InfoValidationResult,
    FixResult, TimelineEvent
)
from src.agents.resolution_loop import ResolutionLoopAgent, DetailedIssueResult, ResolutionStatus
from src.core.state_manager import SessionManager
from src.core.coordination import (
    CoordinationManager, CoordinationEvent, CoordinationRule
)
from src.core.orchestrator_preprocessor import get_orchestrator_preprocessor
from src.services.llm_decision import get_llm_decision_service
from src.models.session import OrchestratorDecision, Task, TaskType, SessionPhase, TaskStatus


class OrchestratorState(Enum):
    """Orchestrator internal states for coordination flow."""
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    WAITING_FOR_USER = "waiting_for_user"
    HANDLING_ERROR = "handling_error"
    COMPLETING = "completing"
    ESCALATING = "escalating"


class OrchestratorAgent(BaseAgent):
    """
    Enhanced orchestrator agent with LLM-based decision making and coordination flow.
    
    Integrates the LLM-based orchestrator design with the existing coordination system,
    providing intelligent routing, task management, and hybrid decision making.
    """
    
    def __init__(self, use_llm_decisions: bool = True):
        super().__init__("Orchestrator")
        self.logger = logging.getLogger(__name__)
        
        # Agent registry - will be populated with actual agent instances
        self.agents: Dict[str, BaseAgent] = {}
        
        # Coordination manager (will be set via dependencies)
        self.coordination_manager: Optional[CoordinationManager] = None
        
        # LLM decision integration
        self.use_llm_decisions = use_llm_decisions
        self.llm_decision_service = None
        
        # Task management
        self.task_counter = 0
        
        # State transition rules - Updated for hierarchical resolution architecture
        self.state_transitions = {
            AgentPhase.CLASSIFY: {
                "success": self._determine_next_after_classification,
                "failure": self._handle_classification_failure
            },
            AgentPhase.RESOLUTION_LOOP: {
                "success": self._determine_next_after_resolution_loop,
                "failure": self._handle_resolution_loop_failure,
                "retry": AgentPhase.RESOLUTION_LOOP
            },
            AgentPhase.VALIDATE: {
                "success": AgentPhase.COMPLETE,
                "failure": self._handle_validation_failure,
                "retry": AgentPhase.VALIDATE
            },
            AgentPhase.FIX: {
                "success": AgentPhase.COMPLETE,
                "failure": self._handle_fix_failure,
                "retry": AgentPhase.FIX
            }
        }
        
        # Maximum retry counts per phase
        self.max_retries = {
            AgentPhase.CLASSIFY: 3,
            AgentPhase.RESOLUTION_LOOP: 5,  # Higher retries for complex hierarchical issues
            AgentPhase.VALIDATE: 3,
            AgentPhase.FIX: 2
        }
    
    def set_dependencies(self, session_manager, tool_registry):
        """Inject dependencies (session manager and tool registry)."""
        self.session_manager = session_manager
        self.tool_registry = tool_registry
        
        # Initialize coordination manager
        if session_manager and not self.coordination_manager:
            self.coordination_manager = CoordinationManager(session_manager)
            
            # Add custom coordination rules
            self._setup_coordination_rules()
        
        # Initialize LLM decision service if enabled
        if self.use_llm_decisions:
            self.llm_decision_service = get_llm_decision_service()
    
    def register_agent(self, phase: AgentPhase, agent: BaseAgent):
        """Register an agent instance for a specific phase."""
        self.agents[phase] = agent
        agent.set_dependencies(self.session_manager, self.tool_registry)
        self.logger.info(f"Registered {agent.name} agent for phase {phase}")
    
    def _setup_coordination_rules(self):
        """Set up custom coordination rules for the orchestrator."""
        if not self.coordination_manager:
            return
        
        # Rule: Route to resolution loop for hierarchical issues
        self.coordination_manager.add_coordination_rule(CoordinationRule(
            trigger_event=CoordinationEvent.AGENT_COMPLETE,
            source_phase=AgentPhase.CLASSIFY,
            condition=lambda data: (
                data.get("classification", {}).get("classified", False) and
                data.get("classification", {}).get("issue_type") in ["general", "detailed"]
            ),
            target_phase=AgentPhase.RESOLUTION_LOOP,
            priority=9
        ))
        
        # Rule: Auto-retry on low confidence classification
        self.coordination_manager.add_coordination_rule(CoordinationRule(
            trigger_event=CoordinationEvent.AGENT_COMPLETE,
            source_phase=AgentPhase.CLASSIFY,
            condition=lambda data: (
                data.get("classification", {}).get("confidence", 0) < 0.6 and
                data.get("session_state", {}).get("retry_count", 0) < 2
            ),
            target_phase=AgentPhase.CLASSIFY,
            priority=8
        ))
        
        # Rule: Fast-track to validation for high confidence detailed issues
        self.coordination_manager.add_coordination_rule(CoordinationRule(
            trigger_event=CoordinationEvent.AGENT_COMPLETE,
            source_phase=AgentPhase.CLASSIFY,
            condition=lambda data: (
                data.get("classification", {}).get("confidence", 0) > 0.9 and
                data.get("classification", {}).get("issue_type") == "detailed" and
                not data.get("classification", {}).get("has_diagnostic_question", False)
            ),
            target_phase=AgentPhase.VALIDATE,
            priority=7
        ))
        
        # Rule: Skip validation if fix agent already resolved the issue
        self.coordination_manager.add_coordination_rule(CoordinationRule(
            trigger_event=CoordinationEvent.AGENT_COMPLETE,
            source_phase=AgentPhase.FIX,
            condition=lambda data: (
                data.get("fix", {}).get("fix_result") == "SUCCESS" and
                data.get("fix", {}).get("verification", {}).get("issue_resolved", False)
            ),
            target_phase=AgentPhase.COMPLETE,
            priority=10
        ))
    
    async def execute(self, session_state: SessionState, **kwargs) -> Dict[str, Any]:
        """
        Execute the orchestrator coordination flow with intelligent preprocessing.
        
        Args:
            session_state: Current session state
            **kwargs: Additional parameters (user_input, agent_response, etc.)
            
        Returns:
            Updated session state and orchestration results
        """
        start_time = datetime.now()
        session_id = session_state.session_id
        
        try:
            # Preprocessing step: Analyze user input and determine best action
            if "user_input" in kwargs:
                orchestrator_decision = await self._preprocess_user_input(
                    session_state, kwargs["user_input"], **{k: v for k, v in kwargs.items() if k != 'user_input'}
                )
                
                # Handle immediate response cases
                if orchestrator_decision.action == "forward_to_current_agent" and orchestrator_decision.user_message:
                    
                    await self._add_timeline_event(
                        session_id,
                        "SYSTEM",
                        "IMMEDIATE_RESPONSE",
                        {
                            "decision_confidence": orchestrator_decision.confidence,
                            "intent_type": orchestrator_decision.intent_type,
                            "response_time_ms": int((datetime.now() - start_time).total_seconds() * 1000)
                        }
                    )
                    
                    return {
                        "session_id": session_id,
                        "current_phase": session_state.current_phase,
                        "next_phase": session_state.current_phase,  # No phase change
                        "outcome": "immediate_response",
                        "agent_result": {},
                        "actions_taken": ["preprocessing_analyzed", "immediate_response"],
                        "requires_user_input": True,
                        "messages": [orchestrator_decision.user_message],
                        "orchestrator_decision": orchestrator_decision,
                        "immediate_response": True
                    }
                
                # Execute LLM decision if LLM decisions are enabled
                if self.use_llm_decisions:
                    result = await self._execute_llm_decision(
                        orchestrator_decision,
                        session_state,
                        user_input=kwargs.get("user_input")
                    )
                    
                    # Add LLM decision completion event to timeline
                    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                    await self._add_timeline_event(
                        session_id,
                        "LLM_ORCHESTRATOR",
                        "LLM_DECISION_EXECUTED",
                        {
                            "action": orchestrator_decision.action,
                            "intent_type": orchestrator_decision.intent_type,
                            "confidence": orchestrator_decision.confidence,
                            "cache_hit": orchestrator_decision.cache_hit
                        },
                        duration_ms
                    )
                    
                    return result
                
                # Add decision insights to kwargs for downstream processing
                kwargs["orchestrator_decision"] = orchestrator_decision
            
            # Start coordination workflow if this is the first execution
            if self.coordination_manager and kwargs.get("start_workflow", False):
                await self.coordination_manager.start_session(session_id)
            
            # Add orchestration start event to timeline
            await self._add_timeline_event(
                session_id,
                "SYSTEM",
                "ORCHESTRATION_STARTED",
                {"phase": session_state.current_phase, **kwargs}
            )
            
            # Process any coordination events first
            if self.coordination_manager and "coordination_event" in kwargs:
                coordination_result = await self.coordination_manager.process_event(
                    session_id,
                    kwargs["coordination_event"],
                    {"session_state": session_state, **kwargs}
                )
                
                if coordination_result:
                    # Coordination rule triggered a phase change
                    await self.session_manager.update_session(
                        session_id,
                        {"current_phase": coordination_result}
                    )
                    session_state.current_phase = coordination_result
            
            # Execute the current phase with preprocessing insights
            result = await self._execute_phase(session_state, **kwargs)
            
            # Process coordination event for agent completion
            if self.coordination_manager and result.get("outcome") == "success":
                coordination_result = await self.coordination_manager.process_event(
                    session_id,
                    CoordinationEvent.AGENT_COMPLETE,
                    {"session_state": session_state, **result}
                )
                
                if coordination_result and coordination_result != result.get("next_phase"):
                    # Coordination rules override the normal flow
                    result["next_phase"] = coordination_result
                    result["coordination_override"] = True
            
            # Add completion event
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            await self._add_timeline_event(
                session_id,
                "SYSTEM", 
                "ORCHESTRATION_COMPLETED",
                {
                    "next_phase": result.get("next_phase"),
                    "duration_ms": duration_ms,
                    "actions_taken": result.get("actions_taken", []),
                    "coordination_override": result.get("coordination_override", False)
                },
                duration_ms
            )
            
            # Check if workflow is complete
            if result.get("next_phase") in [AgentPhase.COMPLETE, AgentPhase.ESCALATE]:
                if self.coordination_manager:
                    success = result.get("next_phase") == AgentPhase.COMPLETE
                    await self.coordination_manager.complete_session(session_id, success)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Orchestration error: {str(e)}")
            
            # Process error event in coordination
            if self.coordination_manager:
                await self.coordination_manager.process_event(
                    session_id,
                    CoordinationEvent.AGENT_ERROR,
                    {"session_state": session_state, "error": str(e)}
                )
            
            return await self.handle_error(e, session_state)
    
    async def _execute_phase(self, session_state: SessionState, **kwargs) -> Dict[str, Any]:
        """Execute the current phase of the workflow."""
        current_phase = session_state.current_phase
        self.logger.info(f"Executing phase: {current_phase}")
        
        # Check if we have a registered agent for this phase
        if current_phase not in self.agents:
            return await self._handle_missing_agent(session_state, current_phase)
        
        agent = self.agents[current_phase]
        
        # Validate agent input
        if not await agent.validate_input(session_state, **kwargs):
            return await self._handle_invalid_input(session_state, current_phase)
        
        # Execute the agent
        try:
            agent_result = await agent.execute(session_state, **kwargs)
            
            # Process the result and determine next actions
            return await self._process_agent_result(
                session_state, current_phase, agent_result, **kwargs
            )
            
        except Exception as e:
            self.logger.error(f"Agent execution error in {current_phase}: {str(e)}")
            return await self._handle_agent_error(session_state, current_phase, e)
    
    async def _process_agent_result(
        self, 
        session_state: SessionState, 
        phase: AgentPhase,
        agent_result: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Process the result from an agent and determine next actions."""
        
        # Update session state with agent results
        await self._update_session_with_agent_result(session_state, phase, agent_result)
        
        # Determine execution outcome
        outcome = self._determine_execution_outcome(agent_result)
        
        # Get transition rules for this phase
        transitions = self.state_transitions.get(phase, {})
        transition_handler = transitions.get(outcome, self._handle_unknown_outcome)
        
        # Execute transition
        next_phase = await transition_handler(session_state, agent_result, **kwargs)
        
        # Prepare response
        response = {
            "session_id": session_state.session_id,
            "current_phase": session_state.current_phase,
            "next_phase": next_phase,
            "outcome": outcome,
            "agent_result": agent_result,
            "actions_taken": agent_result.get("actions_taken", []),
            "requires_user_input": self._requires_user_input(next_phase, agent_result),
            "messages": self._extract_response_messages(agent_result)
        }
        
        # Update session phase if it's changing
        if next_phase != session_state.current_phase:
            await self.session_manager.update_session(
                session_state.session_id,
                {"current_phase": next_phase, "retry_count": 0}
            )
            response["phase_changed"] = True
        
        return response
    
    async def _update_session_with_agent_result(
        self,
        session_state: SessionState,
        phase: AgentPhase,
        agent_result: Dict[str, Any]
    ):
        """Update session state with the results from an agent."""
        update_data = {}
        
        if phase == AgentPhase.CLASSIFY:
            classification_data = agent_result.get("classification", {})
            if classification_data:
                update_data["classification"] = ClassificationResult(**classification_data)
        
        elif phase == AgentPhase.RESOLUTION_LOOP:
            resolution_data = agent_result.get("resolution", {})
            if resolution_data:
                # Store resolution loop results in a custom field
                update_data["resolution_result"] = resolution_data
        
        elif phase == AgentPhase.VALIDATE:
            validation_data = agent_result.get("validation", {})
            if validation_data:
                update_data["validation"] = ValidationResult(**validation_data)
        
        elif phase == AgentPhase.FIX:
            fix_data = agent_result.get("fix", {})
            if fix_data:
                update_data["fix"] = FixResult(**fix_data)
        
        # Update session if we have changes
        if update_data:
            update_data["updated_at"] = datetime.now()
            await self.session_manager.update_session(
                session_state.session_id,
                update_data
            )
    
    def _determine_execution_outcome(self, agent_result: Dict[str, Any]) -> str:
        """Determine if the agent execution was successful, failed, or needs retry."""
        if agent_result.get("error"):
            return "failure"
        
        if agent_result.get("success", False):
            return "success"
        
        # Check for explicit outcome
        outcome = agent_result.get("outcome", "failure")
        return outcome
    
    async def _determine_next_after_classification(
        self,
        session_state: SessionState,
        agent_result: Dict[str, Any],
        **kwargs
    ) -> AgentPhase:
        """
        Determine next phase after classification for hierarchical resolution architecture.
        
        Updated logic:
        - If classification finds a general issue → ResolutionLoop agent (handles detailed children)
        - If classification finds a detailed issue → ResolutionLoop agent (single issue resolution)
        - High confidence detailed issue without diagnostic questions → Validation (optional)
        - Low confidence → Escalate
        """
        classification = session_state.classification
        
        if not classification:
            self.logger.warning("No classification result found")
            return AgentPhase.ESCALATE
        
        # Route based on issue type and confidence
        if classification.confidence >= 0.6:
            if classification.issue_type in ["general", "detailed"]:
                # Route to resolution loop for hierarchical processing
                self.logger.info(f"Classification: {classification.issue_type} issue (confidence: {classification.confidence:.2f}) → ResolutionLoop agent")
                return AgentPhase.RESOLUTION_LOOP
            else:
                # Unknown issue type, try validation
                self.logger.warning(f"Unknown issue type: {classification.issue_type} → Validation")
                return AgentPhase.VALIDATE
        else:
            # Too low confidence, escalate
            self.logger.warning(f"Classification confidence too low: {classification.confidence:.2f} → Escalate")
            return AgentPhase.ESCALATE
    
    async def _determine_next_after_resolution_loop(
        self,
        session_state: SessionState,
        agent_result: Dict[str, Any],
        **kwargs
    ) -> AgentPhase:
        """
        Determine next phase after ResolutionLoop agent.
        
        The ResolutionLoop agent handles hierarchical issue resolution:
        - If fully resolved → COMPLETE
        - If partially resolved but needs more work → CONTINUE (stay in loop)
        - If failed with specific error → ESCALATE
        """
        resolution_status = agent_result.get('resolution_status', ResolutionStatus.FAILED)
        fully_resolved = agent_result.get('fully_resolved', False)
        error_details = agent_result.get('error_details')
        retry_count = agent_result.get('retry_count', 0)
        
        if fully_resolved:
            # All issues resolved successfully
            self.logger.info("ResolutionLoop: All issues resolved → COMPLETE")
            return AgentPhase.COMPLETE
        
        elif resolution_status == ResolutionStatus.PARTIAL:
            # Partial resolution, but user may want to continue
            self.logger.info("ResolutionLoop: Partial resolution → Continue loop")
            # Stay in resolution loop for user to decide on next steps
            return AgentPhase.RESOLUTION_LOOP
        
        elif resolution_status == ResolutionStatus.FAILED and error_details:
            # Check if we should retry based on error type
            if retry_count < self.max_retries[AgentPhase.RESOLUTION_LOOP]:
                self.logger.warning(f"ResolutionLoop: Failed but retryable ({error_details}) → Retry")
                return AgentPhase.RESOLUTION_LOOP
            else:
                self.logger.error("ResolutionLoop: Max retries exceeded → ESCALATE")
                return AgentPhase.ESCALATE
        
        elif resolution_status == ResolutionStatus.USER_STOPPED:
            # User decided to stop the resolution process
            self.logger.info("ResolutionLoop: User stopped resolution → COMPLETE")
            return AgentPhase.COMPLETE
        
        else:
            # Unknown or failed status
            self.logger.warning(f"ResolutionLoop: Unknown status {resolution_status} → ESCALATE")
            return AgentPhase.ESCALATE
    
    async def _handle_resolution_loop_failure(
        self,
        session_state: SessionState,
        agent_result: Dict[str, Any],
        **kwargs
    ) -> AgentPhase:
        """Handle ResolutionLoop agent failure with escalation or retry."""
        error_type = agent_result.get('error_type', 'unknown')
        error_details = agent_result.get('error_details', 'No details provided')
        retry_count = agent_result.get('retry_count', 0)
        
        self.logger.error(f"ResolutionLoop agent failed: {error_type} - {error_details} (retry {retry_count})")
        
        if retry_count >= self.max_retries[AgentPhase.RESOLUTION_LOOP]:
            self.logger.error("ResolutionLoop agent max retries exceeded → ESCALATE")
            return AgentPhase.ESCALATE
        
        # Try again with ResolutionLoop agent
        return AgentPhase.RESOLUTION_LOOP
    
    async def _determine_next_after_validation(
        self,
        session_state: SessionState,
        agent_result: Dict[str, Any],
        **kwargs
    ) -> AgentPhase:
        """Determine next phase after validation."""
        validation = session_state.validation
        
        if not validation:
            return AgentPhase.ESCALATE
        
        if validation.validation_result == "CONFIRMED" and validation.root_cause_confirmed:
            return AgentPhase.FIX
        elif validation.validation_result == "DIFFERENT_ISSUE":
            return AgentPhase.CLASSIFY
        elif validation.validation_result == "NOT_FOUND":
            return AgentPhase.ESCALATE
        else:
            # UNCERTAIN - might need more info
            return AgentPhase.REQUIRED_INFO
    
    async def _handle_classification_failure(
        self,
        session_state: SessionState,
        agent_result: Dict[str, Any],
        **kwargs
    ) -> AgentPhase:
        """Handle classification failure."""
        session_state.retry_count += 1
        
        if session_state.retry_count >= self.max_retries[AgentPhase.CLASSIFY]:
            await self.session_manager.update_session(
                session_state.session_id,
                {
                    "retry_count": session_state.retry_count,
                    "escalation_reason": "Classification failed after maximum retries"
                }
            )
            return AgentPhase.ESCALATE
        
        return AgentPhase.CLASSIFY
    
    async def _handle_info_failure(
        self,
        session_state: SessionState,
        agent_result: Dict[str, Any],
        **kwargs
    ) -> AgentPhase:
        """Handle required info failure."""
        session_state.retry_count += 1
        
        if session_state.retry_count >= self.max_retries[AgentPhase.REQUIRED_INFO]:
            return AgentPhase.ESCALATE
        
        return AgentPhase.REQUIRED_INFO
    
    async def _handle_validation_failure(
        self,
        session_state: SessionState,
        agent_result: Dict[str, Any],
        **kwargs
    ) -> AgentPhase:
        """Handle validation failure."""
        session_state.retry_count += 1
        
        if session_state.retry_count >= self.max_retries[AgentPhase.VALIDATE]:
            return AgentPhase.ESCALATE
        
        return AgentPhase.VALIDATE
    
    async def _handle_fix_failure(
        self,
        session_state: SessionState,
        agent_result: Dict[str, Any],
        **kwargs
    ) -> AgentPhase:
        """Handle fix failure."""
        session_state.retry_count += 1
        
        if session_state.retry_count >= self.max_retries[AgentPhase.FIX]:
            return AgentPhase.ESCALATE
        
        return AgentPhase.FIX
    
    async def _handle_missing_agent(
        self,
        session_state: SessionState,
        phase: AgentPhase
    ) -> Dict[str, Any]:
        """Handle case where no agent is registered for a phase."""
        error_msg = f"No agent registered for phase: {phase}"
        self.logger.error(error_msg)
        
        await self.session_manager.update_session(
            session_state.session_id,
            {
                "escalation_reason": error_msg,
                "current_phase": AgentPhase.ESCALATE
            }
        )
        
        return {
            "session_id": session_state.session_id,
            "current_phase": phase,
            "next_phase": AgentPhase.ESCALATE,
            "outcome": "failure",
            "error": error_msg,
            "actions_taken": [],
            "requires_user_input": False,
            "messages": [{"type": "error", "content": error_msg}]
        }
    
    async def _handle_invalid_input(
        self,
        session_state: SessionState,
        phase: AgentPhase
    ) -> Dict[str, Any]:
        """Handle invalid input for agent."""
        error_msg = f"Invalid input for phase: {phase}"
        self.logger.error(error_msg)
        
        return {
            "session_id": session_state.session_id,
            "current_phase": phase,
            "next_phase": phase,
            "outcome": "failure",
            "error": error_msg,
            "actions_taken": [],
            "requires_user_input": True,
            "messages": [{"type": "error", "content": error_msg}]
        }
    
    async def _handle_agent_error(
        self,
        session_state: SessionState,
        phase: AgentPhase,
        error: Exception
    ) -> Dict[str, Any]:
        """Handle agent execution error."""
        error_msg = f"Agent error in {phase}: {str(error)}"
        self.logger.error(error_msg)
        
        await self._add_timeline_event(
            session_state.session_id,
            "SYSTEM",
            "AGENT_ERROR",
            {"phase": phase, "error": str(error)}
        )
        
        return {
            "session_id": session_state.session_id,
            "current_phase": phase,
            "next_phase": phase,
            "outcome": "failure",
            "error": error_msg,
            "actions_taken": [],
            "requires_user_input": False,
            "messages": [{"type": "error", "content": "An error occurred while processing your request."}]
        }
    
    async def _handle_unknown_outcome(
        self,
        session_state: SessionState,
        agent_result: Dict[str, Any],
        **kwargs
    ) -> AgentPhase:
        """Handle unknown outcome from agent."""
        self.logger.warning(f"Unknown outcome: {agent_result}")
        return AgentPhase.ESCALATE
    
    def _requires_user_input(self, next_phase: AgentPhase, agent_result: Dict[str, Any]) -> bool:
        """Determine if user input is required."""
        if next_phase == AgentPhase.RESOLUTION_LOOP:
            return True  # Resolution loop always needs user confirmation
        
        if agent_result.get("requires_user_input", False):
            return True
        
        return False
    
    def _extract_response_messages(self, agent_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract response messages from agent result."""
        messages = []
        
        if "message" in agent_result:
            messages.append({"type": "agent", "content": agent_result["message"]})
        
        if "questions" in agent_result:
            for question in agent_result["questions"]:
                messages.append({"type": "question", "content": question})
        
        if "error" in agent_result:
            messages.append({"type": "error", "content": agent_result["error"]})
        
        return messages
    
    async def _add_timeline_event(
        self,
        session_id: str,
        phase: str,
        action: str,
        details: Dict[str, Any],
        duration_ms: Optional[int] = None
    ):
        """Add an event to the session timeline."""
        if self.session_manager:
            event = TimelineEvent(
                phase=phase,
                agent=self.name,
                action=action,
                details=details,
                duration_ms=duration_ms
            )
            await self.session_manager.add_timeline_event(session_id, event)
    
    async def validate_input(self, session_state: SessionState, **kwargs) -> bool:
        """Validate that the orchestrator can proceed with the current state."""
        # Check if session is valid
        if not session_state.session_id or not session_state.user_id:
            return False
        
        # Check if current phase is valid
        if session_state.current_phase not in AgentPhase:
            return False
        
        # Check if we haven't exceeded maximum retries
        max_retries_for_phase = self.max_retries.get(session_state.current_phase, 3)
        if session_state.retry_count >= max_retries_for_phase:
            return False
        
        return True
    
    async def handle_user_input(self, session_id: str, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle user input and process it through the coordination flow.
        
        Args:
            session_id: Session identifier
            user_input: User input data
            
        Returns:
            Updated session state and response
        """
        session_state = await self.session_manager.get_session(session_id)
        if not session_state:
            return {
                "error": "Session not found",
                "session_id": session_id
            }
        
        # Add user input to conversation history
        await self.session_manager.add_conversation_message(
            session_id,
            user_input,
            is_user=True
        )
        
        # Process user input event in coordination
        if self.coordination_manager:
            coordination_result = await self.coordination_manager.process_event(
                session_id,
                CoordinationEvent.USER_INPUT,
                {"session_state": session_state, "user_input": user_input}
            )
            
            if coordination_result:
                # Coordination rule triggered a phase change
                await self.session_manager.update_session(
                    session_id,
                    {"current_phase": coordination_result}
                )
                session_state.current_phase = coordination_result
        
        # Execute the orchestrator with user input
        return await self.execute(
            session_state,
            user_input=user_input,
            coordination_event=CoordinationEvent.USER_INPUT
        )
    
    async def get_coordination_metrics(self) -> Dict[str, Any]:
        """Get coordination and workflow performance metrics."""
        metrics = {}
        
        # Coordination metrics
        if self.coordination_manager:
            metrics["coordination"] = self.coordination_manager.get_metrics()
        else:
            metrics["coordination"] = {"error": "Coordination manager not initialized"}
        
        # LLM decision service metrics
        if self.llm_decision_service:
            metrics["llm_decisions"] = self.llm_decision_service.get_metrics()
        else:
            metrics["llm_decisions"] = {"error": "LLM decision service not initialized"}
        
        # Hybrid metrics
        metrics["hybrid_orchestration"] = {
            "llm_decisions_enabled": self.use_llm_decisions,
            "coordination_rules_enabled": True,  # Always enabled
            "total_tasks_processed": self.task_counter
        }
        
        return metrics
    
    async def get_enhanced_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics including LLM decision performance."""
        metrics = await self.get_coordination_metrics()
        
        # Add session state metrics
        if self.session_manager:
            try:
                # This would typically be done through session state management
                metrics["session_state"] = {
                    "active_sessions": "N/A",  # Would need active session tracking
                    "llm_decision_available": self.use_llm_decisions,
                    "llm_decision_service_available": self.llm_decision_service is not None
                }
            except Exception as e:
                self.logger.warning(f"Failed to get session metrics: {e}")
                metrics["session_state"] = {"error": str(e)}
        
        return metrics
    
    async def _preprocess_user_input(
        self,
        session_state: SessionState,
        user_input: str,
        **kwargs
    ) -> OrchestratorDecision:
        """
        Clean preprocessing using LLM decision service.
        
        Args:
            session_state: Current session state
            user_input: User's message
            **kwargs: Additional context
            
        Returns:
            OrchestratorDecision with structured decision
        """
        try:
            # Build session context
            session_context = {
                "session_id": session_state.session_id,
                "current_phase": session_state.current_phase,
                "retry_count": session_state.retry_count,
                "conversation_length": len(session_state.conversation_history),
                "session_duration": (datetime.now() - session_state.created_at).total_seconds()
            }
            
            # Use clean preprocessor
            preprocessor = await get_orchestrator_preprocessor(enable_llm_decisions=self.use_llm_decisions)
            orchestrator_decision = await preprocessor.preprocess_user_input(
                user_input=user_input,
                session_state=session_state,
                session_context=session_context
            )
            
            # Store LLM decision in session state
            session_state.recent_decisions.append(orchestrator_decision)
            if orchestrator_decision.cache_hit:
                session_state.decision_cache_hits += 1
            else:
                session_state.decision_cache_misses += 1
            
            # Update session metrics
            await self.session_manager.update_session(
                session_state.session_id,
                {
                    "recent_decisions": session_state.recent_decisions[-10:],  # Keep last 10 decisions
                    "decision_cache_hits": session_state.decision_cache_hits,
                    "decision_cache_misses": session_state.decision_cache_misses
                }
            )
            
            # Add preprocessing event to timeline
            await self._add_timeline_event(
                session_state.session_id,
                "SYSTEM",
                "PREPROCESSING_COMPLETED",
                {
                    "intent_type": orchestrator_decision.intent_type,
                    "action": orchestrator_decision.action,
                    "confidence": orchestrator_decision.confidence,
                    "llm_decision": orchestrator_decision.model_dump(),
                    "processing_time_ms": orchestrator_decision.processing_time_ms,
                    "cache_hit": orchestrator_decision.cache_hit
                }
            )
            
            self.logger.info(f"Clean preprocessing completed: {orchestrator_decision.intent_type} "
                           f"→ {orchestrator_decision.action} "
                           f"(confidence: {orchestrator_decision.confidence:.2f})")
            
            return orchestrator_decision
            
        except Exception as e:
            self.logger.error(f"Preprocessing failed: {str(e)}")
            
            # Return emergency fallback decision
            return OrchestratorDecision(
                intent_type="ambiguous",
                action="ask_clarification",
                confidence=0.1,
                reasoning=f"Preprocessing failed: {str(e)}",
                user_message="I'm having trouble processing your request. Could you please rephrase it?",
                extracted_entities={},
                conversation_flow="interrupted",
                emotional_state="neutral"
            )
    
    async def _execute_llm_decision(
        self,
        decision: OrchestratorDecision,
        session_state: SessionState,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute an LLM-based decision with coordination integration.
        
        Args:
            decision: LLM decision to execute
            session_state: Current session state
            **kwargs: Additional context
            
        Returns:
            Execution result
        """
        try:
            action = decision.action
            self.logger.info(f"Executing LLM decision: {action} (confidence: {decision.confidence:.2f})")
            
            # Execute decision using LLM decision engine patterns
            if action == "create_new_task":
                return await self._llm_create_new_task(decision, session_state, **kwargs)
            
            elif action == "forward_to_current_agent":
                return await self._llm_forward_to_current_agent(decision, session_state, **kwargs)
            
            elif action == "ask_task_switch_confirmation":
                return await self._llm_ask_task_switch_confirmation(decision, session_state, **kwargs)
            
            elif action == "auto_switch_task":
                return await self._llm_auto_switch_task(decision, session_state, **kwargs)
            
            elif action == "cancel_task":
                return await self._llm_cancel_task(decision, session_state, **kwargs)
            
            elif action == "restart_task":
                return await self._llm_restart_task(decision, session_state, **kwargs)
            
            elif action == "ask_clarification":
                return await self._llm_ask_clarification(decision, session_state, **kwargs)
            
            elif action == "escalate":
                return await self._llm_escalate(decision, session_state, **kwargs)
            
            else:
                raise ValueError(f"Unknown LLM decision action: {action}")
                
        except Exception as e:
            self.logger.error(f"LLM decision execution failed: {str(e)}")
            # Let the error propagate as per user request - no fallback decisions
            raise
    
    async def _llm_create_new_task(
        self,
        decision: OrchestratorDecision,
        session_state: SessionState,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new task based on LLM decision."""
        
        # Create task object
        task_type = TaskType.ERROR_RESOLUTION
        if decision.new_task_type == "feature_usage":
            task_type = TaskType.FEATURE_USAGE
        elif decision.new_task_type == "general_inquiry":
            task_type = TaskType.GENERAL_INQUIRY
        
        new_task = Task(
            task_id=f"TASK_{self._generate_task_id()}",
            task_type=task_type,
            status=TaskStatus.IN_PROGRESS,
            current_phase=SessionPhase.CLASSIFY if task_type == TaskType.ERROR_RESOLUTION else SessionPhase.REQUIRED_INFO,
            current_agent=decision.target_agent or self._get_initial_agent(task_type),
            last_user_message=kwargs.get("user_input", {}).get("message", ""),
            priority=decision.priority,
            decisions=[decision],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Update session state with new task
        if session_state.active_task:
            # Pause current task and move to pending
            session_state.active_task.status = TaskStatus.PAUSED
            session_state.pending_tasks.append(session_state.active_task)
        
        session_state.active_task = new_task
        
        # Add timeline event
        await self._add_timeline_event(
            session_state.session_id,
            "LLM_ORCHESTRATOR",
            "TASK_CREATED",
            {
                "task_id": new_task.task_id,
                "task_type": new_task.task_type.value,
                "agent": new_task.current_agent,
                "decision_confidence": decision.confidence
            }
        )
        
        # Forward to agent
        return await self._forward_to_agent(new_task, session_state, **kwargs)
    
    async def _llm_forward_to_current_agent(
        self,
        decision: OrchestratorDecision,
        session_state: SessionState,
        **kwargs
    ) -> Dict[str, Any]:
        """Forward to current agent as per LLM decision."""
        
        if not session_state.active_task:
            raise ValueError("No active task to forward to")
        
        # Update active task with new decision
        session_state.active_task.decisions.append(decision)
        session_state.active_task.updated_at = datetime.now()
        
        # Add timeline event
        await self._add_timeline_event(
            session_state.session_id,
            "LLM_ORCHESTRATOR",
            "FORWARD_TO_AGENT",
            {
                "task_id": session_state.active_task.task_id,
                "agent": session_state.active_task.current_agent,
                "decision_confidence": decision.confidence
            }
        )
        
        # Forward to agent
        return await self._forward_to_agent(session_state.active_task, session_state, **kwargs)
    
    async def _llm_ask_task_switch_confirmation(
        self,
        decision: OrchestratorDecision,
        session_state: SessionState,
        **kwargs
    ) -> Dict[str, Any]:
        """Ask user for task switch confirmation."""
        
        if session_state.active_task:
            session_state.active_task.current_phase = SessionPhase.WAIT_USER_SELECT
            session_state.active_task.waiting_for = "task_switch_decision"
            session_state.active_task.decisions.append(decision)
        
        return {
            "session_id": session_state.session_id,
            "current_phase": session_state.current_phase,
            "next_phase": SessionPhase.WAIT_USER_SELECT,
            "outcome": "awaiting_user_decision",
            "agent_result": {},
            "actions_taken": ["ask_task_switch_confirmation"],
            "requires_user_input": True,
            "messages": [{
                "type": "question",
                "content": decision.user_message or "You have multiple requests. Please choose which to continue with."
            }],
            "user_options": decision.user_options or ["1", "2", "3"],
            "orchestrator_decision": decision.model_dump()
        }
    
    async def _llm_auto_switch_task(
        self,
        decision: OrchestratorDecision,
        session_state: SessionState,
        **kwargs
    ) -> Dict[str, Any]:
        """Automatically switch tasks based on LLM decision."""
        
        # Pause current task if exists
        if session_state.active_task:
            session_state.active_task.status = TaskStatus.PAUSED
            session_state.active_task.decisions.append(decision)
            session_state.pending_tasks.append(session_state.active_task)
        
        # Create new task
        task_type = TaskType.ERROR_RESOLUTION
        if decision.new_task_type == "feature_usage":
            task_type = TaskType.FEATURE_USAGE
        elif decision.new_task_type == "general_inquiry":
            task_type = TaskType.GENERAL_INQUIRY
        
        new_task = Task(
            task_id=f"TASK_{self._generate_task_id()}",
            task_type=task_type,
            status=TaskStatus.IN_PROGRESS,
            current_phase=SessionPhase.CLASSIFY if task_type == TaskType.ERROR_RESOLUTION else SessionPhase.REQUIRED_INFO,
            current_agent=decision.target_agent or self._get_initial_agent(task_type),
            last_user_message=kwargs.get("user_input", {}).get("message", ""),
            priority=decision.priority,
            decisions=[decision],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        session_state.active_task = new_task
        
        # Add timeline event
        await self._add_timeline_event(
            session_state.session_id,
            "LLM_ORCHESTRATOR",
            "AUTO_TASK_SWITCH",
            {
                "new_task_id": new_task.task_id,
                "paused_tasks": len(session_state.pending_tasks),
                "decision_confidence": decision.confidence
            }
        )
        
        # Forward to agent
        result = await self._forward_to_agent(new_task, session_state, **kwargs)
        
        # Add notification
        if decision.user_message:
            result["notification"] = decision.user_message
        
        return result
    
    async def _llm_cancel_task(
        self,
        decision: OrchestratorDecision,
        session_state: SessionState,
        **kwargs
    ) -> Dict[str, Any]:
        """Cancel current task as per LLM decision."""
        
        if session_state.active_task:
            session_state.active_task.status = TaskStatus.CANCELLED
            session_state.active_task.decisions.append(decision)
            session_state.completed_tasks.append(session_state.active_task)
            session_state.active_task = None
        
        # Add timeline event
        await self._add_timeline_event(
            session_state.session_id,
            "LLM_ORCHESTRATOR",
            "TASK_CANCELLED",
            {"decision_confidence": decision.confidence}
        )
        
        return {
            "session_id": session_state.session_id,
            "current_phase": AgentPhase.COMPLETE,
            "next_phase": AgentPhase.IDLE,
            "outcome": "cancelled",
            "agent_result": {},
            "actions_taken": ["cancel_task"],
            "requires_user_input": False,
            "messages": [{
                "type": "info",
                "content": decision.user_message or "Request has been cancelled."
            }],
            "orchestrator_decision": decision.model_dump()
        }
    
    async def _llm_restart_task(
        self,
        decision: OrchestratorDecision,
        session_state: SessionState,
        **kwargs
    ) -> Dict[str, Any]:
        """Restart current task as per LLM decision."""
        
        if session_state.active_task:
            # Reset task to initial phase
            session_state.active_task.current_phase = SessionPhase.CLASSIFY
            session_state.active_task.current_agent = "classifier_agent"
            session_state.active_task.status = TaskStatus.IN_PROGRESS
            session_state.active_task.decisions.append(decision)
            session_state.active_task.updated_at = datetime.now()
            
            # Clear previous results
            session_state.active_task.classification = None
            session_state.active_task.required_info = None
            session_state.active_task.validation = None
            session_state.active_task.fix = None
            
            # Add timeline event
            await self._add_timeline_event(
                session_state.session_id,
                "LLM_ORCHESTRATOR",
                "TASK_RESTARTED",
                {
                    "task_id": session_state.active_task.task_id,
                    "decision_confidence": decision.confidence
                }
            )
            
            # Forward to classifier
            return await self._forward_to_agent(session_state.active_task, session_state, **kwargs)
        
        return {
            "session_id": session_state.session_id,
            "current_phase": session_state.current_phase,
            "next_phase": session_state.current_phase,
            "outcome": "no_active_task",
            "agent_result": {},
            "actions_taken": [],
            "requires_user_input": False,
            "messages": [{
                "type": "info",
                "content": "No active task to restart."
            }]
        }
    
    async def _llm_ask_clarification(
        self,
        decision: OrchestratorDecision,
        session_state: SessionState,
        **kwargs
    ) -> Dict[str, Any]:
        """Ask for clarification as per LLM decision."""
        
        if session_state.active_task:
            session_state.active_task.current_phase = SessionPhase.WAIT_USER_CLARIFY
            session_state.active_task.waiting_for = "clarification"
            session_state.active_task.decisions.append(decision)
        
        return {
            "session_id": session_state.session_id,
            "current_phase": SessionPhase.WAIT_USER_CLARIFY,
            "next_phase": SessionPhase.WAIT_USER_CLARIFY,
            "outcome": "awaiting_clarification",
            "agent_result": {},
            "actions_taken": ["ask_clarification"],
            "requires_user_input": True,
            "messages": [{
                "type": "question",
                "content": decision.user_message or "I need more information to help you properly. Could you please provide more details?"
            }],
            "orchestrator_decision": decision.model_dump()
        }
    
    async def _llm_escalate(
        self,
        decision: OrchestratorDecision,
        session_state: SessionState,
        **kwargs
    ) -> Dict[str, Any]:
        """Escalate to human as per LLM decision."""
        
        if session_state.active_task:
            session_state.active_task.status = TaskStatus.FAILED
            session_state.active_task.decisions.append(decision)
            session_state.completed_tasks.append(session_state.active_task)
            session_state.active_task = None
        
        # Add timeline event
        await self._add_timeline_event(
            session_state.session_id,
            "LLM_ORCHESTRATOR",
            "ESCALATED",
            {
                "reason": decision.reasoning,
                "confidence": decision.confidence
            }
        )
        
        return {
            "session_id": session_state.session_id,
            "current_phase": AgentPhase.ESCALATE,
            "next_phase": AgentPhase.ESCALATE,
            "outcome": "escalated",
            "agent_result": {},
            "actions_taken": ["escalate"],
            "requires_user_input": False,
            "messages": [{
                "type": "info",
                "content": "Your request has been escalated to a human specialist for assistance."
            }],
            "orchestrator_decision": decision.model_dump()
        }
    
    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        import uuid
        self.task_counter += 1
        return str(uuid.uuid4())[:8]
    
    def _get_initial_agent(self, task_type: TaskType) -> str:
        """Determine initial agent based on task type."""
        if task_type == TaskType.ERROR_RESOLUTION:
            return "classifier_agent"
        elif task_type == TaskType.FEATURE_USAGE:
            return "knowledge_agent"
        elif task_type == TaskType.GENERAL_INQUIRY:
            return "knowledge_agent"
        else:
            return "classifier_agent"  # Default
    
    async def _forward_to_agent(
        self,
        task: Task,
        session_state: SessionState,
        **kwargs
    ) -> Dict[str, Any]:
        """Forward task to appropriate agent."""
        
        if task.current_agent not in self.agents:
            raise ValueError(f"Agent not registered: {task.current_agent}")
        
        agent = self.agents[task.current_agent]
        
        # Execute agent
        agent_result = await agent.execute(session_state, **kwargs)
        
        # Update session phase based on agent result
        if hasattr(session_state, 'current_phase'):
            # Convert AgentPhase to SessionPhase for active task
            if hasattr(SessionPhase, session_state.current_phase.value):
                task.current_phase = SessionPhase[session_state.current_phase.value]
        
        return {
            "session_id": session_state.session_id,
            "current_phase": session_state.current_phase,
            "next_phase": agent_result.get("next_phase", session_state.current_phase),
            "outcome": agent_result.get("outcome", "success"),
            "agent_result": agent_result,
            "actions_taken": agent_result.get("actions_taken", []),
            "requires_user_input": agent_result.get("requires_user_input", False),
            "messages": agent_result.get("messages", [])
        }
    
    async def handle_error(self, error: Exception, session_state: SessionState) -> Dict[str, Any]:
        """Handle errors that occur during orchestration."""
        error_msg = f"Orchestrator error: {str(error)}"
        self.logger.error(error_msg)
        
        # Add error to timeline
        await self._add_timeline_event(
            session_state.session_id,
            "SYSTEM",
            "ORCHESTRATOR_ERROR",
            {"error": str(error), "phase": session_state.current_phase}
        )
        
        # Escalate on orchestrator errors
        await self.session_manager.update_session(
            session_state.session_id,
            {
                "current_phase": AgentPhase.ESCALATE,
                "escalation_reason": error_msg
            }
        )
        
        return {
            "session_id": session_state.session_id,
            "current_phase": session_state.current_phase,
            "next_phase": AgentPhase.ESCALATE,
            "outcome": "failure",
            "error": error_msg,
            "actions_taken": [],
            "requires_user_input": False,
            "messages": [{"type": "error", "content": "A system error occurred. Your request has been escalated."}]
        }
    
    async def _handle_enhanced_routing(
        self,
        session_state: SessionState,
        preprocessing_result: Any,
        session_id: str,
        start_time: datetime
    ):
        """Handle enhanced routing for multi-turn conversations."""
        
        action = preprocessing_result.orchestrator_action.value
        intent = preprocessing_result.user_intent.value
        
        # Add enhanced routing event to timeline
        await self._add_timeline_event(
            session_id,
            "SYSTEM",
            "ENHANCED_ROUTING",
            {
                "intent": intent,
                "action": action,
                "confidence": preprocessing_result.confidence,
                "conversation_flow": preprocessing_result.context_analysis.get("conversation_flow", "unknown"),
                "intent_evolution": preprocessing_result.context_analysis.get("intent_evolution", "unknown")
            }
        )
        
        # Handle specific multi-turn scenarios
        if action in ["continue_workflow", "modify_classification"]:
            # User is providing information or updating issue
            await self._handle_follow_up_info(session_state, preprocessing_result)
            
        elif action in ["follow_up_clarification", "validate_solution"]:
            # User needs clarification or solution validation
            await self._handle_clarification_flow(session_state, preprocessing_result)
            
        elif action == "request_agent_switch":
            # User wants to switch to different approach
            await self._handle_agent_switch(session_state, preprocessing_result)
            
        elif action == "close_case":
            # User wants to end conversation
            await self._handle_case_closure(session_state, preprocessing_result)
    
    async def _handle_follow_up_info(
        self,
        session_state: SessionState,
        preprocessing_result: Any
    ):
        """Handle follow-up information from user."""
        
        # Update session with new information
        update_data = {
            "user_provided_info": True,
            "last_intent": preprocessing_result.user_intent.value,
            "extracted_entities": preprocessing_result.extracted_entities,
            "conversation_flow": "smooth"
        }
        
        await self.session_manager.update_session(
            session_state.session_id,
            update_data
        )
        
        self.logger.info(f"Follow-up info processed: {preprocessing_result.user_intent.value}")
    
    async def _handle_clarification_flow(
        self,
        session_state: SessionState,
        preprocessing_result: Any
    ):
        """Handle clarification requests from user."""
        
        # Update session to indicate clarification needed
        update_data = {
            "clarification_needed": True,
            "clarification_reason": preprocessing_result.user_intent.value,
            "conversation_flow": "interrupted"
        }
        
        await self.session_manager.update_session(
            session_state.session_id,
            update_data
        )
        
        self.logger.info(f"Clarification flow: {preprocessing_result.user_intent.value}")
    
    async def _handle_agent_switch(
        self,
        session_state: SessionState,
        preprocessing_result: Any
    ):
        """Handle request to switch to different agent approach."""
        
        # Determine which phase to switch to based on intent
        target_phase = AgentPhase.CLASSIFY  # Default fallback
        
        if preprocessing_result.user_intent.value in ["issue_report", "update_issue"]:
            target_phase = AgentPhase.CLASSIFY
        elif preprocessing_result.user_intent.value in ["help_guidance", "product_info"]:
            target_phase = AgentPhase.REQUIRED_INFO  # This could guide to documentation
        
        # Update session with agent switch
        await self.session_manager.update_session(
            session_state.session_id,
            {
                "current_phase": target_phase,
                "agent_switch_requested": True,
                "switch_reason": preprocessing_result.user_intent.value
            }
        )
        
        self.logger.info(f"Agent switch requested: {session_state.current_phase} → {target_phase}")
    
    async def _handle_case_closure(
        self,
        session_state: SessionState,
        preprocessing_result: Any
    ):
        """Handle case closure requests."""
        
        # Update session for closure
        await self.session_manager.update_session(
            session_state.session_id,
            {
                "current_phase": AgentPhase.COMPLETE,
                "closure_reason": preprocessing_result.user_intent.value,
                "user_satisfaction": preprocessing_result.context_analysis.get("emotional_state", "neutral")
            }
        )
        
        self.logger.info(f"Case closure requested: {preprocessing_result.user_intent.value}")
    
    async def _create_routing_response(
        self,
        session_state: SessionState,
        preprocessing_result: Any,
        session_id: str,
        start_time: datetime
    ) -> Dict[str, Any]:
        """Create response for enhanced routing scenarios."""
        
        # Determine if we have an immediate response or need to continue workflow
        response_messages = []
        if preprocessing_result.immediate_response:
            response_messages.append(preprocessing_result.immediate_response)
        
        # Get next phase based on routing action
        action = preprocessing_result.orchestrator_action.value
        next_phase = session_state.current_phase
        
        if action == "modify_classification":
            next_phase = AgentPhase.CLASSIFY
        elif action == "continue_workflow":
            # Continue with current phase's next logical step
            if session_state.current_phase == AgentPhase.CLASSIFY:
                next_phase = AgentPhase.REQUIRED_INFO
            elif session_state.current_phase == AgentPhase.REQUIRED_INFO:
                next_phase = AgentPhase.VALIDATE
            elif session_state.current_phase == AgentPhase.VALIDATE:
                next_phase = AgentPhase.FIX
        elif action == "close_case":
            next_phase = AgentPhase.COMPLETE
        elif action == "escalate":
            next_phase = AgentPhase.ESCALATE
        
        return {
            "session_id": session_id,
            "current_phase": session_state.current_phase,
            "next_phase": next_phase,
            "outcome": "enhanced_routing",
            "agent_result": {},
            "actions_taken": ["preprocessing_analyzed", "enhanced_routing"],
            "requires_user_input": True,
            "messages": response_messages,
            "preprocessing_result": preprocessing_result,
            "routing_action": action,
            "intent_evolution": preprocessing_result.context_analysis.get("intent_evolution", "none"),
            "conversation_flow": preprocessing_result.context_analysis.get("conversation_flow", "unknown"),
            "phase_changed": next_phase != session_state.current_phase
        }