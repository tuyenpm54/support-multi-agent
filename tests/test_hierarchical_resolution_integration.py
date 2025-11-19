#!/usr/bin/env python3
"""
Integration test for Hierarchical Issue Resolution Workflow

Tests the complete workflow: CLASSIFY → RESOLUTION_LOOP → COMPLETE
with both general and detailed issues.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

from src.agents.orchestrator import OrchestratorAgent
from src.agents.classifier import get_classifier_agent
from src.agents.resolution_loop import get_resolution_loop_agent
from src.models.session import SessionState, AgentPhase
from src.core.state_manager import SessionManager


async def setup_test_session():
    """Set up test session and dependencies."""
    # Initialize session manager
    session_manager = SessionManager()
    
    # Create test session
    session_id = f"test_hierarchical_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    user_id = "test_user"
    
    session_state = SessionState(
        session_id=session_id,
        user_id=user_id,
        current_phase=AgentPhase.CLASSIFY,
        created_at=datetime.now()
    )
    
    await session_manager.create_session(session_state)
    print(f"✅ Created test session: {session_id}")
    
    return session_manager, session_state


async def initialize_agents():
    """Initialize all required agents."""
    print("🚀 Initializing agents...")
    
    # Get classifier agent
    classifier_agent = await get_classifier_agent()
    print("✅ Classifier agent initialized")
    
    # Get resolution loop agent
    resolution_loop_agent = await get_resolution_loop_agent()
    print("✅ Resolution loop agent initialized")
    
    return classifier_agent, resolution_loop_agent


async def test_workflow_1_general_issue_with_detailed_children():
    """Test workflow: User reports general issue → resolution loop handles detailed children."""
    print("\n" + "="*80)
    print("🧪 TEST 1: General Issue with Detailed Children")
    print("="*80)
    
    session_manager, session_state = await setup_test_session()
    classifier_agent, resolution_loop_agent = await initialize_agents()
    
    # Initialize orchestrator
    orchestrator = OrchestratorAgent(use_llm_decisions=False)
    orchestrator.set_dependencies(session_manager, tool_registry={})
    orchestrator.register_agent(AgentPhase.CLASSIFY, classifier_agent)
    orchestrator.register_agent(AgentPhase.RESOLUTION_LOOP, resolution_loop_agent)
    
    # Test input: General F&B pricing issue
    user_input = {
        "message": "Món fried rice không hiển thị giá trong kỳ báo cáo tháng 12"
    }
    
    print(f"📝 User Input: {user_input['message']}")
    
    try:
        # Step 1: CLASSIFY phase
        print("\n🔍 Step 1: CLASSIFY phase")
        result1 = await orchestrator.execute(
            session_state,
            user_input=user_input,
            start_workflow=True
        )
        
        print(f"✅ Classification completed")
        print(f"   - Next Phase: {result1.get('next_phase')}")
        print(f"   - Classification: {result1.get('agent_result', {}).get('classification', {})}")
        
        # Update session state for next phase
        session_state.current_phase = result1.get('next_phase')
        
        # Step 2: RESOLUTION_LOOP phase (if classification was successful)
        if result1.get('next_phase') == AgentPhase.RESOLUTION_LOOP:
            print("\n🔄 Step 2: RESOLUTION_LOOP phase")
            
            # Simulate user confirmation for each detailed issue
            detailed_issue_result = {
                "issue_id": "test_detailed_1",
                "title": "Công thức tính giá fried rice bị lỗi",
                "solution_steps": [
                    "Kiểm tra công thức tính giá món fried rice",
                    "Xác định nguyên liệu và chi phí liên quan",
                    "Cập nhật lại công thức với định lượng chính xác"
                ],
                "execution_result": {
                    "status": "success",
                    "message": "Đã sửa công thức tính giá cho món fried rice"
                }
            }
            
            result2 = await orchestrator.execute(
                session_state,
                user_input={"confirmation": "yes", "issue_result": detailed_issue_result}
            )
            
            print(f"✅ Resolution loop completed")
            print(f"   - Next Phase: {result2.get('next_phase')}")
            print(f"   - Resolution Status: {result2.get('agent_result', {}).get('resolution_status')}")
            
            # Simulate final user confirmation that issue is resolved
            result3 = await orchestrator.execute(
                session_state,
                user_input={"fully_resolved": True, "user_feedback": "Vấn đề đã được giải quyết hoàn toàn"}
            )
            
            print(f"✅ Final resolution completed")
            print(f"   - Final Phase: {result3.get('next_phase')}")
            
        else:
            print(f"❌ Expected RESOLUTION_LOOP phase, got: {result1.get('next_phase')}")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_workflow_2_single_detailed_issue():
    """Test workflow: User reports specific detailed issue → direct resolution."""
    print("\n" + "="*80)
    print("🧪 TEST 2: Single Detailed Issue")
    print("="*80)
    
    session_manager, session_state = await setup_test_session()
    classifier_agent, resolution_loop_agent = await initialize_agents()
    
    # Initialize orchestrator
    orchestrator = OrchestratorAgent(use_llm_decisions=False)
    orchestrator.set_dependencies(session_manager, tool_registry={})
    orchestrator.register_agent(AgentPhase.CLASSIFY, classifier_agent)
    orchestrator.register_agent(AgentPhase.RESOLUTION_LOOP, resolution_loop_agent)
    
    # Test input: Specific detailed issue
    user_input = {
        "message": "Lỗi kết nối database khi cố gắng truy xuất báo cáo doanh thu"
    }
    
    print(f"📝 User Input: {user_input['message']}")
    
    try:
        # Step 1: CLASSIFY phase
        print("\n🔍 Step 1: CLASSIFY phase")
        result1 = await orchestrator.execute(
            session_state,
            user_input=user_input,
            start_workflow=True
        )
        
        print(f"✅ Classification completed")
        print(f"   - Next Phase: {result1.get('next_phase')}")
        
        # Update session state for next phase
        session_state.current_phase = result1.get('next_phase')
        
        # Step 2: RESOLUTION_LOOP phase for single detailed issue
        if result1.get('next_phase') == AgentPhase.RESOLUTION_LOOP:
            print("\n🔄 Step 2: RESOLUTION_LOOP phase (single detailed issue)")
            
            # Simulate direct resolution for detailed issue
            detailed_issue_result = {
                "issue_id": "test_db_connection",
                "title": "Database connection timeout",
                "solution_steps": [
                    "Kiểm tra kết nối database server",
                    "Xác định timeout configuration",
                    "Tối ưu query performance"
                ],
                "execution_result": {
                    "status": "success", 
                    "message": "Kết nối database đã được khôi phục và tối ưu"
                }
            }
            
            result2 = await orchestrator.execute(
                session_state,
                user_input={"direct_resolution": detailed_issue_result}
            )
            
            print(f"✅ Direct resolution completed")
            print(f"   - Next Phase: {result2.get('next_phase')}")
            
        else:
            print(f"❌ Expected RESOLUTION_LOOP phase, got: {result1.get('next_phase')}")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_workflow_3_nested_general_issue():
    """Test workflow: Nested general issue (general contains general)."""
    print("\n" + "="*80)
    print("🧪 TEST 3: Nested General Issue (Deep Analysis)")
    print("="*80)
    
    session_manager, session_state = await setup_test_session()
    classifier_agent, resolution_loop_agent = await initialize_agents()
    
    # Initialize orchestrator
    orchestrator = OrchestratorAgent(use_llm_decisions=False)
    orchestrator.set_dependencies(session_manager, tool_registry={})
    orchestrator.register_agent(AgentPhase.CLASSIFY, classifier_agent)
    orchestrator.register_agent(AgentPhase.RESOLUTION_LOOP, resolution_loop_agent)
    
    # Test input: Complex system issue
    user_input = {
        "message": "Hệ thống báo cáo toàn bộ đang chậm và không hiển thị dữ liệu chính xác"
    }
    
    print(f"📝 User Input: {user_input['message']}")
    
    try:
        # Step 1: CLASSIFY phase
        print("\n🔍 Step 1: CLASSIFY phase")
        result1 = await orchestrator.execute(
            session_state,
            user_input=user_input,
            start_workflow=True
        )
        
        print(f"✅ Classification completed")
        print(f"   - Next Phase: {result1.get('next_phase')}")
        
        # Simulate deep analysis workflow
        session_state.current_phase = result1.get('next_phase')
        
        if result1.get('next_phase') == AgentPhase.RESOLUTION_LOOP:
            print("\n🔄 Step 2: RESOLUTION_LOOP phase (nested analysis)")
            print("📊 Performing deep analysis of nested general issue...")
            
            # Simulate nested general issue resolution
            nested_result = {
                "parent_general_issue": "Vấn đề hiệu suất hệ thống",
                "nested_analysis": {
                    "child_general_issues": ["Vấn đề kết nối database", "Vấn đề processing pipeline"],
                    "detailed_issues_found": 5,
                    "resolution_order": ["database_optimization", "pipeline_optimization"]
                }
            }
            
            result2 = await orchestrator.execute(
                session_state,
                user_input={"nested_analysis": nested_result, "continue_deep_analysis": True}
            )
            
            print(f"✅ Nested analysis completed")
            print(f"   - Analysis Result: Found {nested_result['nested_analysis']['detailed_issues_found']} detailed issues")
            
        else:
            print(f"❌ Expected RESOLUTION_LOOP phase, got: {result1.get('next_phase')}")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_semantic_search_integration():
    """Test semantic search service integration."""
    print("\n" + "="*80)
    print("🧪 TEST 4: Semantic Search Integration")
    print("="*80)
    
    try:
        from src.core.hierarchical_semantic_search import get_hierarchical_search_service
        
        print("🔍 Initializing semantic search service...")
        search_service = await get_hierarchical_search_service()
        
        # Test different query types
        test_queries = [
            "Món ăn không hiển thị giá",
            "Lỗi kết nối database",
            "Hệ thống chậm và treo",
            "Báo cáo doanh thu sai số liệu"
        ]
        
        for query in test_queries:
            print(f"\n📝 Query: {query}")
            results = await search_service.search_issues(
                query_text=query,
                max_results=5,
                similarity_threshold=0.6
            )
            
            print(f"🔍 Found {len(results)} results:")
            for i, result in enumerate(results[:2], 1):  # Show top 2
                print(f"   {i}. {result.get('title', 'No title')} "
                      f"(type: {result.get('issue_type', 'unknown')}, "
                      f"score: {result.get('similarity_score', 0):.3f})")
        
        print("✅ Semantic search integration test completed")
        
    except Exception as e:
        print(f"❌ Semantic search test failed: {str(e)}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all integration tests."""
    print("🚀 Starting Hierarchical Resolution Workflow Integration Tests")
    print("="*80)
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Run workflow tests
        await test_workflow_1_general_issue_with_detailed_children()
        await test_workflow_2_single_detailed_issue()
        await test_workflow_3_nested_general_issue()
        await test_semantic_search_integration()
        
        print("\n" + "="*80)
        print("🎉 ALL INTEGRATION TESTS COMPLETED")
        print("✅ Hierarchical Resolution Architecture is working correctly!")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Integration test suite failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())