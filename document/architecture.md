# ARCHITECTURE.md - System Architecture Document

## Multi-Agent Customer Support System

**Version:** 1.0  
**Date:** November 10, 2024  
**Status:** Technical Design

---

## 1. ARCHITECTURE OVERVIEW

### 1.1 System Context
```
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL SYSTEMS                         │
│  ┌──────────┐  ┌──────────┐  ┌─────────────┐              │
│  │   LLM    │  │ Domain   │  │   User      │              │
│  │   API    │  │ Database │  │   Clients   │              │
│  │(Claude)  │  │(Postgres)│  │(Web/Mobile) │              │
│  └────┬─────┘  └────┬─────┘  └──────┬──────┘              │
└───────┼─────────────┼────────────────┼─────────────────────┘
        │             │                │
        │             │                │
┌───────▼─────────────▼────────────────▼─────────────────────┐
│              MULTI-AGENT SUPPORT SYSTEM                     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              API GATEWAY LAYER                       │  │
│  │  (Authentication, Rate Limiting, Load Balancing)    │  │
│  └───────────────────────┬─────────────────────────────┘  │
│                          │                                 │
│  ┌───────────────────────▼─────────────────────────────┐  │
│  │           ORCHESTRATOR AGENT (Core)                 │  │
│  │  - State Management                                  │  │
│  │  - Workflow Coordination                            │  │
│  │  - Decision Making                                   │  │
│  │  - Error Handling                                    │  │
│  └──┬────────┬────────┬────────┬─────────────────────┘  │
│     │        │        │        │                         │
│  ┌──▼───┐ ┌─▼────┐ ┌─▼────┐ ┌─▼────┐                   │
│  │CLASS │ │REQ   │ │VALID │ │FIX   │                   │
│  │IFIER │ │INFO  │ │ATE   │ │AGENT │                   │
│  │AGENT │ │AGENT │ │AGENT │ │      │                   │
│  └──┬───┘ └─┬────┘ └─┬────┘ └─┬────┘                   │
│     │       │        │        │                         │
│  ┌──▼───────▼────────▼────────▼─────────────────────┐  │
│  │          TOOL EXECUTION LAYER                     │  │
│  │  - Database Queries                                │  │
│  │  - API Calls                                       │  │
│  │  - System Checks                                   │  │
│  │  - Action Execution                                │  │
│  └────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │          DATA STORAGE LAYER                          │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐           │  │
│  │  │  Issue   │ │  Redis   │ │  Audit   │           │  │
│  │  │ Database │ │  Cache   │ │   Logs   │           │  │
│  │  │(PgVector)│ │ (State)  │ │(TimeSDB) │           │  │
│  │  └──────────┘ └──────────┘ └──────────┘           │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Design Principles

1. **Tool-Based Declarative Architecture**
   - Issue logic trong database, không hardcode
   - Agents execute theo tool declarations
   - Easy to update without code changes

2. **Stateless Agents, Stateful Orchestrator**
   - Each agent call is independent
   - State managed centrally by Orchestrator
   - Enables horizontal scaling

3. **Fail-Safe & Graceful Degradation**
   - Always có fallback path to human
   - Partial success better than complete failure
   - Rollback capability for fixes

4. **Observability First**
   - Every action logged
   - Metrics at every layer
   - Distributed tracing

5. **Cost Optimization**
   - Minimize LLM calls
   - Tools do heavy lifting
   - Semantic search before LLM

---

## 2. COMPONENT ARCHITECTURE

### 2.1 Orchestrator Agent

**Responsibilities:**
- Session state management
- Workflow coordination
- Decision making at each phase
- Error handling and recovery
- User communication

**Technology Stack:**
- Language: Python 3.11+
- Framework: LangGraph
- State Storage: Redis
- Message Queue: Redis Streams (for async operations)

**State Machine:**
```
┌─────────┐
│  START  │
└────┬────┘
     │
     ▼
┌─────────────┐    confidence < 0.65    ┌──────────┐
│  CLASSIFY   │───────────────────────→ │ ESCALATE │
└──────┬──────┘                          └──────────┘
       │ confidence >= 0.65
       ▼
┌─────────────┐    missing info         ┌──────────┐
│ REQUIRED    │←────────────────────────┤   ASK    │
│    INFO     │─────────────────────────→  USER   │
└──────┬──────┘    info complete        └──────────┘
       │
       ▼
┌─────────────┐    NOT_FOUND            ┌──────────┐
│  VALIDATE   │───────────────────────→ │ INFORM   │
└──────┬──────┘                          │  USER    │
       │ CONFIRMED                       └──────────┘
       │ DIFFERENT_ISSUE → Re-classify
       ▼
┌─────────────┐    FAILED/DENIED        ┌──────────┐
│     FIX     │───────────────────────→ │ ESCALATE │
└──────┬──────┘                          └──────────┘
       │ SUCCESS
       ▼
┌─────────────┐
│  COMPLETE   │
└─────────────┘
```

**Key Algorithms:**
```python
# Decision Logic After Classification
def handle_classification_result(state, classification):
    if classification.confidence >= 0.85:
        return transition_to("REQUIRED_INFO")
    
    elif 0.65 <= classification.confidence < 0.85:
        if classification.has_diagnostic_question:
            return ask_diagnostic_question(classification)
        else:
            return transition_to("REQUIRED_INFO", warning=True)
    
    else:  # confidence < 0.65
        if state.fallback_count >= 2:
            return escalate_to_human("LOW_CONFIDENCE")
        else:
            state.fallback_count += 1
            return ask_clarifying_questions(classification)

# Decision Logic After Validation
def handle_validation_result(state, validation):
    if validation.result == "CONFIRMED":
        return transition_to("FIX")
    
    elif validation.result == "NOT_FOUND":
        return inform_user_false_positive(validation)
    
    elif validation.result == "DIFFERENT_ISSUE":
        state.issue_id = validation.detected_issue
        # Check if need new info
        if requires_additional_info(validation.detected_issue):
            return transition_to("REQUIRED_INFO")
        else:
            return transition_to("FIX")
    
    else:  # UNCERTAIN
        return escalate_to_human("VALIDATION_UNCERTAIN", validation)
```

**Session State Schema:**
```python
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

class SessionState(BaseModel):
    # Identifiers
    session_id: str
    user_id: str
    
    # Current phase
    current_phase: str  # CLASSIFY, REQUIRED_INFO, VALIDATE, FIX, COMPLETE
    
    # Agent outputs
    classification: Optional[Dict] = None
    required_info: Optional[Dict] = None
    validation: Optional[Dict] = None
    fix: Optional[Dict] = None
    
    # Timeline
    timeline: List[Dict] = []
    
    # Conversation
    conversation_history: List[Dict] = []
    
    # Control flow
    fallback_count: int = 0
    retry_count: int = 0
    escalation_reason: Optional[str] = None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    
    # Metadata
    user_metadata: Dict
    system_metadata: Dict
```

---

### 2.2 Classifier Agent

**Architecture:**
```
┌─────────────────────────────────────────────┐
│          CLASSIFIER AGENT                   │
├─────────────────────────────────────────────┤
│                                             │
│  ┌────────────────────────────────────┐   │
│  │  1. PREPROCESSING                  │   │
│  │  - Normalize text                  │   │
│  │  - Extract keywords                │   │
│  │  - Language detection              │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  2. SEMANTIC SEARCH                │   │
│  │  - Embed user message              │   │
│  │  - Vector similarity search        │   │
│  │  - Top-K candidate issues          │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  3. ENTITY EXTRACTION              │   │
│  │  - NER (spaCy/custom)              │   │
│  │  - Regex patterns                  │   │
│  │  - Extract from user message       │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  4. LLM REFINEMENT (if needed)     │   │
│  │  - Ambiguous cases only            │   │
│  │  - Multi-intent messages           │   │
│  │  - Confidence < 0.75               │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  5. OUTPUT FORMATTING              │   │
│  │  - Matched issue                   │   │
│  │  - Extracted entities              │   │
│  │  - Confidence score                │   │
│  └────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

