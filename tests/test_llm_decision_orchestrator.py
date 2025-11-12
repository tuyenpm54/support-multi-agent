"""
Tests for Enhanced LLM Decision Orchestrator

Tests the integration of LLM-based decision making with the existing
orchestrator system, including hybrid coordination, caching, and fallback mechanisms.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from src.agents.orchestrator import OrchestratorAgent
from src.models.session import (
    SessionState, AgentPhase, OrchestratorDecision, Task, TaskType, 
    SessionPhase, TaskStatus, ClassificationResult
)
from src.core.state_manager import SessionManager
from src.services.llm_decision import LLMDecisionService
from src.core.orchestrator_preprocessor import get_orchestrator_preprocessor


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager."""
    manager = Mock(spec=SessionManager)
    manager.create_session = AsyncMock(return_value="test_session_123")
    manager.get_session = AsyncMock()
    manager.update_session = AsyncMock(return_value=True)
    manager.add_timeline_event = AsyncMock()
    manager.get_conversation_history = AsyncMock(return_value=[])
    manager.add_conversation_message = AsyncMock()
    return manager


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = Mock()
    client.generate = AsyncMock()
    return client


@pytest.fixture
def enhanced_session_state():
    """Create an enhanced session state with LLM decision support."""
    return SessionState(
        session_id="test_session_123",
        user_id="user_456",
        current_phase=AgentPhase.CLASSIFY,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        # LLM decision fields
        active_task=None,
        pending_tasks=[],
        completed_tasks=[],
        recent_decisions=[],
        decision_cache_hits=0,
        decision_cache_misses=0,
        llm_decisions_enabled=True,
        coordination_rules_enabled=True,
        decision_confidence_threshold=0.7
    )


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    return Task(
        task_id="TASK_12345678",
        task_type=TaskType.ERROR_RESOLUTION,
        status=TaskStatus.IN_PROGRESS,
        current_phase=SessionPhase.CLASSIFY,
        current_agent="classifier_agent",
        last_user_message="Món không hiển thị",
        priority="medium",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        decisions=[]
    )


@pytest.fixture
def orchestrator_with_llm(mock_session_manager):
    """Create an orchestrator with LLM decision support."""
    orchestrator = OrchestratorAgent(use_llm_decisions=True)
    orchestrator.set_dependencies(mock_session_manager, None)
    return orchestrator


@pytest.fixture
def orchestrator_without_llm(mock_session_manager):
    """Create an orchestrator without LLM decision support."""
    orchestrator = OrchestratorAgent(use_llm_decisions=False)
    orchestrator.set_dependencies(mock_session_manager, None)
    return orchestrator


@pytest.fixture
def sample_llm_decision():
    """Create a sample LLM decision."""
    return OrchestratorDecision(
        intent_type="new_request",
        action="create_new_task",
        new_task_type="error_resolution",
        target_agent="classifier_agent",
        confidence=0.95,
        reasoning="User reports error. No active task. Create new error resolution task.",
        user_message=None,
        extracted_entities={"issue_type": "display_issue"},
        conversation_flow="new_topic"
    )


