"""
Smart document selector that determines:
- When to search documents vs when not to
- Which documents to search
- Document relevance to queries
"""
from typing import List, Dict, Any, Optional, Set
import re
from document_store import DocumentStore
from knowledge_graph import KnowledgeGraph
from embedding_generator import EmbeddingGenerator
from config import USE_GPU, EMBEDDING_BATCH_SIZE
from logger_config import logger


class SmartDocumentSelector:
    """
    Intelligently determines when and which documents to search.
    Uses query analysis, document metadata, and knowledge graph.
    """
    
    def __init__(self):
        """Initialize smart document selector."""
        self.document_store = DocumentStore()
        self.knowledge_graph = KnowledgeGraph()
        device = USE_GPU if USE_GPU != 'auto' else None
        self.embedding_generator = EmbeddingGenerator(device=device, batch_size=EMBEDDING_BATCH_SIZE)
    
    def should_search_documents(self, query: str, context: Dict[str, Any] = None) -> bool:
        """
        Determine if documents should be searched for this query.
        
        Returns False for:
        - Casual conversation ("hi", "hello", "thanks")
        - User state queries that don't need documents ("how much gold do I have?")
        - Commands/actions that modify state
        - Questions about users (unless documents are mentioned)
        
        Returns True for:
        - Questions about documents
        - Questions that might need document context
        - Queries explicitly mentioning documents
        """
        query_lower = query.lower().strip()
        
        # Don't search for casual conversation
        casual_patterns = [
            r'^(hi|hello|hey|thanks|thank you|bye|goodbye)[\s!.,]*$',
            r'^(how are you|how\'s it going|what\'s up)[\s?.,]*$'
        ]
        for pattern in casual_patterns:
            if re.match(pattern, query_lower):
                return False
        
        # Don't search for pure state queries (unless documents mentioned)
        state_query_patterns = [
            r'how (much|many) (gold|coins|items?) (do|does) (i|you|he|she|they|@\w+) (have|own)',
            r'what (is|are) (my|your|his|her|their|@\w+\'s) (gold|coins|inventory|items?)',
            r'(i|you|he|she|they|@\w+) (have|has|owns) (how much|how many)'
        ]
        
        mentions_document = any(word in query_lower for word in ['document', 'doc', 'file', 'pdf', 'text'])
        
        for pattern in state_query_patterns:
            if re.search(pattern, query_lower) and not mentions_document:
                return False
        
        # Don't search for pure action commands
        action_patterns = [
            r'^(give|take|set|add|remove)',
            r'^transfer'
        ]
        for pattern in action_patterns:
            if re.match(pattern, query_lower):
                return False
        
        # Search for document-related queries
        document_patterns = [
            r'(document|doc|file|pdf|text|article|paper)',
            r'(what|tell me|explain|describe|summarize).*(document|doc|file)',
            r'in (the|this|that) (document|doc|file)',
            r'from (the|this|that) (document|doc|file)'
        ]
        for pattern in document_patterns:
            if re.search(pattern, query_lower):
                return True
        
        # Search for informational queries (likely need documents)
        informational_patterns = [
            r'^(what|who|when|where|why|how|which|tell me|explain|describe|summarize)',
            r'^(list|show|find|search|get)'
        ]
        for pattern in informational_patterns:
            if re.search(pattern, query_lower):
                return True
        
        # Default: search documents (better to have context than not)
        return True
    
    def select_relevant_documents(self,
                                 query: str,
                                 query_embedding: List[float],
                                 context: Dict[str, Any] = None,
                                 max_docs: int = 5) -> List[Dict[str, Any]]:
        """
        Select which documents are most relevant to the query.
        
        Uses:
        - Semantic similarity
        - Document metadata (filename, topics)
        - Knowledge graph relationships
        - User document history
        """
        # Extract document references from query
        doc_references = self._extract_document_references(query)
        
        # If specific documents mentioned, prioritize them
        if doc_references:
            return self._get_specific_documents(doc_references, max_docs)
        
        # Get all documents
        all_docs = self.document_store.get_all_shared_documents()
        
        if not all_docs:
            return []
        
        # Score documents by relevance
        scored_docs = []
        
        for doc in all_docs:
            score = 0.0
            
            # Factor 1: Filename match
            filename = doc.get("file_name", "").lower()
            query_lower = query.lower()
            if any(word in filename for word in query_lower.split()):
                score += 0.3
            
            # Factor 2: User document history (if user_id provided)
            if context and context.get("user_id"):
                user_history = self.knowledge_graph.get_user_document_history(
                    context["user_id"],
                    limit=20
                )
                if any(h["doc_id"] == doc["id"] for h in user_history):
                    score += 0.2
            
            # Factor 3: Topic relevance (if knowledge graph has topics)
            doc_id = doc.get("id")
            if doc_id:
                try:
                    # Check if document topics match query
                    topics = self._get_document_topics(doc_id)
                    query_words = set(query_lower.split())
                    for topic in topics:
                        if any(word in topic.lower() for word in query_words):
                            score += 0.2
                            break
                except:
                    pass
            
            scored_docs.append({
                **doc,
                "relevance_score": score
            })
        
        # Use semantic similarity for top candidates
        if len(scored_docs) > max_docs:
            # Get top candidates by filename/topic match
            scored_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
            top_candidates = scored_docs[:max_docs * 2]
            
            # Re-score with semantic similarity
            for doc in top_candidates:
                doc_id = doc.get("id")
                if doc_id:
                    # Get document chunks and compute similarity
                    chunks = self.document_store.get_document_chunks(doc_id)
                    if chunks:
                        # Use first chunk as document representation
                        chunk_text = chunks[0].get("text", "")
                        if chunk_text:
                            try:
                                chunk_embedding = self.embedding_generator.generate_embedding(chunk_text[:500])
                                similarity = self._cosine_similarity(query_embedding, chunk_embedding)
                                doc["relevance_score"] += similarity * 0.5
                            except Exception as e:
                                logger.debug(f"Error computing similarity: {e}")
        
        # Sort by relevance and return top docs
        scored_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored_docs[:max_docs]
    
    def _extract_document_references(self, query: str) -> List[str]:
        """Extract document references from query."""
        references = []
        
        # Pattern: "in document X", "from file Y", "document named X"
        patterns = [
            r'(?:in|from|document|file|doc)\s+(?:named|called|titled)?\s+["\']?([^"\']+)["\']?',
            r'document\s+["\']([^"\']+)["\']',
            r'file\s+["\']([^"\']+)["\']'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            references.extend(matches)
        
        return [ref.strip() for ref in references if ref.strip()]
    
    def _get_specific_documents(self, doc_references: List[str], max_docs: int) -> List[Dict[str, Any]]:
        """Get specific documents by filename."""
        all_docs = self.document_store.get_all_shared_documents()
        
        found_docs = []
        for ref in doc_references[:max_docs]:
            ref_lower = ref.lower()
            for doc in all_docs:
                filename = doc.get("file_name", "").lower()
                if ref_lower in filename or filename in ref_lower:
                    found_docs.append(doc)
                    break
        
        return found_docs
    
    def _get_document_topics(self, doc_id: str) -> List[str]:
        """Get topics associated with a document."""
        try:
            # This would query the knowledge graph for document topics
            # For now, return empty list (can be enhanced)
            return []
        except:
            return []
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity."""
        import numpy as np
        
        vec1_arr = np.array(vec1, dtype=np.float32)
        vec2_arr = np.array(vec2, dtype=np.float32)
        
        dot_product = np.dot(vec1_arr, vec2_arr)
        norm1 = np.linalg.norm(vec1_arr)
        norm2 = np.linalg.norm(vec2_arr)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def close(self):
        """Close connections."""
        self.document_store.close()
        self.knowledge_graph.close()

