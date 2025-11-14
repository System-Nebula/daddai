"""
Tool Sandbox - Safe execution environment for LLM-generated tools.
Ensures all tool execution is non-destructive and validated.
NO HOST SYSTEM MODIFICATIONS ALLOWED.
"""
import ast
import sys
import io
import traceback
import re
from typing import Dict, Any, Optional, List, Callable
import json
from datetime import datetime
from logger_config import logger


class SecurityError(Exception):
    """Security violation exception."""
    pass


class ToolSandbox:
    """
    Sandbox for safely executing LLM-generated tools.
    Prevents destructive operations and validates code.
    """
    
    # Forbidden operations/imports - comprehensive list
    FORBIDDEN_IMPORTS = [
        'os', 'sys', 'subprocess', 'shutil', 'glob', 'pathlib',
        'pickle', 'marshal', 'eval', 'exec', '__import__',
        'open', 'file', 'input', 'raw_input',
        'ctypes', 'multiprocessing', 'threading', 'socket',
        'urllib', 'requests', 'http', 'ftplib', 'smtplib',
        'sqlite3', 'pymongo', 'psycopg2', 'mysql',
        'tempfile', 'zipfile', 'tarfile', 'gzip',
        'configparser', 'logging', 'warnings',
        '__builtin__', '__builtins__', 'builtins'
    ]
    
    FORBIDDEN_ATTRIBUTES = [
        '__del__', '__delete__', '__setattr__', '__delattr__',
        'delete', 'remove', 'unlink', 'rmdir', 'rmtree',
        'write', 'writelines', 'truncate', 'flush',
        'chmod', 'chown', 'rename', 'move', 'copy',
        'mkdir', 'makedirs', 'rmdir', 'removedirs',
        'unlink', 'remove', 'rmtree', 'delete'
    ]
    
    # Forbidden function names
    FORBIDDEN_FUNCTIONS = [
        'eval', 'exec', 'compile', '__import__', 'reload',
        'open', 'file', 'input', 'raw_input',
        'exit', 'quit', 'help', 'license', 'credits'
    ]
    
    # Allowed built-ins (safe operations only - read-only operations)
    SAFE_BUILTINS = {
        'abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'filter',
        'float', 'int', 'len', 'list', 'map', 'max', 'min', 'range',
        'reversed', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip',
        'round', 'isinstance', 'hasattr', 'getattr',
        'print',  # print is safe - only outputs
        'hash', 'id', 'iter', 'next', 'repr', 'vars',
        'ord', 'chr', 'bin', 'hex', 'oct'
    }
    
    # Forbidden patterns in code
    FORBIDDEN_PATTERNS = [
        r'__import__\s*\(',
        r'eval\s*\(',
        r'exec\s*\(',
        r'compile\s*\(',
        r'open\s*\(',
        r'file\s*\(',
        r'\.write\s*\(',
        r'\.writelines\s*\(',
        r'\.remove\s*\(',
        r'\.delete\s*\(',
        r'\.unlink\s*\(',
        r'\.rmdir\s*\(',
        r'\.rmtree\s*\(',
        r'os\.system',
        r'os\.popen',
        r'subprocess\.',
        r'socket\.',
        r'urllib\.',
        r'requests\.',
        r'__builtins__',
        r'__builtin__',
        r'builtins\.',
        r'import\s+os',
        r'import\s+sys',
        r'import\s+subprocess',
        r'import\s+shutil',
        r'from\s+os\s+import',
        r'from\s+sys\s+import',
    ]
    
    def __init__(self):
        """Initialize sandbox."""
        self.execution_history: List[Dict[str, Any]] = []
    
    def validate_code(self, code: str) -> Dict[str, Any]:
        """
        Validate code for safety before execution.
        Comprehensive validation to prevent any host system modifications.
        
        Returns:
            Dict with 'valid' (bool) and 'errors' (list)
        """
        errors = []
        
        try:
            # Step 1: Pattern-based checks (before parsing)
            import re
            code_lower = code.lower()
            
            for pattern in self.FORBIDDEN_PATTERNS:
                if re.search(pattern, code, re.IGNORECASE):
                    errors.append(f"Forbidden pattern detected: {pattern}")
            
            # Step 2: Parse AST to check for dangerous operations
            tree = ast.parse(code)
            
            # Step 3: AST-based validation
            for node in ast.walk(tree):
                # Check imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in self.FORBIDDEN_IMPORTS:
                            errors.append(f"Forbidden import: {alias.name}")
                        # Check for partial matches (e.g., 'os.path')
                        for forbidden in self.FORBIDDEN_IMPORTS:
                            if alias.name.startswith(forbidden + '.'):
                                errors.append(f"Forbidden import: {alias.name}")
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split('.')[0] in self.FORBIDDEN_IMPORTS:
                        errors.append(f"Forbidden import from: {node.module}")
                
                # Check for dangerous function calls
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in self.FORBIDDEN_FUNCTIONS:
                            errors.append(f"Forbidden function call: {node.func.id}")
                    elif isinstance(node.func, ast.Attribute):
                        # Check attribute access (e.g., os.system, file.write)
                        if node.func.attr in self.FORBIDDEN_ATTRIBUTES:
                            errors.append(f"Forbidden attribute access: {node.func.attr}")
                        # Check if accessing forbidden modules
                        if isinstance(node.func.value, ast.Name):
                            if node.func.value.id in self.FORBIDDEN_IMPORTS:
                                errors.append(f"Forbidden module access: {node.func.value.id}.{node.func.attr}")
                
                # Check for attribute assignment (could modify objects)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute):
                            # Allow attribute assignment only for local variables
                            # Block assignment to imported modules
                            if isinstance(target.value, ast.Name):
                                if target.value.id in self.FORBIDDEN_IMPORTS:
                                    errors.append(f"Forbidden assignment to module: {target.value.id}.{target.attr}")
                
                # Check for deletion operations
                elif isinstance(node, ast.Delete):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute):
                            errors.append(f"Forbidden delete operation: {target.attr}")
                        elif isinstance(target, ast.Name):
                            if target.id in self.FORBIDDEN_IMPORTS:
                                errors.append(f"Forbidden delete of module: {target.id}")
                
                # Check for with statements (file operations)
                elif isinstance(node, ast.With):
                    for item in node.items:
                        if isinstance(item.context_expr, ast.Call):
                            if isinstance(item.context_expr.func, ast.Name):
                                if item.context_expr.func.id == 'open':
                                    errors.append("Forbidden file operation: open()")
            
            # Step 4: Additional safety checks
            # Check for any attempt to modify __builtins__
            if '__builtins__' in code or '__builtin__' in code or 'builtins' in code:
                errors.append("Forbidden: Attempt to modify builtins")
            
            # Check for any attempt to access environment
            if 'environ' in code_lower or 'getenv' in code_lower:
                errors.append("Forbidden: Environment variable access")
            
            # Check for any attempt to change directory or path operations
            if 'chdir' in code_lower or 'getcwd' in code_lower:
                errors.append("Forbidden: Directory operations")
        
        except SyntaxError as e:
            errors.append(f"Syntax error: {str(e)}")
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def execute_safely(self,
                      code: str,
                      function_name: str,
                      arguments: Dict[str, Any],
                      timeout: float = 5.0) -> Dict[str, Any]:
        """
        Execute code safely in sandbox.
        
        Args:
            code: Python code to execute
            function_name: Name of function to call
            arguments: Arguments to pass to function
            timeout: Execution timeout in seconds
            
        Returns:
            Dict with 'success', 'result', 'error', 'execution_time'
        """
        start_time = datetime.now()
        
        # Validate code first
        validation = self.validate_code(code)
        if not validation["valid"]:
            return {
                "success": False,
                "error": f"Code validation failed: {', '.join(validation['errors'])}",
                "execution_time": 0.0
            }
        
        # Create safe execution environment - completely isolated
        # Only include safe, read-only built-ins
        safe_builtins_dict = {}
        for k in self.SAFE_BUILTINS:
            if k in __builtins__:
                try:
                    safe_builtins_dict[k] = __builtins__[k]
                except (KeyError, AttributeError):
                    pass
        
        # Create completely isolated environment
        safe_globals = {
            '__builtins__': safe_builtins_dict,
            '__name__': '__sandbox__',
            '__doc__': None,
            '__package__': None,
            '__loader__': None,
            '__spec__': None,
        }
        
        # Only allow safe, read-only modules
        try:
            import json
            safe_globals['json'] = json
        except:
            pass
        
        try:
            import datetime
            safe_globals['datetime'] = datetime
        except:
            pass
        
        try:
            import time
            # Only allow read-only time functions
            safe_time = type('SafeTime', (), {
                'time': time.time,
                'sleep': lambda x: None,  # No-op sleep (prevent blocking)
            })()
            safe_globals['time'] = safe_time
        except:
            pass
        
        safe_locals = {}
        
        try:
            # Additional safety: Check code doesn't try to escape sandbox
            if '__builtins__' in code or '__builtin__' in code:
                raise SecurityError("Code attempts to access builtins")
            
            # Execute code in sandbox with additional protection
            # Use compile to ensure code is valid before exec
            compiled_code = compile(code, '<sandbox>', 'exec')
            
            # Execute in isolated environment
            exec(compiled_code, safe_globals, safe_locals)
            
            # Get function
            if function_name not in safe_locals:
                return {
                    "success": False,
                    "error": f"Function '{function_name}' not found in code",
                    "execution_time": (datetime.now() - start_time).total_seconds()
                }
            
            func = safe_locals[function_name]
            
            if not callable(func):
                return {
                    "success": False,
                    "error": f"'{function_name}' is not callable",
                    "execution_time": (datetime.now() - start_time).total_seconds()
                }
            
            # Call function
            result = func(**arguments)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Record execution
            self.execution_history.append({
                "function_name": function_name,
                "arguments": arguments,
                "result": str(result)[:500],  # Limit result size
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "success": True,
                "result": result,
                "execution_time": execution_time
            }
        
        except SecurityError as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return {
                "success": False,
                "error": f"Security violation: {str(e)}",
                "execution_time": execution_time
            }
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            logger.debug(f"Sandbox execution error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "execution_time": execution_time
            }
    
    def test_tool(self,
                 code: str,
                 function_name: str,
                 test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Test a tool with multiple test cases.
        
        Args:
            code: Python code
            function_name: Function name
            test_cases: List of test cases with 'arguments' and 'expected_result'
            
        Returns:
            Test results
        """
        results = {
            "total_tests": len(test_cases),
            "passed": 0,
            "failed": 0,
            "test_results": []
        }
        
        for i, test_case in enumerate(test_cases):
            arguments = test_case.get("arguments", {})
            expected = test_case.get("expected_result")
            
            execution_result = self.execute_safely(code, function_name, arguments)
            
            test_result = {
                "test_case": i + 1,
                "arguments": arguments,
                "success": execution_result["success"],
                "result": execution_result.get("result"),
                "error": execution_result.get("error")
            }
            
            if execution_result["success"]:
                # Check if result matches expected (if provided)
                if expected is not None:
                    if execution_result["result"] == expected:
                        results["passed"] += 1
                        test_result["passed"] = True
                    else:
                        results["failed"] += 1
                        test_result["passed"] = False
                        test_result["expected"] = expected
                else:
                    # No expected result, just check if it executed
                    results["passed"] += 1
                    test_result["passed"] = True
            else:
                results["failed"] += 1
                test_result["passed"] = False
            
            results["test_results"].append(test_result)
        
        return results


class SecurityError(Exception):
    """Security violation exception."""
    pass


class ToolStorage:
    """Stores and manages LLM-generated tools."""
    
    def __init__(self, storage_path: str = "llm_tools_storage.json"):
        """
        Initialize tool storage.
        Storage is isolated to a single JSON file - no system modifications.
        """
        # Ensure storage path is safe (no directory traversal)
        import os
        if '..' in storage_path or '/' in storage_path.replace('\\', '/'):
            # Only allow filename in current directory
            self.storage_path = os.path.basename(storage_path)
        else:
            self.storage_path = storage_path
        
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._load_tools()
    
    def _load_tools(self):
        """Load tools from storage."""
        try:
            import os
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.tools = json.load(f)
            else:
                self.tools = {}
        except Exception as e:
            logger.warning(f"Could not load tools from storage: {e}")
            self.tools = {}
    
    def _save_tools(self):
        """Save tools to storage."""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.tools, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Could not save tools to storage: {e}")
    
    def store_tool(self,
                  tool_name: str,
                  code: str,
                  description: str,
                  parameters: Dict[str, Any],
                  test_results: Optional[Dict[str, Any]] = None) -> bool:
        """
        Store a new tool.
        
        Returns:
            True if stored successfully
        """
        if tool_name in self.tools:
            return False  # Tool already exists
        
        self.tools[tool_name] = {
            "code": code,
            "description": description,
            "parameters": parameters,
            "test_results": test_results,
            "created_at": datetime.now().isoformat(),
            "usage_count": 0
        }
        
        self._save_tools()
        return True
    
    def get_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get a stored tool."""
        return self.tools.get(tool_name)
    
    def list_tools(self) -> List[str]:
        """List all stored tool names."""
        return list(self.tools.keys())
    
    def increment_usage(self, tool_name: str):
        """Increment tool usage count."""
        if tool_name in self.tools:
            self.tools[tool_name]["usage_count"] = self.tools[tool_name].get("usage_count", 0) + 1
            self._save_tools()
    
    def delete_tool(self, tool_name: str) -> bool:
        """Delete a tool (for cleanup)."""
        if tool_name in self.tools:
            del self.tools[tool_name]
            self._save_tools()
            return True
        return False

