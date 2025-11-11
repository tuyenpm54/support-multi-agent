import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import redis.asyncio as redis
from src.core.config import settings
from src.models.session import SessionState, TimelineEvent


class SessionManager:
    """Manages session state using Redis with local caching."""
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        self.session_ttl = settings.session_ttl
        self.state_key_prefix = "session:"
        self.timeline_key_prefix = "timeline:"
        
        # Local cache for frequently accessed sessions
        self.local_cache: Dict[str, SessionState] = {}
        self.cache_ttl = 300  # 5 minutes
        
    async def create_session(self, user_id: str, user_metadata: Dict[str, Any]) -> str:
        """Create a new session with initial state."""
        session_id = f"SESSION_{uuid.uuid4().hex[:12]}"
        
        session_state = SessionState(
            session_id=session_id,
            user_id=user_id,
            user_metadata=user_metadata,
            system_metadata={
                "environment": settings.environment,
                "version": "1.0.0"
            }
        )
        
        await self._store_session(session_state)
        
        # Add creation event to timeline
        await self.add_timeline_event(
            session_id, 
            TimelineEvent(
                phase="SYSTEM",
                action="SESSION_CREATED",
                details={"user_id": user_id}
            )
        )
        
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get session state from cache or Redis."""
        # Check local cache first
        if session_id in self.local_cache:
            cached_session = self.local_cache[session_id]
            # Check if cache is still valid
            if (datetime.now() - cached_session.updated_at).seconds < self.cache_ttl:
                return cached_session
            else:
                del self.local_cache[session_id]
        
        # Fetch from Redis
        session_data = await self.redis_client.get(f"{self.state_key_prefix}{session_id}")
        if not session_data:
            return None
        
        try:
            session_state = SessionState.parse_raw(session_data)
            
            # Update local cache
            self.local_cache[session_id] = session_state
            
            return session_state
        except Exception as e:
            print(f"Error parsing session state: {e}")
            return None
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session state with provided fields."""
        session_state = await self.get_session(session_id)
        if not session_state:
            return False
        
        # Apply updates
        for field, value in updates.items():
            if hasattr(session_state, field):
                setattr(session_state, field, value)
        
        session_state.updated_at = datetime.now()
        
        await self._store_session(session_state)
        
        # Update local cache
        self.local_cache[session_id] = session_state
        
        return True
    
    async def _store_session(self, session_state: SessionState):
        """Store session state in Redis."""
        await self.redis_client.setex(
            f"{self.state_key_prefix}{session_state.session_id}",
            self.session_ttl,
            session_state.json()
        )
    
    async def add_timeline_event(self, session_id: str, event: TimelineEvent):
        """Add an event to the session timeline."""
        timeline_key = f"{self.timeline_key_prefix}{session_id}"
        
        # Prepare event data
        event_data = {
            "timestamp": event.timestamp.isoformat(),
            "phase": event.phase,
            "agent": event.agent,
            "action": event.action,
            "details": event.details,
            "duration_ms": event.duration_ms
        }
        
        # Add to Redis list
        await self.redis_client.lpush(timeline_key, json.dumps(event_data))
        await self.redis_client.expire(timeline_key, self.session_ttl)
        
        # Limit timeline size (keep last 100 events)
        await self.redis_client.ltrim(timeline_key, 0, 99)
        
        # Update session's timeline if cached
        if session_id in self.local_cache:
            self.local_cache[session_id].timeline.append(event)
            self.local_cache[session_id].updated_at = datetime.now()
    
    async def get_session_timeline(self, session_id: str) -> List[TimelineEvent]:
        """Get the complete timeline for a session."""
        timeline_key = f"{self.timeline_key_prefix}{session_id}"
        
        # Get all timeline events from Redis
        timeline_data = await self.redis_client.lrange(timeline_key, 0, -1)
        
        timeline = []
        for event_json in reversed(timeline_data):  # Reverse to get chronological order
            try:
                event_dict = json.loads(event_json)
                event = TimelineEvent(
                    timestamp=datetime.fromisoformat(event_dict["timestamp"]),
                    phase=event_dict["phase"],
                    agent=event_dict.get("agent"),
                    action=event_dict["action"],
                    details=event_dict.get("details", {}),
                    duration_ms=event_dict.get("duration_ms")
                )
                timeline.append(event)
            except Exception as e:
                print(f"Error parsing timeline event: {e}")
                continue
        
        return timeline
    
    async def add_conversation_message(self, session_id: str, message: Dict[str, Any], is_user: bool = True):
        """Add a conversation message to the session history."""
        session_state = await self.get_session(session_id)
        if session_state:
            session_state.conversation_history.append({
                "timestamp": datetime.now().isoformat(),
                "is_user": is_user,
                "message": message
            })
            await self._store_session(session_state)
            
            # Update local cache if present
            if session_id in self.local_cache:
                self.local_cache[session_id].conversation_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "is_user": is_user,
                    "message": message
                })
    
    async def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get the conversation history for a session."""
        session_state = await self.get_session(session_id)
        return session_state.conversation_history if session_state else []
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions (run periodically)."""
        pattern = f"{self.state_key_prefix}*"
        keys = await self.redis_client.keys(pattern)
        
        for key in keys:
            ttl = await self.redis_client.ttl(key)
            if ttl == -1:  # No expiration set
                await self.redis_client.expire(key, self.session_ttl)
            elif ttl == -2:  # Key doesn't exist
                continue
        
        # Clean up local cache
        current_time = datetime.now()
        expired_sessions = [
            session_id for session_id, session in self.local_cache.items()
            if (current_time - session.updated_at).seconds > self.cache_ttl
        ]
        
        for session_id in expired_sessions:
            del self.local_cache[session_id]
    
    async def get_active_sessions(self, user_id: Optional[str] = None) -> List[str]:
        """Get list of active session IDs."""
        pattern = f"{self.state_key_prefix}*"
        keys = await self.redis_client.keys(pattern)
        
        session_ids = []
        for key in keys:
            session_id = key.replace(self.state_key_prefix, "")
            
            # Check if session belongs to user (if specified)
            if user_id:
                session_state = await self.get_session(session_id)
                if session_state and session_state.user_id == user_id:
                    session_ids.append(session_id)
            else:
                session_ids.append(session_id)
        
        return session_ids
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its data."""
        # Delete session state
        state_key = f"{self.state_key_prefix}{session_id}"
        timeline_key = f"{self.timeline_key_prefix}{session_id}"
        
        pipe = self.redis_client.pipeline()
        pipe.delete(state_key)
        pipe.delete(timeline_key)
        await pipe.execute()
        
        # Remove from local cache
        if session_id in self.local_cache:
            del self.local_cache[session_id]
        
        return True


# Global session manager instance
session_manager = SessionManager()