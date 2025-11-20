# Advanced Self-Hosted RAG System with Multi-Agent Capabilities

A production-ready Retrieval-Augmented Generation (RAG) system with agentic capabilities, multi-LLM support, and Discord bot integration. Features state-of-the-art retrieval techniques, intelligent memory management, and tool calling for complex task execution.

## 🎯 Key Features

### Core RAG Capabilities
- 📄 **Document Processing**: Docling-powered extraction from PDFs, Word docs, text files, and more
- 🔍 **Advanced Vector Search**: Neo4j vector index with BGE-base-en-v1.5 embeddings (768 dimensions)
- 🔎 **Hybrid Search**: Optional Elasticsearch integration for semantic + keyword search
- 🧠 **Intelligent Memory**: Context-aware memory consolidation, deduplication, and importance scoring
- 🔗 **Knowledge Graph**: Neo4j-based relationship mapping and graph traversal

### Agentic & Multi-Agent System
- 🤖 **ReAct Agent**: Reasoning + Acting pattern for complex multi-step tasks
- 🔧 **Tool Calling**: Dynamic tool selection and execution (code interpreter, vision, web tools, image generation)
- 👥 **Multi-Agent Workflow**: SearchAgent, AnalyserAgent, ReflectionAgent for specialized tasks
- 💾 **Active Memory**: MemGPT-style core memory management with explicit save/update/retrieve
- 🎨 **Image Generation**: FLUX GGUF workflow integration for AI-generated images
- 👁️ **Vision Support**: Image analysis and understanding capabilities

### LLM Provider Support
- 🏠 **LMStudio**: Local model inference (default)
- 🌐 **OpenAI**: GPT models via API
- ⚡ **Chutes AI**: High-performance thinking models (DeepSeek-V3, etc.)
- 🔌 **Custom Providers**: Extensible architecture for any OpenAI-compatible API

### Advanced Retrieval Techniques
- 🎯 **Cross-Encoder Reranking**: Improved relevance scoring
- 🔄 **Multi-Query Retrieval**: Query expansion with Reciprocal Rank Fusion (RRF)
- 💡 **HyDE**: Hypothetical Document Embeddings for better retrieval
- 📊 **MMR**: Maximal Marginal Relevance for diverse results
- ⏰ **Temporal Weighting**: Time-decay functions for recent content

### Discord Bot Integration (TypeScript)
- 💬 **Full Discord Integration**: Slash commands, message handling, rich embeds
- 📘 **TypeScript**: Modern TypeScript codebase with type safety
- 🔄 **Persistent Services**: Fast JSON-RPC communication via stdin/stdout
- 📈 **Observability**: OpenTelemetry integration, metrics, and monitoring
- 🛡️ **Resilience**: Circuit breakers, retry logic, request queuing
- 🎭 **Thinking States**: Real-time progress updates for long-running tasks

### Performance & Optimization
- 🚀 **GPU Acceleration**: Optimized for RTX 3080 with automatic detection
- ⚡ **Batch Processing**: Efficient embedding generation and document ingestion
- 💾 **Caching**: Intelligent caching for queries and embeddings
- 🔄 **Connection Pooling**: Optimized Neo4j and Elasticsearch connections
- 📊 **Performance Monitoring**: Built-in evaluation and A/B testing capabilities

## Prerequisites

