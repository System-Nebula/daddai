"""
Code Interpreter Tool - Allows the agent to run Python code safely.
Wraps ToolSandbox for secure execution.
Now async for better concurrency.
"""
from typing import Dict, Any, Optional
import asyncio
from src.tools.tool_sandbox import ToolSandbox

class CodeInterpreter:
    """
    Safe Python code interpreter for the agent.
    """
    def __init__(self):
        self.sandbox = ToolSandbox()
        
    async def run_python(self, code: str) -> str:
        """
        Run Python code asynchronously and return the result.
        
        Args:
            code: Python code to execute.
            
        Returns:
            String representation of the result or error.
        """
        # Wrap code in a function to capture return value easily if needed,
        # but ToolSandbox expects a function name.
        # For general script execution, we might need to adapt ToolSandbox or wrap the code.
        
        # ToolSandbox expects: execute_safely(code, function_name, arguments)
        # We'll wrap the user's code in a 'main' function if it's not already structured.
        
        if "def main(" not in code:
            # Indent code
            indented_code = "\n".join(["    " + line for line in code.split("\n")])
            wrapped_code = f"def main():\n{indented_code}"
            function_name = "main"
        else:
            wrapped_code = code
            function_name = "main"
        
        # Run sync sandbox execution in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.sandbox.execute_safely(
                code=wrapped_code,
                function_name=function_name,
                arguments={},
                timeout=10.0
            )
        )
        
        if result["success"]:
            return str(result["result"])
        else:
            return f"Error: {result['error']}"

    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for the LLM."""
        return {
            "name": "run_python",
            "description": "Execute Python code to solve math, logic, or data problems. Code must be safe (no file I/O, no network).",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The Python code to execute. Should return the result."
                    }
                },
                "required": ["code"]
            }
        }

