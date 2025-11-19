from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class AgentPhase(str, Enum):
    CLASSIFY = "CLASSIFY"
    INFO_VALIDATION = "INFO_VALIDATION"
    RESOLUTION_LOOP = "RESOLUTION_LOOP"
    FIX = "FIX"
    COMPLETE = "COMPLETE"
    ESCALATE = "ESCALATE"


class SearchResult(BaseModel):
    issue_id: str
    title: str
    description: str
    category: str
    severity: str
    symptoms: Optional[Dict[str, Any]] = None
    diagnostic_questions: Optional[List[str]] = None
    tools: Optional[List[str]] = None
    similarity_score: float
    confidence_score: float
    created_at: datetime
    updated_at: datetime


class ClassificationResult(BaseModel):
    classified: bool = False
    confidence: float = 0.0
    suggested_category: str = "Unknown"
    suggested_severity: str = "Medium"
    matched_issue_id: Optional[str] = None
    matched_title: Optional[str] = None
    matched_description: Optional[str] = None
    similarity_score: float = 0.0
    diagnostic_questions: List[str] = Field(default_factory=list)
    potential_causes: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_tools: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    
    # Hierarchical resolution fields
    issue_type: Optional[str] = None  # 'general' or 'detailed'
    
    # Legacy fields for backward compatibility
    matched_issue: Optional[Dict[str, Any]] = None
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    reasoning: Optional[str] = None
    has_diagnostic_question: bool = Field(default=False)


class InfoValidationResult(BaseModel):
    """Combined result from information gathering and validation"""
    info_gathered: bool = False
    gathered_fields: Dict[str, Any] = Field(default_factory=dict)
    conversation_turns: int = 0
    
    # Validation results
    validation_result: str = "UNCERTAIN"  # CONFIRMED, NOT_FOUND, DIFFERENT_ISSUE, UNCERTAIN
    validation_confidence: float = 0.5
    ready_for_fix: bool = False
    validation_checks_performed: int = 0
    detected_issue: Optional[str] = None
    validation_reason: Optional[str] = None
    root_cause_confirmed: bool = False
    failed_checks: List[Dict[str, Any]] = Field(default_factory=list)


class FixResult(BaseModel):
    fix_result: str = "FAILED"  # SUCCESS, PARTIAL, FAILED, PERMISSION_DENIED
    actions_performed: List[Dict[str, Any]] = Field(default_factory=list)
    verification: Optional[Dict[str, Any]] = None
    rollback_available: bool = False
    rollback_token: Optional[str] = None
    rolled_back: bool = False


class TimelineEvent(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    phase: str
    agent: Optional[str] = None
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: Optional[int] = None


class SessionPhase(str, Enum):
    """Session phase states for LLM-based orchestrator"""
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


class TaskStatus(str, Enum):
    """Task status states for LLM-based orchestrator"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Task types for LLM-based orchestrator"""
    ERROR_RESOLUTION = "error_resolution"
    FEATURE_USAGE = "feature_usage"
    GENERAL_INQUIRY = "general_inquiry"
    ESCALATION = "escalation"


class OrchestratorDecision(BaseModel):
    """
    Structured decision output from LLM for enhanced orchestration
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
    new_task_type: Optional[Literal["error_resolution", "feature_usage", "general_inquiry"]] = None
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
    
    # Enhanced context
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    conversation_flow: Optional[str] = None  # "smooth", "interrupted", "new_topic"
    intent_evolution: Optional[str] = None  # "same", "refined", "changed"
    emotional_state: Optional[str] = None  # "neutral", "frustrated", "satisfied"
    
    # Timing and performance
    processing_time_ms: Optional[int] = None
    cache_hit: bool = False


class Task(BaseModel):
    """
    Task model for LLM-based orchestrator
    """
    task_id: str
    task_type: TaskType
    status: TaskStatus
    current_phase: SessionPhase
    current_agent: Optional[str] = None
    
    # Context
    classification: Optional[Dict] = None
    required_info: Optional[Dict] = None
    validation: Optional[Dict] = None
    fix: Optional[Dict] = None
    
    # User interaction
    last_user_message: str
    waiting_for: Optional[str] = None
    
    # Task management
    parent_task_id: Optional[str] = None  # For task hierarchies
    child_task_ids: List[str] = Field(default_factory=list)
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    tags: List[str] = Field(default_factory=list)
    
    # Metrics
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    
    # Decision tracking
    decisions: List[OrchestratorDecision] = Field(default_factory=list)


class SessionState(BaseModel):
    # Identifiers
    session_id: str
    user_id: str
    user_metadata: Dict[str, Any] = Field(default_factory=dict)
    system_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Current State
    current_phase: AgentPhase = AgentPhase.CLASSIFY
    
    # Agent Results
    classification: Optional[ClassificationResult] = None
    info_validation: Optional[InfoValidationResult] = None
    fix: Optional[FixResult] = None
    
    # Tasks (LLM-based orchestrator support)
    active_task: Optional[Task] = None
    pending_tasks: List[Task] = Field(default_factory=list)
    completed_tasks: List[Task] = Field(default_factory=list)
    
    # Timeline
    timeline: List[TimelineEvent] = Field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Control Flow
    fallback_count: int = 0
    retry_count: int = 0
    escalation_reason: Optional[str] = None
    
    # LLM Decision Tracking
    recent_decisions: List[OrchestratorDecision] = Field(default_factory=list)
    decision_cache_hits: int = 0
    decision_cache_misses: int = 0
    
    # Hybrid orchestration flags
    llm_decisions_enabled: bool = True
    coordination_rules_enabled: bool = True
    decision_confidence_threshold: float = 0.7
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }