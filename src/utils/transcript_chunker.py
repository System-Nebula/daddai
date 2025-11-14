"""
Smart transcript chunking and summarization utilities.
Handles large transcripts by intelligently chunking and summarizing them.
"""
import re
import time
from typing import List, Dict, Any, Optional
from logger_config import logger


class TranscriptChunker:
    """Intelligently chunk transcripts for better summarization."""
    
    def __init__(self, max_chunk_size: int = 3000, overlap: int = 200):
        """
        Initialize the transcript chunker.
        
        Args:
            max_chunk_size: Maximum characters per chunk (default: 3000)
            overlap: Overlap between chunks in characters (default: 200)
        """
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
    
    def smart_chunk(self, transcript: str, video_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Intelligently chunk a transcript by:
        1. Natural pauses (periods, exclamation marks, question marks)
        2. Paragraph breaks (double newlines)
        3. Topic shifts (longer pauses, transitions)
        4. Sentence boundaries
        
        Args:
            transcript: Full transcript text
            video_id: Optional video ID for metadata
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        chunks = []
        
        # Clean transcript
        transcript = transcript.strip()
        if not transcript:
            return chunks
        
        # Strategy 1: Try to split by paragraphs (double newlines)
        paragraphs = re.split(r'\n\s*\n', transcript)
        
        if len(paragraphs) > 1:
            # We have paragraph breaks - use them as primary boundaries
            logger.info(f"📝 Chunking transcript by paragraphs ({len(paragraphs)} paragraphs)")
            chunks = self._chunk_by_paragraphs(paragraphs)
        else:
            # Strategy 2: Split by sentences with smart grouping
            logger.info(f"📝 Chunking transcript by sentences")
            chunks = self._chunk_by_sentences(transcript)
        
        # Add metadata to each chunk
        for i, chunk in enumerate(chunks):
            chunk['chunk_index'] = i
            chunk['total_chunks'] = len(chunks)
            if video_id:
                chunk['video_id'] = video_id
        
        logger.info(f"✅ Created {len(chunks)} chunks from transcript ({len(transcript)} chars)")
        return chunks
    
    def _chunk_by_paragraphs(self, paragraphs: List[str]) -> List[Dict[str, Any]]:
        """Chunk transcript by paragraphs, grouping small paragraphs together."""
        chunks = []
        current_chunk = []
        current_length = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_length = len(para)
            
            # If adding this paragraph would exceed max size, finalize current chunk
            if current_length + para_length > self.max_chunk_size and current_chunk:
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append({
                    'text': chunk_text,
                    'start_char': sum(len(c['text']) for c in chunks),
                    'end_char': sum(len(c['text']) for c in chunks) + len(chunk_text),
                    'num_paragraphs': len(current_chunk)
                })
                current_chunk = []
                current_length = 0
            
            # Add paragraph to current chunk
            current_chunk.append(para)
            current_length += para_length + 2  # +2 for newline separator
        
        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'start_char': sum(len(c['text']) for c in chunks),
                'end_char': sum(len(c['text']) for c in chunks) + len(chunk_text),
                'num_paragraphs': len(current_chunk)
            })
        
        return chunks
    
    def _chunk_by_sentences(self, text: str) -> List[Dict[str, Any]]:
        """Chunk transcript by sentences, respecting sentence boundaries."""
        # Split by sentence endings (period, exclamation, question mark)
        # Keep the punctuation with the sentence
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            # Fallback: split by commas or just by size
            return self._chunk_by_size(text)
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # If adding this sentence would exceed max size, finalize current chunk
            if current_length + sentence_length > self.max_chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunks.append({
                    'text': chunk_text,
                    'start_char': sum(len(c['text']) for c in chunks),
                    'end_char': sum(len(c['text']) for c in chunks) + len(chunk_text),
                    'num_sentences': len(current_chunk)
                })
                
                # Add overlap: keep last few sentences for context
                overlap_sentences = current_chunk[-3:] if len(current_chunk) >= 3 else current_chunk
                current_chunk = overlap_sentences
                current_length = sum(len(s) for s in overlap_sentences) + len(overlap_sentences) - 1
            else:
                current_chunk.append(sentence)
                current_length += sentence_length + 1  # +1 for space
        
        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'start_char': sum(len(c['text']) for c in chunks),
                'end_char': sum(len(c['text']) for c in chunks) + len(chunk_text),
                'num_sentences': len(current_chunk)
            })
        
        return chunks
    
    def _chunk_by_size(self, text: str) -> List[Dict[str, Any]]:
        """Fallback: chunk by fixed size with overlap."""
        chunks = []
        text_length = len(text)
        
        start = 0
        chunk_index = 0
        
        while start < text_length:
            end = min(start + self.max_chunk_size, text_length)
            
            # Try to break at word boundary
            if end < text_length:
                # Look for last space before end
                last_space = text.rfind(' ', start, end)
                if last_space > start:
                    end = last_space
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    'text': chunk_text,
                    'start_char': start,
                    'end_char': end,
                    'chunk_type': 'fixed_size'
                })
            
            # Move start forward with overlap
            start = max(start + 1, end - self.overlap)
            chunk_index += 1
        
        return chunks


