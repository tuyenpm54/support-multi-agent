"""
Tests for the Orchestrator Agent and coordination flow.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from src.agents.orchestrator import OrchestratorAgent
from src.models.session import SessionState, AgentPhase, ClassificationResult
from src.core.state_manager import SessionManager


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager."""
    manager = Mock(spec=SessionManager)
    manager.create_session = AsyncMock(return_value="test_session_123")
    manager.get_session = AsyncMock()
    manager.update_session = AsyncMock(return_value=True)
    manager.add_timeline_event = AsyncMock()
    return manager


@pytest.fixture
def sample_session_state():
    """Create a sample session state."""
    return SessionState(
        session_id="test_session_123",
        user_id="user_456",
        current_phase=AgentPhase.CLASSIFY,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


@pytest.fixture
def orchestrator(mock_session_manager):
    """Create an orchestrator instance with mocked dependencies."""
    orchestrator = OrchestratorAgent()
    orchestrator.set_dependencies(mock_session_manager, None)
    return orchestrator


class TestOrchestratorAgent:
    """Test cases for OrchestratorAgent."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, orchestrator):
        """Test that orchestrator initializes correctly."""
        assert orchestrator.name == "Orchestrator"
        assert orchestrator.session_manager is not None
        assert orchestrator.coordination_manager is not None
        assert len(orchestrator.max_retries) == 4
    
    @pytest.mark.asyncio
    async def test_workflow_start(self, orchestrator, sample_session_state):
        """Test starting a workflow."""
        orchestrator.session_manager.get_session.return_value = sample_session_state
        
        result = await orchestrator.execute(
            sample_session_state,
            start_workflow=True
        )
        
        assert "session_id" in result
        assert result["session_id"] == "test_session_123"
        assert "current_phase" in result
        assert result["current_phase"] == AgentPhase.CLASSIFY
    
    @pytest.mark.asyncio
    async def test_agent_registration(self, orchestrator, mock_session_manager):
        """Test registering agents."""
        mock_agent = Mock()
        mock_agent.name = "TestAgent"
        mock_agent.set_dependencies = Mock()
        
        orchestrator.register_agent(AgentPhase.CLASSIFY, mock_agent)
        
        assert AgentPhase.CLASSIFY in orchestrator.agents
        assert orchestrator.agents[AgentPhase.CLASSIFY] == mock_agent
        mock_agent.set_dependencies.assert_called_once_with(mock_session_manager, None)
    
    @pytest.mark.asyncio
    async def test_handle_user_input(self, orchestrator, sample_session_state):
        """Test handling user input."""
        orchestrator.session_manager.get_session.return_value = sample_session_state
        orchestrator.session_manager.add_conversation_message = AsyncMock()
        
        user_input = {
            "message": "I can't login to my account",
            "type": "text"
        }
        
        result = await orchestrator.handle_user_input(
            sample_session_state.session_id,
            user_input
        )
        
        assert "session_id" in result
        orchestrator.session_manager.add_conversation_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_coordination_rules_setup(self, orchestrator):
        """Test that coordination rules are set up correctly."""
        assert orchestrator.coordination_manager is not None
        
        # Check that rules were added
        rules = orchestrator.coordination_manager.coordination_flow.rules
        assert len(rules) > 0  # Should have default rules + custom rules
    
    @pytest.mark.asyncio
    async def test_validate_input(self, orchestrator, sample_session_state):
        """Test input validation."""
        # Valid session should pass
        assert await orchestrator.validate_input(sample_session_state) == True
        
        # Invalid session (missing session_id) should fail
        invalid_session = SessionState(
            session_id="",
            user_id="user_456",
            current_phase=AgentPhase.CLASSIFY
        )
        assert await orchestrator.validate_input(invalid_session) == False
    
    def test_state_transitions(self, orchestrator):
        """Test state transition configuration."""
        assert AgentPhase.CLASSIFY in orchestrator.state_transitions
        assert "success" in orchestrator.state_transitions[AgentPhase.CLASSIFY]
        assert "failure" in orchestrator.state_transitions[AgentPhase.CLASSIFY]
        assert "retry" in orchestrator.state_transitions[AgentPhase.CLASSIFY]
    
    def test_max_retries_configuration(self, orchestrator):
        """Test maximum retry configuration."""
        assert orchestrator.max_retries[AgentPhase.CLASSIFY] == 3
        assert orchestrator.max_retries[AgentPhase.REQUIRED_INFO] == 2
        assert orchestrator.max_retries[AgentPhase.VALIDATE] == 3
        assert orchestrator.max_retries[AgentPhase.FIX] == 2


@pytest.mark.asyncio
async def test_full_workflow_simulation():
    """Test a simulated workflow from start to finish."""
    # Mock dependencies
    mock_session_manager = Mock(spec=SessionManager)
    mock_session_manager.create_session = AsyncMock(return_value="test_session_123")
    mock_session_manager.get_session = AsyncMock()
    mock_session_manager.update_session = AsyncMock(return_value=True)
    mock_session_manager.add_timeline_event = AsyncMock()
    mock_session_manager.add_conversation_message = AsyncMock()
    
    # Create orchestrator
    orchestrator = OrchestratorAgent()
    orchestrator.set_dependencies(mock_session_manager, None)
    
    # Create sample session state
    session_state = SessionState(
        session_id="test_session_123",
        user_id="user_456",
        current_phase=AgentPhase.CLASSIFY,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # Mock session manager to return our session state
    mock_session_manager.get_session.return_value = session_state
    
    # Test workflow start
    result = await orchestrator.execute(
        session_state,
        start_workflow=True
    )
    
    assert result["session_id"] == "test_session_123"
    assert result["current_phase"] == AgentPhase.CLASSIFY
    
    # Test user input handling
    user_input = {
        "message": "I'm having trouble with the dashboard",
        "type": "text"
    }
    
    input_result = await orchestrator.handle_user_input(
        session_state.session_id,
        user_input
    )
    
    assert "session_id" in input_result
    assert input_result["session_id"] == "test_session_123"


if __name__ == "__main__":
    pytest.main([__file__])