"""
Tests for YouTube transcript tool.
"""
import pytest
from unittest.mock import Mock, patch
from src.tools.youtube_transcript_tool import (
    summarize_youtube,
    extract_video_id,
    get_video_info
)


class TestYouTubeTranscriptTool:
    """Test YouTube transcript tool functionality."""
    
    @pytest.mark.unit
    def test_extract_video_id_youtube_watch(self):
        """Test extracting video ID from youtube.com/watch URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
    
    @pytest.mark.unit
    def test_extract_video_id_youtu_be(self):
        """Test extracting video ID from youtu.be URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        video_id = extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
    
    @pytest.mark.unit
    def test_extract_video_id_direct_id(self):
        """Test extracting video ID when URL is just the ID."""
        video_id = extract_video_id("dQw4w9WgXcQ")
        assert video_id == "dQw4w9WgXcQ"
    
    @pytest.mark.unit
    def test_extract_video_id_invalid(self):
        """Test handling of invalid URL."""
        video_id = extract_video_id("not-a-valid-url")
        assert video_id is None
    
    @pytest.mark.unit
    @patch('src.tools.youtube_transcript_tool.HAS_YOUTUBE_API', False)
    def test_summarize_youtube_missing_api(self):
        """Test handling when youtube-transcript-api is not installed."""
        result = summarize_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result["success"] is False
        assert "not installed" in result["error"].lower()
    
    @pytest.mark.unit
    @patch('src.tools.youtube_transcript_tool.YouTubeTranscriptApi')
    def test_summarize_youtube_success(self, mock_api, mock_embedding_generator, mock_document_store, mock_document_processor):
        """Test successful YouTube transcript fetching."""
        # Mock transcript API
        mock_transcript = [
            {"text": "Hello", "start": 0.0, "duration": 1.0},
            {"text": "world", "start": 1.0, "duration": 1.0}
        ]
        mock_list = Mock()
        mock_transcript_obj = Mock()
        mock_transcript_obj.fetch.return_value = mock_transcript
        mock_transcript_obj.language_code = "en"
        mock_list.find_transcript.return_value = mock_transcript_obj
        mock_api.list_transcripts.return_value = mock_list
        
        # Mock document processor
        mock_doc_data = {
            "text": "Hello world",
            "chunks": [{"text": "Hello world", "chunk_index": 0}],
            "metadata": {
                "file_name": "youtube_dQw4w9WgXcQ_20241114_120000.md",
                "file_path": "/tmp/test.md",
                "file_type": ".md",
                "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "source_type": "youtube",
                "video_id": "dQw4w9WgXcQ"
            }
        }
        mock_document_processor.process_document.return_value = mock_doc_data
        mock_embedding_generator.generate_embeddings_batch.return_value = [[0.1] * 384]
        mock_document_store.store_document.return_value = "test_doc_id"
        
        result = summarize_youtube(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            save_to_documents=True,
            user_id="test_user",
            document_store=mock_document_store,
            embedding_generator=mock_embedding_generator,
            document_processor=mock_document_processor
        )
        
        assert result["success"] is True
        assert result["video_id"] == "dQw4w9WgXcQ"
        assert "transcript" in result
    
    @pytest.mark.unit
    @patch('src.tools.youtube_transcript_tool.YouTubeTranscriptApi')
    def test_summarize_youtube_no_transcript(self, mock_api):
        """Test handling when transcript is not available."""
        from youtube_transcript_api._errors import NoTranscriptFound
        
        mock_list = Mock()
        mock_list.find_transcript.side_effect = NoTranscriptFound("video_id", None, None)
        mock_api.list_transcripts.return_value = mock_list
        
        result = summarize_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        
        assert result["success"] is False
        assert "transcript" in result["error"].lower()
    
    @pytest.mark.unit
    @patch('src.tools.youtube_transcript_tool.YouTubeTranscriptApi')
    def test_summarize_youtube_video_unavailable(self, mock_api):
        """Test handling when video is unavailable."""
        from youtube_transcript_api._errors import VideoUnavailable
        
        mock_api.list_transcripts.side_effect = VideoUnavailable("video_id")
        
        result = summarize_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        
        assert result["success"] is False
        assert "unavailable" in result["error"].lower()

