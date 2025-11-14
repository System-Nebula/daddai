"""
Website Summarization Tool - Fetches and extracts structured content from websites.
This tool intelligently parses article content and returns structured data for LLM queries.
"""
import requests
from html.parser import HTMLParser
from typing import Dict, Any, List, Optional
import re
from logger_config import logger

# Try to use BeautifulSoup if available for better parsing
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    logger.info("BeautifulSoup not available, using basic HTML parser")

# Import smart chunking and summarization utilities
try:
    from src.utils.transcript_chunker import TranscriptChunker, TranscriptSummarizer
    HAS_SMART_CHUNKING = True
except ImportError:
    HAS_SMART_CHUNKING = False
    logger.warning("Smart content chunking not available - will use basic formatting")


class StructuredExtractor(HTMLParser):
    """Extract structured content from HTML with semantic information."""
    
    def __init__(self):
        super().__init__()
        self.structure = []
        self.current_section = None
        self.skip_tags = {'script', 'style', 'meta', 'link', 'head', 'noscript', 'nav', 'footer', 'header', 'aside'}
        self.in_skip_tag = False
        self.current_tag = None
        self.current_text = []
        
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag.lower()
        if self.current_tag in self.skip_tags:
            self.in_skip_tag = True
        elif self.current_tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            # Save any accumulated text before heading
            if self.current_text:
                self._add_text(' '.join(self.current_text))
                self.current_text = []
            self.current_section = {'type': 'heading', 'level': int(self.current_tag[1]), 'text': ''}
        elif self.current_tag in ['article', 'main', 'section']:
            if self.current_text:
                self._add_text(' '.join(self.current_text))
                self.current_text = []
                
    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in self.skip_tags:
            self.in_skip_tag = False
        elif tag_lower in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            if self.current_section and self.current_section.get('type') == 'heading':
                self.current_section['text'] = ' '.join(self.current_text).strip()
                if self.current_section['text']:
                    self.structure.append(self.current_section)
                self.current_section = None
                self.current_text = []
        elif tag_lower in ['p', 'li', 'div']:
            if self.current_text and not self.in_skip_tag:
                text = ' '.join(self.current_text).strip()
                if text:
                    self._add_text(text)
                self.current_text = []
        self.current_tag = None
            
    def handle_data(self, data):
        if not self.in_skip_tag:
            cleaned = data.strip()
            if cleaned:
                if self.current_section and self.current_section.get('type') == 'heading':
                    self.current_text.append(cleaned)
                else:
                    self.current_text.append(cleaned)
    
    def _add_text(self, text: str):
        """Add text content to structure."""
        if text and len(text) > 10:  # Only add substantial text
            self.structure.append({'type': 'paragraph', 'text': text})
    
    def get_structured_content(self, max_length: int = 50000) -> Dict[str, Any]:
        """Get structured content with headings and paragraphs."""
        # Add any remaining text
        if self.current_text:
            self._add_text(' '.join(self.current_text))
        
        # Build structured content
        sections = []
        current_section = None
        
        for item in self.structure:
            if item['type'] == 'heading':
                # Save previous section
                if current_section:
                    sections.append(current_section)
                # Start new section
                current_section = {
                    'heading': item['text'],
                    'level': item['level'],
                    'content': []
                }
            elif item['type'] == 'paragraph' and current_section:
                current_section['content'].append(item['text'])
            elif item['type'] == 'paragraph':
                # Paragraph without heading
                sections.append({
                    'heading': None,
                    'content': [item['text']]
                })
        
        # Add last section
        if current_section:
            sections.append(current_section)
        
        # Build full text
        full_text_parts = []
        for section in sections:
            if section['heading']:
                full_text_parts.append(f"\n\n## {section['heading']}\n")
            for para in section['content']:
                full_text_parts.append(para)
        
        full_text = '\n'.join(full_text_parts)
        
        # Truncate if needed
        if len(full_text) > max_length:
            full_text = full_text[:max_length] + '\n\n... [content truncated]'
        
        return {
            'full_text': full_text.strip(),
            'sections': sections[:20],  # Limit sections
            'text_length': len(full_text)
        }


