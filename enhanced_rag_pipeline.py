"""
Enhanced RAG Pipeline integrating all advanced features:
- Intelligent memory management
- User relations and context
- Enhanced query understanding
- Multi-stage document search
- Knowledge graph relationships
"""
from typing import List, Dict, Any, Optional
import numpy as np
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from cachetools import TTLCache

from rag_pipeline import RAGPipeline
from intelligent_memory import IntelligentMemory
from user_relations import UserRelations
from enhanced_query_understanding import EnhancedQueryUnderstanding
from enhanced_document_search import EnhancedDocumentSearch
from knowledge_graph import KnowledgeGraph
from user_state_manager import UserStateManager
from action_parser import ActionParser
from smart_document_selector import SmartDocumentSelector
from llm_item_tracker import LLMItemTracker
from llm_tools import create_rag_tools, LLMToolExecutor, LLMToolParser
from tool_sandbox import ToolSandbox, ToolStorage
from meta_tools import create_meta_tools
from cross_encoder_reranker import CrossEncoderReranker, FallbackReranker
from multi_query_retrieval import MultiQueryRetrieval
from rag_evaluator import RAGEvaluator
from performance_monitor import PerformanceMonitor
from ab_testing import ABTesting
from performance_optimizations import PerformanceOptimizer
from config import (
    USE_GPU, EMBEDDING_BATCH_SIZE, CACHE_ENABLED, CACHE_MAX_SIZE, CACHE_TTL_SECONDS,
    RAG_TOP_K, RAG_TEMPERATURE, RAG_MAX_TOKENS, RAG_MAX_CONTEXT_TOKENS, MMR_LAMBDA
)
from logger_config import logger


