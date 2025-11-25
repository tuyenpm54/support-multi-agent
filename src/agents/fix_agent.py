"""
Fix Agent - Unified Issue Resolution with Validation and Fix Steps

This agent implements the core fix logic following the new architecture:
- Handles both general and detailed issues
- For each detailed issue: VALIDATE → COLLECT → FIX → VALIDATE
- Integrates resolution-loop logic from previous ResolutionLoopAgent
- Collects user input for tool parameters when needed

Key Responsibilities:
1. Issue hierarchy processing (general → detailed issues)
2. Two-step resolution: validation + fix for each detailed issue
3. Information collection for tool input parameters
4. Progress tracking across multiple detailed issues
5. Integration with tool management system
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from src.agents.base import BaseAgent
from src.models.session import SessionState, FixResult
from src.core.hierarchical_semantic_search import get_hierarchical_search_service


class ValidationStatus(Enum):
    """Validation status for tracking issue confirmation."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    FAILED = "failed"


class FixStatus(Enum):
    """Fix status for tracking resolution attempts."""
    PENDING = "pending"
    ATTEMPTING = "attempting"
    RESOLVED = "resolved"
    FAILED = "failed"
    SKIPPED = "skipped"


class DetailedIssueProcessingResult:
    """Result of processing a detailed issue through validation and fix steps."""
    
    def __init__(
        self,
        issue_id: str,
        title: str,
        validation_status: ValidationStatus,
        fix_status: FixStatus,
        success: bool,
        processing_time: float,
        validation_details: Optional[Dict[str, Any]] = None,
        fix_details: Optional[Dict[str, Any]] = None,
        error_details: Optional[str] = None,
        user_feedback: Optional[str] = None
    ):
        self.issue_id = issue_id
        self.title = title
        self.validation_status = validation_status
        self.fix_status = fix_status
        self.success = success
        self.processing_time = processing_time
        self.validation_details = validation_details or {}
        self.fix_details = fix_details or {}
        self.error_details = error_details
        self.user_feedback = user_feedback
        self.processed_at = datetime.now()