**Technology Stack:**
- Embedding Model: OpenAI text-embedding-3-small (1536 dimensions)
- Vector DB: PostgreSQL with pgvector extension
- NER: spaCy (for entity extraction)
- LLM: Claude Sonnet 4 (fallback only)

**Semantic Search Implementation:**
```python
import numpy as np
from typing import List, Tuple

class IssueClassifier:
    def __init__(self, embedding_model, vector_db):
        self.embedding_model = embedding_model
        self.vector_db = vector_db
    
    def classify(self, user_message: str, threshold: float = 0.75) -> Dict:
        # 1. Preprocess
        normalized = self.preprocess(user_message)
        
        # 2. Semantic search
        embedding = self.embedding_model.embed(normalized)
        candidates = self.vector_db.similarity_search(
            embedding=embedding,
            top_k=5,
            threshold=0.5
        )
        
        if not candidates:
            return {"matched_issue": None, "confidence": 0.0}
        
        best_match = candidates[0]
        
        # 3. Extract entities
        entities = self.extract_entities(
            message=user_message,
            issue_pattern=best_match
        )
        
        # 4. LLM refinement if uncertain
        if best_match.similarity < threshold:
            refined = self.llm_refinement(
                message=user_message,
                candidates=candidates[:3]
            )
            return refined
        
        # 5. Return result
        return {
            "matched_issue": {
                "issue_id": best_match.issue_id,
                "issue_name": best_match.issue_name,
                "confidence": best_match.similarity,
                "category": best_match.category
            },
            "extracted_entities": entities,
            "reasoning": f"Semantic match with {best_match.similarity:.2f} confidence"
        }
```

---

### 2.3 Required Info Agent

**Architecture:**
```
┌─────────────────────────────────────────────┐
│       REQUIRED INFO AGENT                   │
├─────────────────────────────────────────────┤
│                                             │
│  ┌────────────────────────────────────┐   │
│  │  1. IDENTIFY MISSING FIELDS        │   │
│  │  - Compare extracted vs required   │   │
│  │  - Categorize: critical/optional   │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  2. SMART DEFAULTS                 │   │
│  │  - User's default warehouse        │   │
│  │  - Recent entities accessed        │   │
│  │  - Context-based suggestions       │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  3. LOOKUP TOOLS                   │   │
│  │  - lookup_item(name/code)          │   │
│  │  - lookup_warehouse(name/code)     │   │
│  │  - lookup_menu(name/code)          │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  4. MULTI-TURN CONVERSATION        │   │
│  │  - Present options (if multiple)   │   │
│  │  - Handle user selection           │   │
│  │  - Validate collected info         │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  5. OUTPUT COMPLETE INFO           │   │
│  │  - All required fields filled      │   │
│  │  - Validated format                │   │
│  └────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

**Implementation Pattern:**
```python
class RequiredInfoAgent:
    def __init__(self, tool_registry):
        self.tool_registry = tool_registry
    
    async def gather_info(self, issue, extracted_entities, user_metadata):
        complete_info = {}
        missing_fields = []
        
        # Step 1: Identify missing fields
        for field_config in issue.required_fields:
            field_name = field_config["field"]
            
            if field_name in extracted_entities:
                complete_info[field_name] = extracted_entities[field_name]
            else:
                missing_fields.append(field_config)
        
        # Step 2: Try smart defaults
        for field_config in missing_fields:
            default_value = self.try_smart_default(
                field_config, 
                user_metadata
            )
            if default_value:
                # Ask for confirmation
                confirmed = await self.confirm_default(
                    field_config, 
                    default_value
                )
                if confirmed:
                    complete_info[field_config["field"]] = default_value
                    missing_fields.remove(field_config)
        
        # Step 3: Lookup for remaining fields
        for field_config in missing_fields:
            if field_config.get("lookup_tool"):
                value = await self.lookup_and_ask(field_config)
                complete_info[field_config["field"]] = value
            else:
                value = await self.ask_directly(field_config)
                complete_info[field_config["field"]] = value
        
        # Step 4: Validate
        validated = self.validate_info(complete_info, issue.required_fields)
        
        return {
            "complete_info": validated,
            "info_status": "complete",
            "turns_needed": self.conversation_turns
        }
    
    async def lookup_and_ask(self, field_config):
        # User provided a name, need to find code
        user_input = await self.ask_user(
            f"Nhập {field_config['field']} (tên hoặc mã):"
        )
        
        # Call lookup tool
        tool = self.tool_registry.get(field_config["lookup_tool"])
        results = await tool.execute(name=user_input, fuzzy=True)
        
        if len(results) == 0:
            return await self.handle_no_match(field_config, user_input)
        elif len(results) == 1:
            return await self.confirm_single_match(results[0])
        else:
            return await self.handle_multiple_matches(results)
```

---

### 2.4 Validate Agent

**Architecture:**
```
┌─────────────────────────────────────────────┐
│          VALIDATE AGENT                     │
├─────────────────────────────────────────────┤
│                                             │
│  ┌────────────────────────────────────┐   │
│  │  1. LOAD VALIDATION TOOLS          │   │
│  │  - From issue database             │   │
│  │  - Max 5 tools (priority ordered)  │   │
│  │  - Replace param templates         │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  2. SEQUENTIAL EXECUTION           │   │
│  │  - Execute by priority             │   │
│  │  - Early exit on critical failure  │   │
│  │  - Parallel execution (if safe)    │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  3. RESULT COMPARISON              │   │
│  │  - Actual vs Expected              │   │
│  │  - Check if_fail conditions        │   │
│  │  - Track all check results         │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  4. OUTCOME DETERMINATION          │   │
│  │  - CONFIRMED: Issue verified       │   │
│  │  - NOT_FOUND: False positive       │   │
│  │  - DIFFERENT_ISSUE: Re-classify    │   │
│  │  - UNCERTAIN: Need escalation      │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  5. OUTPUT VALIDATION RESULT       │   │
│  │  - Result + confidence             │   │
│  │  - Checks performed                │   │
│  │  - Root cause confirmation         │   │
│  └────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

