"""
Smart document selector that determines:
- When to search documents vs when not to
- Which documents to search
- Document relevance to queries
Uses HybridDocumentStore for Elasticsearch support if enabled.
"""
from typing import List, Dict, Any, Optional, Set
import re
from config import ELASTICSEARCH_ENABLED, USE_GPU, EMBEDDING_BATCH_SIZE
from logger_config import logger

# Try to use hybrid store if Elasticsearch is enabled
try:
    from src.stores.hybrid_document_store import HybridDocumentStore
    HYBRID_STORE_AVAILABLE = True
except ImportError:
    HYBRID_STORE_AVAILABLE = False

from src.stores.document_store import DocumentStore
from src.utils.knowledge_graph import KnowledgeGraph
from src.processors.embedding_generator import EmbeddingGenerator


class SmartDocumentSelector:
    """
    Intelligently determines when and which documents to search.
    Uses query analysis, document metadata, and knowledge graph.
    """
    
    def __init__(self, document_store=None, embedding_generator=None):
        """Initialize smart document selector."""
        # Use provided stores if available, otherwise create new ones
        if document_store is not None:
            self.document_store = document_store
        elif ELASTICSEARCH_ENABLED and HYBRID_STORE_AVAILABLE:
            try:
                self.document_store = HybridDocumentStore()
            except Exception as e:
                logger.warning(f"Failed to initialize HybridDocumentStore, using regular DocumentStore: {e}")
                self.document_store = DocumentStore()
        else:
            self.document_store = DocumentStore()
        self.knowledge_graph = KnowledgeGraph()
        if embedding_generator is not None:
            self.embedding_generator = embedding_generator
        else:
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
        
        # Remove mentions for pattern matching (they don't affect casual conversation detection)
        query_without_mentions = re.sub(r'<@!?\d+>', '', query_lower).strip()
        
        # Don't search for casual conversation
        casual_patterns = [
            r'^(hi|hello|hey|heyya|heya|thanks|thank you|bye|goodbye)[\s!.,]*$',
            r'^(hi|hello|hey|heyya|heya)\s+(there|everyone|all|guys|folks|@\w+)[\s!.,]*$',
            r'^(how are you|how\'s it going|what\'s up|whats up|sup|wassup)[\s?.,]*$',
            r'^(how are you|how\'s it going|what\'s up|whats up)\s+(doing|going|today)[\s?.,]*$',
            # Thanks and compliments
            r'^(thanks|thank you|thx|ty)[\s!.,]*$',
            r'thanks\s+(so\s+)?much',
            r'thank\s+you\s+(so\s+)?much',
            r'^(nice|cool|awesome|great|sweet|rad)[\s!.,]*$',
            r'(nice|cool|awesome|great)\s+(dude|man|bro|thanks|thank you)',
            r'thanks.*(dude|man|bro|so much|a lot)',
            # Short casual responses
            r'^(just|yeah|yep|nope|sure|ok|okay|alright|fine|good|nice|cool|awesome|great|lol|haha)[\s!.,]*$',
            r'^(just|yeah|yep|nope|sure|ok|okay|alright|fine|good|nice|cool|awesome|great)\s+(felt|feeling|wanted|want|thought|think|decided|decide|tried|try)[\s!.,]*$',
            r'^(just|yeah|yep|nope|sure|ok|okay|alright|fine|good|nice|cool|awesome|great)\s+.*(?:really|though|anyway|anyways|so|then)[\s!.,]*$',
            # Very short responses without question words (likely casual)
            r'^.{1,30}$',  # Very short messages without question words are likely casual
        ]
        for pattern in casual_patterns:
            if re.match(pattern, query_without_mentions):
                return False
        
        # Don't search for pure state queries (unless documents mentioned)
        state_query_patterns = [
            r'how (much|many) (gold|coins|items?) (do|does) (i|you|he|she|they|@\w+) (have|own)',
            r'what (is|are) (my|your|his|her|their|@\w+\'s) (gold|coins|inventory|items?)',
            r'(i|you|he|she|they|@\w+) (have|has|owns) (how much|how many)'
        ]
        
        # Don't search for state SETTING commands (unless documents mentioned)
        state_set_patterns = [
            r'(?:keep track|remember|set|i have|i own|i\'m|i am).*(?:having|with|of).*\d+.*(?:gold|coins?|pieces?)',
            r'(?:keep track|remember|set).*(?:me|i|my).*(?:having|with|of).*\d+.*(?:gold|coins?|pieces?)',
            r'(?:i have|i own|i\'m|i am).*\d+.*(?:gold|coins?|pieces?)',
            r'(?:set|update|change).*(?:my|me|i).*(?:gold|coins?).*to.*\d+',
        ]
        
        mentions_document = any(word in query_lower for word in ['document', 'doc', 'file', 'pdf', 'text'])
        
        for pattern in state_query_patterns + state_set_patterns:
            if re.search(pattern, query_lower) and not mentions_document:
                return False
        
        # Don't search for pure action commands
        action_patterns = [
            r'^(give|take|set|add|remove)',
            r'^transfer',
            # Action variations
            r'(?:i\'m|i am|i\'m going to|i will|i\'ll)\s+(?:giving|give|transferring|transfer|sending|send)',
            r'(?:giving|give|transferring|transfer|sending|send)\s+.*(?:to|@)',
        ]
        for pattern in action_patterns:
            if re.search(pattern, query_lower):
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
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # Extract key topic words from query (remove common words)
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'about', 'can', 'you', 'search', 'discussion', 'question'}
        topic_words = [w for w in query_words if w not in common_words and len(w) > 2]
        
        for doc in all_docs:
            score = 0.0
            filename = doc.get("file_name", "").lower()
            doc_id = doc.get("id")
            
            # Factor 1: Strong filename/keyword match (boost for exact matches)
            for word in topic_words:
                if word in filename:
                    # Strong boost for keyword matches
                    score += 0.5
                elif any(word in filename for word in query_lower.split()):
                    score += 0.3
            
            # Factor 2: Temporal weighting - prioritize recent documents
            uploaded_at = doc.get("uploaded_at")
            if uploaded_at:
                try:
                    from datetime import datetime
                    if isinstance(uploaded_at, str):
                        # Parse ISO format datetime
                        upload_time = datetime.fromisoformat(uploaded_at.replace('Z', '+00:00'))
                    else:
                        upload_time = uploaded_at
                    
                    # Boost documents uploaded in last 24 hours
                    time_diff = (datetime.now(upload_time.tzinfo) - upload_time).total_seconds()
                    if time_diff < 86400:  # 24 hours
                        score += 0.4  # Strong boost for very recent documents
                    elif time_diff < 604800:  # 7 days
                        score += 0.2  # Moderate boost for recent documents
                except:
                    pass
            
            # Factor 3: User document history (if user_id provided)
            if context and context.get("user_id"):
                try:
                    user_history = self.knowledge_graph.get_user_document_history(
                        context["user_id"],
                        limit=20
                    )
                    if any(h["doc_id"] == doc_id for h in user_history):
                        score += 0.2
                except:
                    pass
            
            # Factor 4: Topic relevance (if knowledge graph has topics)
            if doc_id:
                try:
                    # Check if document topics match query
                    topics = self._get_document_topics(doc_id)
                    for topic in topics:
                        topic_lower = topic.lower()
                        if any(word in topic_lower for word in topic_words):
                            score += 0.3  # Boost for topic matches
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
        query_lower = query.lower()
        
        # Extract topic words that might refer to documents
        # Common patterns: "X discussion", "X video", "X document", "the X", "about X"
        topic_patterns = [
            r'(\w+)\s+discussion',
            r'(\w+)\s+video',
            r'(\w+)\s+document',
            r'the\s+(\w+)\s+discussion',
            r'about\s+(\w+)',
            r'(\w+)\s+question',
            r'(\w+)\s+transcript'
        ]
        
        import re
        for pattern in topic_patterns:
            matches = re.findall(pattern, query_lower)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match else ''
                if match and len(match) > 2:  # Ignore very short words
                    references.append(match)
        
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

