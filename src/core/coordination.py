from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass
import logging
import asyncio
from datetime import datetime, timedelta

from src.models.session import SessionState, AgentPhase, TimelineEvent


class CoordinationEvent(Enum):
    """Events that can trigger coordination actions."""
    USER_INPUT = "user_input"
    AGENT_COMPLETE = "agent_complete"
    AGENT_ERROR = "agent_error"
    TIMEOUT = "timeout"
    ESCALATION = "escalation"
    MANUAL_INTERVENTION = "manual_intervention"


class WorkflowState(Enum):
    """High-level workflow states."""
    ACTIVE = "active"
    WAITING = "waiting"
    ERROR = "error"
    COMPLETED = "completed"
    ESCALATED = "escalated"


@dataclass
class CoordinationRule:
    """A rule for coordinating agent transitions."""
    trigger_event: CoordinationEvent
    source_phase: AgentPhase
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    action: Optional[Callable[[SessionState, Dict[str, Any]], Any]] = None
    target_phase: Optional[AgentPhase] = None
    priority: int = 0  # Higher priority rules are evaluated first
    timeout_seconds: Optional[int] = None


class WorkflowMetrics:
    """Metrics collection for workflow performance."""
    
    def __init__(self):
        self.phase_durations: Dict[str, List[float]] = {}
        self.transition_counts: Dict[str, int] = {}
        self.error_counts: Dict[str, int] = {}
        self.completion_times: List[float] = []
        self.escalation_count = 0
    
    def record_phase_start(self, phase: str, session_id: str):
        """Record the start of a phase for a session."""
        key = f"{phase}_{session_id}"
        self.phase_durations[key] = [datetime.now().timestamp()]
    
    def record_phase_end(self, phase: str, session_id: str):
        """Record the end of a phase for a session."""
        key = f"{phase}_{session_id}"
        if key in self.phase_durations and len(self.phase_durations[key]) == 1:
            duration = datetime.now().timestamp() - self.phase_durations[key][0]
            self.phase_durations[key].append(duration)
            
            # Also record in aggregated phase metrics
            phase_key = f"phase_{phase}"
            if phase_key not in self.phase_durations:
                self.phase_durations[phase_key] = []
            self.phase_durations[phase_key].append(duration)
    
    def record_transition(self, from_phase: str, to_phase: str):
        """Record a phase transition."""
        transition_key = f"{from_phase}_to_{to_phase}"
        self.transition_counts[transition_key] = self.transition_counts.get(transition_key, 0) + 1
    
    def record_error(self, phase: str, error_type: str):
        """Record an error occurrence."""
        error_key = f"{phase}_{error_type}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
    
    def record_completion(self, total_time: float):
        """Record workflow completion."""
        self.completion_times.append(total_time)
    
    def record_escalation(self):
        """Record workflow escalation."""
        self.escalation_count += 1


