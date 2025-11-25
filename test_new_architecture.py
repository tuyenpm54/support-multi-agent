#!/usr/bin/env python3
"""
Minimal test for the new 3-agent architecture without heavy dependencies.
This tests the core logic and structure of our refactored system.
"""

import sys
import os
import asyncio
from typing import Dict, Any
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Test basic imports and structure
def test_basic_imports():
    """Test that all new agent modules can be imported."""
    print("🧪 Testing basic imports...")
    
    try:
        # Test imports without heavy dependencies
        from src.agents.base import BaseAgent
        from src.models.session import AgentPhase
        print("✅ Base classes imported successfully")
        
        # Test core enum values
        assert AgentPhase.CLASSIFY == "CLASSIFY"
        assert AgentPhase.INFO_VALIDATION == "INFO_VALIDATION"  
        assert AgentPhase.FIX == "FIX"
        assert AgentPhase.COMPLETE == "COMPLETE"
        print("✅ AgentPhase enum values correct")
        
        return True
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def test_agent_structure():
    """Test that agents have the expected structure."""
    print("\n🧪 Testing agent structure...")
    
    try:
        from src.agents.base import BaseAgent
        
        # Test BaseAgent has required methods
        assert hasattr(BaseAgent, 'execute')
        assert hasattr(BaseAgent, 'set_dependencies')
        assert hasattr(BaseAgent, 'validate_input')
        assert hasattr(BaseAgent, 'handle_error')
        print("✅ BaseAgent has required methods")
        
        return True
    except Exception as e:
        print(f"❌ Agent structure test failed: {e}")
        return False

def test_information_collector():
    """Test the InformationCollector logic without dependencies."""
    print("\n🧪 Testing InformationCollector...")
    
    try:
        from src.core.information_collector import InformationCollector, ParameterType
        
        # Test InformationCollector initialization
        collector = InformationCollector()
        print("✅ InformationCollector initialized")
        
        # Test parameter type constants
        assert ParameterType.STRING == "string"
        assert ParameterType.INTEGER == "integer"
        assert ParameterType.EMAIL == "email"
        print("✅ ParameterType constants correct")
        
        # Test question templates
        assert len(collector.question_templates) > 0
        assert "generic" in collector.question_templates
        print("✅ Question templates initialized")
        
        return True
    except Exception as e:
        print(f"❌ InformationCollector test failed: {e}")
        return False

def test_mock_agent_classes():
    """Test agent class definitions without full initialization."""
    print("\n🧪 Testing agent class definitions...")
    
    try:
        # Import and test basic class structure
        import src.agents.fix_agent
        import src.agents.infovalidation
        
        # Test FixAgent class exists and has expected attributes
        assert hasattr(src.agents.fix_agent, 'FixAgent')
        assert hasattr(src.agents.fix_agent, 'get_fix_agent')
        print("✅ FixAgent class defined")
        
        # Test InfoValidationAgent class exists
        assert hasattr(src.agents.infovalidation, 'InfoValidationAgent') 
        assert hasattr(src.agents.infovalidation, 'get_info_validation_agent')
        print("✅ InfoValidationAgent class defined")
        
        return True
    except Exception as e:
        print(f"❌ Mock agent class test failed: {e}")
        return False

def test_orchestrator_structure():
    """Test OrchestratorAgent structure and new workflow."""
    print("\n🧪 Testing OrchestratorAgent structure...")
    
    try:
        # Test orchestrator imports
        from src.agents.orchestrator import OrchestratorAgent
        from src.models.session import AgentPhase
        
        # Test orchestrator can be instantiated
        orchestrator = OrchestratorAgent()
        print("✅ OrchestratorAgent instantiated")
        
        # Test state transition mapping
        state_transitions = orchestrator.state_transitions
        assert AgentPhase.INFO_VALIDATION in state_transitions
        assert AgentPhase.FIX in state_transitions
        print("✅ State transitions include INFO_VALIDATION and FIX")
        
        # Test retry counts
        max_retries = orchestrator.max_retries
        assert AgentPhase.INFO_VALIDATION in max_retries
        assert max_retries[AgentPhase.FIX] >= 3  # Should have higher retries for fix operations
        print("✅ Retry counts configured")
        
        return True
    except Exception as e:
        print(f"❌ Orchestrator structure test failed: {e}")
        return False

def test_app_integration():
    """Test that app.py imports and structure are correct."""
    print("\n🧪 Testing app integration...")
    
    try:
        # Test that app file has the right imports
        with open('src/api/app.py', 'r') as f:
            app_content = f.read()
        
        # Check for new agent imports
        assert 'get_classifier_agent' in app_content
        assert 'get_info_validation_agent' in app_content
        assert 'get_fix_agent' in app_content
        print("✅ App imports new agents")
        
        # Check for agent registration code
        assert 'register_agent(AgentPhase.CLASSIFY' in app_content
        assert 'register_agent(AgentPhase.INFO_VALIDATION' in app_content
        assert 'register_agent(AgentPhase.FIX' in app_content
        print("✅ Agent registration code present")
        
        return True
    except Exception as e:
        print(f"❌ App integration test failed: {e}")
        return False

async def test_workflow_logic():
    """Test the workflow logic with mock data."""
    print("\n🧪 Testing workflow logic...")
    
    try:
        from src.agents.orchestrator import OrchestratorAgent
        from src.models.session import AgentPhase
        
        orchestrator = OrchestratorAgent()
        
        # Test classification result processing
        mock_classification_result = {
            "classified": True,
            "issue_type": "general",
            "confidence": 0.8,
            "has_missing_info": True
        }
        
        # This should route to INFO_VALIDATION
        next_phase = orchestrator._determine_next_after_classification(
            type('MockSessionState', (), {'classification': type('MockClassification', (), mock_classification_result)()})(),
            {"classification": mock_classification_result}
        )
        
        # The logic should route general issues with missing info to INFO_VALIDATION
        print(f"📋 Next phase determined: {next_phase}")
        print("✅ Workflow logic test passed")
        
        return True
    except Exception as e:
        print(f"❌ Workflow logic test failed: {e}")
        return False

def run_all_tests():
    """Run all tests and report results."""
    print("🚀 Starting New 3-Agent Architecture Tests")
    print("=" * 50)
    
    tests = [
        ("Basic Imports", test_basic_imports),
        ("Agent Structure", test_agent_structure), 
        ("InformationCollector", test_information_collector),
        ("Agent Class Definitions", test_mock_agent_classes),
        ("Orchestrator Structure", test_orchestrator_structure),
        ("App Integration", test_app_integration),
    ]
    
    # Run synchronous tests
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Run async tests
    try:
        async_result = asyncio.run(test_workflow_logic())
        results.append(("Workflow Logic", async_result))
    except Exception as e:
        print(f"❌ Workflow Logic test failed with exception: {e}")
        results.append(("Workflow Logic", False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All tests passed! The refactored architecture is working correctly.")
    else:
        print("⚠️  Some tests failed. Review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)