class TranscriptSummarizer:
    """Summarize transcript chunks intelligently."""
    
    def __init__(self, lmstudio_client=None, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize the transcript summarizer.
        
        Args:
            lmstudio_client: LMStudioClient instance for summarization
            max_retries: Maximum number of retry attempts for transient failures
            retry_delay: Initial delay between retries (exponential backoff)
        """
        self.lmstudio_client = lmstudio_client
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def _validate_summary_quality(self, summary: str, original_text: str) -> bool:
        """
        Validate that a summary is actually a summary and not just truncated text.
        
        Args:
            summary: The generated summary
            original_text: The original text that was summarized
            
        Returns:
            True if summary appears to be valid, False otherwise
        """
        if not summary or len(summary.strip()) < 50:
            return False
        
        # Check if summary is too similar to original (might be truncated)
        summary_words = set(summary.lower().split())
        original_words = set(original_text[:len(summary) * 2].lower().split())
        
        # If summary contains mostly the same words as the beginning of original, it's likely truncated
        if len(summary_words) > 0:
            overlap_ratio = len(summary_words & original_words) / len(summary_words)
            if overlap_ratio > 0.9:  # More than 90% overlap suggests truncation
                logger.warning(f"Summary appears to be truncated (overlap: {overlap_ratio:.2f})")
                return False
        
        # Check for common summary indicators
        summary_lower = summary.lower()
        has_summary_indicators = any([
            'summary' in summary_lower[:100],
            'overview' in summary_lower[:100],
            'key points' in summary_lower,
            'main topics' in summary_lower,
            'discusses' in summary_lower,
            'covers' in summary_lower,
            'explains' in summary_lower,
            len(summary) < len(original_text) * 0.8  # Summary should be shorter
        ])
        
        # If it's much shorter than original, it's likely a summary
        if len(summary) < len(original_text) * 0.5:
            return True
        
        return has_summary_indicators
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        """
        Retry a function call with exponential backoff.
        
        Args:
            func: Function to call
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retries fail
        """
        last_exception = None
        delay = self.retry_delay
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    logger.error(f"All {self.max_retries} attempts failed. Last error: {e}")
        
        raise last_exception
    
    def summarize_chunks(self, 
                        chunks: List[Dict[str, Any]], 
                        max_summary_length: int = 5000,
                        video_title: Optional[str] = None) -> str:
        """
        Summarize transcript chunks intelligently.
        
        Strategy:
        1. If transcript is small (< 10k chars), summarize directly
        2. If medium (10k-30k chars), summarize chunks then combine
        3. If large (> 30k chars), hierarchical summarization
        
        Args:
            chunks: List of transcript chunks
            max_summary_length: Maximum length of final summary
            video_title: Optional video title for context
            
        Returns:
            Summarized transcript text
        """
        if not chunks:
            return ""
        
        # Calculate total length
        total_length = sum(len(chunk.get('text', '')) for chunk in chunks)
        
        # Strategy selection
        if total_length < 10000:
            # Small transcript - summarize directly
            logger.info(f"📝 Small transcript ({total_length} chars) - summarizing directly")
            full_text = '\n\n'.join(chunk.get('text', '') for chunk in chunks)
            return self._summarize_direct(full_text, max_summary_length, video_title)
        
        elif total_length < 30000:
            # Medium transcript - summarize chunks then combine
            logger.info(f"📝 Medium transcript ({total_length} chars) - chunk-based summarization")
            return self._summarize_chunks_then_combine(chunks, max_summary_length, video_title)
        
        else:
            # Large transcript - use faster strategy: summarize key chunks only
            logger.info(f"📝 Large transcript ({total_length} chars) - fast key-chunk summarization")
            return self._summarize_key_chunks(chunks, max_summary_length, video_title)
    
    def _summarize_direct(self, text: str, max_length: int, video_title: Optional[str] = None) -> str:
        """
        Summarize text directly without chunking.
        
        Args:
            text: Text to summarize
            max_length: Maximum length of summary
            video_title: Optional video title for context
            
        Returns:
            Summarized text, or fallback if summarization fails
        """
        if not self.lmstudio_client:
            logger.warning("LMStudio client not available, using fallback summary")
            # Fallback: return key excerpts from text (first, middle, last parts)
            if len(text) > max_length:
                first_part = text[:max_length // 2]
                last_part = text[-max_length // 2:]
                return f"{first_part}\n\n[... middle content ...]\n\n{last_part}"
            return text[:max_length]
        
        # Check if LMStudio is available
        try:
            if not self.lmstudio_client.check_connection():
                logger.warning("LMStudio connection check failed, using fallback summary")
                return self._get_fallback_summary(text, max_length)
        except Exception as e:
            logger.warning(f"Could not check LMStudio connection: {e}, using fallback summary")
            return self._get_fallback_summary(text, max_length)
        
        # Limit input to ~2000 tokens to avoid context overflow (assuming ~4 chars per token)
        # Reserve space for prompt (~500 tokens) and response (~500 tokens)
        # So max input text should be ~1000 tokens = ~4000 chars
        max_input_chars = 4000
        
        prompt = f"""Please provide a comprehensive summary of the following transcript{' from ' + video_title if video_title else ''}.

Focus on:
- Main topics and themes discussed
- Key points and important information
- Important details or findings
- Any conclusions or takeaways

Transcript:
{text[:max_input_chars]}

Summary:"""
        
        try:
            # Use retry logic for transient failures
            def _call_llm():
                return self.lmstudio_client.generate_response(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=min(max_length // 4, 1500)  # Reduced from 2000 to be safer
                )
            
            response = self._retry_with_backoff(_call_llm)
            summary = response.strip() if response else ""
            
            # Validate summary quality
            if summary and self._validate_summary_quality(summary, text):
                logger.info(f"✅ Generated valid summary: {len(summary)} characters")
                return summary
            else:
                logger.warning(f"Summary validation failed (length: {len(summary) if summary else 0}), using fallback")
                return self._get_fallback_summary(text, max_length)
                
        except Exception as e:
            logger.error(f"Error summarizing transcript after retries: {e}", exc_info=True)
            # Fallback: return key excerpts from text
            return self._get_fallback_summary(text, max_length)
    
    def _get_fallback_summary(self, text: str, max_length: int) -> str:
        """
        Generate a fallback summary when LLM summarization fails.
        
        Args:
            text: Original text
            max_length: Maximum length of summary
            
        Returns:
            Fallback summary (key excerpts)
        """
        if len(text) <= max_length:
            return text
        
        # Take first 40%, middle 20%, last 40% for better coverage
        first_part = text[:max_length // 2]
        last_part = text[-max_length // 2:]
        return f"{first_part}\n\n[... middle content ...]\n\n{last_part}"
    
    def _summarize_chunks_then_combine(self, 
                                      chunks: List[Dict[str, Any]], 
                                      max_length: int,
                                      video_title: Optional[str] = None) -> str:
        """Summarize each chunk, then combine summaries."""
        chunk_summaries = []
        
        for i, chunk in enumerate(chunks):
            chunk_text = chunk.get('text', '')
            if not chunk_text:
                continue
            
            logger.info(f"📝 Summarizing chunk {i+1}/{len(chunks)}")
            
            # Summarize this chunk
            chunk_summary = self._summarize_chunk(chunk_text, video_title)
            if chunk_summary:
                chunk_summaries.append({
                    'chunk_index': i,
                    'summary': chunk_summary
                })
        
        # Combine summaries
        if not chunk_summaries:
            return ""
        
        combined_summaries = '\n\n'.join(
            f"Section {cs['chunk_index'] + 1}:\n{cs['summary']}"
            for cs in chunk_summaries
        )
        
        # Final summary of summaries if needed
        if len(combined_summaries) > max_length:
            logger.info(f"📝 Combining {len(chunk_summaries)} chunk summaries")
            return self._summarize_direct(combined_summaries, max_length, video_title)
        
        return combined_summaries
    
    def _summarize_chunk(self, chunk_text: str, video_title: Optional[str] = None) -> str:
        """
        Summarize a single chunk with retry logic and validation.
        
        Args:
            chunk_text: Text chunk to summarize
            video_title: Optional video title for context
            
        Returns:
            Summarized chunk text
        """
        if not self.lmstudio_client:
            logger.debug("LMStudio client not available, using chunk excerpt")
            return chunk_text[:500]  # Fallback
        
        # Check connection
        try:
            if not self.lmstudio_client.check_connection():
                return chunk_text[:500]
        except Exception:
            return chunk_text[:500]
        
        prompt = f"""Summarize the following section of a transcript{' from ' + video_title if video_title else ''}.

Focus on the main points and key information. Be concise but comprehensive.

Transcript section:
{chunk_text[:5000]}

Summary:"""
        
        try:
            # Use retry logic
            def _call_llm():
                return self.lmstudio_client.generate_response(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=500
                )
            
            response = self._retry_with_backoff(_call_llm)
            summary = response.strip() if response else ""
            
            # Validate summary quality
            if summary and len(summary) >= 50 and self._validate_summary_quality(summary, chunk_text):
                return summary
            else:
                logger.debug(f"Chunk summary validation failed, using excerpt")
                return chunk_text[:500]  # Fallback
                
        except Exception as e:
            logger.warning(f"Error summarizing chunk after retries: {e}")
            return chunk_text[:500]  # Fallback
    
    def _summarize_key_chunks(self, 
                              chunks: List[Dict[str, Any]], 
                              max_length: int,
                              video_title: Optional[str] = None) -> str:
        """
        Fast summarization for large transcripts: summarize key chunks (beginning, middle, end).
        This is much faster than hierarchical summarization while still capturing key information.
        """
        if not chunks:
            return ""
        
        # Strategy: Summarize first 2 chunks, middle 1 chunk, and last 2 chunks
        # Reduced from 3+2+3 to avoid context overflow
        num_chunks = len(chunks)
        key_chunks = []
        
        # First 2 chunks (introduction)
        key_chunks.extend(chunks[:min(2, num_chunks)])
        
        # Middle chunk (main content) - take 1 from middle
        if num_chunks > 4:
            mid_start = num_chunks // 2
            key_chunks.append(chunks[mid_start])
        
        # Last 2 chunks (conclusion)
        if num_chunks > 2:
            key_chunks.extend(chunks[-2:])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_key_chunks = []
        for chunk in key_chunks:
            chunk_id = id(chunk)
            if chunk_id not in seen:
                seen.add(chunk_id)
                unique_key_chunks.append(chunk)
        
        logger.info(f"📝 Fast summarization: {num_chunks} chunks -> {len(unique_key_chunks)} key chunks")
        
        # Combine key chunks and limit total size to avoid context overflow
        key_text_parts = []
        total_chars = 0
        max_chars_per_chunk = 1000  # Limit each chunk to ~1000 chars
        
        for chunk in unique_key_chunks:
            chunk_text = chunk.get('text', '')
            if chunk_text:
                # Truncate chunk if too long
                if len(chunk_text) > max_chars_per_chunk:
                    chunk_text = chunk_text[:max_chars_per_chunk] + "..."
                key_text_parts.append(chunk_text)
                total_chars += len(chunk_text)
                
                # Stop if we've reached a safe limit (~3000 chars total)
                if total_chars > 3000:
                    break
        
        key_text = '\n\n'.join(key_text_parts)
        
        # Summarize the combined key chunks
        try:
            return self._summarize_direct(key_text, max_length, video_title)
        except Exception as e:
            logger.error(f"Error in key-chunk summarization: {e}")
            # Fallback: return the key chunks as-is (better than nothing)
            return key_text[:max_length]
    
    def _summarize_hierarchical(self, 
                               chunks: List[Dict[str, Any]], 
                               max_length: int,
                               video_title: Optional[str] = None) -> str:
        """Hierarchical summarization: summarize groups of chunks, then summarize summaries."""
        # Group chunks into larger batches for speed
        batch_size = 8  # Increased from 5 to reduce number of batches
        batches = []
        
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_text = '\n\n'.join(chunk.get('text', '') for chunk in batch_chunks)
            batches.append({
                'batch_index': i // batch_size,
                'text': batch_text
            })
        
        logger.info(f"📝 Hierarchical summarization: {len(chunks)} chunks -> {len(batches)} batches")
        
        # Summarize each batch
        batch_summaries = []
        for batch in batches:
            logger.info(f"📝 Summarizing batch {batch['batch_index'] + 1}/{len(batches)}")
            summary = self._summarize_chunk(batch['text'], video_title)
            if summary:
                batch_summaries.append(summary)
        
        # Combine and finalize
        combined = '\n\n'.join(batch_summaries)
        
        if len(combined) > max_length:
            # Final summary pass
            logger.info(f"📝 Final summary pass")
            return self._summarize_direct(combined, max_length, video_title)
        
        return combined

