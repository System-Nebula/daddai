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
NEO4J_MAX_CONNECTION_LIFETIME = int(os.getenv("NEO4J_MAX_CONNECTION_LIFETIME", "7200"))  # 2 hours (increased)
NEO4J_MAX_CONNECTION_POOL_SIZE = int(os.getenv("NEO4J_MAX_CONNECTION_POOL_SIZE", "100"))  # Increased from 50
NEO4J_CONNECTION_ACQUISITION_TIMEOUT = float(os.getenv("NEO4J_CONNECTION_ACQUISITION_TIMEOUT", "60.0"))  # 60 seconds

# LMStudio Configuration
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "local-model")
LMSTUDIO_TIMEOUT = int(os.getenv("LMSTUDIO_TIMEOUT", "30"))  # Reduced from 60s to 30s for faster failure
LMSTUDIO_MAX_RETRIES = int(os.getenv("LMSTUDIO_MAX_RETRIES", "3"))

# OpenAI-Compatible Provider Configuration
# Set LLM_PROVIDER to choose provider: "lmstudio", "openai", "chutes", or "custom"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "chutes").lower()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

# Chutes AI Configuration
CHUTES_API_KEY = os.getenv("CHUTES_API_KEY", None)
CHUTES_BASE_URL = os.getenv("CHUTES_BASE_URL", "https://llm.chutes.ai/v1")
CHUTES_MODEL = os.getenv("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3-0324")
CHUTES_TIMEOUT = int(os.getenv("CHUTES_TIMEOUT", "90"))  # Increased to 90s for thinking models, YouTube processing, and slower responses
# Default to false - existing chutes work without input_args wrapper
# Set to true only if your Chutes configuration specifically requires it
CHUTES_USE_INPUT_ARGS_WRAPPER = os.getenv("CHUTES_USE_INPUT_ARGS_WRAPPER", "false").lower() == "true"

# Custom Provider Configuration
CUSTOM_LLM_BASE_URL = os.getenv("CUSTOM_LLM_BASE_URL", None)
CUSTOM_LLM_API_KEY = os.getenv("CUSTOM_LLM_API_KEY", None)
CUSTOM_LLM_MODEL = os.getenv("CUSTOM_LLM_MODEL", None)

# Streaming Configuration
LLM_STREAMING_ENABLED = os.getenv("LLM_STREAMING_ENABLED", "false").lower() == "true"

# Embedding Configuration
# Upgraded to BAAI/bge-base-en-v1.5 for better accuracy (768 dimensions, 2-3x better retrieval)
# Alternatives: "BAAI/bge-small-en-v1.5" (384 dims, faster) or "BAAI/bge-large-en-v1.5" (1024 dims, best accuracy)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")  # State-of-the-art embedding model
EMBEDDING_DIMENSION = 768  # Dimension for BAAI/bge-base-en-v1.5 (was 384 for all-MiniLM-L6-v2)
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))  # Reduced batch size for larger model (was 64)
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

# HyDE (Hypothetical Document Embeddings) Configuration
HYDE_ENABLED = os.getenv("HYDE_ENABLED", "true").lower() == "true"
HYDE_USE_ORIGINAL_QUERY = os.getenv("HYDE_USE_ORIGINAL_QUERY", "true").lower() == "true"  # Combine HyDE + original query

# Parent-Child Chunking Configuration
PARENT_CHILD_CHUNKING_ENABLED = os.getenv("PARENT_CHILD_CHUNKING_ENABLED", "true").lower() == "true"
CHILD_CHUNK_SIZE = int(os.getenv("CHILD_CHUNK_SIZE", "300"))  # Small chunks for retrieval
PARENT_CHUNK_SIZE = int(os.getenv("PARENT_CHUNK_SIZE", "1000"))  # Large chunks for context

# Semantic Chunking Configuration
SEMANTIC_CHUNKING_ENABLED = os.getenv("SEMANTIC_CHUNKING_ENABLED", "true").lower() == "true"

# Query Rewriting Configuration
QUERY_REWRITING_ENABLED = os.getenv("QUERY_REWRITING_ENABLED", "true").lower() == "true"

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

# Elasticsearch Configuration (optional - for hybrid search)
ELASTICSEARCH_ENABLED = os.getenv("ELASTICSEARCH_ENABLED", "false").lower() == "true"
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "localhost")
ELASTICSEARCH_PORT = int(os.getenv("ELASTICSEARCH_PORT", "9200"))
ELASTICSEARCH_USER = os.getenv("ELASTICSEARCH_USER", None)
ELASTICSEARCH_PASSWORD = os.getenv("ELASTICSEARCH_PASSWORD", None)
ELASTICSEARCH_USE_SSL = os.getenv("ELASTICSEARCH_USE_SSL", "false").lower() == "true"
ELASTICSEARCH_VERIFY_CERTS = os.getenv("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "true"

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", None)  # None = console only