class TestLLMDecisionService:
    """Test cases for LLM Decision Service."""
    
    @pytest.mark.asyncio
    async def test_llm_decision_service_initialization(self, mock_llm_client):
        """Test LLM decision service initialization."""
        service = LLMDecisionService(mock_llm_client)
        
        assert service.llm_client == mock_llm_client
        assert service.current_prompt_version == "v1.2"
        assert len(service.system_prompts) == 3
        assert service.metrics["total_decisions"] == 0
    
    @pytest.mark.asyncio
    async def test_make_decision_cache_hit(self, mock_llm_client):
        """Test decision caching functionality."""
        service = LLMDecisionService(mock_llm_client)
        
        # Create a session state
        session_state = SessionState(
            session_id="test",
            user_id="user",
            current_phase=AgentPhase.CLASSIFY
        )
        
        # First call - should hit LLM
        mock_llm_client.generate.return_value = '''{
            "intent_type": "new_request",
            "action": "create_new_task",
            "new_task_type": "error_resolution",
            "confidence": 0.9,
            "reasoning": "User reports error"
        }'''
        
        decision1 = await service.make_decision("Test message", session_state)
        assert decision1.intent_type == "new_request"
        assert service.metrics["cache_misses"] == 1
        
        # Second call with same context - should hit cache
        decision2 = await service.make_decision("Test message", session_state)
        assert decision2.intent_type == "new_request"
        assert decision2.cache_hit == True
        assert service.metrics["cache_hits"] == 1
    
    @pytest.mark.asyncio
    async def test_fallback_decision(self, mock_llm_client):
        """Test fallback decision when LLM fails."""
        service = LLMDecisionService(mock_llm_client)
        
        # Configure LLM to fail
        mock_llm_client.generate.side_effect = Exception("LLM API error")
        
        session_state = SessionState(
            session_id="test",
            user_id="user",
            current_phase=AgentPhase.CLASSIFY
        )
        
        decision = await service.make_decision("Test message", session_state)
        
        # Should return fallback decision
        assert decision.intent_type == "ambiguous"
        assert decision.action == "ask_clarification"
        assert decision.confidence == 0.4
        assert service.metrics["fallback_used"] == 1
    
    @pytest.mark.asyncio
    async def test_decision_validation(self, mock_llm_client):
        """Test decision validation and correction."""
        service = LLMDecisionService(mock_llm_client)
        
        # Create invalid decision (forward with no active task)
        mock_llm_client.generate.return_value = '''{
            "intent_type": "continuation",
            "action": "forward_to_current_agent",
            "confidence": 0.8,
            "reasoning": "Invalid decision"
        }'''
        
        session_state = SessionState(
            session_id="test",
            user_id="user",
            current_phase=AgentPhase.CLASSIFY,
            active_task=None
        )
        
        decision = await service.make_decision("Test message", session_state)
        
        # Decision should be corrected
        assert decision.action == "ask_clarification"
        assert decision.confidence == 0.5
        assert "corrected" in decision.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_prompt_versioning(self, mock_llm_client):
        """Test prompt versioning system."""
        service = LLMDecisionService(mock_llm_client)
        
        # Test switching to different prompt version
        service.set_prompt_version("v1.0")
        assert service.current_prompt_version == "v1.0"
        
        # Test invalid version
        with pytest.raises(ValueError):
            service.set_prompt_version("invalid_version")
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, mock_llm_client):
        """Test metrics collection and reporting."""
        service = LLMDecisionService(mock_llm_client)
        
        session_state = SessionState(
            session_id="test",
            user_id="user",
            current_phase=AgentPhase.CLASSIFY
        )
        
        # Make several decisions
        for i in range(5):
            mock_llm_client.generate.return_value = '''{
                "intent_type": "new_request",
                "action": "create_new_task",
                "new_task_type": "error_resolution",
                "confidence": 0.9,
                "reasoning": f"Test decision {i}"
            }'''
            await service.make_decision(f"Test message {i}", session_state)
        
        metrics = service.get_metrics()
        
        assert metrics["total_decisions"] == 5
        assert metrics["cache_hit_rate"] > 0  # Should have cache hits
        assert "cache_size" in metrics
        assert metrics["prompt_version"] == "v1.2"


