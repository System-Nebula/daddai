# Action and State Management Guide

## Overview

The enhanced RAG system now understands actions, tracks user state, and knows when to search documents vs when not to. This guide explains how these features work.

## Key Features

### 1. **Action Parsing and Execution**

The system can parse and execute commands like:
- `give @alexei 20 gold pieces` - Transfers 20 gold from you to Alexei
- `give @alexei a sword` - Transfers a sword from your inventory to Alexei
- `set @alexei level to 10` - Sets Alexei's level to 10
- `add 50 gold to @alexei` - Adds 50 gold to Alexei's balance

### 2. **State Tracking**

The system tracks:
- **Gold/Coins**: Numeric currency values
- **Inventory**: Items and quantities
- **Custom State**: Any key-value pairs (level, stats, etc.)

### 3. **State Queries**

Users can ask about their state:
- `how much gold do I have?` - Returns your gold balance
- `how much gold does @alexei have?` - Returns Alexei's gold balance
- `what is my inventory?` - Returns your inventory
- `what is @alexei's balance?` - Returns Alexei's state summary

### 4. **Smart Document Selection**

The system automatically determines:
- **When to search documents**: Only for informational queries, not casual conversation or state queries
- **Which documents to search**: Based on query relevance, user history, and document topics

## How It Works

### Action Flow

1. **User sends**: `give @alexei 20 gold pieces`
2. **System parses**: Extracts action="give", target="@alexei", item="gold", quantity=20
3. **System executes**: 
   - Transfers 20 gold from your account to Alexei's
   - Updates both users' state
   - Tracks the relationship (you gave gold to Alexei)
   - Stores action in memory
4. **System responds**: "Gave 20 gold to @alexei. They now have X gold."

### State Query Flow

1. **User sends**: `how much gold does @alexei have?`
2. **System detects**: This is a state query (not a document query)
3. **System retrieves**: Alexei's gold balance from state database
4. **System responds**: "@alexei has 20 gold pieces." (no document search needed)

### Document Search Flow

1. **User sends**: `what are the key points in the project plan?`
2. **System detects**: This needs document search
3. **System selects**: Relevant documents (e.g., "project_plan.pdf")
4. **System searches**: Only selected documents
5. **System responds**: Based on document content

## Examples

### Example 1: Giving Gold

```
User: give @alexei 20 gold pieces
Bot: Gave 20 gold to @alexei. They now have 20 gold.

User: how much gold does @alexei have?
Bot: @alexei has 20 gold pieces.
```

### Example 2: Inventory Management

```
User: give @alexei a sword
Bot: Gave 1 sword(s) to @alexei.

User: what is @alexei's inventory?
Bot: @alexei's inventory: 1 sword.
```

### Example 3: State Queries Don't Search Documents

```
User: how much gold do I have?
Bot: You have 100 gold pieces.
(No document search performed - faster response)
```

### Example 4: Document Queries Do Search Documents

```
User: what are the key points in project_plan.pdf?
Bot: [Searches project_plan.pdf and returns answer based on document]
```

## Supported Actions

### Give
- `give @user 20 gold pieces`
- `give @user a sword`
- `give 20 gold pieces to @user`

### Set
- `set @user level to 10`
- `set level to 10 for @user`

### Add
- `add 50 gold to @user`
- `add a potion to @user`

### Take (Future)
- `take 10 gold from @user`
- `take a sword from @user`

## State Keys

Common state keys:
- `gold` - Gold pieces balance
- `coins` - Coins balance
- `silver` - Silver pieces balance
- `inventory` - Dictionary of items and quantities
- `level` - User level
- Custom keys can be set with `set` action

## User Relations

When actions are performed, the system automatically:
- Tracks relationships between users
- Records who gave what to whom
- Updates user interaction graphs
- Stores actions in memory for context

## Integration

The enhanced pipeline automatically handles all of this. Just use it normally:

```python
from enhanced_rag_pipeline import EnhancedRAGPipeline

pipeline = EnhancedRAGPipeline()

# Actions are automatically detected and processed
result = pipeline.query(
    question="give @alexei 20 gold pieces",
    user_id="123456789",
    channel_id="987654321",
    username="JohnDoe"
)

# State queries are automatically handled
result = pipeline.query(
    question="how much gold does @alexei have?",
    user_id="123456789",
    mentioned_user_id="111222333"  # Alexei's ID
)
```

## Benefits

1. **Faster Responses**: State queries don't search documents unnecessarily
2. **Accurate State**: State is tracked and persisted correctly
3. **User Relations**: Relationships are automatically tracked
4. **Context Awareness**: System knows who's talking and what they're asking about
5. **Smart Routing**: Only searches documents when needed

## Future Enhancements

Potential future improvements:
- More action types (take, trade, etc.)
- Complex state queries (comparisons, aggregations)
- State validation and constraints
- State history and rollback
- Multi-user transactions

