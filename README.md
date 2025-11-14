# Self-Hosted RAG System with Docling, Neo4j, and LMStudio

A complete Retrieval-Augmented Generation (RAG) system that runs entirely on your home system. This system uses:
- **Docling**: For processing and extracting content from various document formats
- **Neo4j**: For storing document embeddings and building a knowledge graph
- **LMStudio**: For running local language models
- **Sentence Transformers**: For generating embeddings locally

## Features

- 📄 Process PDFs, Word documents, and text files using Docling
- 🔍 Vector similarity search using Neo4j's vector index
- 🤖 Query local LLM models via LMStudio API
- 🏠 Fully self-hosted - no cloud dependencies
- 🔗 Knowledge graph storage in Neo4j
- 🚀 **GPU acceleration** for fast embedding generation (optimized for RTX 3080)
- ⚡ **Batch processing** for efficient document ingestion

## Prerequisites

1. **Neo4j**: Install and run Neo4j locally
   - Download from [neo4j.com/download](https://neo4j.com/download/)
   - Start Neo4j and note your connection details (default: bolt://localhost:7687)
   - Username: `neo4j`, Password: (set during installation)
   - **Note**: Vector index support requires Neo4j 5.x+. If not available, the system will automatically fall back to cosine similarity calculation.

2. **LMStudio**: Install and run LMStudio
   - Download from [lmstudio.ai](https://lmstudio.ai/)
   - Start LMStudio and load a model
   - Ensure the local server is running (default: http://localhost:1234)

3. **Python 3.8+**: Required for running the scripts

4. **NVIDIA GPU (Recommended)**: RTX 3080 or similar for GPU acceleration
   - CUDA-compatible GPU with 8GB+ VRAM recommended
   - PyTorch with CUDA support will be installed automatically
   - System will automatically detect and use GPU if available

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

3. Set up environment variables (optional, defaults are provided):
Create a `.env` file in the project root:
```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_MODEL=local-model

EMBEDDING_MODEL=all-MiniLM-L6-v2

# GPU Configuration (optional - auto-detected by default)
USE_GPU=auto  # 'auto', 'cuda', or 'cpu'
EMBEDDING_BATCH_SIZE=64  # Batch size for GPU processing (64 for RTX 3080)
```

## Quick Start

1. **Start Neo4j**: Ensure Neo4j is running on your system
2. **Start LMStudio**: Launch LMStudio, load a model, and ensure the local server is running
3. **Ingest documents**: Process your documents into the system
4. **Query**: Ask questions about your documents

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
├── document_processor.py   # Docling-based document processing
├── embedding_generator.py  # Sentence transformer embeddings
├── neo4j_store.py         # Neo4j integration and storage
├── lmstudio_client.py     # LMStudio API client
├── rag_pipeline.py        # Complete RAG pipeline
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## How It Works

1. **Document Processing**: Docling extracts text and structure from documents
2. **Chunking**: Documents are split into manageable chunks with overlap
3. **Embedding**: Each chunk is converted to a vector embedding using sentence transformers
4. **Storage**: Chunks and embeddings are stored in Neo4j with vector indexing
5. **Query**: User questions are embedded and used to find similar chunks
6. **Generation**: Retrieved context is sent to LMStudio for answer generation

## Configuration

Edit `config.py` or set environment variables to customize:

- **Chunking**: `CHUNK_SIZE` and `CHUNK_OVERLAP`
- **Embedding Model**: Change `EMBEDDING_MODEL` to use different sentence transformer models
- **Neo4j**: Connection details
- **LMStudio**: API URL and model name

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

## GPU Optimization (RTX 3080)

The system is optimized for RTX 3080 and will automatically:
- ✅ Detect and use GPU for embedding generation
- ✅ Use batch size of 64 for optimal GPU utilization
- ✅ Normalize embeddings for better cosine similarity
- ✅ Show GPU status during processing

**Performance Expectations on RTX 3080:**
- Embedding generation: ~1000-2000 chunks/second
- Document ingestion: Processes large documents in seconds
- Query response: Near-instant retrieval + LMStudio generation time

**Manual GPU Configuration:**
If you want to force CPU or specify GPU settings, edit `.env`:
```env
USE_GPU=cuda  # Force GPU
# or
USE_GPU=cpu   # Force CPU
EMBEDDING_BATCH_SIZE=128  # Increase if you have more VRAM
```

## Advanced Usage

### Custom Embedding Models

You can use different sentence transformer models by changing `EMBEDDING_MODEL` in `config.py`:
- `all-MiniLM-L6-v2` (default, 384 dimensions, fast)
- `all-mpnet-base-v2` (768 dimensions, more accurate)
- `paraphrase-multilingual-MiniLM-L12-v2` (multilingual support)

### Adjusting Retrieval

Modify `top_k` parameter when querying to retrieve more or fewer chunks:
```bash
python main.py query --question "Your question" --top-k 10
```

## License

This project is provided as-is for personal use.

## Contributing

Feel free to modify and extend this system for your needs!
# Self-Hosted RAG System with Docling, Neo4j, and LMStudio

A complete Retrieval-Augmented Generation (RAG) system that runs entirely on your home system. This system uses:
- **Docling**: For processing and extracting content from various document formats
- **Neo4j**: For storing document embeddings and building a knowledge graph
- **LMStudio**: For running local language models
- **Sentence Transformers**: For generating embeddings locally

## Features

- 📄 Process PDFs, Word documents, and text files using Docling
- 🔍 Vector similarity search using Neo4j's vector index
- 🤖 Query local LLM models via LMStudio API
- 🏠 Fully self-hosted - no cloud dependencies
- 🔗 Knowledge graph storage in Neo4j
- 🚀 **GPU acceleration** for fast embedding generation (optimized for RTX 3080)
- ⚡ **Batch processing** for efficient document ingestion

## Prerequisites

1. **Neo4j**: Install and run Neo4j locally
   - Download from [neo4j.com/download](https://neo4j.com/download/)
   - Start Neo4j and note your connection details (default: bolt://localhost:7687)
   - Username: `neo4j`, Password: (set during installation)
   - **Note**: Vector index support requires Neo4j 5.x+. If not available, the system will automatically fall back to cosine similarity calculation.

2. **LMStudio**: Install and run LMStudio
   - Download from [lmstudio.ai](https://lmstudio.ai/)
   - Start LMStudio and load a model
   - Ensure the local server is running (default: http://localhost:1234)

3. **Python 3.8+**: Required for running the scripts

4. **NVIDIA GPU (Recommended)**: RTX 3080 or similar for GPU acceleration
   - CUDA-compatible GPU with 8GB+ VRAM recommended
   - PyTorch with CUDA support will be installed automatically
   - System will automatically detect and use GPU if available

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

3. Set up environment variables (optional, defaults are provided):
Create a `.env` file in the project root:
```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_MODEL=local-model

EMBEDDING_MODEL=all-MiniLM-L6-v2

# GPU Configuration (optional - auto-detected by default)
USE_GPU=auto  # 'auto', 'cuda', or 'cpu'
EMBEDDING_BATCH_SIZE=64  # Batch size for GPU processing (64 for RTX 3080)
```

## Quick Start

1. **Start Neo4j**: Ensure Neo4j is running on your system
2. **Start LMStudio**: Launch LMStudio, load a model, and ensure the local server is running
3. **Ingest documents**: Process your documents into the system
4. **Query**: Ask questions about your documents

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
├── document_processor.py   # Docling-based document processing
├── embedding_generator.py  # Sentence transformer embeddings
├── neo4j_store.py         # Neo4j integration and storage
├── lmstudio_client.py     # LMStudio API client
├── rag_pipeline.py        # Complete RAG pipeline
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## How It Works

1. **Document Processing**: Docling extracts text and structure from documents
2. **Chunking**: Documents are split into manageable chunks with overlap
3. **Embedding**: Each chunk is converted to a vector embedding using sentence transformers
4. **Storage**: Chunks and embeddings are stored in Neo4j with vector indexing
5. **Query**: User questions are embedded and used to find similar chunks
6. **Generation**: Retrieved context is sent to LMStudio for answer generation

## Configuration

Edit `config.py` or set environment variables to customize:

- **Chunking**: `CHUNK_SIZE` and `CHUNK_OVERLAP`
- **Embedding Model**: Change `EMBEDDING_MODEL` to use different sentence transformer models
- **Neo4j**: Connection details
- **LMStudio**: API URL and model name

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

## GPU Optimization (RTX 3080)

The system is optimized for RTX 3080 and will automatically:
- ✅ Detect and use GPU for embedding generation
- ✅ Use batch size of 64 for optimal GPU utilization
- ✅ Normalize embeddings for better cosine similarity
- ✅ Show GPU status during processing

**Performance Expectations on RTX 3080:**
- Embedding generation: ~1000-2000 chunks/second
- Document ingestion: Processes large documents in seconds
- Query response: Near-instant retrieval + LMStudio generation time

**Manual GPU Configuration:**
If you want to force CPU or specify GPU settings, edit `.env`:
```env
USE_GPU=cuda  # Force GPU
# or
USE_GPU=cpu   # Force CPU
EMBEDDING_BATCH_SIZE=128  # Increase if you have more VRAM
```

## Advanced Usage

### Custom Embedding Models

You can use different sentence transformer models by changing `EMBEDDING_MODEL` in `config.py`:
- `all-MiniLM-L6-v2` (default, 384 dimensions, fast)
- `all-mpnet-base-v2` (768 dimensions, more accurate)
- `paraphrase-multilingual-MiniLM-L12-v2` (multilingual support)

### Adjusting Retrieval

Modify `top_k` parameter when querying to retrieve more or fewer chunks:
```bash
python main.py query --question "Your question" --top-k 10
```

## License

This project is provided as-is for personal use.

## Contributing

Feel free to modify and extend this system for your needs!
