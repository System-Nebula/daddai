# RAG System Improvements

## Changes Made to Improve Question Answering

### 1. Increased Retrieval Coverage
- **Default top_k increased**: From 5 to 10 chunks
- **Better context utilization**: Now retrieves more relevant chunks per query

### 2. Improved Context Handling
- **Token-based limits**: Changed from 2000 characters to 3000 tokens (~12,000 characters)
- **Smart chunk selection**: Prioritizes higher-scoring chunks
- **Better filtering**: Filters chunks by similarity score (>0.5 threshold)

### 3. Enhanced Prompting
- **More explicit instructions**: Tells the model to read ALL context carefully
- **Better structure**: Clearer separation between context and question
- **Comprehensive answers**: Encourages detailed, thorough responses

### 4. Better Chunking Strategy
- **Sentence-based chunking**: Respects sentence boundaries instead of arbitrary word counts
- **Better semantic coherence**: Chunks are more meaningful units
- **Improved overlap**: Better overlap between chunks for context continuity

## Important: Re-ingest Your Documents

**The document you already ingested was processed with the old chunking method.**

To get the full benefits of these improvements, you should re-ingest your documents:

```bash
# First, delete the old document (optional - or just re-ingest to update)
python -c "from neo4j_store import Neo4jStore; store = Neo4jStore(); store.delete_document('doc_CodexSpaceMarines.pdf'); store.close()"

# Then re-ingest with improved chunking
python main.py ingest --path "C:\Users\jovan\OneDrive\Desktop\TestDocs\CodexSpaceMarines.pdf"
```

## Additional Tips for Better Results

### Adjust Retrieval Parameters
- **More chunks**: Use `--top-k 15` or `--top-k 20` for complex questions
- **Lower similarity threshold**: If missing information, the threshold is in `rag_pipeline.py` (line 51)

### Fine-tune Chunk Size
Edit `.env` or `config.py`:
```env
CHUNK_SIZE=800    # Smaller chunks = more granular retrieval
CHUNK_OVERLAP=150 # Overlap between chunks
```

### Query Tips
- **Be specific**: More specific questions get better results
- **Ask follow-ups**: Break complex questions into parts
- **Use keywords**: Include important terms from your document

## Current Configuration

- **Retrieval**: 10 chunks by default (can increase with `--top-k`)
- **Context limit**: ~3000 tokens (~12,000 characters)
- **Similarity threshold**: 0.5 (chunks below this are filtered)
- **Chunk size**: 1000 words (sentence-based)
- **Chunk overlap**: 200 words

## Testing

Try these queries to test the improvements:
```bash
python main.py query --question "What are the different Space Marine Chapters?" --top-k 15
python main.py query --question "What equipment do Space Marines use?" --top-k 10
python main.py query --question "How are Space Marines organized?" --top-k 12
```

# RAG System Improvements

## Changes Made to Improve Question Answering

### 1. Increased Retrieval Coverage
- **Default top_k increased**: From 5 to 10 chunks
- **Better context utilization**: Now retrieves more relevant chunks per query

### 2. Improved Context Handling
- **Token-based limits**: Changed from 2000 characters to 3000 tokens (~12,000 characters)
- **Smart chunk selection**: Prioritizes higher-scoring chunks
- **Better filtering**: Filters chunks by similarity score (>0.5 threshold)

### 3. Enhanced Prompting
- **More explicit instructions**: Tells the model to read ALL context carefully
- **Better structure**: Clearer separation between context and question
- **Comprehensive answers**: Encourages detailed, thorough responses

### 4. Better Chunking Strategy
- **Sentence-based chunking**: Respects sentence boundaries instead of arbitrary word counts
- **Better semantic coherence**: Chunks are more meaningful units
- **Improved overlap**: Better overlap between chunks for context continuity

## Important: Re-ingest Your Documents

**The document you already ingested was processed with the old chunking method.**

To get the full benefits of these improvements, you should re-ingest your documents:

```bash
# First, delete the old document (optional - or just re-ingest to update)
python -c "from neo4j_store import Neo4jStore; store = Neo4jStore(); store.delete_document('doc_CodexSpaceMarines.pdf'); store.close()"

# Then re-ingest with improved chunking
python main.py ingest --path "C:\Users\jovan\OneDrive\Desktop\TestDocs\CodexSpaceMarines.pdf"
```

## Additional Tips for Better Results

### Adjust Retrieval Parameters
- **More chunks**: Use `--top-k 15` or `--top-k 20` for complex questions
- **Lower similarity threshold**: If missing information, the threshold is in `rag_pipeline.py` (line 51)

### Fine-tune Chunk Size
Edit `.env` or `config.py`:
```env
CHUNK_SIZE=800    # Smaller chunks = more granular retrieval
CHUNK_OVERLAP=150 # Overlap between chunks
```

### Query Tips
- **Be specific**: More specific questions get better results
- **Ask follow-ups**: Break complex questions into parts
- **Use keywords**: Include important terms from your document

## Current Configuration

- **Retrieval**: 10 chunks by default (can increase with `--top-k`)
- **Context limit**: ~3000 tokens (~12,000 characters)
- **Similarity threshold**: 0.5 (chunks below this are filtered)
- **Chunk size**: 1000 words (sentence-based)
- **Chunk overlap**: 200 words

## Testing

Try these queries to test the improvements:
```bash
python main.py query --question "What are the different Space Marine Chapters?" --top-k 15
python main.py query --question "What equipment do Space Marines use?" --top-k 10
python main.py query --question "How are Space Marines organized?" --top-k 12
```

