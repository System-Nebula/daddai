# Test Suite

Comprehensive test suite for the RAG system covering all major components.

## Structure

```
tests/
├── conftest.py              # Shared fixtures and pytest configuration
├── test_tools_website.py    # Website summarizer tool tests
├── test_tools_youtube.py    # YouTube transcript tool tests
├── test_tools_sandbox.py    # Tool sandbox security tests
├── test_tools_meta.py       # Meta-tools (write_tool, test_tool, register_tool) tests
├── test_processors.py       # Document processor and embedding generator tests
├── test_stores.py           # Document and memory store tests
├── test_core_rag.py         # Core RAG pipeline tests
├── test_api.py              # API endpoint tests
├── test_utils.py            # Utility function tests
└── test_integration.py      # Integration tests (require external services)
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest tests/test_tools_website.py
```

### Run specific test class
```bash
pytest tests/test_tools_website.py::TestWebsiteSummarizerTool
```

### Run specific test function
```bash
pytest tests/test_tools_youtube.py::TestYouTubeTranscriptTool::test_extract_video_id_youtube_watch
```

### Run only unit tests (fast)
```bash
pytest -m unit
```

### Run with coverage (requires pytest-cov)
```bash
pytest --cov=src --cov-report=html
```

### Skip slow tests
```bash
pytest -m "not slow"
```

## Test Markers

Tests are marked with categories for easy filtering:

- `@pytest.mark.unit` - Fast unit tests, no external dependencies
- `@pytest.mark.integration` - Integration tests, may require services
- `@pytest.mark.slow` - Slow tests (skip by default)
- `@pytest.mark.requires_neo4j` - Requires Neo4j database
- `@pytest.mark.requires_elasticsearch` - Requires Elasticsearch
- `@pytest.mark.requires_lmstudio` - Requires LMStudio running
- `@pytest.mark.requires_gpu` - Requires GPU

## Test Coverage

### Tools (100%)
- ✅ Website summarizer tool
- ✅ YouTube transcript tool
- ✅ Tool sandbox security
- ✅ Meta-tools (write_tool, test_tool, register_tool)

### Processors (100%)
- ✅ Document processor (text, markdown, PDF)
- ✅ Embedding generator (single and batch)

### Stores (100%)
- ✅ Document store (CRUD operations)
- ✅ Similarity search
- ✅ URL-based document lookup

### Core RAG (Partial)
- ✅ Pipeline initialization
- ✅ Input validation
- ⚠️ Full query flow (requires LMStudio)

### API (Partial)
- ✅ Document upload logic
- ⚠️ Full API endpoints (require full setup)

### Utils (100%)
- ✅ User state manager

## Fixtures

Common fixtures available in `conftest.py`:

- `temp_dir` - Temporary directory for test files
- `sample_text_file` - Sample text file
- `sample_markdown_file` - Sample markdown file
- `mock_neo4j_driver` - Mock Neo4j driver
- `mock_embedding` - Mock embedding vector
- `mock_embeddings` - Mock list of embeddings
- `sample_document_data` - Sample document structure
- `mock_lmstudio_client` - Mock LMStudio client
- `mock_embedding_generator` - Mock embedding generator
- `mock_document_store` - Mock document store
- `mock_requests_get` - Mock HTTP requests
- `mock_youtube_transcript_api` - Mock YouTube API

## Writing New Tests

1. Create test file: `tests/test_<module_name>.py`
2. Import pytest and necessary modules
3. Use fixtures from `conftest.py`
4. Mark tests appropriately (`@pytest.mark.unit`, etc.)
5. Follow naming convention: `test_<functionality>`

Example:
```python
import pytest
from src.tools.my_tool import my_function

class TestMyTool:
    @pytest.mark.unit
    def test_my_function_success(self):
        result = my_function("input")
        assert result == "expected_output"
```

## Continuous Integration

Tests can be run in CI/CD pipelines:

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest -v --tb=short

# Run with coverage
pytest --cov=src --cov-report=xml
```

## Notes

- Unit tests use mocks and don't require external services
- Integration tests are marked and can be skipped if services unavailable
- Slow tests are marked and can be skipped for faster test runs
- All tests should be deterministic and not depend on external state

