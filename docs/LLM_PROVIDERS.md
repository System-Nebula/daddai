# LLM Provider Integration Guide

This project now supports multiple OpenAI-compatible LLM providers, including Chutes AI, OpenAI, and custom providers.

## Supported Providers

- **LMStudio** (default) - Local LLM models
- **OpenAI** - Official OpenAI API
- **Chutes AI** - OpenAI-compatible provider with thinking models
- **Custom** - Any OpenAI-compatible API endpoint

## Configuration

Set the following environment variables in your `.env` file:

### Provider Selection
```env
# Choose provider: "lmstudio", "openai", "chutes", or "custom"
LLM_PROVIDER=chutes

# Enable streaming (optional, default: false)
LLM_STREAMING_ENABLED=true
```

### Chutes AI Configuration
```env
CHUTES_API_KEY=your_chutes_api_key
CHUTES_BASE_URL=https://llm.chutes.ai/v1
CHUTES_MODEL=deepseek-ai/DeepSeek-V3-0324
# Optional: Set to true only if your Chutes configuration specifically requires input_args wrapper (default: false)
# Most existing chutes work without the wrapper
CHUTES_USE_INPUT_ARGS_WRAPPER=false
```

### OpenAI Configuration
```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo
```

### Custom Provider Configuration
```env
CUSTOM_LLM_BASE_URL=https://your-provider.com/v1
CUSTOM_LLM_API_KEY=your_api_key
CUSTOM_LLM_MODEL=your-model-name
```

## Usage

### Using the Client Factory

```python
from src.clients.llm_client_factory import get_llm_client

# Get default client (uses LLM_PROVIDER from config)
client = get_llm_client()

# Or specify provider explicitly
client = get_llm_client(provider="chutes")

# Generate response
messages = [
    {"role": "user", "content": "Tell me a story."}
]
response = client.generate_response(
    messages=messages,
    temperature=0.7,
    max_tokens=500
)
```

### Streaming Support

```python
from src.clients.llm_client_factory import get_llm_client

client = get_llm_client(provider="chutes")

messages = [
    {"role": "user", "content": "Tell me a 250 word story."}
]

# Stream response
for chunk in client.generate_stream(
    messages=messages,
    temperature=0.7,
    max_tokens=1024
):
    if chunk.get('content'):
        print(chunk['content'], end='', flush=True)
    
    # For thinking models, you can also access thinking content
    if chunk.get('thinking'):
        print(f"\n[Thinking: {chunk['thinking']}]")
    
    if chunk.get('finish_reason'):
        print(f"\n[Finished: {chunk['finish_reason']}]")
```

### Advanced Parameters

The client supports all OpenAI-compatible parameters. You can pass additional parameters via `**kwargs`:

```python
client = get_llm_client(provider="chutes")

response = client.generate_response(
    messages=[...],
    temperature=0.7,
    max_tokens=1024,
    top_p=0.9,           # Nucleus sampling
    top_k=40,            # Top-k sampling
    presence_penalty=0.1, # Presence penalty
    frequency_penalty=0.1,# Frequency penalty
    repetition_penalty=1.1 # Repetition penalty
)
```

Supported parameters include:
- `top_p`, `top_k` - Sampling parameters
- `presence_penalty`, `frequency_penalty` - Penalty parameters
- `repetition_penalty` - Repetition control
- `stop` - Stop sequences (string or array)
- `seed` - Random seed for reproducibility
- `logprobs` - Return log probabilities
- And more (see Chutes API schema)

### Chutes AI Example

Chutes AI supports thinking models and streaming. Here's a complete example:

```python
import os
from src.clients.llm_client_factory import get_llm_client

# Set environment variables
os.environ['LLM_PROVIDER'] = 'chutes'
os.environ['CHUTES_API_KEY'] = 'your-api-key'
os.environ['CHUTES_MODEL'] = 'moonshotai/Kimi-K2-Thinking'
os.environ['LLM_STREAMING_ENABLED'] = 'true'

# Get client
client = get_llm_client(provider="chutes")

# Stream response
messages = [
    {
        "role": "user",
        "content": "Tell me a 250 word story."
    }
]

full_response = ""
for chunk in client.generate_stream(
    messages=messages,
    temperature=0.7,
    max_tokens=1024
):
    if chunk.get('content'):
        content = chunk['content']
        full_response += content
        print(content, end='', flush=True)

print(f"\n\nComplete response: {full_response}")
```

## Command Line Usage

### Chat API with Streaming

```bash
# Non-streaming (default)
python src/api/chat_api.py --message "Hello!"

# With streaming
python src/api/chat_api.py --message "Tell me a story" --stream
```

### Test Chutes Integration

```bash
# Test streaming
python examples/test_chutes_integration.py --mode stream

# Test non-streaming
python examples/test_chutes_integration.py --mode non-stream

# Test both
python examples/test_chutes_integration.py --mode both
```

## API Compatibility

All providers must support the OpenAI Chat Completions API format:

```json
{
  "model": "model-name",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": true
}
```

### Streaming Response Format

Streaming responses use Server-Sent Events (SSE) format:

```
data: {"choices": [{"delta": {"content": "Hello"}}]}
data: {"choices": [{"delta": {"content": " world"}}]}
data: [DONE]
```

### Thinking Models

For thinking models (like Chutes), the delta may include a `thinking` field:

```json
{
  "choices": [{
    "delta": {
      "content": "Hello",
      "thinking": "The user wants a greeting..."
    }
  }]
}
```

## Migration from LMStudio

If you're currently using LMStudio and want to switch to Chutes or another provider:

1. Update your `.env` file with the new provider settings
2. Set `LLM_PROVIDER` to your desired provider
3. No code changes needed - the factory handles provider selection automatically

The existing code will continue to work:

```python
# This still works - uses factory internally
from src.clients.llm_client_factory import get_default_llm_client

client = get_default_llm_client()
response = client.generate_response(messages=[...])
```

## Troubleshooting

### API Key Not Set
```
ValueError: CHUTES_API_KEY must be set for Chutes provider
```
**Solution**: Set the API key in your `.env` file or environment variables.

### Connection Timeout
```
Exception: API timeout after 30s
```
**Solution**: Increase timeout in config or check network connectivity.

### Streaming Not Working
If streaming doesn't work, check:
1. `LLM_STREAMING_ENABLED=true` is set
2. The provider supports streaming (`stream: true`)
3. The client has `generate_stream` method

### Thinking Content Not Appearing
Thinking models may not always include thinking content in every chunk. Check:
1. The model supports thinking (e.g., Chutes with thinking models)
2. The API response includes `thinking` in the delta
3. You're accessing `chunk.get('thinking')` correctly

### Input Args Wrapper
Some Chutes endpoints may require requests wrapped in `{"input_args": {...}}`. If you encounter API errors, try:
```env
CHUTES_USE_INPUT_ARGS_WRAPPER=true
```

### Stop Reason vs Finish Reason
Chutes API may return both `stop_reason` and `finish_reason`. The client handles both:
- `finish_reason` is the primary field (OpenAI standard)
- `stop_reason` is also captured if present (Chutes-specific)

## Examples

See `examples/test_chutes_integration.py` for a complete working example.