class CoordinationFlow:
    """
    Manages the coordination flow between agents with configurable rules and metrics.
    """
    
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.logger = logging.getLogger(__name__)
        self.rules: List[CoordinationRule] = []
        self.active_sessions: Dict[str, WorkflowState] = {}
        self.session_timeouts: Dict[str, datetime] = {}
        self.metrics = WorkflowMetrics()
        
        # Default coordination rules
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Set up default coordination rules."""
        
        # Rule: Auto-escalate on repeated failures
        self.add_rule(CoordinationRule(
            trigger_event=CoordinationEvent.AGENT_ERROR,
            source_phase=AgentPhase.CLASSIFY,
            condition=lambda data: data.get("retry_count", 0) >= 3,
            target_phase=AgentPhase.ESCALATE,
            priority=10
        ))
        
        # Rule: Timeout handling
        self.add_rule(CoordinationRule(
            trigger_event=CoordinationEvent.TIMEOUT,
            source_phase=AgentPhase.CLASSIFY,
            target_phase=AgentPhase.ESCALATE,
            priority=8
        ))
        
        # Rule: User input triggers required info phase
        self.add_rule(CoordinationRule(
            trigger_event=CoordinationEvent.USER_INPUT,
            source_phase=AgentPhase.CLASSIFY,
            condition=lambda data: "diagnostic_question" in data.get("classification", {}),
            target_phase=AgentPhase.REQUIRED_INFO,
            priority=5
        ))
        
        # Rule: Validation success triggers fix phase
        self.add_rule(CoordinationRule(
            trigger_event=CoordinationEvent.AGENT_COMPLETE,
            source_phase=AgentPhase.VALIDATE,
            condition=lambda data: data.get("validation", {}).get("validation_result") == "CONFIRMED",
            target_phase=AgentPhase.FIX,
            priority=7
        ))
    
    def add_rule(self, rule: CoordinationRule):
        """Add a coordination rule."""
        self.rules.append(rule)
        # Sort rules by priority (higher priority first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        self.logger.info(f"Added coordination rule: {rule.trigger_event} → {rule.target_phase}")
    
    async def process_event(
        self,
        session_id: str,
        event: CoordinationEvent,
        data: Dict[str, Any]
    ) -> Optional[AgentPhase]:
        """
        Process a coordination event and return the target phase if a rule matches.
        
        Args:
            session_id: Session identifier
            event: The coordination event
            data: Event data (session state, agent results, etc.)
            
        Returns:
            Target phase if a rule matches and triggers a transition, None otherwise
        """
        session_state = data.get("session_state")
        if not session_state:
            self.logger.error(f"No session state provided for event {event}")
            return None
        
        current_phase = session_state.current_phase
        
        self.logger.info(f"Processing event {event} for session {session_id} in phase {current_phase}")
        
        # Find matching rules
        matching_rules = [
            rule for rule in self.rules
            if (rule.trigger_event == event and 
                rule.source_phase == current_phase and
                (rule.condition is None or rule.condition(data)))
        ]
        
        if not matching_rules:
            self.logger.debug(f"No matching rules for event {event} in phase {current_phase}")
            return None
        
        # Apply highest priority rule
        rule = matching_rules[0]
        
        self.logger.info(f"Applying rule: {event} → {rule.target_phase} (priority: {rule.priority})")
        
        # Record transition
        if rule.target_phase and rule.target_phase != current_phase:
            self.metrics.record_transition(current_phase, rule.target_phase)
        
        # Execute rule action if provided
        if rule.action:
            try:
                await rule.action(session_state, data)
            except Exception as e:
                self.logger.error(f"Error executing rule action: {str(e)}")
        
        # Update workflow state
        await self._update_workflow_state(session_id, event, data)
        
        return rule.target_phase
    
    async def _update_workflow_state(
        self,
        session_id: str,
        event: CoordinationEvent,
        data: Dict[str, Any]
    ):
        """Update the workflow state for a session."""
        
        if event == CoordinationEvent.AGENT_COMPLETE:
            self.active_sessions[session_id] = WorkflowState.ACTIVE
            
        elif event == CoordinationEvent.USER_INPUT:
            self.active_sessions[session_id] = WorkflowState.WAITING
            
        elif event == CoordinationEvent.AGENT_ERROR:
            self.active_sessions[session_id] = WorkflowState.ERROR
            
        elif event == CoordinationEvent.ESCALATION:
            self.active_sessions[session_id] = WorkflowState.ESCALATED
            self.metrics.record_escalation()
        
        # Update timeout if specified
        session_state = data.get("session_state")
        if session_state:
            # Set default timeout of 30 minutes from now
            timeout = datetime.now() + timedelta(minutes=30)
            self.session_timeouts[session_id] = timeout
    
    async def check_timeouts(self):
        """Check for session timeouts and handle them."""
        now = datetime.now()
        expired_sessions = [
            session_id for session_id, timeout in self.session_timeouts.items()
            if timeout < now
        ]
        
        for session_id in expired_sessions:
            self.logger.warning(f"Session {session_id} timed out")
            
            # Get session state
            session_state = await self.session_manager.get_session(session_id)
            if session_state:
                # Process timeout event
                await self.process_event(
                    session_id,
                    CoordinationEvent.TIMEOUT,
                    {"session_state": session_state}
                )
            
            # Remove from active sessions
            self.active_sessions.pop(session_id, None)
            self.session_timeouts.pop(session_id, None)
    
    async def start_session_workflow(self, session_id: str):
        """Start workflow tracking for a new session."""
        self.active_sessions[session_id] = WorkflowState.ACTIVE
        self.metrics.record_phase_start("workflow", session_id)
        
        # Add timeline event
        await self.session_manager.add_timeline_event(
            session_id,
            TimelineEvent(
                phase="SYSTEM",
                action="WORKFLOW_STARTED",
                details={"timestamp": datetime.now().isoformat()}
            )
        )
    
    async def complete_session_workflow(self, session_id: str, success: bool = True):
        """Complete workflow tracking for a session."""
        self.metrics.record_phase_end("workflow", session_id)
        
        if session_id in self.active_sessions:
            self.active_sessions[session_id] = WorkflowState.COMPLETED if success else WorkflowState.ESCALATED
        
        # Remove from timeouts
        self.session_timeouts.pop(session_id, None)
        
        # Add timeline event
        await self.session_manager.add_timeline_event(
            session_id,
            TimelineEvent(
                phase="SYSTEM",
                action="WORKFLOW_COMPLETED",
                details={"success": success, "timestamp": datetime.now().isoformat()}
            )
        )
    
    def get_session_state(self, session_id: str) -> Optional[WorkflowState]:
        """Get the current workflow state for a session."""
        return self.active_sessions.get(session_id)
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        return [
            session_id for session_id, state in self.active_sessions.items()
            if state in [WorkflowState.ACTIVE, WorkflowState.WAITING]
        ]
    
    def get_workflow_metrics(self) -> Dict[str, Any]:
        """Get workflow performance metrics."""
        metrics = {}
        
        # Calculate average phase durations
        phase_averages = {}
        for key, durations in self.metrics.phase_durations.items():
            if key.startswith("phase_") and len(durations) > 0:
                phase_name = key[6:]  # Remove "phase_" prefix
                phase_averages[phase_name] = sum(durations) / len(durations)
        
        metrics["average_phase_durations"] = phase_averages
        
        # Most common transitions
        if self.metrics.transition_counts:
            metrics["top_transitions"] = sorted(
                self.metrics.transition_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        
        # Error rates by phase
        error_rates = {}
        for key, count in self.metrics.error_counts.items():
            if "_" in key:
                phase = key.split("_")[0]
                error_rates[phase] = error_rates.get(phase, 0) + count
        metrics["error_rates"] = error_rates
        
        # Completion metrics
        if self.metrics.completion_times:
            metrics["average_completion_time"] = sum(self.metrics.completion_times) / len(self.metrics.completion_times)
            metrics["total_completions"] = len(self.metrics.completion_times)
        
        # Escalation rate
        metrics["escalation_count"] = self.metrics.escalation_count
        
        # Active sessions
        metrics["active_sessions"] = len(self.get_active_sessions())
        
        return metrics
    
    async def cleanup_expired_sessions(self):
        """Clean up data for expired sessions."""
        # Remove old workflow states (older than 24 hours)
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        expired_sessions = []
        for session_id, timeout in self.session_timeouts.items():
            if timeout < cutoff_time:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.active_sessions.pop(session_id, None)
            self.session_timeouts.pop(session_id, None)
            
            # Clean up metrics data for this session
            keys_to_remove = [key for key in self.metrics.phase_durations.keys() if session_id in key]
            for key in keys_to_remove:
                del self.metrics.phase_durations[key]
        
        if expired_sessions:
            self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")


class CoordinationManager:
    """
    High-level manager for coordination flows with session lifecycle management.
    """
    
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.coordination_flow = CoordinationFlow(session_manager)
        self.logger = logging.getLogger(__name__)
        
        # Start timeout checker task
        self.timeout_task = asyncio.create_task(self._timeout_checker())
    
    async def _timeout_checker(self):
        """Periodically check for session timeouts."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self.coordination_flow.check_timeouts()
                await self.coordination_flow.cleanup_expired_sessions()
            except Exception as e:
                self.logger.error(f"Error in timeout checker: {str(e)}")
    
    async def start_session(self, session_id: str):
        """Start coordination for a new session."""
        await self.coordination_flow.start_session_workflow(session_id)
        self.logger.info(f"Started coordination for session {session_id}")
    
    async def process_event(
        self,
        session_id: str,
        event: CoordinationEvent,
        data: Dict[str, Any]
    ) -> Optional[AgentPhase]:
        """Process a coordination event."""
        return await self.coordination_flow.process_event(session_id, event, data)
    
    async def complete_session(self, session_id: str, success: bool = True):
        """Complete coordination for a session."""
        await self.coordination_flow.complete_session_workflow(session_id, success)
        self.logger.info(f"Completed coordination for session {session_id}, success: {success}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get coordination metrics."""
        return self.coordination_flow.get_workflow_metrics()
    
    def add_coordination_rule(self, rule: CoordinationRule):
        """Add a new coordination rule."""
        self.coordination_flow.add_rule(rule)
    
    async def shutdown(self):
        """Shutdown the coordination manager."""
        if self.timeout_task:
            self.timeout_task.cancel()
            try:
                await self.timeout_task
            except asyncio.CancelledError:
                pass