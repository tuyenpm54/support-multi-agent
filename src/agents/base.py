from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.models.session import SessionState, ClassificationResult, InfoValidationResult, FixResult


class BaseAgent(ABC):
    """Base class for all agents in the support system."""
    
    def __init__(self, name: str):
        self.name = name
        self.session_manager = None  # Will be injected by orchestrator
        self.tool_registry = None   # Will be injected by orchestrator
    
    def set_dependencies(self, session_manager, tool_registry):
        """Inject dependencies (session manager and tool registry)."""
        self.session_manager = session_manager
        self.tool_registry = tool_registry
    
    @abstractmethod
    async def execute(self, session_state: SessionState, **kwargs) -> Dict[str, Any]:
        """
        Execute the agent's primary function.
        
        Args:
            session_state: Current session state
            **kwargs: Additional parameters specific to the agent
            
        Returns:
            Result of the agent execution with updated state fields
        """
        pass
    
    async def validate_input(self, session_state: SessionState, **kwargs) -> bool:
        """
        Validate that the agent can execute with the current state.
        
        Args:
            session_state: Current session state
            **kwargs: Additional parameters
            
        Returns:
            True if the agent can proceed, False otherwise
        """
        return True
    
    async def handle_error(self, error: Exception, session_state: SessionState) -> Dict[str, Any]:
        """
        Handle errors that occur during agent execution.
        
        Args:
            error: The exception that occurred
            session_state: Current session state
            
        Returns:
            Error handling result with potential fallback actions
        """
        return {
            "error": str(error),
            "phase": session_state.current_phase,
            "action": "retry"
        }