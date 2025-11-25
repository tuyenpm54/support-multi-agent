"""
Information Collector - Dynamic Parameter Gathering for Tool Execution

This component handles the collection of user input for tool parameters when:
- Tool execution requires specific parameters that are not available
- Information collection is needed before validation or fix steps
- Dynamic question generation based on tool requirements and issue context

Key Responsibilities:
1. Analyze tool parameter requirements
2. Generate contextual questions for missing parameters
3. Collect and validate user responses
4. Merge collected information with existing context
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from abc import ABC, abstractmethod


class ParameterType:
    """Parameter types for information collection."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    EMAIL = "email"
    URL = "url"
    PASSWORD = "password"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    DATETIME = "datetime"
    FILE_PATH = "file_path"


class QuestionTemplate:
    """Template for generating contextual questions."""
    
    def __init__(
        self,
        parameter_name: str,
        parameter_type: str,
        question_template: str,
        validation_rules: Optional[Dict[str, Any]] = None,
        options: Optional[List[str]] = None,
        required: bool = True,
        context_hints: Optional[List[str]] = None
    ):
        self.parameter_name = parameter_name
        self.parameter_type = parameter_type
        self.question_template = question_template
        self.validation_rules = validation_rules or {}
        self.options = options
        self.required = required
        self.context_hints = context_hints or []


