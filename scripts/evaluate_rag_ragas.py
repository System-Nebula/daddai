
import sys
import os
import json
from typing import List, Dict

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.evaluation.rag_evaluator import RAGEvaluator
from src.core.rag_pipeline import RAGPipeline
from logger_config import logger

def run_evaluation():
    """Run RAGAS evaluation on a set of sample questions."""
    print("=" * 60)
    print("Running RAGAS Evaluation")
    print("=" * 60)
    
    # 1. Define sample questions and ground truths
    # Ideally these should come from a dataset file
    samples = [
        {
            "question": "What is the main purpose of the Docling library?",
            "ground_truth": "Docling is a library for document processing that supports OCR, table extraction, and structured content extraction from various formats."
        },
        {
            "question": "How does the hybrid search architecture work?",
            "ground_truth": "The hybrid search architecture combines Neo4j vector search (semantic) with Elasticsearch (keyword) to improve retrieval accuracy."
        },
        {
            "question": "What is Parent-Child chunking?",
            "ground_truth": "Parent-Child chunking involves storing small chunks for retrieval that are linked to larger parent chunks which are returned as context to provide better coherence."
        }
    ]
    
    print(f"\nEvaluating {len(samples)} samples...")
    
    # 2. Initialize Pipeline and Evaluator
    pipeline = RAGPipeline()
    evaluator = RAGEvaluator()
    
    eval_data = []
    
    # 3. Generate answers using the pipeline
    print("\nGenerating answers...")
    for sample in samples:
        question = sample["question"]
        print(f"  Q: {question}")
        
        # Run pipeline
        result = pipeline.query(question)
        answer = result["answer"]
        
        # Extract contexts
        contexts = [chunk["text"] for chunk in result["context_chunks"]]
        
        eval_data.append({
            "question": question,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": sample["ground_truth"]
        })
        print(f"  A: {answer[:100]}...")
    
    # 4. Run RAGAS evaluation
    print("\nCalculating RAGAS metrics (this may take a while)...")
    try:
        results = evaluator.evaluate_with_ragas(eval_data)
        
        print("\n" + "=" * 60)
        print("Evaluation Results")
        print("=" * 60)
        print(json.dumps(results, indent=2))
        
        # Save results
        with open("ragas_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("\nResults saved to ragas_results.json")
        
    except Exception as e:
        print(f"\n❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pipeline.close()
        evaluator.close()

if __name__ == "__main__":
    run_evaluation()
