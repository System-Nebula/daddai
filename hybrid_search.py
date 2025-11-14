"""
Hybrid search combining semantic (vector) and keyword (BM25) search.
Optimized for speed with vectorized operations.
"""
from typing import List, Dict, Any
import numpy as np
import re
from collections import Counter
import math


class BM25:
    """Fast BM25 implementation for keyword matching."""
    
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.doc_freqs = []
        self.idf = {}
        self.avg_doc_length = 0
        self.doc_lengths = []
        self.corpus_size = 0
    
    def fit(self, documents: List[str]):
        """Pre-compute BM25 statistics for corpus."""
        self.corpus_size = len(documents)
        self.doc_lengths = [len(doc.split()) for doc in documents]
        self.avg_doc_length = sum(self.doc_lengths) / self.corpus_size if self.corpus_size > 0 else 0
        
        # Compute document frequencies
        df = {}
        for doc in documents:
            words = set(self._tokenize(doc))
            for word in words:
                df[word] = df.get(word, 0) + 1
        
        # Compute IDF
        for word, freq in df.items():
            self.idf[word] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        text = text.lower()
        # Remove punctuation and split
        text = re.sub(r'[^\w\s]', ' ', text)
        return text.split()
    
    def get_scores(self, query: str, documents: List[str]) -> List[float]:
        """Get BM25 scores for query against documents."""
        query_terms = self._tokenize(query)
        scores = []
        
        for i, doc in enumerate(documents):
            doc_terms = self._tokenize(doc)
            doc_length = self.doc_lengths[i]
            score = 0.0
            
            for term in query_terms:
                if term in self.idf:
                    tf = doc_terms.count(term)
                    idf = self.idf[term]
                    numerator = idf * tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / self.avg_doc_length))
                    score += numerator / denominator if denominator > 0 else 0
            
            scores.append(score)
        
        return scores


class HybridSearch:
    """Combines semantic (vector) and keyword (BM25) search."""
    
    def __init__(self, semantic_weight: float = 0.7, keyword_weight: float = 0.3):
        """
        Initialize hybrid search.
        
        Args:
            semantic_weight: Weight for semantic similarity (0-1)
            keyword_weight: Weight for keyword matching (0-1)
        """
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.bm25 = BM25()
        self._documents_cache = []
        self._bm25_fitted = False
    
    def search(self,
               query: str,
               documents: List[Dict[str, Any]],
               query_embedding: List[float],
               semantic_scores: List[float],
               top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining semantic and keyword scores.
        
        Args:
            query: Query text
            documents: List of document chunks with 'text' field
            query_embedding: Query embedding vector
            semantic_scores: Pre-computed semantic similarity scores
            top_k: Number of results to return
            
        Returns:
            List of documents with combined scores
        """
        if not documents:
            return []
        
        # Extract texts for BM25
        texts = [doc.get('text', '') for doc in documents]
        
        # Fit BM25 if needed (only if corpus changed)
        if not self._bm25_fitted or len(texts) != len(self._documents_cache):
            self.bm25.fit(texts)
            self._documents_cache = texts
            self._bm25_fitted = True
        
        # Get BM25 scores
        bm25_scores = self.bm25.get_scores(query, texts)
        
        # Normalize scores to [0, 1] range
        if semantic_scores:
            max_sem = max(semantic_scores) if max(semantic_scores) > 0 else 1.0
            min_sem = min(semantic_scores) if min(semantic_scores) < max_sem else 0.0
            semantic_range = max_sem - min_sem if max_sem > min_sem else 1.0
            normalized_semantic = [(s - min_sem) / semantic_range for s in semantic_scores]
        else:
            normalized_semantic = [0.0] * len(documents)
        
        if bm25_scores:
            max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1.0
            min_bm25 = min(bm25_scores) if min(bm25_scores) < max_bm25 else 0.0
            bm25_range = max_bm25 - min_bm25 if max_bm25 > min_bm25 else 1.0
            normalized_bm25 = [(s - min_bm25) / bm25_range for s in bm25_scores] if bm25_range > 0 else [0.0] * len(documents)
        else:
            normalized_bm25 = [0.0] * len(documents)
        
        # Combine scores
        results = []
        for i, doc in enumerate(documents):
            combined_score = (
                self.semantic_weight * normalized_semantic[i] +
                self.keyword_weight * normalized_bm25[i]
            )
            result = doc.copy()
            result['score'] = combined_score
            result['semantic_score'] = semantic_scores[i] if i < len(semantic_scores) else 0.0
            result['keyword_score'] = bm25_scores[i] if i < len(bm25_scores) else 0.0
            results.append(result)
        
        # Sort by combined score
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

