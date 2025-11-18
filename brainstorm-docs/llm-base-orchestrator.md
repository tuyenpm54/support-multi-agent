# ORCHESTRATOR AGENT - SIMPLIFIED WITH LLM-BASED DECISION

## KIẾN TRÚC ĐƠN GIẢN HÓA: LLM AS DECISION ENGINE

**Version:** 2.0  
**Date:** November 10, 2024

---

## 1. TỔNG QUAN KIẾN TRÚC MỚI

### 1.1 Core Principle: LLM-Driven Decision Making

```
User Input + Context → LLM → Structured JSON Decision → Execute
                       (1 call)   (clear schema)
```


## 2. SESSION STATE (Unchanged)

```python
from enum import Enum
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel

class SessionPhase(Enum):
    IDLE = "idle"
    CLASSIFY = "classify"
    REQUIRED_INFO = "required_info"
    VALIDATE = "validate"
    FIX = "fix"
    COMPLETE = "complete"
    WAIT_USER_PROVIDE_INFO = "wait_user_provide_info"
    WAIT_USER_CONFIRM = "wait_user_confirm"
    WAIT_USER_SELECT = "wait_user_select"
    WAIT_USER_CLARIFY = "wait_user_clarify"

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task(BaseModel):
    task_id: str
    task_type: str  # "error_resolution", "feature_usage"
    status: TaskStatus
    current_phase: SessionPhase
    current_agent: Optional[str] = None
    
    # Context
    classification: Optional[Dict] = None
    required_info: Optional[Dict] = None
    validation: Optional[Dict] = None
    fix: Optional[Dict] = None
    
    last_user_message: str
    waiting_for: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime

class SessionState(BaseModel):
    session_id: str
    user_id: str
    
    # Tasks
    active_task: Optional[Task] = None
    pending_tasks: List[Task] = []
    completed_tasks: List[Task] = []
    
    # History
    conversation_history: List[Dict] = []
    timeline: List[Dict] = []
    
    # Context
    user_metadata: Dict
    last_activity: datetime
```

---

## 3. LLM DECISION REQUEST SCHEMA

### 3.1 Decision Response Schema

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional, List

class OrchestratorDecision(BaseModel):
    """
    Structured decision output from LLM
    """
    
    # Primary decision
    intent_type: Literal[
        "new_request",
        "continuation", 
        "control_command",
        "ambiguous"
    ] = Field(description="Type of user intent")
    
    # Action to take
    action: Literal[
        "create_new_task",
        "forward_to_current_agent",
        "ask_task_switch_confirmation",
        "auto_switch_task",
        "cancel_task",
        "restart_task",
        "ask_clarification",
        "escalate"
    ] = Field(description="Action orchestrator should take")
    
    # Task details (if creating new)
    new_task_type: Optional[Literal["error_resolution", "feature_usage"]] = None
    target_agent: Optional[str] = None  # "classifier_agent", "knowledge_agent", etc.
    
    # Message to user (if needed)
    user_message: Optional[str] = Field(
        None,
        description="Message to show user (for clarification, confirmation, etc.)"
    )
    
    # Options for user (if asking selection)
    user_options: Optional[List[str]] = None
    
    # Reasoning
    confidence: float = Field(
        ge=0.0, 
        le=1.0,
        description="Confidence in this decision (0-1)"
    )
    reasoning: str = Field(
        description="Brief explanation of why this decision was made"
    )
    
    # Additional context
    should_pause_current_task: bool = False
    should_resume_task_after: Optional[str] = None  # task_id to resume
    priority: Literal["low", "medium", "high", "critical"] = "medium"
```

---

## 4. ORCHESTRATOR SIMPLIFIED

### 4.1 Main Process Flow

```python
class Orchestrator:
    def __init__(self, llm_client, agent_registry):
        self.llm = llm_client
        self.agents = agent_registry
    
    async def process_user_input(
        self, 
        user_message: str, 
        session_state: SessionState
    ) -> Dict:
        """
        Main entry point - simplified to 3 steps
        """
        
        # STEP 1: Get decision from LLM
        decision = await self.get_llm_decision(
            user_message=user_message,
            session_state=session_state
        )
        
        # STEP 2: Execute decision
        result = await self.execute_decision(
            decision=decision,
            session_state=session_state
        )
        
        # STEP 3: Update state
        self.update_session_state(
            session_state=session_state,
            decision=decision,
            result=result
        )
        
        return result
```

### 4.2 LLM Decision Request

```python
async def get_llm_decision(
    self,
    user_message: str,
    session_state: SessionState
) -> OrchestratorDecision:
    """
    Single LLM call to determine what to do
    """
    
    # Build context for LLM
    context = self._build_context(session_state)
    
    # Create prompt
    system_prompt = self._get_system_prompt()
    user_prompt = self._build_user_prompt(user_message, context)
    
    # Call LLM with structured output
    response = await self.llm.generate(
        system=system_prompt,
        user=user_prompt,
        response_format=OrchestratorDecision,
        temperature=0.3  # Lower for consistent decisions
    )
    
    # Parse response
    decision = OrchestratorDecision.model_validate_json(response)
    
    # Log decision
    self._log_decision(decision, session_state)
    
    return decision

