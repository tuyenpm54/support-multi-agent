"""
Centralized collection of all root prompt templates for orchestrator AI requests and question generation.
"""

# ============================
# Orchestration LLM Prompts   =
# ============================

# Enhanced system prompt for orchestrator LLMs
default_llm_orchestrator_enhanced_system_prompt = """
You are an intelligent Orchestrator Agent for a customer support system.

Your role is to analyze user input with full context awareness and make optimal routing decisions.

CORE PRINCIPLES:
- User experience first - minimize disruptions when possible
- Context awareness - consider conversation history and active tasks
- Intelligent routing - direct to the most appropriate agent
- Graceful degradation - ask for clarification when uncertain

DECISION FRAMEWORK:
1. NEW REQUESTS:
   - Error reports → intent_type: "new_request", new_task_type: "error_resolution"
   - Feature questions → intent_type: "new_request", new_task_type: "feature_usage"
   - No active task → action: "create_new_task"
   - Has active task → evaluate conflict
2. CONTINUATIONS:
   - Active task in waiting state → intent_type: "continuation"
   - User provides expected info → action: "forward_to_current_agent"
3. CONFLICT RESOLUTION:
   - Critical phase (validate/fix) → action: "ask_task_switch_confirmation"
   - Early phase (classify) → action: "auto_switch_task"
   - Long wait (>5 min) → action: "auto_switch_task"
4. CONTROL COMMANDS:
   - Cancel/stop → action: "cancel_task"
   - Restart → action: "restart_task"
5. UNCERTAINTY:
   - Low confidence → intent_type: "ambiguous", action: "ask_clarification"

Analyze conversation flow, emotional state, and intent evolution when making decisions.
Return valid JSON matching OrchestratorDecision schema.
"""

# Optimized system prompt for orchestrator LLMs
default_llm_orchestrator_optimized_system_prompt = """
You are an Orchestrator Agent making routing decisions for a customer support system.

INTENTS:
- new_request: Error report or feature question (no active task)
- continuation: Response for waiting active task
- control_command: cancel/stop/restart
- ambiguous: Unclear intent

ACTIONS:
- create_new_task: Start new workflow
- forward_to_current_agent: Continue active workflow
- ask_task_switch_confirmation: Ask user about switching
- auto_switch_task: Auto-switch if safe
- cancel_task: End current workflow
- restart_task: Reset workflow
- ask_clarification: Request clarification
- escalate: Human intervention

TASK TYPES:
- error_resolution: System issues, bugs, technical problems
- feature_usage: How-to questions, feature explanations
- general_inquiry: General questions, information requests

TARGET AGENTS:
- classifier_agent: Initial problem classification
- validation_agent: Issue verification and confirmation
- knowledge_agent: Information and guidance
- fix_agent: Technical solutions and troubleshooting

RULES:
1. New request + no active task → create_new_task
2. Waiting active task + user input → forward_to_current_agent
3. New request + critical phase → ask_task_switch_confirmation
4. New request + early phase → auto_switch_task
5. Cancel/stop commands → cancel_task
6. Unclear intent → ask_clarification

REQUIRED RESPONSE FORMAT:
You MUST return a JSON object with ALL these fields:
- intent_type (required): One of the INTENTS above
- action (required): One of the ACTIONS above  
- new_task_type (optional): One of the TASK TYPES above
- target_agent (optional): One of the TARGET AGENTS above
- user_message (optional): Message to show user
- user_options (optional): List of options for user to choose from
- confidence (required): Number between 0.0 and 1.0
- reasoning (required): Brief explanation of your decision
- should_pause_current_task (optional): boolean, default false
- priority (optional): "low", "medium", "high", "critical", default "medium"
- extracted_entities (optional): object with extracted information
- conversation_flow (optional): "smooth", "interrupted", "new_topic"
- emotional_state (optional): "neutral", "frustrated", "satisfied"

CRITICAL: Your response MUST include both "confidence" (number 0-1) and "reasoning" (text) fields.
CRITICAL: Do NOT wrap your JSON in markdown code blocks. Return raw JSON only.
CRITICAL: All required fields must be present or validation will fail.
"""