**Implementation Pattern:**
```python
class ValidateAgent:
    def __init__(self, tool_registry):
        self.tool_registry = tool_registry
    
    async def validate(self, issue, complete_info):
        validation_results = []
        stop_early = False
        early_exit_reason = None
        
        # Get validation tools from issue
        validation_tools = issue.validation_tools[:issue.max_validation_tools]
        
        # Execute tools sequentially
        for tool_config in validation_tools:
            if stop_early:
                break
            
            # Replace param templates
            params = self.replace_params(
                tool_config["params"], 
                complete_info
            )
            
            # Execute tool
            tool = self.tool_registry.get(tool_config["tool_name"])
            result = await tool.execute(**params)
            
            # Compare with expected
            match = self.compare_result(
                actual=result,
                expected=tool_config["expected_result"]
            )
            
            validation_results.append({
                "tool": tool_config["tool_name"],
                "result": result,
                "expected": tool_config["expected_result"],
                "match": match,
                "priority": tool_config["priority"]
            })
            
            # Check early exit
            if not match and tool_config.get("if_fail"):
                if tool_config["if_fail"] in ["ITEM_NOT_FOUND", "ALREADY_LINKED"]:
                    stop_early = True
                    early_exit_reason = tool_config["if_fail"]
        
        # Analyze results
        return self.determine_outcome(
            validation_results, 
            stop_early, 
            early_exit_reason
        )
    
    def determine_outcome(self, results, stop_early, early_exit_reason):
        if stop_early:
            if early_exit_reason == "ITEM_NOT_FOUND":
                return {
                    "validation_result": "NOT_FOUND",
                    "confidence": 1.0,
                    "checks_performed": len(results),
                    "reason": "Entity does not exist"
                }
            elif early_exit_reason == "ALREADY_LINKED":
                return {
                    "validation_result": "NOT_FOUND",
                    "confidence": 0.95,
                    "checks_performed": len(results),
                    "reason": "Issue already resolved (false positive)"
                }
        
        # Check if all passed
        all_passed = all(r["match"] for r in results)
        
        if all_passed:
            return {
                "validation_result": "CONFIRMED",
                "confidence": 0.95,
                "checks_performed": len(results),
                "root_cause_confirmed": True
            }
        
        # Check if different issue
        failed_checks = [r for r in results if not r["match"]]
        detected_issue = self.detect_different_issue(failed_checks)
        
        if detected_issue:
            return {
                "validation_result": "DIFFERENT_ISSUE",
                "detected_issue": detected_issue,
                "confidence": 0.88,
                "checks_performed": len(results)
            }
        
        # Uncertain
        return {
            "validation_result": "UNCERTAIN",
            "confidence": 0.50,
            "checks_performed": len(results),
            "failed_checks": failed_checks
        }
```

---

### 2.5 Fix Agent

**Architecture:**
```
┌─────────────────────────────────────────────┐
│              FIX AGENT                      │
├─────────────────────────────────────────────┤
│                                             │
│  ┌────────────────────────────────────┐   │
│  │  1. LOAD FIX TOOLS                 │   │
│  │  - From issue database             │   │
│  │  - Max 5 tools (execution order)   │   │
│  │  - Check permission levels         │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  2. PERMISSION HANDLING            │   │
│  │  - auto: Execute immediately       │   │
│  │  - user_confirmation: Ask user     │   │
│  │  - supervisor_approval: Ask mgr    │   │
│  │  - manual_only: Escalate           │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  3. STATE CAPTURE (Rollback)       │   │
│  │  - Snapshot current state          │   │
│  │  - Generate rollback token         │   │
│  │  - Store rollback actions          │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  4. SEQUENTIAL EXECUTION           │   │
│  │  - Execute by execution_order      │   │
│  │  - Retry on transient failures     │   │
│  │  - Rollback on critical failure    │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  5. POST-FIX VERIFICATION          │   │
│  │  - Re-run validation checks        │   │
│  │  - Functional test (if possible)   │   │
│  │  - User confirmation               │   │
│  └──────────────┬─────────────────────┘   │
│                 │                           │
│  ┌──────────────▼─────────────────────┐   │
│  │  6. OUTPUT FIX RESULT              │   │
│  │  - Success/Partial/Failed          │   │
│  │  - Actions performed               │   │
│  │  - Rollback token (if applicable)  │   │
│  └────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

**Implementation Pattern:**
```python
class FixAgent:
    def __init__(self, tool_registry):
        self.tool_registry = tool_registry
    
    async def fix(self, issue, complete_info, user_context):
        fix_results = []
        rollback_stack = []
        
        # Get fix tools from issue
        fix_tools = issue.fix_tools[:issue.max_fix_tools]
        
        # Step 1: Check permissions
        for tool_config in fix_tools:
            if not await self.check_permission(tool_config, user_context):
                return {
                    "fix_result": "PERMISSION_DENIED",
                    "tool": tool_config["tool_name"]
                }
        
        # Step 2: Capture state for rollback
        rollback_token = await self.capture_state(complete_info, fix_tools)
        
        # Step 3: Execute tools
        for tool_config in fix_tools:
            params = self.replace_params(
                tool_config["params"], 
                complete_info
            )
            
            try:
                tool = self.tool_registry.get(tool_config["tool_name"])
                result = await tool.execute(**params)
                
                fix_results.append({
                    "tool": tool_config["tool_name"],
                    "status": "SUCCESS",
                    "result": result,
                    "timestamp": datetime.now()
                })
                
                # Save rollback action if reversible
                if tool_config.get("reversible"):
                    rollback_stack.append({
                        "tool": tool_config["rollback_tool"],
                        "params": params
                    })
            
            except Exception as e:
                fix_results.append({
                    "tool": tool_config["tool_name"],
                    "status": "FAILED",
                    "error": str(e)
                })
                
                # Decide: rollback or continue?
                if tool_config.get("critical", True):
                    # Rollback all previous actions
                    await self.execute_rollback(rollback_stack)
                    return {
                        "fix_result": "FAILED",
                        "actions_performed": fix_results,
                        "rolled_back": True
                    }
                else:
                    # Continue (best-effort)
                    continue
        
        # Step 4: Verify fix
        verification = await self.verify_fix(issue, complete_info)
        
        return {
            "fix_result": "SUCCESS",
            "actions_performed": fix_results,
            "verification": verification,
            "rollback_available": True,
            "rollback_token": rollback_token
        }
    
    async def check_permission(self, tool_config, user_context):
        permission_level = tool_config.get("permission_level", "manual_only")
        
        if permission_level == "auto":
            return True
        
        elif permission_level == "user_confirmation":
            # Ask user for approval
            approved = await self.request_user_approval(tool_config)
            return approved
        
        elif permission_level == "supervisor_approval":
            # Request from manager
            approved = await self.request_supervisor_approval(
                tool_config, 
                user_context
            )
            return approved
        
        else:  # manual_only
            return False
```

---

## 3. DATA ARCHITECTURE

### 3.1 Issue Database Schema
```sql
-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Issue Patterns Table
CREATE TABLE issue_patterns (
    issue_id VARCHAR(50) PRIMARY KEY,
    issue_name VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    description TEXT,
    
    -- For semantic search
    embedding vector(1536),
    symptom_keywords TEXT[],
    
    -- Entity extraction config
    entity_patterns JSONB,
    
    -- Required fields config
    required_fields JSONB NOT NULL,
    
    -- Validation tools config
    validation_tools JSONB NOT NULL,
    max_validation_tools INT DEFAULT 5,
    
    -- Fix tools config
    fix_tools JSONB NOT NULL,
    max_fix_tools INT DEFAULT 5,
    fix_execution_strategy VARCHAR(20) DEFAULT 'atomic', -- 'atomic' or 'progressive'
    
    -- Alternative issues
    alternative_issues JSONB,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Indexes
    INDEX idx_issue_category (category),
    INDEX idx_issue_active (is_active),
    VECTOR INDEX idx_issue_embedding (embedding)
);

