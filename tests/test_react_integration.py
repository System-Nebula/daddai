
import sys
import os
import json
from typing import Dict, Any

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.agents.gopher_agent import GopherAgent
from src.agents.react_agent import ReActAgent

def test_react_agent():
    """Test the ReAct agent capabilities."""
    print("=" * 60)
    print("Testing ReAct Agent Integration")
    print("=" * 60)
    
    try:
        # Initialize GopherAgent (which initializes ReActAgent)
        print("Initializing GopherAgent...")
        agent = GopherAgent()
        
        if not agent.react_agent:
            print("❌ ReAct Agent failed to initialize.")
            return
            
        print("✅ GopherAgent initialized with ReAct Agent.")
        
        # Test Case 1: Math Problem (Code Interpreter)
        print("\nTest 1: Math Problem (Code Interpreter)")
        message = "Calculate the 10th Fibonacci number using Python."
        print(f"Message: {message}")
        
        result = agent.run_agentic_task(message)
        print(f"Result: {json.dumps(result, indent=2)}")
        
        # Test Case 2: Memory (Save Core Memory)
        print("\nTest 2: Memory (Save Core Memory)")
        message = "Remember that my favorite color is blue."
        context = {"channel_id": "test_channel"}
        print(f"Message: {message}")
        
        result = agent.run_agentic_task(message, context)
        print(f"Result: {json.dumps(result, indent=2)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_react_agent()