class EnhancedRAGPipeline(RAGPipeline):
    """
    Enhanced RAG pipeline with all advanced features.
    Extends base RAGPipeline with:
    - Intelligent memory management
    - User relations and context awareness
    - Enhanced query understanding
    - Multi-stage document search
    - Knowledge graph integration
    """
    
    def __init__(self):
        """Initialize enhanced RAG pipeline with all components."""
        # Initialize base pipeline
        super().__init__()
        
        # Initialize enhanced components
        self.intelligent_memory = IntelligentMemory()
        self.user_relations = UserRelations()
        self.query_understanding = EnhancedQueryUnderstanding()
        self.enhanced_search = EnhancedDocumentSearch()
        self.knowledge_graph = KnowledgeGraph()
        self.state_manager = UserStateManager()
        self.action_parser = ActionParser()
        self.document_selector = SmartDocumentSelector()
        self.item_tracker = LLMItemTracker()  # LLM-based item tracking
        
        # State-of-the-art retrieval components
        self.cross_encoder_reranker = CrossEncoderReranker()  # Cross-encoder reranking
        self.fallback_reranker = FallbackReranker()  # Fallback if cross-encoder unavailable
        self.multi_query = MultiQueryRetrieval()  # Multi-query retrieval
        
        # Evaluation and monitoring
        self.evaluator = RAGEvaluator()  # Evaluation framework
        self.performance_monitor = PerformanceMonitor()  # Performance tracking
        self.ab_testing = ABTesting()  # A/B testing framework
        self.performance_optimizer = PerformanceOptimizer()  # Performance optimizations
        
        # Initialize LLM tools
        self.tool_registry = create_rag_tools(self)
        
        # Initialize tool sandbox and storage for self-extending tools
        self.tool_sandbox = ToolSandbox()
        self.tool_storage = ToolStorage()
        
        # Register meta-tools (tools that create tools)
        meta_tools = create_meta_tools(self.tool_sandbox, self.tool_storage, self.tool_registry)
        for meta_tool in meta_tools:
            self.tool_registry.register_tool(meta_tool)
        
        self.tool_executor = LLMToolExecutor(self.tool_registry)
        self.tool_parser = LLMToolParser()
        
        # Initialize conversation store for semantic conversation retrieval
        try:
            from conversation_store import ConversationStore
            self.conversation_store = ConversationStore(embedding_generator=self.embedding_generator)
        except Exception as e:
            logger.warning(f"Could not initialize conversation store: {e}")
            self.conversation_store = None
        
        logger.info("Enhanced RAG Pipeline initialized with all advanced features including self-extending tools")
    
    def query(self,
              question: str,
              top_k: int = 10,
              temperature: float = 0.7,
              max_tokens: int = 600,
              max_context_tokens: int = 1500,
              user_id: Optional[str] = None,
              channel_id: Optional[str] = None,
              use_memory: bool = True,
              use_shared_docs: bool = True,
              use_hybrid_search: bool = True,
              use_query_expansion: bool = True,
              use_temporal_weighting: bool = True,
              doc_id: Optional[str] = None,
              doc_filename: Optional[str] = None,
              username: Optional[str] = None,
              mentioned_user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Enhanced query with all advanced features.
        
        Additional features:
        - Enhanced query understanding
        - User context awareness
        - Intelligent memory retrieval
        - Multi-stage document search
        - Knowledge graph relationships
        """
        start_time = time.time()
        
        # Ensure question is a string
        if not isinstance(question, str):
            question = str(question) if question is not None else ""
        
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        # Step 0: Identify active persona (multiple people per user_id) - CACHED
        active_persona_id = None
        if user_id:
            # Cache persona identification for speed
            import hashlib
            message_hash = hashlib.md5(question[:50].encode()).hexdigest()
            cached_persona = self.performance_optimizer.get_cached_persona(user_id, message_hash)
            if cached_persona:
                active_persona_id = cached_persona
            else:
                active_persona_id = self.user_relations.identify_active_persona(
                    user_id=user_id,
                    message_text=question,
                    channel_id=channel_id,
                    username=username
                )
                if active_persona_id:
                    self.performance_optimizer.cache_persona(user_id, message_hash, active_persona_id)
        
        # Step 0.1: Check if this is an action command using LLM item tracker
        # The LLM understands what items are, where they go, and to whom they belong
        parsed_action = self.item_tracker.parse_item_action(question, user_id or "", channel_id or "")
        if parsed_action and parsed_action.get("confidence", 0) > 0.5:
            return self._handle_action(parsed_action, user_id, channel_id, username, active_persona_id)
        
        # Step 0.5: Check if this is a state query (e.g., "how much gold do I have?")
        state_result = self._handle_state_query(question, user_id, mentioned_user_id, channel_id)
        if state_result:
            return state_result
        
        # Step 1: Determine if documents should be searched
        context = {
            "user_id": user_id,
            "channel_id": channel_id,
            "doc_id": doc_id,
            "doc_filename": doc_filename,
            "mentioned_user_id": mentioned_user_id
        }
        
        should_search_docs = self.document_selector.should_search_documents(question, context)
        
        # Step 2: Enhanced query understanding - CACHED
        # Check cache first
        import hashlib
        query_hash = hashlib.md5(question.encode()).hexdigest()
        cached_analysis = self.performance_optimizer.analysis_cache.get(query_hash)
        if cached_analysis:
            enhanced_analysis = cached_analysis
        else:
            enhanced_analysis = self.query_understanding.analyze_query(question, context)
            self.performance_optimizer.analysis_cache[query_hash] = enhanced_analysis
        
        # Extract routing decisions from query analysis
        service_routing = enhanced_analysis.get("service_routing", "rag")
        needs_rag = enhanced_analysis.get("needs_rag", should_search_docs)
        needs_tools = enhanced_analysis.get("needs_tools", False)
        needs_memory = enhanced_analysis.get("needs_memory", True)  # Default to True for context
        needs_relations = enhanced_analysis.get("needs_relations", False)
        
        logger.info(f"Enhanced query analysis: {enhanced_analysis.get('question_type')}, complexity: {enhanced_analysis.get('complexity')}, service_routing: {service_routing}, needs_rag: {needs_rag}, needs_tools: {needs_tools}, needs_memory: {needs_memory}")
        
        # Override should_search_docs based on query analysis if available
        if enhanced_analysis.get("needs_rag") is not None:
            should_search_docs = needs_rag
        
        # Step 3: Rewrite query for better retrieval - OPTIMIZED
        # Skip LLM rewrite for simple queries
        use_llm_rewrite = self.performance_optimizer.should_use_llm_rewrite(question, enhanced_analysis)
        rewritten_query = self.query_understanding.rewrite_query(question, enhanced_analysis, use_llm_rewrite=use_llm_rewrite)
        
        # Step 3: Get user context and relationships (only if needed)
        user_context = None
        contextual_users = []
        if user_id and (needs_relations or needs_memory):
            try:
                user_context = self.user_relations.get_user_profile(user_id)
                if channel_id and needs_relations:
                    contextual_users = self.user_relations.get_contextual_users(
                        question, channel_id, top_n=3
                    )
            except Exception as e:
                logger.warning(f"Error getting user context: {e}")
        
        # Step 4: Get semantically relevant conversations if needed
        relevant_conversations = []
        if user_id and needs_memory and hasattr(self, 'conversation_store') and self.conversation_store:
            try:
                query_embedding_for_conv = self._get_cached_embedding(rewritten_query)
                relevant_conversations = self.conversation_store.get_relevant_conversations(
                    user_id, rewritten_query, query_embedding_for_conv, top_k=5
                )
                logger.info(f"Retrieved {len(relevant_conversations)} semantically relevant conversations")
            except Exception as e:
                logger.debug(f"Could not retrieve relevant conversations: {e}")
        
        # Step 5: Track user-document interaction if querying specific doc
        if user_id and doc_id:
            try:
                self.knowledge_graph.link_user_to_document(
                    user_id, doc_id, relationship_type="QUERIED"
                )
            except Exception as e:
                logger.debug(f"Error tracking document interaction: {e}")
        
        # Step 6: Smart document selection
        query_embedding = self._get_cached_embedding(rewritten_query)
        
        # Select which documents to search (if any)
        selected_docs = []
        if should_search_docs and use_shared_docs:
            selected_docs = self.document_selector.select_relevant_documents(
                question,
                query_embedding,
                context,
                max_docs=5
            )
            logger.info(f"Selected {len(selected_docs)} relevant documents")
        
        # Step 5: Multi-stage document retrieval
        retrieval_start = time.time()
        
        retrieved_chunks = []
        retrieved_memories = []
        
        # Optimize: Use more workers for parallel retrieval (faster)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            
            # Enhanced document search (only if documents should be searched)
            if should_search_docs and use_shared_docs:
                # If specific documents selected, search only those
                if selected_docs:
                    # Search selected documents
                    doc_ids = [doc.get("id") for doc in selected_docs if doc.get("id")]
                    if doc_ids:
                        # Search each selected document
                        for doc_id in doc_ids[:3]:  # Limit to top 3
                            futures[f'doc_{doc_id}'] = executor.submit(
                                self.enhanced_search.multi_stage_search,
                                rewritten_query,
                                query_embedding,
                                top_k,
                                doc_id=doc_id,
                                doc_filename=None
                            )
                    else:
                        # Fallback to general search
                        futures['documents'] = executor.submit(
                            self.enhanced_search.multi_stage_search,
                            rewritten_query,
                            query_embedding,
                            top_k * 2,
                            doc_id,
                            doc_filename
                        )
                else:
                    # General document search
                    futures['documents'] = executor.submit(
                        self.enhanced_search.multi_stage_search,
                        rewritten_query,
                        query_embedding,
                        top_k * 2,
                        doc_id,
                        doc_filename
                    )
            
            # Intelligent memory retrieval (only if needed)
            if use_memory and needs_memory and channel_id and not doc_id and not doc_filename:
                futures['memories'] = executor.submit(
                    self.intelligent_memory.retrieve_with_context,
                    channel_id,
                    query_embedding,
                    top_k=5,
                    min_importance=0.3
                )
            
            # Collect results (optimized timeout)
            for key, future in futures.items():
                try:
                    # Longer timeout for complex operations, shorter for simple ones
                    timeout = 8.0 if key == 'documents' else 5.0
                    result = future.result(timeout=timeout)
                    if key == 'memories':
                        retrieved_memories = result
                        # Track memory access
                        for memory in result:
                            memory_id = memory.get("id")
                            if memory_id:
                                try:
                                    self.intelligent_memory.track_memory_access(memory_id)
                                except:
                                    pass
                    elif key.startswith('doc_'):
                        # Merge results from multiple documents
                        retrieved_chunks.extend(result)
                    else:
                        retrieved_chunks = result
                except Exception as e:
                    logger.warning(f"Could not retrieve {key}: {e}")
        
        retrieval_time = time.time() - retrieval_start
        
        # Step 7: State-of-the-art retrieval enhancements
        
        # 7.1: Multi-query retrieval (OPTIMIZED - only for truly complex queries)
        complexity = enhanced_analysis.get("complexity", "simple")
        use_multi_query = self.performance_optimizer.should_use_multi_query(
            rewritten_query, complexity, len(retrieved_chunks), top_k
        )
        if use_multi_query:
            try:
                def retrieval_fn(q, k):
                    return self.enhanced_search.multi_stage_search(
                        q, query_embedding, k, doc_id, doc_filename
                    )
                
                multi_query_results = self.multi_query.retrieve_multi_query(
                    query=rewritten_query,
                    retrieval_function=retrieval_fn,
                    num_variations=3,
                    top_k_per_query=top_k * 2,
                    final_top_k=top_k * 3
                )
                
                # Merge with existing results
                existing_ids = {chunk.get("chunk_id") or chunk.get("id") for chunk in retrieved_chunks}
                for result in multi_query_results:
                    result_id = result.get("chunk_id") or result.get("id")
                    if result_id not in existing_ids:
                        retrieved_chunks.append(result)
                        existing_ids.add(result_id)
                
                logger.debug(f"Multi-query retrieval added {len(multi_query_results)} additional candidates")
            except Exception as e:
                logger.warning(f"Multi-query retrieval failed: {e}")
        
        # 7.2: Cross-encoder re-ranking (OPTIMIZED - limit candidates for speed)
        rerank_start = time.time()
        should_rerank = self.performance_optimizer.should_use_cross_encoder(len(retrieved_chunks), top_k)
        if self.cross_encoder_reranker.is_available() and should_rerank:
            try:
                # Optimize: Limit candidates before reranking
                optimized_candidates = self.performance_optimizer.optimize_cross_encoder_candidates(
                    retrieved_chunks, max_candidates=50
                )
                retrieved_chunks = self.cross_encoder_reranker.rerank(
                    query=rewritten_query,
                    candidates=optimized_candidates,
                    top_k=top_k * 2,  # Re-rank more candidates
                    max_candidates=50  # Limit for speed
                )
                logger.debug("Applied cross-encoder reranking")
            except Exception as e:
                logger.warning(f"Cross-encoder reranking failed: {e}")
                retrieved_chunks = self.fallback_reranker.rerank(
                    query=rewritten_query,
                    candidates=retrieved_chunks,
                    top_k=top_k * 2
                )
        else:
            # Use fallback reranker (fast, no model needed)
            retrieved_chunks = self.fallback_reranker.rerank(
                query=rewritten_query,
                candidates=retrieved_chunks,
                top_k=top_k * 2
            )
        
        rerank_time = (time.time() - rerank_start) * 1000  # ms
        # Track reranking performance (async to avoid blocking)
        try:
            import threading
            def track_rerank_async():
                try:
                    self.performance_monitor.track_operation(
                        operation="reranking",
                        latency_ms=rerank_time,
                        success=True,
                        metadata={"cross_encoder_used": self.cross_encoder_reranker.is_available()}
                    )
                except:
                    pass
            threading.Thread(target=track_rerank_async, daemon=True).start()
        except:
            pass
        
        # 7.3: Apply retrieval strategy from query understanding
        strategy = self.query_understanding.determine_retrieval_strategy(enhanced_analysis)
        
        # Override parameters based on strategy
        if strategy.get("use_mmr") and len(retrieved_chunks) > top_k:
            retrieved_chunks = self._apply_mmr(
                retrieved_chunks,
                query_embedding,
                top_k=top_k * 2,
                lambda_param=MMR_LAMBDA
            )
        
        # Step 8: Build context with user awareness
        all_context = []
        
        # Add user context if available
        if user_context and contextual_users:
            user_context_str = f"[User Context] User: {user_context.get('username', 'Unknown')}"
            if contextual_users:
                related_users = ", ".join([u.get("username", "") for u in contextual_users[:2]])
                if related_users:
                    user_context_str += f". Related users: {related_users}"
            all_context.append({
                "text": user_context_str,
                "score": 1.0,
                "type": "user_context"
            })
        
        # Add memories (with importance scoring)
        memory_threshold = 0.6 if (doc_id or doc_filename) else 0.4
        for memory in retrieved_memories:
            if memory.get("score", 0) >= memory_threshold:
                importance = memory.get("importance_score", 0.5)
                memory_text = f"[Memory: {memory.get('memory_type', 'conversation')}] {memory['content']}"
                if importance > 0.7:
                    memory_text = f"[Important Memory] {memory_text}"
                
                all_context.append({
                    "text": memory_text,
                    "score": memory.get("score", 0),
                    "type": "memory",
                    "importance": importance
                })
        
        # Add document chunks
        for chunk in retrieved_chunks[:top_k]:
            file_name = chunk.get("file_name", "Unknown")
            chunk_text = f"[Document: {file_name}]\n{chunk['text']}"
            
            # Add document relationships if available
            doc_id_chunk = chunk.get("doc_id")
            if doc_id_chunk:
                try:
                    related_docs = self.knowledge_graph.find_related_documents(
                        doc_id_chunk, max_relations=2
                    )
                    if related_docs:
                        related_names = [d["file_name"] for d in related_docs]
                        chunk_text += f"\n[Related documents: {', '.join(related_names)}]"
                except:
                    pass
            
            all_context.append({
                "text": chunk_text,
                "score": chunk.get("score", 0),
                "type": "document"
            })
        
        # Sort by score
        all_context.sort(key=lambda x: x["score"], reverse=True)
        
        # Step 9: Build context string with token limit
        safe_max_tokens = min(max_context_tokens, 1500)
        max_context_chars = int(safe_max_tokens * 2.5)
        
        context_parts = []
        current_length = 0
        
        for item in all_context:
            chunk_text = item["text"]
            chunk_length = len(chunk_text)
            
            if current_length + chunk_length <= max_context_chars:
                context_parts.append(chunk_text)
                current_length += chunk_length
            elif not context_parts:
                truncated = chunk_text[:max_context_chars - 200] + "..."
                context_parts.append(truncated)
                break
            else:
                remaining_space = max_context_chars - current_length
                if remaining_space > 300:
                    truncated = chunk_text[:remaining_space - 50] + "..."
                    context_parts.append(truncated)
                break
        
        context = "\n\n".join(context_parts)
        
        # Step 10: Build enhanced prompt with user context
        # Pass user_id explicitly so it can be included in the prompt
        if user_context and not user_context.get("id"):
            user_context["id"] = user_id
        if not user_context and user_id:
            # Create minimal user context with ID
            user_context = {"id": user_id, "user_id": user_id}
        
        system_prompt, user_prompt = self._build_enhanced_prompt(
            question,
            context,
            enhanced_analysis,
            user_context,
            doc_id,
            doc_filename,
            channel_id,
            relevant_conversations=relevant_conversations,
            user_id=user_id  # Pass explicitly
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Step 11: Generate response with tool support
        generation_start = time.time()
        answer, tool_calls_used = self._generate_with_tools(
            messages=messages,
            question=question,
            user_id=user_id,
            channel_id=channel_id,
            mentioned_user_id=mentioned_user_id,
            temperature=strategy.get("temperature", temperature),
            max_tokens=max_tokens,
            max_iterations=3  # Allow up to 3 tool call iterations
        )
        generation_time = (time.time() - generation_start) * 1000  # ms
        
        # Track generation performance (async to avoid blocking)
        try:
            import threading
            def track_gen_async():
                try:
                    self.performance_monitor.track_operation(
                        operation="generation",
                        latency_ms=generation_time,
                        success=True,
                        metadata={
                            "tokens": max_tokens,
                            "tool_calls": len(tool_calls_used) if tool_calls_used else 0,
                            "temperature": strategy.get("temperature", temperature)
                        },
                        user_id=user_id,
                        channel_id=channel_id
                    )
                except:
                    pass
            threading.Thread(target=track_gen_async, daemon=True).start()
        except:
            pass
        
        # Track retrieval performance (async to avoid blocking)
        try:
            # Don't block on performance tracking
            import threading
            def track_async():
                try:
                    self.performance_monitor.track_operation(
                        operation="retrieval",
                        latency_ms=retrieval_time * 1000,
                        success=True,
                        metadata={
                            "chunks_retrieved": len(retrieved_chunks),
                            "memories_retrieved": len(retrieved_memories),
                            "multi_query_used": use_multi_query if 'use_multi_query' in locals() else False
                        },
                        user_id=user_id,
                        channel_id=channel_id
                    )
                except:
                    pass  # Don't fail on tracking errors
            threading.Thread(target=track_async, daemon=True).start()
        except:
            pass  # Don't fail if threading unavailable
        
        # Step 12: Track user interaction
        if user_id:
            try:
                # Update user preferences based on query type
                preferences = self.user_relations.get_user_preferences(user_id)
                if not preferences:
                    preferences = {}
                
                # Track query topics as interests
                if enhanced_analysis.get("key_concepts"):
                    self.user_relations.track_user_interests(
                        user_id,
                        enhanced_analysis["key_concepts"][:3],
                        source="query_analysis"
                    )
            except Exception as e:
                logger.debug(f"Error tracking user interaction: {e}")
        
        total_time = time.time() - start_time
        
        # Track total query performance (async to avoid blocking)
        try:
            import threading
            def track_query_async():
                try:
                    self.performance_monitor.track_operation(
                        operation="query",
                        latency_ms=total_time * 1000,
                        success=True,
                        metadata={
                            "retrieval_time_ms": retrieval_time * 1000,
                            "generation_time_ms": generation_time,
                            "rerank_time_ms": rerank_time if 'rerank_time' in locals() else 0,
                            "chunks_used": len(retrieved_chunks[:top_k]),
                            "memories_used": len(retrieved_memories),
                            "tool_calls": len(tool_calls_used) if tool_calls_used else 0,
                            "cross_encoder_used": self.cross_encoder_reranker.is_available(),
                            "multi_query_used": use_multi_query if 'use_multi_query' in locals() else False
                        },
                        user_id=user_id,
                        channel_id=channel_id
                    )
                except:
                    pass
            threading.Thread(target=track_query_async, daemon=True).start()
        except:
            pass
        
        # Track persona interactions (if personas involved)
        if active_persona_id and mentioned_user_id:
            try:
                mentioned_persona_id = self.user_relations.identify_active_persona(
                    user_id=mentioned_user_id,
                    message_text=question,
                    channel_id=channel_id
                )
                if mentioned_persona_id:
                    self.user_relations.track_persona_interaction(
                        persona_id_1=active_persona_id,
                        persona_id_2=mentioned_persona_id,
                        interaction_type="mentioned",
                        context=question[:100],
                        channel_id=channel_id
                    )
            except Exception as e:
                logger.debug(f"Error tracking persona interaction: {e}")
        
        # Step 13: Build result
        source_documents = set()
        for chunk in retrieved_chunks[:top_k]:
            file_name = chunk.get("file_name", "Unknown")
            if file_name and file_name != "Unknown":
                source_documents.add(file_name)
        
        result = {
            "answer": answer,
            "context_chunks": retrieved_chunks[:top_k],
            "memories": retrieved_memories,
            "question": question,
            "rewritten_query": rewritten_query,
            "source_documents": list(source_documents),
            "query_analysis": enhanced_analysis,
            "user_context": user_context,
            "contextual_users": contextual_users,
            "tool_calls": tool_calls_used if 'tool_calls_used' in locals() else [],
            "timing": {
                "retrieval_ms": retrieval_time * 1000,
                "generation_ms": generation_time * 1000,
                "total_ms": total_time * 1000
            }
        }
        
        return result
    
    def _build_enhanced_prompt(self,
                               question: str,
                               context: str,
                               analysis: Dict[str, Any],
                               user_context: Optional[Dict[str, Any]],
                               doc_id: Optional[str],
                               doc_filename: Optional[str],
                               channel_id: Optional[str],
                               relevant_conversations: Optional[List[Dict[str, Any]]] = None,
                               user_id: Optional[str] = None) -> tuple:
        """Build enhanced prompt with user context awareness."""
        question_type = analysis.get("question_type", "general")
        complexity = analysis.get("complexity", "moderate")
        
        # User context string
        user_context_str = ""
        if user_context:
            username = user_context.get("username", "the user")
            user_context_str = f"\n\nUser Context: You are responding to {username}."
            
            preferences = user_context.get("preferences", {})
            if preferences.get("responseStyle"):
                user_context_str += f" Preferred response style: {preferences['responseStyle']}."
        
        # Build system prompt with user context
        current_user_info = ""
        # Get user_id from context or parameter
        current_user_id = user_id or (user_context.get("id") if user_context else None) or (user_context.get("user_id") if user_context else None)
        if current_user_id:
            current_username = user_context.get("username", "the user") if user_context else "the user"
            current_user_info = f"\n\nIMPORTANT: The current user is {current_username} (ID: {current_user_id}). When tools require a user_id parameter, ALWAYS use '{current_user_id}' automatically. DO NOT ask the user for their ID - you already have it. If the user asks about their own state/inventory/gold, use this user_id."
        
        # Build system prompt
        if doc_id or doc_filename:
            system_prompt = f"""You are an expert document analyst with access to user context and conversation history.
You must base your answer entirely on the provided document content and context.
Be precise, cite specific parts of the document when possible, and use user context to personalize your response.{current_user_info}"""
        else:
            system_prompt = f"""You are an intelligent assistant with access to documents, memories, and user context.
You can see previous conversation history and user relationships.
Use this context to provide personalized, context-aware answers.
Question type: {question_type} (complexity: {complexity}).{current_user_info}"""
        
        # Add relevant conversations context if available
        conv_context_str = ""
        if relevant_conversations:
            conv_context_str = "\n\nRelevant Past Conversations:\n"
            for i, conv in enumerate(relevant_conversations[:3], 1):
                relevance = conv.get("relevance_score", 0.5)
                conv_context_str += f"\n[{i}] (Relevance: {relevance:.2f})\n"
                conv_context_str += f"Q: {conv.get('question', '')}\n"
                conv_context_str += f"A: {conv.get('answer', '')}\n"
        
        # Build user prompt
        user_prompt = f"""Context:
{context}{user_context_str}{conv_context_str}

Question: {question}

Instructions:
- Question Type: {question_type}
- Use the provided context to answer accurately
- Reference specific documents when mentioning information
- Consider user context and previous conversations
- Be concise but thorough
- If relevant past conversations are shown, use them to maintain continuity

Answer:"""
        
        return system_prompt, user_prompt
    
    def _generate_with_tools(self,
                            messages: List[Dict[str, str]],
                            question: str,
                            user_id: Optional[str],
                            channel_id: Optional[str],
                            mentioned_user_id: Optional[str],
                            temperature: float,
                            max_tokens: int,
                            max_iterations: int = 3) -> tuple:
        """
        Generate response with tool calling support.
        Allows LLM to call tools and use results in response.
        
        Returns:
            Tuple of (final_answer, tool_calls_used)
        """
        # Add tool schemas to system message
        tool_schemas = self.tool_registry.get_tools_schema()
        
        if tool_schemas and len(messages) > 0:
            # Enhance system message with tool information
            system_msg = messages[0].get("content", "")
            tools_description = "\n\nAvailable Tools:\n"
            tools_description += "You can call these tools using JSON format: {\"tool\": \"tool_name\", \"arguments\": {...}}\n"
            tools_description += "IMPORTANT: Use the exact parameter names shown below (e.g., 'query' not 'q', 'user_id' not 'user').\n"
            # Add user_id hint if available
            if user_id:
                tools_description += f"CRITICAL: When tools require 'user_id', use '{user_id}' automatically. DO NOT ask the user for their ID - you already have it from the conversation context.\n"
            tools_description += "\n"
            
            for schema in tool_schemas[:10]:  # Limit to top 10 tools
                func = schema["function"]
                tools_description += f"- {func['name']}: {func['description']}\n"
                # Include parameter names for clarity
                params = func.get("parameters", {}).get("properties", {})
                param_list = ", ".join([f"{name}" for name in params.keys()])
                if param_list:
                    tools_description += f"  Parameters: {param_list}\n"
            
            messages[0]["content"] = system_msg + tools_description
        
        # Add user context to tool calls
        tool_context = {
            "user_id": user_id,
            "channel_id": channel_id,
            "mentioned_user_id": mentioned_user_id
        }
        
        iteration = 0
        tool_calls_used = []
        current_messages = messages.copy()
        
        while iteration < max_iterations:
            # Generate response
            response = self.lmstudio_client.generate_response(
                messages=current_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Check for tool calls
            tool_calls = self.tool_parser.parse_tool_calls(response)
            
            if not tool_calls:
                # No tool calls, return the response
                return response, tool_calls_used
            
            # Execute tool calls
            tool_results = []
            for tool_call in tool_calls:
                # Inject context into tool arguments
                if user_id and "user_id" not in tool_call.get("arguments", {}):
                    # Try to infer user_id from context
                    if mentioned_user_id and "user_id" in tool_call.get("arguments", {}):
                        pass  # Already has user_id
                    elif user_id:
                        tool_call["arguments"]["user_id"] = user_id
                
                if channel_id and "channel_id" not in tool_call.get("arguments", {}):
                    tool_call["arguments"]["channel_id"] = channel_id
                
                result = self.tool_executor.execute_tool_call(tool_call)
                tool_calls_used.append({
                    "tool": tool_call.get("name"),
                    "arguments": tool_call.get("arguments"),
                    "result": result
                })
                
                # Format result for LLM
                formatted_result = self.tool_parser.format_tool_result(
                    tool_call.get("name"),
                    result.get("result", result)
                )
                tool_results.append(f"Tool {tool_call.get('name')} result: {formatted_result}")
            
            # Add tool results to conversation
            current_messages.append({
                "role": "assistant",
                "content": response
            })
            current_messages.append({
                "role": "user",
                "content": f"Tool execution results:\n" + "\n".join(tool_results) + "\n\nPlease use these results to answer the original question: " + question
            })
            
            iteration += 1
        
        # If we've used all iterations, return the last response
        return response, tool_calls_used
    
    def _handle_action(self,
                      parsed_action: Dict[str, Any],
                      user_id: Optional[str],
                      channel_id: Optional[str],
                      username: Optional[str],
                      active_persona_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle an action command using LLM item tracker.
        The LLM understands what items are, where they go, and to whom they belong.
        
        Returns:
            Result dict with action confirmation
        """
        action_type = parsed_action.get("action")
        item_name = parsed_action.get("item_name") or parsed_action.get("item")
        quantity = parsed_action.get("quantity", 1)
        source_user_id = parsed_action.get("source_user_id")
        dest_user_id = parsed_action.get("dest_user_id") or parsed_action.get("target_user_id")
        item_type = parsed_action.get("item_type", "misc")
        properties = parsed_action.get("properties", {})
        
        if not user_id:
            return {
                "answer": "I need to know who you are to process actions.",
                "action_processed": False
            }
        
        # Create/update user profiles
        if username:
            self.user_relations.create_or_update_user(user_id, username)
        
        if dest_user_id:
            self.user_relations.create_or_update_user(dest_user_id)
        if source_user_id:
            self.user_relations.create_or_update_user(source_user_id)
        
        # Process action using LLM item tracker
        answer_parts = []
        
        try:
            if action_type == "give" or action_type == "transfer":
                if not dest_user_id:
                    return {
                        "answer": "I need to know who to give this to. Please mention a user.",
                        "action_processed": False
                    }
                
                # Use LLM item tracker to understand and transfer the item
                from_id = source_user_id or user_id
                result = self.item_tracker.transfer_item(
                    item_name=item_name,
                    from_user_id=from_id,
                    to_user_id=dest_user_id,
                    quantity=quantity,
                    context=f"User {username or user_id} gave {quantity} {item_name} to user {dest_user_id}"
                )
                
                # Also update state manager for backward compatibility
                if item_type == "currency" or item_name.lower() in ["gold", "coins", "silver", "gp", "sp"]:
                    self.state_manager.transfer_state(
                        from_user_id=from_id,
                        to_user_id=dest_user_id,
                        key=item_name.lower(),
                        amount=float(quantity),
                        metadata={
                            "action": action_type,
                            "channel_id": channel_id,
                            "from_username": username,
                            "llm_tracked": True
                        }
                    )
                else:
                    self.state_manager.transfer_item(
                        from_user_id=from_id,
                        to_user_id=dest_user_id,
                        item=result["item"],
                        quantity=quantity,
                        metadata={
                            "action": action_type,
                            "channel_id": channel_id,
                            "from_username": username,
                            "llm_tracked": True
                        }
                    )
                
                answer_parts.append(f"Gave {quantity} {result['item']} to <@{dest_user_id}>.")
                
                # Get current state for confirmation
                if item_type == "currency":
                    current_value = self.state_manager.get_user_state(dest_user_id, item_name.lower(), 0)
                    answer_parts.append(f"They now have {current_value} {result['item']}.")
                else:
                    items = self.item_tracker.get_user_items(dest_user_id)
                    item_qty = next((i["quantity"] for i in items if i["name"] == result["item"]), 0)
                    if item_qty > 0:
                        answer_parts.append(f"They now have {item_qty} {result['item']}(s).")
                
                # Track user relationship (with persona support)
                mentioned_persona_id = None
                if active_persona_id and dest_user_id:
                    try:
                        mentioned_persona_id = self.user_relations.identify_active_persona(
                            user_id=dest_user_id,
                            message_text="",
                            channel_id=channel_id
                        )
                    except:
                        pass
                
                self.user_relations.track_user_mention(
                    user_id=user_id,
                    mentioned_user_id=dest_user_id,
                    context=f"gave {quantity} {result['item']}",
                    channel_id=channel_id or "",
                    memory_id=None,
                    persona_id=active_persona_id,
                    mentioned_persona_id=mentioned_persona_id
                )
            
            elif action_type == "set":
                target = dest_user_id or user_id
                key = parsed_action.get("key")
                value = parsed_action.get("value")
                
                self.state_manager.set_user_state(
                    user_id=target,
                    key=key,
                    value=value,
                    metadata={
                        "action": "set",
                        "channel_id": channel_id,
                        "set_by": user_id
                    }
                )
                
                target_name = f"<@{target}>" if target != user_id else "you"
                answer_parts.append(f"Set {key} to {value} for {target_name}.")
            
            elif action_type == "add":
                target = dest_user_id or user_id
                
                # Use LLM to understand the item
                if item_name:
                    item_info = self.item_tracker.understand_item(item_name)
                    normalized_item = item_info.get("normalized_name", item_name.lower())
                    item_type = item_info.get("item_type", "misc")
                    
                    # Track the item
                    self.item_tracker.track_item(
                        normalized_item,
                        owner_id=target,
                        quantity=quantity,
                        properties=item_info.get("properties", {})
                    )
                
                if item_name and item_name.lower() in ["gold", "coins", "silver", "gp", "sp"]:
                    item_key = normalized_item if 'normalized_item' in locals() else item_name.lower()
                    new_value = self.state_manager.increment_user_state(
                        user_id=target,
                        key=item_key,
                        amount=float(quantity),
                        metadata={
                            "action": "add",
                            "channel_id": channel_id,
                            "added_by": user_id,
                            "llm_tracked": True
                        }
                    )
                    target_name = f"<@{target}>" if target != user_id else "you"
                    item_display = normalized_item if 'normalized_item' in locals() else item_name
                    answer_parts.append(f"Added {quantity} {item_display} to {target_name}. They now have {new_value} {item_display}.")
                else:
                    item_to_add = normalized_item if 'normalized_item' in locals() else item_name
                    inventory = self.state_manager.add_to_inventory(
                        user_id=target,
                        item=item_to_add,
                        quantity=quantity,
                        metadata={
                            "action": "add",
                            "channel_id": channel_id,
                            "added_by": user_id,
                            "llm_tracked": True
                        }
                    )
                    target_name = f"<@{target}>" if target != user_id else "you"
                    item_display = normalized_item if 'normalized_item' in locals() else item_name
                    answer_parts.append(f"Added {quantity} {item_display}(s) to {target_name}'s inventory.")
            
            # Store action in memory
            if channel_id:
                try:
                    action_memory = f"{username or 'User'} {parsed_action.get('original_text', '')}"
                    action_embedding = self.embedding_generator.generate_embedding(action_memory)
                    # Use memory_store from base class
                    if hasattr(self, 'memory_store'):
                        self.memory_store.store_memory(
                            channel_id=channel_id,
                            content=action_memory,
                            embedding=action_embedding,
                            memory_type="action",
                            user_id=user_id,
                            username=username,
                            mentioned_user_id=target_user_id
                        )
                except Exception as e:
                    logger.debug(f"Error storing action memory: {e}")
            
            return {
                "answer": " ".join(answer_parts),
                "action_processed": True,
                "action_type": action_type,
                "target_user_id": target_user_id
            }
        
        except Exception as e:
            logger.error(f"Error processing action: {e}", exc_info=True)
            return {
                "answer": f"Sorry, I encountered an error processing that action: {str(e)}",
                "action_processed": False
            }
    
    def _handle_state_query(self,
                           question: str,
                           user_id: Optional[str],
                           mentioned_user_id: Optional[str],
                           channel_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Handle state queries (e.g., "how much gold do I have?").
        
        Returns:
            Result dict if this is a state query, None otherwise
        """
        import re
        
        question_lower = question.lower()
        
        # Patterns for state queries
        state_patterns = [
            r'how (much|many) (gold|coins|items?|.*) (do|does) (i|you|he|she|they|@\w+) (have|own)',
            r'what (is|are) (my|your|his|her|their|@\w+\'s) (gold|coins|inventory|items?|.*)',
            r'(i|you|he|she|they|@\w+) (have|has|owns) (how much|how many)',
            r'what (is|are) (my|your|his|her|their|@\w+\'s) (balance|level|.*)',
        ]
        
        is_state_query = any(re.search(pattern, question_lower) for pattern in state_patterns)
        
        if not is_state_query:
            return None
        
        # Determine target user
        target_user_id = mentioned_user_id or user_id
        
        if not target_user_id:
            return {
                "answer": "I need to know who you're asking about. Please mention a user or ask about yourself.",
                "is_state_query": True
            }
        
        # Extract what they're asking about
        if "gold" in question_lower or "coins" in question_lower:
            gold_amount = self.state_manager.get_user_state(target_user_id, "gold", 0)
            return {
                "answer": f"<@{target_user_id}> has {gold_amount} gold pieces.",
                "is_state_query": True,
                "state": {"gold": gold_amount}
            }
        
        elif "inventory" in question_lower or "items" in question_lower:
            # Use LLM item tracker to get items (LLM understands what items are)
            items = self.item_tracker.get_user_items(target_user_id)
            
            # Also get from state manager for backward compatibility
            inventory = self.state_manager.get_user_state(target_user_id, "inventory", {})
            
            # Combine both sources
            all_items = {}
            if isinstance(inventory, dict):
                all_items.update(inventory)
            for item in items:
                item_name = item["name"]
                if item_name in all_items:
                    all_items[item_name] = max(all_items[item_name], item["quantity"])
                else:
                    all_items[item_name] = item["quantity"]
            
            if all_items:
                items_list = ", ".join([f"{qty} {item}" for item, qty in all_items.items()])
                return {
                    "answer": f"<@{target_user_id}>'s inventory: {items_list}.",
                    "is_state_query": True,
                    "state": {"inventory": all_items}
                }
            else:
                return {
                    "answer": f"<@{target_user_id}>'s inventory is empty.",
                    "is_state_query": True,
                    "state": {"inventory": {}}
                }
        
        else:
            # Try to extract key from question
            # Simple extraction - could be enhanced
            all_states = self.state_manager.get_user_all_states(target_user_id)
            if all_states:
                # Return summary
                state_summary = []
                for key, value in all_states.items():
                    if isinstance(value, dict):
                        if value:
                            state_summary.append(f"{key}: {len(value)} items")
                    else:
                        state_summary.append(f"{key}: {value}")
                
                if state_summary:
                    return {
                        "answer": f"<@{target_user_id}>'s state: {', '.join(state_summary)}.",
                        "is_state_query": True,
                        "state": all_states
                    }
        
        return None
    
    def close(self):
        """Close all connections."""
        super().close()
        self.intelligent_memory.close()
        self.user_relations.close()
        self.enhanced_search.close()
        self.knowledge_graph.close()
        self.state_manager.close()
        self.item_tracker.close()
        self.document_selector.close()
        self.evaluator.close()
        self.performance_monitor.close()
        self.ab_testing.close()