def _build_context(self, session_state: SessionState) -> Dict:
    """
    Build context object for LLM
    """
    
    context = {
        "session_id": session_state.session_id,
        "user_id": session_state.user_id,
        "has_active_task": session_state.active_task is not None,
        "conversation_turns": len(session_state.conversation_history)
    }
    
    # Active task info
    if session_state.active_task:
        task = session_state.active_task
        context["active_task"] = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status.value,
            "current_phase": task.current_phase.value,
            "current_agent": task.current_agent,
            "waiting_for": task.waiting_for,
            "last_user_message": task.last_user_message,
            "is_critical_phase": task.current_phase in [
                SessionPhase.VALIDATE, 
                SessionPhase.FIX
            ]
        }
    
    # Pending tasks
    if session_state.pending_tasks:
        context["pending_tasks_count"] = len(session_state.pending_tasks)
    
    # Recent conversation
    if session_state.conversation_history:
        context["recent_messages"] = session_state.conversation_history[-3:]
    
    # User metadata
    context["user_metadata"] = session_state.user_metadata
    
    return context

def _get_system_prompt(self) -> str:
    """
    System prompt defining orchestrator behavior
    """
    
    return """You are an Orchestrator Agent for a customer support system.

Your role is to analyze user input in context and decide the next action.

DECISION RULES:

1. **New Request Detection:**
   - User reports error → intent_type: "new_request", new_task_type: "error_resolution"
   - User asks how to use feature → intent_type: "new_request", new_task_type: "feature_usage"
   - If NO active task → action: "create_new_task"
   - If HAS active task → check conflict (see below)

2. **Continuation Detection:**
   - Active task exists AND in waiting state (wait_user_*) → intent_type: "continuation"
   - User provides info/confirmation/selection → action: "forward_to_current_agent"

3. **Control Commands:**
   - User says cancel/stop → intent_type: "control_command", action: "cancel_task"
   - User says restart → intent_type: "control_command", action: "restart_task"

4. **Task Conflict Handling:**
   - New request while active task exists:
     * IF active task in CRITICAL phase (validate, fix) → action: "ask_task_switch_confirmation"
     * IF active task in EARLY phase (classify) → action: "auto_switch_task"
     * IF active task waiting >5 min → action: "auto_switch_task"

5. **Ambiguous Cases:**
   - Cannot determine intent → intent_type: "ambiguous", action: "ask_clarification"

OUTPUT FORMAT:
Return ONLY valid JSON matching OrchestratorDecision schema.
Be concise in reasoning (max 50 words).

IMPORTANT:
- Always consider current context
- Prioritize user experience
- Be conservative with auto-switches during critical phases
- Provide clear user_message when asking for input
"""

def _build_user_prompt(
    self, 
    user_message: str, 
    context: Dict
) -> str:
    """
    Build user prompt with context
    """
    
    prompt_parts = []
    
    # Current context
    prompt_parts.append("=== CURRENT CONTEXT ===")
    
    if context.get("has_active_task"):
        task_info = context["active_task"]
        prompt_parts.append(f"""
Active Task:
- Task ID: {task_info['task_id']}
- Type: {task_info['task_type']}
- Phase: {task_info['current_phase']}
- Status: {task_info['status']}
- Current Agent: {task_info['current_agent']}
- Waiting For: {task_info['waiting_for']}
- Is Critical Phase: {task_info['is_critical_phase']}
- Last User Message: "{task_info['last_user_message']}"
""")
    else:
        prompt_parts.append("Active Task: None")
    
    # Pending tasks
    if context.get("pending_tasks_count"):
        prompt_parts.append(f"Pending Tasks: {context['pending_tasks_count']}")
    
    # Recent conversation
    if context.get("recent_messages"):
        prompt_parts.append("\n=== RECENT CONVERSATION ===")
        for msg in context["recent_messages"]:
            role = msg["role"]
            content = msg["content"]
            prompt_parts.append(f"{role}: {content}")
    
    # New user message
    prompt_parts.append("\n=== NEW USER MESSAGE ===")
    prompt_parts.append(f'User: "{user_message}"')
    
    # Request
    prompt_parts.append("\n=== YOUR TASK ===")
    prompt_parts.append("""
Analyze the user message in context and decide:
1. What is the user's intent?
2. What action should the orchestrator take?
3. What message (if any) should be shown to user?

Return your decision as JSON following OrchestratorDecision schema.
""")
    
    return "\n".join(prompt_parts)