class TestEnhancedOrchestratorPreprocessor:
    """Test cases for Enhanced Orchestrator Preprocessor."""
    
    @pytest.mark.asyncio
    async def test_enhanced_preprocessing_with_llm(self, mock_llm_client):
        """Test enhanced preprocessing using LLM decisions."""
        preprocessor = await get_orchestrator_preprocessor(use_enhanced=True)
        
        # Mock LLM decision service
        with patch('src.core.orchestrator_preprocessor.get_llm_decision_service') as mock_get_service:
            mock_service = Mock()
            mock_service.make_decision = AsyncMock()
            
            # Set up mock decision
            mock_decision = OrchestratorDecision(
                intent_type="new_request",
                action="create_new_task",
                new_task_type="error_resolution",
                target_agent="classifier_agent",
                confidence=0.95,
                reasoning="User reports error",
                cache_hit=False,
                processing_time_ms=150
            )
            mock_service.make_decision.return_value = mock_decision
            
            mock_get_service.return_value = mock_service
            
            result = await preprocessor.preprocess_user_input(
                user_input="Món không hiển thị",
                current_state={"session_id": "test", "current_phase": "CLASSIFY"},
                conversation_history=[],
                session_context={}
            )
            
            assert result.success is True
            assert result.orchestrator_decision is not None
            assert result.orchestrator_decision.intent_type == "new_request"
            assert result.orchestrator_decision.cache_hit is False
            assert result.context_analysis["llm_decision_available"] is True
    
    @pytest.mark.asyncio
    async def test_legacy_preprocessing_fallback(self, mock_llm_client):
        """Test fallback to legacy preprocessing when enhanced fails."""
        preprocessor = await get_orchestrator_preprocessor(use_enhanced=True)
        
        # Mock LLM decision service to fail
        with patch('src.core.orchestrator_preprocessor.get_llm_decision_service') as mock_get_service:
            mock_service = Mock()
            mock_service.make_decision = AsyncMock(side_effect=Exception("LLM service failed"))
            mock_get_service.return_value = mock_service
            
            # Mock legacy LLM manager
            with patch.object(preprocessor, 'llm_manager', None):
                with patch.object(preprocessor, 'initialize', new_callable=AsyncMock()) as mock_init:
                    # Don't set llm_manager to trigger fallback
                    mock_init.return_value = None
                    
                    result = await preprocessor.preprocess_user_input(
                        user_input="Test message",
                        current_state={"session_id": "test", "current_phase": "CLASSIFY"},
                        conversation_history=[],
                        session_context={}
                    )
            
            assert result.success is True
            assert result.user_intent.value == "issue_report"
            assert result.orchestrator_action.value == "start_classification"
            assert result.confidence == 0.4  # Fallback confidence
    
    @pytest.mark.asyncio
    async def test_clean_preprocessing_interface(self):
        """Test clean preprocessing interface with SessionState."""
        preprocessor = await get_orchestrator_preprocessor(enable_llm_decisions=False)
        
        # Create test session state
        session_state = SessionState(
            session_id="test_session",
            user_id="test_user",
            current_phase=AgentPhase.CLASSIFY
        )
        
        # Test clean preprocessing interface
        decision = await preprocessor.preprocess_user_input(
            user_input="I need help with login issues",
            session_state=session_state
        )
        
        # Verify decision structure
        assert isinstance(decision, OrchestratorDecision)
        assert decision.intent_type in ["new_request", "continuation", "control_command", "ambiguous"]
        assert decision.action in [
            "create_new_task", "forward_to_current_agent", "ask_task_switch_confirmation",
            "auto_switch_task", "cancel_task", "restart_task", "ask_clarification", "escalate"
        ]
        assert 0.0 <= decision.confidence <= 1.0
        assert isinstance(decision.reasoning, str)
        assert isinstance(decision.extracted_entities, dict)
        
        # Test fallback behavior with greeting
        greeting_decision = await preprocessor.preprocess_user_input(
            user_input="hello there",
            session_state=session_state
        )
        
        # Verify greeting fallback decision
        assert greeting_decision.intent_type == "new_request"
        assert greeting_decision.action == "forward_to_current_agent"
        assert greeting_decision.new_task_type == "general_inquiry"
        assert greeting_decision.user_message is not None
        assert greeting_decision.confidence == 0.7
        
        # Test emergency fallback
        emergency_decision = preprocessor._emergency_fallback("unknown input")
        assert emergency_decision.intent_type == "ambiguous"
        assert emergency_decision.action == "ask_clarification"
        assert emergency_decision.confidence == 0.1


