"""
Cross-encoder re-ranking for state-of-the-art retrieval accuracy.
Uses dedicated cross-encoder models for superior re-ranking performance.
"""
from typing import List, Dict, Any, Optional
import numpy as np
from logger_config import logger

try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    logger.warning("sentence-transformers not available for cross-encoder. Install with: pip install sentence-transformers")


class CrossEncoderReranker:
    """
    State-of-the-art cross-encoder re-ranking.
    Cross-encoders are significantly more accurate than bi-encoders for re-ranking.
    """
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", lazy_load: bool = True):
        """
        Initialize cross-encoder reranker.
        Uses faster model by default for better performance.
        
        Args:
            model_name: Cross-encoder model name
                - "cross-encoder/ms-marco-MiniLM-L-6-v2" (default, fastest)
                - "BAAI/bge-reranker-base" (better accuracy, slower)
                - "BAAI/bge-reranker-large" (best accuracy, slowest)
            lazy_load: If True, load model on first use (faster startup). If False, load immediately.
        """
        self.model_name = model_name
        self.model = None
        self._model_loaded = False
        self.lazy_load = lazy_load
        
        if not lazy_load:
            self._load_model()
    
    def _load_model(self):
        """Load cross-encoder model (lazy loading)."""
        if self._model_loaded:
            return
        
        if not CROSS_ENCODER_AVAILABLE:
            logger.warning("Cross-encoder not available. Falling back to bi-encoder re-ranking.")
            self._model_loaded = True
            return
        
        try:
            logger.info(f"Loading cross-encoder model: {self.model_name}")
            self.model = CrossEncoder(self.model_name, max_length=512)
            logger.info("Cross-encoder model loaded successfully")
            self._model_loaded = True
        except Exception as e:
            logger.error(f"Failed to load cross-encoder model: {e}")
            logger.warning("Will fall back to bi-encoder re-ranking")
            self.model = None
            self._model_loaded = True
    
    def rerank(self,
               query: str,
               candidates: List[Dict[str, Any]],
               top_k: Optional[int] = None,
               max_candidates: int = 50) -> List[Dict[str, Any]]:
        """
        Re-rank candidates using cross-encoder.
        Optimized for speed by limiting candidates.
        
        Args:
            query: Query text
            candidates: List of candidate chunks with 'text' field
            top_k: Return top k results (None = return all)
            max_candidates: Maximum candidates to rerank (for speed)
            
        Returns:
            Re-ranked list of candidates with 'rerank_score' field
        """
        # Lazy load model on first use
        if not self._model_loaded:
            self._load_model()
        
        if not self.model or not candidates:
            # Fallback to original scores
            return candidates[:top_k] if top_k else candidates
        
        try:
            # Optimize: Only rerank top candidates for speed
            if len(candidates) > max_candidates:
                # Pre-sort by existing score
                sorted_candidates = sorted(candidates, key=lambda x: x.get("score", 0.0), reverse=True)
                candidates_to_rerank = sorted_candidates[:max_candidates]
                # Keep rest for later merging
                remaining_candidates = sorted_candidates[max_candidates:]
            else:
                candidates_to_rerank = candidates
                remaining_candidates = []
            
            # Prepare pairs for cross-encoder (limit text length for speed)
            pairs = []
            for candidate in candidates_to_rerank:
                text = candidate.get("text", "")
                # Truncate text to 400 chars for faster processing
                if len(text) > 400:
                    text = text[:400] + "..."
                pairs.append([query, text])
            
            # Get scores from cross-encoder (batch processing)
            scores = self.model.predict(pairs, show_progress_bar=False, batch_size=32)
            
            # Add rerank scores to candidates
            reranked = []
            for candidate, score in zip(candidates_to_rerank, scores):
                candidate_copy = candidate.copy()
                candidate_copy["rerank_score"] = float(score)
                # Combine original score with rerank score (weighted)
                original_score = candidate.get("score", 0.0)
                candidate_copy["final_score"] = 0.7 * float(score) + 0.3 * original_score
                reranked.append(candidate_copy)
            
            # Merge with remaining candidates (with lower scores)
            for candidate in remaining_candidates:
                candidate_copy = candidate.copy()
                candidate_copy["final_score"] = candidate.get("score", 0.0) * 0.5  # Penalize non-reranked
                reranked.append(candidate_copy)
            
            # Sort by final score
            reranked.sort(key=lambda x: x["final_score"], reverse=True)
            
            # Return top k
            if top_k:
                return reranked[:top_k]
            
            return reranked
            
        except Exception as e:
            logger.error(f"Error in cross-encoder reranking: {e}")
            # Fallback to original ranking
            return candidates[:top_k] if top_k else candidates
    
    def is_available(self) -> bool:
        """Check if cross-encoder is available."""
        return self.model is not None


class FallbackReranker:
    """
    Fallback reranker using bi-encoder similarity when cross-encoder unavailable.
    """
    
    def __init__(self):
        """Initialize fallback reranker."""
        pass
    
    def rerank(self,
               query: str,
               candidates: List[Dict[str, Any]],
               top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fallback re-ranking using existing scores.
        
        Args:
            query: Query text (not used in fallback)
            candidates: List of candidates
            top_k: Return top k results
            
        Returns:
            Sorted candidates
        """
        # Sort by existing score
        sorted_candidates = sorted(candidates, key=lambda x: x.get("score", 0.0), reverse=True)
        
        if top_k:
            return sorted_candidates[:top_k]
        
        return sorted_candidates