-- Tool Registry Table
CREATE TABLE tool_registry (
    tool_name VARCHAR(100) PRIMARY KEY,
    tool_type VARCHAR(50) NOT NULL, -- lookup, check, fix, rollback
    description TEXT,
    
    -- Configuration
    params_schema JSONB NOT NULL,
    returns_schema JSONB NOT NULL,
    
    -- Implementation
    implementation_type VARCHAR(50) NOT NULL, -- api_endpoint, database_query, script
    endpoint_url VARCHAR(500),
    timeout_seconds INT DEFAULT 30,
    retry_count INT DEFAULT 3,
    
    -- Performance metrics
    rate_limit VARCHAR(20), -- "100/minute"
    avg_latency_ms INT DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 100.00,
    
    -- Metadata
    version VARCHAR(20) DEFAULT '1.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Conversation Archive Table
CREATE TABLE conversation_archive (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    
    -- Issue details
    issue_id VARCHAR(50),
    classification_result JSONB,
    final_outcome VARCHAR(50), -- RESOLVED, ESCALATED, FAILED
    
    -- Conversation data
    conversation_data JSONB NOT NULL,
    agent_interactions JSONB[],
    tool_executions JSONB[],
    
    -- Metrics
    total_duration_seconds INT,
    agent_turns INT,
    user_satisfaction_score INT CHECK (user_satisfaction_score >= 1 AND user_satisfaction_score <= 5),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_conversation_user (user_id),
    INDEX idx_conversation_issue (issue_id),
    INDEX idx_conversation_outcome (final_outcome),
    INDEX idx_conversation_created (created_at)
);

-- Rollback Tokens Table
CREATE TABLE rollback_tokens (
    rollback_token UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    issue_id VARCHAR(50) NOT NULL,
    
    -- Rollback data
    rollback_actions JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    used_at TIMESTAMP,
    
    -- Indexes
    INDEX idx_rollback_session (session_id),
    INDEX idx_rollback_user (user_id),
    INDEX idx_rollback_expires (expires_at)
);
```

### 3.2 Vector Search Implementation

**Embedding Strategy:**
```python
class IssueEmbeddingManager:
    def __init__(self, embedding_model, vector_db):
        self.embedding_model = embedding_model
        self.vector_db = vector_db
    
    def generate_embedding(self, text: str) -> List[float]:
        # Combine issue name, description, and keywords
        combined_text = f"{issue_name} {description} {' '.join(keywords)}"
        return self.embedding_model.embed(combined_text)
    
    def update_issue_embedding(self, issue_id: str):
        # Regenerate and update embedding when issue is modified
        issue = self.get_issue(issue_id)
        embedding = self.generate_embedding(issue)
        self.vector_db.update_embedding(issue_id, embedding)
    
    def semantic_search(self, query: str, top_k: int = 5, threshold: float = 0.5) -> List[Dict]:
        embedding = self.embedding_model.embed(query)
        results = self.vector_db.similarity_search(
            embedding=embedding,
            top_k=top_k,
            threshold=threshold,
            filter_conditions={"is_active": True}
        )
        return results
```

**Vector Index Configuration:**
```sql
-- Create efficient vector index for semantic search
CREATE INDEX CONCURRENTLY idx_issue_embedding_cosine 
ON issue_patterns 
USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);

-- Configure for optimal performance
SET hnsw.ef_search = 100;
```

### 3.3 Session State Management

**Redis Schema:**
```python
class SessionStateManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.session_ttl = 3600  # 1 hour
        self.state_key_prefix = "session:"
        self.timeline_key_prefix = "timeline:"
    
    async def create_session(self, user_id: str, user_metadata: Dict) -> str:
        session_id = f"SESSION_{uuid4().hex[:12]}"
        
        # Initialize session state
        session_state = SessionState(
            session_id=session_id,
            user_id=user_id,
            current_phase="CLASSIFY",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            user_metadata=user_metadata,
            system_metadata={}
        )
        
        # Store in Redis with TTL
        await self.redis.setex(
            f"{self.state_key_prefix}{session_id}",
            self.session_ttl,
            session_state.json()
        )
        
        return session_id
    
    async def update_session(self, session_id: str, updates: Dict):
        key = f"{self.state_key_prefix}{session_id}"
        
        # Get current state
        current_data = await self.redis.get(key)
        if not current_data:
            raise ValueError("Session not found")
        
        session_state = SessionState.parse_raw(current_data)
        
        # Apply updates
        for field, value in updates.items():
            setattr(session_state, field, value)
        
        session_state.updated_at = datetime.now()
        
        # Store updated state
        await self.redis.setex(key, self.session_ttl, session_state.json())
    
    async def add_timeline_event(self, session_id: str, event: Dict):
        timeline_key = f"{self.timeline_key_prefix}{session_id}"
        event["timestamp"] = datetime.now().isoformat()
        
        # Add to timeline list
        await self.redis.lpush(timeline_key, json.dumps(event))
        await self.redis.expire(timeline_key, self.session_ttl)
    
    async def get_session_timeline(self, session_id: str) -> List[Dict]:
        timeline_key = f"{self.timeline_key_prefix}{session_id}"
        events = await self.redis.lrange(timeline_key, 0, -1)
        return [json.loads(event) for event in events]
```

---

## 4. API ARCHITECTURE

### 4.1 API Gateway Layer

**Technology Stack:**
- API Gateway: Kong/Nginx
- Authentication: OAuth 2.0 + JWT
- Rate Limiting: Redis-based token bucket
- Load Balancing: Round-robin with health checks

**API Endpoints:**
```yaml
# Session Management
POST /api/v1/sessions:
  description: Create new support session
  body:
    user_id: string
    user_metadata: object
  response:
    session_id: string
    websocket_url: string

GET /api/v1/sessions/{session_id}:
  description: Get session status
  response:
    session_state: SessionState
    timeline: TimelineEvent[]

# WebSocket Communication
WS /api/v1/sessions/{session_id}/ws:
  description: Real-time conversation channel
  messages:
    user_message: UserMessage
    agent_response: AgentResponse
    progress_update: ProgressUpdate
    system_notification: SystemNotification

# Tool Execution
POST /api/v1/tools/{tool_name}/execute:
  description: Execute domain-specific tool
  body:
    params: object
    context: object
  response:
    result: object
    execution_time_ms: int
```

### 4.2 WebSocket Communication Protocol

**Message Format:**
```json
{
  "type": "user_message|agent_response|progress_update|system_notification",
  "session_id": "SESSION_...",
  "timestamp": "2024-11-10T10:30:00Z",
  "data": {
    // Message-specific data
  }
}
```

**User Message:**
```json
{
  "type": "user_message",
  "data": {
    "message": "Món phở không hiển thị",
    "attachments": [],
    "metadata": {}
  }
}
```

**Agent Response:**
```json
{
  "type": "agent_response",
  "data": {
    "phase": "CLASSIFY|REQUIRED_INFO|VALIDATE|FIX|COMPLETE",
    "message": "Để kiểm tra, tôi cần biết món nào và ở kho nào?",
    "actions": [
      {
        "type": "ask_input",
        "field": "item_name",
        "prompt": "Nhập tên món:"
      }
    ],
    "confidence": 0.93
  }
}
```

**Progress Update:**
```json
{
  "type": "progress_update",
  "data": {
    "current_phase": "VALIDATE",
    "status": "IN_PROGRESS",
    "message": "⏳ Đang kiểm tra hệ thống...",
    "progress_percentage": 60,
    "estimated_remaining_seconds": 15
  }
}
```

### 4.3 Authentication & Authorization

**JWT Token Structure:**
```json
{
  "sub": "USER_12345",
  "session_id": "SESSION_ABCDEF",
  "roles": ["end_user"],
  "permissions": ["read_own_data", "execute_fix_tools"],
  "domain_context": {
    "warehouse_id": "WH_001",
    "branch_id": "BR_001"
  },
  "iat": 1731241800,
  "exp": 1731243600
}
```

**Permission Matrix:**
```yaml
role_permissions:
  end_user:
    - create_session
    - send_message
    - view_own_session
    - execute_fix_tools (with confirmation)
  
  support_agent:
    - view_all_sessions
    - take_over_session
    - execute_all_tools
    - manage_issue_database
  
  admin:
    - full_access
    - system_configuration
    - user_management
