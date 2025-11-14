"""
Evaluation framework for RAG system.
Tracks metrics: MRR, NDCG, precision, recall, semantic similarity.
"""
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from datetime import datetime
from collections import defaultdict
import json
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from logger_config import logger

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False


class RAGEvaluator:
    """
    Comprehensive evaluation framework for RAG system.
    Tracks retrieval and generation metrics.
    """
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD, lazy_load: bool = True):
        """Initialize RAG evaluator."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._initialize_schema()
        
        # Lazy load embedding model (only load when needed)
        self.embedding_model = None
        self._embedding_loaded = False
        self.lazy_load = lazy_load
        
        if not lazy_load:
            self._load_embedding_model()
    
    def _load_embedding_model(self):
        """Load embedding model for semantic similarity (lazy loading)."""
        if self._embedding_loaded:
            return
        
        if EMBEDDING_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                self._embedding_loaded = True
            except Exception as e:
                logger.warning(f"Could not load embedding model for evaluation: {e}")
                self.embedding_model = None
                self._embedding_loaded = True
        else:
            self._embedding_loaded = True
    
    def _initialize_schema(self):
        """Initialize evaluation schema."""
        with self.driver.session() as session:
            try:
                session.run("CREATE CONSTRAINT eval_id IF NOT EXISTS FOR (e:Evaluation) REQUIRE e.id IS UNIQUE")
                session.run("CREATE INDEX eval_timestamp IF NOT EXISTS FOR (e:Evaluation) ON (e.timestamp)")
            except Exception as e:
                logger.debug(f"Schema initialization (may already exist): {e}")
    
    def evaluate_retrieval(self,
                          query: str,
                          retrieved_chunks: List[Dict[str, Any]],
                          relevant_chunk_ids: List[str],
                          k: int = 10) -> Dict[str, float]:
        """
        Evaluate retrieval performance.
        
        Args:
            query: Query text
            retrieved_chunks: Retrieved chunks with 'chunk_id' field
            relevant_chunk_ids: List of relevant chunk IDs (ground truth)
            k: Evaluation depth (top-k)
            
        Returns:
            Dict with metrics: precision@k, recall@k, mrr, ndcg@k
        """
        if not relevant_chunk_ids:
            return {
                "precision@k": 0.0,
                "recall@k": 0.0,
                "mrr": 0.0,
                "ndcg@k": 0.0
            }
        
        retrieved_ids = [chunk.get("chunk_id") or chunk.get("id") for chunk in retrieved_chunks[:k]]
        retrieved_ids = [id for id in retrieved_ids if id]
        
        # Precision@k
        relevant_retrieved = len(set(retrieved_ids) & set(relevant_chunk_ids))
        precision = relevant_retrieved / k if k > 0 else 0.0
        
        # Recall@k
        recall = relevant_retrieved / len(relevant_chunk_ids) if relevant_chunk_ids else 0.0
        
        # MRR (Mean Reciprocal Rank)
        mrr = 0.0
        for rank, chunk_id in enumerate(retrieved_ids, start=1):
            if chunk_id in relevant_chunk_ids:
                mrr = 1.0 / rank
                break
        
        # NDCG@k (Normalized Discounted Cumulative Gain)
        dcg = 0.0
        for rank, chunk_id in enumerate(retrieved_ids, start=1):
            if chunk_id in relevant_chunk_ids:
                dcg += 1.0 / np.log2(rank + 1)
        
        # Ideal DCG (all relevant at top)
        ideal_dcg = sum(1.0 / np.log2(i + 1) for i in range(1, min(len(relevant_chunk_ids), k) + 1))
        ndcg = dcg / ideal_dcg if ideal_dcg > 0 else 0.0
        
        return {
            "precision@k": precision,
            "recall@k": recall,
            "mrr": mrr,
            "ndcg@k": ndcg,
            "relevant_retrieved": relevant_retrieved,
            "total_relevant": len(relevant_chunk_ids),
            "total_retrieved": len(retrieved_ids)
        }
    
    def evaluate_generation(self,
                           query: str,
                           generated_answer: str,
                           reference_answer: Optional[str] = None,
                           retrieved_context: Optional[List[str]] = None) -> Dict[str, float]:
        """
        Evaluate generation quality.
        
        Args:
            query: Query text
            generated_answer: Generated answer
            reference_answer: Reference/ground truth answer (optional)
            retrieved_context: Retrieved context chunks (optional)
            
        Returns:
            Dict with metrics: semantic_similarity, faithfulness, etc.
        """
        metrics = {}
        
        # Semantic similarity to reference (if available)
        # Lazy load embedding model if needed
        if not self._embedding_loaded:
            self._load_embedding_model()
        
        if reference_answer and self.embedding_model:
            try:
                query_emb = self.embedding_model.encode([query])
                gen_emb = self.embedding_model.encode([generated_answer])
                ref_emb = self.embedding_model.encode([reference_answer])
                
                # Cosine similarity
                gen_sim = np.dot(gen_emb[0], ref_emb[0]) / (
                    np.linalg.norm(gen_emb[0]) * np.linalg.norm(ref_emb[0])
                )
                metrics["semantic_similarity_to_reference"] = float(gen_sim)
            except Exception as e:
                logger.warning(f"Error computing semantic similarity: {e}")
        
        # Faithfulness (answer grounded in context)
        # Lazy load embedding model if needed
        if not self._embedding_loaded:
            self._load_embedding_model()
        
        if retrieved_context and self.embedding_model:
            try:
                context_text = " ".join(retrieved_context[:3])  # Top 3 chunks
                gen_emb = self.embedding_model.encode([generated_answer])
                ctx_emb = self.embedding_model.encode([context_text])
                
                faithfulness = np.dot(gen_emb[0], ctx_emb[0]) / (
                    np.linalg.norm(gen_emb[0]) * np.linalg.norm(ctx_emb[0])
                )
                metrics["faithfulness"] = float(faithfulness)
            except Exception as e:
                logger.warning(f"Error computing faithfulness: {e}")
        
        # Answer length (heuristic)
        metrics["answer_length"] = len(generated_answer.split())
        
        return metrics
    
    def log_evaluation(self,
                      query: str,
                      retrieval_metrics: Dict[str, float],
                      generation_metrics: Dict[str, float],
                      user_id: Optional[str] = None,
                      channel_id: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None):
        """
        Log evaluation results to Neo4j.
        
        Args:
            query: Query text
            retrieval_metrics: Retrieval evaluation metrics
            generation_metrics: Generation evaluation metrics
            user_id: User ID (optional)
            channel_id: Channel ID (optional)
            metadata: Additional metadata
        """
        eval_id = f"eval_{datetime.now().timestamp()}"
        
        with self.driver.session() as session:
            session.run("""
                CREATE (e:Evaluation {
                    id: $eval_id,
                    query: $query,
                    retrieval_metrics: $retrieval_metrics_json,
                    generation_metrics: $generation_metrics_json,
                    metadata: $metadata_json,
                    timestamp: datetime()
                })
                WITH e
                WHERE $user_id IS NOT NULL
                MATCH (u:User {id: $user_id})
                MERGE (u)-[:EVALUATED]->(e)
            """,
                eval_id=eval_id,
                query=query,
                retrieval_metrics_json=json.dumps(retrieval_metrics),
                generation_metrics_json=json.dumps(generation_metrics),
                metadata_json=json.dumps(metadata or {}),
                user_id=user_id
            )
    
    def get_average_metrics(self,
                           days: int = 7,
                           user_id: Optional[str] = None) -> Dict[str, float]:
        """
        Get average metrics over time period.
        
        Args:
            days: Number of days to look back
            user_id: Filter by user (optional)
            
        Returns:
            Average metrics
        """
        with self.driver.session() as session:
            cypher = """
                MATCH (e:Evaluation)
                WHERE e.timestamp > datetime() - duration({days: $days})
            """
            params = {"days": days}
            
            if user_id:
                cypher += """
                    MATCH (u:User {id: $user_id})-[:EVALUATED]->(e)
                """
                params["user_id"] = user_id
            
            cypher += """
                RETURN avg(e.retrieval_metrics.precision@k) AS avg_precision,
                       avg(e.retrieval_metrics.recall@k) AS avg_recall,
                       avg(e.retrieval_metrics.mrr) AS avg_mrr,
                       avg(e.retrieval_metrics.ndcg@k) AS avg_ndcg,
                       avg(e.generation_metrics.semantic_similarity_to_reference) AS avg_semantic_sim,
                       count(e) AS total_evaluations
            """
            
            result = session.run(cypher, **params)
            record = result.single()
            
            if record:
                return {
                    "avg_precision@k": record.get("avg_precision", 0.0),
                    "avg_recall@k": record.get("avg_recall", 0.0),
                    "avg_mrr": record.get("avg_mrr", 0.0),
                    "avg_ndcg@k": record.get("avg_ndcg", 0.0),
                    "avg_semantic_similarity": record.get("avg_semantic_sim", 0.0),
                    "total_evaluations": record.get("total_evaluations", 0)
                }
            
            return {}
    
    def close(self):
        """Close connection."""
        self.driver.close()

