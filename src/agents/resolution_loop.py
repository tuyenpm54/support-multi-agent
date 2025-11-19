"""
Resolution Loop Agent - Hierarchical Issue Resolution

This agent implements the while(true) loop logic for hierarchical issue resolution:
- Iterates through detailed issues of a general issue
- Validates and fixes each detailed issue until user confirms resolution
- Supports deep analysis for nested general issues
- Manages user confirmation and feedback loops

Key Responsibilities:
1. Sequential issue resolution with user confirmation
2. Deep analysis of nested hierarchical structures
3. Progress tracking across multiple detailed issues
4. User interaction management
5. Resolution validation and rollback
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from src.agents.base import BaseAgent
from src.models.session import SessionState
from src.core.hierarchical_semantic_search import get_hierarchical_search_service


class ResolutionStatus(Enum):
    """Resolution status for tracking issue attempts."""
    PENDING = "pending"
    ATTEMPTING = "attempting"
    RESOLVED = "resolved"
    FAILED = "failed"
    SKIPPED = "skipped"
    USER_CONFIRMED = "user_confirmed"
    USER_REJECTED = "user_rejected"


class DetailedIssueResult:
    """Result of attempting to resolve a detailed issue."""
    
    def __init__(
        self,
        issue_id: str,
        title: str,
        status: ResolutionStatus,
        success: bool,
        execution_time: float,
        error_details: Optional[str] = None,
        user_feedback: Optional[str] = None,
        solution_applied: Optional[Dict[str, Any]] = None
    ):
        self.issue_id = issue_id
        self.title = title
        self.status = status
        self.success = success
        self.execution_time = execution_time
        self.error_details = error_details
        self.user_feedback = user_feedback
        self.solution_applied = solution_applied
        self.attempted_at = datetime.now()


class ResolutionLoopAgent(BaseAgent):
    """
    Agent for hierarchical issue resolution with user confirmation loops.
    
    Implements the core logic for:
    - Iterating through detailed issues
    - User confirmation after each resolution attempt
    - Deep analysis of nested structures
    - Progress tracking and rollback
    """
    
    def __init__(self):
        super().__init__("ResolutionLoopAgent")
        self.logger = logging.getLogger(__name__)
        self.semantic_search_service = None
        
        # Configuration
        self.max_resolution_attempts = 3
        self.user_confirmation_timeout = 300  # 5 minutes
        self.progress_tracking = True
        
        # Resolution state
        self.resolution_history: List[DetailedIssueResult] = []
        self.current_issue_index = 0
        self.resolved_count = 0
        self.failed_count = 0
    
    async def initialize(self):
        """Initialize the resolution loop agent."""
        try:
            self.semantic_search_service = await get_hierarchical_search_service()
            self.logger.info("Resolution loop agent initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize resolution loop agent: {str(e)}")
            raise
    
    async def execute(self, session_state: SessionState, **kwargs) -> Dict[str, Any]:
        """
        Execute resolution loop for hierarchical issues.
        
        Args:
            session_state: Current session state
            **kwargs: Additional parameters (issue_id, root_issue_id, user_input, etc.)
            
        Returns:
            Resolution result with progress and next actions
        """
        issue_id = kwargs.get('issue_id')
        root_issue_id = kwargs.get('root_issue_id')
        user_input = kwargs.get('user_input', '')
        
        if not issue_id:
            raise ValueError("issue_id is required for resolution loop")
        
        self.logger.info(f"Starting resolution loop for issue: {issue_id}")
        
        try:
            # Step 1: Get issue details and hierarchy
            issue_details = await self._get_issue_details(issue_id)
            
            # Step 2: Determine resolution strategy
            resolution_strategy = await self._determine_resolution_strategy(
                issue_details, session_state
            )
            
            # Step 3: Execute resolution based on issue type
            if issue_details['issue_type'] == 'detailed':
                # Single detailed issue resolution
                result = await self._resolve_single_issue(
                    session_state, issue_details, user_input
                )
            else:
                # General issue - iterate through detailed issues
                result = await self._resolve_general_issue(
                    session_state, issue_details, user_input, root_issue_id
                )
            
            # Step 4: Track resolution results
            await self._track_resolution_results(session_state, result)
            
            return {
                "success": True,
                "issue_id": issue_id,
                "issue_type": issue_details['issue_type'],
                "resolution_strategy": resolution_strategy,
                "result": result,
                "progress": {
                    "total_detailed": result.get('total_detailed_issues', 1),
                    "resolved": result.get('resolved_count', 1 if result.get('success') else 0),
                    "failed": result.get('failed_count', 0),
                    "remaining": result.get('remaining_count', 0)
                },
                "processing_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Resolution loop failed: {str(e)}")
            return await self.handle_error(e, session_state)
    
    async def _get_issue_details(self, issue_id: str) -> Dict[str, Any]:
        """Get detailed information about an issue including hierarchy."""
        try:
            async with self.semantic_search_service._connection_pool.acquire() as conn:
                # Get issue details
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
    
    async def _determine_resolution_strategy(
        self,
        issue_details: Dict[str, Any],
        session_state: SessionState
    ) -> Dict[str, Any]:
        """Determine the best resolution strategy for the issue."""
        if issue_details['issue_type'] == 'detailed':
            return {
                "strategy": "direct",
                "approach": "attempt_resolution",
                "user_confirmation": False,
                "max_attempts": self.max_resolution_attempts
            }
        
        # General issue strategy
        child_count = len(issue_details.get('detailed_issues', []))
        
        strategy = {
            "strategy": "sequential",
            "approach": "iterate_detailed",
            "user_confirmation": True,
            "stop_on_first_success": False,
            "max_attempts": child_count,
            "total_detailed": child_count
        }
        
        # Adjust strategy based on issue complexity
        if child_count > 5:
            strategy["approach"] = "prioritized"  # Prioritize by severity/score
        elif any(child.get('parent_issue_id') for child in issue_details.get('detailed_issues', [])):
            strategy["approach"] = "deep_analysis"  # Handle nested general issues
        
        return strategy
    
    async def _resolve_single_issue(
        self,
        session_state: SessionState,
        issue_details: Dict[str, Any],
        user_input: str
    ) -> Dict[str, Any]:
        """Resolve a single detailed issue."""
        issue_id = issue_details['issue_id']
        issue_title = issue_details['title']
        
        self.logger.info(f"Resolving detailed issue: {issue_title}")
        
        resolution_results = []
        
        for attempt in range(self.max_resolution_attempts):
            self.logger.info(f"Attempt {attempt + 1}/{self.max_resolution_attempts} for issue {issue_title}")
            
            try:
                start_time = datetime.now()
                
                # Execute the solution steps
                solution_result = await self._execute_solution_steps(
                    issue_details, user_input, attempt + 1
                )
                
                execution_time = (datetime.now() - start_time).total_seconds()
                
                # Create resolution result
                result = DetailedIssueResult(
                    issue_id=issue_id,
                    title=issue_title,
                    status=ResolutionStatus.RESOLVED if solution_result['success'] else ResolutionStatus.FAILED,
                    success=solution_result['success'],
                    execution_time=execution_time,
                    user_feedback=solution_result.get('user_feedback'),
                    solution_applied=solution_result.get('steps_applied')
                )
                
                resolution_results.append(result)
                
                if solution_result['success']:
                    self.logger.info(f"Successfully resolved issue {issue_title}")
                    break
                else:
                    self.logger.warning(f"Failed to resolve issue {issue_title} on attempt {attempt + 1}")
                    
            except Exception as e:
                self.logger.error(f"Error in resolution attempt {attempt + 1}: {str(e)}")
                
                result = DetailedIssueResult(
                    issue_id=issue_id,
                    title=issue_title,
                    status=ResolutionStatus.FAILED,
                    success=False,
                    execution_time=0,
                    error_details=str(e)
                )
                
                resolution_results.append(result)
        
        # Determine final result
        final_result = resolution_results[-1] if resolution_results else DetailedIssueResult(
            issue_id=issue_id, title=issue_title, status=ResolutionStatus.FAILED, success=False, execution_time=0
        )
        
        return {
            "success": final_result.success,
            "issue_id": issue_id,
            "issue_title": issue_title,
            "final_status": final_result.status.value,
            "attempts": len(resolution_results),
            "total_time": sum(r.execution_time for r in resolution_results),
            "resolution_history": [
                {
                    "attempt": i + 1,
                    "status": r.status.value,
                    "success": r.success,
                    "execution_time": r.execution_time,
                    "error": r.error_details,
                    "user_feedback": r.user_feedback
                }
                for i, r in enumerate(resolution_results)
            ]
        }
    
    async def _resolve_general_issue(
        self,
        session_state: SessionState,
        issue_details: Dict[str, Any],
        user_input: str,
        root_issue_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Resolve a general issue by iterating through its detailed issues."""
        general_issue_id = issue_details['issue_id']
        general_title = issue_details['title']
        detailed_issues = issue_details.get('detailed_issues', [])
        
        self.logger.info(f"Resolving general issue: {general_title} with {len(detailed_issues)} detailed issues")
        
        resolution_results = []
        resolved_count = 0
        failed_count = 0
        
        for index, detailed_issue in enumerate(detailed_issues):
            self.logger.info(f"Processing detailed issue {index + 1}/{len(detailed_issues)}: {detailed_issue['title']}")
            
            try:
                # Resolve the detailed issue
                detail_result = await self._resolve_single_issue(
                    session_state, detailed_issue, user_input
                )
                
                resolution_results.append({
                    "detailed_issue_id": detailed_issue['issue_id'],
                    "detailed_title": detailed_issue['title'],
                    "result": detail_result
                })
                
                # Get user confirmation
                user_confirmed = await self._get_user_confirmation(
                    session_state, general_title, detail_result
                )
                
                if user_confirmed and detail_result['success']:
                    resolved_count += 1
                    self.logger.info(f"User confirmed resolution for: {detailed_issue['title']}")
                    
                    # Ask if the general issue is fully resolved
                    fully_resolved = await self._ask_if_fully_resolved(session_state, general_title, resolved_count, len(detailed_issues) - index - 1)
                    
                    if fully_resolved:
                        self.logger.info(f"User confirmed general issue {general_title} is fully resolved")
                        break
                    else:
                        self.logger.info(f"User wants to continue with remaining detailed issues")
                        
                else:
                    failed_count += 1
                    self.logger.info(f"User did not confirm resolution or resolution failed for: {detailed_issue['title']}")
                    
            except Exception as e:
                self.logger.error(f"Error processing detailed issue {detailed_issue['title']}: {str(e)}")
                
                resolution_results.append({
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
            "resolution_results": resolution_results
        }
    
    async def _execute_solution_steps(
        self,
        issue_details: Dict[str, Any],
        user_input: str,
        attempt_number: int
    ) -> Dict[str, Any]:
        """Execute the solution steps for an issue."""
        try:
            # Get solution steps from issue
            solution_steps = issue_details.get('solution_steps', [])
            
            if not solution_steps:
                # Generate default solution steps based on category
                solution_steps = await self._generate_default_solution_steps(issue_details)
            
            executed_steps = []
            
            for step_num, step in enumerate(solution_steps):
                self.logger.info(f"Executing step {step_num + 1}/{len(solution_steps)}: {step}")
                
                # Execute the step (this would integrate with the tool management system)
                step_result = await self._execute_step(step, issue_details, user_input, step_num + 1)
                
                executed_steps.append({
                    "step_number": step_num + 1,
                    "description": step,
                    "result": step_result,
                    "success": step_result.get('success', False),
                    "error": step_result.get('error')
                })
                
                # If step fails and it's critical, stop execution
                if not step_result.get('success', False) and step_result.get('critical', False):
                    self.logger.error(f"Critical step failed, stopping execution: {step}")
                    break
            
            # Validate resolution
            validation_result = await self._validate_resolution(issue_details, executed_steps)
            
            return {
                "success": validation_result['success'],
                "steps_applied": executed_steps,
                "validation_result": validation_result,
                "user_feedback": validation_result.get('user_feedback')
            }
            
        except Exception as e:
            self.logger.error(f"Failed to execute solution steps: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "steps_applied": executed_steps if 'executed_steps' in locals() else []
            }
    
    async def _generate_default_solution_steps(self, issue_details: Dict[str, Any]) -> List[str]:
        """Generate default solution steps based on issue category and details."""
        category = issue_details.get('category', 'unknown')
        title = issue_details.get('title', '')
        
        # Category-specific solution steps
        if category == 'formula':
            return [
                "Kiểm tra công thức món ăn trong kho áp dụng",
                "Xác nhận giá nguyên vật liệu đầu vào",
                "Kiểm tra tỷ lệ định lượng trong công thức",
                "Tính lại giá thành và cập nhật hệ thống"
            ]
        elif category == 'Performance':
            return [
                "Kiểm tra hiệu suất hệ thống hiện tại",
                "Xác định các thao tác chậm",
                "Tối ưu hóa truy vấn cơ sở dữ liệu",
                "Kiểm tra tài nguyên hệ thống"
            ]
        elif category == 'Integration':
            return [
                "Kiểm tra kết nối đến hệ thống bên ngoài",
                "Xác thực cấu hình đồng bộ",
                "Thử nghiệm kết nối thử nghiệm",
                "Thực hiện đồng bộ dữ liệu"
            ]
        else:
            # Generic steps
            return [
                "Phân tích vấn đề và nguyên nhân",
                "Tìm kiếm giải pháp trong hệ thống tri thức",
                "Thực hiện sửa đổi cần thiết",
                "Xác minh vấn đề đã được giải quyết"
            ]
    
    async def _execute_step(self, step: str, issue_details: Dict[str, Any], user_input: str, step_number: int) -> Dict[str, Any]:
        """Execute a single solution step."""
        # This would integrate with the tool management system
        # For now, simulate step execution
        
        try:
            self.logger.info(f"Executing step: {step}")
            
            # Simulate step execution time
            await asyncio.sleep(0.1)
            
            # Check if this is a critical step
            critical_keywords = ['xóa', 'delete', 'rollback', 'nhân tạo', 'recreate']
            is_critical = any(keyword in step.lower() for keyword in critical_keywords)
            
            # Simulate 80% success rate
            import random
            success = random.random() > 0.2
            
            return {
                "success": success,
                "step": step,
                "step_number": step_number,
                "execution_time": 0.1,
                "critical": is_critical,
                "details": f"Step {step_number} {'success' if success else 'failed'}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "step": step,
                "error": str(e),
                "critical": False
            }
    
    async def _validate_resolution(
        self,
        issue_details: Dict[str, Any],
        executed_steps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate that the resolution was successful."""
        try:
            # Get validation criteria from issue details
            validation_criteria = issue_details.get('validation_criteria', [])
            
            if not validation_criteria:
                # Default validation
                validation_criteria = ["Issue marked as resolved by system"]
            
            validation_results = []
            all_passed = True
            
            for criterion in validation_criteria:
                try:
                    # Simulate validation check
                    passed = await self._check_validation_criterion(
                        criterion, issue_details, executed_steps
                    )
                    
                    validation_results.append({
                        "criterion": criterion,
                        "passed": passed,
                        "details": f"Validation {'passed' if passed else 'failed'} for: {criterion}"
                    })
                    
                    if not passed:
                        all_passed = False
                        
                except Exception as e:
                    self.logger.error(f"Error checking validation criterion '{criterion}': {str(e)}")
                    validation_results.append({
                        "criterion": criterion,
                        "passed": False,
                        "error": str(e)
                    })
                    all_passed = False
            
            return {
                "success": all_passed,
                "validation_results": validation_results,
                "user_feedback": "Validation completed" if all_passed else "Some validations failed"
            }
            
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _check_validation_criterion(
        self,
        criterion: str,
        issue_details: Dict[str, Any],
        executed_steps: List[Dict[str, Any]]
    ) -> bool:
        """Check a single validation criterion."""
        # This would implement actual validation logic
        # For now, simulate validation
        
        if "giá hiển thị > 0" in criterion.lower():
            return True  # Assume validation passes
        elif "dữ liệu đồng bộ" in criterion.lower():
            return True  # Assume validation passes
        elif "hệ thống hoạt động" in criterion.lower():
            return True  # Assume validation passes
        else:
            return True  # Default to pass for unknown criteria
    
    async def _get_user_confirmation(
        self,
        session_state: SessionState,
        general_title: str,
        detail_result: Dict[str, Any]
    ) -> bool:
        """
        Get user confirmation for a detailed issue resolution.
        
        In a real implementation, this would:
        1. Send the result to the user interface
        2. Wait for user response
        3. Process the confirmation
        """
        # For now, simulate user confirmation based on success rate
        # In production, this would integrate with the chat interface
        
        if detail_result['success']:
            # Simulate 90% user confirmation rate for successful resolutions
            import random
            return random.random() > 0.1
        else:
            # 30% chance user asks to try again even for failed attempts
            return random.random() > 0.7
    
    async def _ask_if_fully_resolved(
        self,
        session_state: SessionState,
        general_title: str,
        resolved_count: int,
        remaining_count: int
    ) -> bool:
        """Ask user if the general issue is fully resolved."""
        # Simulate user decision based on resolution progress
        if remaining_count == 0:
            return True  # All issues resolved, assume user confirms
        
        # If more than 70% resolved, likely user confirms
        resolution_rate = resolved_count / (resolved_count + remaining_count)
        return resolution_rate > 0.7
    
    async def _track_resolution_results(
        self,
        session_state: SessionState,
        result: Dict[str, Any]
    ) -> None:
        """Track resolution results for analytics and learning."""
        try:
            # This would integrate with a learning system
            # For now, just log the results
            self.logger.info(f"Resolution tracking: {result}")
            
            # Store in session state for future reference
            if 'resolution_history' not in session_state.__dict__:
                session_state.resolution_history = []
            
            session_state.resolution_history.append({
                "timestamp": datetime.now().isoformat(),
                "result": result
            })
            
        except Exception as e:
            self.logger.error(f"Failed to track resolution results: {str(e)}")
    
    async def validate_input(self, session_state: SessionState, **kwargs) -> bool:
        """Validate input for resolution loop."""
        return kwargs.get('issue_id') is not None
    
    async def handle_error(self, error: Exception, session_state: SessionState) -> Dict[str, Any]:
        """Handle resolution loop errors with fallback behavior."""
        self.logger.error(f"Resolution loop error: {str(error)}")
        
        return {
            "success": False,
            "error": str(error),
            "error_type": "resolution_loop_error",
            "processing_time": datetime.now().isoformat(),
            "fallback_message": "I encountered an error while trying to resolve your issue. Would you like me to try a different approach?"
        }


# Global resolution loop agent instance
resolution_loop_agent = ResolutionLoopAgent()


async def get_resolution_loop_agent() -> ResolutionLoopAgent:
    """Get the global resolution loop agent instance."""
    return resolution_loop_agent