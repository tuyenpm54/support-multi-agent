from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging

from src.core.state_manager import session_manager
from src.agents.orchestrator import OrchestratorAgent

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = {}
    message_type: str = "text"
    metadata: Dict[str, Any] = {}


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    session_id: str
    response: str
    phase: str
    confidence: float
    actions: list = []
    requires_follow_up: bool
    suggested_next_actions: list = []
    decision_metadata: Optional[Dict[str, Any]] = {}
    timestamp: Optional[str] = None


# Global orchestrator reference (will be set during app startup)
orchestrator: Optional[OrchestratorAgent] = None


def get_orchestrator() -> OrchestratorAgent:
    """Dependency to get orchestrator instance."""
    global orchestrator
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    return orchestrator


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    orch: OrchestratorAgent = Depends(get_orchestrator)
):
    """
    Main chat endpoint that receives user input and processes it through the orchestrator.
    """
    try:
        # Handle session creation or retrieval
        if request.session_id:
            # Use existing session
            session_state = await session_manager.get_session(request.session_id)
            if not session_state:
                raise HTTPException(status_code=404, detail="Session not found")
            session_id = request.session_id
        else:
            # Create new session
            session_id = await session_manager.create_session(
                user_id=request.user_id or "anonymous",
                user_metadata=request.context or {}
            )
            logger.info(f"Created new session: {session_id}")
        
        # Prepare user input for orchestrator
        user_input = {
            "message": request.message,
            "type": request.message_type,
            "metadata": {
                "user_id": request.user_id,
                "context": request.context or {},
                **request.metadata,
                "timestamp": "2025-01-17T00:00:00Z"
            }
        }
        
        # Process through orchestrator
        logger.info(f"Processing message for session {session_id}: {request.message[:100]}...")
        
        # Get orchestrator decision by calling handle_user_input
        result = await orch.handle_user_input(session_id, user_input)
        
        # Extract response information from orchestrator result
        if "error" in result:
            logger.error(f"Orchestrator error: {result['error']}")
            raise HTTPException(status_code=500, detail=result.get("error", "Orchestrator processing error"))
        
        # Get updated session state to extract decision info
        updated_session = await session_manager.get_session(session_id)
        
        # Extract decision information if available
        decision = None
        confidence = 0.0
        phase = "unknown"
        response_text = ""
        requires_follow_up = False
        
        # First try to get decision from orchestrator result (most reliable)
        if "orchestrator_decision" in result:
            decision = result["orchestrator_decision"]
            
            # Handle both dict and OrchestratorDecision object
            if isinstance(decision, dict):
                confidence = decision.get("confidence", 0.0)
                phase = decision.get("action", "unknown")
                response_text = decision.get("user_message", f"Processed: {decision.get('action', 'unknown')} (confidence: {confidence:.2f})")
                requires_follow_up = decision.get("action") in ["ask_clarification", "ask_task_switch_confirmation"]
                action = decision.get("action", "unknown")
            else:
                # OrchestratorDecision object
                confidence = decision.confidence
                phase = decision.action if decision.action else "unknown"
                response_text = decision.user_message if decision.user_message else f"Processed: {decision.action} (confidence: {confidence:.2f})"
                requires_follow_up = decision.action in ["ask_clarification", "ask_task_switch_confirmation"]
                action = decision.action
            
            logger.info(f"Chat API - Using orchestrator result decision: {action} with confidence {confidence}")
        # Try to get decision from session state as fallback
        elif updated_session and hasattr(updated_session, 'recent_decisions') and updated_session.recent_decisions:
            # Get the most recent decision
            decision = updated_session.recent_decisions[-1]
            confidence = decision.confidence
            # Use action as phase since session_phase is not available in OrchestratorDecision
            phase = decision.action if decision.action else "unknown"
            # Use the decision's user_message if available
            if hasattr(decision, 'user_message') and decision.user_message:
                response_text = decision.user_message
            else:
                response_text = f"Processed: {decision.action} (confidence: {confidence:.2f})"
            requires_follow_up = decision.action in ["ask_clarification", "ask_task_switch_confirmation"]
            logger.info(f"Chat API - Using session decision: {decision.action} with confidence {confidence}")
        else:
            # Fallback to orchestrator result
            if "response" in result:
                response_text = result["response"]
            elif "message" in result:
                response_text = result["message"]
            elif "agent_response" in result:
                response_text = result["agent_response"]
            else:
                response_text = "Processing your request..."
            
            requires_follow_up = result.get("requires_user_input", result.get("requires_follow_up", False))
            logger.warning(f"Chat API - No decision found, using fallback response")
        
        # Extract follow-up requirement (already set above, but also check result)
        if not requires_follow_up:
            requires_follow_up = result.get("requires_user_input", result.get("requires_follow_up", False))
        
        # Extract actions and next steps
        actions = result.get("actions_taken", [])
        if decision and hasattr(decision, 'primary_action') and decision.primary_action:
            actions.append(decision.primary_action.dict() if hasattr(decision.primary_action, 'dict') else str(decision.primary_action))
        
        suggested_actions = []
        if decision and hasattr(decision, 'next_steps') and decision.next_steps:
            suggested_actions = [step.dict() if hasattr(step, 'dict') else str(step) for step in decision.next_steps]
        
        return ChatResponse(
            session_id=session_id,
            response=response_text,
            phase=phase,
            confidence=confidence,
            actions=actions,
            requires_follow_up=requires_follow_up,
            suggested_next_actions=suggested_actions,
            decision_metadata=decision.dict() if decision and hasattr(decision, 'dict') else (decision if isinstance(decision, dict) else {}),
            timestamp="2025-01-17T00:00:00Z"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {str(e)}"
        )


@router.get("/chat/{session_id}/status")
async def get_chat_status(session_id: str):
    """Get current status of chat session."""
    try:
        session_state = await session_manager.get_session(session_id)
        if not session_state:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session_id,
            "current_phase": getattr(session_state, 'current_phase', 'UNKNOWN'),
            "is_active": True,  # Simplified for demo
            "retry_count": getattr(session_state, 'retry_count', 0),
            "escalation_reason": getattr(session_state, 'escalation_reason', None),
            "decision": getattr(session_state, 'current_decision', None).dict() if hasattr(session_state, 'current_decision') and session_state.current_decision else None,
            "conversation_count": len(getattr(session_state, 'conversation_history', [])),
            "created_at": getattr(session_state, 'created_at', None).isoformat() if hasattr(session_state, 'created_at') and session_state.created_at else None,
            "updated_at": getattr(session_state, 'updated_at', None).isoformat() if hasattr(session_state, 'updated_at') and session_state.updated_at else None,
            "completed_at": getattr(session_state, 'completed_at', None).isoformat() if hasattr(session_state, 'completed_at') and session_state.completed_at else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get session status: {str(e)}")


@router.get("/chat/{session_id}/history")
async def get_chat_history(session_id: str):
    """Get conversation history for a session."""
    try:
        session_state = await session_manager.get_session(session_id)
        if not session_state:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session_id,
            "history": getattr(session_state, 'conversation_history', []),
            "conversation_count": len(getattr(session_state, 'conversation_history', []))
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get chat history: {str(e)}")


def set_orchestrator_instance(orchestrator_instance: OrchestratorAgent):
    """Set the global orchestrator instance (called during app startup)."""
    global orchestrator
    orchestrator = orchestrator_instance
    logger.info("Orchestrator instance set for unified chat router")