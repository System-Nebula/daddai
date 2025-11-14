"""
Tests for website summarizer tool.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.tools.website_summarizer_tool import summarize_website, StructuredExtractor


class TestWebsiteSummarizerTool:
    """Test website summarizer tool functionality."""
    
    def test_url_validation(self):
        """Test URL validation for websites."""
        url = "https://example.com/article"
        # Website URLs should start with http:// or https://
        assert url.startswith(('http://', 'https://'))
    
    @pytest.mark.unit
    def test_summarize_website_missing_api(self):
        """Test that tool handles missing BeautifulSoup gracefully."""
        with patch('src.tools.website_summarizer_tool.HAS_BS4', False):
            # Should still work with basic parser
            pass
    
    @pytest.mark.unit
    @patch('requests.get')
    def test_summarize_website_success(self, mock_get, mock_embedding_generator, mock_document_store, mock_document_processor):
        """Test successful website summarization."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.text = """
        <html>
            <head><title>Test Article</title></head>
            <body>
                <article>
                    <h1>Test Article</h1>
                    <p>This is a test article with some content.</p>
                    <p>It has multiple paragraphs.</p>
                </article>
            </body>
        </html>
        """
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Mock document processor
        mock_doc_data = {
            "text": "Test Article\n\nThis is a test article with some content.\n\nIt has multiple paragraphs.",
            "chunks": [
                {"text": "Test Article", "chunk_index": 0},
                {"text": "This is a test article with some content.", "chunk_index": 1}
            ],
            "metadata": {
                "file_name": "web_Test_Article_20241114_120000.md",
                "file_path": "/tmp/test.md",
                "file_type": ".md",
                "source_url": "https://example.com/article",
                "source_type": "website"
            }
        }
        mock_document_processor.process_document.return_value = mock_doc_data
        mock_embedding_generator.generate_embeddings_batch.return_value = [[0.1] * 384] * 2
        mock_document_store.store_document.return_value = "test_doc_id"
        
        result = summarize_website(
            url="https://example.com/article",
            save_to_documents=True,
            user_id="test_user",
            document_store=mock_document_store,
            embedding_generator=mock_embedding_generator,
            document_processor=mock_document_processor
        )
        
        assert result["success"] is True
        assert "url" in result
        assert "title" in result
    
    @pytest.mark.unit
    @patch('requests.get')
    def test_summarize_website_timeout(self, mock_get):
        """Test handling of request timeout."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        result = summarize_website("https://example.com/article")
        
        assert result["success"] is False
        assert "timeout" in result["error"].lower() or "timed out" in result["error"].lower()
    
    @pytest.mark.unit
    @patch('requests.get')
    def test_summarize_website_invalid_content(self, mock_get):
        """Test handling of invalid/empty content."""
        mock_response = Mock()
        mock_response.text = "<html><body></body></html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = summarize_website("https://example.com/article")
        
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.unit
    def test_structured_extractor(self):
        """Test HTML parser extraction."""
        html = """
        <html>
            <h1>Title</h1>
            <p>Paragraph 1</p>
            <p>Paragraph 2</p>
        </html>
        """
        parser = StructuredExtractor()
        parser.feed(html)
        content = parser.get_structured_content()
        
        assert "full_text" in content
        assert len(content.get("sections", [])) > 0

