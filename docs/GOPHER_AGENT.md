# GopherAgent - Agentic System Documentation

## Overview

GopherAgent is a smart, agentic system that makes intelligent routing and decision-making for all messages. It's optimized for RTX 3080 GPU with fast inference, aggressive caching, and batch processing.

## Features

### 🤖 Agentic Decision-Making
- **LLM-controlled routing**: Uses LLM to classify message intent and route to appropriate handlers
- **Context-aware**: Considers recent messages, user history, and channel context
- **Intelligent fallback**: Falls back to pattern matching if LLM fails

### ⚡ GPU-Optimized Performance
- **RTX 3080 optimized**: Uses GPU acceleration for embeddings and inference
- **Aggressive caching**: 5-minute TTL cache for fast repeated queries
- **Batch processing**: Processes multiple messages efficiently
- **Fast inference**: Low-temperature, low-token classification for speed

### 🎯 Smart Routing
Routes messages to appropriate handlers:
- **rag**: Document search queries
- **chat**: Casual conversation
- **tools**: Tool calls needed
- **memory**: Past conversation queries
- **action**: State modification commands
- **upload**: File uploads
- **ignore**: Don't respond

## Architecture

```
Message → GopherAgent.classify_intent() → Intent Classification
    ↓
GopherAgent.route_message() → Handler Selection
    ↓
Route to Handler (rag/chat/tools/memory/action/upload/ignore)
```

## Usage

### Python API

```python
from src.agents import get_gopher_agent

agent = get_gopher_agent()

# Classify intent
result = agent.classify_intent(
    message="What are Space Marines?",
    context={"isMentioned": True, "recentMessages": [...]}
)

# Route message
routing = agent.route_message(
    message="What are Space Marines?",
    context={"isMentioned": True}
)
```

### Discord Bot Integration

The Discord bot automatically uses GopherAgent for all message routing:

```javascript
// Automatically called in message handler
const routingResult = await gopherAgent.routeMessage(message.content, context);
// routingResult.handler = 'rag', 'chat', 'tools', etc.
```

## Configuration

### GPU Settings

GopherAgent automatically detects and uses GPU. Configure in `.env`:

```env
USE_GPU=auto  # 'auto', 'cuda', or 'cpu'
EMBEDDING_BATCH_SIZE=64  # Optimal for RTX 3080
```

### Cache Settings

```env
CACHE_ENABLED=true
CACHE_MAX_SIZE=1000
CACHE_TTL_SECONDS=300  # 5 minutes
```

## Performance Metrics

GopherAgent tracks performance metrics:

```python
metrics = agent.get_metrics()
# {
#     "intent_classifications": 100,
#     "cache_hits": 75,
#     "cache_misses": 25,
#     "cache_hit_rate": 0.75,
#     "avg_latency_ms": 150.5,
#     "gpu_enabled": True,
#     "cache_size": 500
# }
```

## Optimization Tips

### For RTX 3080 (10GB VRAM)

1. **Batch Size**: Use `EMBEDDING_BATCH_SIZE=64` (default)
2. **Cache**: Enable caching for repeated queries
3. **Model**: Use fast, efficient models in LMStudio
4. **Temperature**: Low temperature (0.1) for consistent classification

### Performance Expectations

- **Classification latency**: ~100-200ms (with cache: ~1-5ms)
- **Cache hit rate**: 70-80% (typical)
- **GPU utilization**: High during batch processing
- **Memory usage**: ~2-3GB VRAM for embeddings

## Troubleshooting

### GopherAgent not responding

1. Check LMStudio is running: `http://localhost:1234/v1`
2. Verify Python path: `PYTHON_PATH=python` in `.env`
3. Check logs for errors

### Slow performance

1. Enable GPU: `USE_GPU=cuda`
2. Increase cache size: `CACHE_MAX_SIZE=2000`
3. Use faster model in LMStudio
4. Check GPU utilization

### Cache not working

1. Verify `CACHE_ENABLED=true`
2. Check cache TTL: `CACHE_TTL_SECONDS=300`
3. Monitor cache hit rate: `agent.get_metrics()`

## Future Enhancements

- [ ] Batch LLM inference (if LMStudio supports)
- [ ] Multi-GPU support
- [ ] Advanced caching strategies
- [ ] Real-time metrics dashboard
- [ ] A/B testing framework