class TestEnhancedOrchestratorIntegration:
    """Test cases for Enhanced Orchestrator integration."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_with_llm_decisions(self, orchestrator_with_llm, mock_llm_client, sample_llm_decision, enhanced_session_state):
        """Test orchestrator with LLM decision making enabled."""
        
        # Mock LLM decision service
        with patch('src.agents.orchestrator.get_llm_decision_service') as mock_get_service:
            mock_service = Mock()
            mock_service.make_decision = AsyncMock(return_value=sample_llm_decision)
            mock_get_service.return_value = mock_service
            
            # Mock agent registry
            classifier_agent = Mock()
            classifier_agent.execute = AsyncMock(return_value={
                "success": True,
                "next_phase": AgentPhase.REQUIRED_INFO,
                "actions_taken": ["classification"]
            })
            orchestrator_with_llm.agents[AgentPhase.CLASSIFY] = classifier_agent
            
            # Execute orchestrator with user input
            result = await orchestrator_with_llm.execute(
                session_state=enhanced_session_state,
                user_input="Món không hiển thị"
            )
            
            assert result["session_id"] == "test_session_123"
            assert result["outcome"] == "success"
            assert len(orchestrator_with_llm.agents) > 0
            
            # Check that timeline event was added
            orchestrator_with_llm.session_manager.add_timeline_event.assert_called()
    
    @pytest.mark.asyncio
    async def test_orchestrator_without_llm_decisions(self, orchestrator_without_llm, enhanced_session_state):
        """Test orchestrator with LLM decision making disabled."""
        
        # Mock preprocessor to return legacy result
        with patch('src.core.orchestrator_preprocessor.get_orchestrator_preprocessor') as mock_get_preprocessor:
            mock_preprocessor = AsyncMock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.user_intent.value = "issue_report"
            mock_result.orchestrator_action.value = "start_classification"
            mock_result.confidence = 0.8
            mock_result.orchestrator_decision = None  # No LLM decision
            mock_preprocessor.preprocess_user_input = AsyncMock(return_value=mock_result)
            mock_get_preprocessor.return_value = mock_preprocessor
            
            # Mock agent
            classifier_agent = Mock()
            classifier_agent.execute = AsyncMock(return_value={
                "success": True,
                "next_phase": AgentPhase.REQUIRED_INFO,
                "actions_taken": ["classification"]
            })
            orchestrator_without_llm.agents[AgentPhase.CLASSIFY] = classifier_agent
            
            # Execute orchestrator
            result = await orchestrator_without_llm.execute(
                session_state=enhanced_session_state,
                user_input="Món không hiển thị"
            )
            
            assert result["session_id"] == "test_session_123"
            # Should use coordination-based execution instead of LLM decisions
    
    @pytest.mark.asyncio
    async def test_llm_task_creation(self, orchestrator_with_llm, sample_llm_decision, enhanced_session_state):
        """Test LLM-based task creation."""
        
        with patch('src.agents.orchestrator.get_llm_decision_service') as mock_get_service:
            mock_service = Mock()
            mock_service.make_decision = AsyncMock(return_value=sample_llm_decision)
            mock_get_service.return_value = mock_service
            
            # Mock agent
            classifier_agent = Mock()
            classifier_agent.execute = AsyncMock(return_value={
                "success": True,
                "next_phase": AgentPhase.REQUIRED_INFO,
                "actions_taken": ["classification"]
            })
            orchestrator_with_llm.agents[AgentPhase.CLASSIFY] = classifier_agent
            
            # Execute LLM decision
            result = await orchestrator_with_llm._execute_llm_decision(
                sample_llm_decision,
                enhanced_session_state,
                user_input="Món không hiển thị"
            )
            
            assert result["session_id"] == "test_session_123"
            assert result["outcome"] == "success"
            # Should have created a task
            assert enhanced_session_state.active_task is not None
            assert enhanced_session_state.active_task.task_type == TaskType.ERROR_RESOLUTION
            assert enhanced_session_state.active_task.current_agent == "classifier_agent"
    
    @pytest.mark.asyncio
    async def test_llm_task_switch_confirmation(self, orchestrator_with_llm, sample_task, enhanced_session_state):
        """Test LLM-based task switch confirmation."""
        
        # Create decision for task switch confirmation
        decision = OrchestratorDecision(
            intent_type="new_request",
            action="ask_task_switch_confirmation",
            new_task_type="feature_usage",
            user_message="Bạn có muốn chuyển sang yêu cầu mới không?\n1. Tiếp tục hiện tại\n2. Chuyển sang mới",
            user_options=["1", "2"],
            confidence=0.9,
            reasoning="New request during active task"
        )
        
        enhanced_session_state.active_task = sample_task
        
        result = await orchestrator_with_llm._execute_llm_decision(
            decision,
            enhanced_session_state
        )
        
        assert result["requires_user_input"] is True
        assert result["outcome"] == "awaiting_user_decision"
        assert result["next_phase"] == SessionPhase.WAIT_USER_SELECT
        assert "user_options" in result or "options" in result
        
        # Task should be in waiting state
        assert enhanced_session_state.active_task.current_phase == SessionPhase.WAIT_USER_SELECT
        assert enhanced_session_state.active_task.waiting_for == "task_switch_decision"
    
    @pytest.mark.asyncio
    async def test_llm_auto_task_switch(self, orchestrator_llm, enhanced_session_state):
        """Test LLM-based automatic task switching."""
        
        # Create decision for auto task switch
        decision = OrchestratorDecision(
            intent_type="new_request",
            action="auto_switch_task",
            new_task_type="feature_usage",
            target_agent="knowledge_agent",
            user_message="Đang xử lý yêu cầu mới. Yêu cầu trước đã tạm dừng.",
            confidence=0.9,
            reasoning="New request while task in early phase - safe to auto-switch"
        )
        
        # Create initial task
        initial_task = Task(
            task_id="TASK_INITIAL",
            task_type=TaskType.ERROR_RESOLUTION,
            status=TaskStatus.IN_PROGRESS,
            current_phase=SessionPhase.CLASSIFY,
            current_agent="classifier_agent",
            last_user_message="Initial error",
            priority="medium",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        enhanced_session_state.active_task = initial_task
        
        # Mock agent for new task
        knowledge_agent = Mock()
        knowledge_agent.execute = AsyncMock(return_value={
            "success": True,
            "next_phase": AgentPhase.REQUIRED_INFO,
            "actions_taken": ["feature_info"]
        })
        orchestrator_llm.agents["knowledge_agent"] = knowledge_agent
        
        result = await orchestrator_llm._execute_llm_decision(
            decision,
            enhanced_session_state
        )
        
        assert result["outcome"] == "success"
        assert "notification" in result
        
        # Should have paused initial task and created new one
        assert enhanced_session_state.active_task.task_id != "TASK_INITIAL"
        assert enhanced_session_state.active_task.task_type == TaskType.FEATURE_USAGE
        assert len(enhanced_session_state.pending_tasks) == 1
        assert enhanced_session_state.pending_tasks[0].task_id == "TASK_INITIAL"
        assert enhanced_session_state.pending_tasks[0].status == TaskStatus.PAUSED
    
    @pytest.mark.asyncio
    async def test_enhanced_metrics_collection(self, orchestrator_with_llm):
        """Test enhanced metrics collection including LLM decisions."""
        
        # Mock LLM decision service
        with patch('src.agents.orchestrator.get_llm_decision_service') as mock_get_service:
            mock_service = Mock()
            mock_service.get_metrics = Mock(return_value={
                "total_decisions": 25,
                "cache_hit_rate": 0.8,
                "fallback_rate": 0.1,
                "low_confidence_rate": 0.2,
                "error_rate": 0.0,
                "prompt_version": "v1.2"
            })
            mock_get_service.return_value = mock_service
            
            metrics = await orchestrator_with_llm.get_enhanced_metrics()
            
            assert "llm_decisions" in metrics
            assert "coordination" in metrics
            assert "hybrid_orchestration" in metrics
            
            # Check LLM decision metrics
            llm_metrics = metrics["llm_decisions"]
            assert llm_metrics["total_decisions"] == 25
            assert llm_metrics["cache_hit_rate"] == 0.8
            assert llm_metrics["prompt_version"] == "v1.2"
            
            # Check hybrid metrics
            hybrid_metrics = metrics["hybrid_orchestration"]
            assert hybrid_metrics["llm_decisions_enabled"] is True
            assert hybrid_metrics["coordination_rules_enabled"] is True


class TestHybridOrchestrationFlow:
    """Test cases for hybrid orchestration flow combining LLM and coordination."""
    
    @pytest.mark.asyncio
    async def test_llm_and_coordination_interaction(self, orchestrator_with_llm, enhanced_session_state):
        """Test interaction between LLM decisions and coordination rules."""
        
        # Create coordination manager mock
        coordination_manager = Mock()
        coordination_manager.process_event = AsyncMock(return_value=None)
        coordination_manager.get_metrics = Mock(return_value={"workflow_events": 5})
        orchestrator_with_llm.coordination_manager = coordination_manager
        
        # Create LLM decision that should trigger coordination
        decision = OrchestratorDecision(
            intent_type="new_request",
            action="create_new_task",
            new_task_type="error_resolution",
            confidence=0.95,
            reasoning="High confidence new request"
        )
        
        # Mock LLM service and agent
        with patch('src.agents.orchestrator.get_llm_decision_service') as mock_get_service:
            mock_service = Mock()
            mock_service.make_decision = AsyncMock(return_value=decision)
            mock_get_service.return_value = mock_service
            
            classifier_agent = Mock()
            classifier_agent.execute = AsyncMock(return_value={
                "success": True,
                "next_phase": AgentPhase.REQUIRED_INFO,
                "actions_taken": ["classification"]
            })
            orchestrator_with_llm.agents[AgentPhase.CLASSIFY] = classifier_agent
            
            # Execute with LLM decision
            result = await orchestrator_with_llm.execute(
                session_state=enhanced_session_state,
                user_input="Test error message"
            )
            
            # Both LLM decision should be used and coordination should process events
            assert result["outcome"] == "success"
            coordination_manager.process_event.assert_called()
            
            # Check metrics
            metrics = await orchestrator_with_llm.get_coordination_metrics()
            assert "coordination" in metrics
            assert "llm_decisions" in metrics
            assert "hybrid_orchestration" in metrics
    
    @pytest.mark.asyncio
    async def test_fallback_to_coordination(self, orchestrator_with_llm, enhanced_session_state):
        """Test fallback to coordination when LLM decisions fail."""
        
        # Mock LLM service to fail
        with patch('src.agents.orchestrator.get_llm_decision_service') as mock_get_service:
            mock_service = Mock()
            mock_service.make_decision = AsyncMock(side_effect=Exception("LLM service unavailable"))
            mock_get_service.return_value = mock_service
            
            # Mock coordination
            coordination_manager = Mock()
            coordination_manager.process_event = AsyncMock(return_value=None)
            orchestrator_with_llm.coordination_manager = coordination_manager
            
            # Mock preprocessor to provide legacy fallback
            with patch('src.core.orchestrator_preprocessor.get_orchestrator_preprocessor') as mock_get_preprocessor:
                mock_preprocessor = AsyncMock()
                mock_result = Mock()
                mock_result.success = True
                mock_result.user_intent.value = "issue_report"
                mock_result.orchestrator_action.value = "start_classification"
                mock_result.confidence = 0.8
                mock_result.orchestrator_decision = None
                mock_preprocessor.preprocess_user_input = AsyncMock(return_value=mock_result)
                mock_get_preprocessor.return_value = mock_preprocessor
                
                # Mock agent
                classifier_agent = Mock()
                classifier_agent.execute = AsyncMock(return_value={
                    "success": True,
                    "next_phase": AgentPhase.REQUIRED_INFO,
                    "actions_taken": ["classification"]
                })
                orchestrator_with_llm.agents[AgentPhase.CLASSIFY] = classifier_agent
                
                # Execute with LLM disabled (should fallback to coordination)
                result = await orchestrator_with_llm.execute(
                    session_state=enhanced_session_state,
                    user_input="Test message"
                )
                
                # Should use coordination-based execution
                assert result["session_id"] == "test_session_123"
                coordination_manager.process_event.assert_called()


# Test utilities and helper functions
class TestDecisionCaching:
    """Test decision caching functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self):
        """Test cache key generation consistency."""
        service = LLMDecisionService()
        
        session_state1 = SessionState(
            session_id="test_session",
            user_id="user",
            current_phase=AgentPhase.CLASSIFY,
            conversation_history=[]
        )
        
        session_state2 = SessionState(
            session_id="test_session",
            user_id="user",
            current_phase=AgentPhase.CLASSIFY,
            conversation_history=[]
        )
        
        session_state3 = SessionState(
            session_id="test_session",
            user_id="user",
            current_phase=AgentPhase.REQUIRED_INFO,  # Different phase
            conversation_history=[]
        )
        
        # Same context should produce same cache key
        key1 = service._get_cache_key("Test message", session_state1)
        key2 = service._get_cache_key("Test message", session_state2)
        key3 = service._get_cache_key("Test message", session_state3)
        
        assert key1 == key2  # Same context
        assert key1 != key3  # Different phase
        
        # Different message should produce different cache key
        key4 = service._get_cache_key("Different message", session_state1)
        assert key1 != key4
    
    @pytest.asyncio
    async def test_cache_cleanup(self):
        """Test cache cleanup functionality."""
        service = LLMDecisionService()
        
        # Fill cache beyond limit
        for i in range(service.max_cache_size + 10):
            decision = OrchestratorDecision(
                intent_type="new_request",
                action="create_new_task",
                confidence=0.9,
                reasoning=f"Test decision {i}"
            )
            service.decision_cache[f"key_{i}"] = {
                "decision": decision,
                "timestamp": datetime.now() - timedelta(minutes=i)  # Staggered timestamps
            }
        
        initial_size = len(service.decision_cache)
        service._cleanup_cache()
        
        # Should remove expired and oldest entries
        final_size = len(service.decision_cache)
        assert final_size < initial_size
        assert final_size <= service.max_cache_size


