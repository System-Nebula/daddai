# Refactored Architecture Documentation

## Overview

The refactored codebase implements Smart Agent-to-Agent (A2A) communication, enabling agents to communicate directly, discover each other dynamically, and collaborate on complex tasks.

## Core Components

### 1. BaseAgent

Abstract base class for all agents providing:
- Message handling infrastructure
- Capability registration
- A2A communication methods
- Event subscription

### 2. AgentRegistry

Central registry for agent management:
- Dynamic agent registration/unregistration
- Capability-based agent discovery
- Health monitoring
- Load balancing

### 3. MessageBus

Async message routing system:
- Request/response handling
- Event publishing/subscription
- Message queuing with priorities
- Timeout management

### 4. AgentMessage Protocol

Standardized message format:
- Request/Response/Event/Error types
- Correlation IDs for request/response pairing
- Priority levels
- Timeout configuration

## Agent Communication Patterns

### Direct Communication

Agents send messages directly to other agents:

```python
response = await agent.send_message(
    receiver_id="target_agent",
    action="perform_action",
    payload={"data": "value"}
)
```

### Agent Delegation

Agents delegate tasks based on capabilities:

```python
response = await agent.delegate_to_agent(
    capability_type=CapabilityType.SEARCH,
    action="search",
    payload={"query": "test"}
)
```

### Event Publishing

Agents publish events for subscribers:

```python
await agent.send_event(
    event_type="document_processed",
    payload={"document_id": "123"}
)
```

## Workflow Patterns

### Reflection Pattern

CoordinatorAgent orchestrates:
1. SearchAgent performs search
2. AnalyserAgent generates analysis
3. ReflectionAgent evaluates quality
4. Iterate if quality below threshold

### RAG Workflow

Simple search and retrieval:
1. SearchAgent performs search
2. Return results

## Testing Strategy

### Unit Tests

Test individual components in isolation:
- BaseAgent functionality
- Message protocol
- Registry operations
- Message bus routing

### Integration Tests

Test agent interactions:
- A2A communication
- Agent delegation
- Multi-agent workflows

### E2E Tests

Test complete workflows:
- Full RAG pipeline
- Reflection pattern workflow
- Error handling

## Migration Notes

The refactored codebase:
- Maintains compatibility with original functionality
- Adds A2A communication layer
- Improves separation of concerns
- Enables dynamic agent composition

