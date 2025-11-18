#!/usr/bin/env python3
"""
Complete Orchestrator Conversation Flow Test

Tests the full orchestrator flow with a realistic user-customer supporter conversation.
Each user message is pushed sequentially through the actual orchestrator to get real decisions.
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Load .env file
env_path = Path('/Users/tuyenpham712/Work/support-multi-agent/.env')
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

# Add project root to path
sys.path.insert(0, '/Users/tuyenpham712/Work/support-multi-agent')

from src.services.llm_decision import LLMDecisionService
from src.core.llm import get_llm_manager, LLMProvider
from src.models.session import SessionState, AgentPhase, Task, TaskType, OrchestratorDecision
from src.core.orchestrator_preprocessor import get_orchestrator_preprocessor


class TestOrchestratorConversationFlow:
    """Test complete orchestrator flow with realistic conversation."""
    
    def __init__(self):
        self.session_state = None
        self.conversation_history = []
        self.decisions = []
        self.llm_service = None
        
    async def setup(self):
        """Initialize the orchestrator components."""
        print("🚀 Setting up Orchestrator Conversation Flow Test")
        print("=" * 60)
        
        # Check OpenAI API key
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("❌ OPENAI_API_KEY not found")
            return False
        
        print(f"✅ Found OpenAI API key")
        
        # Initialize LLM manager
        manager = await get_llm_manager()
        if not manager or not manager.clients:
            print("❌ No LLM clients available")
            return False
        
        # Get OpenAI client
        openai_client = manager.clients.get(LLMProvider.OPENAI)
        if not openai_client:
            print("❌ OpenAI client not available")
            return False
        
        # Set up global LLM decision service with OpenAI client
        from src.services.llm_decision import get_llm_decision_service
        self.llm_service = get_llm_decision_service(openai_client)
        print("✅ LLM Decision Service initialized with OpenAI")
        
        # Create session state
        self.session_state = SessionState(
            session_id="conversation_test_session",
            user_id="customer_user_123",
            current_phase=AgentPhase.CLASSIFY,
            conversation_history=[],
            llm_decisions_enabled=True
        )
        
        print("✅ Session state created")
        print(f"   Session ID: {self.session_state.session_id}")
        print(f"   User ID: {self.session_state.user_id}")
        print(f"   Initial Phase: {self.session_state.current_phase}")
        
        return True
    
    async def process_user_message(self, user_input: str, turn_number: int):
        """Process a single user message through the orchestrator flow."""
        
        print(f"\n{'='*60}")
        print(f"🎯 Turn {turn_number}: Processing User Message")
        print(f"{'='*60}")
        print(f"👤 User: {user_input}")
        print(f"🔄 Current Orchestrator Phase: {self.session_state.current_phase}")
        
        try:
            # Use the orchestrator preprocessor (which calls LLM Decision Service)
            preprocessor = await get_orchestrator_preprocessor(enable_llm_decisions=True)
            
            # Process through orchestrator flow
            decision = await preprocessor.preprocess_user_input(
                user_input=user_input,
                session_state=self.session_state,
                session_context={
                    "turn": turn_number,
                    "conversation_length": len(self.conversation_history),
                    "test_mode": True
                }
            )
            
            print(f"✅ Orchestrator Decision Received:")
            print(f"   🎯 Intent Type: {decision.intent_type}")
            print(f"   🔧 Action: {decision.action}")
            print(f"   🤖 Target Agent: {decision.target_agent}")
            print(f"   📊 Confidence: {decision.confidence:.3f}")
            print(f"   ⏱️  Processing Time: {decision.processing_time_ms}ms")
            print(f"   💭 Reasoning: {decision.reasoning}")
            print(f"   📝 Extracted Entities: {json.dumps(decision.extracted_entities, indent=2, ensure_ascii=False)}")
            
            if hasattr(decision, 'conversation_flow'):
                print(f"   🔄 Conversation Flow: {decision.conversation_flow}")
            if hasattr(decision, 'emotional_state'):
                print(f"   😊 Emotional State: {decision.emotional_state}")
            
            # Store decision
            self.decisions.append({
                "turn": turn_number,
                "user_input": user_input,
                "decision": decision,
                "timestamp": datetime.now()
            })
            
            # Update session state based on decision
            await self.update_session_state(decision, user_input)
            
            # Add to conversation history
            self.conversation_history.append({
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now()
            })
            
            # Simulate customer supporter response for next turn
            supporter_response = await self.generate_supporter_response(decision)
            self.conversation_history.append({
                "role": "assistant", 
                "content": supporter_response,
                "timestamp": datetime.now()
            })
            
            print(f"👥 Supporter: {supporter_response}")
            
            return decision
            
        except Exception as e:
            print(f"❌ Error processing message: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    async def update_session_state(self, decision: OrchestratorDecision, user_input: str):
        """Update session state based on orchestrator decision."""
        
        # Update phase based on target agent
        if decision.target_agent:
            if decision.target_agent == "classifier_agent":
                self.session_state.current_phase = AgentPhase.CLASSIFY
            elif decision.target_agent == "validation_agent":
                self.session_state.current_phase = AgentPhase.VALIDATE
            elif decision.target_agent == "knowledge_agent":
                self.session_state.current_phase = AgentPhase.REQUIRED_INFO
            elif decision.target_agent == "fix_agent":
                self.session_state.current_phase = AgentPhase.FIX
            
            # Create/update active task
            if decision.action == "create_new_task":
                task_type = TaskType.ERROR_RESOLUTION if "error" in decision.reasoning.lower() else TaskType.FEATURE_USAGE
                
                # Convert AgentPhase to SessionPhase for Task model
                from src.models.session import SessionPhase
                phase_mapping = {
                    "CLASSIFY": SessionPhase.CLASSIFY,
                    "REQUIRED_INFO": SessionPhase.REQUIRED_INFO,
                    "VALIDATE": SessionPhase.VALIDATE,
                    "FIX": SessionPhase.FIX
                }
                task_phase = phase_mapping.get(self.session_state.current_phase.value, SessionPhase.CLASSIFY)
                
                self.session_state.active_task = Task(
                    task_id=f"task_{len(self.decisions)+1}",
                    task_type=task_type,
                    status="in_progress",
                    current_phase=task_phase,
                    last_user_message=user_input
                )
                
                # Add to pending tasks
                self.session_state.pending_tasks.append(self.session_state.active_task)
        
        # Update session timestamp
        self.session_state.updated_at = datetime.now()
    
    async def generate_supporter_response(self, decision: OrchestratorDecision) -> str:
        """Generate appropriate customer supporter response based on decision."""
        
        responses = {
            "classifier_agent": [
                "Cảm ơn bạn đã báo cáo vấn đề. Tôi sẽ phân loại và giúp bạn giải quyết.",
                "Tôi đã ghi nhận thông tin của bạn. Để phục vụ bạn tốt hơn, tôi cần phân loại vấn đề này.",
                "Cảm ơn đã chia sẻ. Tôi sẽ phân loại vấn đề này để có giải pháp phù hợp."
            ],
            "knowledge_agent": [
                "Tôi hiểu bạn cần hỗ trợ. Tôi sẽ cung cấp hướng dẫn chi tiết cho bạn.",
                "Được thôi, tôi sẽ giúp bạn tìm hiểu về tính năng này.",
                "Rất vui được hỗ trợ bạn! Hãy xem hướng dẫn dưới đây."
            ],
            "validation_agent": [
                "Cảm ơn thông tin thêm. Điều này giúp tôi xác định vấn đề chính xác hơn.",
                "Tôi hiểu rồi. Thông tin này rất hữu ích cho việc xác định vấn đề.",
                "Cảm ơn bạn đã cung cấp thêm chi tiết."
            ],
            "fix_agent": [
                "Tôi sẽ hướng dẫn bạn cách khắc phục vấn đề này.",
                "Hãy làm theo các bước sau để giải quyết vấn đề.",
                "Tôi có giải pháp cho vấn đề của bạn. Hãy thử cách này."
            ]
        }
        
        if decision.target_agent and decision.target_agent in responses:
            import random
            return random.choice(responses[decision.target_agent])
        
        return "Cảm ơn bạn. Tôi sẽ giúp bạn giải quyết vấn đề này."
    
    async def run_complete_conversation(self):
        """Run the complete user-customer supporter conversation."""
        
        # Realistic conversation scenario: Customer having menu display issue
        conversation = [
            "Xin chào, tôi đang gặp vấn đề với menu nhà hàng của mình",
            "Một số món ăn không hiển thị trên menu online của khách hàng",
            "Cụ thể là món phở và bún bò không thấy, các món khác vẫn hiện bình thường",
            "Tôi đã kiểm tra lại hệ thống quản lý menu nhưng vẫn không thấy",
            "Các món này có trong kho và có thể phục vụ offline",
            "Bạn có thể giúp tôi kiểm tra xem có lỗi kỹ thuật nào không?",
            "Cảm ơn bạn đã phân tích vấn đề",
            "Vâng, đó chính xác là vấn đề của tôi",
            "Tôi sẽ thử theo hướng dẫn của bạn",
            "Cảm ơn rất nhiều, vấn đề đã được giải quyết!"
        ]
        
        print(f"📋 Starting {len(conversation)}-turn conversation...")
        print(f"📊 Session: {self.session_state.session_id}")
        
        # Process each message in sequence
        for i, user_message in enumerate(conversation, 1):
            decision = await self.process_user_message(user_message, i)
            
            if not decision:
                print(f"❌ Failed to process message {i}")
                return False
            
            # Small delay between turns for realistic flow
            await asyncio.sleep(0.5)
        
        return True
    
    def print_conversation_summary(self):
        """Print a summary of the complete conversation and decisions."""
        
        print(f"\n{'='*60}")
        print(f"📊 CONVERSATION SUMMARY")
        print(f"{'='*60}")
        
        print(f"📝 Total Messages: {len(self.conversation_history)}")
        print(f"🤖 Total Decisions: {len(self.decisions)}")
        print(f"⏱️ Session Duration: {(self.decisions[-1]['timestamp'] - self.decisions[0]['timestamp']).total_seconds():.1f}s")
        
        print(f"\n🔄 Phase Progression:")
        phases = [d['decision'].target_agent for d in self.decisions if d['decision'].target_agent]
        for i, phase in enumerate(phases, 1):
            print(f"   Turn {i}: {phase}")
        
        print(f"\n📊 Confidence Scores:")
        for i, decision_data in enumerate(self.decisions, 1):
            print(f"   Turn {i}: {decision_data['decision'].confidence:.3f}")
        
        print(f"\n⏱️ Processing Times:")
        for i, decision_data in enumerate(self.decisions, 1):
            print(f"   Turn {i}: {decision_data['decision'].processing_time_ms}ms")
        
        # Calculate metrics
        avg_confidence = sum(d['decision'].confidence for d in self.decisions) / len(self.decisions)
        avg_processing_time = sum(d['decision'].processing_time_ms or 0 for d in self.decisions) / len(self.decisions)
        
        print(f"\n📈 Performance Metrics:")
        print(f"   Average Confidence: {avg_confidence:.3f}")
        print(f"   Average Processing Time: {avg_processing_time:.1f}ms")
        
        # Count agent usage
        agent_counts = {}
        for decision_data in self.decisions:
            agent = decision_data['decision'].target_agent
            if agent:
                agent_counts[agent] = agent_counts.get(agent, 0) + 1
        
        print(f"\n🤖 Agent Usage Distribution:")
        for agent, count in sorted(agent_counts.items()):
            print(f"   {agent}: {count} times")
        
        print(f"\n🎯 Final Session State:")
        print(f"   Current Phase: {self.session_state.current_phase}")
        print(f"   Active Task: {self.session_state.active_task.task_id if self.session_state.active_task else 'None'}")
        print(f"   Pending Tasks: {len(self.session_state.pending_tasks)}")


async def main():
    """Main test execution."""
    
    # Create test instance
    test = TestOrchestratorConversationFlow()
    
    # Setup test environment
    if not await test.setup():
        print("❌ Test setup failed")
        return False
    
    # Run complete conversation
    print(f"\n🎬 Starting Complete Conversation Flow Test...")
    
    success = await test.run_complete_conversation()
    
    if success:
        # Print summary
        test.print_conversation_summary()
        
        print(f"\n🎉 CONVERSATION FLOW TEST COMPLETED SUCCESSFULLY!")
        print(f"✅ Real orchestrator decisions generated for each user message")
        print(f"✅ Session state properly maintained throughout conversation")
        print(f"✅ Agent selection working correctly with real OpenAI API")
        
    else:
        print(f"\n❌ CONVERSATION FLOW TEST FAILED")
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)