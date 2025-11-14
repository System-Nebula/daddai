"""
Configuration file for the RAG system.
Set environment variables or modify defaults here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")  # Must be set via environment variable
NEO4J_MAX_CONNECTION_LIFETIME = int(os.getenv("NEO4J_MAX_CONNECTION_LIFETIME", "3600"))  # 1 hour
NEO4J_MAX_CONNECTION_POOL_SIZE = int(os.getenv("NEO4J_MAX_CONNECTION_POOL_SIZE", "50"))

# LMStudio Configuration
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "local-model")
LMSTUDIO_TIMEOUT = int(os.getenv("LMSTUDIO_TIMEOUT", "30"))  # Reduced from 60s to 30s for faster failure
LMSTUDIO_MAX_RETRIES = int(os.getenv("LMSTUDIO_MAX_RETRIES", "3"))

# Embedding Configuration
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")  # Local sentence transformer model
EMBEDDING_DIMENSION = 384  # Dimension for all-MiniLM-L6-v2
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))  # Batch size for GPU processing
USE_GPU = os.getenv("USE_GPU", "auto").lower()  # 'auto', 'cuda', or 'cpu'

# Document Processing Configuration
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# RAG Configuration
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "10"))
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.5"))
RAG_MEMORY_THRESHOLD = float(os.getenv("RAG_MEMORY_THRESHOLD", "0.5"))
RAG_MAX_CONTEXT_TOKENS = int(os.getenv("RAG_MAX_CONTEXT_TOKENS", "1500"))  # Reduced to speed up processing
RAG_TEMPERATURE = float(os.getenv("RAG_TEMPERATURE", "0.7"))
RAG_MAX_TOKENS = int(os.getenv("RAG_MAX_TOKENS", "600"))  # Reduced for faster generation

# Hybrid Search Configuration
HYBRID_SEMANTIC_WEIGHT = float(os.getenv("HYBRID_SEMANTIC_WEIGHT", "0.7"))
HYBRID_KEYWORD_WEIGHT = float(os.getenv("HYBRID_KEYWORD_WEIGHT", "0.3"))

# Query Expansion Configuration
QUERY_EXPANSION_ENABLED = os.getenv("QUERY_EXPANSION_ENABLED", "true").lower() == "true"
QUERY_EXPANSION_MAX_TERMS = int(os.getenv("QUERY_EXPANSION_MAX_TERMS", "3"))

# Temporal Weighting Configuration
TEMPORAL_WEIGHTING_ENABLED = os.getenv("TEMPORAL_WEIGHTING_ENABLED", "true").lower() == "true"
TEMPORAL_DECAY_DAYS = int(os.getenv("TEMPORAL_DECAY_DAYS", "30"))
TEMPORAL_MEMORY_DECAY_DAYS = int(os.getenv("TEMPORAL_MEMORY_DECAY_DAYS", "7"))

# MMR Configuration
MMR_LAMBDA = float(os.getenv("MMR_LAMBDA", "0.5"))
MMR_ENABLED = os.getenv("MMR_ENABLED", "true").lower() == "true"

# Caching Configuration
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "1000"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", None)  # None = console only
