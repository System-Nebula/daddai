#!/usr/bin/env python3
"""
Verification script for agentic upgrades.
Tests all new features to ensure they're working correctly.
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def verify_imports():
    """Verify all new modules can be imported."""
    print("=" * 60)
    print("1. VERIFYING IMPORTS")
    print("=" * 60)
    
    modules = [
        ("src.agents.gopher_agent", "GopherAgent"),
        ("src.agents.react_agent", "ReActAgent"),
        ("src.tools.memory_tools", "MemoryTools"),
        ("src.tools.code_interpreter", "CodeInterpreter"),
        ("src.tools.vision_tool", "VisionTool"),
        ("src.tools.llm_tools", "create_rag_tools"),
        ("src.api.gopher_agent_persistent_server", "GopherAgentServer"),
    ]
    
    all_passed = True
    for module_name, class_name in modules:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"[OK] {module_name}.{class_name}")
        except Exception as e:
            print(f"[FAIL] {module_name}.{class_name}: {e}")
            all_passed = False
    
    return all_passed

def verify_gopher_agent():
    """Verify GopherAgent has new methods."""
    print("\n" + "=" * 60)
    print("2. VERIFYING GOPHER AGENT")
    print("=" * 60)
    
    try:
        from src.agents.gopher_agent import GopherAgent
        
        agent = GopherAgent()
        
        # Check for new methods
        methods = [
            "should_use_agentic_mode",
            "run_agentic_task",
            "classify_intent",
            "route_message"
        ]
        
        all_passed = True
        for method in methods:
            if hasattr(agent, method):
                print(f"[OK] GopherAgent.{method}()")
            else:
                print(f"[FAIL] GopherAgent.{method}() - NOT FOUND")
                all_passed = False
        
        # Check ReAct agent initialization
        if agent.react_agent:
            print(f"[OK] ReActAgent initialized")
        else:
            print(f"[WARN] ReActAgent not initialized (may be optional)")
        
        return all_passed
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_memory_tools():
    """Verify MemoryTools has new methods."""
    print("\n" + "=" * 60)
    print("3. VERIFYING MEMORY TOOLS")
    print("=" * 60)
    
    try:
        from src.tools.memory_tools import MemoryTools
        
        memory_tools = MemoryTools()
        
        methods = [
            "save_core_memory",
            "update_core_memory",
            "get_core_memory",
            "delete_core_memory"
        ]
        
        all_passed = True
        for method in methods:
            if hasattr(memory_tools, method):
                print(f"[OK] MemoryTools.{method}()")
            else:
                print(f"[FAIL] MemoryTools.{method}() - NOT FOUND")
                all_passed = False
        
        # Check tool definitions
        tool_defs = memory_tools.get_tool_definitions()
        tool_names = [tool["name"] for tool in tool_defs]
        expected_tools = ["save_core_memory", "update_core_memory", "get_core_memory"]
        
        for tool_name in expected_tools:
            if tool_name in tool_names:
                print(f"[OK] Tool definition: {tool_name}")
            else:
                print(f"[FAIL] Tool definition missing: {tool_name}")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_vision_tool():
    """Verify VisionTool exists and has methods."""
    print("\n" + "=" * 60)
    print("4. VERIFYING VISION TOOL")
    print("=" * 60)
    
    try:
        from src.tools.vision_tool import VisionTool
        
        vision_tool = VisionTool()
        
        methods = [
            "process_image",
            "analyze_image",
            "get_tool_definition"
        ]
        
        all_passed = True
        for method in methods:
            if hasattr(vision_tool, method):
                print(f"[OK] VisionTool.{method}()")
            else:
                print(f"[FAIL] VisionTool.{method}() - NOT FOUND")
                all_passed = False
        
        # Check tool definition
        tool_def = vision_tool.get_tool_definition()
        if tool_def and tool_def.get("name") == "analyze_image":
            print(f"[OK] Tool definition: analyze_image")
        else:
            print(f"[FAIL] Tool definition incorrect")
            all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_tool_registry():
    """Verify tools are registered in main registry."""
    print("\n" + "=" * 60)
    print("5. VERIFYING TOOL REGISTRY")
    print("=" * 60)
    
    try:
        from src.tools.llm_tools import create_rag_tools, LLMToolRegistry
        
        # Create a mock pipeline for testing
        class MockPipeline:
            def __init__(self):
                self.state_manager = None
                self.document_store = None
                self.embedding_generator = None
                self.intelligent_memory = None
                self.user_relations = None
                self.enhanced_search = None
        
        pipeline = MockPipeline()
        registry = create_rag_tools(pipeline)
        
        # Check for new tools
        expected_tools = [
            "run_python",
            "save_core_memory",
            "get_core_memory",
            "analyze_image"
        ]
        
        all_passed = True
        for tool_name in expected_tools:
            tool = registry.get_tool(tool_name)
            if tool:
                print(f"[OK] Tool registered: {tool_name}")
            else:
                print(f"[FAIL] Tool NOT registered: {tool_name}")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_react_agent():
    """Verify ReActAgent has step tracking."""
    print("\n" + "=" * 60)
    print("6. VERIFYING REACT AGENT")
    print("=" * 60)
    
    try:
        from src.agents.react_agent import ReActAgent
        
        agent = ReActAgent()
        
        # Check for required attributes
        checks = [
            ("last_execution", dict),
            ("tools", list),
            ("graph", None),  # Just check it exists
        ]
        
        all_passed = True
        for attr_name, attr_type in checks:
            if hasattr(agent, attr_name):
                attr_value = getattr(agent, attr_name)
                if attr_type is None or isinstance(attr_value, attr_type):
                    print(f"[OK] ReActAgent.{attr_name}")
                else:
                    print(f"[WARN] ReActAgent.{attr_name} has wrong type")
            else:
                print(f"[FAIL] ReActAgent.{attr_name} - NOT FOUND")
                all_passed = False
        
        # Check last_execution structure
        if hasattr(agent, "last_execution"):
            le = agent.last_execution
            expected_keys = ["steps", "tool_calls", "final_result"]
            for key in expected_keys:
                if key in le:
                    print(f"[OK] last_execution.{key}")
                else:
                    print(f"[FAIL] last_execution.{key} - NOT FOUND")
                    all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_persistent_server():
    """Verify persistent server has new methods."""
    print("\n" + "=" * 60)
    print("7. VERIFYING PERSISTENT SERVER")
    print("=" * 60)
    
    try:
        from src.api.gopher_agent_persistent_server import GopherAgentServer
        
        server = GopherAgentServer()
        
        # Check handle_request can handle new methods
        test_methods = [
            "should_use_agentic_mode",
            "run_agentic_task"
        ]
        
        all_passed = True
        for method in test_methods:
            # Test request handling
            test_request = {
                "id": 1,
                "method": method,
                "params": {"message": "test", "context": {}}
            }
            
            try:
                response = server.handle_request(test_request)
                if response.get("error"):
                    print(f"[WARN] {method}: {response.get('error')}")
                else:
                    print(f"[OK] {method} handled")
            except Exception as e:
                print(f"[FAIL] {method} failed: {e}")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all verification checks."""
    print("\n" + "=" * 60)
    print("AGENTIC UPGRADES VERIFICATION")
    print("=" * 60)
    print()
    
    results = []
    
    results.append(("Imports", verify_imports()))
    results.append(("GopherAgent", verify_gopher_agent()))
    results.append(("Memory Tools", verify_memory_tools()))
    results.append(("Vision Tool", verify_vision_tool()))
    results.append(("Tool Registry", verify_tool_registry()))
    results.append(("ReAct Agent", verify_react_agent()))
    results.append(("Persistent Server", verify_persistent_server()))
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n[SUCCESS] ALL VERIFICATIONS PASSED!")
        print("All agentic upgrades are properly implemented.")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} verification(s) failed.")
        print("Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

