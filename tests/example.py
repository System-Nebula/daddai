"""
Example script demonstrating how to use the RAG system.
"""
from src.processors.document_processor import DocumentProcessor
from src.processors.embedding_generator import EmbeddingGenerator
from src.stores.neo4j_store import Neo4jStore
from src.core.rag_pipeline import RAGPipeline
from config import USE_GPU, EMBEDDING_BATCH_SIZE


def example_ingest():
    """Example: Ingest a document."""
    print("Example: Ingesting a document")
    print("-" * 50)
    
    # Initialize components
    processor = DocumentProcessor()
    
    # Initialize with GPU support (auto-detected)
    device = USE_GPU if USE_GPU != 'auto' else None
    embedding_gen = EmbeddingGenerator(device=device, batch_size=EMBEDDING_BATCH_SIZE)
    
    neo4j_store = Neo4jStore()
    
    # Process a document (replace with your file path)
    file_path = "sample_document.pdf"  # Change this to your document
    
    try:
        # Process document
        document = processor.process_document(file_path)
        print(f"Processed document: {document['metadata']['file_name']}")
        print(f"Number of chunks: {len(document['chunks'])}")
        
        # Generate embeddings
        chunk_texts = [chunk['text'] for chunk in document['chunks']]
        embeddings = embedding_gen.generate_embeddings_batch(chunk_texts)
        print(f"Generated {len(embeddings)} embeddings")
        
        # Store in Neo4j
        doc_id = neo4j_store.store_document(document, embeddings)
        print(f"Stored in Neo4j as: {doc_id}")
        
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        print("Please update the file_path variable with a valid document path")
    finally:
        neo4j_store.close()


def example_query():
    """Example: Query the RAG system."""
    print("\nExample: Querying the RAG system")
    print("-" * 50)
    
    # Initialize RAG pipeline
    pipeline = RAGPipeline()
    
    # Check LMStudio connection
    if not pipeline.lmstudio_client.check_connection():
        print("Warning: LMStudio is not running or not accessible")
        print("Please start LMStudio and load a model")
        pipeline.close()
        return
    
    # Ask a question
    question = "What is the main topic of the documents?"
    print(f"Question: {question}\n")
    
    try:
        # Get answer
        result = pipeline.query(question, top_k=3)
        
        print("Answer:")
        print(result['answer'])
        print(f"\nRetrieved {len(result['context_chunks'])} relevant chunks")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        pipeline.close()


if __name__ == "__main__":
    print("=" * 50)
    print("RAG System Examples")
    print("=" * 50)
    
    # Uncomment the example you want to run:
    # example_ingest()
    # example_query()
    
    print("\nTo run examples, uncomment the desired function calls above.")
