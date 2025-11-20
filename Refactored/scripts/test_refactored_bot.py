"""
Test script for refactored bot functionality.
Demonstrates how the refactored agents work together.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Refactored.src.api.refactored_agent_server import get_server
from Refactored.logger_config import logger


async def test_bot_functionality():
    """Test refactored bot functionality."""
    print("=" * 60)
    print("Testing Refactored Bot Functionality")
    print("=" * 60)
    
    server = get_server()
    
    try:
        await server.initialize()
        
        # Test 1: Message Routing
        print("\n[Test 1] Message Routing")
        print("-" * 60)
        test_messages = [
            ("What is Python?", {"isMentioned": True, "userId": "user123"}),
            ("Hello, how are you?", {"isMentioned": False, "userId": "user123"}),
            ("Search for machine learning", {"isMentioned": True, "userId": "user123"}),
        ]
        
        for message, context in test_messages:
            routing = await server.route_message(message, context)
            print(f"Message: '{message}'")
            print(f"  Handler: {routing.get('handler')}")
            print(f"  Intent: {routing.get('intent', {}).get('intent')}")
            print(f"  Confidence: {routing.get('routing_confidence', 0):.2f}")
            print()
        
        # Test 2: Agentic Mode Detection
        print("\n[Test 2] Agentic Mode Detection")
        print("-" * 60)
        test_tasks = [
            "Calculate 15 * 23",
            "What is the weather?",
            "Solve for x: 2x + 5 = 15",
            "Generate an image of a cat"
        ]
        
        for task in test_tasks:
            should_use = await server.should_use_agentic_mode(task)
            print(f"Task: '{task}'")
            print(f"  Use Agentic Mode: {should_use}")
            print()
        
        # Test 3: Agentic Task Execution
        print("\n[Test 3] Agentic Task Execution")
        print("-" * 60)
        agentic_task = "Calculate 15 * 23"
        print(f"Task: '{agentic_task}'")
        
        result = await server.run_agentic_task(
            agentic_task,
            {"channel_id": "test_channel", "user_id": "test_user"}
        )
        
        print(f"Status: {result.get('status')}")
        if result.get('status') == 'success':
            print(f"Result: {result.get('result', '')[:100]}")
            print(f"Tool Calls: {len(result.get('tool_calls', []))}")
            print(f"Steps: {len(result.get('steps', []))}")
        else:
            print(f"Error: {result.get('error')}")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] All tests completed!")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"Error during testing: {e}", exc_info=True)
        print(f"\n[ERROR] Error: {e}")
    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(test_bot_functionality())