class FixAgent(BaseAgent):
    """
    Agent for comprehensive issue resolution with validation and fix steps.
    
    Implements the core logic for:
    - Processing general issues by iterating through detailed issues
    - Two-step resolution: validation + fix for each detailed issue
    - Information collection for tool parameters
    - Progress tracking and user confirmation
    """
    
    def __init__(self):
        super().__init__("FixAgent")
        self.logger = logging.getLogger(__name__)
        self.semantic_search_service = None
        
        # Configuration
        self.max_fix_attempts = 3
        self.validation_timeout = 300  # 5 minutes
        self.information_collection_timeout = 600  # 10 minutes
        
        # Processing state
        self.processing_history: List[DetailedIssueProcessingResult] = []
        self.current_general_issue_id = None
        self.resolved_count = 0
        self.failed_count = 0
        
        # Information collection (will be implemented separately)
        self.information_collector = None
    
    async def initialize(self):
        """Initialize the fix agent."""
        try:
            self.semantic_search_service = await get_hierarchical_search_service()
            self.logger.info("Fix agent initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize fix agent: {str(e)}")
            raise
    
    async def execute(self, session_state: SessionState, **kwargs) -> Dict[str, Any]:
        """
        Execute fix process for issues.
        
        Args:
            session_state: Current session state
            **kwargs: Additional parameters (issue_id, user_input, etc.)
            
        Returns:
            Fix result with processing details and next actions
        """
        issue_id = kwargs.get('issue_id')
        user_input = kwargs.get('user_input', '')
        
        if not issue_id:
            raise ValueError("issue_id is required for fix agent")
        
        self.logger.info(f"Starting fix process for issue: {issue_id}")
        
        try:
            # Step 1: Get issue details and hierarchy
            issue_details = await self._get_issue_details(issue_id)
            
            # Step 2: Process based on issue type
            if issue_details['issue_type'] == 'detailed':
                # Single detailed issue processing
                result = await self._process_detailed_issue(
                    session_state, issue_details, user_input
                )
            else:
                # General issue - iterate through detailed issues
                result = await self._process_general_issue(
                    session_state, issue_details, user_input
                )
            
            # Step 3: Track processing results
            await self._track_processing_results(session_state, result)
            
            return {
                "success": True,
                "issue_id": issue_id,
                "issue_type": issue_details['issue_type'],
                "result": result,
                "progress": {
                    "total_detailed": result.get('total_detailed_issues', 1),
                    "resolved": result.get('resolved_count', 0),
                    "failed": result.get('failed_count', 0),
                    "remaining": result.get('remaining_count', 0)
                },
                "processing_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Fix process failed: {str(e)}")
            return await self.handle_error(e, session_state)
    
    async def _get_issue_details(self, issue_id: str) -> Dict[str, Any]:
        """Get detailed information about an issue including hierarchy."""
        try:
            async with self.semantic_search_service._connection_pool.acquire() as conn:
                # Get issue details (reused from ResolutionLoopAgent)
                issue = await conn.fetchrow("""
                    SELECT i.*, 
                           COALESCE(child_count.child_count, 0) as child_count,
                           COALESCE(parent_info.parent_title, NULL) as parent_title
                    FROM issues i
                    LEFT JOIN (
                        SELECT parent_issue_id, COUNT(*) as child_count
                        FROM issues
                        WHERE parent_issue_id IS NOT NULL
                        GROUP BY parent_issue_id
                    ) child_count ON i.issue_id = child_count.parent_issue_id
                    LEFT JOIN (
                        SELECT issue_id, title as parent_title
                        FROM issues
                    ) parent_info ON i.parent_issue_id = parent_info.issue_id
                    WHERE i.issue_id = $1
                """, issue_id)
                
                if not issue:
                    raise ValueError(f"Issue not found: {issue_id}")
                
                issue_details = dict(issue)
                
                # Get detailed children for general issues
                if issue_details['issue_type'] == 'general' and issue_details['child_count'] > 0:
                    children = await conn.fetch("""
                        SELECT * FROM get_child_issues_ordered($1)
                        ORDER BY order_index
                    """, issue_id)
                    
                    issue_details['detailed_issues'] = [dict(child) for child in children]
                else:
                    issue_details['detailed_issues'] = []
                
                return issue_details
                
        except Exception as e:
            self.logger.error(f"Failed to get issue details: {str(e)}")
            raise
    
    async def _process_detailed_issue(
        self,
        session_state: SessionState,
        issue_details: Dict[str, Any],
        user_input: str
    ) -> Dict[str, Any]:
        """Process a single detailed issue with validation and fix steps."""
        issue_id = issue_details['issue_id']
        issue_title = issue_details['title']
        
        self.logger.info(f"Processing detailed issue: {issue_title}")
        
        start_time = datetime.now()
        
        try:
            # STEP 1: VALIDATE the issue is actually happening
            self.logger.info(f"Step 1: Validating issue exists - {issue_title}")
            validation_result = await self._validate_issue_exists(
                session_state, issue_details, user_input
            )
            
            if not validation_result['confirmed']:
                self.logger.info(f"Issue validation failed for: {issue_title}")
                processing_time = (datetime.now() - start_time).total_seconds()
                
                result = DetailedIssueProcessingResult(
                    issue_id=issue_id,
                    title=issue_title,
                    validation_status=ValidationStatus.REJECTED,
                    fix_status=FixStatus.SKIPPED,
                    success=False,
                    processing_time=processing_time,
                    validation_details=validation_result
                )
                
                self.processing_history.append(result)
                self.failed_count += 1
                
                return {
                    "success": False,
                    "issue_id": issue_id,
                    "issue_title": issue_title,
                    "validation_result": validation_result,
                    "fix_result": None,
                    "processing_skipped": True,
                    "reason": "Issue validation failed"
                }
            
            # STEP 2: COLLECT information needed for tool execution
            self.logger.info(f"Step 2: Collecting information for fix - {issue_title}")
            tool_inputs = await self._collect_fix_information(
                session_state, issue_details, user_input
            )
            
            # STEP 3: EXECUTE the fix
            self.logger.info(f"Step 3: Executing fix - {issue_title}")
            fix_result = await self._execute_fix(
                session_state, issue_details, tool_inputs
            )
            
            # STEP 4: VALIDATE the fix was successful
            self.logger.info(f"Step 4: Validating fix success - {issue_title}")
            fix_validation = await self._validate_fix_success(
                session_state, issue_details, fix_result
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Create processing result
            result = DetailedIssueProcessingResult(
                issue_id=issue_id,
                title=issue_title,
                validation_status=ValidationStatus.CONFIRMED,
                fix_status=FixStatus.RESOLVED if fix_validation['success'] else FixStatus.FAILED,
                success=fix_validation['success'],
                processing_time=processing_time,
                validation_details=validation_result,
                fix_details={
                    "tool_inputs": tool_inputs,
                    "execution_result": fix_result,
                    "validation_result": fix_validation
                }
            )
            
            self.processing_history.append(result)
            
            if fix_validation['success']:
                self.resolved_count += 1
                self.logger.info(f"Successfully resolved issue: {issue_title}")
            else:
                self.failed_count += 1
                self.logger.warning(f"Failed to resolve issue: {issue_title}")
            
            return {
                "success": fix_validation['success'],
                "issue_id": issue_id,
                "issue_title": issue_title,
                "validation_result": validation_result,
                "tool_inputs": tool_inputs,
                "fix_result": fix_result,
                "fix_validation": fix_validation,
                "processing_time": processing_time
            }
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Error processing detailed issue {issue_title}: {str(e)}")
            
            result = DetailedIssueProcessingResult(
                issue_id=issue_id,
                title=issue_title,
                validation_status=ValidationStatus.FAILED,
                fix_status=FixStatus.FAILED,
                success=False,
                processing_time=processing_time,
                error_details=str(e)
            )
            
            self.processing_history.append(result)
            self.failed_count += 1
            
            return {
                "success": False,
                "issue_id": issue_id,
                "issue_title": issue_title,
                "error": str(e),
                "processing_time": processing_time
            }
    
    async def _process_general_issue(
        self,
        session_state: SessionState,
        issue_details: Dict[str, Any],
        user_input: str
    ) -> Dict[str, Any]:
        """Process a general issue by iterating through its detailed issues."""
        general_issue_id = issue_details['issue_id']
        general_title = issue_details['title']
        detailed_issues = issue_details.get('detailed_issues', [])
        
        self.logger.info(f"Processing general issue: {general_title} with {len(detailed_issues)} detailed issues")
        
        self.current_general_issue_id = general_issue_id
        processing_results = []
        resolved_count = 0
        failed_count = 0
        
        for index, detailed_issue in enumerate(detailed_issues):
            self.logger.info(f"Processing detailed issue {index + 1}/{len(detailed_issues)}: {detailed_issue['title']}")
            
            try:
                # Process the detailed issue
                detail_result = await self._process_detailed_issue(
                    session_state, detailed_issue, user_input
                )
                
                processing_results.append({
                    "detailed_issue_id": detailed_issue['issue_id'],
                    "detailed_title": detailed_issue['title'],
                    "result": detail_result
                })
                
                if detail_result['success']:
                    resolved_count += 1
                else:
                    failed_count += 1
                
                # Get user confirmation for the resolution
                if detail_result['success']:
                    user_confirmed = await self._get_user_confirmation_for_detailed_issue(
                        session_state, detailed_issue['title'], detail_result
                    )
                    
                    if user_confirmed:
                        self.logger.info(f"User confirmed resolution for: {detailed_issue['title']}")
                        
                        # Ask if the general issue is fully resolved
                        fully_resolved = await self._ask_if_general_issue_resolved(
                            session_state, general_title, resolved_count, len(detailed_issues) - index - 1
                        )
                        
                        if fully_resolved:
                            self.logger.info(f"User confirmed general issue {general_title} is fully resolved")
                            break
                        else:
                            self.logger.info(f"User wants to continue with remaining detailed issues")
                    else:
                        self.logger.info(f"User did not confirm resolution for: {detailed_issue['title']}")
                        failed_count += 1
                        resolved_count -= 1  # Revert the increment
                        
            except Exception as e:
                self.logger.error(f"Error processing detailed issue {detailed_issue['title']}: {str(e)}")
                
                processing_results.append({
                    "detailed_issue_id": detailed_issue['issue_id'],
                    "detailed_title": detailed_issue['title'],
                    "result": {
                        "success": False,
                        "error": str(e)
                    }
                })
                failed_count += 1
        
        remaining_count = len(detailed_issues) - resolved_count - failed_count
        
        return {
            "success": resolved_count > 0,
            "general_issue_id": general_issue_id,
            "general_title": general_title,
            "total_detailed_issues": len(detailed_issues),
            "resolved_count": resolved_count,
            "failed_count": failed_count,
            "remaining_count": remaining_count,
            "processing_results": processing_results
        }
    
    async def _validate_issue_exists(
        self,
        session_state: SessionState,
        issue_details: Dict[str, Any],
        user_input: str
    ) -> Dict[str, Any]:
        """
        Validate that the issue actually exists by calling diagnostic tools.
        This is Step 1 of the two-step resolution process.
        """
        try:
            # Get validation tools for this issue category
            validation_tools = await self._get_validation_tools(issue_details)
            
            if not validation_tools:
                # If no validation tools available, assume issue exists based on user input
                return {
                    "confirmed": True,
                    "confidence": 0.7,
                    "method": "user_input_assumption",
                    "details": "No validation tools available, proceeding based on user input"
                }
            
            # Execute validation tools
            validation_results = []
            for tool in validation_tools:
                try:
                    # Collect information needed for validation tool
                    tool_inputs = await self._collect_validation_tool_inputs(
                        tool, issue_details, user_input
                    )
                    
                    # Execute the validation tool
                    tool_result = await self._execute_validation_tool(tool, tool_inputs)
                    validation_results.append({
                        "tool": tool['name'],
                        "result": tool_result,
                        "success": tool_result.get('success', False)
                    })
                    
                except Exception as e:
                    self.logger.error(f"Validation tool {tool['name']} failed: {str(e)}")
                    validation_results.append({
                        "tool": tool['name'],
                        "result": {"success": False, "error": str(e)},
                        "success": False
                    })
            
            # Determine if issue is confirmed based on validation results
            confirmed_count = sum(1 for r in validation_results if r['success'])
            total_tools = len(validation_results)
            confirmation_rate = confirmed_count / total_tools if total_tools > 0 else 0
            
            # Issue is confirmed if >60% of validation tools pass
            confirmed = confirmation_rate > 0.6
            
            return {
                "confirmed": confirmed,
                "confidence": confirmation_rate,
                "method": "diagnostic_tools",
                "validation_results": validation_results,
                "details": f"Issue confirmed by {confirmed_count}/{total_tools} validation tools"
            }
            
        except Exception as e:
            self.logger.error(f"Issue validation failed: {str(e)}")
            return {
                "confirmed": False,
                "confidence": 0.0,
                "method": "validation_failed",
                "error": str(e),
                "details": "Validation process encountered an error"
            }
    
    async def _collect_fix_information(
        self,
        session_state: SessionState,
        issue_details: Dict[str, Any],
        user_input: str
    ) -> Dict[str, Any]:
        """
        Collect information needed for tool execution.
        This is Step 2 of the two-step resolution process.
        """
        try:
            # Get fix tools for this issue
            fix_tools = await self._get_fix_tools(issue_details)
            
            if not fix_tools:
                return {}
            
            # Collect all required parameters for all fix tools
            all_required_params = {}
            for tool in fix_tools:
                tool_params = await self._identify_required_tool_parameters(tool, issue_details)
                all_required_params.update(tool_params)
            
            # Check which parameters are already available from context or user input
            available_params = await self._extract_available_parameters(
                all_required_params, issue_details, user_input
            )
            
            # Identify missing parameters that need to be collected from user
            missing_params = {
                param: config for param, config in all_required_params.items()
                if param not in available_params
            }
            
            if missing_params:
                # Collect missing parameters from user
                collected_params = await self._collect_parameters_from_user(
                    missing_params, session_state
                )
                available_params.update(collected_params)
            
            return available_params
            
        except Exception as e:
            self.logger.error(f"Information collection failed: {str(e)}")
            return {}
    
    async def _execute_fix(
        self,
        session_state: SessionState,
        issue_details: Dict[str, Any],
        tool_inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the fix by running appropriate tools.
        This is Step 3 of the two-step resolution process.
        """
        try:
            # Get fix tools for this issue
            fix_tools = await self._get_fix_tools(issue_details)
            
            if not fix_tools:
                return {
                    "success": False,
                    "error": "No fix tools available for this issue",
                    "tools_executed": []
                }
            
            execution_results = []
            
            for tool in fix_tools:
                try:
                    self.logger.info(f"Executing fix tool: {tool['name']}")
                    
                    # Prepare tool-specific inputs
                    tool_specific_inputs = await self._prepare_tool_inputs(
                        tool, tool_inputs, issue_details
                    )
                    
                    # Execute the tool
                    tool_result = await self._execute_tool(tool, tool_specific_inputs)
                    
                    execution_results.append({
                        "tool": tool['name'],
                        "inputs": tool_specific_inputs,
                        "result": tool_result,
                        "success": tool_result.get('success', False),
                        "execution_time": tool_result.get('execution_time', 0)
                    })
                    
                except Exception as e:
                    self.logger.error(f"Fix tool {tool['name']} failed: {str(e)}")
                    execution_results.append({
                        "tool": tool['name'],
                        "result": {"success": False, "error": str(e)},
                        "success": False,
                        "error": str(e)
                    })
            
            # Determine overall success
            successful_tools = sum(1 for r in execution_results if r['success'])
            total_tools = len(execution_results)
            success_rate = successful_tools / total_tools if total_tools > 0 else 0
            
            return {
                "success": success_rate > 0.6,  # 60% of tools must succeed
                "execution_results": execution_results,
                "summary": {
                    "total_tools": total_tools,
                    "successful_tools": successful_tools,
                    "success_rate": success_rate
                }
            }
            
        except Exception as e:
            self.logger.error(f"Fix execution failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "execution_results": []
            }
    
    async def _validate_fix_success(
        self,
        session_state: SessionState,
        issue_details: Dict[str, Any],
        fix_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate that the fix was successful.
        This is Step 4 of the two-step resolution process.
        """
        try:
            if not fix_result['success']:
                return {
                    "success": False,
                    "confidence": 0.0,
                    "method": "fix_execution_failed",
                    "details": "Cannot validate success because fix execution failed"
                }
            
            # Get validation criteria from issue details
            validation_criteria = issue_details.get('validation_criteria', [])
            
            if not validation_criteria:
                # Default validation - ask user for confirmation
                user_confirmation = await self._get_user_fix_confirmation(
                    session_state, issue_details, fix_result
                )
                
                return {
                    "success": user_confirmation,
                    "confidence": 0.8 if user_confirmation else 0.2,
                    "method": "user_confirmation",
                    "details": "User confirmed the fix was successful" if user_confirmation else "User rejected the fix"
                }
            
            # Execute automated validation
            validation_results = []
            for criterion in validation_criteria:
                try:
                    # For now, simulate validation checks
                    # In real implementation, this would run actual validation tools
                    passed = await self._check_validation_criterion(
                        criterion, issue_details, fix_result
                    )
                    
                    validation_results.append({
                        "criterion": criterion,
                        "passed": passed,
                        "details": f"Validation {'passed' if passed else 'failed'} for: {criterion}"
                    })
                    
                except Exception as e:
                    self.logger.error(f"Error checking validation criterion '{criterion}': {str(e)}")
                    validation_results.append({
                        "criterion": criterion,
                        "passed": False,
                        "error": str(e)
                    })
            
            # Determine overall validation success
            passed_count = sum(1 for r in validation_results if r['passed'])
            total_criteria = len(validation_results)
            pass_rate = passed_count / total_criteria if total_criteria > 0 else 0
            
            success = pass_rate > 0.7  # 70% of criteria must pass
            
            return {
                "success": success,
                "confidence": pass_rate,
                "method": "automated_validation",
                "validation_results": validation_results,
                "details": f"Validation passed for {passed_count}/{total_criteria} criteria"
            }
            
        except Exception as e:
            self.logger.error(f"Fix validation failed: {str(e)}")
            return {
                "success": False,
                "confidence": 0.0,
                "method": "validation_error",
                "error": str(e)
            }
    
    # Placeholder methods for tool management and information collection
    # These will be implemented in the next phase
    
    async def _get_validation_tools(self, issue_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get validation tools for the issue category."""
        # Placeholder: return validation tools from tool registry
        return []
    
    async def _get_fix_tools(self, issue_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get fix tools for the issue category."""
        # Placeholder: return fix tools from tool registry
        return []
    
    async def _collect_validation_tool_inputs(
        self, tool: Dict[str, Any], issue_details: Dict[str, Any], user_input: str
    ) -> Dict[str, Any]:
        """Collect inputs needed for validation tool execution."""
        # Placeholder: implement parameter collection logic
        return {"user_input": user_input}
    
    async def _identify_required_tool_parameters(
        self, tool: Dict[str, Any], issue_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Identify parameters required for tool execution."""
        # Placeholder: implement parameter identification logic
        return {}
    
    async def _extract_available_parameters(
        self, required_params: Dict[str, Any], issue_details: Dict[str, Any], user_input: str
    ) -> Dict[str, Any]:
        """Extract parameters available from context and user input."""
        # Placeholder: implement parameter extraction logic
        return {}
    
    async def _collect_parameters_from_user(
        self, missing_params: Dict[str, Any], session_state: SessionState
    ) -> Dict[str, Any]:
        """Collect missing parameters from the user."""
        # Placeholder: implement user interaction logic
        return {}
    
    async def _prepare_tool_inputs(
        self, tool: Dict[str, Any], collected_inputs: Dict[str, Any], issue_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare tool-specific inputs from collected parameters."""
        # Placeholder: implement input preparation logic
        return collected_inputs
    
    async def _execute_tool(self, tool: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with the provided inputs."""
        # Placeholder: implement actual tool execution logic
        return {
            "success": True,
            "result": f"Tool {tool['name']} executed successfully",
            "execution_time": 1.0
        }
    
    async def _execute_validation_tool(self, tool: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a validation tool."""
        # Placeholder: implement validation tool execution
        return {
            "success": True,
            "result": f"Validation tool {tool['name']} confirmed issue exists"
        }
    
    async def _check_validation_criterion(
        self, criterion: str, issue_details: Dict[str, Any], fix_result: Dict[str, Any]
    ) -> bool:
        """Check a single validation criterion."""
        # Placeholder: implement actual validation logic
        return True  # Assume validation passes for now
    
    async def _get_user_confirmation_for_detailed_issue(
        self, session_state: SessionState, issue_title: str, detail_result: Dict[str, Any]
    ) -> bool:
        """Get user confirmation for detailed issue resolution."""
        # Placeholder: implement user interaction logic
        # Simulate 85% confirmation rate for successful resolutions
        import random
        return detail_result['success'] and random.random() > 0.15
    
    async def _ask_if_general_issue_resolved(
        self, session_state: SessionState, general_title: str, resolved_count: int, remaining_count: int
    ) -> bool:
        """Ask user if the general issue is fully resolved."""
        # Placeholder: implement user interaction logic
        if remaining_count == 0:
            return True  # All issues resolved
        
        # If more than 70% resolved, likely user confirms
        resolution_rate = resolved_count / (resolved_count + remaining_count)
        return resolution_rate > 0.7
    
    async def _get_user_fix_confirmation(
        self, session_state: SessionState, issue_details: Dict[str, Any], fix_result: Dict[str, Any]
    ) -> bool:
        """Get user confirmation that the fix was successful."""
        # Placeholder: implement user interaction logic
        # Simulate 80% confirmation rate for successful fix attempts
        import random
        return fix_result['success'] and random.random() > 0.2
    
    async def _track_processing_results(
        self, session_state: SessionState, result: Dict[str, Any]
    ) -> None:
        """Track processing results for analytics and learning."""
        try:
            # Store in session state for future reference
            if 'fix_history' not in session_state.__dict__:
                session_state.fix_history = []
            
            session_state.fix_history.append({
                "timestamp": datetime.now().isoformat(),
                "result": result
            })
            
            self.logger.info(f"Fix processing completed: {result}")
            
        except Exception as e:
            self.logger.error(f"Failed to track processing results: {str(e)}")
    
    async def validate_input(self, session_state: SessionState, **kwargs) -> bool:
        """Validate input for fix agent."""
        return kwargs.get('issue_id') is not None
    
    async def handle_error(self, error: Exception, session_state: SessionState) -> Dict[str, Any]:
        """Handle fix agent errors with fallback behavior."""
        self.logger.error(f"Fix agent error: {str(error)}")
        
        return {
            "success": False,
            "error": str(error),
            "error_type": "fix_agent_error",
            "processing_time": datetime.now().isoformat(),
            "fallback_message": "I encountered an error while trying to fix your issue. Would you like me to try a different approach?"
        }


# Global fix agent instance
fix_agent = FixAgent()


async def get_fix_agent() -> FixAgent:
    """Get the global fix agent instance."""
    return fix_agent