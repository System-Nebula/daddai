# Agentic Discord Bot Design

## Overview

This document outlines the design for making the Discord bot more agentic and LLM-controlled while maintaining safety and performance.

## Current State

### Pattern-Based Detection (Current)
- ✅ Detects attachments → document upload
- ✅ Detects mentions → respond
- ✅ Detects question marks → respond
- ❌ Misses implicit requests
- ❌ Doesn't understand context
- ❌ Can't handle multi-turn conversations well

### LLM-Controlled Detection (Proposed)
- ✅ Understands intent and context
- ✅ Handles implicit requests
- ✅ Better multi-turn conversation support
- ⚠️ Higher latency/cost
- ⚠️ Requires careful prompt engineering

## Architecture

### Hybrid Approach

```
Message Received
    ↓
[Deterministic Checks]
    ├─ Bot message? → Ignore
    ├─ Rate limit exceeded? → Ignore/Reply
    ├─ Channel not allowed? → Ignore
    ├─ Has attachments? → Handle upload (fast path)
    └─ Pass to LLM Classifier
        ↓
[LLM Intent Classifier] (lightweight, cached)
    ├─ Intent: question → Route to RAG
    ├─ Intent: command → Route to command handler
    ├─ Intent: casual → Route to chat
    ├─ Intent: action → Route to action parser
    ├─ Intent: upload → Route to upload handler
    └─ Intent: ignore → Don't respond
        ↓
[Route to Handler]
```

## Implementation Strategy

### Phase 1: Lightweight LLM Classifier

Create a fast, lightweight LLM call that classifies message intent:

```python
def classify_message_intent(message: str, context: dict) -> dict:
    """
    Classify message intent using LLM.
    Returns: {
        "should_respond": bool,
        "intent": str,  # "question", "command", "casual", "action", "upload", "ignore"
        "confidence": float,
        "routing": str  # "rag", "chat", "tools", "memory", "action"
    }
    """
```

**Optimizations:**
- Cache results for similar messages (TTL: 5 minutes)
- Use fast/cheap model for classification
- Batch multiple messages if possible
- Fallback to pattern matching if LLM fails

### Phase 2: Context-Aware Classification

Enhance classifier with conversation context:

```python
def classify_with_context(
    message: str,
    recent_messages: list,
    user_history: dict,
    channel_context: dict
) -> dict:
    """
    Classify with full context awareness.
    """
```

### Phase 3: Full Agentic Behavior

Allow LLM to decide on actions, not just routing:

```python
def agentic_decision(
    message: str,
    context: dict,
    available_actions: list
) -> dict:
    """
    LLM decides what action to take, not just routing.
    Can suggest: respond, ignore, ask_clarification, etc.
    """
```

## Benefits

### 1. Better Intent Detection
- Handles implicit requests: "can you help?" → detects as question
- Understands context: "what about that file?" → references previous message
- Reduces false positives: "I have a question" → doesn't trigger response

### 2. More Natural Interactions
- Responds to conversational cues, not just patterns
- Handles multi-turn conversations better
- Understands user intent even without explicit triggers

### 3. Unified Decision-Making
- Consistent with RAG pipeline's LLM-based routing
- Single source of truth for intent understanding
- Easier to maintain and improve

## Trade-offs

### Pros
- ✅ Better user experience
- ✅ More natural interactions
- ✅ Handles edge cases better
- ✅ Consistent with existing LLM tool calling

### Cons
- ⚠️ Higher latency (adds LLM call)
- ⚠️ Higher cost (more LLM calls)
- ⚠️ More complex error handling
- ⚠️ Requires prompt engineering

## Mitigation Strategies

### 1. Caching
- Cache classification results for similar messages
- Use message hash + context hash as cache key
- TTL: 5 minutes

### 2. Fast Paths
- Keep deterministic checks for obvious cases (attachments)
- Only use LLM for ambiguous cases
- Fallback to pattern matching if LLM fails

### 3. Cost Optimization
- Use cheaper/faster model for classification
- Batch multiple messages if possible
- Only classify messages that pass initial filters

### 4. Latency Optimization
- Async classification (don't block message handling)
- Use streaming/fast models
- Pre-classify common patterns

## Implementation Plan

### Step 1: Create Message Classifier Service
```python
# src/services/message_classifier.py
class MessageClassifier:
    def classify(self, message: str, context: dict) -> dict:
        # Lightweight LLM call
        # Cache results
        # Fallback to patterns
        pass
```

### Step 2: Integrate into Discord Bot
```javascript
// discord-bot/src/messageClassifier.js
class MessageClassifier {
    async classify(message, context) {
        // Call Python service
        // Cache results
        // Return intent
    }
}
```

### Step 3: Update Message Handler
```javascript
// discord-bot/index.js
client.on(Events.MessageCreate, async (message) => {
    // ... existing checks ...
    
    // LLM classification for ambiguous cases
    const intent = await messageClassifier.classify(message.content, {
        hasAttachments: message.attachments.size > 0,
        isMentioned: message.mentions.has(client.user),
        recentMessages: await getRecentMessages(message.channel, 5),
        userHistory: await getUserHistory(message.author.id)
    });
    
    if (intent.should_respond) {
        await routeToHandler(message, intent);
    }
});
```

## Testing Strategy

### 1. Unit Tests
- Test classifier with various message types
- Test caching behavior
- Test fallback to patterns

### 2. Integration Tests
- Test end-to-end message handling
- Test with real Discord messages
- Test performance/latency

### 3. A/B Testing
- Compare pattern-based vs LLM-based detection
- Measure user satisfaction
- Track false positive/negative rates

## Metrics to Track

- Classification accuracy
- Response latency
- Cost per message
- User satisfaction
- False positive/negative rates

## Conclusion

Making the Discord bot more agentic will improve user experience and consistency with the RAG pipeline. The hybrid approach balances benefits with costs, using LLM for intent classification while keeping deterministic checks for safety and performance.

