"""Quick test script to verify system setup."""
from src.processors.embedding_generator import EmbeddingGenerator
import torch

print("=" * 60)
print("System Test")
print("=" * 60)

print("\n1. GPU Detection:")
print(f"   CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"   GPU Name: {torch.cuda.get_device_name(0)}")
    print(f"   CUDA Version: {torch.version.cuda}")

print("\n2. Embedding Generator:")
gen = EmbeddingGenerator()
print(f"   [OK] Initialized successfully")
print(f"   GPU in use: {gen.is_gpu_available()}")
print(f"   Batch size: {gen.batch_size}")
print(f"   Embedding dimension: {gen.embedding_dimension}")

print("\n3. Test Embedding Generation:")
test_text = "This is a test document for the RAG system."
embedding = gen.generate_embedding(test_text)
print(f"   [OK] Generated embedding: {len(embedding)} dimensions")

print("\n" + "=" * 60)
print("[OK] All tests passed! System is ready.")
print("=" * 60)