def _extract_with_bs4(html: str, max_length: int) -> Dict[str, Any]:
    """Extract content using BeautifulSoup for better parsing."""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove unwanted elements
    for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript']):
        element.decompose()
    
    # Extract title
    title = None
    if soup.title:
        title = soup.title.get_text().strip()
    elif soup.find('h1'):
        title = soup.find('h1').get_text().strip()
    
    # Try to find main article content
    article = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile(r'article|content|post|blog', re.I))
    
    if article:
        content_elem = article
    else:
        content_elem = soup.find('body') or soup
    
    # Extract structured content
    sections = []
    current_heading = None
    current_content = []
    
    for elem in content_elem.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'div']):
        tag = elem.name.lower()
        text = elem.get_text(strip=True)
        
        if not text or len(text) < 10:
            continue
            
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            # Save previous section
            if current_heading or current_content:
                sections.append({
                    'heading': current_heading,
                    'level': int(tag[1]) if tag.startswith('h') else 0,
                    'content': current_content
                })
            # Start new section
            current_heading = text
            current_content = []
        elif tag in ['p', 'li']:
            current_content.append(text)
        elif tag == 'div' and text:
            # Only add divs with substantial content
            if len(text) > 50:
                current_content.append(text)
    
    # Add last section
    if current_heading or current_content:
        sections.append({
            'heading': current_heading,
            'content': current_content
        })
    
    # Build full text with structure
    full_text_parts = []
    for section in sections:
        if section['heading']:
            full_text_parts.append(f"\n\n## {section['heading']}\n")
        for para in section['content']:
            full_text_parts.append(para)
    
    full_text = '\n'.join(full_text_parts).strip()
    
    # Extract metadata
    metadata = {}
    
    # Try to find author
    author_elem = soup.find(['span', 'div', 'p'], class_=re.compile(r'author|byline|writer', re.I))
    if author_elem:
        metadata['author'] = author_elem.get_text(strip=True)
    
    # Try to find date
    date_elem = soup.find(['time', 'span', 'div'], class_=re.compile(r'date|time|published', re.I))
    if date_elem:
        metadata['date'] = date_elem.get_text(strip=True)
        if date_elem.get('datetime'):
            metadata['date'] = date_elem.get('datetime')
    
    # Truncate if needed
    if len(full_text) > max_length:
        full_text = full_text[:max_length] + '\n\n... [content truncated]'
    
    return {
        'full_text': full_text,
        'sections': sections[:30],  # Limit sections
        'title': title,
        'metadata': metadata,
        'text_length': len(full_text)
    }