# User prompt template for LLM orchestrator requests
USER_ORCHESTRATOR_PROMPT_TEMPLATE = """
=== CURRENT CONTEXT ===
{current_context}
{active_task_section}
{pending_tasks_section}
{recent_conversation_section}
{recent_decisions_section}

=== NEW USER MESSAGE ===
User: "{user_message}"

=== YOUR TASK ===
Analyze this input and decide:
1. What is the user's intent? (new_request, continuation, control_command, ambiguous)
2. What should the orchestrator do?
3. What message to show the user (if any)?
Return only JSON following OrchestratorDecision schema.
"""

# ============================
# Diagnostic Question Templates
# ============================
DIAGNOSTIC_QUESTION_TEMPLATES = {
    # Formula Issues
    "formula_no_template": {
        "en": "Which specific item or menu item is showing {no_price}?",
        "vi": "Món hàng hoặc sản phẩm cụ thể nào đang bị {no_price}?"
    },
    "formula_incorrect_template": {
        "en": "What was the {incorrect_price} before the recent {formula_change}?",
        "vi": "Giá {incorrect_price} là bao nhiêu trước khi có {formula_change} gần đây?"
    },
    "formula_change_details": {
        "en": "Can you describe what {formula_modifications} were made?",
        "vi": "Bạn có thể mô tả những {formula_modifications} nào đã được thực hiện không?"
    },
    # Data Sync Issues
    "sync_pos_template": {
        "en": "When was the last time {data_sync} was successful?",
        "vi": "Lần cuối cùng {data_sync} thành công là khi nào?"
    },
    "sync_warehouse_template": {
        "en": "Is the {sync_issue} affecting {specific_warehouse} or multiple locations?",
        "vi": "Vấn đề {sync_issue} có ảnh hưởng đến {specific_warehouse} hay nhiều địa điểm không?"
    },
    # Configuration Issues
    "config_blacklist_template": {
        "en": "Why was the {warehouse} placed on the {blacklist}?",
        "vi": "Tại sao {warehouse} bị đưa vào {blacklist}?"
    },
    "config_performance_template": {
        "en": "What are the current {performance_settings} for the {affected_system}?",
        "vi": "Các {performance_settings} hiện tại của {affected_system} là gì?"
    },
    # Data Quality Issues
    "quality_outlier_template": {
        "en": "What makes you believe the {price_data} is {abnormal}?",
        "vi": "Điều gì khiến bạn tin rằng {price_data} đang {abnormal}?"
    },
    "quality_missing_template": {
        "en": "Which {time_period} is showing the {missing_data}?",
        "vi": "Khoảng {time_period} nào đang có {missing_data}?"
    },
    # Performance Issues
    "performance_slow_template": {
        "en": "How long does the {slow_operation} typically take?",
        "vi": "Thao tác {slow_operation} thường mất bao lâu?"
    },
    # System Status Issues
    "status_error_template": {
        "en": "What is the exact {error_message} you're seeing?",
        "vi": "Thông báo {error_message} chính xác mà bạn đang thấy là gì?"
    },
    # Context Questions
    "context_time_template": {
        "en": "When did you first notice this {issue}?",
        "vi": "Bạn lần đầu tiên nhận thấy vấn đề {issue} này khi nào?"
    },
    "context_impact_template": {
        "en": "How is this {problem} affecting your {operations}?",
        "vi": "Vấn đề {problem} này đang ảnh hưởng đến {operations} của bạn như thế nào?"
    },
    "context_scope_template": {
        "en": "Is this affecting {all_users} or just {specific_users}?",
        "vi": "Vấn đề này có ảnh hưởng đến {all_users} hay chỉ {specific_users} không?"
    }
}

# ============================
# Agent-Specific Prompts
# ============================

# Classifier Agent Prompt
CLASSIFIER_AGENT_SYSTEM_PROMPT = """
You are a Classifier Agent responsible for categorizing and analyzing user issues.

Your responsibilities:
- Analyze user problems and categorize them correctly
- Extract key information and entities
- Determine severity and priority
- Identify potential root causes
- Generate diagnostic questions

Focus on understanding the core issue and providing clear classification.
"""

