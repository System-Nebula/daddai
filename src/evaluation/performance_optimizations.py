"""
Performance optimizations for RAG system.
Includes caching, early exits, and parallel processing improvements.
"""
from typing import Dict, Any, Optional, List
from cachetools import TTLCache
from functools import lru_cache
import time
from logger_config import logger


class PerformanceOptimizer:
    """
    Performance optimization utilities for RAG system.
    """
    
    def __init__(self):
        """Initialize performance optimizer."""
        # Cache for query variations (multi-query)
        self.query_variation_cache = TTLCache(maxsize=500, ttl=3600)  # 1 hour
        
        # Cache for persona identification
        self.persona_cache = TTLCache(maxsize=1000, ttl=1800)  # 30 minutes
        
        # Cache for query analysis
        self.analysis_cache = TTLCache(maxsize=1000, ttl=1800)  # 30 minutes
    
    def get_cached_query_variations(self, query: str) -> Optional[List[str]]:
        """Get cached query variations."""
        return self.query_variation_cache.get(query)
    
    def cache_query_variations(self, query: str, variations: List[str]):
        """Cache query variations."""
        self.query_variation_cache[query] = variations
    
    def get_cached_persona(self, user_id: str, message_hash: str) -> Optional[str]:
        """Get cached persona ID."""
        cache_key = f"{user_id}_{message_hash}"
        return self.persona_cache.get(cache_key)
    
    def cache_persona(self, user_id: str, message_hash: str, persona_id: str):
        """Cache persona ID."""
        cache_key = f"{user_id}_{message_hash}"
        self.persona_cache[cache_key] = persona_id
    
    def should_use_multi_query(self, query: str, complexity: str, retrieved_count: int, top_k: int) -> bool:
        """
        Determine if multi-query retrieval should be used.
        More conservative to avoid unnecessary LLM calls.
        """
        # Only use for truly complex queries
        if complexity != "complex":
            return False
        
        # Only if we don't have enough results
        if retrieved_count >= top_k * 2:
            return False
        
        # Skip for very short queries (likely simple)
        if len(query.split()) < 5:
            return False
        
        return True
    
    def should_use_cross_encoder(self, candidates_count: int, top_k: int) -> bool:
        """
        Determine if cross-encoder reranking should be used.
        Only rerank if we have enough candidates to benefit.
        """
        # Only rerank if we have significantly more candidates than needed
        if candidates_count <= top_k * 1.5:
            return False
        
        # Limit reranking to reasonable number (cross-encoder can be slow)
        if candidates_count > 100:
            return False  # Too many candidates, will be slow
        
        return True
    
    def optimize_cross_encoder_candidates(self, candidates: List[Dict[str, Any]], max_candidates: int = 50) -> List[Dict[str, Any]]:
        """
        Optimize candidates before cross-encoder reranking.
        Pre-filter to top candidates to speed up reranking.
        """
        if len(candidates) <= max_candidates:
            return candidates
        
        # Pre-sort by existing score and take top candidates
        sorted_candidates = sorted(candidates, key=lambda x: x.get("score", 0.0), reverse=True)
        return sorted_candidates[:max_candidates]
    
    def should_use_llm_rewrite(self, query: str, analysis: Dict[str, Any]) -> bool:
        """
        Determine if LLM-based query rewriting should be used.
        Skip for simple queries to save time.
        """
        # Skip if query is already good
        if analysis.get("suggested_rewrite"):
            return False  # Already have rewrite from analysis
        
        # Skip for very simple queries
        complexity = analysis.get("complexity", "simple")
        if complexity == "simple":
            return False
        
        # Skip for very short queries
        if len(query.split()) < 4:
            return False
        
        return True