# Integration test class
class TestEndToEndFlow:
    """End-to-end integration tests for the complete enhanced system."""
    
    @pytest.mark.asyncio
    async def test_complete_decision_flow_with_caching(self, mock_llm_client, mock_session_manager):
        """Test complete decision flow with caching enabled."""
        
        # Create enhanced orchestrator
        orchestrator = OrchestratorAgent(use_llm_decisions=True)
        orchestrator.set_dependencies(mock_session_manager, None)
        
        # Mock LLM decision service
        with patch('src.agents.orchestrator.get_llm_decision_service') as mock_get_service:
            mock_service = Mock()
            mock_service.make_decision = AsyncMock()
            mock_service.get_metrics = Mock(return_value={
                "total_decisions": 2,
                "cache_hit_rate": 0.5,
                "cache_size": 1
            })
            mock_get_service.return_value = mock_service
            
            # Mock agent
            classifier_agent = Mock()
            classifier_agent.execute = AsyncMock(return_value={
                "success": True,
                "next_phase": AgentPhase.REQUIRED_INFO,
                "actions_taken": ["classification"]
            })
            orchestrator.agents[AgentPhase.CLASSIFY] = classifier_agent
            
            # Create session state
            session_state = SessionState(
                session_id="integration_test",
                user_id="test_user",
                current_phase=AgentPhase.CLASSIFY,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # First request - should hit LLM
            result1 = await orchestrator.execute(
                session_state=session_state,
                user_input="Món không hiển thị trong menu"
            )
            
            assert result1["outcome"] == "success"
            assert session_state.active_task is not None
            
            # Second request with similar context - should hit cache
            result2 = await orchestrator.execute(
                session_state=session_state,
                user_input="Món không hiển thị trong menu"
            )
            
            assert result2["outcome"] == "success"
            
            # Check that caching metrics reflect usage
            metrics = await orchestrator.get_enhanced_metrics()
            llm_metrics = metrics["llm_decisions"]
            assert llm_metrics["cache_hit_rate"] == 0.5  # Should have cache hits


if __name__ == "__main__":
    # Run tests when executed directly
    import sys
    sys.exit(pytest.main([__file__]))