```

---

## 5. DECISION EXECUTION

### 5.1 Execute Decision

```python
async def execute_decision(
    self,
    decision: OrchestratorDecision,
    session_state: SessionState
) -> Dict:
    """
    Execute the decision made by LLM
    """
    
    action = decision.action
    
    # ========================================
    # CREATE NEW TASK
    # ========================================
    if action == "create_new_task":
        # Create task object
        new_task = Task(
            task_id=f"TASK_{self._generate_id()}",
            task_type=decision.new_task_type,
            status=TaskStatus.IN_PROGRESS,
            current_phase=SessionPhase.CLASSIFY if decision.new_task_type == "error_resolution" else SessionPhase.REQUIRED_INFO,
            current_agent=decision.target_agent or self._get_initial_agent(decision.new_task_type),
            last_user_message=session_state.conversation_history[-1]["content"],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Set as active
        session_state.active_task = new_task
        
        # Forward to agent
        agent = self.agents.get(new_task.current_agent)
        result = await agent.process(
            message=session_state.conversation_history[-1]["content"],
            task_state=new_task,
            session_context=session_state
        )
        
        return result
    
    # ========================================
    # FORWARD TO CURRENT AGENT
    # ========================================
    elif action == "forward_to_current_agent":
        if not session_state.active_task:
            raise ValueError("No active task to forward to")
        
        agent = self.agents.get(session_state.active_task.current_agent)
        
        result = await agent.process(
            message=session_state.conversation_history[-1]["content"],
            task_state=session_state.active_task,
            session_context=session_state
        )
        
        return result
    
    # ========================================
    # ASK TASK SWITCH CONFIRMATION
    # ========================================
    elif action == "ask_task_switch_confirmation":
        # Update state to waiting
        session_state.active_task.current_phase = SessionPhase.WAIT_USER_SELECT
        session_state.active_task.waiting_for = "task_switch_decision"
        
        return {
            "type": "question",
            "message": decision.user_message,
            "options": decision.user_options or ["1", "2", "3"],
            "requires_user_action": True
        }
    
    # ========================================
    # AUTO SWITCH TASK
    # ========================================
    elif action == "auto_switch_task":
        # Pause current task
        if session_state.active_task:
            session_state.active_task.status = TaskStatus.PAUSED
            session_state.pending_tasks.append(session_state.active_task)
        
        # Create new task
        new_task = Task(
            task_id=f"TASK_{self._generate_id()}",
            task_type=decision.new_task_type,
            status=TaskStatus.IN_PROGRESS,
            current_phase=SessionPhase.CLASSIFY if decision.new_task_type == "error_resolution" else SessionPhase.REQUIRED_INFO,
            current_agent=decision.target_agent or self._get_initial_agent(decision.new_task_type),
            last_user_message=session_state.conversation_history[-1]["content"],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        session_state.active_task = new_task
        
        # Forward to agent
        agent = self.agents.get(new_task.current_agent)
        result = await agent.process(
            message=session_state.conversation_history[-1]["content"],
            task_state=new_task,
            session_context=session_state
        )
        
        # Add notification
        if decision.user_message:
            result["notification"] = decision.user_message
        
        return result
    
    # ========================================
    # CANCEL TASK
    # ========================================
    elif action == "cancel_task":
        if session_state.active_task:
            session_state.active_task.status = TaskStatus.CANCELLED
            session_state.completed_tasks.append(session_state.active_task)
            session_state.active_task = None
        
        return {
            "type": "info",
            "message": decision.user_message or "Đã hủy yêu cầu hiện tại."
        }
    
    # ========================================
    # RESTART TASK
    # ========================================
    elif action == "restart_task":
        if session_state.active_task:
            # Reset task to initial phase
            session_state.active_task.current_phase = SessionPhase.CLASSIFY
            session_state.active_task.current_agent = "classifier_agent"
            session_state.active_task.classification = None
            session_state.active_task.required_info = None
            session_state.active_task.validation = None
            session_state.active_task.fix = None
            session_state.active_task.updated_at = datetime.now()
            
            # Forward to classifier
            agent = self.agents.get("classifier_agent")
            result = await agent.process(
                message=session_state.active_task.last_user_message,
                task_state=session_state.active_task,
                session_context=session_state
            )
            
            return result
        
        return {
            "type": "info",
            "message": "Không có task nào để restart."
        }
    
    # ========================================
    # ASK CLARIFICATION
    # ========================================
    elif action == "ask_clarification":
        if session_state.active_task:
            session_state.active_task.current_phase = SessionPhase.WAIT_USER_CLARIFY
            session_state.active_task.waiting_for = "clarification"
        
        return {
            "type": "question",
            "message": decision.user_message,
            "requires_user_action": True
        }
    
    # ========================================
    # ESCALATE
    # ========================================
    elif action == "escalate":
        return await self._escalate_to_human(
            reason=decision.reasoning,
            session_state=session_state
        )
    
    # ========================================
    # UNKNOWN ACTION
    # ========================================
    else:
        raise ValueError(f"Unknown action: {action}")

def _get_initial_agent(self, task_type: str) -> str:
    """
    Determine initial agent based on task type
    """
    if task_type == "error_resolution":
        return "classifier_agent"
    elif task_type == "feature_usage":
        return "knowledge_agent"
    else:
        return "classifier_agent"  # Default
```

---

## 6. EXAMPLE SCENARIOS

### 6.1 Scenario 1: Simple New Request

**Input:**
```json
{
  "user_message": "Món không hiển thị trong menu",
  "context": {
    "has_active_task": false,
    "conversation_turns": 1
  }
}
```

**LLM Decision Output:**
```json
{
  "intent_type": "new_request",
  "action": "create_new_task",
  "new_task_type": "error_resolution",
  "target_agent": "classifier_agent",
  "user_message": null,
  "confidence": 0.95,
  "reasoning": "User reports error. No active task. Create new error resolution task."
}
```

**Orchestrator Action:**
- Creates Task-001
- Forwards to Classifier Agent
- Classifier proceeds with classification

---

### 6.2 Scenario 2: Continuation (Providing Info)

**Input:**
```json
{
  "user_message": "Món Phở bò, kho chi nhánh 1",
  "context": {
    "has_active_task": true,
    "active_task": {
      "task_id": "TASK_001",
      "task_type": "error_resolution",
      "current_phase": "wait_user_provide_info",
      "current_agent": "required_info_agent",
      "waiting_for": "info_provision",
      "last_user_message": "Món không hiển thị"
    }
  }
}
```

**LLM Decision Output:**
```json
{
  "intent_type": "continuation",
  "action": "forward_to_current_agent",
  "target_agent": "required_info_agent",
  "confidence": 0.98,
  "reasoning": "Active task waiting for info. User provides info. Forward to current agent."
}
```

**Orchestrator Action:**
- Forwards to Required Info Agent
- Agent processes the provided information

---

### 6.3 Scenario 3: Task Conflict (Critical Phase)

**Input:**
```json
{
  "user_message": "Tôi muốn hỏi về báo cáo",
  "context": {
    "has_active_task": true,
    "active_task": {
      "task_id": "TASK_001",
      "task_type": "error_resolution",
      "current_phase": "fix",
      "current_agent": "fix_agent",
      "is_critical_phase": true,
      "last_user_message": "Món không hiển thị"
    }
  }
}
```

**LLM Decision Output:**
```json
{
  "intent_type": "new_request",
  "action": "ask_task_switch_confirmation",
  "new_task_type": "feature_usage",
  "user_message": "Bạn đang có yêu cầu đang xử lý:\n• Khắc phục lỗi 'Món không hiển thị'\n• Trạng thái: Đang thực hiện sửa lỗi\n\nBạn vừa gửi yêu cầu mới:\n• Hỏi về báo cáo\n\nBạn muốn:\n1️⃣ Tiếp tục yêu cầu hiện tại (khuyến nghị)\n2️⃣ Chuyển sang yêu cầu mới\n3️⃣ Hủy yêu cầu hiện tại\n\nChọn 1, 2 hoặc 3.",
  "user_options": ["1", "2", "3"],
  "confidence": 0.92,
  "reasoning": "New request during critical phase (fix). Ask user for confirmation."
}
```

**Orchestrator Action:**
- Presents options to user
- Waits for user decision
- Will process based on user's choice

---

### 6.4 Scenario 4: Task Conflict (Early Phase)

**Input:**
```json
{
  "user_message": "Làm sao thêm món mới?",
  "context": {
    "has_active_task": true,
    "active_task": {
      "task_id": "TASK_001",
      "task_type": "error_resolution",
      "current_phase": "classify",
      "current_agent": "classifier_agent",
      "is_critical_phase": false,
      "last_user_message": "Món không hiển thị"
    }
  }
}
```

**LLM Decision Output:**
```json
{
  "intent_type": "new_request",
  "action": "auto_switch_task",
  "new_task_type": "feature_usage",
  "target_agent": "knowledge_agent",
  "user_message": "Đang xử lý yêu cầu mới. Yêu cầu trước đã tạm dừng.",
  "should_pause_current_task": true,
  "confidence": 0.90,
  "reasoning": "New request while task in early phase (classify). Safe to auto-switch."
}
```

**Orchestrator Action:**
- Pauses Task-001
- Creates Task-002 (feature_usage)
- Forwards to Knowledge Agent
- Notifies user about switch

---

### 6.5 Scenario 5: Ambiguous Input

**Input:**
```json
{
  "user_message": "OK",
  "context": {
    "has_active_task": true,
    "active_task": {
      "task_id": "TASK_001",
      "current_phase": "classify",
      "waiting_for": null
    },
    "recent_messages": [
      {"role": "user", "content": "Món không hiển thị"},
      {"role": "assistant", "content": "Đang phân loại vấn đề..."}
    ]
  }
}
```

**LLM Decision Output:**
```json
{
  "intent_type": "ambiguous",
  "action": "ask_clarification",
  "user_message": "Xin lỗi, tôi không hiểu ý bạn. Bạn có thể nói rõ hơn không?\n\nBạn muốn:\n- Tiếp tục với vấn đề 'Món không hiển thị'\n- Yêu cầu khác\n- Hủy yêu cầu hiện tại",
  "confidence": 0.60,
  "reasoning": "User says 'OK' but not in waiting state. Ambiguous intent. Need clarification."
}
```

**Orchestrator Action:**
- Asks for clarification
- Waits for clearer user input

---

## 7. IMPLEMENTATION CODE

### 7.1 Complete Orchestrator Class

```python
from typing import Dict, Optional
from datetime import datetime
import json

class Orchestrator:
    def __init__(self, llm_client, agent_registry, logger):
        self.llm = llm_client
        self.agents = agent_registry
        self.logger = logger
    
    async def process_user_input(
        self, 
        user_message: str, 
        session_state: SessionState
    ) -> Dict:
        """
        Main entry point
        """
        
        try:
            # Add message to conversation history
            session_state.conversation_history.append({
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now().isoformat()
            })
            
            # Get LLM decision
            decision = await self.get_llm_decision(
                user_message=user_message,
                session_state=session_state
            )
            
            # Execute decision
            result = await self.execute_decision(
                decision=decision,
                session_state=session_state
            )
            
            # Update state
            self.update_session_state(
                session_state=session_state,
                decision=decision,
                result=result
            )
            
            # Add response to history
            session_state.conversation_history.append({
                "role": "assistant",
                "content": result.get("message", ""),
                "timestamp": datetime.now().isoformat()
            })
            
            # Update timeline
            session_state.timeline.append({
                "action": decision.action,
                "intent_type": decision.intent_type,
                "confidence": decision.confidence,
                "timestamp": datetime.now().isoformat()
            })
            
            return result
        
        except Exception as e:
            self.logger.error(f"Orchestrator error: {e}")
            return await self._handle_error(e, session_state)
    
    async def get_llm_decision(
        self,
        user_message: str,
        session_state: SessionState
    ) -> OrchestratorDecision:
        """
        Get decision from LLM
        """
        
        context = self._build_context(session_state)
        system_prompt = self._get_system_prompt()
        user_prompt = self._build_user_prompt(user_message, context)
        
        # Call LLM
        response = await self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "orchestrator_decision",
                    "schema": OrchestratorDecision.model_json_schema()
                }
            },
            temperature=0.3,
            max_tokens=500
        )
        
        # Parse and validate
        decision = OrchestratorDecision.model_validate_json(response)
        
        # Log
        self.logger.info(f"LLM Decision: {decision.model_dump_json()}")
        
        return decision
    
    def update_session_state(
        self,
        session_state: SessionState,
        decision: OrchestratorDecision,
        result: Dict
    ):
        """
        Update session state after execution
        """
        
        session_state.last_activity = datetime.now()
        
        # Update active task if exists
        if session_state.active_task:
            session_state.active_task.updated_at = datetime.now()
    
    async def _handle_error(
        self, 
        error: Exception, 
        session_state: SessionState
    ) -> Dict:
        """
        Handle errors gracefully
        """
        
        self.logger.error(f"Error in orchestrator: {error}")
        
        return {
            "type": "error",
            "message": "Xin lỗi, có lỗi xảy ra. Vui lòng thử lại hoặc liên hệ support.",
            "error": str(error)
        }
    
    def _generate_id(self) -> str:
        """Generate unique ID"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    # [_build_context, _get_system_prompt, _build_user_prompt methods from earlier]
    # [execute_decision method from earlier]
```

---

## 8. PROMPT OPTIMIZATION TIPS

### 8.1 System Prompt Best Practices

```
✅ DO:
- Be specific about output format (JSON schema)
- Provide clear decision rules
- Include examples of edge cases
- Set clear priorities (user experience first)
- Limit reasoning length (avoid verbosity)

❌ DON'T:
- Over-complicate with too many rules
- Leave ambiguous cases unhandled
- Forget to specify confidence scoring
- Omit context about system capabilities
```

### 8.2 Prompt Versioning

```python
SYSTEM_PROMPTS = {
    "v1.0": "Original prompt...",
    "v1.1": "Improved handling of task conflicts...",
    "v1.2": "Better ambiguity detection..."
}

def _get_system_prompt(self, version="v1.2"):
    return SYSTEM_PROMPTS[version]
```

---

## 9. MONITORING & DEBUGGING

### 9.1 Log Decision Quality

```python
async def _log_decision(
    self,
    decision: OrchestratorDecision,
    session_state: SessionState
):
    """
    Log decision for monitoring and debugging
    """
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_state.session_id,
        "user_id": session_state.user_id,
        
        # Decision details
        "intent_type": decision.intent_type,
        "action": decision.action,
        "confidence": decision.confidence,
        "reasoning": decision.reasoning,
        
        # Context
        "had_active_task": session_state.active_task is not None,
        "active_task_phase": session_state.active_task.current_phase.value if session_state.active_task else None,
        "conversation_turns": len(session_state.conversation_history),
        
        # Additional
        "new_task_type": decision.new_task_type,
        "target_agent": decision.target_agent,
        "priority": decision.priority
    }
    
    # Store in metrics database
    await self.metrics_db.insert("orchestrator_decisions", log_entry)
    
    # Track metrics
    self.metrics.increment(
        "orchestrator_decisions_total",
        labels={
            "intent_type": decision.intent_type,
            "action": decision.action
        }
    )
    
    if decision.confidence < 0.7:
        self.metrics.increment("orchestrator_low_confidence_decisions")
```

### 9.2 A/B Testing Prompts

```python
class Orchestrator:
    def __init__(self, llm_client, agent_registry, logger, experiment_config=None):
        self.llm = llm_client
        self.agents = agent_registry
        self.logger = logger
        self.experiment_config = experiment_config or {}
    
    def _get_system_prompt(self) -> str:
        """
        Get system prompt with A/B testing support
        """
        
        # Check if user is in experiment
        if self.experiment_config.get("enabled"):
            variant = self._get_user_variant()
            
            if variant == "control":
                return SYSTEM_PROMPTS["v1.2"]  # Current version
            elif variant == "test_a":
                return SYSTEM_PROMPTS["v1.3_test_a"]  # New variant A
            elif variant == "test_b":
                return SYSTEM_PROMPTS["v1.3_test_b"]  # New variant B
        
        return SYSTEM_PROMPTS["v1.2"]  # Default
    
    def _get_user_variant(self) -> str:
        """
        Assign user to experiment variant
        """
        # Simple hash-based assignment
        import hashlib
        
        hash_val = int(hashlib.md5(
            self.session_state.user_id.encode()
        ).hexdigest(), 16)
        
        if hash_val % 3 == 0:
            return "control"
        elif hash_val % 3 == 1:
            return "test_a"
        else:
            return "test_b"
```

### 9.3 Decision Quality Metrics

```python
class OrchestratorMetrics:
    """
    Track orchestrator performance
    """
    
    def __init__(self):
        self.decisions = []
    
    async def track_decision_outcome(
        self,
        decision: OrchestratorDecision,
        outcome: Dict
    ):
        """
        Track if decision led to successful outcome
        """
        
        metric = {
            "decision": decision.model_dump(),
            "outcome": outcome,
            "successful": outcome.get("status") == "success",
            "user_satisfied": outcome.get("user_feedback") in ["positive", "thumbs_up"],
            "required_escalation": outcome.get("escalated", False),
            "timestamp": datetime.now()
        }
        
        self.decisions.append(metric)
        
        # Calculate metrics
        if len(self.decisions) >= 100:
            await self._calculate_metrics()
    
    async def _calculate_metrics(self):
        """
        Calculate aggregate metrics
        """
        
        recent = self.decisions[-100:]
        
        # Success rate by intent type
        by_intent = {}
        for d in recent:
            intent = d["decision"]["intent_type"]
            if intent not in by_intent:
                by_intent[intent] = {"total": 0, "successful": 0}
            
            by_intent[intent]["total"] += 1
            if d["successful"]:
                by_intent[intent]["successful"] += 1
        
        for intent, stats in by_intent.items():
            success_rate = stats["successful"] / stats["total"]
            print(f"Intent '{intent}': {success_rate:.2%} success rate")
        
        # Average confidence by outcome
        successful = [d for d in recent if d["successful"]]
        failed = [d for d in recent if not d["successful"]]
        
        avg_conf_success = sum(d["decision"]["confidence"] for d in successful) / len(successful)
        avg_conf_fail = sum(d["decision"]["confidence"] for d in failed) / len(failed) if failed else 0
        
        print(f"Avg confidence (successful): {avg_conf_success:.2f}")
        print(f"Avg confidence (failed): {avg_conf_fail:.2f}")
```

---

## 10. ERROR HANDLING & FALLBACKS

### 10.1 LLM Call Failures

```python
async def get_llm_decision(
    self,
    user_message: str,
    session_state: SessionState
) -> OrchestratorDecision:
    """
    Get decision with retry and fallback
    """
    
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            context = self._build_context(session_state)
            system_prompt = self._get_system_prompt()
            user_prompt = self._build_user_prompt(user_message, context)
            
            response = await self.llm.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "orchestrator_decision",
                        "schema": OrchestratorDecision.model_json_schema()
                    }
                },
                temperature=0.3,
                max_tokens=500,
                timeout=10  # 10 second timeout
            )
            
            decision = OrchestratorDecision.model_validate_json(response)
            return decision
        
        except TimeoutError:
            self.logger.warning(f"LLM timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                # Final fallback
                return self._fallback_decision(user_message, session_state)
        
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON from LLM: {e}")
            if attempt < max_retries - 1:
                continue
            else:
                return self._fallback_decision(user_message, session_state)
        
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
            else:
                return self._fallback_decision(user_message, session_state)

def _fallback_decision(
    self,
    user_message: str,
    session_state: SessionState
) -> OrchestratorDecision:
    """
    Simple rule-based fallback when LLM fails
    """
    
    # If waiting for user input, assume continuation
    if session_state.active_task and \
       session_state.active_task.current_phase.value.startswith("wait_user"):
        return OrchestratorDecision(
            intent_type="continuation",
            action="forward_to_current_agent",
            target_agent=session_state.active_task.current_agent,
            confidence=0.6,
            reasoning="Fallback: Waiting state detected, forwarding to current agent"
        )
    
    # If no active task, escalate
    elif not session_state.active_task:
        return OrchestratorDecision(
            intent_type="ambiguous",
            action="escalate",
            confidence=0.5,
            reasoning="Fallback: LLM unavailable, escalating to human"
        )
    
    # Default: ask clarification
    else:
        return OrchestratorDecision(
            intent_type="ambiguous",
            action="ask_clarification",
            user_message="Xin lỗi, tôi đang gặp sự cố. Bạn có thể nói rõ hơn không?",
            confidence=0.5,
            reasoning="Fallback: LLM unavailable, asking for clarification"
        )
```

### 10.2 Invalid Decision Handling

```python
def _validate_decision(
    self,
    decision: OrchestratorDecision,
    session_state: SessionState
) -> bool:
    """
    Validate decision makes sense in current context
    """
    
    # If action is forward but no active task
    if decision.action == "forward_to_current_agent" and \
       not session_state.active_task:
        self.logger.warning("Invalid decision: forward with no active task")
        return False
    
    # If creating new task but no task type specified
    if decision.action == "create_new_task" and \
       not decision.new_task_type:
        self.logger.warning("Invalid decision: create task without type")
        return False
    
    # If asking confirmation but no message
    if decision.action == "ask_task_switch_confirmation" and \
       not decision.user_message:
        self.logger.warning("Invalid decision: ask confirmation without message")
        return False
    
    return True

async def get_llm_decision(self, user_message, session_state):
    # ... [LLM call code] ...
    
    decision = OrchestratorDecision.model_validate_json(response)
    
    # Validate decision
    if not self._validate_decision(decision, session_state):
        self.logger.error("Invalid decision from LLM, using fallback")
        decision = self._fallback_decision(user_message, session_state)
    
    return decision
```

---

## 11. TESTING ORCHESTRATOR

### 11.1 Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def orchestrator():
    llm_client = AsyncMock()
    agent_registry = MagicMock()
    logger = MagicMock()
    
    return Orchestrator(llm_client, agent_registry, logger)

@pytest.fixture
def empty_session():
    return SessionState(
        session_id="TEST_SESSION_001",
        user_id="TEST_USER_001",
        active_task=None,
        pending_tasks=[],
        completed_tasks=[],
        conversation_history=[],
        timeline=[],
        user_metadata={"role": "staff"},
        last_activity=datetime.now()
    )

@pytest.mark.asyncio
async def test_new_request_no_active_task(orchestrator, empty_session):
    """
    Test: New request when no active task
    Expected: Create new task
    """
    
    # Mock LLM response
    orchestrator.llm.generate = AsyncMock(return_value=json.dumps({
        "intent_type": "new_request",
        "action": "create_new_task",
        "new_task_type": "error_resolution",
        "target_agent": "classifier_agent",
        "user_message": None,
        "confidence": 0.95,
        "reasoning": "New error report, no active task"
    }))
    
    # Mock classifier agent
    orchestrator.agents.get = MagicMock(return_value=AsyncMock())
    orchestrator.agents.get.return_value.process = AsyncMock(return_value={
        "type": "info",
        "message": "Đang phân loại vấn đề..."
    })
    
    # Process input
    result = await orchestrator.process_user_input(
        user_message="Món không hiển thị",
        session_state=empty_session
    )
    
    # Assertions
    assert empty_session.active_task is not None
    assert empty_session.active_task.task_type == "error_resolution"
    assert empty_session.active_task.current_agent == "classifier_agent"
    assert len(empty_session.conversation_history) == 2  # user + assistant

@pytest.mark.asyncio
async def test_continuation_in_waiting_state(orchestrator):
    """
    Test: User provides info when in waiting state
    Expected: Forward to current agent
    """
    
    # Setup session with active task in waiting state
    session = SessionState(
        session_id="TEST_SESSION_002",
        user_id="TEST_USER_001",
        active_task=Task(
            task_id="TASK_001",
            task_type="error_resolution",
            status=TaskStatus.IN_PROGRESS,
            current_phase=SessionPhase.WAIT_USER_PROVIDE_INFO,
            current_agent="required_info_agent",
            waiting_for="info_provision",
            last_user_message="Món không hiển thị",
            created_at=datetime.now(),
            updated_at=datetime.now()
        ),
        pending_tasks=[],
        completed_tasks=[],
        conversation_history=[
            {"role": "user", "content": "Món không hiển thị"},
            {"role": "assistant", "content": "Món nào? Kho nào?"}
        ],
        timeline=[],
        user_metadata={},
        last_activity=datetime.now()
    )
    
    # Mock LLM response
    orchestrator.llm.generate = AsyncMock(return_value=json.dumps({
        "intent_type": "continuation",
        "action": "forward_to_current_agent",
        "target_agent": "required_info_agent",
        "confidence": 0.98,
        "reasoning": "Waiting for info, user provides info"
    }))
    
    # Mock required_info agent
    orchestrator.agents.get = MagicMock(return_value=AsyncMock())
    orchestrator.agents.get.return_value.process = AsyncMock(return_value={
        "type": "info",
        "message": "Đang xử lý..."
    })
    
    # Process input
    result = await orchestrator.process_user_input(
        user_message="Món Phở bò, kho chi nhánh 1",
        session_state=session
    )
    
    # Assertions
    orchestrator.agents.get.assert_called_with("required_info_agent")
    assert len(session.conversation_history) == 4  # 2 previous + 2 new

@pytest.mark.asyncio
async def test_task_conflict_critical_phase(orchestrator):
    """
    Test: New request during critical phase
    Expected: Ask user for confirmation
    """
    
    session = SessionState(
        session_id="TEST_SESSION_003",
        user_id="TEST_USER_001",
        active_task=Task(
            task_id="TASK_001",
            task_type="error_resolution",
            status=TaskStatus.IN_PROGRESS,
            current_phase=SessionPhase.FIX,
            current_agent="fix_agent",
            last_user_message="Món không hiển thị",
            created_at=datetime.now(),
            updated_at=datetime.now()
        ),
        pending_tasks=[],
        completed_tasks=[],
        conversation_history=[],
        timeline=[],
        user_metadata={},
        last_activity=datetime.now()
    )
    
    # Mock LLM response
    orchestrator.llm.generate = AsyncMock(return_value=json.dumps({
        "intent_type": "new_request",
        "action": "ask_task_switch_confirmation",
        "new_task_type": "feature_usage",
        "user_message": "Bạn muốn chuyển sang yêu cầu mới không?",
        "user_options": ["1", "2", "3"],
        "confidence": 0.90,
        "reasoning": "New request during critical phase"
    }))
    
    # Process input
    result = await orchestrator.process_user_input(
        user_message="Làm sao thêm món mới?",
        session_state=session
    )
    
    # Assertions
    assert result["type"] == "question"
    assert "user_options" in result or "options" in result
    assert session.active_task.current_phase == SessionPhase.WAIT_USER_SELECT
```

### 11.2 Integration Tests

```python
@pytest.mark.asyncio
async def test_full_conversation_flow():
    """
    Test complete conversation flow
    """
    
    # Setup
    orchestrator = create_test_orchestrator()
    session = create_empty_session()
    
    # Turn 1: User reports error
    result1 = await orchestrator.process_user_input(
        "Món không hiển thị",
        session
    )
    assert session.active_task is not None
    assert session.active_task.task_type == "error_resolution"
    
    # Turn 2: Agent asks for info
    # (Simulate agent response setting waiting state)
    session.active_task.current_phase = SessionPhase.WAIT_USER_PROVIDE_INFO
    
    result2 = await orchestrator.process_user_input(
        "Món Phở bò, kho chi nhánh 1",
        session
    )
    # Should forward to agent
    
    # Turn 3: Agent asks for selection
    session.active_task.current_phase = SessionPhase.WAIT_USER_SELECT
    
    result3 = await orchestrator.process_user_input(
        "Chọn món 1",
        session
    )
    # Should forward selection
    
    # Turn 4: Agent asks for confirmation
    session.active_task.current_phase = SessionPhase.WAIT_USER_CONFIRM
    
    result4 = await orchestrator.process_user_input(
        "Đồng ý",
        session
    )
    # Should proceed with fix
    
    # Verify flow
    assert len(session.timeline) >= 4
    assert len(session.conversation_history) >= 8
```

---

## 12. OPTIMIZATION TIPS

### 12.1 Reduce LLM Latency

```python
# Use smaller, faster models for decision-making
async def get_llm_decision(self, user_message, session_state):
    # Use Claude Haiku for orchestration (faster, cheaper)
    response = await self.llm.generate(
        messages=[...],
        model="claude-3-haiku-20240307",  # Faster model
        max_tokens=300,  # Limit tokens
        temperature=0.2   # Lower for consistent decisions
    )
```

### 12.2 Cache Common Decisions

```python
from functools import lru_cache
import hashlib

class Orchestrator:
    def __init__(self, ...):
        # ...
        self.decision_cache = {}
    
    def _get_cache_key(self, user_message, context):
        """Generate cache key"""
        context_str = json.dumps(context, sort_keys=True)
        key = f"{user_message}:{context_str}"
        return hashlib.md5(key.encode()).hexdigest()
    
    async def get_llm_decision(self, user_message, session_state):
        context = self._build_context(session_state)
        cache_key = self._get_cache_key(user_message, context)
        
        # Check cache
        if cache_key in self.decision_cache:
            self.logger.info("Decision cache hit")
            return self.decision_cache[cache_key]
        
        # Call LLM
        decision = await self._call_llm(user_message, context)
        
        # Cache if high confidence
        if decision.confidence > 0.9:
            self.decision_cache[cache_key] = decision
        
        return decision
```

### 12.3 Parallel Processing (when applicable)

```python
async def process_user_input(self, user_message, session_state):
    # In some cases, can prepare context while calling LLM
    
    context_task = asyncio.create_task(
        self._build_context_async(session_state)
    )
    
    # Simple preprocessing can happen in parallel
    preprocessed = self._preprocess_message(user_message)
    
    context = await context_task
    
    decision = await self.get_llm_decision(preprocessed, context)
    # ...
```

---

## 13. SUMMARY

### 13.1 Key Benefits of LLM-Based Orchestrator

```
✅ SIMPLICITY
   - 1 LLM call replaces 100+ rules
   - Easier to understand and maintain
   - No complex if-else logic

✅ FLEXIBILITY
   - Handles edge cases naturally
   - Adapts to context automatically
   - Easy to add new capabilities (update prompt)

✅ ROBUSTNESS
   - Better understanding of user intent
   - Handles ambiguity well
   - Natural fallback to clarification

✅ MAINTAINABILITY
   - Update prompt instead of code
   - Version control for prompts
   - A/B test different strategies easily

✅ OBSERVABILITY
   - Clear reasoning in responses
   - Easy to debug (check LLM decision)
   - Track confidence scores
```

### 13.2 Trade-offs

```
⚠️ LATENCY
   - LLM call adds ~500-1000ms
   - Mitigation: Use faster models (Haiku), caching

⚠️ COST
   - Each decision costs ~$0.0001-0.0003
   - Mitigation: Cache common patterns, use smaller models

⚠️ DETERMINISM
   - Slightly less deterministic than rules
   - Mitigation: Low temperature, validation logic

⚠️ DEPENDENCY
   - Requires LLM API availability
   - Mitigation: Fallback to rule-based, retries
```

### 13.3 When to Use This Approach

```
✅ USE when:
- Complex decision logic
- Many edge cases
- Natural language understanding needed
- Rapid iteration required
- Context-aware decisions important

❌ DON'T USE when:
- Ultra-low latency required (<100ms)
- Determinism critical (regulatory)
- Very high volume (millions/day)
- Simple state machine sufficient
```

---

**End of Document**

Bạn muốn tôi tiếp tục với phần nào? Ví dụ:
- Chi tiết về prompt engineering cho từng scenario
- Integration với các agents khác
- Deployment & monitoring strategy
- Cost optimization techniques