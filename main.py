"""
Main script for ingesting documents and querying the RAG system.
"""
import argparse
import os
import sys
from document_processor import DocumentProcessor
from embedding_generator import EmbeddingGenerator
from neo4j_store import Neo4jStore
from rag_pipeline import RAGPipeline
from config import CHUNK_SIZE, CHUNK_OVERLAP, USE_GPU, EMBEDDING_BATCH_SIZE
from logger_config import logger


def ingest_documents(file_path: str):
    """Ingest documents into Neo4j."""
    logger.info("=" * 60)
    logger.info("Document Ingestion Pipeline")
    logger.info("=" * 60)
    
    try:
        # Initialize components
        processor = DocumentProcessor(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        
        # Initialize embedding generator with GPU support
        device = USE_GPU if USE_GPU != 'auto' else None
        embedding_gen = EmbeddingGenerator(device=device, batch_size=EMBEDDING_BATCH_SIZE)
        
        neo4j_store = Neo4jStore()
        
        # Process documents
        if os.path.isfile(file_path):
            logger.info(f"\nProcessing file: {file_path}")
            documents = [processor.process_document(file_path)]
        elif os.path.isdir(file_path):
            logger.info(f"\nProcessing directory: {file_path}")
            documents = processor.process_directory(file_path)
        else:
            logger.error(f"Error: {file_path} is not a valid file or directory")
            return
        
        # Store documents in Neo4j
        logger.info(f"\nStoring {len(documents)} document(s) in Neo4j...")
        for doc in documents:
            logger.info(f"  Processing: {doc['metadata']['file_name']}")
            
            # Generate embeddings for all chunks (GPU accelerated)
            chunk_texts = [chunk['text'] for chunk in doc['chunks']]
            logger.info(f"  Generating embeddings for {len(chunk_texts)} chunks...")
            if embedding_gen.is_gpu_available():
                logger.info(f"  Using GPU acceleration")
            embeddings = embedding_gen.generate_embeddings_batch(chunk_texts)
            
            # Store in Neo4j
            logger.info(f"  Storing in Neo4j...")
            doc_id = neo4j_store.store_document(doc, embeddings)
            logger.info(f"  [OK] Stored as: {doc_id}")
        
        neo4j_store.close()
        logger.info("\nIngestion complete!")
    except Exception as e:
        logger.error(f"Error during document ingestion: {e}", exc_info=True)
        raise


def query_rag(question: str, top_k: int = 10):
    """Query the RAG system."""
    logger.info("=" * 60)
    logger.info("RAG Query")
    logger.info("=" * 60)
    
    pipeline = None
    try:
        pipeline = RAGPipeline()
        
        # Check LMStudio connection
        if not pipeline.lmstudio_client.check_connection():
            logger.warning("Cannot connect to LMStudio. Make sure it's running on http://localhost:1234")
            logger.warning("Continuing anyway...")
        
        logger.info(f"\nQuestion: {question}\n")
        logger.info("Retrieving relevant context and generating answer...\n")
        
        result = pipeline.query(question, top_k=top_k)
        
        print("=" * 60)
        print("Answer:")
        print("=" * 60)
        print(result['answer'])
        print("\n" + "=" * 60)
        print("Retrieved Context:")
        print("=" * 60)
        
        # Show query analysis if available
        if 'query_analysis' in result:
            qa = result['query_analysis']
            print(f"\nQuery Type: {qa.get('question_type', 'unknown')}")
            print(f"Answer Type: {qa.get('answer_type', 'unknown')}")
            if qa.get('entities'):
                print(f"Entities: {qa['entities']}")
        
        for i, chunk in enumerate(result['context_chunks'], 1):
            print(f"\n[{i}] From: {chunk['file_name']} (Score: {chunk['score']:.4f})")
            print(f"    {chunk['text'][:200]}...")
        
        logger.info(f"Query completed in {result['timing']['total_ms']:.0f}ms")
    except Exception as e:
        logger.error(f"Error during RAG query: {e}", exc_info=True)
        raise
    finally:
        if pipeline:
            pipeline.close()


def interactive_mode():
    """Run interactive query mode."""
    logger.info("=" * 60)
    logger.info("Interactive RAG Query Mode")
    logger.info("Type 'exit' or 'quit' to stop")
    logger.info("=" * 60)
    
    pipeline = None
    try:
        pipeline = RAGPipeline()
        
        # Check LMStudio connection
        if not pipeline.lmstudio_client.check_connection():
            logger.warning("Cannot connect to LMStudio. Make sure it's running on http://localhost:1234")
            return
        
        while True:
            question = input("\nEnter your question: ").strip()
            
            if question.lower() in ['exit', 'quit']:
                break
            
            if not question:
                continue
            
            try:
                result = pipeline.query(question)
                print(f"\nAnswer: {result['answer']}")
                print(f"\nRetrieved {len(result['context_chunks'])} relevant chunks")
                if 'query_analysis' in result:
                    qa = result['query_analysis']
                    print(f"Query type: {qa.get('question_type', 'unknown')}")
            except Exception as e:
                logger.error(f"Error processing query: {e}", exc_info=True)
                print(f"Error: {e}")
    except KeyboardInterrupt:
        logger.info("Interactive mode interrupted by user")
    except Exception as e:
        logger.error(f"Error in interactive mode: {e}", exc_info=True)
    finally:
        if pipeline:
            pipeline.close()
        logger.info("\nGoodbye!")


def main():
    parser = argparse.ArgumentParser(description="RAG System with Docling, Neo4j, and LMStudio")
    parser.add_argument(
        "mode",
        choices=["ingest", "query", "interactive"],
        help="Mode: ingest documents, query once, or interactive mode"
    )
    parser.add_argument(
        "--path",
        type=str,
        help="Path to document file or directory (for ingest mode)"
    )
    parser.add_argument(
        "--question",
        type=str,
        help="Question to ask (for query mode)"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of chunks to retrieve (default: 10)"
    )
    
    args = parser.parse_args()
    
    if args.mode == "ingest":
        if not args.path:
            print("Error: --path is required for ingest mode")
            return
        ingest_documents(args.path)
    
    elif args.mode == "query":
        if not args.question:
            print("Error: --question is required for query mode")
            return
        query_rag(args.question, top_k=args.top_k)
    
    elif args.mode == "interactive":
        interactive_mode()


if __name__ == "__main__":
    main()
