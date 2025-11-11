from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AgentPhase(str, Enum):
    CLASSIFY = "CLASSIFY"
    REQUIRED_INFO = "REQUIRED_INFO"
    VALIDATE = "VALIDATE"
    FIX = "FIX"
    COMPLETE = "COMPLETE"
    ESCALATE = "ESCALATE"


class ClassificationResult(BaseModel):
    matched_issue: Optional[Dict[str, Any]] = None
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    reasoning: Optional[str] = None
    has_diagnostic_question: bool = False


class RequiredInfoResult(BaseModel):
    complete_info: Dict[str, Any] = Field(default_factory=dict)
    info_status: str = "incomplete"  # incomplete, complete
    turns_needed: int = 0
    missing_fields: List[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    validation_result: str = "UNCERTAIN"  # CONFIRMED, NOT_FOUND, DIFFERENT_ISSUE, UNCERTAIN
    confidence: float = 0.5
    checks_performed: int = 0
    detected_issue: Optional[str] = None
    reason: Optional[str] = None
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
    required_info: Optional[RequiredInfoResult] = None
    validation: Optional[ValidationResult] = None
    fix: Optional[FixResult] = None
    
    # Timeline
    timeline: List[TimelineEvent] = Field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Control Flow
    fallback_count: int = 0
    retry_count: int = 0
    escalation_reason: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }