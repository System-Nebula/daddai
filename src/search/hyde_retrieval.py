"""
HyDE (Hypothetical Document Embeddings) for improved retrieval.
Generates hypothetical answer first, then searches using that answer.
Improves recall for complex/abstract queries.
"""
from typing import List, Dict, Any, Optional
from logger_config import logger


class HyDERetrieval:
    """
    Hypothetical Document Embeddings (HyDE) retrieval.
    Generates a hypothetical answer to the query, then searches using that answer.
    This improves recall for complex queries where the query itself might not match document language.
    """
    
    def __init__(self, llm_client=None, embedding_generator=None):
        """
        Initialize HyDE retrieval.
        
        Args:
            llm_client: LLM client for generating hypothetical answers
            embedding_generator: Embedding generator for creating embeddings
        """
        self.llm_client = llm_client
        self.embedding_generator = embedding_generator
        self.use_hyde = True  # Can be disabled via config
    
    def generate_hypothetical_answer(self, query: str, max_length: int = 200) -> str:
        """
        Generate a hypothetical answer to the query.
        This answer represents what a relevant document might contain.
        
        Args:
            query: User's query
            max_length: Maximum length of hypothetical answer
            
        Returns:
            Hypothetical answer text
        """
        if not self.llm_client:
            logger.warning("No LLM client available for HyDE. Using query as-is.")
            return query
        
        prompt = f"""Given the following question, write a brief hypothetical answer that a relevant document might contain.
The answer should be informative and directly address the question.
Keep it concise (under {max_length} words).

Question: {query}

Hypothetical answer:"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            hypothetical_answer = self.llm_client.generate_response(
                messages=messages,
                temperature=0.7,
                max_tokens=max_length
            )
            
            # Clean up the answer
            hypothetical_answer = hypothetical_answer.strip()
            
            # Remove common prefixes LLMs might add
            prefixes_to_remove = [
                "Hypothetical answer:",
                "Answer:",
                "The hypothetical answer is:",
                "A relevant document might contain:"
            ]
            for prefix in prefixes_to_remove:
                if hypothetical_answer.lower().startswith(prefix.lower()):
                    hypothetical_answer = hypothetical_answer[len(prefix):].strip()
            
            logger.debug(f"Generated hypothetical answer for query: {query[:50]}...")
            return hypothetical_answer
            
        except Exception as e:
            logger.warning(f"Failed to generate hypothetical answer: {e}. Using original query.")
            return query
    
    def retrieve_with_hyde(self,
                          query: str,
                          retrieval_function,
                          top_k: int = 10,
                          use_original_query: bool = True) -> List[Dict[str, Any]]:
        """
        Retrieve documents using HyDE strategy.
        
        Args:
            query: Original query
            retrieval_function: Function that takes (query_embedding, top_k) and returns results
            top_k: Number of results to return
            use_original_query: If True, also search with original query and combine results
            
        Returns:
            Combined results from hypothetical answer and optionally original query
        """
        if not self.use_hyde or not self.embedding_generator:
            # Fallback to regular retrieval
            if self.embedding_generator:
                query_embedding = self.embedding_generator.generate_embedding(query)
                return retrieval_function(query_embedding, top_k)
            else:
                logger.warning("HyDE requires embedding generator. Falling back.")
                return []
        
        try:
            # Step 1: Generate hypothetical answer
            hypothetical_answer = self.generate_hypothetical_answer(query)
            
            # Step 2: Generate embedding for hypothetical answer
            hyde_embedding = self.embedding_generator.generate_embedding(hypothetical_answer)
            
            # Step 3: Retrieve using hypothetical answer embedding
            hyde_results = retrieval_function(hyde_embedding, top_k * 2)  # Get more for combination
            
            # Step 4: Optionally also search with original query
            if use_original_query:
                original_embedding = self.embedding_generator.generate_embedding(query)
                original_results = retrieval_function(original_embedding, top_k * 2)
                
                # Combine results using reciprocal rank fusion
                combined_results = self._combine_results_rrf(hyde_results, original_results, top_k)
                return combined_results
            else:
                return hyde_results[:top_k]
                
        except Exception as e:
            logger.error(f"Error in HyDE retrieval: {e}. Falling back to regular retrieval.")
            # Fallback to regular retrieval
            try:
                query_embedding = self.embedding_generator.generate_embedding(query)
                return retrieval_function(query_embedding, top_k)
            except Exception as e2:
                logger.error(f"Fallback retrieval also failed: {e2}")
                return []
    
    def _combine_results_rrf(self,
                             results1: List[Dict[str, Any]],
                             results2: List[Dict[str, Any]],
                             top_k: int,
                             k: int = 60) -> List[Dict[str, Any]]:
        """
        Combine two result lists using Reciprocal Rank Fusion (RRF).
        
        Args:
            results1: First result list (from HyDE)
            results2: Second result list (from original query)
            top_k: Number of final results to return
            k: RRF constant (typically 60)
            
        Returns:
            Combined and ranked results
        """
        from collections import defaultdict
        
        # Track scores by chunk_id
        chunk_scores = defaultdict(float)
        chunk_data = {}
        
        # Process first result set (HyDE)
        for rank, result in enumerate(results1, start=1):
            chunk_id = result.get("chunk_id") or result.get("id") or f"hyde_{rank}"
            rrf_score = 1.0 / (k + rank)
            chunk_scores[chunk_id] += rrf_score * 1.2  # Slight boost for HyDE results
            if chunk_id not in chunk_data:
                chunk_data[chunk_id] = result.copy()
        
        # Process second result set (original query)
        for rank, result in enumerate(results2, start=1):
            chunk_id = result.get("chunk_id") or result.get("id") or f"original_{rank}"
            rrf_score = 1.0 / (k + rank)
            chunk_scores[chunk_id] += rrf_score
            if chunk_id not in chunk_data:
                chunk_data[chunk_id] = result.copy()
            else:
                # Keep the one with higher original score
                if result.get("score", 0) > chunk_data[chunk_id].get("score", 0):
                    chunk_data[chunk_id] = result.copy()
        
        # Create combined results sorted by RRF score
        combined = []
        for chunk_id, rrf_score in sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True):
            chunk = chunk_data[chunk_id].copy()
            chunk["rrf_score"] = rrf_score
            chunk["final_score"] = rrf_score
            combined.append(chunk)
        
        return combined[:top_k]

