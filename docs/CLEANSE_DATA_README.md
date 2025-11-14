# Data Cleansing Script

## Overview

The `cleanse_all_data.py` script provides comprehensive data cleansing to ensure no old/stale data is retrieved. It clears:

- ✅ All Neo4j data (documents, chunks, memories, channels, users, relationships)
- ✅ Vector indexes (will be recreated automatically)
- ✅ Python cache files (`__pycache__`)
- ✅ Discord bot logs and temp files
- ✅ Provides verification to ensure everything is cleared

## Why Use This Script?

If you're experiencing issues with old data being retrieved:
- Stale documents appearing in search results
- Old memories being used in responses
- Cached data causing incorrect results
- After major system changes or migrations

## Usage

### Interactive Mode (Recommended)

```bash
python cleanse_all_data.py
```

You'll be prompted to type `DELETE ALL DATA` to confirm.

### Non-Interactive Mode (Use with Caution!)

```bash
python cleanse_all_data.py --yes
```

### Options

```bash
# Skip verification after deletion
python cleanse_all_data.py --yes --no-verify

# Only clear Neo4j data (skip cache clearing)
python cleanse_all_data.py --yes --neo4j-only

# Only clear caches (skip Neo4j data)
python cleanse_all_data.py --yes --cache-only
```

### Windows

```bash
cleanse_all_data.bat
```

### Linux/Mac

```bash
chmod +x cleanse_all_data.sh
./cleanse_all_data.sh
```

## What Gets Deleted

### Neo4j Database
- **SharedDocument** nodes (all shared documents)
- **SharedChunk** nodes (all shared document chunks)
- **Document** nodes (all personal documents)
- **Chunk** nodes (all personal document chunks)
- **Memory** nodes (all conversation memories)
- **Channel** nodes (all Discord channels)
- **User** nodes (all Discord users)
- **All relationships** between nodes
- **Vector indexes** (will be recreated automatically)

### Cache Files
- Python `__pycache__` directories
- Discord bot log files
- Discord bot temp files

### In-Memory Caches
- RAG pipeline query caches (cleared on restart)
- Embedding caches (cleared on restart)

## Verification

The script automatically verifies that all data has been deleted. You'll see output like:

```
✓ Verification passed: All data cleared
```

If any data remains, you'll see warnings:

```
⚠ Verification warning: Some data remains:
  - documents: 5 remaining
```

## After Running the Script

1. **Restart the Discord bot** to clear in-memory caches:
   ```bash
   cd discord-bot
   npm start
   ```

2. **Restart the RAG server** (if running separately):
   ```bash
   python rag_server.py
   ```

3. **Re-upload documents** you need:
   - Use `/upload` command in Discord
   - Or use `python main.py ingest --path <file_or_directory>`

## Safety Features

- ✅ Requires explicit confirmation (`DELETE ALL DATA`)
- ✅ Verification step to ensure deletion worked
- ✅ Comprehensive logging of all operations
- ✅ Error handling with rollback on failure
- ✅ Can skip verification with `--no-verify` flag

## Example Output

```
======================================================================
COMPREHENSIVE DATA CLEANSING SCRIPT
======================================================================

⚠️  WARNING: This will delete:
   - ALL documents (SharedDocument and Document)
   - ALL chunks (SharedChunk and Chunk)
   - ALL memories
   - ALL channels
   - ALL users
   - ALL relationships
   - Vector indexes
   - Python cache files (__pycache__)
   - Discord bot logs and temp files

This action CANNOT be undone!

Type 'DELETE ALL DATA' to confirm: DELETE ALL DATA

======================================================================
CLEARING NEO4J DATA
======================================================================
Connecting to Neo4j...
Starting data deletion...
Deleting all relationships...
  ✓ Deleted 1523 relationships
Deleting SharedChunk nodes...
  ✓ Deleted 450 SharedChunk nodes
Deleting SharedDocument nodes...
  ✓ Deleted 12 SharedDocument nodes
Deleting Chunk nodes...
  ✓ Deleted 230 Chunk nodes
Deleting Document nodes...
  ✓ Deleted 5 Document nodes
Deleting Memory nodes...
  ✓ Deleted 89 Memory nodes
Deleting Channel nodes...
  ✓ Deleted 3 Channel nodes
Deleting User nodes...
  ✓ Deleted 15 User nodes
Dropping vector indexes...
  ✓ Dropped document_embeddings index
  ✓ Dropped memory_embeddings index
Verifying deletion...
  ✓ Verification passed: All data cleared

✅ Data deletion complete!
   Total items deleted: 2331

======================================================================
CLEARING CACHES
======================================================================
Clearing Python cache files...
  ✓ Cleared __pycache__
Clearing Discord bot cache...
  ✓ Cleared files in discord-bot/logs
  ✓ Cleared Discord bot cache
Clearing RAG pipeline caches...
  Note: In-memory caches (query_embedding_cache, query_result_cache)
        will be cleared when the RAG pipeline is restarted.
  ✓ RAG cache clearing instructions logged

======================================================================
✅ DATA CLEANSING COMPLETE!
======================================================================

Next steps:
  1. Restart the Discord bot to clear in-memory caches
  2. Restart the RAG server to clear query caches
  3. Re-upload any documents you need
```

## Troubleshooting

### "Connection refused" error
- Make sure Neo4j is running
- Check your Neo4j connection settings in `.env` or `config.py`

### "Permission denied" error
- Make sure you have write permissions for cache directories
- Run with appropriate permissions if needed

### Data still appears after cleansing
- Restart the Discord bot and RAG server
- Check if you're querying a different Neo4j instance
- Verify Neo4j connection settings

## Related Scripts

- `clear_all_data.py` - Simpler script (Neo4j only, no cache clearing)
- `clear_memories.py` - Only clears memories (keeps documents)

## Notes

- Vector indexes will be automatically recreated when you next use the system
- The script uses proper logging (see `logs/` directory)
- All operations are logged for audit purposes
- The script is safe to run multiple times (idempotent)

