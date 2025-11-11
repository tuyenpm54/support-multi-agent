from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel

from src.core.state_manager import session_manager
from src.agents.orchestrator import OrchestratorAgent


router = APIRouter()


class MessageRequest(BaseModel):
    """Request model for sending a message."""
    message: str
    message_type: str = "text"  # text, image, file, etc.
    metadata: Dict[str, Any] = {}


class MessageResponse(BaseModel):
    """Response model for agent responses."""
    session_id: str
    response: str
    phase: str
    requires_user_input: bool
    actions_taken: list = []


@router.post("/{session_id}/message")
async def send_message(session_id: str, request: MessageRequest):
    """Send a message to the support system."""
    try:
        # Get session
        session_state = await session_manager.get_session(session_id)
        if not session_state:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Prepare user input
        user_input = {
            "message": request.message,
            "type": request.message_type,
            "metadata": request.metadata
        }
        
        # Get orchestrator (this should be injected properly in a real app)
        # For now, we'll create a temporary instance
        orchestrator = OrchestratorAgent()
        orchestrator.set_dependencies(session_manager, None)
        
        # Process message through orchestrator
        result = await orchestrator.handle_user_input(session_id, user_input)
        
        return {
            "session_id": session_id,
            "response": result,
            "timestamp": "2025-01-11T00:00:00Z"  # Would use actual timestamp
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")


@router.get("/{session_id}/status")
async def get_conversation_status(session_id: str):
    """Get current conversation status."""
    session_state = await session_manager.get_session(session_id)
    
    if not session_state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "current_phase": session_state.current_phase,
        "phase_status": {
            "classification": session_state.classification.dict() if session_state.classification else None,
            "required_info": session_state.required_info.dict() if session_state.required_info else None,
            "validation": session_state.validation.dict() if session_state.validation else None,
            "fix": session_state.fix.dict() if session_state.fix else None,
        },
        "retry_count": session_state.retry_count,
        "escalation_reason": session_state.escalation_reason,
        "completed_at": session_state.completed_at.isoformat() if session_state.completed_at else None
    }