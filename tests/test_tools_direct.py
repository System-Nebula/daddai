import sys
import os
import json

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from config import (
    LLM_PROVIDER, LMSTUDIO_BASE_URL, LMSTUDIO_MODEL,
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
    CHUTES_API_KEY, CHUTES_BASE_URL, CHUTES_MODEL
)

def test_tools():
    print(f"Testing tools with provider: {LLM_PROVIDER}")
    
    if LLM_PROVIDER == "lmstudio":
        llm = ChatOpenAI(
            base_url=LMSTUDIO_BASE_URL,
            api_key="lm-studio",
            model=LMSTUDIO_MODEL,
            temperature=0
        )
    elif LLM_PROVIDER == "chutes":
        llm = ChatOpenAI(
            base_url=CHUTES_BASE_URL,
            api_key=CHUTES_API_KEY,
            model=CHUTES_MODEL,
            temperature=0
        )
    else:
        llm = ChatOpenAI(
            base_url=OPENAI_BASE_URL,
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            temperature=0
        )

    @tool
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    tools = [add]
    llm_with_tools = llm.bind_tools(tools)

    try:
        print("Invoking LLM with tool...")
        response = llm_with_tools.invoke("What is 5 + 7?")
        print(f"Response: {response}")
        print(f"Tool calls: {response.tool_calls}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_tools()
