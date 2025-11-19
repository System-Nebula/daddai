"""
Semantic chunking module for intelligent document chunking.
Chunks documents by meaning rather than fixed size for better context preservation.
"""
from typing import List, Dict, Any, Optional
import re
from logger_config import logger

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter, SemanticChunker
    from langchain.embeddings import HuggingFaceEmbeddings
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain not available. Falling back to sentence-based chunking.")


class SemanticChunker:
    """
    Semantic chunker that splits text by meaning rather than fixed size.
    Falls back to recursive chunking if semantic chunking unavailable.
    """
    
    def __init__(self, 
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 use_semantic: bool = True,
                 embedding_model_name: Optional[str] = None):
        """
        Initialize semantic chunker.
        
        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
            use_semantic: Whether to use semantic chunking (requires langchain)
            embedding_model_name: Embedding model for semantic chunking
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.use_semantic = use_semantic and LANGCHAIN_AVAILABLE
        
        if self.use_semantic:
            try:
                # Use lightweight embedding model for chunking
                embedding_model = embedding_model_name or "sentence-transformers/all-MiniLM-L6-v2"
                embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
                self.semantic_chunker = SemanticChunker(
                    embeddings=embeddings,
                    breakpoint_threshold_type="percentile",
                    breakpoint_threshold_amount=95
                )
                logger.info(f"✅ Semantic chunker initialized with {embedding_model}")
            except Exception as e:
                logger.warning(f"Failed to initialize semantic chunker: {e}. Falling back to recursive chunking.")
                self.use_semantic = False
        
        if not self.use_semantic:
            # Fallback to recursive chunking
            if LANGCHAIN_AVAILABLE:
                self.recursive_chunker = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    separators=["\n\n", "\n", ". ", " ", ""]
                )
            logger.info("Using recursive character chunking")
    
    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Chunk text semantically or recursively.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text or not text.strip():
            return []
        
        chunks = []
        
        if self.use_semantic:
            try:
                # Use semantic chunking
                semantic_chunks = self.semantic_chunker.create_documents([text])
                for i, chunk in enumerate(semantic_chunks):
                    chunks.append({
                        "text": chunk.page_content,
                        "chunk_index": i,
                        "chunk_type": "semantic",
                        "metadata": chunk.metadata
                    })
                logger.debug(f"Created {len(chunks)} semantic chunks")
                return chunks
            except Exception as e:
                logger.warning(f"Semantic chunking failed: {e}. Falling back to recursive chunking.")
        
        # Fallback to recursive or sentence-based chunking
        if LANGCHAIN_AVAILABLE and hasattr(self, 'recursive_chunker'):
            try:
                recursive_chunks = self.recursive_chunker.create_documents([text])
                for i, chunk in enumerate(recursive_chunks):
                    chunks.append({
                        "text": chunk.page_content,
                        "chunk_index": i,
                        "chunk_type": "recursive",
                        "metadata": chunk.metadata
                    })
                return chunks
            except Exception as e:
                logger.warning(f"Recursive chunking failed: {e}. Falling back to sentence-based chunking.")
        
        # Final fallback: sentence-based chunking
        return self._sentence_based_chunking(text)
    
    def _sentence_based_chunking(self, text: str) -> List[Dict[str, Any]]:
        """Fallback sentence-based chunking."""
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks = []
        current_chunk = []
        current_length = 0
        overlap_sentences = []
        overlap_sentence_count = max(1, int(self.chunk_overlap / 100))
        
        for i, sentence in enumerate(sentences):
            sentence_length = len(sentence.split())
            
            if current_length + sentence_length > self.chunk_size and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "text": chunk_text,
                    "chunk_index": len(chunks),
                    "chunk_type": "sentence",
                    "start_sentence": i - len(current_chunk),
                    "end_sentence": i
                })
                
                overlap_sentences = current_chunk[-overlap_sentence_count:] if len(current_chunk) >= overlap_sentence_count else current_chunk
                current_chunk = overlap_sentences.copy()
                current_length = sum(len(s.split()) for s in current_chunk)
            
            current_chunk.append(sentence)
            current_length += sentence_length
        
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "chunk_index": len(chunks),
                "chunk_type": "sentence",
                "start_sentence": len(sentences) - len(current_chunk),
                "end_sentence": len(sentences)
            })
        
        return chunks

