# Chat API Documentation

## Overview

The Chat API provides a comprehensive REST interface for interacting with the Multi-Agent Customer Support System. It combines the best features of both simple chat and conversation management, supporting both automatic session creation and advanced session control.

## Base URL

```
http://localhost:8000/api/v1
```

## API Endpoints

### Primary Chat Endpoints

#### POST /chat

**Main chat endpoint with automatic session creation.** Perfect for simple clients that want to start conversations without managing session lifecycle.

**Request:**
```json
{
  "message": "I can't log into my account",
  "session_id": null,  // Optional: creates new session if null/omitted
  "user_id": "user123",  // Optional
  "context": {  // Optional context for the session
    "source": "web",
    "user_agent": "Mozilla/5.0..."
  },
  "message_type": "text",  // Optional: text, image, file, etc.
  "metadata": {}  // Optional additional metadata
}
```

**Response:**
```json
{
  "session_id": "session_abc123",
  "response": "I understand you're having trouble logging into your account. Let me help you with that.",
  "phase": "CLASSIFY",
  "confidence": 0.85,
  "actions": [
    {
      "action_type": "classify_issue",
      "description": "Login issue classified as authentication problem"
    }
  ],
  "requires_follow_up": true,
  "suggested_next_actions": [
    {
      "action_type": "ask_diagnostic_questions",
      "description": "Ask about specific error messages"
    }
  ],
  "decision_metadata": {
    "intent_type": "account_issue",
    "confidence": 0.85,
    "session_phase": "CLASSIFY",
    "primary_action": {
      "action_type": "classify_issue"
    },
    "next_steps": [
      {
        "action_type": "ask_diagnostic_questions",
        "description": "Ask about specific error messages"
      }
    ]
  },
  "timestamp": "2025-01-17T10:30:00Z"
}
```

#### POST /sessions/{session_id}/message

**Send message to existing session.** Perfect for clients that manage their own session lifecycle.

**Request:**
```json
{
  "message": "I'm getting a password error",
  "message_type": "text",  // Optional: text, image, file, etc.
  "metadata": {}  // Optional additional metadata
}
```

**Response:** Same format as POST /chat above, but with the provided session_id.

### Session Management Endpoints

#### GET /sessions/{session_id}/status

Get comprehensive session status including detailed phase information.

**Response:**
```json
{
  "session_id": "session_abc123",
  "current_phase": "CLASSIFY",
  "is_active": true,
  "retry_count": 0,
  "escalation_reason": null,
  "decision": {
    "intent_type": "account_issue",
    "primary_action": {
      "action_type": "classify_issue"
    },
    "confidence": 0.85
  },
  "conversation_count": 5,
  "phase_status": {
    "classification": {
      "intent_type": "account_issue",
      "confidence": 0.85,
      "identified_issue": "login_problem"
    },
    "required_info": null,
    "validation": null,
    "fix": null
  },
  "created_at": "2025-01-17T10:25:00Z",
  "updated_at": "2025-01-17T10:35:00Z",
  "completed_at": null
}
```

#### GET /sessions/{session_id}/history

Get conversation history with pagination support.

**Query Parameters:**
- `limit` (optional): Number of messages to return (default: 50)
- `offset` (optional): Number of messages to skip (default: 0)

**Response:**
```json
{
  "session_id": "session_abc123",
  "messages": [
    {
      "id": "msg_001",
      "sender": "user",
      "content": "I can't log into my account",
      "timestamp": "2025-01-17T10:30:00Z",
      "metadata": {
        "user_id": "user123",
        "source": "web"
      }
    },
    {
      "id": "msg_002", 
      "sender": "agent",
      "content": "I understand you're having trouble logging in. Can you tell me what specific error you're seeing?",
      "timestamp": "2025-01-17T10:30:15Z",
      "metadata": {
        "phase": "CLASSIFY"
      }
    }
  ],
  "total_count": 25,
  "has_more": true
}
```

#### DELETE /sessions/{session_id}

