"""
Query rewriting for improved retrieval.
Rewrites queries to be more effective for document search.
"""
from typing import Optional
from logger_config import logger


class QueryRewriter:
    """
    Query rewriter that improves queries for better retrieval.
    Different from query expansion - rewriting changes the query structure.
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize query rewriter.
        
        Args:
            llm_client: LLM client for rewriting queries
        """
        self.llm_client = llm_client
        self.use_rewriting = True
    
    def rewrite_query(self, query: str, context: Optional[str] = None) -> str:
        """
        Rewrite query to be more effective for retrieval.
        
        Args:
            query: Original query
            context: Optional context about what the user is looking for
            
        Returns:
            Rewritten query
        """
        if not self.use_rewriting or not self.llm_client:
            return query
        
        # Simple queries don't need rewriting
        if len(query.split()) <= 3:
            return query
        
        prompt = f"""Rewrite the following search query to be more effective for finding relevant documents.
The rewritten query should:
- Use more specific, searchable terms
- Include synonyms or related concepts
- Be clear and unambiguous
- Maintain the original intent

Original query: {query}
{f'Context: {context}' if context else ''}

Rewritten query:"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            rewritten = self.llm_client.generate_response(
                messages=messages,
                temperature=0.3,  # Lower temperature for more consistent rewriting
                max_tokens=100
            )
            
            # Clean up the rewritten query
            rewritten = rewritten.strip()
            
            # Remove common prefixes
            prefixes_to_remove = [
                "Rewritten query:",
                "Query:",
                "Rewritten:",
                "Improved query:"
            ]
            for prefix in prefixes_to_remove:
                if rewritten.lower().startswith(prefix.lower()):
                    rewritten = rewritten[len(prefix):].strip()
            
            # Ensure we got something reasonable
            if len(rewritten) < 5 or len(rewritten) > 500:
                logger.warning(f"Rewritten query seems invalid: {rewritten[:50]}. Using original.")
                return query
            
            logger.debug(f"Rewrote query: '{query[:50]}...' -> '{rewritten[:50]}...'")
            return rewritten
            
        except Exception as e:
            logger.warning(f"Failed to rewrite query: {e}. Using original query.")
            return query
    
    def rewrite_for_document_search(self, query: str) -> str:
        """
        Rewrite query specifically for document search.
        Focuses on making queries more document-search friendly.
        
        Args:
            query: Original query
            
        Returns:
            Rewritten query optimized for document search
        """
        if not self.llm_client:
            return query
        
        prompt = f"""Rewrite this query to be optimal for searching through documents.
The rewritten query should:
- Use keywords and phrases that appear in documents
- Include technical terms and proper nouns
- Be specific rather than vague
- Use document-friendly language

Query: {query}

Rewritten query for document search:"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            rewritten = self.llm_client.generate_response(
                messages=messages,
                temperature=0.3,
                max_tokens=100
            )
            
            rewritten = rewritten.strip()
            
            # Remove prefixes
            for prefix in ["Rewritten query for document search:", "Rewritten:", "Query:"]:
                if rewritten.lower().startswith(prefix.lower()):
                    rewritten = rewritten[len(prefix):].strip()
            
            if len(rewritten) < 5:
                return query
            
            return rewritten
            
        except Exception as e:
            logger.warning(f"Failed to rewrite query for document search: {e}")
            return query

