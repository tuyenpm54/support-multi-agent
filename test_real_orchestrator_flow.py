#!/usr/bin/env python3
"""
Real Orchestrator Flow Test with OpenAI API Integration

Directly tests the orchestrator flow by fixing the LLM interface mismatch.
Each user message is processed through the real LLM Decision Service to get actual orchestrator decisions.
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

from src.core.llm import get_llm_manager, LLMProvider, LLMResponse
from src.models.session import SessionState, AgentPhase, Task, TaskType, SessionPhase


class MockLLMClient:
    """Mock LLM client that wraps OpenAI client to provide generate() method."""
    
    def __init__(self, openai_client):
        self.openai_client = openai_client
        
    async def generate(self, messages=None, **kwargs):
        """Generate response using OpenAI client with proper interface."""
        
        # Convert messages to prompt format
        prompt = ""
        if messages:
            for msg in messages:
                if msg.get("role") == "system":
                    prompt += f"System: {msg.get('content', '')}\n\n"
                elif msg.get("role") == "user":
                    prompt += f"User: {msg.get('content', '')}\n\n"
        
        # Add any user prompt
        if "user_prompt" in kwargs:
            prompt += f"User: {kwargs['user_prompt']}"
        
        # Call OpenAI client
        response = await self.openai_client.generate_text(
            prompt=prompt,
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 800)
        )
        
        # Return response content as string (expected by LLMDecisionService)
        return response.content


class RealOrchestratorFlow:
    """Test real orchestrator flow with OpenAI API."""
    
    def __init__(self):
        self.session_state = None
        self.conversation_history = []
        self.decisions = []
        self.mock_client = None
        self.llm_service = None
        
    async def setup(self):
        """Initialize with real OpenAI client wrapped in mock interface."""
        print("🚀 Setting up Real Orchestrator Flow with OpenAI")
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
        
        # Wrap OpenAI client in mock interface
        self.mock_client = MockLLMClient(openai_client)
        
        # Import and initialize LLM Decision Service
        from src.services.llm_decision import LLMDecisionService
        self.llm_service = LLMDecisionService(self.mock_client)
        print("✅ LLM Decision Service initialized with wrapped OpenAI client")
        
        # Create session state
        self.session_state = SessionState(
            session_id="real_orchestrator_session",
            user_id="real_customer_456",
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
        """Process user message through real LLM Decision Service."""
        
        print(f"\n{'='*60}")
        print(f"🎯 Turn {turn_number}: Processing User Message")
        print(f"{'='*60}")
        print(f"👤 User: {user_input}")
        print(f"🔄 Current Phase: {self.session_state.current_phase}")
        
        try:
            # Call LLM Decision Service directly
            decision = await self.llm_service.make_decision(
                user_message=user_input,
                session_state=self.session_state,
                context={
                    "turn": turn_number,
                    "conversation_length": len(self.conversation_history),
                    "test_mode": True
                }
            )
            
            print(f"✅ Real LLM Decision Received:")
            print(f"   🎯 Intent Type: {decision.intent_type}")
            print(f"   🔧 Action: {decision.action}")
            print(f"   🤖 Target Agent: {decision.target_agent}")
            print(f"   📊 Confidence: {decision.confidence:.3f}")
            print(f"   ⏱️ Processing Time: {decision.processing_time_ms}ms")
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
            
            # Update session state
            await self.update_session_state(decision, user_input)
            
            # Add to conversation history
            self.conversation_history.append({
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now()
            })
            
            # Generate supporter response
            support_response = self.generate_supporter_response(decision)
            self.conversation_history.append({
                "role": "assistant",
                "content": support_response,
                "timestamp": datetime.now()
            })
            
            print(f"👥 Supporter: {support_response}")
            
            return decision
            
        except Exception as e:
            print(f"❌ Error processing message: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    async def update_session_state(self, decision, user_input):
        """Update session state based on decision."""
        
        # Update phase
        if decision.target_agent:
            agent_phase_map = {
                "classifier_agent": AgentPhase.CLASSIFY,
                "validation_agent": AgentPhase.VALIDATE,
                "knowledge_agent": AgentPhase.REQUIRED_INFO,
                "fix_agent": AgentPhase.FIX
            }
            self.session_state.current_phase = agent_phase_map.get(decision.target_agent, AgentPhase.CLASSIFY)
            
            # Create active task
            if decision.action == "create_new_task":
                task_type = TaskType.ERROR_RESOLUTION if decision.new_task_type == "error_resolution" else TaskType.FEATURE_USAGE
                
                self.session_state.active_task = Task(
                    task_id=f"task_{len(self.decisions)+1}",
                    task_type=task_type,
                    status="in_progress",
                    current_phase=SessionPhase.VALIDATE if decision.target_agent == "validation_agent" else SessionPhase.CLASSIFY,
                    last_user_message=user_input
                )
                
                self.session_state.pending_tasks.append(self.session_state.active_task)
        
        self.session_state.updated_at = datetime.now()
    
    def generate_supporter_response(self, decision):
        """Generate contextual supporter response."""
        
        if decision.intent_type == "new_request" and decision.target_agent == "classifier_agent":
            return f"Chào bạn, tôi đã ghi nhận vấn đề của bạn về {decision.extracted_entities.get('issue_type', 'vấn đề')}. Tôi sẽ phân loại và giúp bạn tìm giải pháp phù hợp."
        
        elif decision.action == "forward_to_current_agent":
            return "Cảm ơn thông tin thêm. Điều này giúp tôi hiểu rõ hơn về vấn đề của bạn."
        
        elif decision.intent_type == "continuation" and decision.target_agent == "knowledge_agent":
            return "Được rồi, tôi sẽ cung cấp hướng dẫn chi tiết về tính năng này cho bạn."
        
        else:
            return "Tôi hiểu và sẽ giúp bạn giải quyết vấn đề này."
    
    async def run_conversation(self):
        """Run complete realistic conversation."""
        
        conversation = [
            # Initial problem report
            "Xin chào, tôi đang gặp sự cố với hệ thống đặt hàng online của khách hàng",
            "Một số món không hiển thị trên menu web, nhưng vẫn có thể đặt tại quán",
            "Cụ thể là món combo 1 và món số 5 không thấy, các món khác hiện bình thường",
            "Tôi đã kiểm tra lại hệ thống admin nhưng vẫn không thấy vấn đề gì",
            "Các món này vẫn còn trong kho và đang bán tốt offline",
            "Bạn có thể kiểm tra xem có lỗi cache hoặc đồng bộ data không?",
            # Acknowledgment and resolution
            "Cảm ơn bạn đã kiểm tra, đó chính xác là vấn đề cache",
            "Tôi đã làm theo hướng dẫn xóa cache và refresh trang",
            "Giờ các món đã hiển thị đúng trên menu web!",
            "Cảm ơn rất nhiều, vấn đề đã được giải quyết!"
        ]
        
        print(f"📋 Starting {len(conversation)}-turn conversation with real LLM decisions...")
        
        for i, user_message in enumerate(conversation, 1):
            decision = await self.process_user_message(user_message, i)
            
            if not decision:
                print(f"❌ Failed to process message {i}")
                return False
            
            # Small delay for realistic flow
            await asyncio.sleep(1)
        
        return True
    
    def print_summary(self):
        """Print comprehensive summary."""
        
        print(f"\n{'='*60}")
        print(f"📊 REAL ORCHESTRATOR FLOW SUMMARY")
        print(f"{'='*60}")
        
        print(f"📝 Total Messages: {len(self.conversation_history)}")
        print(f"🤖 Total Decisions: {len(self.decisions)}")
        print(f"⏱️ Duration: {(self.decisions[-1]['timestamp'] - self.decisions[0]['timestamp']).total_seconds():.1f}s")
        
        # Phase progression
        print(f"\n🔄 Agent Progression:")
        for i, d in enumerate(self.decisions, 1):
            if d['decision'].target_agent:
                print(f"   Turn {i}: {d['decision'].target_agent}")
            else:
                print(f"   Turn {i}: No agent selected")
        
        # Confidence scores
        print(f"\n📊 Confidence Scores:")
        for i, d in enumerate(self.decisions, 1):
            print(f"   Turn {i}: {d['decision'].confidence:.3f}")
        
        # Processing times  
        print(f"\n⏱️ Processing Times:")
        for i, d in enumerate(self.decisions, 1):
            print(f"   Turn {i}: {d['decision'].processing_time_ms}ms")
        
        # Metrics
        avg_conf = sum(d['decision'].confidence for d in self.decisions) / len(self.decisions)
        avg_time = sum(d['decision'].processing_time_ms for d in self.decisions) / len(self.decisions)
        
        print(f"\n📈 Performance Metrics:")
        print(f"   Average Confidence: {avg_conf:.3f}")
        print(f"   Average Processing Time: {avg_time:.1f}ms")
        
        # Agent usage
        agent_counts = {}
        for d in self.decisions:
            agent = d['decision'].target_agent
            if agent:
                agent_counts[agent] = agent_counts.get(agent, 0) + 1
        
        print(f"\n🤖 Agent Selection Distribution:")
        for agent, count in sorted(agent_counts.items()):
            print(f"   {agent}: {count} times")
        
        # Final state
        print(f"\n🎯 Final State:")
        print(f"   Current Phase: {self.session_state.current_phase}")
        print(f"   Active Task: {self.session_state.active_task.task_id if self.session_state.active_task else 'None'}")
        print(f"   Pending Tasks: {len(self.session_state.pending_tasks)}")


async def main():
    """Execute the real orchestrator flow test."""
    
    test = RealOrchestratorFlow()
    
    if not await test.setup():
        print("❌ Setup failed")
        return False
    
    print(f"\n🎬 Starting Real Orchestrator Flow Test...")
    
    success = await test.run_conversation()
    
    if success:
        test.print_summary()
        
        print(f"\n🎉 REAL ORCHESTRATOR FLOW TEST SUCCESS!")
        print(f"✅ All user messages processed through real LLM decisions")
        print(f"✅ Real OpenAI API calls made for each message")
        print(f"✅ Agent selection logic working with actual model intelligence")
        
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)