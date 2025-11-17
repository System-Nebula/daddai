# Setting Up Discord Bot with Chutes AI

## Quick Setup

1. **Update your `.env` file** (in the project root, not discord-bot folder):

```env
# Set provider to Chutes
LLM_PROVIDER=chutes

# Chutes AI Configuration
CHUTES_API_KEY=your-chutes-api-key-here
CHUTES_BASE_URL=https://llm.chutes.ai/v1
CHUTES_MODEL=deepseek-ai/DeepSeek-V3-0324

# Optional: Enable streaming
LLM_STREAMING_ENABLED=true

# Optional: Set to true only if your Chutes configuration specifically requires input_args wrapper (default: false)
# Most existing chutes work without the wrapper
CHUTES_USE_INPUT_ARGS_WRAPPER=false
```

2. **Restart the Discord bot**:

```bash
cd discord-bot
node index.js
```

## What Gets Updated

The bot uses two Python services that now support Chutes:

1. **Chat Service** (`src/api/chat_api.py`)
   - Simple chat responses
   - Uses `get_default_llm_client()` which respects `LLM_PROVIDER`

2. **RAG Service** (`src/core/enhanced_rag_pipeline.py`)
   - Complex queries with document search
   - Uses `LMStudioClient` which can be updated to use the factory

## Testing

1. **Test simple chat**: Mention the bot with a simple message
   ```
   @bot hello!
   ```

2. **Test with tools**: Ask something that might need tools
   ```
   @bot what's the weather in New York?
   ```

3. **Test RAG**: Ask about documents
   ```
   @bot summarize this document: [attach file]
   ```

## Verification

Check the bot logs for:
```
Initialized Chutes AI client: https://llm.chutes.ai/v1
```

If you see this, Chutes is being used!

## Troubleshooting

- **Still using LMStudio?** Make sure `LLM_PROVIDER=chutes` is set in `.env`
- **API errors?** Check that `CHUTES_API_KEY` is correct
- **Connection issues?** Verify the API endpoint is accessible

