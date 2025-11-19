#!/usr/bin/env python3
"""
Test script to verify Python servers can be imported correctly
"""
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("Testing Python server imports...\n")

# Test memory_server
try:
    from src.api.memory_server import MemoryServer
    print("[OK] memory_server.py imports correctly")
    print("  -> MemoryServer class available")
except Exception as e:
    print(f"[FAIL] memory_server.py failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test chat_server
try:
    from src.api.chat_server import ChatServer
    print("[OK] chat_server.py imports correctly")
    print("  -> ChatServer class available")
except Exception as e:
    print(f"[FAIL] chat_server.py failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n=== All Python Servers Import Successfully ===")
print("Python servers are ready to use!")

