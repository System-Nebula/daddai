"""
Enhanced RAG Pipeline with smart query analysis, improved prompts, and better user recognition.
Combines document retrieval from Neo4j with LMStudio generation.
"""
from typing import List, Dict, Any, Optional
import numpy as np
import time
from datetime import datetime, timedelta
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from cachetools import TTLCache
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.stores.neo4j_store import Neo4jStore
from src.processors.embedding_generator import EmbeddingGenerator
from src.clients.lmstudio_client import LMStudioClient
from config import ELASTICSEARCH_ENABLED
from src.stores.memory_store import MemoryStore
from src.stores.document_store import DocumentStore
from src.search.hybrid_search import HybridSearch
from src.search.query_expander import QueryExpander
from src.search.query_analyzer import QueryAnalyzer
from config import (
    USE_GPU, EMBEDDING_BATCH_SIZE, CACHE_ENABLED, CACHE_MAX_SIZE, CACHE_TTL_SECONDS,
    RAG_TOP_K, RAG_TEMPERATURE, RAG_MAX_TOKENS, RAG_MAX_CONTEXT_TOKENS,
    QUERY_EXPANSION_ENABLED, TEMPORAL_WEIGHTING_ENABLED, MMR_ENABLED, MMR_LAMBDA
)
from logger_config import logger

# Try to use hybrid stores if Elasticsearch is enabled
try:
    from src.stores.hybrid_memory_store import HybridMemoryStore
    HYBRID_MEMORY_AVAILABLE = True
except ImportError:
    HYBRID_MEMORY_AVAILABLE = False

try:
    from src.stores.hybrid_document_store import HybridDocumentStore
    HYBRID_STORE_AVAILABLE = True
except ImportError:
    HYBRID_STORE_AVAILABLE = False


