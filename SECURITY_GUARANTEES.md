# Security Guarantees - Host System Protection

## Overview

The tool sandbox system is designed with **zero tolerance** for host system modifications. All tool execution is completely isolated and non-destructive.

## Security Layers

### Layer 1: Code Validation (Pre-Execution)

Before any code executes, it undergoes comprehensive validation:

1. **Pattern Matching**: Scans for dangerous patterns (file operations, system calls, etc.)
2. **AST Parsing**: Analyzes code structure for forbidden operations
3. **Import Blocking**: Prevents importing dangerous modules
4. **Function Blocking**: Blocks dangerous built-in functions

### Layer 2: Sandboxed Execution

During execution:

1. **Isolated Namespace**: Code runs in completely isolated environment
2. **Limited Built-ins**: Only safe, read-only functions available
3. **No File Access**: Cannot read or write files
4. **No System Calls**: Cannot execute system commands
5. **No Network**: Cannot make network requests
6. **Timeout Protection**: Execution times out after 5 seconds

### Layer 3: Runtime Protection

Additional runtime safeguards:

1. **Builtins Protection**: Cannot modify `__builtins__` or `__builtin__`
2. **Module Protection**: Cannot modify imported modules
3. **Environment Protection**: Cannot access environment variables
4. **Directory Protection**: Cannot change directories or access paths

## What is BLOCKED

### File Operations
- ❌ `open()` - File reading/writing
- ❌ `file()` - File operations
- ❌ `.write()` - Writing to files
- ❌ `.writelines()` - Writing lines
- ❌ `.remove()` - File deletion
- ❌ `.unlink()` - File unlinking
- ❌ `.rmdir()` - Directory removal
- ❌ `.rmtree()` - Recursive deletion

### System Operations
- ❌ `os.system()` - System command execution
- ❌ `os.popen()` - Process execution
- ❌ `subprocess.*` - All subprocess operations
- ❌ `shutil.*` - File system operations
- ❌ `pathlib.*` - Path operations

### Network Operations
- ❌ `socket.*` - Network sockets
- ❌ `urllib.*` - URL operations
- ❌ `requests.*` - HTTP requests
- ❌ `ftplib.*` - FTP operations
- ❌ `smtplib.*` - Email operations

### Dangerous Functions
- ❌ `eval()` - Code evaluation
- ❌ `exec()` - Code execution
- ❌ `compile()` - Code compilation
- ❌ `__import__()` - Dynamic imports
- ❌ `reload()` - Module reloading

### Environment Access
- ❌ `os.environ` - Environment variables
- ❌ `os.getenv()` - Get environment variable
- ❌ `os.chdir()` - Change directory
- ❌ `os.getcwd()` - Get current directory

### Module Modification
- ❌ Modifying `__builtins__`
- ❌ Modifying `__builtin__`
- ❌ Modifying imported modules
- ❌ Deleting module attributes

## What is ALLOWED

### Safe Operations
- ✅ Mathematical operations (+, -, *, /, etc.)
- ✅ String operations (formatting, splitting, etc.)
- ✅ List/dict operations (filtering, mapping, etc.)
- ✅ JSON operations (parsing, serialization)
- ✅ Date/time operations (read-only)
- ✅ Safe built-ins (abs, len, sum, etc.)

### Read-Only Operations
- ✅ Reading from provided data
- ✅ Processing data in memory
- ✅ Returning computed results
- ✅ Printing output (to stdout only)

## Storage Isolation

### Tool Storage
- Tools are stored in a **single JSON file** (`llm_tools_storage.json`)
- No directory traversal allowed
- No file system modifications
- Storage is completely isolated

### Execution Isolation
- Each tool execution is completely isolated
- No shared state between executions
- No persistent modifications
- Results are returned, not stored

## Validation Process

### Step 1: Pattern Check
```python
# Scans code for dangerous patterns
FORBIDDEN_PATTERNS = [
    r'open\s*\(',
    r'\.write\s*\(',
    r'os\.system',
    # ... etc
]
```

### Step 2: AST Analysis
```python
# Parses code structure
tree = ast.parse(code)
# Checks for forbidden imports, calls, assignments
```

### Step 3: Execution Environment
```python
# Creates isolated namespace
safe_globals = {
    '__builtins__': {only_safe_functions},
    # No file access
    # No system access
    # No network access
}
```

## Security Guarantees

### ✅ Guarantee 1: No File System Access
- Cannot read files
- Cannot write files
- Cannot delete files
- Cannot modify file permissions

### ✅ Guarantee 2: No System Modification
- Cannot execute system commands
- Cannot modify system settings
- Cannot access environment variables
- Cannot change directories

### ✅ Guarantee 3: No Network Access
- Cannot make HTTP requests
- Cannot open sockets
- Cannot send emails
- Cannot access external services

### ✅ Guarantee 4: No Code Injection
- Cannot execute arbitrary code
- Cannot import dangerous modules
- Cannot modify built-ins
- Cannot escape sandbox

### ✅ Guarantee 5: No Persistent Changes
- Cannot modify host files
- Cannot modify system configuration
- Cannot create persistent processes
- Cannot modify registry/system settings

## Testing Security

To verify security, try these (they should all be blocked):

```python
# These should all fail validation:
code1 = "import os; os.system('rm -rf /')"  # BLOCKED
code2 = "open('file.txt', 'w').write('data')"  # BLOCKED
code3 = "__import__('subprocess').call(['ls'])"  # BLOCKED
code4 = "eval('__import__(\"os\").system(\"ls\")')"  # BLOCKED
```

## Error Handling

When security violations are detected:

1. **Validation Phase**: Code is rejected before execution
2. **Execution Phase**: SecurityError is raised and caught
3. **Result**: Tool execution fails safely with error message
4. **No Damage**: Host system remains completely untouched

## Best Practices

1. **Always Validate**: Code is validated before execution
2. **Isolated Execution**: Each execution is completely isolated
3. **Timeout Protection**: Long-running code is terminated
4. **Error Handling**: All errors are caught and reported safely
5. **No Side Effects**: Tools cannot have side effects on host system

## Conclusion

The tool sandbox provides **complete isolation** from the host system. Tools can:
- ✅ Process data
- ✅ Perform calculations
- ✅ Return results

Tools **cannot**:
- ❌ Modify files
- ❌ Execute commands
- ❌ Access network
- ❌ Modify system
- ❌ Escape sandbox

**The host system is completely protected.**