class InformationCollector:
    """
    Collects user input for tool parameters with contextual question generation.
    
    This component bridges the gap between tool requirements and available information
    by generating appropriate questions and collecting user responses.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Common question templates for different parameter types and contexts
        self.question_templates = self._initialize_question_templates()
    
    async def collect_tool_inputs(
        self,
        tool_config: Dict[str, Any],
        issue_context: Dict[str, Any],
        session_state: Any,
        user_input: str = ""
    ) -> Dict[str, Any]:
        """
        Collect tool inputs by identifying missing parameters and asking user questions.
        
        Args:
            tool_config: Configuration of the tool to execute
            issue_context: Issue details and context
            session_state: Current session state
            user_input: Initial user input
            
        Returns:
            Complete parameter set for tool execution
        """
        try:
            self.logger.info(f"Collecting inputs for tool: {tool_config.get('name', 'unknown')}")
            
            # Step 1: Identify required parameters for the tool
            required_params = await self._identify_required_parameters(tool_config, issue_context)
            
            # Step 2: Extract available parameters from context
            available_params = await self._extract_available_parameters(
                required_params, issue_context, user_input
            )
            
            # Step 3: Identify missing parameters
            missing_params = {
                param: config for param, config in required_params.items()
                if param not in available_params
            }
            
            # Step 4: Generate questions for missing parameters
            if missing_params:
                questions = await self._generate_questions(
                    missing_params, tool_config, issue_context
                )
                
                # Step 5: Ask user questions and collect responses
                collected_params = await self._ask_user_questions(
                    questions, session_state, tool_config, issue_context
                )
                
                # Step 6: Validate collected parameters
                validated_params = await self._validate_collected_parameters(
                    collected_params, missing_params
                )
                
                available_params.update(validated_params)
            
            # Step 7: Final parameter completeness check
            final_params = await self._ensure_parameter_completeness(
                available_params, required_params
            )
            
            self.logger.info(f"Collected {len(final_params)} parameters for tool {tool_config.get('name')}")
            
            return final_params
            
        except Exception as e:
            self.logger.error(f"Information collection failed: {str(e)}")
            return {}
    
    async def _identify_required_parameters(
        self, tool_config: Dict[str, Any], issue_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Identify all parameters required for tool execution."""
        try:
            # Get parameter definitions from tool config
            param_definitions = tool_config.get('parameters', {})
            required_params = {}
            
            for param_name, param_config in param_definitions.items():
                # Check if parameter is required or conditionally required
                is_required = param_config.get('required', False)
                
                # Check conditional requirements
                if not is_required:
                    condition = param_config.get('required_if')
                    if condition:
                        is_required = await self._evaluate_condition(condition, issue_context)
                
                if is_required:
                    required_params[param_name] = {
                        'type': param_config.get('type', ParameterType.STRING),
                        'description': param_config.get('description', ''),
                        'validation': param_config.get('validation', {}),
                        'options': param_config.get('options', []),
                        'default': param_config.get('default'),
                        'sensitive': param_config.get('sensitive', False)
                    }
            
            return required_params
            
        except Exception as e:
            self.logger.error(f"Failed to identify required parameters: {str(e)}")
            return {}
    
    async def _extract_available_parameters(
        self,
        required_params: Dict[str, Any],
        issue_context: Dict[str, Any],
        user_input: str
    ) -> Dict[str, Any]:
        """Extract parameters that are already available from context."""
        available_params = {}
        
        try:
            # Extract from issue details
            issue_params = await self._extract_from_issue_details(required_params, issue_context)
            available_params.update(issue_params)
            
            # Extract from user input
            input_params = await self._extract_from_user_input(required_params, user_input)
            available_params.update(input_params)
            
            # Apply defaults for missing non-sensitive parameters
            defaults = await self._apply_parameter_defaults(required_params, available_params)
            available_params.update(defaults)
            
            return available_params
            
        except Exception as e:
            self.logger.error(f"Failed to extract available parameters: {str(e)}")
            return {}
    
    async def _generate_questions(
        self,
        missing_params: Dict[str, Any],
        tool_config: Dict[str, Any],
        issue_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate contextual questions for missing parameters."""
        questions = []
        
        try:
            for param_name, param_config in missing_params.items():
                # Get appropriate question template
                template = await self._get_question_template(
                    param_name, param_config, tool_config, issue_context
                )
                
                # Generate contextual question
                question = await self._generate_contextual_question(
                    template, param_name, param_config, issue_context
                )
                
                questions.append({
                    'parameter_name': param_name,
                    'parameter_type': param_config['type'],
                    'question': question,
                    'validation_rules': param_config['validation'],
                    'options': param_config.get('options', []),
                    'required': True,
                    'sensitive': param_config.get('sensitive', False)
                })
            
            return questions
            
        except Exception as e:
            self.logger.error(f"Failed to generate questions: {str(e)}")
            return []
    
    async def _ask_user_questions(
        self,
        questions: List[Dict[str, Any]],
        session_state: Any,
        tool_config: Dict[str, Any],
        issue_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ask user questions and collect responses."""
        responses = {}
        
        try:
            for question in questions:
                param_name = question['parameter_name']
                
                # Generate the question to ask user
                user_question = await self._format_user_question(question, tool_config, issue_context)
                
                # Simulate user response (in real implementation, this would interact with UI)
                response = await self._simulate_user_response(question, user_question)
                
                # Store the response
                responses[param_name] = response
                
                self.logger.info(f"Collected parameter {param_name}: {'[HIDDEN]' if question['sensitive'] else response}")
            
            return responses
            
        except Exception as e:
            self.logger.error(f"Failed to ask user questions: {str(e)}")
            return {}
    
    async def _validate_collected_parameters(
        self,
        collected_params: Dict[str, Any],
        param_configs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate collected parameters against their validation rules."""
        validated_params = {}
        
        try:
            for param_name, value in collected_params.items():
                param_config = param_configs.get(param_name, {})
                
                # Validate the parameter
                validation_result = await self._validate_parameter(
                    value, param_config
                )
                
                if validation_result['valid']:
                    validated_params[param_name] = validation_result['value']
                else:
                    self.logger.warning(f"Parameter {param_name} validation failed: {validation_result['error']}")
                    # For now, still include the invalid value but log the issue
                    # In production, we might want to re-ask the question
                    validated_params[param_name] = value
            
            return validated_params
            
        except Exception as e:
            self.logger.error(f"Failed to validate collected parameters: {str(e)}")
            return collected_params
    
    async def _evaluate_condition(self, condition: Dict[str, Any], issue_context: Dict[str, Any]) -> bool:
        """Evaluate conditional parameter requirements."""
        try:
            condition_type = condition.get('type', 'field_exists')
            
            if condition_type == 'field_exists':
                field = condition.get('field')
                return field in issue_context and bool(issue_context[field])
            
            elif condition_type == 'field_equals':
                field = condition.get('field')
                value = condition.get('value')
                return issue_context.get(field) == value
            
            elif condition_type == 'field_in':
                field = condition.get('field')
                values = condition.get('values', [])
                return issue_context.get(field) in values
            
            elif condition_type == 'custom':
                # Custom condition evaluation
                condition_func = condition.get('function')
                if callable(condition_func):
                    return condition_func(issue_context)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to evaluate condition: {str(e)}")
            return False
    
    async def _extract_from_issue_details(
        self, required_params: Dict[str, Any], issue_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters from issue details and context."""
        extracted = {}
        
        try:
            # Direct field matches
            for param_name, param_config in required_params.items():
                if param_name in issue_context:
                    extracted[param_name] = issue_context[param_name]
            
            # Smart extraction based on parameter name patterns
            for param_name, param_config in required_params.items():
                if param_name not in extracted:
                    value = await self._smart_extract_parameter(param_name, issue_context)
                    if value is not None:
                        extracted[param_name] = value
            
            return extracted
            
        except Exception as e:
            self.logger.error(f"Failed to extract from issue details: {str(e)}")
            return {}
    
    async def _extract_from_user_input(
        self, required_params: Dict[str, Any], user_input: str
    ) -> Dict[str, Any]:
        """Extract parameters from user input using NLP techniques."""
        extracted = {}
        
        try:
            if not user_input:
                return extracted
            
            # For now, implement simple extraction patterns
            # In production, this would use more sophisticated NLP
            
            # Email extraction
            import re
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, user_input)
            if emails and 'email' in required_params:
                extracted['email'] = emails[0]
            
            # URL extraction
            url_pattern = r'https?://[^\s<>"{}|\\^`[\]]+'
            urls = re.findall(url_pattern, user_input)
            if urls and 'url' in required_params:
                extracted['url'] = urls[0]
            
            # Number extraction
            number_pattern = r'\b\d+\.?\d*\b'
            numbers = re.findall(number_pattern, user_input)
            if numbers:
                # Try to match numbers to parameter requirements
                for param_name, param_config in required_params.items():
                    if param_config['type'] in [ParameterType.INTEGER, ParameterType.FLOAT]:
                        if param_name not in extracted and numbers:
                            value = numbers[0]
                            if param_config['type'] == ParameterType.INTEGER:
                                extracted[param_name] = int(float(value))
                            else:
                                extracted[param_name] = float(value)
                            break
            
            return extracted
            
        except Exception as e:
            self.logger.error(f"Failed to extract from user input: {str(e)}")
            return {}
    
    async def _apply_parameter_defaults(
        self, required_params: Dict[str, Any], available_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply default values for non-sensitive missing parameters."""
        defaults = {}
        
        try:
            for param_name, param_config in required_params.items():
                if (param_name not in available_params and 
                    'default' in param_config and 
                    not param_config.get('sensitive', False)):
                    defaults[param_name] = param_config['default']
            
            return defaults
            
        except Exception as e:
            self.logger.error(f"Failed to apply parameter defaults: {str(e)}")
            return {}
    
    async def _get_question_template(
        self, param_name: str, param_config: Dict[str, Any], 
        tool_config: Dict[str, Any], issue_context: Dict[str, Any]
    ) -> QuestionTemplate:
        """Get appropriate question template for a parameter."""
        
        # Check for custom templates first
        template_key = f"{tool_config.get('category', 'general')}_{param_name}"
        if template_key in self.question_templates:
            return self.question_templates[template_key]
        
        # Check for parameter-type templates
        type_key = param_config['type']
        if type_key in self.question_templates:
            return self.question_templates[type_key]
        
        # Fall back to generic template
        return self.question_templates.get('generic', QuestionTemplate(
            param_name, param_config['type'], "What is the {parameter_name}?"
        ))
    
    async def _generate_contextual_question(
        self, template: QuestionTemplate, param_name: str, 
        param_config: Dict[str, Any], issue_context: Dict[str, Any]
    ) -> str:
        """Generate a contextual question based on template and issue context."""
        
        # Base question from template
        question = template.question_template.format(
            parameter_name=param_name.replace('_', ' ').title(),
            description=param_config.get('description', ''),
            **issue_context
        )
        
        # Add context hints if available
        if template.context_hints:
            relevant_hints = [
                hint for hint in template.context_hints 
                if any(keyword in issue_context.get('title', '').lower() + issue_context.get('description', '').lower() 
                      for keyword in hint.lower().split())
            ]
            if relevant_hints:
                question += f" Context: {relevant_hints[0]}"
        
        # Add options hint for select parameters
        if param_config.get('options'):
            options_str = ", ".join(str(opt) for opt in param_config['options'][:5])
            if len(param_config['options']) > 5:
                options_str += f", or {len(param_config['options']) - 5} more options"
            question += f" Options: {options_str}"
        
        return question
    
    async def _simulate_user_response(
        self, question: Dict[str, Any], user_question: str
    ) -> Any:
        """Simulate user response for testing purposes."""
        # In production, this would interact with the user interface
        
        param_type = question['parameter_type']
        param_name = question['parameter_name']
        
        # Generate realistic test responses based on parameter type and name
        if param_type == ParameterType.EMAIL:
            if 'username' in param_name:
                return "test.user@example.com"
            elif 'admin' in param_name:
                return "admin@company.com"
            else:
                return "user@example.com"
        
        elif param_type == ParameterType.STRING:
            if 'username' in param_name:
                return "john_doe"
            elif 'name' in param_name:
                return "John Doe"
            elif 'title' in param_name:
                return "Test Issue Title"
            elif 'description' in param_name:
                return "Test issue description"
            else:
                return f"test_{param_name}_value"
        
        elif param_type == ParameterType.INTEGER:
            if 'port' in param_name:
                return 8080
            elif 'count' in param_name or 'number' in param_name:
                return 5
            else:
                return 1
        
        elif param_type == ParameterType.BOOLEAN:
            return True
        
        elif param_type == ParameterType.SELECT:
            options = question.get('options', [])
            return options[0] if options else "option1"
        
        else:
            return f"test_value_for_{param_name}"
    
    async def _validate_parameter(
        self, value: Any, param_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate a single parameter against its validation rules."""
        try:
            param_type = param_config.get('type', ParameterType.STRING)
            validation_rules = param_config.get('validation', {})
            
            # Type validation
            if not await self._validate_parameter_type(value, param_type):
                return {
                    'valid': False,
                    'error': f"Invalid type. Expected {param_type}, got {type(value).__name__}",
                    'value': value
                }
            
            # Custom validation rules
            for rule_name, rule_config in validation_rules.items():
                if not await self._apply_validation_rule(value, rule_name, rule_config):
                    return {
                        'valid': False,
                        'error': f"Validation failed for rule: {rule_name}",
                        'value': value
                    }
            
            return {
                'valid': True,
                'value': value
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"Validation error: {str(e)}",
                'value': value
            }
    
    async def _validate_parameter_type(self, value: Any, expected_type: str) -> bool:
        """Validate parameter type."""
        try:
            if expected_type == ParameterType.STRING:
                return isinstance(value, str)
            elif expected_type == ParameterType.INTEGER:
                return isinstance(value, int)
            elif expected_type == ParameterType.FLOAT:
                return isinstance(value, (int, float))
            elif expected_type == ParameterType.BOOLEAN:
                return isinstance(value, bool)
            elif expected_type == ParameterType.EMAIL:
                import re
                pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
                return isinstance(value, str) and re.match(pattern, value) is not None
            elif expected_type == ParameterType.URL:
                import re
                pattern = r'^https?://[^\s<>"{}|\\^`[\]]+$'
                return isinstance(value, str) and re.match(pattern, value) is not None
            else:
                return True  # Unknown type, assume valid
                
        except Exception:
            return False
    
    async def _apply_validation_rule(self, value: Any, rule_name: str, rule_config: Any) -> bool:
        """Apply a specific validation rule."""
        try:
            if rule_name == 'min_length':
                return len(str(value)) >= rule_config
            elif rule_name == 'max_length':
                return len(str(value)) <= rule_config
            elif rule_name == 'min_value':
                return float(value) >= float(rule_config)
            elif rule_name == 'max_value':
                return float(value) <= float(rule_config)
            elif rule_name == 'pattern':
                import re
                return re.match(rule_config, str(value)) is not None
            elif rule_name == 'allowed_values':
                return value in rule_config
            else:
                return True  # Unknown rule, assume valid
                
        except Exception:
            return False
    
    async def _smart_extract_parameter(self, param_name: str, issue_context: Dict[str, Any]) -> Any:
        """Smart parameter extraction based on name patterns."""
        # Simple pattern matching for common parameter names
        param_lower = param_name.lower()
        
        # Check direct field matches
        if param_lower in issue_context:
            return issue_context[param_lower]
        
        # Check similar field names
        for field_name, field_value in issue_context.items():
            if param_lower in field_name.lower() or field_name.lower() in param_lower:
                return field_value
        
        return None
    
    async def _format_user_question(
        self, question: Dict[str, Any], tool_config: Dict[str, Any], issue_context: Dict[str, Any]
    ) -> str:
        """Format question for user display."""
        base_question = question['question']
        
        # Add tool context
        tool_name = tool_config.get('name', 'tool')
        question = f"For the {tool_name} tool, {base_question.lower()}"
        
        # Add issue context
        issue_title = issue_context.get('title', '')
        if issue_title:
            question += f" (Issue: {issue_title})"
        
        return question
    
    async def _ensure_parameter_completeness(
        self, available_params: Dict[str, Any], required_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ensure all required parameters are present, applying defaults if needed."""
        final_params = available_params.copy()
        
        for param_name, param_config in required_params.items():
            if param_name not in final_params:
                # Try to apply a default value
                default_value = param_config.get('default')
                if default_value is not None:
                    final_params[param_name] = default_value
                    self.logger.info(f"Applied default value for {param_name}: {default_value}")
                else:
                    self.logger.warning(f"Missing required parameter: {param_name}")
        
        return final_params
    
    def _initialize_question_templates(self) -> Dict[str, QuestionTemplate]:
        """Initialize default question templates."""
        return {
            ParameterType.STRING: QuestionTemplate(
                "generic_string", ParameterType.STRING, 
                "What is the {parameter_name}?"
            ),
            ParameterType.INTEGER: QuestionTemplate(
                "generic_integer", ParameterType.INTEGER,
                "What is the {parameter_name} (please provide a number)?"
            ),
            ParameterType.EMAIL: QuestionTemplate(
                "generic_email", ParameterType.EMAIL,
                "What is the email address for {parameter_name}?"
            ),
            ParameterType.URL: QuestionTemplate(
                "generic_url", ParameterType.URL,
                "What is the URL for {parameter_name}?"
            ),
            ParameterType.SELECT: QuestionTemplate(
                "generic_select", ParameterType.SELECT,
                "Please select the {parameter_name} from the available options."
            ),
            # Category-specific templates
            "user_authentication_username": QuestionTemplate(
                "username", ParameterType.STRING,
                "What is the username that is experiencing the issue?",
                context_hints=["login", "authentication", "user"]
            ),
            "performance_process_name": QuestionTemplate(
                "process_name", ParameterType.STRING,
                "What is the name of the process causing performance issues?",
                context_hints=["performance", "cpu", "memory", "process"]
            ),
            "database_table_name": QuestionTemplate(
                "table_name", ParameterType.STRING,
                "Which database table is affected?",
                context_hints=["database", "table", "sql", "query"]
            ),
            "network_endpoint": QuestionTemplate(
                "endpoint", ParameterType.URL,
                "What is the network endpoint or API URL that is failing?",
                context_hints=["network", "api", "endpoint", "connection"]
            ),
            "generic": QuestionTemplate(
                "generic", ParameterType.STRING,
                "Please provide the {parameter_name}: {description}"
            )
        }


# Global information collector instance
information_collector = InformationCollector()


def get_information_collector() -> InformationCollector:
    """Get the global information collector instance."""
    return information_collector