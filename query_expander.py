"""
Query expansion for better retrieval recall.
Uses simple synonym/keyword expansion optimized for speed.
"""
from typing import List, Set
import re


class QueryExpander:
    """Expand queries with related terms for better recall."""
    
    # Simple synonym/expansion dictionary (can be enhanced with WordNet or embeddings)
    EXPANSIONS = {
        'what': ['which', 'how'],
        'who': ['which person', 'what person'],
        'when': ['what time', 'what date'],
        'where': ['what location', 'what place'],
        'how': ['what method', 'what way'],
        'why': ['what reason', 'what cause'],
        'explain': ['describe', 'detail', 'clarify'],
        'describe': ['explain', 'detail'],
        'define': ['explain', 'describe'],
        'list': ['enumerate', 'name'],
        'show': ['display', 'present'],
        'find': ['locate', 'search', 'discover'],
        'get': ['obtain', 'retrieve', 'fetch'],
        'use': ['utilize', 'employ'],
        'create': ['make', 'generate', 'build'],
        'document': ['file', 'paper', 'text'],
        'information': ['data', 'details', 'facts'],
        'content': ['text', 'information', 'data'],
    }
    
    def expand(self, query: str, max_expansions: int = 3) -> str:
        """
        Expand query with synonyms and related terms.
        
        Args:
            query: Original query
            max_expansions: Maximum number of expansion terms to add
            
        Returns:
            Expanded query
        """
        # Validate input
        if query is None:
            return ""
        
        if not isinstance(query, str):
            query = str(query) if query is not None else ""
        
        # Remove null bytes and clean
        query = query.replace('\x00', '').strip()
        
        if not query:
            return ""
        
        try:
            words = self._tokenize(query.lower())
            expanded_terms = set(words)
            
            # Add expansions for key terms
            for word in words:
                if word in self.EXPANSIONS:
                    expansions = self.EXPANSIONS[word][:max_expansions]
                    expanded_terms.update(expansions)
            
            # Add original query first, then expansions
            expanded_query = query
            if len(expanded_terms) > len(words):
                # Add key expansion terms
                new_terms = expanded_terms - set(words)
                if new_terms:
                    expanded_query = f"{query} {' '.join(list(new_terms)[:max_expansions])}"
            
            # Ensure we return a valid string
            if not isinstance(expanded_query, str):
                expanded_query = str(expanded_query) if expanded_query is not None else query
            
            # Remove null bytes again (in case they were introduced)
            expanded_query = expanded_query.replace('\x00', '').strip()
            
            return expanded_query if expanded_query else query
        except Exception as e:
            # If expansion fails, return original query
            return query
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        text = re.sub(r'[^\w\s]', ' ', text)
        return text.split()

