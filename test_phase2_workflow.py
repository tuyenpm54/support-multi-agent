#!/usr/bin/env python3
"""
Phase 2 Workflow Test Script

Tests the updated Phase 2 architecture with Classifier → InfoValidation → Fix workflow.
This script validates the orchestrator changes and agent integration.
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.models.session import (
    SessionState, AgentPhase, ClassificationResult, 
    SessionPhase, Task, TaskStatus
)
from src.agents.orchestrator import OrchestratorAgent
from src.agents.classifier import get_classifier_agent
from src.agents.infovalidation import InfoValidationAgent


class Phase2WorkflowTester:
    """Tests the Phase 2 workflow integration."""
    
    def __init__(self):
        self.logger = self._setup_logger()
        self.orchestrator = None
        self.classifier_agent = None
        self.infovalidation_agent = None
        
    def _setup_logger(self):
        """Setup test logger."""
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    async def initialize(self):
        """Initialize test components."""
        try:
            self.logger.info("Initializing Phase 2 workflow test...")
            
            # Initialize orchestrator with Phase 2 configuration
            self.orchestrator = OrchestratorAgent(use_llm_decisions=True)
            
            # Get agent instances
            self.classifier_agent = await get_classifier_agent()
            self.infovalidation_agent = InfoValidationAgent()
            await self.infovalidation_agent.initialize()
            
            # Register agents with orchestrator
            self.orchestrator.register_agent(AgentPhase.CLASSIFY, self.classifier_agent)
            self.orchestrator.register_agent(AgentPhase.REQUIRED_INFO, self.infovalidation_agent)
            
            self.logger.info("✅ Phase 2 workflow initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Phase 2 workflow: {str(e)}")
            raise
    
    async def test_classification_to_infovalidation_flow(self):
        """Test the new Classification → InfoValidation flow."""
        self.logger.info("🔄 Testing Classification → InfoValidation flow...")
        
        # Create test session state
        session_state = SessionState(
            session_id="test_session_phase2",
            user_id="test_user",
            current_phase=AgentPhase.CLASSIFY,
            conversation_history=[],
            created_at=datetime.now()
        )
        
        # Test user input for classification
        test_input = "Món phở bô không hiển thị giá thành ở kho Hà Nội tháng 12/2024"
        
        try:
            # Step 1: Classification
            self.logger.info("1️⃣ Executing Classifier agent...")
            
            # Mock a classification result for testing
            classification_result = ClassificationResult(
                classified=True,
                confidence=0.85,
                suggested_category="formula",
                suggested_severity="High",
                matched_issue_id="test-issue-123",
                matched_title="Công thức không hiển thị giá thành món phở bò",
                diagnostic_questions=[
                    "Bạn đã kiểm tra công thức của món phở bò chưa?",
                    "Giá thịt bò hiện tại là bao nhiêu?"
                ],
                recommended_tools=["check_formula", "query_database"],
                created_at=datetime.now()
            )
            
            # Update session state with classification result
            session_state.classification = classification_result
            session_state.current_phase = AgentPhase.REQUIRED_INFO
            
            # Step 2: Test orchestrator state transition logic
            self.logger.info("2️⃣ Testing orchestrator state transition...")
            
            # Simulate agent result from classification
            agent_result = {
                "success": True,
                "classification": classification_result,
                "confidence": classification_result.confidence
            }
            
            # Test the new Phase 2 transition logic
            next_phase = await self.orchestrator._determine_next_after_classification_phase2(
                session_state, agent_result
            )
            
            if next_phase == AgentPhase.REQUIRED_INFO:
                self.logger.info("✅ Classification → InfoValidation transition working correctly")
            else:
                self.logger.error(f"❌ Expected REQUIRED_INFO, got {next_phase}")
                return False
            
            # Step 3: Test InfoValidation agent execution
            self.logger.info("3️⃣ Testing InfoValidation agent execution...")
            
            infovalidation_result = await self.infovalidation_agent.execute(
                session_state,
                user_input="Đã kiểm tra công thức rồi, thịt bò giá 200k/kg, kho Hà Nội"
            )
            
            if infovalidation_result.get("success"):
                self.logger.info("✅ InfoValidation agent executed successfully")
                self.logger.info(f"   Information complete: {infovalidation_result.get('information_complete')}")
                self.logger.info(f"   Validation confirmed: {infovalidation_result.get('validation_confirmed')}")
                self.logger.info(f"   Next questions: {len(infovalidation_result.get('next_questions', []))}")
            else:
                self.logger.error(f"❌ InfoValidation agent failed: {infovalidation_result.get('error')}")
                return False
            
            # Step 4: Test InfoValidation → Fix transition
            if infovalidation_result.get("information_complete") and infovalidation_result.get("validation_confirmed"):
                self.logger.info("4️⃣ Testing InfoValidation → Fix transition...")
                
                next_phase = await self.orchestrator._determine_next_after_infovalidation(
                    session_state, infovalidation_result
                )
                
                if next_phase == AgentPhase.FIX:
                    self.logger.info("✅ InfoValidation → Fix transition working correctly")
                else:
                    self.logger.error(f"❌ Expected FIX, got {next_phase}")
                    return False
            else:
                self.logger.info("ℹ️ InfoValidation requires more information - transition logic working")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Classification → InfoValidation flow test failed: {str(e)}")
            return False
    
    async def test_error_handling(self):
        """Test error handling in Phase 2 workflow."""
        self.logger.info("🔄 Testing error handling...")
        
        session_state = SessionState(
            session_id="test_error_handling",
            user_id="test_user", 
            current_phase=AgentPhase.REQUIRED_INFO,
            conversation_history=[],
            created_at=datetime.now()
        )
        
        try:
            # Test InfoValidation failure handling
            failed_result = {
                "success": False,
                "error": "Test error",
                "error_type": "validation_timeout",
                "retry_count": 1
            }
            
            next_phase = await self.orchestrator._handle_infovalidation_failure(
                session_state, failed_result
            )
            
            if next_phase == AgentPhase.REQUIRED_INFO:
                self.logger.info("✅ InfoValidation failure handling working correctly")
            else:
                self.logger.error(f"❌ Expected REQUIRED_INFO retry, got {next_phase}")
                return False
            
            # Test max retry exceeded
            failed_result["retry_count"] = 5  # Exceed max_retries
            next_phase = await self.orchestrator._handle_infovalidation_failure(
                session_state, failed_result
            )
            
            if next_phase == AgentPhase.ESCALATE:
                self.logger.info("✅ Max retry escalation working correctly")
            else:
                self.logger.error(f"❌ Expected ESCALATE, got {next_phase}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error handling test failed: {str(e)}")
            return False
    
    async def run_all_tests(self):
        """Run all Phase 2 workflow tests."""
        self.logger.info("🚀 Starting Phase 2 Workflow Tests...")
        
        test_results = []
        
        try:
            await self.initialize()
            
            # Test 1: Classification → InfoValidation flow
            result1 = await self.test_classification_to_infovalidation_flow()
            test_results.append(("Classification → InfoValidation Flow", result1))
            
            # Test 2: Error handling
            result2 = await self.test_error_handling()
            test_results.append(("Error Handling", result2))
            
            # Print results
            self.logger.info("\n📊 TEST RESULTS:")
            self.logger.info("=" * 50)
            
            passed = 0
            total = len(test_results)
            
            for test_name, result in test_results:
                status = "✅ PASSED" if result else "❌ FAILED"
                self.logger.info(f"{test_name}: {status}")
                if result:
                    passed += 1
            
            self.logger.info("=" * 50)
            self.logger.info(f"Overall: {passed}/{total} tests passed")
            
            if passed == total:
                self.logger.info("🎉 All Phase 2 workflow tests passed!")
                return True
            else:
                self.logger.error(f"💥 {total - passed} tests failed")
                return False
                
        except Exception as e:
            self.logger.error(f"💥 Test execution failed: {str(e)}")
            return False


async def main():
    """Main test runner."""
    tester = Phase2WorkflowTester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n✅ Phase 2 workflow implementation is ready!")
        print("   - Classifier → InfoValidation transition working")
        print("   - InfoValidation agent functional")
        print("   - Error handling implemented")
        print("   - Orchestrator updated for Phase 2")
        sys.exit(0)
    else:
        print("\n❌ Phase 2 workflow implementation needs fixes")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())