```

---

## 5. TOOL EXECUTION LAYER

### 5.1 Tool Registry Architecture

**Tool Interface:**
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseTool(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config["tool_name"]
        self.timeout = config.get("timeout_seconds", 30)
    
    @abstractmethod
    async def execute(self, **params) -> Dict[str, Any]:
        """Execute the tool with given parameters"""
        pass
    
    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        pass
    
    async def health_check(self) -> bool:
        """Check if tool is operational"""
        return True
```

**Example Tool Implementation:**
```python
class LookupItemTool(BaseTool):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_endpoint = config["endpoint_url"]
        self.api_key = config.get("api_key")
    
    async def execute(self, name: Optional[str] = None, 
                      code: Optional[str] = None, 
                      fuzzy: bool = True) -> Dict[str, Any]:
        params = {"fuzzy": fuzzy}
        if name:
            params["name"] = name
        if code:
            params["code"] = code
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.api_endpoint}/search",
                params=params,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "matches": data["items"],
                        "total_matches": len(data["items"])
                    }
                else:
                    raise ToolExecutionError(f"API error: {response.status}")
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        return "name" in params or "code" in params
```

### 5.2 Tool Execution Engine

**Execution Pipeline:**
```python
class ToolExecutionEngine:
    def __init__(self, tool_registry: Dict[str, BaseTool], 
                 rate_limiter: RateLimiter,
                 circuit_breaker: CircuitBreaker):
        self.tools = tool_registry
        self.rate_limiter = rate_limiter
        self.circuit_breaker = circuit_breaker
        self.metrics_collector = MetricsCollector()
    
    async def execute_tool(self, tool_name: str, params: Dict[str, Any],
                          context: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        
        try:
            # 1. Get tool
            tool = self.tools.get(tool_name)
            if not tool:
                raise ToolNotFoundError(f"Tool {tool_name} not found")
            
            # 2. Rate limiting
            await self.rate_limiter.check_limit(tool_name, context["user_id"])
            
            # 3. Circuit breaker check
            if not self.circuit_breaker.is_available(tool_name):
                raise ToolUnavailableError(f"Tool {tool_name} is circuit-broken")
            
            # 4. Validate parameters
            if not tool.validate_params(params):
                raise InvalidParametersError("Invalid parameters")
            
            # 5. Execute with timeout
            result = await asyncio.wait_for(
                tool.execute(**params),
                timeout=tool.timeout
            )
            
            # 6. Record metrics
            execution_time = (time.time() - start_time) * 1000
            self.metrics_collector.record_success(
                tool_name, execution_time
            )
            
            # 7. Update circuit breaker
            self.circuit_breaker.record_success(tool_name)
            
            return {
                "result": result,
                "execution_time_ms": execution_time,
                "tool_name": tool_name
            }
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.metrics_collector.record_failure(tool_name, execution_time)
            self.circuit_breaker.record_failure(tool_name)
            raise
```

### 5.3 Tool Categories

**Lookup Tools:**
```yaml
lookup_item:
  description: Search for items by name or code
  params:
    name: {type: string, required: false}
    code: {type: string, required: false}
    fuzzy: {type: boolean, default: true}
  returns:
    matches: array of Item objects
    total_matches: integer

lookup_warehouse:
  description: Search for warehouses
  params:
    name: {type: string, required: false}
    code: {type: string, required: false}
    location: {type: string, required: false}
  returns:
    matches: array of Warehouse objects

lookup_menu:
  description: Search for menus
  params:
    name: {type: string, required: false}
    code: {type: string, required: false}
    active_only: {type: boolean, default: true}
  returns:
    matches: array of Menu objects
```

**Check Tools:**
```yaml
check_item_exists:
  description: Verify if item exists in system
  params:
    item_code: {type: string, required: true}
  returns:
    exists: boolean
    item_details: object or null

check_item_menu_link:
  description: Check if item is linked to menu
  params:
    item_code: {type: string, required: true}
    menu_id: {type: string, required: true}
  returns:
    linked: boolean
    link_details: object or null

check_user_permissions:
  description: Verify user permissions
  params:
    user_id: {type: string, required: true}
    action: {type: string, required: true}
    resource: {type: string, required: true}
  returns:
    permitted: boolean
    reason: string
```

**Fix Tools:**
```yaml
link_item_to_menu:
  description: Link item to menu
  params:
    item_code: {type: string, required: true}
    menu_id: {type: string, required: true}
    price: {type: number, required: false}
  returns:
    success: boolean
    link_id: string
  rollback_tool: unlink_item_from_menu

unlink_item_from_menu:
  description: Remove item from menu
  params:
    item_code: {type: string, required: true}
    menu_id: {type: string, required: true}
  returns:
    success: boolean

refresh_menu_cache:
  description: Refresh menu cache
  params:
    menu_id: {type: string, required: true}
  returns:
    success: boolean
    cache_version: string
```

---

## 6. DEPLOYMENT ARCHITECTURE

### 6.1 Container Architecture

**Docker Compose Configuration:**
```yaml
version: '3.8'

services:
  # API Gateway
  api-gateway:
    image: kong:3.4
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/declarative/kong.yml
    volumes:
      - ./kong.yml:/kong/declarative/kong.yml
    ports:
      - "8000:8000"
      - "8443:8443"
    depends_on:
      - orchestrator
      - redis

  # Orchestrator Service
  orchestrator:
    build: ./orchestrator
    environment:
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://postgres:password@postgres:5432/support_system
      LLM_API_KEY: ${LLM_API_KEY}
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M

  # Classifier Service
  classifier:
    build: ./classifier
    environment:
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://postgres:password@postgres:5432/support_system
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 2

  # Required Info Service
  required-info:
    build: ./required-info
    environment:
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://postgres:password@postgres:5432/support_system
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 2

  # Validate Service
  validate:
    build: ./validate
    environment:
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://postgres:password@postgres:5432/support_system
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 2

  # Fix Service
  fix:
    build: ./fix
    environment:
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://postgres:password@postgres:5432/support_system
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 2

  # PostgreSQL Database
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: support_system
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
    ports:
      - "5432:5432"

  # Redis Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  # TimescaleDB for Metrics
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_DB: metrics
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - timescale_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"

volumes:
  postgres_data:
  redis_data:
  timescale_data:
```

### 6.2 Kubernetes Deployment

**Namespace Configuration:**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: support-system
  labels:
    name: support-system
```

**Orchestrator Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestrator
  namespace: support-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: orchestrator
  template:
    metadata:
      labels:
        app: orchestrator
    spec:
      containers:
      - name: orchestrator
        image: support-system/orchestrator:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        - name: LLM_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: claude-api-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: orchestrator-service
  namespace: support-system
spec:
  selector:
    app: orchestrator
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: ClusterIP
```

### 6.3 Infrastructure Components

**Ingress Configuration:**
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: support-system-ingress
  namespace: support-system
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/websocket-services: "orchestrator-service"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
spec:
  tls:
  - hosts:
    - support-api.example.com
    secretName: support-api-tls
  rules:
  - host: support-api.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: orchestrator-service
            port:
              number: 8000
      - path: /ws
        pathType: Prefix
        backend:
          service:
            name: orchestrator-service
            port:
              number: 8000
```

**ConfigMap for Application Config:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: support-system-config
  namespace: support-system
data:
  config.yaml: |
    database:
      host: postgres-service
      port: 5432
      name: support_system
      pool_size: 20
      max_overflow: 30
    
    redis:
      host: redis-service
      port: 6379
      db: 0
      max_connections: 100
    
    llm:
      provider: anthropic
      model: claude-3-sonnet-20240229
      max_tokens: 4000
      temperature: 0.1
    
    agents:
      classifier:
        confidence_threshold: 0.75
        max_candidates: 5
      required_info:
        max_turns: 3
        timeout_seconds: 120
      validate:
        max_tools: 5
        timeout_seconds: 30
      fix:
        max_tools: 5
        timeout_seconds: 60
    
    monitoring:
      metrics_enabled: true
      tracing_enabled: true
      log_level: INFO
```

