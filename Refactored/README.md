# Refactored Codebase with Smart A2A Communication

This is the refactored version of the codebase with Smart Agent-to-Agent (A2A) communication capabilities.

## Architecture

### Smart A2A Communication

The refactored system implements a comprehensive A2A communication framework:

1. **BaseAgent**: Abstract base class for all agents with communication capabilities
2. **AgentRegistry**: Dynamic agent discovery and registration
3. **MessageBus**: Async message routing and event handling
4. **AgentMessage**: Standardized message protocol

### Key Features

- **Direct Agent Communication**: Agents can send messages directly to each other
- **Dynamic Agent Discovery**: Agents register capabilities and can be discovered dynamically
- **Agent Delegation**: Agents can delegate tasks to other agents based on capabilities
- **Event-Driven Architecture**: Agents can publish and subscribe to events

## Agents

### Refactored Agents

- **SearchAgent**: Performs hybrid search, extends BaseAgent
- **AnalyserAgent**: Generates analysis, delegates search via A2A
- **ReflectionAgent**: Evaluates quality, communicates with AnalyserAgent via A2A
- **ReActAgent**: ReAct pattern with agent delegation
- **GopherAgent**: Router agent coordinating via A2A
- **CoordinatorAgent**: Orchestrates multi-agent workflows

## Testing

### Unit Tests

- `tests/unit/test_base_agent.py`: BaseAgent tests
- `tests/unit/test_agent_message.py`: Message protocol tests
- `tests/unit/test_agent_registry.py`: Registry tests

### Integration Tests

- `tests/integration/test_a2a_communication.py`: A2A communication tests
- `tests/integration/test_workflows.py`: Multi-agent workflow tests

### E2E Tests

- `tests/e2e/test_full_workflow.py`: Complete workflow tests

## Usage

```python
from Refactored.src.agents.registry import get_registry
from Refactored.src.agents.message_bus import get_message_bus
from Refactored.src.agents.search_agent import SearchAgent
from Refactored.src.agents.analyser_agent import AnalyserAgent

# Initialize registry and message bus
registry = get_registry()
bus = get_message_bus(registry)
await bus.start()

# Register agents
search_agent = SearchAgent()
search_agent.message_bus = bus
search_agent.registry = registry
await registry.register(search_agent)

# Use A2A communication
analyser = AnalyserAgent()
analyser.message_bus = bus
analyser.registry = registry
await registry.register(analyser)

# Delegate search task
response = await analyser.delegate_to_agent(
    capability_type=CapabilityType.SEARCH,
    action="search",
    payload={"query": "test query", "top_k": 10}
)
```

## Differences from Original

1. **A2A Communication**: All agents can communicate directly
2. **Dynamic Discovery**: Agents are discovered via capability matching
3. **Better Separation**: Cleaner separation of concerns
4. **Event-Driven**: Support for event publishing/subscription
5. **Comprehensive Tests**: Full test coverage for A2A patterns

