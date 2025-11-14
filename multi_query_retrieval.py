"""
Multi-query retrieval for improved recall.
Generates multiple query variations and combines results using reciprocal rank fusion.
"""
from typing import List, Dict, Any, Optional
import numpy as np
from collections import defaultdict
from lmstudio_client import LMStudioClient
from logger_config import logger


class MultiQueryRetrieval:
    """
    State-of-the-art multi-query retrieval.
    Generates multiple query variations and combines results for better recall.
    """
    
    def __init__(self):
        """Initialize multi-query retrieval."""
        self.llm_client = LMStudioClient()
        # Cache for query variations
        from cachetools import TTLCache
        self._variation_cache = TTLCache(maxsize=500, ttl=3600)  # 1 hour cache
    
    def generate_query_variations(self, query: str, num_variations: int = 3, use_cache: bool = True) -> List[str]:
        """
        Generate multiple query variations using LLM.
        
        Args:
            query: Original query
            num_variations: Number of variations to generate
            
        Returns:
            List of query variations (including original)
        """
        if num_variations <= 1:
            return [query]
        
        # Check cache first (if enabled)
        if use_cache and hasattr(self, '_variation_cache'):
            cached = self._variation_cache.get(query)
            if cached:
                return cached[:num_variations]
        
        prompt = f"""Generate {num_variations} different ways to ask the same question.
Each variation should:
- Use different wording
- Focus on different aspects
- Use synonyms or related terms
- Maintain the same core intent

Original query: "{query}"

Respond with ONLY the {num_variations} variations, one per line, no numbering or bullets.
Each variation should be a complete, natural question.
"""
        
        try:
            response = self.llm_client.generate_response(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200
            )
            
            # Parse variations from response
            variations = [line.strip() for line in response.strip().split('\n') if line.strip()]
            
            # Filter out empty or too short variations
            variations = [v for v in variations if len(v) > 10]
            
            # Ensure we have at least the original query
            if query not in variations:
                variations.insert(0, query)
            else:
                # Move original to front
                variations.remove(query)
                variations.insert(0, query)
            
            # Limit to requested number
            variations = variations[:num_variations]
            
            # Cache variations
            if use_cache:
                if not hasattr(self, '_variation_cache'):
                    from cachetools import TTLCache
                    self._variation_cache = TTLCache(maxsize=500, ttl=3600)
                self._variation_cache[query] = variations
            
            logger.debug(f"Generated {len(variations)} query variations")
            return variations
            
        except Exception as e:
            logger.warning(f"Failed to generate query variations: {e}. Using original query only.")
            return [query]
    
    def reciprocal_rank_fusion(self,
                              query_results: List[List[Dict[str, Any]]],
                              k: int = 60) -> List[Dict[str, Any]]:
        """
        Combine multiple query results using Reciprocal Rank Fusion (RRF).
        
        RRF formula: score = sum(1 / (k + rank)) for each query result
        
        Args:
            query_results: List of result lists, one per query variation
            k: RRF constant (typically 60)
            
        Returns:
            Combined and ranked results
        """
        # Track scores by chunk_id
        chunk_scores = defaultdict(float)
        chunk_data = {}
        
        # Process each query's results
        for query_idx, results in enumerate(query_results):
            for rank, result in enumerate(results, start=1):
                chunk_id = result.get("chunk_id") or result.get("id") or f"{query_idx}_{rank}"
                
                # RRF score
                rrf_score = 1.0 / (k + rank)
                chunk_scores[chunk_id] += rrf_score
                
                # Store chunk data (use first occurrence or best score)
                if chunk_id not in chunk_data:
                    chunk_data[chunk_id] = result.copy()
                else:
                    # Keep the one with higher original score
                    if result.get("score", 0) > chunk_data[chunk_id].get("score", 0):
                        chunk_data[chunk_id] = result.copy()
        
        # Create combined results
        combined = []
        for chunk_id, rrf_score in sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True):
            chunk = chunk_data[chunk_id].copy()
            chunk["rrf_score"] = rrf_score
            chunk["final_score"] = rrf_score  # Use RRF as final score
            combined.append(chunk)
        
        return combined
    
    def retrieve_multi_query(self,
                            query: str,
                            retrieval_function,
                            num_variations: int = 3,
                            top_k_per_query: int = 20,
                            final_top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Perform multi-query retrieval.
        
        Args:
            query: Original query
            retrieval_function: Function that takes (query, top_k) and returns results
            num_variations: Number of query variations to generate
            top_k_per_query: How many results to retrieve per query
            final_top_k: Final number of results to return
            
        Returns:
            Combined and ranked results
        """
        # Generate query variations
        variations = self.generate_query_variations(query, num_variations)
        
        # Retrieve for each variation
        all_results = []
        for variation in variations:
            try:
                results = retrieval_function(variation, top_k_per_query)
                all_results.append(results)
            except Exception as e:
                logger.warning(f"Error retrieving for variation '{variation}': {e}")
                continue
        
        if not all_results:
            logger.warning("No results from any query variation. Falling back to original query.")
            try:
                results = retrieval_function(query, top_k_per_query)
                return results[:final_top_k]
            except Exception as e:
                logger.error(f"Error in fallback retrieval: {e}")
                return []
        
        # Combine using RRF
        combined = self.reciprocal_rank_fusion(all_results)
        
        # Return top k
        return combined[:final_top_k]

