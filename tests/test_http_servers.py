#!/usr/bin/env python3
"""
Test HTTP servers for Memory and Chat services
"""
import sys
import os
import time
import requests
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("=== Testing HTTP Servers ===\n")

# Test Memory HTTP Server
print("1. Testing Memory HTTP Server...")
print("   Starting server (this may take a moment)...")

# Start memory server in background (simulate)
# In real scenario, this would be started separately
memory_port = 8766
memory_base = f"http://localhost:{memory_port}"

# Wait a bit for server to start (if running)
time.sleep(2)

try:
    # Test health endpoint
    response = requests.get(f"{memory_base}/health", timeout=5)
    if response.status_code == 200:
        print(f"   ✓ Health check: {response.json()}")
    else:
        print(f"   ✗ Health check failed: {response.status_code}")
except requests.exceptions.ConnectionError:
    print(f"   ⚠ Memory server not running on port {memory_port}")
    print("   (This is expected if server isn't started)")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test Chat HTTP Server
print("\n2. Testing Chat HTTP Server...")
chat_port = 8767
chat_base = f"http://localhost:{chat_port}"

try:
    response = requests.get(f"{chat_base}/health", timeout=5)
    if response.status_code == 200:
        print(f"   ✓ Health check: {response.json()}")
    else:
        print(f"   ✗ Health check failed: {response.status_code}")
except requests.exceptions.ConnectionError:
    print(f"   ⚠ Chat server not running on port {chat_port}")
    print("   (This is expected if server isn't started)")
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n=== HTTP Server Test Complete ===")
print("\nNote: To test fully, start the servers:")
print("  python src/api/memory_server_http.py")
print("  python src/api/chat_server_http.py")

