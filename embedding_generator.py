"""
Embedding generation module using sentence transformers.
Generates vector embeddings for document chunks with GPU acceleration.
"""
from typing import List
import numpy as np
import torch
from sentence_transformers import SentenceTransformer


class EmbeddingGenerator:
    """Generate embeddings for text chunks using local models with GPU acceleration."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = None, batch_size: int = None):
        """
        Initialize the embedding generator.
        
        Args:
            model_name: Name of the sentence transformer model to use
            device: Device to use ('cuda', 'cpu', or None for auto-detect)
            batch_size: Batch size for processing (None for auto-detect based on device)
        """
        import sys
        
        # Auto-detect device if not specified
        if device is None:
            if torch.cuda.is_available():
                device = 'cuda'
                print(f"GPU detected: {torch.cuda.get_device_name(0)}", file=sys.stderr)
                print(f"CUDA version: {torch.version.cuda}", file=sys.stderr)
            else:
                device = 'cpu'
                print("No GPU detected, using CPU", file=sys.stderr)
        
        self.device = device
        print(f"Loading embedding model: {model_name} on {device}", file=sys.stderr)
        
        # Load model on specified device
        self.model = SentenceTransformer(model_name, device=device)
        self.embedding_dimension = self.model.get_sentence_embedding_dimension()
        
        # Set optimal batch size based on device
        if batch_size is None:
            if device == 'cuda':
                # RTX 3080 has 10GB VRAM, use larger batches
                self.batch_size = 64
            else:
                self.batch_size = 16
        else:
            self.batch_size = batch_size
        
        print(f"Embedding dimension: {self.embedding_dimension}", file=sys.stderr)
        print(f"Batch size: {self.batch_size}", file=sys.stderr)
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of float values representing the embedding
        """
        # Validate and sanitize input
        if text is None:
            raise ValueError("Text cannot be None")
        
        # Ensure text is a string
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
        
        # Remove any null bytes or invalid characters
        text = text.replace('\x00', '').strip()
        
        # Remove Discord mentions and other special formatting that might confuse tokenizer
        import re
        text = re.sub(r'<@!?\d+>', '', text)  # Remove user mentions
        text = re.sub(r'<@&\d+>', '', text)   # Remove role mentions
        text = re.sub(r'<#\d+>', '', text)    # Remove channel mentions
        text = re.sub(r'<:\w+:\d+>', '', text)  # Remove custom emojis
        text = re.sub(r'<a:\w+:\d+>', '', text)  # Remove animated emojis
        text = re.sub(r'https?://[^\s]+', '', text)  # Remove URLs
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Ensure text is not empty
        if not text:
            raise ValueError("Text cannot be empty after cleaning")
        
        # Truncate very long texts (sentence transformers work best with shorter texts)
        # For queries, we want to keep them reasonable (max 2000 chars)
        # For document chunks, we can allow more (up to 10000 chars)
        max_length = 2000 if len(text) < 5000 else 10000
        if len(text) > max_length:
            text = text[:max_length]
            import warnings
            warnings.warn(f"Text truncated to {max_length} characters for embedding")
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True, device=self.device)
            return embedding.tolist()
        except Exception as e:
            raise ValueError(f"Error generating embedding: {e}. Text type: {type(text)}, Text length: {len(text) if text else 0}, Text preview: {str(text)[:100] if text else 'None'}")
    
    def generate_embeddings_batch(self, texts: List[str], batch_size: int = None) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently using GPU batching.
        
        Args:
            texts: List of texts to embed
            batch_size: Override default batch size
            
        Returns:
            List of embeddings
        """
        if not texts:
            return []
        
        # Validate and sanitize inputs
        sanitized_texts = []
        for i, text in enumerate(texts):
            if text is None:
                raise ValueError(f"Text at index {i} cannot be None")
            
            # Ensure text is a string
            if not isinstance(text, str):
                text = str(text) if text is not None else ""
            
            # Remove null bytes and invalid characters
            text = text.replace('\x00', '').strip()
            
            # Skip empty texts but warn
            if not text:
                import warnings
                warnings.warn(f"Empty text at index {i}, skipping")
                sanitized_texts.append(" ")  # Use space as placeholder
            else:
                # Truncate if too long
                if len(text) > 100000:
                    text = text[:100000]
                sanitized_texts.append(text)
        
        if not sanitized_texts:
            raise ValueError("No valid texts to embed")
        
        bs = batch_size if batch_size else self.batch_size
        
        try:
            embeddings = self.model.encode(
                sanitized_texts, 
                convert_to_numpy=True, 
                show_progress_bar=True,
                batch_size=bs,
                device=self.device,
                normalize_embeddings=True  # Normalize for better cosine similarity
            )
            return embeddings.tolist()
        except Exception as e:
            raise ValueError(f"Error generating batch embeddings: {e}. Text count: {len(sanitized_texts)}, First text type: {type(sanitized_texts[0]) if sanitized_texts else None}, First text length: {len(sanitized_texts[0]) if sanitized_texts else 0}")
    
    def get_dimension(self) -> int:
        """Get the dimension of embeddings."""
        return self.embedding_dimension
    
    def is_gpu_available(self) -> bool:
        """Check if GPU is being used."""
        return self.device == 'cuda' and torch.cuda.is_available()
