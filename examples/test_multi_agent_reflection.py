"""
Example: Testing Multi-Agent Reflection Pattern System

This example demonstrates how to use the multi-agent reflection pattern
with LangGraph orchestration for improved RAG quality.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.enhanced_rag_pipeline import EnhancedRAGPipeline
from logger_config import logger


def test_reflection_pattern():
    """Test the multi-agent reflection pattern."""
    logger.info("🚀 Testing Multi-Agent Reflection Pattern")
    
    # Initialize pipeline
    pipeline = EnhancedRAGPipeline()
    
    # Example query
    query = "What are the main causes of system failures in distributed systems?"
    
    logger.info(f"📝 Query: {query}")
    
    try:
        # Use reflection pattern workflow
        result = pipeline.query_with_reflection(
            question=query,
            top_k=15,
            max_iterations=3,
            quality_threshold=0.8,
            use_memory=True
        )
        
        logger.info("\n" + "="*80)
        logger.info("✅ RESULT:")
        logger.info("="*80)
        logger.info(f"Answer: {result.get('answer', 'N/A')}")
        logger.info(f"Quality Score: {result.get('quality_score', 0.0):.2f}")
        logger.info(f"Iterations: {result.get('iteration', 1)}")
        logger.info(f"Sources Used: {result.get('sources_used', [])}")
        logger.info(f"Search Results: {result.get('search_results_count', 0)}")
        logger.info(f"Used Reflection: {result.get('used_reflection', False)}")
        
        if result.get('metadata'):
            logger.info(f"\nMetadata: {result['metadata']}")
        
        logger.info("="*80)
        
        return result
    except Exception as e:
        logger.error(f"Error testing reflection pattern: {e}", exc_info=True)
        return None
    finally:
        pipeline.close()


def test_standard_vs_reflection():
    """Compare standard query vs reflection pattern."""
    logger.info("\n🔄 Comparing Standard Query vs Reflection Pattern")
    
    pipeline = EnhancedRAGPipeline()
    query = "Explain the key principles of microservices architecture"
    
    try:
        # Standard query
        logger.info("\n--- Standard Query ---")
        standard_result = pipeline.query(question=query, top_k=10)
        logger.info(f"Answer length: {len(standard_result.get('answer', ''))}")
        
        # Reflection pattern query
        logger.info("\n--- Reflection Pattern Query ---")
        reflection_result = pipeline.query_with_reflection(
            question=query,
            top_k=15,
            max_iterations=3,
            quality_threshold=0.8
        )
        logger.info(f"Answer length: {len(reflection_result.get('answer', ''))}")
        logger.info(f"Quality Score: {reflection_result.get('quality_score', 0.0):.2f}")
        logger.info(f"Iterations: {reflection_result.get('iteration', 1)}")
        
    except Exception as e:
        logger.error(f"Error in comparison: {e}", exc_info=True)
    finally:
        pipeline.close()


if __name__ == "__main__":
    # Test reflection pattern
    test_reflection_pattern()
    
    # Compare standard vs reflection
    # test_standard_vs_reflection()

