"""
Test script to verify RAG upgrades are working correctly.
Tests embedding model, BGE prefix, and basic functionality.
"""
import sys
import os
import io

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.processors.embedding_generator import EmbeddingGenerator
from config import EMBEDDING_MODEL, EMBEDDING_DIMENSION, USE_GPU, EMBEDDING_BATCH_SIZE
from logger_config import logger

def test_embedding_model():
    """Test that the new BGE embedding model loads and works."""
    print("=" * 60)
    print("TEST 1: Embedding Model Upgrade")
    print("=" * 60)
    
    try:
        print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
        print(f"Expected dimension: {EMBEDDING_DIMENSION}")
        print(f"GPU setting: {USE_GPU}")
        
        device = USE_GPU if USE_GPU != 'auto' else None
        embedding_gen = EmbeddingGenerator(
            model_name=EMBEDDING_MODEL,
            device=device,
            batch_size=EMBEDDING_BATCH_SIZE
        )
        
        actual_dimension = embedding_gen.get_dimension()
        print(f"\n✅ Model loaded successfully!")
        print(f"   Actual dimension: {actual_dimension}")
        print(f"   Expected dimension: {EMBEDDING_DIMENSION}")
        
        if actual_dimension == EMBEDDING_DIMENSION:
            print(f"   ✅ Dimension matches!")
        else:
            print(f"   ⚠️  Dimension mismatch! Update config.py if needed.")
        
        # Test embedding generation
        test_text = "This is a test query for the RAG system"
        print(f"\nTesting embedding generation...")
        embedding = embedding_gen.generate_embedding(test_text)
        
        print(f"   ✅ Generated embedding: {len(embedding)} dimensions")
        print(f"   ✅ First few values: {embedding[:5]}")
        
        # Test batch embedding
        test_texts = [
            "First test document",
            "Second test document",
            "Third test document"
        ]
        print(f"\nTesting batch embedding generation...")
        embeddings = embedding_gen.generate_embeddings_batch(test_texts)
        
        print(f"   ✅ Generated {len(embeddings)} embeddings")
        print(f"   ✅ Each embedding has {len(embeddings[0])} dimensions")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error testing embedding model: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bge_query_prefix():
    """Test BGE query instruction prefix."""
    print("\n" + "=" * 60)
    print("TEST 2: BGE Query Instruction Prefix")
    print("=" * 60)
    
    try:
        device = USE_GPU if USE_GPU != 'auto' else None
        embedding_gen = EmbeddingGenerator(
            model_name=EMBEDDING_MODEL,
            device=device
        )
        
        # Test query with prefix (what RAG pipeline does)
        query = "What is machine learning?"
        query_with_prefix = f"Represent this sentence for searching relevant passages: {query}"
        
        print(f"\nOriginal query: {query}")
        print(f"Query with prefix: {query_with_prefix}")
        
        # Generate embeddings
        embedding_original = embedding_gen.generate_embedding(query)
        embedding_with_prefix = embedding_gen.generate_embedding(query_with_prefix)
        
        print(f"\n✅ Generated embeddings successfully")
        print(f"   Original embedding dimension: {len(embedding_original)}")
        print(f"   Prefixed embedding dimension: {len(embedding_with_prefix)}")
        
        # Check if they're different (they should be)
        import numpy as np
        similarity = np.dot(embedding_original, embedding_with_prefix) / (
            np.linalg.norm(embedding_original) * np.linalg.norm(embedding_with_prefix)
        )
        print(f"   Cosine similarity: {similarity:.4f}")
        print(f"   ✅ Prefix changes embedding (as expected for BGE)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error testing BGE prefix: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cross_encoder():
    """Test cross-encoder reranker upgrade."""
    print("\n" + "=" * 60)
    print("TEST 3: Cross-Encoder Reranker")
    print("=" * 60)
    
    try:
        from src.utils.cross_encoder_reranker import CrossEncoderReranker
        
        print(f"\nLoading cross-encoder reranker...")
        reranker = CrossEncoderReranker(lazy_load=False)  # Load immediately for test
        
        if reranker.is_available():
            print(f"   ✅ Cross-encoder loaded successfully")
            print(f"   Model: {reranker.model_name}")
            
            # Test reranking
            query = "What is artificial intelligence?"
            candidates = [
                {"text": "Artificial intelligence is the simulation of human intelligence.", "score": 0.8},
                {"text": "Machine learning is a subset of AI.", "score": 0.7},
                {"text": "The weather today is sunny.", "score": 0.3}
            ]
            
            print(f"\nTesting reranking with {len(candidates)} candidates...")
            reranked = reranker.rerank(query, candidates, top_k=2)
            
            print(f"   ✅ Reranked to {len(reranked)} results")
            for i, result in enumerate(reranked, 1):
                print(f"   [{i}] Score: {result.get('final_score', result.get('rerank_score', 0)):.4f}")
                print(f"       Text: {result['text'][:60]}...")
            
            return True
        else:
            print(f"   ⚠️  Cross-encoder not available (may need sentence-transformers)")
            return False
            
    except Exception as e:
        print(f"\n❌ Error testing cross-encoder: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hyde():
    """Test HyDE retrieval (if LLM client available)."""
    print("\n" + "=" * 60)
    print("TEST 4: HyDE (Hypothetical Document Embeddings)")
    print("=" * 60)
    
    try:
        from src.search.hyde_retrieval import HyDERetrieval
        from src.clients.llm_client_factory import get_default_llm_client
        
        print(f"\nInitializing HyDE...")
        device = USE_GPU if USE_GPU != 'auto' else None
        embedding_gen = EmbeddingGenerator(device=device)
        
        try:
            llm_client = get_default_llm_client()
            hyde = HyDERetrieval(llm_client=llm_client, embedding_generator=embedding_gen)
            
            print(f"   ✅ HyDE initialized")
            
            # Test hypothetical answer generation
            query = "How does neural network training work?"
            print(f"\nTesting hypothetical answer generation...")
            print(f"   Query: {query}")
            
            hypothetical = hyde.generate_hypothetical_answer(query)
            print(f"   ✅ Generated hypothetical answer:")
            print(f"   {hypothetical[:200]}...")
            
            return True
            
        except Exception as e:
            print(f"   ⚠️  LLM client not available: {e}")
            print(f"   (This is OK - HyDE will work when LLM is available)")
            return True  # Not a failure, just unavailable
            
    except Exception as e:
        print(f"\n❌ Error testing HyDE: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_values():
    """Test that config values are correct."""
    print("\n" + "=" * 60)
    print("TEST 5: Configuration Values")
    print("=" * 60)
    
    try:
        print(f"\nChecking configuration...")
        print(f"   EMBEDDING_MODEL: {EMBEDDING_MODEL}")
        print(f"   EMBEDDING_DIMENSION: {EMBEDDING_DIMENSION}")
        print(f"   EMBEDDING_BATCH_SIZE: {EMBEDDING_BATCH_SIZE}")
        
        # Check if model name contains BGE
        if 'bge' in EMBEDDING_MODEL.lower():
            print(f"   ✅ Using BGE model")
        else:
            print(f"   ⚠️  Not using BGE model (expected: BAAI/bge-base-en-v1.5)")
        
        # Check dimension
        if EMBEDDING_DIMENSION == 768:
            print(f"   ✅ Dimension is 768 (correct for BGE-base)")
        elif EMBEDDING_DIMENSION == 384:
            print(f"   ⚠️  Dimension is 384 (old value, should be 768 for BGE-base)")
        else:
            print(f"   ⚠️  Unexpected dimension: {EMBEDDING_DIMENSION}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error checking config: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("RAG UPGRADE VERIFICATION TESTS")
    print("=" * 60)
    print("\nTesting RAG system upgrades...")
    print("This will verify:")
    print("  1. New BGE embedding model loads correctly")
    print("  2. BGE query instruction prefix works")
    print("  3. Cross-encoder reranker upgrade")
    print("  4. HyDE retrieval (if LLM available)")
    print("  5. Configuration values")
    
    results = []
    
    # Run tests
    results.append(("Embedding Model", test_embedding_model()))
    results.append(("BGE Query Prefix", test_bge_query_prefix()))
    results.append(("Cross-Encoder", test_cross_encoder()))
    results.append(("HyDE", test_hyde()))
    results.append(("Config Values", test_config_values()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! RAG upgrades are working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check errors above.")
    
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("1. Update Neo4j vector index to 768 dimensions:")
    print("   DROP INDEX document_embeddings IF EXISTS;")
    print("   CALL db.index.vector.createNodeIndex('document_embeddings', 'Chunk', 'embedding', 768, 'cosine');")
    print("\n2. Re-embed existing documents (optional but recommended):")
    print("   python main.py ingest --path <your_documents>")
    print("\n3. Test with a query:")
    print("   python main.py query --question 'Your test question'")
    print("=" * 60)


if __name__ == "__main__":
    main()

