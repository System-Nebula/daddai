# Quick Integration Guide - Enhanced RAG System

## Quick Start

### Option 1: Use Enhanced Pipeline Directly (Recommended)

Simply replace `RAGPipeline` with `EnhancedRAGPipeline` in your code:

```python
# Old code
from rag_pipeline import RAGPipeline
pipeline = RAGPipeline()

# New code
from enhanced_rag_pipeline import EnhancedRAGPipeline
pipeline = EnhancedRAGPipeline()
```

That's it! The enhanced pipeline is a drop-in replacement that automatically uses all improvements.

### Option 2: Gradual Integration

You can integrate components individually:

```python
from rag_pipeline import RAGPipeline
from intelligent_memory import IntelligentMemory
from user_relations import UserRelations

# Use base pipeline
pipeline = RAGPipeline()

# Add intelligent memory
intelligent_memory = IntelligentMemory()

# Add user relations
user_relations = UserRelations()
```

## Discord Bot Integration

Update your Discord bot's RAG service:

```python
# In discord-bot/src/ragServicePersistent.js or similar
# Update the Python script call to use enhanced_rag_pipeline.py

# Or update rag_api.py to use EnhancedRAGPipeline
```

### Update `rag_api.py`:

```python
# Change this line:
from rag_pipeline import RAGPipeline

# To this:
from enhanced_rag_pipeline import EnhancedRAGPipeline as RAGPipeline

# Everything else stays the same!
```

## Key Features Now Available

### 1. User Context Awareness

The system now automatically:
- Tracks user preferences
- Remembers user relationships
- Identifies user expertise
- Personalizes responses

### 2. Smarter Memory Management

Memories are now:
- Scored by importance
- Automatically consolidated
- Archived when old/unimportant
- Retrieved with context awareness

### 3. Better Query Understanding

Queries are now:
- Analyzed with LLM (when available)
- Rewritten for better retrieval
- Enhanced with entity extraction
- Optimized for retrieval strategy

### 4. Enhanced Document Search

Document search now:
- Uses multi-stage retrieval
- Re-ranks results
- Ensures diversity
- Provides document-level context

### 5. Knowledge Graph

The system now tracks:
- Document relationships
- User-document interactions
- Topic clusters
- Entity relationships

## Example Usage

### Basic Query

```python
from enhanced_rag_pipeline import EnhancedRAGPipeline

pipeline = EnhancedRAGPipeline()

result = pipeline.query(
    question="What is the project status?",
    channel_id="123456789",
    user_id="987654321",
    username="JohnDoe"
)

print(result["answer"])
```

### Query with User Mention

```python
result = pipeline.query(
    question="How many gold pieces does @alexei have?",
    channel_id="123456789",
    user_id="987654321",
    username="JohnDoe",
    mentioned_user_id="111222333"  # Alexei's ID
)
```

### Query Specific Document

```python
result = pipeline.query(
    question="What are the key points?",
    channel_id="123456789",
    user_id="987654321",
    doc_filename="project_plan.pdf"
)
```

## Maintenance Tasks

### Periodic Memory Consolidation

Run this periodically (e.g., daily cron job):

```python
from intelligent_memory import IntelligentMemory

memory = IntelligentMemory()

# Consolidate similar memories
for channel_id in channel_ids:
    consolidations = memory.consolidate_similar_memories(
        channel_id=channel_id,
        similarity_threshold=0.85,
        max_age_days=7
    )
    print(f"Consolidated {len(consolidations)} memory groups in {channel_id}")

# Archive old memories
archived = memory.archive_old_memories(
    channel_id=channel_id,
    max_age_days=90,
    min_importance=0.2
)
print(f"Archived {archived} memories")
```

### Close Inactive Threads

```python
from conversation_threading import ConversationThreading

threading = ConversationThreading()
closed = threading.close_inactive_threads(max_inactivity_hours=24)
print(f"Closed {closed} inactive threads")
```

## Performance Tips

1. **Caching**: All components use caching - no changes needed
2. **Connection Pooling**: Neo4j connections are pooled automatically
3. **Parallel Processing**: Multi-stage retrieval uses parallel execution
4. **Lazy Loading**: Components initialize only when needed

## Troubleshooting

### If LLM is unavailable:
- System automatically falls back to pattern-based analysis
- All features still work, just without LLM enhancements

### If Neo4j is slow:
- Check connection pool settings in `config.py`
- Consider increasing `NEO4J_MAX_CONNECTION_POOL_SIZE`

### Memory consolidation taking too long:
- Run it during off-peak hours
- Increase `similarity_threshold` to consolidate fewer memories
- Reduce `max_age_days` to process fewer memories

## Next Steps

1. **Test the enhanced pipeline** with your existing queries
2. **Monitor performance** - check if response times are acceptable
3. **Review memory consolidation** - check if memories are being consolidated appropriately
4. **Adjust thresholds** - fine-tune importance scores, similarity thresholds, etc.

## Rollback

If you need to rollback, simply change back to the original pipeline:

```python
from rag_pipeline import RAGPipeline
pipeline = RAGPipeline()
```

All your data remains in Neo4j - the enhanced components just add additional features.