End a chat session (marks as inactive, doesn't delete data).

**Response:**
```json
{
  "session_id": "session_abc123",
  "message": "Session ended successfully",
  "status": "completed"
}
```

## Usage Patterns

### Pattern 1: Simple Chat (Automatic Sessions)

Perfect for web chats, mobile apps, and simple integrations:

```python
import requests

# First message - automatically creates session
response = requests.post("http://localhost:8000/api/v1/chat", json={
    "message": "I need help with my account",
    "user_id": "user123"
})

data = response.json()
session_id = data['session_id']

# Continue conversation
response = requests.post("http://localhost:8000/api/v1/chat", json={
    "message": "I forgot my password",
    "session_id": session_id
})
```

### Pattern 2: Advanced Session Management

Perfect for enterprise applications with full session control:

```python
import requests

# Create session first (using sessions API)
session_response = requests.post("http://localhost:8000/api/v1/sessions", json={
    "user_id": "user123",
    "context": {"source": "enterprise_app"}
})
session_id = session_response.json()["session_id"]

# Send messages to existing session
response = requests.post(f"http://localhost:8000/api/v1/sessions/{session_id}/message", json={
    "message": "I need help with billing",
    "metadata": {"priority": "high"}
})

# Get detailed status
status = requests.get(f"http://localhost:8000/api/v1/sessions/{session_id}/status")
```

### Pattern 3: Conversation History & Analytics

```python
# Get conversation history with pagination
history_response = requests.get(
    f"http://localhost:8000/api/v1/sessions/{session_id}/history",
    params={"limit": 20, "offset": 0}
)

data = history_response.json()
messages = data["messages"]
total_messages = data["total_count"]

# Process messages for analytics
for message in messages:
    print(f"{message['sender']}: {message['content']}")
```

## Request/Response Fields Reference

### ChatRequest Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| message | string | ✅ | User message content |
| session_id | string | ❌ | Existing session ID (creates new if null/omitted) |
| user_id | string | ❌ | User identifier |
| context | object | ❌ | Initial session context (only used for new sessions) |
| message_type | string | ❌ | Message type: text, image, file, etc. (default: text) |
| metadata | object | ❌ | Additional message metadata |

### ChatResponse Fields

| Field | Type | Description |
|-------|------|-------------|
| session_id | string | Session identifier |
| response | string | Agent's response message |
| phase | string | Current orchestrator phase (CLASSIFY, REQUIRED_INFO, VALIDATE, FIX, COMPLETE) |
| confidence | float | Orchestrator confidence score (0.0-1.0) |
| actions | array | List of actions taken by orchestrator |
| requires_follow_up | boolean | Whether user needs to provide more information |
| suggested_next_actions | array | Recommended next steps |
| decision_metadata | object | Full orchestrator decision details |
| timestamp | string | Response timestamp |

### SessionStatusResponse Fields

| Field | Type | Description |
|-------|------|-------------|
| session_id | string | Session identifier |
| current_phase | string | Current orchestrator phase |
| is_active | boolean | Whether session is currently active |
| retry_count | int | Number of retry attempts |
| escalation_reason | string | Reason for escalation if escalated |
| decision | object | Current orchestrator decision |
| conversation_count | int | Number of messages in conversation |
| phase_status | object | Detailed status for each phase |
| created_at | string | Session creation timestamp |
| updated_at | string | Last update timestamp |
| completed_at | string | Session completion timestamp |

## Error Handling

The API returns standard HTTP status codes:

- **200**: Success
- **400**: Bad request (invalid input data)
- **404**: Session not found
- **500**: Internal server error
- **503**: System not ready (orchestrator not initialized)

**Error Response Format:**
```json
{
  "detail": "Session not found"
}
```

## Integration Examples

### JavaScript/TypeScript

```typescript
class ChatClient {
  private baseUrl = 'http://localhost:8000/api/v1';
  private sessionId?: string;

  async sendMessage(message: string, userId?: string): Promise<any> {
    const response = await fetch(`${this.baseUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: this.sessionId,
        user_id: userId,
        context: { source: 'web_app' }
      })
    });
    
    const data = await response.json();
    this.sessionId = data.session_id; // Store for subsequent messages
    return data;
  }

  async getStatus(): Promise<any> {
    if (!this.sessionId) throw new Error('No active session');
    
    const response = await fetch(`${this.baseUrl}/sessions/${this.sessionId}/status`);
    return response.json();
  }

  async getHistory(limit = 50): Promise<any> {
    if (!this.sessionId) throw new Error('No active session');
    
    const response = await fetch(
      `${this.baseUrl}/sessions/${this.sessionId}/history?limit=${limit}`
    );
    return response.json();
  }
}

// Usage
const chat = new ChatClient();
const response = await chat.sendMessage("I need help with my account", "user123");
console.log(response.response);
```

### Python

```python
import requests
from typing import Optional, Dict, Any, List

class UnifiedChatClient:
    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        self.base_url = base_url
        self.session_id: Optional[str] = None
    
    def send_message(
        self, 
        message: str, 
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send a message, automatically creating session if needed."""
        response = requests.post(
            f"{self.base_url}/chat",
            json={
                "message": message,
                "session_id": self.session_id,
                "user_id": user_id,
                "context": context or {}
            }
        )
        
        data = response.json()
        self.session_id = data["session_id"]
        return data
    
    def get_status(self) -> Dict[str, Any]:
        """Get current session status."""
        if not self.session_id:
            raise ValueError("No active session")
        
        response = requests.get(f"{self.base_url}/sessions/{self.session_id}/status")
        return response.json()
    
    def get_history(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get conversation history."""
        if not self.session_id:
            raise ValueError("No active session")
        
        response = requests.get(
            f"{self.base_url}/sessions/{self.session_id}/history",
            params={"limit": limit, "offset": offset}
        )
        return response.json()
    
    def end_session(self) -> Dict[str, Any]:
        """End the current session."""
        if not self.session_id:
            raise ValueError("No active session")
        
        response = requests.delete(f"{self.base_url}/sessions/{self.session_id}")
        self.session_id = None
        return response.json()

# Usage
chat = UnifiedChatClient()
response = chat.send_message("I can't log into my account", user_id="user123")
print(f"Agent: {response['response']}")
print(f"Phase: {response['phase']}")

status = chat.get_status()
print(f"Session phase: {status['current_phase']}")
```

## Migration from Old APIs

If you were using the previous separate `chat` and `conversations` APIs:

### Old Chat API → New Unified API
- `POST /api/v1/chat` → **No change** (same endpoint, enhanced response)
- `GET /api/v1/chat/{session_id}/status` → `GET /api/v1/sessions/{session_id}/status` (enhanced response)
- `DELETE /api/v1/chat/{session_id}` → `GET /api/v1/sessions/{session_id}` (same functionality)

### Old Conversations API → New Unified API  
- `POST /api/v1/conversations/{session_id}/message` → `POST /api/v1/sessions/{session_id}/message` (enhanced response)
- `GET /api/v1/conversations/{session_id}/status` → `GET /api/v1/sessions/{session_id}/status` (enhanced response)

The new unified API maintains backward compatibility while providing enhanced features and more consistent response formats.