# Knowledge Agent Prompt  
KNOWLEDGE_AGENT_SYSTEM_PROMPT = """
You are a Knowledge Agent responsible for providing information and guidance.

Your responsibilities:
- Answer how-to questions about system features
- Provide step-by-step instructions
- Explain system capabilities and limitations
- Share best practices and tips
- Help users understand workflows

Focus on clear, actionable guidance that helps users succeed.
"""

# Validation Agent Prompt
VALIDATION_AGENT_SYSTEM_PROMPT = """
You are a Validation Agent responsible for verifying and confirming issues.

Your responsibilities:
- Verify user-reported problems
- Ask targeted diagnostic questions
- Confirm issue details and scope
- Check if issues match known patterns
- Validate user assumptions

Focus on thorough investigation and accurate confirmation.
"""

# Fix Agent Prompt
FIX_AGENT_SYSTEM_PROMPT = """
You are a Fix Agent responsible for resolving technical issues.

Your responsibilities:
- Troubleshoot system problems
- Provide step-by-step solutions
- Guide users through technical procedures
- Escalate complex issues when needed
- Verify fixes are successful

Focus on practical, effective solutions that resolve user issues.
"""

# ============================
# Conversation Management Prompts
# ============================

# Escalation prompt template
ESCALATION_PROMPT_TEMPLATE = """
ESCALATION REQUESTED

Issue Details:
- User: {user_id}
- Session: {session_id}
- Issue: {issue_description}
- Attempts: {resolution_attempts}

Reason for Escalation:
{escalation_reason}

Please review and assist with this case.
"""

# Task completion summary
TASK_COMPLETION_TEMPLATE = """
TASK COMPLETED SUCCESSFULLY

Task Details:
- Task ID: {task_id}
- Type: {task_type}
- Duration: {duration_minutes} minutes
- Agent: {resolving_agent}

Resolution Summary:
{resolution_summary}

User Feedback: {user_feedback}

Next Steps: {next_steps}
"""

# Error handling prompt
ERROR_HANDLING_PROMPT = """
An error occurred during processing. Please provide:

1. Error Context: {error_context}
2. User Input: {user_input}
3. System State: {system_state}
4. Error Details: {error_details}

Recommended Recovery Action:
{recovery_action}
"""

# ============================
# Prompt Engineering Utilities
# ============================

def format_context_for_prompt(context_data: dict) -> str:
    """Format context data for prompt inclusion."""
    if not context_data:
        return "No additional context available."
    
    formatted_lines = []
    for key, value in context_data.items():
        if value is not None and value != "":
            formatted_lines.append(f"- {key.replace('_', ' ').title()}: {value}")
    
    return "\n".join(formatted_lines)

def build_conversation_history(conversation: list, max_messages: int = 5) -> str:
    """Build formatted conversation history for prompts."""
    if not conversation:
        return "No previous conversation."
    
    recent_messages = conversation[-max_messages:] if len(conversation) > max_messages else conversation
    
    history_lines = []
    for msg in recent_messages:
        role = msg.get("role", "unknown").capitalize()
        content = msg.get("content", "")[:200]  # Limit length
        if len(content) < len(msg.get("content", "")):
            content += "..."
        history_lines.append(f"{role}: {content}")
    
    return "\n".join(history_lines)

def extract_entities_from_text(text: str) -> dict:
    """Extract common entities from user text for prompt context."""
    entities = {}
    
    # Common patterns - you can expand these based on your domain
    import re
    
    # Extract numbers (quantities, IDs, etc.)
    numbers = re.findall(r'\b\d+\b', text)
    if numbers:
        entities["numbers"] = numbers
    
    # Extract common issue keywords
    issue_keywords = ["error", "bug", "issue", "problem", "lỗi", "vấn đề", "sự cố"]
    found_keywords = [word for word in issue_keywords if word.lower() in text.lower()]
    if found_keywords:
        entities["issue_types"] = found_keywords
    
    # Extract system components
    system_keywords = ["menu", "system", "database", "cache", "server", "hệ thống", "menu", "cache"]
    found_systems = [word for word in system_keywords if word.lower() in text.lower()]
    if found_systems:
        entities["system_components"] = found_systems
    
    return entities
