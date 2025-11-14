# Quick Start Guide

## Prerequisites

1. **Neo4j** - Running on `bolt://localhost:7687`
2. **LMStudio** - Running with a model loaded on `http://localhost:1234`
3. **Python 3.8+** with dependencies installed
4. **Node.js** (for Discord bot, optional)

## Installation

```bash
# Install Python dependencies
pip install -r requirements.txt
```

## Running the RAG System

### 1. Ingest Documents

```bash
# Process a single file
python main.py ingest --path path/to/document.pdf

# Process all documents in a directory
python main.py ingest --path path/to/documents/
```

Supported formats: PDF, DOCX, DOC, TXT, MD, CSV, JSON, IPYNB

### 2. Query the System

#### Single Query
```bash
python main.py query --question "What is the main topic of the documents?"
```

#### Interactive Mode (Recommended)
```bash
python main.py interactive
```

This starts an interactive session where you can ask multiple questions. Type `exit` or `quit` to stop.

### 3. Advanced Query Options

```bash
# Retrieve more chunks
python main.py query --question "Your question" --top-k 20
```

## Running the Discord Bot (Optional)

### Setup

1. Navigate to discord-bot directory:
```bash
cd discord-bot
```

2. Install Node.js dependencies:
```bash
npm install
```

3. Create `.env` file:
```env
DISCORD_TOKEN=your_discord_bot_token_here
PYTHON_PATH=python
DEBUG=false
```

4. Start the bot:
```bash
npm start
```

The bot will automatically start the RAG server and be ready to answer questions.

## Running the RAG Server (Standalone)

For persistent RAG server (used by Discord bot):

```bash
python src/api/rag_server.py
```

This starts a persistent server that handles multiple requests efficiently.

## Running Individual APIs

### Document API
```bash
python src/api/document_api.py --action list
python src/api/document_api.py --action upload --file path/to/file.pdf
```

### Memory API
```bash
python src/api/memory_api.py --action list --user-id user123
python src/api/memory_api.py --action add --user-id user123 --content "User likes Python"
```

### Chat API
```bash
python src/api/chat_api.py --message "Hello, how are you?"
```

### Search API
```bash
python src/api/search_api.py --query "search term" --store documents --top-k 10
```

## Utility Scripts

All utility scripts are in the `scripts/` directory:

```bash
# Setup Neo4j
python scripts/setup_neo4j.py

# List all documents
python scripts/list_all_documents.py

# Clear all data (use with caution!)
python scripts/clear_all_documents_and_memories.py

# Migrate to Elasticsearch
python scripts/migrate_to_elasticsearch.py
```

## Configuration

Edit `config.py` or create a `.env` file in the project root:

```env
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# LMStudio
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_MODEL=local-model

# Embedding
EMBEDDING_MODEL=all-MiniLM-L6-v2
USE_GPU=auto
EMBEDDING_BATCH_SIZE=64

# RAG Settings
RAG_TOP_K=10
RAG_TEMPERATURE=0.7
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

## Troubleshooting

### Import Errors
If you see import errors, make sure you're running from the project root directory:
```bash
cd C:\Users\jovan\OneDrive\Desktop\docling
python main.py query --question "test"
```

### Neo4j Connection Issues
- Ensure Neo4j is running
- Check connection details in `config.py` or `.env`
- Test connection: `cypher-shell -u neo4j -p your_password`

### LMStudio Connection Issues
- Ensure LMStudio is running with a model loaded
- Check that local server is enabled in LMStudio settings
- Verify API URL: `http://localhost:1234/v1`

### Discord Bot Issues
- Make sure Python RAG system works first: `python main.py query --question "test"`
- Check that `PYTHON_PATH` in `.env` points to correct Python executable
- Verify Discord bot token is correct

## Example Workflow

1. **Start services:**
   ```bash
   # Terminal 1: Start Neo4j (if not running as service)
   # Terminal 2: Start LMStudio and load a model
   ```

2. **Ingest documents:**
   ```bash
   python main.py ingest --path documents/
   ```

3. **Query:**
   ```bash
   python main.py interactive
   # Then ask questions interactively
   ```

4. **Or use Discord bot:**
   ```bash
   cd discord-bot
   npm start
   # Then use /rag command in Discord
   ```

