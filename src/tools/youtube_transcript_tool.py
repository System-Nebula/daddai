"""
YouTube Transcript Tool - Fetches and extracts transcripts from YouTube videos.
This tool intelligently extracts video transcripts and saves them for RAG queries.
"""
import re
from typing import Dict, Any, Optional
from logger_config import logger

# Import smart chunking and summarization utilities
try:
    from src.utils.transcript_chunker import TranscriptChunker, TranscriptSummarizer
    HAS_SMART_CHUNKING = True
except ImportError:
    HAS_SMART_CHUNKING = False
    logger.warning("Smart transcript chunking not available - will use basic formatting")

# Try to import youtube-transcript-api
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
    HAS_YOUTUBE_API = True
except ImportError:
    HAS_YOUTUBE_API = False
    logger.warning("youtube-transcript-api not available. Install with: pip install youtube-transcript-api")


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract YouTube video ID from various URL formats.
    
    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://m.youtube.com/watch?v=VIDEO_ID
    - VIDEO_ID (if already just the ID)
    """
    if not url:
        return None
    
    # If it's already just an ID (11 characters, alphanumeric)
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url
    
    # Extract from various URL patterns
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|m\.youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def get_video_info(video_id: str) -> Dict[str, Any]:
    """
    Get basic video information (title, etc.) using youtube-transcript-api.
    Note: This is limited - we mainly get transcript data.
    """
    try:
        # Create API instance and get transcript list
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        
        # Extract available language codes
        available_languages = []
        for transcript in transcript_list:
            available_languages.append(transcript.language_code)
        
        return {
            'video_id': video_id,
            'available_transcripts': available_languages,
            'url': f'https://www.youtube.com/watch?v={video_id}'
        }
    except Exception as e:
        logger.warning(f"Could not get video info for {video_id}: {e}")
        return {
            'video_id': video_id,
            'available_transcripts': [],
            'url': f'https://www.youtube.com/watch?v={video_id}'
        }


def summarize_youtube(
    url: str,
    language_codes: list = None,
    save_to_documents: bool = False,
    user_id: str = None,
    document_store=None,
    embedding_generator=None,
    document_processor=None
) -> Dict[str, Any]:
    """
    Fetch YouTube video transcript and optionally save to document store.
    
    Args:
        url: YouTube video URL or video ID
        language_codes: List of language codes to try (default: ['en', 'en-US', 'en-GB'])
        save_to_documents: Whether to save transcript to document store
        user_id: User ID for document attribution
        document_store: Document store instance
        embedding_generator: Embedding generator instance
        document_processor: Document processor instance
        
    Returns:
        Dict with transcript data and metadata
    """
    if not HAS_YOUTUBE_API:
        return {
            "success": False,
            "error": "youtube-transcript-api not installed. Install with: pip install youtube-transcript-api",
            "url": url
        }
    
    try:
        # Extract video ID from URL
        video_id = extract_video_id(url)
        if not video_id:
            return {
                "success": False,
                "error": f"Could not extract video ID from URL: {url}",
                "url": url
            }
        
        logger.info(f"🎥 Checking for existing transcript for YouTube video: {video_id}")
        
        # Check if document already exists for this video_id
        existing_doc = None
        if document_store and hasattr(document_store, 'find_document_by_video_id'):
            try:
                existing_doc = document_store.find_document_by_video_id(video_id)
                if existing_doc:
                    logger.info(f"📄 Found existing document for video: {video_id} (doc_id: {existing_doc['id']})")
                    # Retrieve the full content
                    doc_content = document_store.get_document_content(existing_doc['id'])
                    if doc_content and doc_content.get('text'):
                        # Extract transcript from stored content (remove markdown headers)
                        stored_text = doc_content['text']
                        # Remove markdown headers if present
                        transcript_text = stored_text
                        if "## Transcript" in stored_text:
                            transcript_text = stored_text.split("## Transcript")[-1].strip()
                        
                        # Return existing content
                        return {
                            "success": True,
                            "url": f"https://www.youtube.com/watch?v={video_id}",
                            "video_id": video_id,
                            "transcript": transcript_text,
                            "language": doc_content.get('language', 'unknown'),
                            "transcript_length": len(transcript_text),
                            "num_segments": 0,  # Not stored
                            "existing_document": True,
                            "doc_id": existing_doc['id'],
                            "message": f"YouTube transcript already exists in document store (doc_id: {existing_doc['id']}). Using stored content.",
                            "saved_to_documents": True
                        }
            except Exception as e:
                logger.debug(f"Could not check for existing document: {e}")
        
        logger.info(f"🎥 Fetching new transcript for YouTube video: {video_id}")
        
        # Default language codes to try
        if language_codes is None:
            language_codes = ['en', 'en-US', 'en-GB', 'en-CA', 'en-AU']
        
        # Try to get transcript
        transcript_data = None
        transcript_text = None
        language_used = None
        smart_summary = None
        chunks = None
        
        try:
            # Create API instance (required for this version of youtube-transcript-api)
            api = YouTubeTranscriptApi()
            
            # Get transcript list
            transcript_list = api.list(video_id)
            logger.debug(f"Got transcript list for video {video_id}")
            
            transcript_data = None
            language_used = None
            
            # Try preferred languages first
            for lang_code in language_codes:
                try:
                    # Find transcript for this language
                    transcript = transcript_list.find_transcript([lang_code])
                    # Fetch the transcript data
                    fetched_transcript = transcript.fetch()
                    language_used = lang_code
                    
                    # Convert FetchedTranscriptSnippet objects to dict format
                    transcript_data = []
                    for snippet in fetched_transcript:
                        transcript_data.append({
                            'text': snippet.text,
                            'start': snippet.start,
                            'duration': snippet.duration
                        })
                    
                    logger.info(f"✅ Got transcript in language: {lang_code} ({len(transcript_data)} segments)")
                    break
                except NoTranscriptFound:
                    logger.debug(f"No transcript found in {lang_code}")
                    continue
                except TranscriptsDisabled:
                    logger.debug(f"Transcripts disabled for {lang_code}")
                    continue
                except Exception as e:
                    logger.debug(f"Error getting transcript in {lang_code}: {e}")
                    continue
            
            # If no preferred language found, try any available transcript
            if not transcript_data:
                try:
                    # Try manually created English first
                    transcript = transcript_list.find_manually_created_transcript(['en'])
                    fetched_transcript = transcript.fetch()
                    language_used = 'en'
                    
                    transcript_data = []
                    for snippet in fetched_transcript:
                        transcript_data.append({
                            'text': snippet.text,
                            'start': snippet.start,
                            'duration': snippet.duration
                        })
                    logger.info(f"✅ Got manually created transcript in English ({len(transcript_data)} segments)")
                except:
                    # Try any available transcript
                    for transcript in transcript_list:
                        try:
                            fetched_transcript = transcript.fetch()
                            language_used = transcript.language_code
                            
                            transcript_data = []
                            for snippet in fetched_transcript:
                                transcript_data.append({
                                    'text': snippet.text,
                                    'start': snippet.start,
                                    'duration': snippet.duration
                                })
                            logger.info(f"✅ Got transcript in language: {language_used} ({len(transcript_data)} segments)")
                            break
                        except Exception as e:
                            logger.debug(f"Error fetching transcript {transcript.language_code}: {e}")
                            continue
            
            if not transcript_data:
                # Provide more helpful error message
                error_msg = f"No transcript available for video {video_id}. "
                error_msg += "The video may not have captions enabled, or the transcript may not be available in the requested languages."
                logger.warning(f"⚠️ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "video_id": video_id,
                    "tried_languages": language_codes
                }
            
            # Combine transcript entries into text
            transcript_parts = []
            for entry in transcript_data:
                text = entry.get('text', '').strip()
                if text:
                    transcript_parts.append(text)
            
            transcript_text = ' '.join(transcript_parts)
            
            if not transcript_text or len(transcript_text.strip()) < 10:
                return {
                    "success": False,
                    "error": "Transcript is empty or too short",
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "video_id": video_id
                }
            
            logger.info(f"✅ Extracted transcript: {len(transcript_text)} characters, language: {language_used}")
            
            # Smart chunking and summarization for large transcripts
            smart_summary = None
            chunks = None
            
            if HAS_SMART_CHUNKING and len(transcript_text) > 5000:
                try:
                    logger.info(f"📝 Applying smart chunking and summarization to transcript ({len(transcript_text)} chars)")
                    chunker = TranscriptChunker(max_chunk_size=3000, overlap=200)
                    chunks = chunker.smart_chunk(transcript_text, video_id=video_id)
                    
                    if not chunks:
                        logger.warning("Chunking produced no chunks, skipping summarization")
                    else:
                        # Get LMStudio client for summarization (lazy import to avoid circular deps)
                        try:
                            from src.clients.lmstudio_client import LMStudioClient
                            from config import LMSTUDIO_BASE_URL
                            
                            # Initialize summarizer with retry configuration
                            lmstudio_client = LMStudioClient(base_url=LMSTUDIO_BASE_URL)
                            summarizer = TranscriptSummarizer(
                                lmstudio_client=lmstudio_client,
                                max_retries=3,
                                retry_delay=1.0
                            )
                            
                            # Attempt summarization with better error handling
                            logger.info(f"📝 Summarizing {len(chunks)} chunks...")
                            smart_summary = summarizer.summarize_chunks(
                                chunks, 
                                max_summary_length=6000,
                                video_title=f"YouTube Video {video_id}"
                            )
                            
                            # Validate summary quality (not just length)
                            if smart_summary and len(smart_summary.strip()) >= 100:
                                # Additional validation: check if it's actually a summary
                                # TranscriptSummarizer is already imported at the top of the file
                                if summarizer._validate_summary_quality(smart_summary, transcript_text):
                                    logger.info(f"✅ Generated valid smart summary: {len(smart_summary)} characters from {len(chunks)} chunks")
                                else:
                                    logger.warning(f"Smart summary failed quality validation - will use full transcript")
                                    smart_summary = None
                            else:
                                logger.warning(f"Smart summary too short or empty ({len(smart_summary) if smart_summary else 0} chars) - will use full transcript")
                                smart_summary = None
                                
                        except ImportError as e:
                            logger.warning(f"Could not import LMStudio client: {e} - will use full transcript")
                            smart_summary = None
                        except Exception as e:
                            logger.error(f"Could not generate smart summary: {e}", exc_info=True)
                            smart_summary = None
                            
                except Exception as e:
                    logger.error(f"Could not apply smart chunking: {e}", exc_info=True)
                    chunks = None
                    smart_summary = None
            
        except VideoUnavailable:
            return {
                "success": False,
                "error": "Video is unavailable or has been removed",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id
            }
        except TranscriptsDisabled:
            return {
                "success": False,
                "error": "Transcripts are disabled for this video",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id
            }
        except NoTranscriptFound:
            return {
                "success": False,
                "error": "No transcript found for this video",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id
            }
        except Exception as e:
            logger.error(f"Error fetching YouTube transcript: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to fetch transcript: {str(e)}",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id
            }
        
        # Get video info
        video_info = get_video_info(video_id)
        video_url = video_info['url']
        
        # Build structured markdown document for RAG
        markdown_parts = [f"# YouTube Video Transcript\n"]
        markdown_parts.append(f"**Video URL:** {video_url}\n")
        markdown_parts.append(f"**Video ID:** {video_id}\n")
        if language_used:
            markdown_parts.append(f"**Language:** {language_used}\n")
        markdown_parts.append("\n---\n\n")
        
        # Format transcript with timestamps (optional - can be removed for cleaner text)
        # For now, just add the transcript text
        markdown_parts.append("## Transcript\n\n")
        markdown_parts.append(transcript_text)
        
        markdown_content = '\n'.join(markdown_parts)
        
        # Always save to document store (for caching)
        # Use save_to_documents flag to determine if user explicitly requested saving
        doc_id = None
        temp_filename = None
        should_save = save_to_documents or True  # Always save for caching
        
        # Log what we have available for saving
        logger.info(f"💾 Saving check - document_store: {document_store is not None}, "
                   f"embedding_generator: {embedding_generator is not None}, "
                   f"document_processor: {document_processor is not None}, "
                   f"user_id: {user_id}, should_save: {should_save}")
        
        if should_save and document_store and embedding_generator and document_processor and user_id:
            try:
                import tempfile
                import os
                from datetime import datetime
                
                # Create a temporary markdown file
                safe_filename = f"youtube_{video_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                temp_filename = safe_filename
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as temp_file:
                    temp_file.write(markdown_content)
                    temp_path = temp_file.name
                
                try:
                    # Process document
                    document_data = document_processor.process_document(temp_path)
                    
                    # Update metadata to reflect it's a YouTube video
                    document_data['metadata']['file_name'] = temp_filename
                    document_data['metadata']['file_path'] = temp_path
                    document_data['metadata']['file_type'] = '.md'
                    document_data['metadata']['source_url'] = video_url
                    document_data['metadata']['source_type'] = 'youtube'
                    document_data['metadata']['video_id'] = video_id
                    document_data['metadata']['language'] = language_used
                    
                    # Generate embeddings
                    chunk_texts = [chunk['text'] for chunk in document_data['chunks']]
                    embeddings = embedding_generator.generate_embeddings_batch(chunk_texts)
                    
                    # Store document
                    doc_id = document_store.store_document(
                        uploaded_by=user_id,
                        document_data=document_data,
                        embeddings=embeddings
                    )
                    
                    logger.info(f"📄 Saved YouTube transcript as document: {doc_id} ({len(document_data['chunks'])} chunks)")
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                        
            except Exception as e:
                logger.error(f"Error saving YouTube transcript to document store: {e}", exc_info=True)
                # Continue - don't fail the whole operation if saving fails
        
        result = {
            "success": True,
            "url": video_url,
            "video_id": video_id,
            "transcript": transcript_text,
            "language": language_used,
            "transcript_length": len(transcript_text),
            "num_segments": len(transcript_data) if transcript_data else 0,
            "smart_summary": smart_summary,  # Smart summary if available
            "chunks": chunks,  # Chunks if available
            "has_smart_summary": smart_summary is not None
        }
        
        if doc_id:
            result["doc_id"] = doc_id
            result["saved_to_documents"] = True
            result["message"] = f"YouTube transcript saved as document '{temp_filename}' and is now available for RAG queries."
        elif save_to_documents:
            result["saved_to_documents"] = False
            result["warning"] = "Could not save to document store (missing dependencies or error occurred)."
        
        return result
        
    except Exception as e:
        logger.error(f"Error in summarize_youtube: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "url": url
        }

