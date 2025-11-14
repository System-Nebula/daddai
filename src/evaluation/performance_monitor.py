"""
Performance monitoring and metrics tracking for RAG system.
Tracks latency, token usage, cache hit rates, error rates, etc.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict, deque
import time
from neo4j import GraphDatabase
import json
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from logger_config import logger


class PerformanceMonitor:
    """
    Comprehensive performance monitoring for RAG system.
    Tracks metrics for optimization and debugging.
    """
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize performance monitor."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._initialize_schema()
        
        # In-memory metrics (for real-time monitoring)
        self.metrics_window = deque(maxlen=1000)  # Last 1000 operations
        self.error_counts = defaultdict(int)
        self.latency_history = deque(maxlen=1000)
    
    def _initialize_schema(self):
        """Initialize performance monitoring schema."""
        with self.driver.session() as session:
            try:
                session.run("CREATE CONSTRAINT perf_id IF NOT EXISTS FOR (p:PerformanceMetric) REQUIRE p.id IS UNIQUE")
                session.run("CREATE INDEX perf_timestamp IF NOT EXISTS FOR (p:PerformanceMetric) ON (p.timestamp)")
                session.run("CREATE INDEX perf_operation IF NOT EXISTS FOR (p:PerformanceMetric) ON (p.operation)")
            except Exception as e:
                logger.debug(f"Schema initialization (may already exist): {e}")
    
    def track_operation(self,
                       operation: str,
                       latency_ms: float,
                       success: bool = True,
                       metadata: Optional[Dict[str, Any]] = None,
                       user_id: Optional[str] = None,
                       channel_id: Optional[str] = None):
        """
        Track an operation's performance.
        
        Args:
            operation: Operation name (e.g., "retrieval", "generation", "reranking")
            latency_ms: Latency in milliseconds
            success: Whether operation succeeded
            metadata: Additional metadata (token_count, cache_hit, etc.)
            user_id: User ID (optional)
            channel_id: Channel ID (optional)
        """
        timestamp = datetime.now()
        
        # Store in-memory
        metric = {
            "operation": operation,
            "latency_ms": latency_ms,
            "success": success,
            "timestamp": timestamp,
            "metadata": metadata or {},
            "user_id": user_id,
            "channel_id": channel_id
        }
        self.metrics_window.append(metric)
        self.latency_history.append(latency_ms)
        
        if not success:
            self.error_counts[operation] += 1
        
        # Store in Neo4j (async, don't block)
        try:
            self._store_metric(metric)
        except Exception as e:
            logger.warning(f"Failed to store performance metric: {e}")
    
    def _store_metric(self, metric: Dict[str, Any]):
        """Store metric in Neo4j."""
        import uuid
        # Use timestamp + UUID suffix to ensure uniqueness even for concurrent operations
        metric_id = f"perf_{datetime.now().timestamp()}_{uuid.uuid4().hex[:8]}"
        
        with self.driver.session() as session:
            # Use MERGE to handle potential duplicates gracefully
            try:
                session.run("""
                    MERGE (p:PerformanceMetric {id: $metric_id})
                    SET p.operation = $operation,
                        p.latency_ms = $latency_ms,
                        p.success = $success,
                        p.metadata = $metadata_json,
                        p.timestamp = datetime()
                    WITH p
                    WHERE $user_id IS NOT NULL
                    MATCH (u:User {id: $user_id})
                    MERGE (u)-[:PERFORMED]->(p)
                """,
                    metric_id=metric_id,
                    operation=metric["operation"],
                    latency_ms=metric["latency_ms"],
                    success=metric["success"],
                    metadata_json=json.dumps(metric.get("metadata", {})),
                    user_id=metric.get("user_id")
                )
            except Exception as e:
                # If MERGE still fails (shouldn't happen with UUID), log and continue
                logger.debug(f"Could not store performance metric (non-critical): {e}")
    
    def get_latency_stats(self, operation: Optional[str] = None, minutes: int = 60) -> Dict[str, float]:
        """
        Get latency statistics.
        
        Args:
            operation: Filter by operation (None = all operations)
            minutes: Time window in minutes
            
        Returns:
            Dict with p50, p95, p99, mean, max latency
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        relevant_metrics = [
            m for m in self.metrics_window
            if m["timestamp"] >= cutoff_time and
            (operation is None or m["operation"] == operation) and
            m["success"]
        ]
        
        if not relevant_metrics:
            return {
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "mean": 0.0,
                "max": 0.0,
                "count": 0
            }
        
        latencies = sorted([m["latency_ms"] for m in relevant_metrics])
        count = len(latencies)
        
        return {
            "p50": latencies[int(count * 0.5)] if count > 0 else 0.0,
            "p95": latencies[int(count * 0.95)] if count > 0 else 0.0,
            "p99": latencies[int(count * 0.99)] if count > 0 else 0.0,
            "mean": sum(latencies) / count if count > 0 else 0.0,
            "max": max(latencies) if latencies else 0.0,
            "count": count
        }
    
    def get_error_rate(self, operation: Optional[str] = None, minutes: int = 60) -> float:
        """
        Get error rate.
        
        Args:
            operation: Filter by operation (None = all operations)
            minutes: Time window in minutes
            
        Returns:
            Error rate (0.0 to 1.0)
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        relevant_metrics = [
            m for m in self.metrics_window
            if m["timestamp"] >= cutoff_time and
            (operation is None or m["operation"] == operation)
        ]
        
        if not relevant_metrics:
            return 0.0
        
        errors = sum(1 for m in relevant_metrics if not m["success"])
        return errors / len(relevant_metrics)
    
    def get_cache_stats(self, minutes: int = 60) -> Dict[str, Any]:
        """Get cache statistics."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        cache_metrics = [
            m for m in self.metrics_window
            if m["timestamp"] >= cutoff_time and
            "cache_hit" in m.get("metadata", {})
        ]
        
        if not cache_metrics:
            return {
                "hit_rate": 0.0,
                "hits": 0,
                "misses": 0,
                "total": 0
            }
        
        hits = sum(1 for m in cache_metrics if m["metadata"].get("cache_hit", False))
        total = len(cache_metrics)
        
        return {
            "hit_rate": hits / total if total > 0 else 0.0,
            "hits": hits,
            "misses": total - hits,
            "total": total
        }
    
    def get_summary(self, minutes: int = 60) -> Dict[str, Any]:
        """Get performance summary."""
        return {
            "latency": self.get_latency_stats(minutes=minutes),
            "error_rate": self.get_error_rate(minutes=minutes),
            "cache_stats": self.get_cache_stats(minutes=minutes),
            "total_operations": len([m for m in self.metrics_window 
                                    if m["timestamp"] >= datetime.now() - timedelta(minutes=minutes)])
        }
    
    def close(self):
        """Close connection."""
        self.driver.close()

