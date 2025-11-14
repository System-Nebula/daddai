"""
A/B testing framework for RAG system.
Allows testing different retrieval strategies, prompts, parameters, etc.
"""
from typing import Dict, Any, Optional, List
import random
import hashlib
from datetime import datetime
from neo4j import GraphDatabase
import json
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from logger_config import logger


class ABTesting:
    """
    A/B testing framework for RAG improvements.
    Tests different strategies and tracks results.
    """
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize A/B testing framework."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._initialize_schema()
        self.active_experiments = {}
    
    def _initialize_schema(self):
        """Initialize A/B testing schema."""
        with self.driver.session() as session:
            try:
                session.run("CREATE CONSTRAINT experiment_id IF NOT EXISTS FOR (e:Experiment) REQUIRE e.id IS UNIQUE")
                session.run("CREATE INDEX exp_name IF NOT EXISTS FOR (e:Experiment) ON (e.name)")
                session.run("CREATE INDEX exp_active IF NOT EXISTS FOR (e:Experiment) ON (e.active)")
            except Exception as e:
                logger.debug(f"Schema initialization (may already exist): {e}")
    
    def create_experiment(self,
                         name: str,
                         variants: List[Dict[str, Any]],
                         traffic_split: Optional[Dict[str, float]] = None) -> str:
        """
        Create an A/B test experiment.
        
        Args:
            name: Experiment name
            variants: List of variant configs, e.g.:
                [
                    {"name": "control", "config": {"use_cross_encoder": False}},
                    {"name": "treatment", "config": {"use_cross_encoder": True}}
                ]
            traffic_split: Dict mapping variant names to traffic percentages
                          (default: equal split)
        
        Returns:
            Experiment ID
        """
        if not variants:
            raise ValueError("Must provide at least one variant")
        
        # Default to equal split
        if not traffic_split:
            traffic_split = {v["name"]: 1.0 / len(variants) for v in variants}
        
        # Normalize traffic split
        total = sum(traffic_split.values())
        traffic_split = {k: v / total for k, v in traffic_split.items()}
        
        experiment_id = f"exp_{name}_{datetime.now().timestamp()}"
        
        with self.driver.session() as session:
            session.run("""
                CREATE (e:Experiment {
                    id: $experiment_id,
                    name: $name,
                    variants: $variants_json,
                    traffic_split: $traffic_split_json,
                    active: true,
                    created_at: datetime()
                })
            """,
                experiment_id=experiment_id,
                name=name,
                variants_json=json.dumps(variants),
                traffic_split_json=json.dumps(traffic_split)
            )
        
        self.active_experiments[experiment_id] = {
            "name": name,
            "variants": variants,
            "traffic_split": traffic_split
        }
        
        logger.info(f"Created A/B test experiment: {name} ({experiment_id})")
        return experiment_id
    
    def get_variant(self,
                   experiment_id: str,
                   user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get variant assignment for a user/request.
        Uses consistent hashing to ensure same user gets same variant.
        
        Args:
            experiment_id: Experiment ID
            user_id: User ID (for consistent assignment)
            
        Returns:
            Variant config dict
        """
        if experiment_id not in self.active_experiments:
            # Load from Neo4j
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (e:Experiment {id: $experiment_id, active: true})
                    RETURN e.variants AS variants, e.traffic_split AS traffic_split
                """,
                    experiment_id=experiment_id
                )
                record = result.single()
                if not record:
                    raise ValueError(f"Experiment {experiment_id} not found or inactive")
                
                variants = json.loads(record.get("variants", "[]"))
                traffic_split = json.loads(record.get("traffic_split", "{}"))
                
                self.active_experiments[experiment_id] = {
                    "variants": variants,
                    "traffic_split": traffic_split
                }
        
        exp = self.active_experiments[experiment_id]
        variants = exp["variants"]
        traffic_split = exp["traffic_split"]
        
        # Consistent hashing for user assignment
        if user_id:
            # Hash user_id to get consistent assignment
            hash_value = int(hashlib.md5(f"{experiment_id}_{user_id}".encode()).hexdigest(), 16)
            random.seed(hash_value)
        else:
            random.seed()
        
        # Select variant based on traffic split
        rand = random.random()
        cumulative = 0.0
        
        for variant_name, percentage in traffic_split.items():
            cumulative += percentage
            if rand <= cumulative:
                variant = next((v for v in variants if v["name"] == variant_name), None)
                if variant:
                    return variant["config"]
        
        # Fallback to first variant
        return variants[0]["config"]
    
    def log_result(self,
                   experiment_id: str,
                   variant_name: str,
                   metrics: Dict[str, Any],
                   user_id: Optional[str] = None):
        """
        Log experiment result.
        
        Args:
            experiment_id: Experiment ID
            variant_name: Variant name
            metrics: Metrics dict (latency, accuracy, etc.)
            user_id: User ID (optional)
        """
        result_id = f"result_{experiment_id}_{datetime.now().timestamp()}"
        
        with self.driver.session() as session:
            session.run("""
                MATCH (e:Experiment {id: $experiment_id})
                CREATE (r:ExperimentResult {
                    id: $result_id,
                    variant_name: $variant_name,
                    metrics: $metrics_json,
                    timestamp: datetime()
                })
                MERGE (e)-[:HAS_RESULT]->(r)
                WITH r
                WHERE $user_id IS NOT NULL
                MATCH (u:User {id: $user_id})
                MERGE (u)-[:PARTICIPATED_IN]->(r)
            """,
                experiment_id=experiment_id,
                result_id=result_id,
                variant_name=variant_name,
                metrics_json=json.dumps(metrics),
                user_id=user_id
            )
    
    def get_experiment_results(self, experiment_id: str) -> Dict[str, Any]:
        """
        Get aggregated experiment results.
        
        Args:
            experiment_id: Experiment ID
            
        Returns:
            Dict with results per variant
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e:Experiment {id: $experiment_id})-[:HAS_RESULT]->(r:ExperimentResult)
                WITH r.variant_name AS variant, r.metrics AS metrics
                RETURN variant,
                       collect(metrics) AS all_metrics,
                       count(*) AS sample_size
            """,
                experiment_id=experiment_id
            )
            
            results = {}
            for record in result:
                variant = record.get("variant")
                all_metrics = [json.loads(m) if isinstance(m, str) else m for m in record.get("all_metrics", [])]
                sample_size = record.get("sample_size", 0)
                
                # Aggregate metrics
                aggregated = {}
                if all_metrics:
                    for key in all_metrics[0].keys():
                        values = [m.get(key) for m in all_metrics if key in m and isinstance(m[key], (int, float))]
                        if values:
                            aggregated[f"avg_{key}"] = sum(values) / len(values)
                            aggregated[f"min_{key}"] = min(values)
                            aggregated[f"max_{key}"] = max(values)
                
                results[variant] = {
                    "sample_size": sample_size,
                    "metrics": aggregated
                }
            
            return results
    
    def close(self):
        """Close connection."""
        self.driver.close()

