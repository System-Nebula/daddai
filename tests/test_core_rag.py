"""
Tests for core RAG pipeline components.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.core.rag_pipeline import RAGPipeline


class TestRAGPipeline:
    """Test RAG pipeline functionality."""
    
    @pytest.mark.unit
    @patch('src.core.rag_pipeline.LMStudioClient')
    @patch('src.core.rag_pipeline.Neo4jStore')
    @patch('src.core.rag_pipeline.EmbeddingGenerator')
    def test_pipeline_initialization(self, mock_embedding, mock_store, mock_client):
        """Test RAG pipeline initialization."""
        mock_client_instance = Mock()
        mock_client_instance.check_connection.return_value = True
        mock_client.return_value = mock_client_instance
        
        pipeline = RAGPipeline()
        
        assert pipeline is not None
        assert hasattr(pipeline, 'query')
    
    @pytest.mark.unit
    @patch('src.core.rag_pipeline.LMStudioClient')
    @patch('src.core.rag_pipeline.Neo4jStore')
    @patch('src.core.rag_pipeline.EmbeddingGenerator')
    def test_query_empty_question(self, mock_embedding, mock_store, mock_client):
        """Test that empty questions raise ValueError."""
        mock_client_instance = Mock()
        mock_client_instance.check_connection.return_value = True
        mock_client.return_value = mock_client_instance
        
        pipeline = RAGPipeline()
        
        with pytest.raises(ValueError):
            pipeline.query("")
    
    @pytest.mark.unit
    @patch('src.core.rag_pipeline.LMStudioClient')
    @patch('src.core.rag_pipeline.Neo4jStore')
    @patch('src.core.rag_pipeline.EmbeddingGenerator')
    def test_query_whitespace_only(self, mock_embedding, mock_store, mock_client):
        """Test that whitespace-only questions raise ValueError."""
        mock_client_instance = Mock()
        mock_client_instance.check_connection.return_value = True
        mock_client.return_value = mock_client_instance
        
        pipeline = RAGPipeline()
        
        with pytest.raises(ValueError):
            pipeline.query("   ")