---

## 7. MONITORING & OBSERVABILITY

### 7.1 Metrics Collection

**Business Metrics:**
```python
class BusinessMetricsCollector:
    def __init__(self, timescale_client):
        self.db = timescale_client
    
    async def record_resolution(self, session_id: str, outcome: str, 
                             duration_seconds: int, satisfaction: Optional[int]):
        await self.db.execute("""
            INSERT INTO resolution_metrics 
            (session_id, outcome, duration_seconds, satisfaction_score, timestamp)
            VALUES ($1, $2, $3, $4, NOW())
        """, session_id, outcome, duration_seconds, satisfaction)
    
    async def record_agent_performance(self, agent_name: str, phase: str,
                                     execution_time_ms: int, success: boolean):
        await self.db.execute("""
            INSERT INTO agent_performance_metrics 
            (agent_name, phase, execution_time_ms, success, timestamp)
            VALUES ($1, $2, $3, $4, NOW())
        """, agent_name, phase, execution_time_ms, success)
    
    async def get_resolution_rate(self, time_range: str = '24 hours') -> float:
        result = await self.db.fetch_one("""
            SELECT 
                COUNT(CASE WHEN outcome = 'RESOLVED' THEN 1 END)::float / 
                COUNT(*)::float as resolution_rate
            FROM resolution_metrics 
            WHERE timestamp >= NOW() - INTERVAL '%s'
        """, time_range)
        return result['resolution_rate']
```

**Technical Metrics:**
```python
class TechnicalMetricsCollector:
    def __init__(self, prometheus_client):
        self.prometheus = prometheus_client
        
        # Define metrics
        self.request_duration = Histogram(
            'request_duration_seconds',
            'Request duration',
            ['endpoint', 'method', 'status']
        )
        
        self.agent_execution_time = Histogram(
            'agent_execution_time_seconds',
            'Agent execution time',
            ['agent_name', 'phase']
        )
        
        self.tool_execution_time = Histogram(
            'tool_execution_time_seconds',
            'Tool execution time',
            ['tool_name', 'status']
        )
        
        self.active_sessions = Gauge(
            'active_sessions_total',
            'Number of active sessions'
        )
        
        self.llm_token_usage = Counter(
            'llm_token_usage_total',
            'LLM token usage',
            ['model', 'type']  # type: input/output
        )
```

### 7.2 Logging Strategy

**Structured Logging Format:**
```python
import structlog

logger = structlog.get_logger()

class LogContext:
    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.correlation_id = str(uuid4())
    
    def bind(self, **kwargs):
        return structlog.bind(
            session_id=self.session_id,
            user_id=self.user_id,
            correlation_id=self.correlation_id,
            **kwargs
        )

# Usage in agents
async def classify_message(self, message: str, context: LogContext):
    log = context.bind(phase="CLASSIFY", agent="classifier")
    
    log.info("Starting classification", message_length=len(message))
    
    try:
        result = await self._classify_internal(message)
        log.info("Classification completed", 
                issue_id=result["issue_id"], 
                confidence=result["confidence"])
        return result
    except Exception as e:
        log.error("Classification failed", error=str(e))
        raise
```

**Log Retention Policy:**
```yaml
# TimescaleDB hypertable configuration
SELECT add_retention_policy('resolution_metrics', INTERVAL '1 year');
SELECT add_retention_policy('agent_performance_metrics', INTERVAL '6 months');
SELECT add_retention_policy('system_logs', INTERVAL '90 days');

# Continuous aggregates for long-term metrics
CREATE MATERIALIZED VIEW daily_resolution_metrics WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', timestamp) as day,
    COUNT(*) as total_sessions,
    COUNT(CASE WHEN outcome = 'RESOLVED' THEN 1 END) as resolved_sessions,
    AVG(duration_seconds) as avg_duration,
    AVG(satisfaction_score) as avg_satisfaction
FROM resolution_metrics
GROUP BY day;
```

### 7.3 Distributed Tracing

**OpenTelemetry Configuration:**
```python
from opentelemetry import trace, baggage
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

class TracingManager:
    def __init__(self):
        # Initialize tracer
        trace.set_tracer_provider(TracerProvider())
        tracer = trace.get_tracer(__name__)
        
        # Configure Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name="jaeger",
            agent_port=6831,
        )
        
        span_processor = BatchSpanProcessor(jaeger_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
    
    def trace_agent_execution(self, agent_name: str, phase: str):
        def decorator(func):
            async def wrapper(*args, **kwargs):
                with trace.get_tracer(__name__).start_as_current_span(
                    f"{agent_name}.{phase}"
                ) as span:
                    span.set_attribute("agent.name", agent_name)
                    span.set_attribute("agent.phase", phase)
                    span.set_attribute("service.name", "support-system")
                    
                    try:
                        result = await func(*args, **kwargs)
                        span.set_attribute("execution.success", True)
                        return result
                    except Exception as e:
                        span.set_attribute("execution.success", False)
                        span.set_attribute("error.message", str(e))
                        raise
            return wrapper
        return decorator
```

**Trace Correlation:**
```python
class TraceContext:
    @staticmethod
    def extract_from_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """Extract trace context from HTTP headers"""
        carrier = {}
        for key, value in headers.items():
            if key.startswith("X-Trace-"):
                carrier[key[7:]] = value
        return carrier
    
    @staticmethod
    def inject_into_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """Inject trace context into HTTP headers"""
        current_span = trace.get_current_span()
        if current_span:
            span_context = current_span.get_span_context()
            headers.update({
                "X-Trace-Id": span_context.trace_id,
                "X-Parent-Span-Id": span_context.span_id,
            })
        return headers
```

---

## 8. SECURITY ARCHITECTURE

### 8.1 Authentication Flow

**OAuth 2.0 Implementation:**
```python
class AuthenticationManager:
    def __init__(self, oauth_provider, jwt_secret):
        self.oauth_provider = oauth_provider
        self.jwt_secret = jwt_secret
    
    async def authenticate_user(self, authorization_code: str) -> Dict[str, Any]:
        # 1. Exchange code for tokens
        token_response = await self.oauth_provider.exchange_code_for_token(
            authorization_code
        )
        
        # 2. Get user info
        user_info = await self.oauth_provider.get_user_info(
            token_response["access_token"]
        )
        
        # 3. Load user permissions
        permissions = await self.load_user_permissions(user_info["id"])
        
        # 4. Create JWT token
        jwt_payload = {
            "sub": user_info["id"],
            "email": user_info["email"],
            "roles": user_info["roles"],
            "permissions": permissions,
            "iat": datetime.now(),
            "exp": datetime.now() + timedelta(minutes=30)
        }
        
        jwt_token = jwt.encode(jwt_payload, self.jwt_secret, algorithm="HS256")
        
        return {
            "access_token": jwt_token,
            "token_type": "Bearer",
            "expires_in": 1800,
            "user_info": user_info
        }
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token expired")
        except jwt.InvalidTokenError:
            raise AuthenticationError("Invalid token")
```

### 8.2 Authorization Framework

