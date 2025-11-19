"""
ReAct Agent using LangGraph.
Implements a Thought-Action-Observation loop for complex tasks.
"""
import operator
import time
from typing import Annotated, List, Union, Dict, Any
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from config import (
    LLM_PROVIDER, LMSTUDIO_BASE_URL, LMSTUDIO_MODEL,
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
    CHUTES_API_KEY, CHUTES_BASE_URL, CHUTES_MODEL
)
from src.tools.code_interpreter import CodeInterpreter
from src.tools.memory_tools import MemoryTools
from logger_config import logger

# Define State
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

class ReActAgent:
    """
    Agent that uses ReAct pattern via LangGraph.
    Implements Thought -> Action -> Observation loop with step tracking.
    """
    def __init__(self):
        self.tools = self._setup_tools()
        self.llm = self._setup_llm()
        self.graph = self._build_graph()
        self.last_execution = {
            "steps": [],
            "tool_calls": [],
            "final_result": None
        }
        
    def _setup_tools(self):
        """Initialize tools."""
        code_interpreter = CodeInterpreter()
        memory_tools = MemoryTools()
        
        # Wrap tools for LangChain
        from langchain_core.tools import tool
        
        @tool
        def run_python(code: str) -> str:
            """Execute Python code to solve math, logic, or data problems. Code must be safe (no file I/O, no network). Returns the result or error message."""
            try:
                result = code_interpreter.run_python(code)
                # Track tool call
                self.last_execution["tool_calls"].append({
                    "tool": "run_python",
                    "code": code[:200],  # Truncate for logging
                    "success": True
                })
                return result
            except Exception as e:
                self.last_execution["tool_calls"].append({
                    "tool": "run_python",
                    "code": code[:200],
                    "success": False,
                    "error": str(e)
                })
                return f"Error: {str(e)}"
            
        @tool
        def save_core_memory(content: str, channel_id: str) -> str:
            """Save an important fact, user preference, or long-term memory to core memory. Use this to remember important information about users or preferences."""
            try:
                result = memory_tools.save_core_memory(content, channel_id)
                self.last_execution["tool_calls"].append({
                    "tool": "save_core_memory",
                    "content": content[:200],
                    "channel_id": channel_id,
                    "success": True
                })
                return result
            except Exception as e:
                self.last_execution["tool_calls"].append({
                    "tool": "save_core_memory",
                    "success": False,
                    "error": str(e)
                })
                return f"Error: {str(e)}"
        
        @tool
        def update_core_memory(memory_id: str, content: str, channel_id: str) -> str:
            """Update an existing core memory. Use this to modify or update previously saved memories."""
            try:
                # MemoryTools doesn't have update yet, so we'll add it
                result = memory_tools.update_core_memory(memory_id, content, channel_id)
                self.last_execution["tool_calls"].append({
                    "tool": "update_core_memory",
                    "memory_id": memory_id,
                    "content": content[:200],
                    "success": True
                })
                return result
            except Exception as e:
                self.last_execution["tool_calls"].append({
                    "tool": "update_core_memory",
                    "success": False,
                    "error": str(e)
                })
                return f"Error: {str(e)}"
            
        return [run_python, save_core_memory, update_core_memory]

    def _setup_llm(self):
        """Configure LLM based on config.py."""
        # Note: We bind tools manually in the graph or let the model handle it
        if LLM_PROVIDER == "lmstudio":
            return ChatOpenAI(
                base_url=LMSTUDIO_BASE_URL,
                api_key="lm-studio",
                model=LMSTUDIO_MODEL,
                temperature=0
            )
        elif LLM_PROVIDER == "chutes":
            return ChatOpenAI(
                base_url=CHUTES_BASE_URL,
                api_key=CHUTES_API_KEY,
                model=CHUTES_MODEL,
                temperature=0
            )
        else: # openai or default
            return ChatOpenAI(
                base_url=OPENAI_BASE_URL,
                api_key=OPENAI_API_KEY,
                model=OPENAI_MODEL,
                temperature=0
            )

    def _build_graph(self):
        """Build the LangGraph with step tracking."""
        # Bind tools to LLM
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Define nodes with step tracking
        def call_model(state):
            messages = state['messages']
            
            # Track step
            step = {
                "type": "thought",
                "timestamp": time.time(),
                "content": messages[-1].content if messages else "Initial message"
            }
            self.last_execution["steps"].append(step)
            
            response = llm_with_tools.invoke(messages)
            
            # Track action if tool calls are present
            if hasattr(response, 'tool_calls') and response.tool_calls:
                action_step = {
                    "type": "action",
                    "timestamp": time.time(),
                    "tool_calls": [
                        {
                            "name": tc.get("name", ""),
                            "arguments": tc.get("args", {})
                        }
                        for tc in response.tool_calls
                    ]
                }
                self.last_execution["steps"].append(action_step)
            
            return {"messages": [response]}

        def execute_tools(state):
            """Execute tools and track observations."""
            messages = state['messages']
            last_message = messages[-1]
            
            # Execute tools
            tool_node = ToolNode(self.tools)
            tool_results = tool_node.invoke(state)
            
            # Track observations
            for tool_message in tool_results.get("messages", []):
                if isinstance(tool_message, ToolMessage):
                    observation_step = {
                        "type": "observation",
                        "timestamp": time.time(),
                        "tool": tool_message.name if hasattr(tool_message, 'name') else "unknown",
                        "result": str(tool_message.content)[:500]  # Truncate for logging
                    }
                    self.last_execution["steps"].append(observation_step)
            
            return tool_results
        
        workflow = StateGraph(AgentState)
        
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", execute_tools)
        
        # Define edges
        workflow.set_entry_point("agent")
        
        def should_continue(state):
            messages = state['messages']
            last_message = messages[-1]
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tools"
            return END
            
        workflow.add_conditional_edges(
            "agent",
            should_continue,
        )
        
        workflow.add_edge("tools", "agent")
        
        return workflow.compile()

    def run(self, message: str, context: Dict[str, Any] = None) -> str:
        """
        Run the agent on a message with ReAct pattern.
        Implements Thought -> Action -> Observation loop.
        """
        # Reset execution tracking
        self.last_execution = {
            "steps": [],
            "tool_calls": [],
            "final_result": None
        }
        
        channel_id = context.get("channel_id", "unknown") if context else "unknown"
        user_id = context.get("user_id", "unknown") if context else "unknown"
        
        system_prompt = f"""You are a helpful AI assistant with access to tools. Use the ReAct pattern:
        1. **Thought**: Think about what you need to do
        2. **Action**: Use tools if needed (run_python for calculations, save_core_memory for remembering)
        3. **Observation**: Analyze the tool results
        4. Repeat until you have the final answer
        
        Available tools:
        - run_python(code): Execute Python code for math, logic, or data processing. Code must be safe (no file I/O, no network).
        - save_core_memory(content, channel_id): Save important facts or user preferences to long-term memory.
        - update_core_memory(memory_id, content, channel_id): Update existing memories.
        
        Context:
        - Channel ID: {channel_id}
        - User ID: {user_id}
        
        Think step by step, use tools when needed, and provide a clear final answer.
        """
        
        inputs = {
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=message)
            ]
        }
        
        # Run graph with max iterations
        max_iterations = 10
        iteration = 0
        
        try:
            final_state = self.graph.invoke(inputs)
            final_message = final_state['messages'][-1]
            
            # Store final result
            self.last_execution["final_result"] = final_message.content if hasattr(final_message, 'content') else str(final_message)
            
            return self.last_execution["final_result"]
        except Exception as e:
            logger.error(f"ReAct agent error: {e}", exc_info=True)
            self.last_execution["final_result"] = f"Error: {str(e)}"
            return f"I encountered an error while processing your request: {str(e)}"
