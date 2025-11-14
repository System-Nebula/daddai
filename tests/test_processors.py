"""
Tests for document processors and embedding generators.
"""
import pytest
from unittest.mock import Mock, patch
from src.processors.document_processor import DocumentProcessor
from src.processors.embedding_generator import EmbeddingGenerator


class TestDocumentProcessor:
    """Test document processing functionality."""
    
    @pytest.mark.unit
    def test_process_text_file(self, sample_text_file):
        """Test processing a text file."""
        processor = DocumentProcessor(chunk_size=100, chunk_overlap=20)
        result = processor.process_document(sample_text_file)
        
        assert "text" in result
        assert "chunks" in result
        assert "metadata" in result
        assert len(result["chunks"]) > 0
        assert result["metadata"]["file_type"] == ".txt"
    
    @pytest.mark.unit
    def test_process_markdown_file(self, sample_markdown_file):
        """Test processing a markdown file."""
        processor = DocumentProcessor()
        result = processor.process_document(sample_markdown_file)
        
        assert "text" in result
        assert "chunks" in result
        assert result["metadata"]["file_type"] == ".md"
    
    @pytest.mark.unit
    def test_process_nonexistent_file(self):
        """Test handling of non-existent file."""
        processor = DocumentProcessor()
        with pytest.raises(FileNotFoundError):
            processor.process_document("/nonexistent/file.txt")
    
    @pytest.mark.unit
    def test_chunk_text(self):
        """Test text chunking functionality."""
        processor = DocumentProcessor(chunk_size=50, chunk_overlap=10)
        text = "This is a test document. " * 10
        chunks = processor._chunk_text(text)
        
        assert len(chunks) > 0
        assert all("text" in chunk for chunk in chunks)
        assert all("chunk_index" in chunk for chunk in chunks)


class TestEmbeddingGenerator:
    """Test embedding generation functionality."""
    
    @pytest.mark.unit
    def test_generate_embedding(self):
        """Test generating a single embedding."""
        generator = EmbeddingGenerator(device='cpu', batch_size=1)
        text = "This is a test sentence."
        embedding = generator.generate_embedding(text)
        
        assert isinstance(embedding, list)
        assert len(embedding) == generator.embedding_dimension
    
    @pytest.mark.unit
    def test_generate_embeddings_batch(self):
        """Test generating embeddings in batch."""
        generator = EmbeddingGenerator(device='cpu', batch_size=2)
        texts = ["First sentence.", "Second sentence.", "Third sentence."]
        embeddings = generator.generate_embeddings_batch(texts)
        
        assert len(embeddings) == len(texts)
        assert all(len(emb) == generator.embedding_dimension for emb in embeddings)
    
    @pytest.mark.unit
    def test_embedding_dimension(self):
        """Test that embedding dimension is correct."""
        generator = EmbeddingGenerator()
        assert generator.embedding_dimension == 384  # all-MiniLM-L6-v2 dimension
    
    @pytest.mark.unit
    def test_empty_text(self):
        """Test handling of empty text."""
        generator = EmbeddingGenerator(device='cpu')
        embedding = generator.generate_embedding("")
        assert len(embedding) == generator.embedding_dimension