class RAGPipeline:
    """Optimized RAG pipeline with advanced retrieval techniques."""
    
    def __init__(self):
        """Initialize the RAG pipeline components."""
        self.neo4j_store = Neo4jStore()
        
        # Use hybrid memory store if Elasticsearch is enabled
        if ELASTICSEARCH_ENABLED and HYBRID_MEMORY_AVAILABLE:
            try:
                self.memory_store = HybridMemoryStore()
                logger.info("✅ Using HybridMemoryStore (Neo4j + Elasticsearch)")
            except Exception as e:
                logger.warning(f"Failed to initialize HybridMemoryStore, using regular MemoryStore: {e}")
                self.memory_store = MemoryStore()
        else:
            self.memory_store = MemoryStore()
        
        # Use hybrid document store if Elasticsearch is enabled
        if ELASTICSEARCH_ENABLED and HYBRID_STORE_AVAILABLE:
            try:
                self.document_store = HybridDocumentStore()
                logger.info("✅ Using HybridDocumentStore (Neo4j + Elasticsearch)")
            except Exception as e:
                logger.warning(f"Failed to initialize HybridDocumentStore, using regular DocumentStore: {e}")
                self.document_store = DocumentStore()
        else:
            self.document_store = DocumentStore()
        
        # Initialize embedding generator with GPU support (cached per instance)
        device = USE_GPU if USE_GPU != 'auto' else None
        self.embedding_generator = EmbeddingGenerator(device=device, batch_size=EMBEDDING_BATCH_SIZE)
        
        self.lmstudio_client = LMStudioClient()
        
        # Initialize hybrid search and query expansion
        self.hybrid_search = HybridSearch(semantic_weight=0.7, keyword_weight=0.3)
        self.query_expander = QueryExpander()
        self.query_analyzer = QueryAnalyzer()
        
        # Smart caching with TTL
        if CACHE_ENABLED:
            self._query_embedding_cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL_SECONDS)
            self._query_result_cache = TTLCache(maxsize=CACHE_MAX_SIZE // 2, ttl=CACHE_TTL_SECONDS)
        else:
            self._query_embedding_cache = {}
            self._query_result_cache = {}
    
    def query(self, 
              question: str, 
              top_k: int = 10,
              temperature: float = 0.7,
              max_tokens: int = 600,  # Reduced for faster generation
              max_context_tokens: int = 1500,  # Reduced to speed up processing and prevent timeouts
              user_id: Optional[str] = None,  # Kept for backward compat, but channel_id should be passed here
              channel_id: Optional[str] = None,  # New: channel ID for channel-based memories
              use_memory: bool = True,
              use_shared_docs: bool = True,
              use_hybrid_search: bool = True,
              use_query_expansion: bool = True,
              use_temporal_weighting: bool = True,
              doc_id: Optional[str] = None,  # Filter to specific document by ID
              doc_filename: Optional[str] = None,  # Filter to specific document by filename
              mentioned_user_id: Optional[str] = None,  # Mentioned user ID for state queries
              is_admin: bool = False) -> Dict[str, Any]:  # Admin status for tool creation permissions
        """
        Query the RAG system with optimized retrieval.
        
        Args:
            question: User's question
            top_k: Number of relevant chunks to retrieve
            temperature: Sampling temperature for generation
            max_tokens: Maximum tokens in response
            max_context_tokens: Maximum tokens in context
            user_id: Discord user ID for memory
            use_memory: Use long-term memory
            use_shared_docs: Use shared documents
            use_hybrid_search: Use hybrid semantic+keyword search
            use_query_expansion: Expand query with synonyms
            use_temporal_weighting: Weight recent documents/memories higher
            
        Returns:
            Dictionary containing answer and retrieved context
        """
        start_time = time.time()
        
        # Ensure question is a string
        if not isinstance(question, str):
            question = str(question) if question is not None else ""
        
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        # Analyze query for smart retrieval
        query_analysis = self.query_analyzer.analyze(question)
        logger.info(f"Query analysis: type={query_analysis['question_type']}, strategy={query_analysis['retrieval_strategy']}")
        
        # Use suggested parameters if not explicitly provided
        if top_k == 10:  # Default value
            top_k = query_analysis['suggested_top_k']
        if temperature == 0.7:  # Default value
            temperature = query_analysis['suggested_temperature']
        
        # Expand query for better recall
        expanded_query = self.query_expander.expand(question) if (use_query_expansion and QUERY_EXPANSION_ENABLED) else question
        
        # Ensure expanded_query is a string
        if not isinstance(expanded_query, str):
            expanded_query = str(expanded_query) if expanded_query is not None else question
        
        if not expanded_query or not expanded_query.strip():
            expanded_query = question
        
        # Enhance query with entity context
        try:
            enhanced_query = self.query_analyzer.enhance_query(expanded_query, query_analysis)
        except Exception as e:
            logger.warning(f"Error enhancing query, using expanded query: {e}")
            enhanced_query = expanded_query
        
        # Ensure enhanced_query is a valid string
        if enhanced_query is None:
            enhanced_query = question
        elif not isinstance(enhanced_query, str):
            try:
                enhanced_query = str(enhanced_query)
            except:
                enhanced_query = question
        
        # Remove null bytes and ensure it's not empty
        enhanced_query = enhanced_query.replace('\x00', '').strip()
        if not enhanced_query:
            enhanced_query = question
        
        # Check cache first
        cache_key = f"{enhanced_query}_{channel_id}_{doc_id}_{doc_filename}"
        if CACHE_ENABLED and cache_key in self._query_result_cache:
            logger.debug("Returning cached result")
            return self._query_result_cache[cache_key]
        
        # Generate embedding for the question (with caching)
        query_embedding = self._get_cached_embedding(enhanced_query)
        
        # Parallel retrieval from multiple sources
        retrieved_chunks = []
        retrieved_memories = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            
            # Personal documents
            futures['personal'] = executor.submit(
                self.neo4j_store.similarity_search, query_embedding, top_k
            )
            
            # Shared documents (with optional document filter)
            if use_shared_docs:
                futures['shared'] = executor.submit(
                    self.document_store.similarity_search_shared, 
                    query_embedding, 
                    top_k,
                    doc_id=doc_id,
                    doc_filename=doc_filename
                )
            
            # Memories (now channel-based)
            # Skip memory retrieval if querying a specific document (to avoid contamination)
            # Use channel_id if provided, otherwise skip memory retrieval
            if use_memory and channel_id and not doc_id and not doc_filename:
                futures['memories'] = executor.submit(
                    self.memory_store.retrieve_relevant_memories, channel_id, query_embedding, 5
                )
            
            # Collect results
            for key, future in futures.items():
                try:
                    result = future.result(timeout=5.0)  # 5 second timeout per source
                    if key == 'memories':
                        retrieved_memories = result
                    else:
                        retrieved_chunks.extend(result)
                except Exception as e:
                    print(f"Warning: Could not retrieve {key}: {e}", file=__import__('sys').stderr)
        
        retrieval_time = time.time() - start_time
        
        # Apply hybrid search if enabled
        if use_hybrid_search and retrieved_chunks:
            semantic_scores = [chunk.get('score', 0) for chunk in retrieved_chunks]
            retrieved_chunks = self.hybrid_search.search(
                expanded_query,
                retrieved_chunks,
                query_embedding,
                semantic_scores,
                top_k=top_k * 2
            )
        
        # Apply temporal weighting if enabled
        if use_temporal_weighting and TEMPORAL_WEIGHTING_ENABLED:
            retrieved_chunks = self._apply_temporal_weighting(retrieved_chunks)
            retrieved_memories = self._apply_temporal_weighting_memories(retrieved_memories)
        
        # Apply MMR (Maximal Marginal Relevance) to reduce redundancy
        if MMR_ENABLED and query_analysis['retrieval_strategy'] in ['diverse', 'balanced']:
            filtered_chunks = self._apply_mmr(retrieved_chunks, query_embedding, top_k=top_k * 2, lambda_param=MMR_LAMBDA)
        else:
            # Simple top-k selection for precise queries
            filtered_chunks = sorted(retrieved_chunks, key=lambda x: x.get('score', 0), reverse=True)[:top_k * 2]
        
        # Adaptive thresholding
        if filtered_chunks:
            scores = [chunk.get('score', 0) for chunk in filtered_chunks]
            threshold = np.percentile(scores, 30) if len(scores) > 3 else min(scores) if scores else 0
            filtered_chunks = [chunk for chunk in filtered_chunks if chunk.get('score', 0) >= threshold]
        
        if not filtered_chunks:
            filtered_chunks = retrieved_chunks[:top_k] if retrieved_chunks else []
        
        # Combine memories and chunks, prioritize by relevance
        all_context = []
        
        # Separate bot responses from other memories
        # IMPORTANT: When querying a specific document, use a higher threshold to avoid unrelated memories
        bot_responses = []
        other_memories = []
        
        # Use higher threshold when a specific document is targeted to prevent contamination
        memory_threshold = 0.7 if (doc_id or doc_filename) else 0.5
        
        for memory in retrieved_memories:
            if memory.get('score', 0) >= memory_threshold:
                if memory.get('memory_type') == 'bot_response':
                    bot_responses.append(memory)
                else:
                    other_memories.append(memory)
        
        # Add bot responses first
        for memory in bot_responses:
            all_context.append({
                'text': f"[Previous Bot Response] {memory['content']}",
                'score': memory['score'],
                'type': 'bot_response'
            })
        
        # Add other memories
        for memory in other_memories:
            all_context.append({
                'text': f"[Memory: {memory['memory_type']}] {memory['content']}",
                'score': memory['score'],
                'type': 'memory'
            })
        
        # Add document chunks
        for chunk in filtered_chunks:
            file_name = chunk.get('file_name', 'Unknown')
            all_context.append({
                'text': f"[Document: {file_name}]\n{chunk['text']}",
                'score': chunk.get('score', 0),
                'type': 'document'
            })
        
        # Sort by score
        all_context.sort(key=lambda x: x['score'], reverse=True)
        
        # Build context with token limit (be conservative - LMStudio models often have 4096 token limit)
        # Reduce context size to speed up generation and prevent timeouts
        # Reserve ~800 tokens for prompt/system message, so use ~1500 tokens for context
        safe_max_tokens = min(max_context_tokens, 1500)  # Reduced to 1500 for faster processing
        max_context_chars = int(safe_max_tokens * 2.5)  # More conservative estimate (2.5 chars per token)
        
        context_parts = []
        current_length = 0
        
        # Prioritize higher-scoring items
        for item in all_context:
            chunk_text = item['text']
            chunk_length = len(chunk_text)
            
            # If adding this would exceed limit, truncate or skip
            if current_length + chunk_length <= max_context_chars:
                context_parts.append(chunk_text)
                current_length += chunk_length
            elif not context_parts:
                # Must include at least one chunk, truncate if needed
                truncated = chunk_text[:max_context_chars - 200] + "..."
                context_parts.append(truncated)
                current_length = len(truncated)
                break
            else:
                # Try to fit a truncated version if there's significant space
                remaining_space = max_context_chars - current_length
                if remaining_space > 300:  # Only if meaningful space remains
                    truncated = chunk_text[:remaining_space - 50] + "..."
                    context_parts.append(truncated)
                break
        
        context = "\n\n".join(context_parts)
        
        # Final safety check: if context is still too long, truncate it
        if len(context) > max_context_chars:
            context = context[:max_context_chars - 100] + "..."
        
        # Extract source documents early for prompt construction
        source_documents_preview = set()
        for chunk in filtered_chunks:
            file_name = chunk.get('file_name', 'Unknown')
            if file_name and file_name != 'Unknown':
                source_documents_preview.add(file_name)
        
        # Smart prompt construction based on query analysis
        system_prompt, user_prompt = self._build_smart_prompt(
            question, context, query_analysis, doc_id, doc_filename, channel_id, list(source_documents_preview)
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Generate response using LMStudio
        generation_start = time.time()
        answer = self.lmstudio_client.generate_response(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        generation_time = time.time() - generation_start
        
        # Extract source information
        source_documents = set()
        source_memories = []
        
        for chunk in filtered_chunks:
            file_name = chunk.get('file_name', 'Unknown')
            if file_name and file_name != 'Unknown':
                source_documents.add(file_name)
        
        # Use higher threshold for source_memories when a specific document is targeted
        source_memory_threshold = 0.7 if (doc_id or doc_filename) else 0.5
        
        for memory in retrieved_memories:
            if memory.get('score', 0) >= source_memory_threshold:
                source_memories.append({
                    'type': memory.get('memory_type', 'conversation'),
                    'preview': memory.get('content', '')[:100] + '...' if len(memory.get('content', '')) > 100 else memory.get('content', '')
                })
        
        total_time = time.time() - start_time
        
        result = {
            "answer": answer,
            "context_chunks": filtered_chunks,
            "memories": retrieved_memories,
            "question": question,
            "source_documents": list(source_documents),
            "source_memories": source_memories,
            "query_analysis": query_analysis,
            "timing": {
                "retrieval_ms": retrieval_time * 1000,
                "generation_ms": generation_time * 1000,
                "total_ms": total_time * 1000
            }
        }
        
        # Cache result
        if CACHE_ENABLED:
            self._query_result_cache[cache_key] = result
        
        return result
    
    def _get_cached_embedding(self, query: str) -> List[float]:
        """Get embedding with caching."""
        # Ensure query is a valid string
        if query is None:
            raise ValueError("Query cannot be None for embedding generation")
        
        if not isinstance(query, str):
            try:
                query = str(query)
            except Exception as e:
                raise ValueError(f"Cannot convert query to string: {e}")
        
        # Remove null bytes and clean
        query = query.replace('\x00', '').strip()
        
        if not query:
            raise ValueError("Query cannot be empty for embedding generation")
        
        # Check cache (TTLCache handles expiration automatically)
        if query in self._query_embedding_cache:
            logger.debug(f"Cache hit for query embedding: {query[:50]}...")
            return self._query_embedding_cache[query]
        
        try:
            embedding = self.embedding_generator.generate_embedding(query)
        except Exception as e:
            logger.error(f"Error generating embedding for query: {query[:100]}... Error: {e}")
            raise ValueError(f"Failed to generate embedding: {e}")
        
        # Store in cache (TTLCache handles size management)
        self._query_embedding_cache[query] = embedding
        logger.debug(f"Cached query embedding: {query[:50]}...")
        return embedding
    
    def _apply_temporal_weighting(self, chunks: List[Dict[str, Any]], decay_days: int = 30) -> List[Dict[str, Any]]:
        """Apply temporal weighting to boost recent documents."""
        import datetime
        
        current_time = datetime.datetime.now()
        weighted_chunks = []
        
        for chunk in chunks:
            # Try to get upload/creation time from metadata
            # For now, assume all chunks are equally recent (can be enhanced)
            # Boost score slightly for temporal relevance
            weighted_chunk = chunk.copy()
            original_score = chunk.get('score', 0)
            
            # Small boost (can be enhanced with actual timestamps)
            weighted_chunk['score'] = original_score * 1.05  # 5% boost
            
            weighted_chunks.append(weighted_chunk)
        
        return weighted_chunks
    
    def _apply_temporal_weighting_memories(self, memories: List[Dict[str, Any]], decay_days: int = 7) -> List[Dict[str, Any]]:
        """Apply temporal weighting to boost recent memories."""
        import datetime
        
        current_time = datetime.datetime.now()
        weighted_memories = []
        
        for memory in memories:
            weighted_memory = memory.copy()
            original_score = memory.get('score', 0)
            
            # Try to parse created_at timestamp
            created_at_str = memory.get('created_at', '')
            if created_at_str:
                try:
                    # Parse Neo4j datetime string format
                    # Format: "2024-01-01T12:00:00.000000000Z"
                    created_at = datetime.datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    age_days = (current_time - created_at.replace(tzinfo=None)).days
                    
                    # Boost recent memories (within decay_days)
                    if age_days <= decay_days:
                        boost = 1.0 + (1.0 - (age_days / decay_days)) * 0.2  # Up to 20% boost
                        weighted_memory['score'] = original_score * boost
                except:
                    # If parsing fails, use original score
                    pass
            
            weighted_memories.append(weighted_memory)
        
        return weighted_memories
    
    def _apply_mmr(self, 
                   chunks: List[Dict[str, Any]], 
                   query_embedding: List[float],
                   top_k: int = 10,
                   lambda_param: float = 0.5) -> List[Dict[str, Any]]:
        """Apply Maximal Marginal Relevance for diverse results."""
        if not chunks or top_k <= 0:
            return []
        
        sorted_chunks = sorted(chunks, key=lambda x: x.get('score', 0), reverse=True)
        
        if len(sorted_chunks) <= top_k:
            return sorted_chunks
        
        # Fast MMR: ensure diversity by document
        selected = []
        selected_doc_ids = set()
        
        for chunk in sorted_chunks:
            if len(selected) >= top_k:
                break
            
            doc_id = chunk.get('doc_id', '')
            if doc_id not in selected_doc_ids or len(selected) < top_k // 2:
                selected.append(chunk)
                selected_doc_ids.add(doc_id)
        
        if len(selected) < top_k:
            for chunk in sorted_chunks:
                if len(selected) >= top_k:
                    break
                if chunk not in selected:
                    selected.append(chunk)
        
        return selected[:top_k]
    
    def _build_smart_prompt(self, 
                           question: str, 
                           context: str, 
                           query_analysis: Dict[str, Any],
                           doc_id: Optional[str],
                           doc_filename: Optional[str],
                           channel_id: Optional[str],
                           source_documents: Optional[List[str]] = None) -> tuple:
        """
        Build smart prompts based on query analysis and context.
        
        Args:
            question: User's question
            context: Retrieved context
            query_analysis: Query analysis results
            doc_id: Optional document ID filter
            doc_filename: Optional document filename filter
            channel_id: Optional channel ID for user context
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        question_type = query_analysis['question_type']
        answer_type = query_analysis['answer_type']
        entities = query_analysis['entities']
        is_complex = query_analysis['is_complex']
        
        # Truncate question if too long
        safe_question = question[:400] if len(question) > 400 else question
        
        # Build entity context string
        entity_context = ""
        if entities:
            all_entities = []
            for entity_list in entities.values():
                all_entities.extend(entity_list)
            if all_entities:
                entity_context = f"\n\nKey entities mentioned: {', '.join(set(all_entities))}"
        
        # Document-specific prompts
        if doc_id or doc_filename:
            system_prompt = """You are an expert document analyst. Your task is to answer questions using ONLY the provided document content. 
You must base your answer entirely on the document. Do not use general knowledge or information from other sources.
Be precise, cite specific parts of the document when possible, and clearly state when information is not available in the document.
CRITICAL: START DIRECTLY WITH THE ANSWER - NO GREETINGS, NO 'Hey there', NO 'I'm not sure', NO CONVERSATIONAL INTRO!
Your first sentence should be the answer or first fact, NOT a greeting!"""
            
            user_prompt = f"""Analyze the following document to answer the user's question.

Document Content:
{context}

User's Question: {safe_question}{entity_context}

Instructions:
- Question Type: {question_type} (expecting {answer_type} answer)
- Extract relevant information that directly answers the question
- If asking for specific data (numbers, names, dates), provide exact values from the document
- If asking for analysis, provide insights based on patterns in the document
- If asking for comparisons, identify and present relevant comparisons
- Be specific and cite document sections when possible
- If the document doesn't contain enough information, clearly state what IS available
- START WITH THE ANSWER, NOT A GREETING - Your first sentence should be the answer or first fact!

Answer based on the document (START WITH THE ANSWER, NOT A GREETING):"""
        
        else:
            # Build document list for prompt (used in all question types)
            doc_list_text = ""
            if source_documents and len(source_documents) > 0:
                doc_list_text = f"\n\nAvailable documents in this context: {', '.join(source_documents)}"
            elif not context or len(context.strip()) < 50:
                doc_list_text = "\n\nNo documents are available in the provided context."
            
            anti_hallucination_note = "\n\nCRITICAL: When mentioning documents, ONLY mention those listed above. NEVER make up document names."
            
            # Smart prompts based on question type
            if question_type == 'factual':
                system_prompt = """You are a precise information assistant. Answer factual questions accurately using the provided context.
Focus on extracting specific facts, numbers, names, dates, and concrete information. Be concise and direct.
NEVER mention documents that aren't explicitly listed in the available documents.
CRITICAL: START DIRECTLY WITH THE ANSWER - NO GREETINGS, NO 'Hey there', NO 'I'm not sure', NO CONVERSATIONAL INTRO!
Your first sentence should be the answer or first fact, NOT a greeting!"""
                
                user_prompt = f"""Context:
{context}{doc_list_text}{anti_hallucination_note}

Question: {safe_question}{entity_context}

Provide a factual, direct answer based on the context. START WITH THE ANSWER, NOT A GREETING:"""
            
            elif question_type == 'analytical':
                system_prompt = """You are an analytical assistant. Analyze the provided context to answer analytical questions.
Provide insights, explanations, and reasoning based on the information available. Connect ideas and identify patterns.
CRITICAL: START DIRECTLY WITH THE ANSWER - NO GREETINGS, NO 'Hey there', NO 'I'm not sure', NO CONVERSATIONAL INTRO!
Your first sentence should be the answer or first insight, NOT a greeting!"""
                
                user_prompt = f"""Context:
{context}{doc_list_text}{anti_hallucination_note}

Question: {safe_question}{entity_context}

Analyze the context and provide a thoughtful answer with reasoning. START WITH THE ANSWER, NOT A GREETING:"""
            
            elif question_type == 'comparative':
                system_prompt = """You are a comparison expert. Compare and contrast information from the context to answer comparative questions.
Identify similarities, differences, advantages, and relationships between items."""
                
                user_prompt = f"""Context:
{context}{doc_list_text}{anti_hallucination_note}

Question: {safe_question}{entity_context}

Compare and contrast the relevant information to answer:"""
            
            elif question_type == 'procedural':
                system_prompt = """You are a procedural assistant. Provide clear, step-by-step instructions based on the context.
Organize information in a logical sequence and make it easy to follow."""
                
                user_prompt = f"""Context:
{context}{doc_list_text}{anti_hallucination_note}

Question: {safe_question}{entity_context}

Provide clear step-by-step instructions based on the context:"""
            
            elif question_type == 'quantitative':
                system_prompt = """You are a data analyst. Extract and present quantitative information accurately.
Focus on numbers, statistics, measurements, and numerical data from the context."""
                
                user_prompt = f"""Context:
{context}{doc_list_text}{anti_hallucination_note}

Question: {safe_question}{entity_context}

Extract and present the quantitative information requested:"""
            
            else:
                # General prompt with user context awareness
                user_context = ""
                if channel_id:
                    user_context = "\n\nNote: Consider previous conversation context if available in the memories above."
                
                system_prompt = """You are a helpful assistant. Answer questions using the provided context.
If you see "[Previous Bot Response]", reference your previous responses for consistency.
If you see "[Memory: ...]", use that information to provide personalized, context-aware answers.

CRITICAL: Only mention documents listed in "Available documents" below. Never make up document names. If memories mention documents not in the list, those documents were deleted and should not be mentioned."""
                
                user_prompt = f"""Context:
{context}{doc_list_text}

Question: {safe_question}{entity_context}{user_context}

Answer:"""
        
        return system_prompt, user_prompt
    
    def close(self):
        """Close connections."""
        self.neo4j_store.close()
        self.memory_store.close()
        self.document_store.close()
