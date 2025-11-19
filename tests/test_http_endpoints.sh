#!/bin/bash
# Test HTTP endpoints (for reference - Windows users can use curl or PowerShell)

echo "=== Testing HTTP Endpoints ==="
echo ""
echo "Note: Start HTTP servers first:"
echo "  python src/api/memory_server_http.py"
echo "  python src/api/chat_server_http.py"
echo ""

# Test Memory Service
echo "1. Testing Memory Service..."
echo "   Health check:"
curl -s http://localhost:8766/health | jq .
echo ""
echo "   Ping:"
curl -s http://localhost:8766/ping | jq .
echo ""
echo "   Store memory:"
curl -s -X POST http://localhost:8766/store \
  -H "Content-Type: application/json" \
  -d '{"channel_id":"test_123","content":"Test memory","memory_type":"conversation"}' | jq .
echo ""

# Test Chat Service
echo "2. Testing Chat Service..."
echo "   Health check:"
curl -s http://localhost:8767/health | jq .
echo ""
echo "   Ping:"
curl -s http://localhost:8767/ping | jq .
echo ""
echo "   Chat:"
curl -s -X POST http://localhost:8767/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello, test!"}' | jq .
echo ""

echo "=== Test Complete ==="