**RBAC Implementation:**
```python
class AuthorizationManager:
    def __init__(self, permissions_db):
        self.permissions_db = permissions_db
    
    async def check_permission(self, user_id: str, resource: str, 
                             action: str, context: Dict[str, Any]) -> bool:
        # 1. Get user roles
        user_roles = await self.permissions_db.get_user_roles(user_id)
        
        # 2. Check role-based permissions
        for role in user_roles:
            if await self._check_role_permission(role, resource, action):
                # 3. Apply attribute-based access control (ABAC)
                return await self._check_contextual_constraints(
                    role, resource, action, context
                )
        
        return False
    
    async def _check_role_permission(self, role: str, resource: str, 
                                   action: str) -> bool:
        permission_rules = {
            "end_user": {
                "session": ["create", "read"],
                "tool": ["execute:fix", "execute:lookup"]
            },
            "support_agent": {
                "session": ["read:all", "takeover"],
                "tool": ["execute:all"],
                "issue": ["create", "update", "delete"]
            },
            "admin": {
                "*": ["*"]  # Full access
            }
        }
        
        user_permissions = permission_rules.get(role, {})
        
        # Check for wildcard permission
        if "*" in user_permissions:
            return "*" in user_permissions["*"] or action in user_permissions["*"]
        
        # Check resource-specific permission
        resource_perms = user_permissions.get(resource, [])
        return action in resource_perms or f"execute:{action}" in resource_perms
```

### 8.3 Data Privacy & Protection

**PII Redaction:**
```python
import re
from typing import Dict, Any

class PrivacyManager:
    def __init__(self):
        self.pii_patterns = {
            "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "phone": re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
            "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            "credit_card": re.compile(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'),
        }
    
    def redact_pii(self, text: str) -> str:
        redacted_text = text
        
        for pii_type, pattern in self.pii_patterns.items():
            redacted_text = pattern.sub(f'[REDACTED_{pii_type.upper()}]', redacted_text)
        
        return redacted_text
    
    def sanitize_log_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = self.redact_pii(value)
            elif isinstance(value, dict):
                sanitized[key] = self.sanitize_log_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self.redact_pii(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized
```

**Encryption at Rest:**
```python
from cryptography.fernet import Fernet

class EncryptionManager:
    def __init__(self, encryption_key: bytes):
        self.cipher = Fernet(encryption_key)
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive conversation data"""
        encrypted_data = self.cipher.encrypt(data.encode())
        return encrypted_data.decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive conversation data"""
        decrypted_data = self.cipher.decrypt(encrypted_data.encode())
        return decrypted_data.decode()
    
    def encrypt_session_data(self, session_state: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive fields in session state"""
        sensitive_fields = ["user_metadata", "conversation_history"]
        
        encrypted_state = session_state.copy()
        for field in sensitive_fields:
            if field in encrypted_state and encrypted_state[field]:
                encrypted_state[field] = self.encrypt_sensitive_data(
                    json.dumps(encrypted_state[field])
                )
        
        return encrypted_state
```

---

## 9. PERFORMANCE OPTIMIZATION

### 9.1 Caching Strategy

**Multi-Level Caching:**
```python
class CacheManager:
    def __init__(self, redis_client, local_cache):
        self.redis = redis_client  # L2 cache
        self.local = local_cache  # L1 cache (in-memory)
        
    async def get(self, key: str, cache_level: str = "auto") -> Optional[Any]:
        # Try L1 cache first
        if cache_level in ["auto", "l1"]:
            value = self.local.get(key)
            if value is not None:
                return value
        
        # Try L2 cache
        if cache_level in ["auto", "l2"]:
            value = await self.redis.get(key)
            if value is not None:
                # Populate L1 cache
                self.local.set(key, value, ttl=300)  # 5 minutes
                return value
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600, 
                  cache_level: str = "both"):
        if cache_level in ["both", "l1"]:
            self.local.set(key, value, ttl=min(ttl, 300))  # Max 5 min for L1
        
        if cache_level in ["both", "l2"]:
            await self.redis.setex(key, ttl, value)

# Usage in agents
class CachedClassifier:
    def __init__(self, classifier, cache_manager):
        self.classifier = classifier
        self.cache = cache_manager
    
    async def classify(self, message: str) -> Dict[str, Any]:
        cache_key = f"classify:{hashlib.md5(message.encode()).hexdigest()}"
        
        # Try cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Perform classification
        result = await self.classifier.classify(message)
        
        # Cache result for 30 minutes
        await self.cache.set(cache_key, result, ttl=1800)
        
        return result
```

### 9.2 Database Optimization

**Connection Pooling:**
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

class DatabaseManager:
    def __init__(self, database_url: str):
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
        
        self.async_engine = create_async_engine(
            database_url.replace("postgresql://", "postgresql+asyncpg://"),
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
            pool_recycle=3600
        )
    
    async def execute_query(self, query: str, params: Dict = None) -> List[Dict]:
        async with self.async_engine.connect() as conn:
            result = await conn.execute(text(query), params or {})
            return [dict(row) for row in result.fetchall()]
```

**Query Optimization:**
```sql
-- Optimized vector search query
WITH candidate_issues AS (
    SELECT 
        issue_id,
        issue_name,
        category,
        1 - (embedding <=> $1::vector) as similarity,
        symptom_keywords
    FROM issue_patterns 
    WHERE 
        embedding <=> $1::vector < 0.5  -- Pre-filter by distance
        AND is_active = true
    ORDER BY embedding <=> $1::vector
    LIMIT 10
)
SELECT 
    ci.*,
    COUNT(*) OVER() as total_candidates
FROM candidate_issues ci
WHERE ci.similarity >= $2  -- Final similarity threshold
ORDER BY ci.similarity DESC
LIMIT 5;

-- Tool performance monitoring query
SELECT 
    tool_name,
    COUNT(*) as execution_count,
    AVG(execution_time_ms) as avg_execution_time,
    COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END)::float / COUNT(*) as success_rate,
    DATE_TRUNC('hour', created_at) as hour_bucket
FROM tool_execution_metrics
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY tool_name, hour_bucket
ORDER BY hour_bucket DESC, tool_name;
```

### 9.3 Resource Management

**Async Processing:**
```python
import asyncio
from asyncio import Semaphore

class ResourceManager:
    def __init__(self):
        self.llm_semaphore = Semaphore(10)  # Max 10 concurrent LLM calls
        self.tool_semaphore = Semaphore(50)  # Max 50 concurrent tool calls
        self.db_semaphore = Semaphore(100)  # Max 100 concurrent DB queries
    
    async def execute_with_resource_management(
        self, 
        resource_type: str, 
        coro, 
        *args, 
        **kwargs
    ):
        semaphore = getattr(self, f"{resource_type}_semaphore")
        
        async with semaphore:
            return await coro(*args, **kwargs)

# Usage in orchestrator
class OrchestratorAgent:
    def __init__(self):
        self.resource_manager = ResourceManager()
    
    async def process_message(self, message: str, session_id: str):
        async with self.resource_manager.llm_semaphore:
            classification = await self.classifier.classify(message)
        
        if classification["confidence"] >= 0.85:
            async with self.resource_manager.tool_semaphore:
                info = await self.required_info.gather_info(
                    classification["issue_id"],
                    classification["extracted_entities"]
                )
        
        # Continue workflow...
```

**Memory Management:**
```python
import gc
import psutil
from typing import Any

class MemoryManager:
    def __init__(self, max_memory_mb: int = 1024):
        self.max_memory_mb = max_memory_mb
    
    def check_memory_usage(self) -> float:
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB
    
    def should_trigger_gc(self) -> bool:
        current_memory = self.check_memory_usage()
        return current_memory > self.max_memory_mb * 0.8
    
    def trigger_cleanup(self):
        if self.should_trigger_gc():
            gc.collect()
            
            # Clear caches if needed
            if self.check_memory_usage() > self.max_memory_mb * 0.9:
                self.clear_caches()
    
    def clear_caches(self):
        # Clear local caches
        cache_manager.clear_local_cache()
        
        # Clear LLM model caches if applicable
        if hasattr(self, 'llm_model'):
            self.llm_model.clear_cache()
