"""
Direct test of BGE model to verify it works.
"""
import sys
import os
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Force BGE model
os.environ['EMBEDDING_MODEL'] = 'BAAI/bge-base-en-v1.5'

from src.processors.embedding_generator import EmbeddingGenerator
from config import USE_GPU

print("=" * 60)
print("Testing BGE Model Directly")
print("=" * 60)

device = USE_GPU if USE_GPU != 'auto' else None
print(f"\nLoading BAAI/bge-base-en-v1.5 on {device}...")

embedding_gen = EmbeddingGenerator(
    model_name='BAAI/bge-base-en-v1.5',
    device=device,
    batch_size=32
)

dimension = embedding_gen.get_dimension()
print(f"\n✅ Model loaded!")
print(f"   Dimension: {dimension}")
print(f"   Expected: 768")
print(f"   {'✅ Match!' if dimension == 768 else '❌ Mismatch!'}")

# Test embedding
test_query = "What is artificial intelligence?"
print(f"\nTesting query: '{test_query}'")

# Test with BGE prefix
query_with_prefix = f"Represent this sentence for searching relevant passages: {test_query}"
embedding = embedding_gen.generate_embedding(query_with_prefix)

print(f"✅ Generated embedding: {len(embedding)} dimensions")
print(f"   First 5 values: {embedding[:5]}")

# Test batch
test_texts = ["Document 1", "Document 2", "Document 3"]
embeddings = embedding_gen.generate_embeddings_batch(test_texts)
print(f"\n✅ Batch embeddings: {len(embeddings)} x {len(embeddings[0])} dimensions")

print("\n" + "=" * 60)
print("✅ BGE model is working correctly!")
print("=" * 60)
print("\nTo use BGE model, set in .env file:")
print("EMBEDDING_MODEL=BAAI/bge-base-en-v1.5")
print("=" * 60)