### Required
1. **Python 3.8+**: Core runtime requirement
2. **Neo4j 5.x+**: Graph database for vector storage and knowledge graph
   - Download from [neo4j.com/download](https://neo4j.com/download/)
   - Default: `bolt://localhost:7687`
   - Username: `neo4j`, Password: (set during installation)
   - Vector index support requires Neo4j 5.x+ (automatic fallback available)

### LLM Provider (Choose One)
3. **LMStudio** (Recommended for local): 
   - Download from [lmstudio.ai](https://lmstudio.ai/)
   - Start server: `http://localhost:1234`
   - Load any compatible model

   **OR**

   **Chutes AI** (Recommended for cloud):
   - Sign up at [chutes.ai](https://chutes.ai)
   - Get API key and configure in `.env`

   **OR**

   **OpenAI**:
   - Get API key from [platform.openai.com](https://platform.openai.com)
   - Configure in `.env`

### Optional
4. **Elasticsearch 8.x+**: For hybrid search (optional but recommended for large collections)
   - Download from [elastic.co/downloads/elasticsearch](https://www.elastic.co/downloads/elasticsearch)
   - Default: `http://localhost:9200`
   - Enables faster hybrid semantic+keyword search

5. **Node.js 18+**: Required for Discord bot (TypeScript)
   - Download from [nodejs.org](https://nodejs.org/)
   - TypeScript support via `tsx` (included in dependencies)

6. **NVIDIA GPU** (Recommended): RTX 3080 or similar
   - CUDA-compatible GPU with 8GB+ VRAM
   - Automatic GPU detection and optimization
   - PyTorch CUDA support installed automatically

## Installation

1. Clone or download this repository

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

**Windows Quick Setup**: Run the provided setup script:
```cmd
setup_windows.bat
```

**Manual Windows Setup**: If you encounter issues with PyTorch installation, install it separately first:
```bash
# For CUDA 11.8 (recommended for RTX 3080)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Then install other dependencies
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the project root:
```env
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# LLM Provider Configuration
# Choose one: "lmstudio", "chutes", "openai", or "custom"
LLM_PROVIDER=chutes

# LMStudio Configuration (if using LMStudio)
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_MODEL=local-model

# Chutes AI Configuration (if using Chutes)
CHUTES_API_KEY=your-chutes-api-key
CHUTES_BASE_URL=https://llm.chutes.ai/v1
CHUTES_MODEL=deepseek-ai/DeepSeek-V3-0324

# OpenAI Configuration (if using OpenAI)
OPENAI_API_KEY=your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo

# Embedding Configuration (State-of-the-art BGE model)
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5  # 768 dimensions, excellent accuracy
# Alternatives: BAAI/bge-small-en-v1.5 (384 dims, faster) or BAAI/bge-large-en-v1.5 (1024 dims, best)

# GPU Configuration (auto-detected by default)
USE_GPU=auto  # 'auto', 'cuda', or 'cpu'
EMBEDDING_BATCH_SIZE=32  # Optimized for BGE-base model

# Elasticsearch Configuration (optional - for hybrid search)
ELASTICSEARCH_ENABLED=false  # Set to 'true' to enable hybrid search
ELASTICSEARCH_HOST=localhost
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_USER=
ELASTICSEARCH_PASSWORD=
ELASTICSEARCH_USE_SSL=false

# Discord Bot Configuration (if using Discord bot)
DISCORD_TOKEN=your-discord-bot-token
```

## Quick Start

### Python RAG System
1. **Start Neo4j**: Ensure Neo4j is running
2. **Start LLM Provider**: 
   - LMStudio: Launch and start server
   - Chutes AI: Configure API key in `.env`
   - OpenAI: Configure API key in `.env`
3. **Ingest documents**: `python main.py ingest --path documents/`
4. **Query**: `python main.py query --question "Your question"`

### Discord Bot (Optional - TypeScript)
1. **Install Node.js dependencies**: `cd discord-bot && npm install`
2. **Configure Discord token**: Add `DISCORD_TOKEN` to `.env`
3. **Start bot**: 
   - TypeScript (default): `cd discord-bot && npm start`
   - Development mode: `cd discord-bot && npm run dev`
   - JavaScript fallback: `cd discord-bot && npm run start:js`
4. **Use slash commands**: `/rag`, `/upload`, `/chat`, etc.

**Note**: The bot is written in TypeScript with full type safety. The codebase includes both `.ts` (TypeScript) and `.js` (JavaScript) files for compatibility.

### HTTP API Servers (Optional)
1. **Start Memory Server**: `python src/api/memory_server_http.py`
2. **Start Chat Server**: `python src/api/chat_server_http.py`
3. **Access APIs**: `http://localhost:8766` (memory) and `http://localhost:8767` (chat)

## Usage

### 1. Ingest Documents

Process and store documents in Neo4j:

```bash
# Process a single file
python main.py ingest --path documents/sample.pdf

# Process all documents in a directory
python main.py ingest --path documents/
```

Supported formats: PDF, DOCX, DOC, TXT, MD, CSV, JSON, IPYNB (Jupyter Notebooks)

### 2. Query the RAG System

#### Single Query
```bash
python main.py query --question "What is the main topic of the documents?"
```

#### Interactive Mode
```bash
python main.py interactive
```

This will start an interactive session where you can ask multiple questions.

## Project Structure

```
.
├── main.py                 # Main entry point
├── config.py              # Configuration settings
├── logger_config.py        # Logging configuration
├── requirements.txt        # Python dependencies
├── src/                    # Source code
│   ├── core/              # Core RAG components
│   ├── stores/            # Storage backends (Neo4j, Elasticsearch, hybrid)
│   ├── processors/        # Document processing
│   ├── api/               # API servers
│   ├── memory/            # Memory management
│   ├── search/            # Search components
│   ├── tools/             # LLM tools
│   ├── evaluation/        # Evaluation and monitoring
│   ├── clients/           # External clients (LMStudio, Ollama)
│   └── utils/             # Utilities
├── scripts/               # Utility scripts
├── tests/                 # Test files
├── docs/                  # Documentation
│   ├── upgrades/         # Upgrade documentation
│   └── assessments/      # Assessment documentation
├── discord-bot/           # Discord bot (TypeScript/Node.js)
│   ├── src/              # Bot source code (TypeScript + JavaScript)
│   ├── tests/            # Bot test files
│   ├── docs/             # Bot documentation
│   ├── scripts/          # Bot utility scripts
│   ├── index.ts          # Main TypeScript entry point
│   └── tsconfig.json     # TypeScript configuration
├── config/                # Config package (legacy)
├── logger/                # Logger package
└── deps/                  # Dependencies
```

See the `docs/` directory for detailed documentation:
- `docs/QUICK_START.md` - Quick start guide
- `docs/COMMANDS_REFERENCE.md` - Complete commands reference
- `docs/GOPHER_AGENT.md` - Gopher agent documentation
- `docs/upgrades/` - Upgrade and modernization documentation
- `docs/assessments/` - Codebase assessments and analysis

## How It Works

### Document Ingestion Pipeline
1. **Document Processing**: Docling extracts text, structure, tables, and metadata from various formats
2. **Intelligent Chunking**: Documents split with overlap, preserving context (semantic chunking available)
3. **Embedding Generation**: BGE-base-en-v1.5 creates 768-dimensional vectors (GPU-accelerated)
4. **Storage**: Chunks stored in Neo4j with vector indexes; optionally in Elasticsearch for hybrid search
5. **Knowledge Graph**: Relationships and metadata stored for graph traversal

### Query Pipeline
1. **Query Understanding**: Enhanced query analysis, intent classification, and entity extraction
2. **Multi-Stage Retrieval**:
   - **HyDE**: Generate hypothetical answer for better retrieval
   - **Multi-Query**: Expand query into multiple variations
   - **Vector Search**: Semantic similarity in Neo4j/Elasticsearch
   - **Keyword Search**: BM25 full-text search (if Elasticsearch enabled)
3. **Reranking**: Cross-encoder reranking for improved relevance
4. **MMR**: Maximal Marginal Relevance for diverse, non-redundant results
5. **Memory Integration**: Retrieve relevant conversation history and user context
6. **Generation**: LLM generates answer with retrieved context and tools

### Agentic Mode (Complex Tasks)
1. **Complexity Detection**: GopherAgent determines if task requires agentic mode
2. **ReAct Pattern**: Reasoning → Action → Observation loop
3. **Tool Execution**: Dynamic tool calling (code interpreter, vision, web tools, etc.)
4. **Iterative Refinement**: Multiple reasoning steps until task completion
5. **Memory Updates**: Save important information to core memory

## Configuration

Edit `config.py` or set environment variables to customize:

- **Chunking**: `CHUNK_SIZE` and `CHUNK_OVERLAP`
- **Embedding Model**: Change `EMBEDDING_MODEL` to use different sentence transformer models
- **Neo4j**: Connection details
- **LMStudio**: API URL and model name
- **Elasticsearch (Optional)**: Enable hybrid search by setting `ELASTICSEARCH_ENABLED=true` and configuring connection details

## Troubleshooting

### Neo4j Connection Issues
- Ensure Neo4j is running: `neo4j status` (or check Neo4j Desktop)
- Check connection URI and credentials in `.env` or `config.py`
- Verify Neo4j is accessible at the configured port
- Test connection: `cypher-shell -u neo4j -p your_password`

### Neo4j Vector Index
- If you see "Vector index not available" message, the system will automatically use cosine similarity calculation
- For better performance with large datasets, install Neo4j 5.x+ with vector index support
- The fallback method works but may be slower for very large document collections

### LMStudio Connection Issues
- Ensure LMStudio is running and a model is loaded
- Check that the local server is enabled in LMStudio settings (Settings → Server)
- Verify the API URL matches LMStudio's server address (default: http://localhost:1234)
- Test connection: `curl http://localhost:1234/v1/models`

### Elasticsearch (Optional)
- **Not installed**: The system works fine with Neo4j only. Elasticsearch is optional for hybrid search.
- **To enable**: Install Elasticsearch server and Python client (`pip install elasticsearch>=8.0.0`), then set `ELASTICSEARCH_ENABLED=true` in `.env`
- **Connection issues**: Verify Elasticsearch is running: `curl http://localhost:9200`
- **Benefits**: Faster search on large document collections, hybrid semantic+keyword search
- **Fallback**: If Elasticsearch is unavailable, the system automatically falls back to Neo4j-only mode

### Document Processing Errors
- Ensure documents are in supported formats (PDF, DOCX, DOC, TXT, MD, CSV, JSON, IPYNB)
- Check file permissions
- For PDFs, ensure you have necessary system dependencies
- Docling may require additional system libraries for OCR (Tesseract)

### GPU Issues (Windows)
- **CUDA not detected**: Install CUDA Toolkit 11.8 or 12.1 from NVIDIA
- **Out of memory**: Reduce `EMBEDDING_BATCH_SIZE` in `.env` (try 32 or 16)
- **PyTorch CUDA errors**: Reinstall PyTorch with correct CUDA version:
  ```bash
  pip uninstall torch torchvision torchaudio
  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
  ```
- **GPU not being used**: Check that CUDA is available: `python -c "import torch; print(torch.cuda.is_available())"`

## Performance & Optimization

### GPU Optimization (RTX 3080)

The system automatically optimizes for GPU:
- ✅ Auto-detects CUDA availability
- ✅ Batch size optimized for BGE-base model (32 chunks/batch)
- ✅ Normalized embeddings for cosine similarity
- ✅ GPU status displayed during processing

**Performance Expectations:**
- **Embedding Generation**: ~500-1000 chunks/second (BGE-base, 768 dims)
- **Document Ingestion**: Large documents processed in seconds
- **Query Response**: <100ms retrieval + LLM generation time
- **Image Generation**: 5-15 minutes (depends on queue and model)

**Manual GPU Configuration:**
```env
USE_GPU=cuda  # Force GPU
USE_GPU=cpu   # Force CPU
USE_GPU=auto  # Auto-detect (default)
EMBEDDING_BATCH_SIZE=32  # Adjust for your GPU (32 for RTX 3080)
```

### Caching & Performance

- **Query Caching**: TTL-based cache for frequent queries
- **Embedding Cache**: Cached embeddings for faster retrieval
- **Connection Pooling**: Optimized database connections
- **Batch Processing**: Efficient bulk operations

## Advanced Usage

### Available Tools

The system includes a comprehensive tool ecosystem:

- **Code Interpreter**: Execute Python code for calculations and data processing
- **Vision Tool**: Analyze images and extract information
- **Web Tools**: Summarize websites and YouTube videos
- **Image Generation**: Generate images using FLUX GGUF workflow
- **Memory Tools**: Save, retrieve, and update core memories
- **Document Search**: RAG-powered document retrieval
- **Meta Tools**: Create, test, and register custom tools dynamically

### Custom Embedding Models

Change `EMBEDDING_MODEL` in `config.py` or `.env`:
- `BAAI/bge-base-en-v1.5` (default, 768 dimensions, excellent accuracy)
- `BAAI/bge-small-en-v1.5` (384 dimensions, faster)
- `BAAI/bge-large-en-v1.5` (1024 dimensions, best accuracy)
- `all-MiniLM-L6-v2` (384 dimensions, legacy)
- `all-mpnet-base-v2` (768 dimensions, legacy)

### Adjusting Retrieval

Modify retrieval parameters:
```bash
# Adjust number of retrieved chunks
python main.py query --question "Your question" --top-k 10

# Enable/disable features in config.py
HYDE_ENABLED=true  # Enable Hypothetical Document Embeddings
MMR_LAMBDA=0.5     # Adjust diversity vs relevance (0.0-1.0)
```

### Discord Bot Commands

- `/rag <question>` - Query documents with RAG
- `/upload <file>` - Upload and process documents
- `/chat <message>` - General conversation
- `/clear` - Clear conversation history
- `/config` - Configure bot settings

### HTTP API Endpoints

**Memory Server** (`http://localhost:8766`):
- `POST /query` - Query memories
- `POST /store` - Store memory
- `GET /health` - Health check

**Chat Server** (`http://localhost:8767`):
- `POST /chat` - Chat completion
- `POST /query` - RAG query
- `GET /health` - Health check

## Recent Updates

### Project Reorganization
- ✅ Organized project structure (tests/, scripts/, docs/ directories)
- ✅ Improved import paths and module organization
- ✅ Better separation of concerns

### Performance Improvements
- ✅ Upgraded to BGE-base-en-v1.5 embeddings (768 dimensions, 2-3x better retrieval)
- ✅ Fixed Elasticsearch k-NN compatibility issues
- ✅ Increased image generation timeout to 15 minutes
- ✅ Improved agentic mode timeout handling with local fallback
- ✅ Refactored Discord bot to TypeScript with HTTP A2A communication, tool_calls handling, and enhanced thinking messages
- ✅ Updated .gitignore to exclude secret .env files from the refactored bot

### Feature Enhancements
- ✅ FLUX GGUF image generation workflow
- ✅ Enhanced tool calling and execution
- ✅ Improved LLM response formatting
- ✅ Better error handling and resilience

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                    Discord Bot (Node.js)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ GopherAgent  │  │ RAG Service  │  │ Chat Service │ │
│  │ (Routing)    │  │ (Persistent) │  │ (Persistent) │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└───────────────────────┬─────────────────────────────────┘
                        │ JSON-RPC (stdin/stdout)
┌───────────────────────┴─────────────────────────────────┐
│              Python RAG System                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ ReAct Agent  │  │ Enhanced RAG │  │ Tool Executor│  │
│  │ (Agentic)    │  │ Pipeline     │  │ (LLM Tools)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Memory Store │  │ Document     │  │ Embedding    │  │
│  │ (Intelligent)│  │ Store        │  │ Generator    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└───────────┬───────────────────────────────┬──────────────┘
            │                               │
    ┌───────┴───────┐               ┌───────┴───────┐
    │    Neo4j      │               │ Elasticsearch │
    │ (Vector DB +  │               │  (Hybrid)     │
    │  Graph DB)    │               │  (Optional)   │
    └───────────────┘               └───────────────┘
```

### Key Design Patterns

- **Persistent Services**: Long-running Python processes for fast communication
- **JSON-RPC**: Efficient stdin/stdout protocol for inter-process communication
- **Hybrid Architecture**: Neo4j for graph + vectors, Elasticsearch for hybrid search
- **Multi-Agent System**: Specialized agents for different task types
- **Tool Ecosystem**: Extensible tool calling framework
- **Resilience**: Circuit breakers, retries, timeouts, graceful degradation

## Documentation

See the `docs/` directory for detailed documentation:
- `docs/QUICK_START.md` - Quick start guide
- `docs/COMMANDS_REFERENCE.md` - Complete commands reference
- `docs/GOPHER_AGENT.md` - Gopher agent documentation
- `docs/TOOL_CALLING.md` - Tool calling system
- `docs/MULTI_AGENT_REFLECTION.md` - Multi-agent patterns
- `docs/LLM_PROVIDERS.md` - LLM provider configuration
- `docs/HTTP_SERVERS.md` - HTTP API documentation
- `docs/upgrades/` - Upgrade guides and changelogs
- `docs/assessments/` - Technical assessments

## License

This project is provided as-is for personal use.

## Contributing

Feel free to modify and extend this system for your needs! The codebase is well-organized and documented for easy customization.