```

---

## 10. KNOWLEDGE EXTRACTION FLOW

### 10.1 Pattern Discovery Pipeline

**Batch Processing Architecture:**
```python
class KnowledgeExtractionPipeline:
    def __init__(self, conversation_storage, pattern_analyzer, issue_db):
        self.conversation_storage = conversation_storage
        self.pattern_analyzer = pattern_analyzer
        self.issue_db = issue_db
    
    async def extract_patterns_from_conversations(
        self, 
        time_range: str = "24 hours"
    ) -> List[Dict]:
        # 1. Fetch resolved conversations
        conversations = await self.conversation_storage.get_resolved_conversations(
            time_range=time_range
        )
        
        # 2. Group by similar issue characteristics
        conversation_groups = await self.group_similar_conversations(
            conversations
        )
        
        # 3. Extract patterns from each group
        new_patterns = []
        for group in conversation_groups:
            pattern = await self.pattern_analyzer.extract_pattern(group)
            if pattern and pattern["confidence"] >= 0.8:
                new_patterns.append(pattern)
        
        # 4. Validate and store new patterns
        for pattern in new_patterns:
            await self.validate_and_store_pattern(pattern)
        
        return new_patterns
    
    async def group_similar_conversations(
        self, 
        conversations: List[Dict]
    ) -> List[List[Dict]]:
        groups = []
        processed = set()
        
        for conv in conversations:
            if conv["id"] in processed:
                continue
            
            similar_convs = [conv]
            processed.add(conv["id"])
            
            # Find similar conversations
            for other_conv in conversations:
                if other_conv["id"] not in processed:
                    similarity = await self.calculate_conversation_similarity(
                        conv, other_conv
                    )
                    if similarity >= 0.8:
                        similar_convs.append(other_conv)
                        processed.add(other_conv["id"])
            
            if len(similar_convs) >= 3:  # Minimum group size
                groups.append(similar_convs)
        
        return groups
```

### 10.2 Pattern Analysis Engine

**Pattern Extraction Algorithm:**
```python
class PatternAnalyzer:
    def __init__(self, llm_client, embedding_model):
        self.llm = llm_client
        self.embedding_model = embedding_model
    
    async def extract_pattern(self, conversation_group: List[Dict]) -> Optional[Dict]:
        # 1. Analyze common characteristics
        common_entities = self.extract_common_entities(conversation_group)
        common_keywords = self.extract_common_keywords(conversation_group)
        
        # 2. Generate pattern description
        pattern_description = await self.generate_pattern_description(
            conversation_group, common_entities, common_keywords
        )
        
        # 3. Extract validation and fix patterns
        validation_pattern = await self.extract_validation_pattern(conversation_group)
        fix_pattern = await self.extract_fix_pattern(conversation_group)
        
        # 4. Calculate confidence score
        confidence = self.calculate_pattern_confidence(
            len(conversation_group),
            validation_pattern,
            fix_pattern
        )
        
        if confidence >= 0.8:
            return {
                "issue_name": pattern_description["name"],
                "category": pattern_description["category"],
                "description": pattern_description["description"],
                "required_fields": pattern_description["required_fields"],
                "validation_tools": validation_pattern,
                "fix_tools": fix_pattern,
                "confidence": confidence,
                "source_conversations": [conv["id"] for conv in conversation_group],
                "occurrence_count": len(conversation_group)
            }
        
        return None
    
    async def extract_validation_pattern(self, conversations: List[Dict]) -> List[Dict]:
        # Analyze successful validation steps from conversations
        validation_steps = []
        
        for conv in conversations:
            for step in conv["tool_executions"]:
                if step["phase"] == "VALIDATE" and step["status"] == "SUCCESS":
                    validation_steps.append({
                        "tool_name": step["tool_name"],
                        "params": step["params"],
                        "expected_result": step["expected_result"],
                        "priority": step.get("priority", 1)
                    })
        
        # Find most common validation pattern
        return self.find_most_common_pattern(validation_steps)
    
    async def extract_fix_pattern(self, conversations: List[Dict]) -> List[Dict]:
        # Analyze successful fix steps from conversations
        fix_steps = []
        
        for conv in conversations:
            for step in conv["tool_executions"]:
                if step["phase"] == "FIX" and step["status"] == "SUCCESS":
                    fix_steps.append({
                        "tool_name": step["tool_name"],
                        "params": step["params"],
                        "execution_order": step["order"],
                        "permission_level": step.get("permission_level", "auto"),
                        "reversible": step.get("reversible", False)
                    })
        
        # Find most common fix pattern
        return self.find_most_common_pattern(fix_steps)
```

### 10.3 Automated Pattern Validation

**Pattern Testing Framework:**
```python
class PatternValidator:
    def __init__(self, test_conversations, issue_db):
        self.test_conversations = test_conversations
        self.issue_db = issue_db
    
    async def validate_new_pattern(self, pattern: Dict) -> Dict[str, Any]:
        validation_results = {
            "pattern_id": pattern.get("issue_id"),
            "validation_tests": [],
            "overall_score": 0.0,
            "recommendations": []
        }
        
        # 1. Test with historical conversations
        historical_accuracy = await self.test_with_historical_data(pattern)
        validation_results["validation_tests"].append({
            "test_type": "historical_accuracy",
            "score": historical_accuracy["accuracy"],
            "details": historical_accuracy
        })
        
        # 2. Test classification accuracy
        classification_accuracy = await self.test_classification_accuracy(pattern)
        validation_results["validation_tests"].append({
            "test_type": "classification_accuracy",
            "score": classification_accuracy["accuracy"],
            "details": classification_accuracy
        })
        
        # 3. Test tool execution
        tool_execution_success = await self.test_tool_execution(pattern)
        validation_results["validation_tests"].append({
            "test_type": "tool_execution",
            "score": tool_execution_success["success_rate"],
            "details": tool_execution_success
        })
        
        # 4. Calculate overall score
        total_score = sum(test["score"] for test in validation_results["validation_tests"])
        validation_results["overall_score"] = total_score / len(validation_results["validation_tests"])
        
        # 5. Generate recommendations
        validation_results["recommendations"] = self.generate_recommendations(
            validation_results
        )
        
        return validation_results
    
    async def test_with_historical_data(self, pattern: Dict) -> Dict[str, Any]:
        # Find conversations that match this pattern
        matching_convs = []
        
        for conv in self.test_conversations:
            if self.conversation_matches_pattern(conv, pattern):
                matching_convs.append(conv)
        
        if len(matching_convs) < 5:
            return {"accuracy": 0.0, "reason": "Insufficient matching conversations"}
        
        # Test if pattern would have correctly identified and resolved these conversations
        correct_identifications = 0
        successful_resolutions = 0
        
        for conv in matching_convs:
            # Test classification
            if self.would_classify_correctly(conv, pattern):
                correct_identifications += 1
            
            # Test resolution
            if self.would_resolve_correctly(conv, pattern):
                successful_resolutions += 1
        
        return {
            "accuracy": (correct_identifications + successful_resolutions) / (len(matching_convs) * 2),
            "matching_conversations": len(matching_convs),
            "correct_classifications": correct_identifications,
            "successful_resolutions": successful_resolutions
        }
```

This completes the architecture document with comprehensive technical specifications covering all aspects from component design through deployment, monitoring, security, and the knowledge extraction flow as specified in the PRD.