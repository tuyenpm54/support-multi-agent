"""
Diagnostic Question Generation System

This module implements an advanced diagnostic question generation system
that creates context-aware questions based on classification results,
entity extraction, and pattern detection. Supports multi-turn conversation
strategies and Vietnamese language questions.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class QuestionType(Enum):
    """Types of diagnostic questions"""
    CLARIFICATION = "clarification"
    VERIFICATION = "verification"
    TROUBLESHOOTING = "troubleshooting"
    IMPACT_ASSESSMENT = "impact_assessment"
    ISOLATION = "isolation"
    ROOT_CAUSE = "root_cause"
    CONTEXT = "context"

class QuestionStrategy(Enum):
    """Question generation strategies"""
    SEQUENTIAL = "sequential"  # Ask questions one by one
    PARALLEL = "parallel"     # Ask multiple related questions
    ADAPTIVE = "adaptive"     # Adapt based on previous answers
    TARGETED = "targeted"     # Focus on specific issue types

@dataclass
class QuestionTemplate:
    """Template for generating diagnostic questions"""
    id: str
    category: str
    question_type: QuestionType
    template: str
    vietnamese_template: str
    required_entities: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    follow_up_questions: List[str] = field(default_factory=list)
    priority: int = 5
    max_occurrences: int = 1

@dataclass
class DiagnosticQuestion:
    """Generated diagnostic question with metadata"""
    id: str
    question: str
    vietnamese_question: str
    question_type: QuestionType
    category: str
    priority: int
    context: Dict[str, Any] = field(default_factory=dict)
    expected_answer_type: str = "text"
    follow_up_questions: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)

@dataclass
class QuestionGenerationResult:
    """Result of diagnostic question generation"""
    success: bool
    questions: List[DiagnosticQuestion]
    strategy: QuestionStrategy
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

class DiagnosticQuestionGenerator:
    """Advanced diagnostic question generation system"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.templates = self._initialize_templates()
        self.question_history = {}  # Track questions asked per session
        self.entity_patterns = self._initialize_entity_patterns()
        
    def _initialize_templates(self) -> Dict[str, QuestionTemplate]:
        """Initialize question templates for different issue categories"""
        templates = {
            # Formula Issues
            "formula_no_template": QuestionTemplate(
                id="formula_no_template",
                category="formula",
                question_type=QuestionType.ROOT_CAUSE,
                template="Which specific item or menu item is showing {no_price}?",
                vietnamese_template="Món hàng hoặc sản phẩm cụ thể nào đang bị {no_price}?",
                required_entities=["menu_item", "product"],
                priority=10,
                follow_up_questions=["formula_when_started", "formula_affected_items"]
            ),
            
            "formula_incorrect_template": QuestionTemplate(
                id="formula_incorrect_template", 
                category="formula",
                question_type=QuestionType.VERIFICATION,
                template="What was the {incorrect_price} before the recent {formula_change}?",
                vietnamese_template="Giá {incorrect_price} là bao nhiêu trước khi có {formula_change} gần đây?",
                required_entities=["price", "change"],
                priority=9,
                follow_up_questions=["formula_change_details", "formula_expected_price"]
            ),
            
            "formula_change_details": QuestionTemplate(
                id="formula_change_details",
                category="formula", 
                question_type=QuestionType.CONTEXT,
                template="Can you describe what {formula_modifications} were made?",
                vietnamese_template="Bạn có thể mô tả những {formula_modifications} nào đã được thực hiện không?",
                required_entities=["modifications"],
                priority=8
            ),
            
            # Data Sync Issues  
            "sync_pos_template": QuestionTemplate(
                id="sync_pos_template",
                category="data_sync",
                question_type=QuestionType.TROUBLESHOOTING,
                template="When was the last time {data_sync} was successful?",
                vietnamese_template="Lần cuối cùng {data_sync} thành công là khi nào?",
                required_entities=["sync_time", "system"],
                priority=9,
                follow_up_questions=["sync_error_messages", "sync_affected_data"]
            ),
            
            "sync_warehouse_template": QuestionTemplate(
                id="sync_warehouse_template",
                category="data_sync",
                question_type=QuestionType.ISOLATION,
                template="Is the {sync_issue} affecting {specific_warehouse} or multiple locations?",
                vietnamese_template="Vấn đề {sync_issue} có ảnh hưởng đến {specific_warehouse} hay nhiều địa điểm không?",
                required_entities=["warehouse", "locations"],
                priority=8
            ),
            
            # Configuration Issues
            "config_blacklist_template": QuestionTemplate(
                id="config_blacklist_template",
                category="configuration",
                question_type=QuestionType.ROOT_CAUSE,
                template="Why was the {warehouse} placed on the {blacklist}?",
                vietnamese_template="Tại sao {warehouse} bị đưa vào {blacklist}?",
                required_entities=["warehouse", "reason"],
                priority=10,
                follow_up_questions=["config_blacklist_duration", "config_impact"]
            ),
            
            "config_performance_template": QuestionTemplate(
                id="config_performance_template",
                category="configuration",
                question_type=QuestionType.VERIFICATION,
                template="What are the current {performance_settings} for the {affected_system}?",
                vietnamese_template="Các {performance_settings} hiện tại của {affected_system} là gì?",
                required_entities=["settings", "system"],
                priority=7
            ),
            
            # Data Quality Issues
            "quality_outlier_template": QuestionTemplate(
                id="quality_outlier_template",
                category="data_quality",
                question_type=QuestionType.CLARIFICATION,
                template="What makes you believe the {price_data} is {abnormal}?",
                vietnamese_template="Điều gì khiến bạn tin rằng {price_data} đang {abnormal}?",
                required_entities=["price", "abnormal_behavior"],
                priority=8,
                follow_up_questions=["quality_expected_range", "quality_source_data"]
            ),
            
            "quality_missing_template": QuestionTemplate(
                id="quality_missing_template",
                category="data_quality",
                question_type=QuestionType.ISOLATION,
                template="Which {time_period} is showing the {missing_data}?",
                vietnamese_template="Khoảng {time_period} nào đang có {missing_data}?",
                required_entities=["time_period", "data_type"],
                priority=9
            ),
            
            # Performance Issues
            "performance_slow_template": QuestionTemplate(
                id="performance_slow_template",
                category="performance",
                question_type=QuestionType.TROUBLESHOOTING,
                template="How long does the {slow_operation} typically take?",
                vietnamese_template="Thao tác {slow_operation} thường mất bao lâu?",
                required_entities=["operation", "duration"],
                priority=8,
                follow_up_questions=["performance_recent_changes", "performance_comparison"]
            ),
            
            # System Status Issues
            "status_error_template": QuestionTemplate(
                id="status_error_template",
                category="system_status",
                question_type=QuestionType.VERIFICATION,
                template="What is the exact {error_message} you're seeing?",
                vietnamese_template="Thông báo {error_message} chính xác mà bạn đang thấy là gì?",
                required_entities=["error_message", "context"],
                priority=10
            ),
            
            # Context Questions
            "context_time_template": QuestionTemplate(
                id="context_time_template",
                category="context",
                question_type=QuestionType.CONTEXT,
                template="When did you first notice this {issue}?",
                vietnamese_template="Bạn lần đầu tiên nhận thấy vấn đề {issue} này khi nào?",
                priority=6
            ),
            
            "context_impact_template": QuestionTemplate(
                id="context_impact_template",
                category="context",
                question_type=QuestionType.IMPACT_ASSESSMENT,
                template="How is this {problem} affecting your {operations}?",
                vietnamese_template="Vấn đề {problem} này đang ảnh hưởng đến {operations} của bạn như thế nào?",
                priority=7
            ),
            
            "context_scope_template": QuestionTemplate(
                id="context_scope_template", 
                category="context",
                question_type=QuestionType.ISOLATION,
                template="Is this affecting {all_users} or just {specific_users}?",
                vietnamese_template="Vấn đề này có ảnh hưởng đến {all_users} hay chỉ {specific_users} không?",
                priority=7
            )
        }
        return templates
    
    def _initialize_entity_patterns(self) -> Dict[str, List[str]]:
        """Initialize entity patterns for question generation"""
        return {
            "menu_item": ["món", "sản phẩm", "hàng", "item", "product"],
            "price": ["giá", "giá tiền", "cost", "price", "giá vốn"],
            "warehouse": ["kho", "nhà kho", "warehouse", "kho hàng"],
            "time": ["thời gian", "lúc", "khi nào", "when", "time"],
            "error": ["lỗi", "báo lỗi", "error", "thông báo lỗi"],
            "system": ["hệ thống", "system", "phần mềm", "software"],
            "sync": ["đồng bộ", "sync", "đồng bộ hóa", "synchronization"],
            "formula": ["công thức", "formula", "cách tính", "calculation"],
            "data": ["dữ liệu", "data", "thông tin", "information"]
        }
    
    async def generate_questions(
        self,
        classification_result: Dict[str, Any],
        entities: Dict[str, Any],
        detected_patterns: Dict[str, Any],
        session_state: Optional[Dict[str, Any]] = None,
        strategy: QuestionStrategy = QuestionStrategy.ADAPTIVE,
        max_questions: int = 5
    ) -> QuestionGenerationResult:
        """
        Generate diagnostic questions based on classification and analysis results
        
        Args:
            classification_result: Result from issue classification
            entities: Extracted entities from user input
            detected_patterns: Pattern detection results
            session_state: Current session state and history
            strategy: Question generation strategy
            max_questions: Maximum number of questions to generate
            
        Returns:
            QuestionGenerationResult with generated questions and metadata
        """
        
        try:
            self.logger.info(f"Generating diagnostic questions using {strategy.value} strategy")
            
            # Extract key information
            category = classification_result.get('suggested_category', 'unknown')
            confidence = classification_result.get('confidence', 0.0)
            matched_title = classification_result.get('matched_title', '')
            
            # Get session history
            session_id = session_state.get('session_id', 'unknown') if session_state else 'unknown'
            asked_questions = self.question_history.get(session_id, [])
            
            # Select relevant templates
            relevant_templates = self._select_relevant_templates(
                category, entities, detected_patterns, asked_questions
            )
            
            # Generate questions based on strategy
            if strategy == QuestionStrategy.SEQUENTIAL:
                questions = await self._generate_sequential_questions(
                    relevant_templates, entities, detected_patterns, max_questions
                )
            elif strategy == QuestionStrategy.PARALLEL:
                questions = await self._generate_parallel_questions(
                    relevant_templates, entities, detected_patterns, max_questions  
                )
            elif strategy == QuestionStrategy.TARGETED:
                questions = await self._generate_targeted_questions(
                    relevant_templates, entities, detected_patterns, max_questions
                )
            else:  # ADAPTIVE (default)
                questions = await self._generate_adaptive_questions(
                    relevant_templates, entities, detected_patterns, session_state, max_questions
                )
            
            # Update question history
            self.question_history[session_id] = asked_questions + [q.id for q in questions]
            
            # Sort by priority
            questions.sort(key=lambda q: q.priority, reverse=True)
            
            self.logger.info(f"Generated {len(questions)} diagnostic questions")
            
            return QuestionGenerationResult(
                success=True,
                questions=questions[:max_questions],
                strategy=strategy,
                context={
                    "category": category,
                    "confidence": confidence,
                    "matched_title": matched_title,
                    "entities_count": len(entities),
                    "patterns_detected": len(detected_patterns.get('confidence_scores', {}))
                },
                metadata={
                    "templates_considered": len(relevant_templates),
                    "questions_filtered": max(0, len(questions) - max_questions),
                    "generation_time": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Question generation failed: {str(e)}")
            return QuestionGenerationResult(
                success=False,
                questions=[],
                strategy=strategy,
                error=str(e)
            )
    
    def _select_relevant_templates(
        self,
        category: str,
        entities: Dict[str, Any],
        detected_patterns: Dict[str, Any],
        asked_questions: List[str]
    ) -> List[QuestionTemplate]:
        """Select relevant question templates based on context"""
        
        relevant_templates = []
        
        for template in self.templates.values():
            # Skip if already asked too many times
            if asked_questions.count(template.id) >= template.max_occurrences:
                continue
                
            # Check category relevance
            if template.category == category or template.category == "context":
                relevance_score = 0
                
                # Check entity relevance
                for required_entity in template.required_entities:
                    if required_entity in entities and entities[required_entity]:
                        relevance_score += 2
                
                # Check pattern relevance
                primary_pattern = detected_patterns.get('primary_issue_type')
                if primary_pattern and template.category == primary_pattern:
                    relevance_score += 3
                
                # Check category match
                if template.category == category:
                    relevance_score += 2
                
                # Add if relevant enough
                if relevance_score >= 2:
                    relevant_templates.append((template, relevance_score))
        
        # Sort by relevance score and priority
        relevant_templates.sort(key=lambda x: (x[1], x[0].priority), reverse=True)
        
        return [template for template, _ in relevant_templates]
    
    async def _generate_sequential_questions(
        self,
        templates: List[QuestionTemplate],
        entities: Dict[str, Any],
        detected_patterns: Dict[str, Any],
        max_questions: int
    ) -> List[DiagnosticQuestion]:
        """Generate questions sequentially (one by one)"""
        
        questions = []
        
        for i, template in enumerate(templates[:max_questions]):
            # Generate primary question
            question = self._generate_question_from_template(
                template, entities, detected_patterns, i
            )
            questions.append(question)
            
            # Add follow-up questions if they exist
            if len(questions) + len(template.follow_up_questions) <= max_questions:
                for follow_up_id in template.follow_up_questions:
                    if follow_up_id in self.templates:
                        follow_up_template = self.templates[follow_up_id]
                        follow_up_question = self._generate_question_from_template(
                            follow_up_template, entities, detected_patterns, len(questions)
                        )
                        questions.append(follow_up_question)
        
        return questions
    
    async def _generate_parallel_questions(
        self,
        templates: List[QuestionTemplate],
        entities: Dict[str, Any], 
        detected_patterns: Dict[str, Any],
        max_questions: int
    ) -> List[DiagnosticQuestion]:
        """Generate multiple questions in parallel"""
        
        questions = []
        
        # Group templates by question type
        template_groups = {}
        for template in templates[:max_questions]:
            if template.question_type not in template_groups:
                template_groups[template.question_type] = []
            template_groups[template.question_type].append(template)
        
        # Generate questions from each group
        for question_type, group_templates in template_groups.items():
            for template in group_templates[:2]:  # Max 2 per type
                question = self._generate_question_from_template(
                    template, entities, detected_patterns, len(questions)
                )
                questions.append(question)
                
                if len(questions) >= max_questions:
                    break
            
            if len(questions) >= max_questions:
                break
        
        return questions
    
    async def _generate_targeted_questions(
        self,
        templates: List[QuestionTemplate],
        entities: Dict[str, Any],
        detected_patterns: Dict[str, Any],
        max_questions: int
    ) -> List[DiagnosticQuestion]:
        """Generate targeted questions for specific issue types"""
        
        questions = []
        primary_pattern = detected_patterns.get('primary_issue_type')
        
        # Prioritize templates that match the primary pattern
        pattern_templates = [t for t in templates if t.category == primary_pattern]
        other_templates = [t for t in templates if t.category != primary_pattern]
        
        # Generate from pattern-matching templates first
        for template in pattern_templates[:max_questions//2 + 1]:
            question = self._generate_question_from_template(
                template, entities, detected_patterns, len(questions)
            )
            questions.append(question)
        
        # Fill with other templates
        remaining_slots = max_questions - len(questions)
        for template in other_templates[:remaining_slots]:
            question = self._generate_question_from_template(
                template, entities, detected_patterns, len(questions)
            )
            questions.append(question)
        
        return questions
    
    async def _generate_adaptive_questions(
        self,
        templates: List[QuestionTemplate],
        entities: Dict[str, Any],
        detected_patterns: Dict[str, Any],
        session_state: Optional[Dict[str, Any]],
        max_questions: int
    ) -> List[DiagnosticQuestion]:
        """Generate questions adaptively based on session state"""
        
        questions = []
        
        # Check if this is a follow-up session
        conversation_history = session_state.get('conversation_history', []) if session_state else []
        is_follow_up = len(conversation_history) > 1
        
        if is_follow_up:
            # Focus on clarification and verification questions
            follow_up_templates = [
                t for t in templates 
                if t.question_type in [QuestionType.CLARIFICATION, QuestionType.VERIFICATION]
            ]
            other_templates = [
                t for t in templates 
                if t.question_type not in [QuestionType.CLARIFICATION, QuestionType.VERIFICATION]
            ]
            
            # Generate follow-up questions first
            for template in follow_up_templates[:max_questions//2]:
                question = self._generate_question_from_template(
                    template, entities, detected_patterns, len(questions)
                )
                questions.append(question)
            
            # Add other questions
            remaining_slots = max_questions - len(questions)
            for template in other_templates[:remaining_slots]:
                question = self._generate_question_from_template(
                    template, entities, detected_patterns, len(questions)
                )
                questions.append(question)
        else:
            # First interaction - focus on context and isolation
            context_templates = [
                t for t in templates
                if t.question_type in [QuestionType.CONTEXT, QuestionType.ISOLATION]
            ]
            other_templates = [
                t for t in templates
                if t.question_type not in [QuestionType.CONTEXT, QuestionType.ISOLATION]
            ]
            
            # Generate context questions first
            for template in context_templates[:max_questions//2]:
                question = self._generate_question_from_template(
                    template, entities, detected_patterns, len(questions)
                )
                questions.append(question)
            
            # Add other questions
            remaining_slots = max_questions - len(questions)
            for template in other_templates[:remaining_slots]:
                question = self._generate_question_from_template(
                    template, entities, detected_patterns, len(questions)
                )
                questions.append(question)
        
        return questions
    
    def _generate_question_from_template(
        self,
        template: QuestionTemplate,
        entities: Dict[str, Any],
        detected_patterns: Dict[str, Any],
        question_index: int
    ) -> DiagnosticQuestion:
        """Generate a specific question from a template"""
        
        # Prepare entity substitutions
        entity_subs = {}
        
        # Handle special case substitutions for common placeholders
        if "no_price" in template.template or "no_price" in template.vietnamese_template:
            entity_subs["no_price"] = self._find_entity_value(entities, ["menu_item", "product", "issue_type"], "hiển thị giá")
        
        if "incorrect_price" in template.template or "incorrect_price" in template.vietnamese_template:
            entity_subs["incorrect_price"] = self._find_entity_value(entities, ["price", "price_terms"], "giá")
        
        if "formula_change" in template.template or "formula_change" in template.vietnamese_template:
            entity_subs["formula_change"] = self._find_entity_value(entities, ["formula", "formula_terms"], "thay đổi công thức")
        
        if "formula_modifications" in template.template or "formula_modifications" in template.vietnamese_template:
            entity_subs["formula_modifications"] = self._find_entity_value(entities, ["formula", "formula_terms"], "các thay đổi công thức")
        
        if "data_sync" in template.template or "data_sync" in template.vietnamese_template:
            entity_subs["data_sync"] = self._find_entity_value(entities, ["sync", "sync_terms"], "việc đồng bộ dữ liệu")
        
        if "sync_issue" in template.template or "sync_issue" in template.vietnamese_template:
            entity_subs["sync_issue"] = self._find_entity_value(entities, ["sync", "sync_terms"], "vấn đề đồng bộ")
        
        if "specific_warehouse" in template.template or "specific_warehouse" in template.vietnamese_template:
            entity_subs["specific_warehouse"] = self._find_entity_value(entities, ["warehouse", "location"], "kho cụ thể")
        
        if "blacklist" in template.template or "blacklist" in template.vietnamese_template:
            entity_subs["blacklist"] = self._find_entity_value(entities, ["config_terms", "blacklist"], "danh sách đen")
        
        if "warehouse" in template.template or "warehouse" in template.vietnamese_template:
            entity_subs["warehouse"] = self._find_entity_value(entities, ["warehouse", "location"], "kho hàng")
        
        if "price_data" in template.template or "price_data" in template.vietnamese_template:
            entity_subs["price_data"] = self._find_entity_value(entities, ["price", "price_terms"], "giá cả")
        
        if "abnormal" in template.template or "abnormal" in template.vietnamese_template:
            entity_subs["abnormal"] = self._find_entity_value(entities, ["data_quality", "price_terms"], "bất thường")
        
        if "time_period" in template.template or "time_period" in template.vietnamese_template:
            entity_subs["time_period"] = self._find_entity_value(entities, ["time", "time_indicators"], "khoảng thời gian")
        
        if "missing_data" in template.template or "missing_data" in template.vietnamese_template:
            entity_subs["missing_data"] = self._find_entity_value(entities, ["data", "data_type"], "dữ liệu bị thiếu")
        
        if "slow_operation" in template.template or "slow_operation" in template.vietnamese_template:
            entity_subs["slow_operation"] = self._find_entity_value(entities, ["operation", "performance_issue"], "thao tác này")
        
        if "error_message" in template.template or "error_message" in template.vietnamese_template:
            entity_subs["error_message"] = self._find_entity_value(entities, ["error", "error_message"], "thông báo lỗi")
        
        if "issue" in template.template or "issue" in template.vietnamese_template:
            entity_subs["issue"] = self._find_entity_value(entities, ["issue_type", "menu_item"], "vấn đề này")
        
        if "problem" in template.template or "problem" in template.vietnamese_template:
            entity_subs["problem"] = self._find_entity_value(entities, ["issue_type", "performance_issue"], "vấn đề")
        
        if "operations" in template.template or "operations" in template.vietnamese_template:
            entity_subs["operations"] = self._find_entity_value(entities, ["system", "operation"], "hoạt động của bạn")
        
        if "affected_system" in template.template or "affected_system" in template.vietnamese_template:
            entity_subs["affected_system"] = self._find_entity_value(entities, ["system", "location"], "hệ thống bị ảnh hưởng")
        
        if "performance_settings" in template.template or "performance_settings" in template.vietnamese_template:
            entity_subs["performance_settings"] = self._find_entity_value(entities, ["config_terms", "settings"], "cài đặt hiệu suất")
        
        # Handle remaining required entities
        for entity_key in template.required_entities:
            if entity_key not in entity_subs:
                if entity_key in entities and entities[entity_key]:
                    entity_subs[entity_key] = entities[entity_key]
                else:
                    # Use generic placeholder if entity not found
                    entity_subs[entity_key] = self._get_generic_placeholder(entity_key)
        
        # Generate English question
        question = template.template
        for key, value in entity_subs.items():
            placeholder = f"{{{key}}}"
            if isinstance(value, list) and value:
                question = question.replace(placeholder, value[0] if len(value) == 1 else f"{value[0]} (or similar)")
            else:
                question = question.replace(placeholder, str(value))
        
        # Generate Vietnamese question
        vietnamese_question = template.vietnamese_template
        for key, value in entity_subs.items():
            placeholder = f"{{{key}}}"
            if isinstance(value, list) and value:
                vietnamese_question = vietnamese_question.replace(placeholder, value[0] if len(value) == 1 else f"{value[0]} (hoặc tương tự)")
            else:
                vietnamese_question = vietnamese_question.replace(placeholder, str(value))
        
        return DiagnosticQuestion(
            id=f"{template.id}_{question_index}_{hash(question) % 10000}",
            question=question,
            vietnamese_question=vietnamese_question,
            question_type=template.question_type,
            category=template.category,
            priority=template.priority,
            context={
                "template_id": template.id,
                "entities_used": entity_subs,
                "pattern_confidence": detected_patterns.get('confidence_scores', {}).get(template.category, 0.0)
            },
            expected_answer_type=self._get_expected_answer_type(template.question_type),
            follow_up_questions=template.follow_up_questions,
            conditions=template.conditions
        )
    
    def _get_generic_placeholder(self, entity_key: str) -> str:
        """Get generic placeholder for missing entities"""
        placeholders = {
            "menu_item": "sản phẩm cụ thể",
            "product": "sản phẩm", 
            "price": "giá",
            "warehouse": "kho hàng",
            "time": "thời gian",
            "error": "lỗi",
            "system": "hệ thống",
            "sync": "đồng bộ",
            "formula": "công thức",
            "data": "dữ liệu",
            "modifications": "thay đổi",
            "change": "thay đổi",
            "settings": "cài đặt",
            "operation": "thao tác",
            "duration": "thời gian",
            "message": "thông báo",
            "issue": "vấn đề",
            "problem": "vấn đề",
            "operations": "hoạt động",
            "users": "người dùng"
        }
        return placeholders.get(entity_key, "thông tin cụ thể")
    
    def _find_entity_value(self, entities: Dict[str, Any], possible_keys: List[str], default_value: str) -> str:
        """Find the best entity value from multiple possible keys"""
        for key in possible_keys:
            if key in entities and entities[key]:
                value = entities[key]
                if isinstance(value, list):
                    if value and len(value) > 0:
                        return str(value[0])
                elif value:
                    return str(value)
        return default_value
    
    def _get_expected_answer_type(self, question_type: QuestionType) -> str:
        """Get expected answer type for question type"""
        answer_types = {
            QuestionType.CLARIFICATION: "detailed_description",
            QuestionType.VERIFICATION: "confirmation_or_details",
            QuestionType.TROUBLESHOOTING: "steps_taken",
            QuestionType.IMPACT_ASSESSMENT: "impact_description",
            QuestionType.ISOLATION: "scope_or_location",
            QuestionType.ROOT_CAUSE: "cause_explanation",
            QuestionType.CONTEXT: "contextual_information"
        }
        return answer_types.get(question_type, "text")
    
    def get_questions_by_category(self, category: str) -> List[QuestionTemplate]:
        """Get all question templates for a specific category"""
        return [template for template in self.templates.values() if template.category == category]
    
    def add_custom_template(self, template: QuestionTemplate):
        """Add a custom question template"""
        self.templates[template.id] = template
        self.logger.info(f"Added custom question template: {template.id}")
    
    def clear_session_history(self, session_id: str):
        """Clear question history for a session"""
        if session_id in self.question_history:
            del self.question_history[session_id]
            self.logger.info(f"Cleared question history for session: {session_id}")

# Global instance
_diagnostic_generator = None

def get_diagnostic_generator() -> DiagnosticQuestionGenerator:
    """Get or create the global diagnostic question generator instance"""
    global _diagnostic_generator
    if _diagnostic_generator is None:
        _diagnostic_generator = DiagnosticQuestionGenerator()
    return _diagnostic_generator