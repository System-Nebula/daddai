"""
Tests for document and memory stores.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.stores.document_store import DocumentStore
from src.stores.neo4j_store import Neo4jStore


class TestDocumentStore:
    """Test document store functionality."""
    
    @pytest.mark.unit
    @patch('src.stores.document_store.GraphDatabase')
    def test_store_document(self, mock_graph_db, sample_document_data, mock_embeddings):
        """Test storing a document."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_driver.session.return_value.__exit__.return_value = None
        mock_graph_db.driver.return_value = mock_driver
        
        store = DocumentStore()
        doc_id = store.store_document(
            uploaded_by="test_user",
            document_data=sample_document_data,
            embeddings=mock_embeddings
        )
        
        assert doc_id is not None
        assert doc_id.startswith("shared_doc_")
        assert mock_session.run.called
    
    @pytest.mark.unit
    @patch('src.stores.document_store.GraphDatabase')
    def test_get_all_shared_documents(self, mock_graph_db):
        """Test retrieving all shared documents."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_record = Mock()
        mock_record.get.side_effect = lambda key, default=None: {
            'id': 'doc1',
            'file_name': 'test.txt',
            'uploaded_by': 'user1',
            'uploaded_at': '2024-01-01',
            'chunk_count': 5
        }.get(key, default)
        
        mock_result = Mock()
        mock_result.__iter__.return_value = [mock_record]
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_driver.session.return_value.__exit__.return_value = None
        mock_graph_db.driver.return_value = mock_driver
        
        store = DocumentStore()
        documents = store.get_all_shared_documents()
        
        assert isinstance(documents, list)
    
    @pytest.mark.unit
    @patch('src.stores.document_store.GraphDatabase')
    def test_find_document_by_url(self, mock_graph_db):
        """Test finding document by URL."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_record = Mock()
        mock_record.get.side_effect = lambda key, default=None: {
            'id': 'doc1',
            'file_name': 'test.txt',
            'uploaded_by': 'user1',
            'uploaded_at': '2024-01-01',
            'source_url': 'https://example.com',
            'chunk_count': 5
        }.get(key, default)
        
        mock_result = Mock()
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_driver.session.return_value.__exit__.return_value = None
        mock_graph_db.driver.return_value = mock_driver
        
        store = DocumentStore()
        doc = store.find_document_by_url("https://example.com")
        
        assert doc is not None
        assert doc['id'] == 'doc1'
    
    @pytest.mark.unit
    @patch('src.stores.document_store.GraphDatabase')
    def test_similarity_search_shared(self, mock_graph_db, mock_embedding):
        """Test similarity search in shared documents."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_record = Mock()
        mock_record.__getitem__.side_effect = lambda key: {
            'text': 'Test chunk',
            'chunk_index': 0,
            'embedding': [0.1] * 384,
            'file_name': 'test.txt',
            'doc_id': 'doc1',
            'uploaded_by': 'user1'
        }[key]
        
        mock_result = Mock()
        mock_result.__iter__.return_value = [mock_record]
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_driver.session.return_value.__exit__.return_value = None
        mock_graph_db.driver.return_value = mock_driver
        
        store = DocumentStore()
        results = store.similarity_search_shared(mock_embedding, top_k=5)
        
        assert isinstance(results, list)

