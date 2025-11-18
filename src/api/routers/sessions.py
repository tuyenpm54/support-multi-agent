from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from pydantic import BaseModel

from src.core.state_manager import session_manager
from src.models.session import SessionState


router = APIRouter()


class SessionCreateRequest(BaseModel):
    """Request model for creating a session."""
    user_id: str
    user_metadata: Dict[str, Any] = {}


class SessionResponse(BaseModel):
    """Response model for session data."""
    session_id: str
    user_id: str
    current_phase: str
    created_at: str
    updated_at: str
    # Add other fields as needed


@router.post("/", response_model=Dict[str, Any])
async def create_session(request: SessionCreateRequest):
    """Create a new support session."""
    try:
        session_id = await session_manager.create_session(
            user_id=request.user_id,
            user_metadata=request.user_metadata
        )
        
        # Session created successfully - workflow will be started on first message
        
        return {
            "session_id": session_id,
            "message": "Session created successfully",
            "status": "active"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    session_state = await session_manager.get_session(session_id)
    
    if not session_state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_state.session_id,
        "user_id": session_state.user_id,
        "current_phase": session_state.current_phase,
        "created_at": session_state.created_at.isoformat(),
        "updated_at": session_state.updated_at.isoformat(),
        "classification": session_state.classification.dict() if session_state.classification else None,
        "required_info": session_state.required_info.dict() if session_state.required_info else None,
        "validation": session_state.validation.dict() if session_state.validation else None,
        "fix": session_state.fix.dict() if session_state.fix else None,
        "retry_count": session_state.retry_count,
        "fallback_count": session_state.fallback_count
    }


@router.get("/{session_id}/timeline")
async def get_session_timeline(session_id: str):
    """Get session timeline events."""
    timeline = await session_manager.get_session_timeline(session_id)
    
    return {
        "session_id": session_id,
        "timeline": [
            {
                "timestamp": event.timestamp.isoformat(),
                "phase": event.phase,
                "agent": event.agent,
                "action": event.action,
                "details": event.details,
                "duration_ms": event.duration_ms
            }
            for event in timeline
        ]
    }


@router.get("/{session_id}/conversation")
async def get_conversation_history(session_id: str):
    """Get conversation history for a session."""
    history = await session_manager.get_conversation_history(session_id)
    
    return {
        "session_id": session_id,
        "conversation_history": history
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all its data."""
    try:
        success = await session_manager.delete_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {"message": "Session deleted successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


@router.get("/")
async def list_sessions(user_id: str = None):
    """List active sessions, optionally filtered by user."""
    try:
        session_ids = await session_manager.get_active_sessions(user_id)
        
        # Get basic info for each session
        sessions = []
        for session_id in session_ids[:50]:  # Limit to 50 for performance
            session_state = await session_manager.get_session(session_id)
            if session_state:
                sessions.append({
                    "session_id": session_state.session_id,
                    "user_id": session_state.user_id,
                    "current_phase": session_state.current_phase,
                    "created_at": session_state.created_at.isoformat(),
                    "updated_at": session_state.updated_at.isoformat()
                })
        
        return {
            "sessions": sessions,
            "total_count": len(session_ids),
            "showing": len(sessions)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")