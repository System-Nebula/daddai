"""
Pytest configuration and shared fixtures for all tests.
"""
import pytest
import os
import sys
import tempfile
import shutil
from unittest.mock import Mock, MagicMock, patch
from typing import Generator

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_text_file(temp_dir: str) -> str:
    """Create a sample text file for testing."""
    file_path = os.path.join(temp_dir, "sample.txt")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("This is a sample document for testing.\n")
        f.write("It contains multiple lines of text.\n")
        f.write("We can use it to test document processing.")
    return file_path


@pytest.fixture
def sample_markdown_file(temp_dir: str) -> str:
    """Create a sample markdown file for testing."""
    file_path = os.path.join(temp_dir, "sample.md")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("# Test Document\n\n")
        f.write("This is a **markdown** document.\n\n")
        f.write("## Section 1\n\n")
        f.write("Content here.\n")
    return file_path


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for testing."""
    mock_driver = Mock()
    mock_session = Mock()
    mock_driver.session.return_value.__enter__.return_value = mock_session
    mock_driver.session.return_value.__exit__.return_value = None
    mock_session.run.return_value = []
    return mock_driver


@pytest.fixture
def mock_embedding():
    """Mock embedding vector for testing."""
    return [0.1] * 384  # Standard embedding dimension


@pytest.fixture
def mock_embeddings(mock_embedding):
    """Mock list of embeddings for testing."""
    return [mock_embedding] * 5


@pytest.fixture
def sample_document_data():
    """Sample document data structure for testing."""
    return {
        "text": "This is a sample document with multiple sentences. It contains information for testing.",
        "chunks": [
            {"text": "This is a sample document with multiple sentences.", "chunk_index": 0},
            {"text": "It contains information for testing.", "chunk_index": 1}
        ],
        "metadata": {
            "file_name": "test.txt",
            "file_path": "/path/to/test.txt",
            "file_type": ".txt"
        }
    }


@pytest.fixture
def mock_lmstudio_client():
    """Mock LMStudio client for testing."""
    mock_client = Mock()
    mock_client.check_connection.return_value = True
    mock_client.generate_response.return_value = "This is a mock response."
    mock_client.analyze_query.return_value = {
        "intent": "question",
        "entities": [],
        "needs_context": True
    }
    return mock_client


@pytest.fixture
def mock_embedding_generator():
    """Mock embedding generator for testing."""
    mock_gen = Mock()
    mock_gen.generate_embedding.return_value = [0.1] * 384
    mock_gen.generate_embeddings_batch.return_value = [[0.1] * 384] * 5
    mock_gen.embedding_dimension = 384
    mock_gen.batch_size = 32
    return mock_gen


@pytest.fixture
def mock_document_store():
    """Mock document store for testing."""
    mock_store = Mock()
    mock_store.store_document.return_value = "test_doc_id_123"
    mock_store.get_all_shared_documents.return_value = []
    mock_store.find_document_by_url.return_value = None
    mock_store.similarity_search_shared.return_value = []
    return mock_store


@pytest.fixture
def mock_document_processor():
    """Mock document processor for testing."""
    mock_processor = Mock()
    mock_processor.process_document.return_value = {
        "text": "Test document text",
        "chunks": [
            {"text": "Test document text", "chunk_index": 0}
        ],
        "metadata": {
            "file_name": "test.txt",
            "file_path": "/tmp/test.txt",
            "file_type": ".txt"
        }
    }
    return mock_processor


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for testing HTTP calls."""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_youtube_transcript_api():
    """Mock YouTube Transcript API for testing."""
    with patch('youtube_transcript_api.YouTubeTranscriptApi') as mock_api:
        mock_transcript = [
            {"text": "Hello", "start": 0.0, "duration": 1.0},
            {"text": "world", "start": 1.0, "duration": 1.0}
        ]
        mock_list = Mock()
        mock_transcript_obj = Mock()
        mock_transcript_obj.fetch.return_value = mock_transcript
        mock_transcript_obj.language_code = "en"
        mock_list.find_transcript.return_value = mock_transcript_obj
        mock_list.find_manually_created_transcript.return_value = mock_transcript_obj
        mock_list.__iter__.return_value = [mock_transcript_obj]
        mock_api.list_transcripts.return_value = mock_list
        yield mock_api