def summarize_website(url: str, max_length: int = 50000, save_to_documents: bool = False, user_id: str = None, document_store=None, embedding_generator=None, document_processor=None) -> Dict[str, Any]:
    """
    Fetch a website and intelligently extract structured article content.
    The LLM can use this structured content to answer specific questions about the article.
    
    Args:
        url: Website URL to fetch
        max_length: Maximum length of extracted text (default: 50000 chars)
        
    Returns:
        Dict with structured content including:
        - url: Original URL
        - title: Article title
        - full_text: Complete article text with headings
        - sections: List of sections with headings and content
        - metadata: Author, date, etc.
        - success: Whether extraction succeeded
    """
    try:
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Check if document already exists for this URL
        existing_doc = None
        if document_store and hasattr(document_store, 'find_document_by_url'):
            try:
                existing_doc = document_store.find_document_by_url(url)
                if existing_doc:
                    logger.info(f"📄 Found existing document for URL: {url} (doc_id: {existing_doc['id']})")
                    # Retrieve the full content
                    doc_content = document_store.get_document_content(existing_doc['id'])
                    if doc_content and doc_content.get('text'):
                        # Extract content from stored document
                        stored_text = doc_content['text']
                        
                        # Try to extract title and sections if stored in markdown format
                        title = doc_content.get('file_name', 'Unknown')
                        if stored_text.startswith('#'):
                            # Extract title from markdown
                            first_line = stored_text.split('\n')[0]
                            title = first_line.replace('#', '').strip()
                        
                        # Return existing content
                        return {
                            "success": True,
                            "url": url,
                            "title": title,
                            "full_text": stored_text,
                            "text_length": len(stored_text),
                            "num_sections": len(doc_content.get('chunks', [])),
                            "existing_document": True,
                            "doc_id": existing_doc['id'],
                            "message": f"Website content already exists in document store (doc_id: {existing_doc['id']}). Using stored content.",
                            "saved_to_documents": True
                        }
            except Exception as e:
                logger.debug(f"Could not check for existing document: {e}")
        
        # Fetch the website
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        logger.info(f"🌐 Fetching website: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Use BeautifulSoup if available, otherwise use basic parser
        if HAS_BS4:
            logger.info("Using BeautifulSoup for enhanced parsing")
            content_data = _extract_with_bs4(response.text, max_length)
        else:
            logger.info("Using basic HTML parser")
            parser = StructuredExtractor()
            parser.feed(response.text)
            content_data = parser.get_structured_content(max_length)
            
            # Extract title with basic parser
            title_match = re.search(r'<title[^>]*>(.*?)</title>', response.text, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else None
            if title:
                title = re.sub(r'&[a-z]+;', '', title)
                title = re.sub(r'<[^>]+>', '', title)
            content_data['title'] = title
            content_data['metadata'] = {}
        
        if not content_data.get('full_text') or len(content_data['full_text'].strip()) < 50:
            return {
                "success": False,
                "error": "Could not extract meaningful text content from the website",
                "url": url
            }
        
        logger.info(f"✅ Extracted {content_data['text_length']} characters in {len(content_data.get('sections', []))} sections from {url}")
        
        # Smart chunking and summarization for large articles
        full_text = content_data.get('full_text', '')
        smart_summary = None
        chunks = None
        
        if HAS_SMART_CHUNKING and len(full_text) > 5000:
            try:
                logger.info(f"📝 Applying smart chunking and summarization to article")
                chunker = TranscriptChunker(max_chunk_size=3000, overlap=200)
                chunks = chunker.smart_chunk(full_text)
                
                # Get LMStudio client for summarization (lazy import to avoid circular deps)
                try:
                    from src.clients.lmstudio_client import LMStudioClient
                    from config import LMSTUDIO_BASE_URL
                    summarizer = TranscriptSummarizer(lmstudio_client=LMStudioClient(base_url=LMSTUDIO_BASE_URL))
                    article_title = content_data.get('title', 'Article')
                    smart_summary = summarizer.summarize_chunks(
                        chunks, 
                        max_summary_length=8000,
                        video_title=article_title
                    )
                    logger.info(f"✅ Generated smart summary: {len(smart_summary)} characters from {len(chunks)} chunks")
                except Exception as e:
                    logger.warning(f"Could not generate smart summary: {e} - will use full article")
                    smart_summary = None
            except Exception as e:
                logger.warning(f"Could not apply smart chunking: {e} - will use full article")
                chunks = None
                smart_summary = None
        
        # Build structured markdown document for RAG
        title = content_data.get('title', 'Untitled')
        article_metadata = content_data.get('metadata', {})
        
        # Create markdown document with proper structure
        markdown_parts = [f"# {title}\n"]
        
        # Add metadata if available
        if article_metadata.get('author'):
            markdown_parts.append(f"**Author:** {article_metadata['author']}\n")
        if article_metadata.get('date'):
            markdown_parts.append(f"**Date:** {article_metadata['date']}\n")
        markdown_parts.append(f"**Source URL:** {url}\n")
        markdown_parts.append("\n---\n\n")
        
        # Add structured content
        markdown_parts.append(content_data['full_text'])
        
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
                safe_title = re.sub(r'[^\w\s-]', '', title)[:50].strip().replace(' ', '_')
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                temp_filename = f"web_{safe_title}_{timestamp}.md"
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as temp_file:
                    temp_file.write(markdown_content)
                    temp_path = temp_file.name
                
                try:
                    # Process document
                    document_data = document_processor.process_document(temp_path)
                    
                    # Update metadata to reflect it's a web document
                    document_data['metadata']['file_name'] = temp_filename
                    document_data['metadata']['file_path'] = temp_path
                    document_data['metadata']['file_type'] = '.md'
                    document_data['metadata']['source_url'] = url
                    document_data['metadata']['source_type'] = 'website'
                    
                    # Generate embeddings
                    chunk_texts = [chunk['text'] for chunk in document_data['chunks']]
                    embeddings = embedding_generator.generate_embeddings_batch(chunk_texts)
                    
                    # Store document
                    doc_id = document_store.store_document(
                        uploaded_by=user_id,
                        document_data=document_data,
                        embeddings=embeddings
                    )
                    
                    logger.info(f"📄 Saved website content as document: {doc_id} ({len(document_data['chunks'])} chunks)")
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                        
            except Exception as e:
                logger.error(f"Error saving website to document store: {e}", exc_info=True)
                # Continue - don't fail the whole operation if saving fails
        
        result = {
            "success": True,
            "url": url,
            "title": title,
            "full_text": content_data['full_text'],
            "sections": content_data.get('sections', []),
            "metadata": article_metadata,
            "text_length": content_data['text_length'],
            "num_sections": len(content_data.get('sections', [])),
            "smart_summary": smart_summary,  # Smart summary if available
            "chunks": chunks,  # Chunks if available
            "has_smart_summary": smart_summary is not None
        }
        
        if doc_id:
            result["doc_id"] = doc_id
            result["saved_to_documents"] = True
            result["message"] = f"Website content saved as document '{temp_filename}' and is now available for RAG queries."
        elif save_to_documents:
            result["saved_to_documents"] = False
            result["warning"] = "Could not save to document store (missing dependencies or error occurred)."
        
        return result
        
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Request timed out. The website may be slow or unavailable.",
            "url": url
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to fetch website: {str(e)}",
            "url": url
        }
    except Exception as e:
        logger.error(f"Error summarizing website {url}: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "url": url
        }

