# GopherAgent Optimization Guide

## Performance Issues Fixed

### 1. Tool Name Validation
- ✅ Added validation BEFORE tool execution
- ✅ Catches invalid tool names like "BMAD" 
- ✅ Redirects to correct tool for URLs
- ✅ Lists available tools in error messages

### 2. Improved Tool Descriptions
- ✅ Explicitly lists valid tool names
- ✅ Warns against inventing tool names
- ✅ Clearer instructions for URL tools
- ✅ Shows exact tool name format

### 3. Faster Discord Bot Calls

#### Option A: HTTP Server (Recommended)
Start GopherAgent HTTP server for faster calls:

```bash
# Start HTTP server
python src/api/gopher_agent_server.py

# Or with custom port
GOPHER_AGENT_PORT=8765 python src/api/gopher_agent_server.py
```

Enable in Discord bot `.env`:
```env
GOPHER_AGENT_HTTP=true
GOPHER_AGENT_URL=http://localhost:8765
```

**Benefits:**
- ✅ Much faster (no subprocess overhead)
- ✅ Persistent connection
- ✅ Better error handling
- ✅ Lower latency

#### Option B: Subprocess (Current)
- ✅ Increased timeout to 8s
- ✅ Better caching
- ✅ Optimized prompts
- ✅ Reduced tokens (150 instead of 200)

## Tool Calling Improvements

### Invalid Tool Name Handling
When LLM calls invalid tool (like "BMAD"):
1. **Validation**: Check if tool exists BEFORE execution
2. **Redirect**: If URL detected, redirect to correct tool
3. **Error**: Log available tools and skip invalid call
4. **Feedback**: Tell LLM what went wrong

### Tool Description Updates
- Explicitly lists valid tool names
- Warns against inventing names
- Shows exact format for URL tools
- Provides examples

## Configuration

### For Best Performance

```env
# Enable HTTP server mode (faster)
GOPHER_AGENT_HTTP=true
GOPHER_AGENT_URL=http://localhost:8765

# Or use subprocess mode (current default)
# GOPHER_AGENT_HTTP=false
```

### Cache Settings
```env
CACHE_ENABLED=true
CACHE_MAX_SIZE=2000  # Increased for better hit rate
CACHE_TTL_SECONDS=600  # 10 minutes
```

## Monitoring

### Check GopherAgent Status
```python
from src.agents import get_gopher_agent
agent = get_gopher_agent()
metrics = agent.get_metrics()
print(f"Cache hit rate: {metrics['cache_hit_rate']:.2%}")
```

### HTTP Server Health
```bash
curl http://localhost:8765/health
```

## Troubleshooting

### Timeout Issues
1. **Use HTTP server**: Much faster than subprocess
2. **Increase cache**: More cache hits = faster responses
3. **Check LMStudio**: Ensure it's running and responsive

### Wrong Tool Names
- ✅ Now validated BEFORE execution
- ✅ Redirects to correct tool automatically
- ✅ Logs available tools for debugging

### Performance
- **HTTP mode**: ~50-100ms (vs 5-8s subprocess)
- **Cache hits**: ~1-5ms (instant)
- **Cache miss**: ~100-200ms (LLM call)

## Next Steps

1. **Start HTTP server** for best performance
2. **Monitor cache hit rate** - should be 70-80%
3. **Check logs** for tool validation messages
4. **Adjust cache size** based on usage patterns

