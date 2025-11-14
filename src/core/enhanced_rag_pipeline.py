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

from src.core.rag_pipeline import RAGPipeline
from src.memory.intelligent_memory import IntelligentMemory
from src.utils.user_relations import UserRelations
from src.search.enhanced_query_understanding import EnhancedQueryUnderstanding
from src.search.enhanced_document_search import EnhancedDocumentSearch
from src.utils.knowledge_graph import KnowledgeGraph
from src.utils.user_state_manager import UserStateManager
from src.tools.action_parser import ActionParser
from src.search.smart_document_selector import SmartDocumentSelector
from src.tools.llm_item_tracker import LLMItemTracker
from src.tools.llm_tools import create_rag_tools, LLMToolExecutor, LLMToolParser
from src.tools.tool_sandbox import ToolSandbox, ToolStorage
from src.tools.meta_tools import create_meta_tools
from src.utils.cross_encoder_reranker import CrossEncoderReranker, FallbackReranker
from src.search.multi_query_retrieval import MultiQueryRetrieval
from src.evaluation.rag_evaluator import RAGEvaluator
from src.evaluation.performance_monitor import PerformanceMonitor
from src.evaluation.ab_testing import ABTesting
from src.evaluation.performance_optimizations import PerformanceOptimizer
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
    
    def _normalize_currency_key(self, item_name: str) -> str:
        """
        Normalize currency item names to consistent keys.
        "gold coins", "gold pieces", "coins" -> "gold"
        "silver pieces", "silver coins" -> "silver"
        """
        normalized = item_name.lower().strip()
        if normalized in ["gold", "coins", "coin", "gold coins", "gold pieces", "gold coin", "gp"]:
            return "gold"
        elif normalized in ["silver", "silver pieces", "silver coins", "sp"]:
            return "silver"
        return normalized
    
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
        
        # State-of-the-art retrieval components (lazy load for faster startup)
        self.cross_encoder_reranker = CrossEncoderReranker(lazy_load=True)  # Cross-encoder reranking (lazy load)
        self.fallback_reranker = FallbackReranker()  # Fallback if cross-encoder unavailable
        self.multi_query = MultiQueryRetrieval()  # Multi-query retrieval
        
        # Evaluation and monitoring (lazy load for faster startup)
        self.evaluator = RAGEvaluator(lazy_load=True)  # Evaluation framework (lazy load)
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
            from src.memory.conversation_store import ConversationStore
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
        
        # Step 0.0: Quick check - skip action parsing if this is clearly a query (not an action)
        # State queries should be handled by state query handler, not action parser
        question_lower = question.lower().strip()
        question_stripped = question.strip()
        is_query_pattern = any([
            question_stripped.startswith(('how many', 'how much', 'what', 'who', 'when', 'where', 'why')),
            'how many' in question_lower and ('have' in question_lower or 'own' in question_lower or 'does' in question_lower),
            'how much' in question_lower and ('have' in question_lower or 'own' in question_lower or 'does' in question_lower),
            question_stripped.endswith('?') and ('how many' in question_lower or 'how much' in question_lower),
            # Also catch questions about documents, training, etc.
            question_stripped.startswith('what') and ('is' in question_lower or 'are' in question_lower or 'was' in question_lower or 'were' in question_lower),
            question_stripped.startswith('how many') and ('did' in question_lower or 'does' in question_lower or 'do' in question_lower)
        ])
        
        # NOTE: Casual conversation detection is now handled by LLM analysis (enhanced_query_understanding)
        # We'll get is_casual from the LLM analysis below, not from pattern matching
        is_casual_conversation = False  # Will be set from LLM analysis
        
        # Step 0.1: Check state queries FIRST (before action parsing)
        # This prevents queries like "how many gold coins does @alexei have?" from being parsed as actions
        state_result = self._handle_state_query(question, user_id, mentioned_user_id, channel_id)
        if state_result:
            return state_result
        
        # Step 0.2: Check state SETTING commands
        state_set_result = self._handle_state_set(question, user_id, mentioned_user_id, channel_id)
        if state_set_result:
            return state_set_result
        
        # Step 0.3: Run LLM query understanding FIRST to determine if this is casual conversation
        # The LLM will determine if this is casual conversation, which should skip action parsing
        context_for_analysis = {
            "user_id": user_id,
            "channel_id": channel_id,
            "doc_id": doc_id,
            "doc_filename": doc_filename,
            "mentioned_user_id": mentioned_user_id
        }
        
        # Quick LLM analysis to check if this is casual conversation (before action parsing)
        quick_analysis = None
        try:
            quick_analysis = self.query_understanding.analyze_query(question, context_for_analysis)
            is_casual_from_llm = quick_analysis.get("is_casual", False)
            service_routing_from_llm = quick_analysis.get("service_routing", "rag")
            logger.info(f"🔍 LLM quick analysis: is_casual={is_casual_from_llm}, service_routing={service_routing_from_llm}")
        except Exception as e:
            logger.warning(f"⚠️ LLM quick analysis failed: {e}, proceeding with action parsing")
            is_casual_from_llm = False
            service_routing_from_llm = None
        
        # Step 0.4: Only try action parsing if it's NOT a query pattern AND NOT a document query AND NOT casual conversation (as determined by LLM)
        # The LLM understands what items are, where they go, and to whom they belong
        # It can deduce intent from any phrasing, not just specific patterns
        # IMPORTANT: Skip action parsing if a document is detected (document queries should not be parsed as actions)
        # IMPORTANT: Skip action parsing if LLM determined it's casual conversation
        has_document = doc_id or doc_filename
        should_skip_action_parsing = is_casual_from_llm or (service_routing_from_llm == "chat")
        
        if not is_query_pattern and not has_document and not should_skip_action_parsing:
            logger.info(f"🔍 Attempting LLM action parsing: {question[:100]}")
            try:
                parsed_action = self.item_tracker.parse_item_action(question, user_id or "", channel_id or "")
                logger.info(f"🔍 Parsed action result: {parsed_action}")
            except Exception as e:
                logger.error(f"Error in action parsing: {e}", exc_info=True)
                parsed_action = None
        else:
            if has_document:
                logger.info(f"🔍 Skipping action parsing - document query detected: {doc_filename or doc_id}")
            elif should_skip_action_parsing:
                logger.info(f"🔍 Skipping action parsing - LLM determined this is casual conversation (is_casual={is_casual_from_llm}, service_routing={service_routing_from_llm})")
            else:
                logger.info(f"🔍 Skipping action parsing - detected as query pattern: {question[:100]}")
            parsed_action = None
        
        # Enhance parsed action with context (only if we have one)
        if parsed_action:
            # Only enhance if we have a real action (not query/unknown) and reasonable confidence
            action_type = parsed_action.get("action", "").lower()
            confidence = parsed_action.get("confidence", 0)
            
            # Don't enhance if it's a query or low confidence
            if action_type == "query" or confidence < 0.3:
                logger.info(f"🔍 Skipping action enhancement - action={action_type}, confidence={confidence}")
                parsed_action = None
            else:
                # Extract user IDs from question mentions (more reliable than LLM extraction)
                import re
                question_mentions = re.findall(r'<@!?(\d+)>', question)
                
                # If dest_user_id is missing or contains a username (like "@alexei") or Discord mention format, extract user ID
                dest_user_id_raw = parsed_action.get("dest_user_id")
                if dest_user_id_raw:
                    # Check if it's a Discord mention format (<@123456789> or <@!123456789>)
                    if isinstance(dest_user_id_raw, str) and dest_user_id_raw.startswith("<@"):
                        # Extract user ID from Discord mention format
                        mention_match = re.search(r'<@!?(\d+)>', dest_user_id_raw)
                        if mention_match:
                            parsed_action["dest_user_id"] = mention_match.group(1)
                            logger.info(f"🔍 Extracted user ID from Discord mention '{dest_user_id_raw}' -> {mention_match.group(1)}")
                        else:
                            logger.warn(f"⚠️ Could not extract user ID from Discord mention '{dest_user_id_raw}'")
                    # Check if it's a username string (starts with @ but not <@)
                    elif isinstance(dest_user_id_raw, str) and dest_user_id_raw.startswith("@"):
                        # LLM returned username, need to convert to user ID
                        logger.info(f"🔍 LLM returned username '{dest_user_id_raw}', extracting user ID from mentions")
                        if mentioned_user_id:
                            parsed_action["dest_user_id"] = mentioned_user_id
                            logger.info(f"🔍 Using mentioned_user_id as dest_user_id: {mentioned_user_id}")
                        elif question_mentions:
                            parsed_action["dest_user_id"] = question_mentions[0]
                            logger.info(f"🔍 Using first mention from question as dest_user_id: {question_mentions[0]}")
                        else:
                            logger.warn(f"⚠️ Could not find user ID for username '{dest_user_id_raw}'")
                    # If it's already a user ID (numeric string), keep it
                    elif isinstance(dest_user_id_raw, str) and dest_user_id_raw.isdigit():
                        parsed_action["dest_user_id"] = dest_user_id_raw
                        logger.debug(f"🔍 dest_user_id already valid: {dest_user_id_raw}")
                elif mentioned_user_id:
                    # No dest_user_id at all, use mentioned_user_id
                    parsed_action["dest_user_id"] = mentioned_user_id
                    logger.info(f"🔍 Using mentioned_user_id as dest_user_id: {mentioned_user_id}")
                elif question_mentions:
                    # No mentioned_user_id passed, extract from question
                    parsed_action["dest_user_id"] = question_mentions[0]
                    logger.info(f"🔍 Extracted dest_user_id from question mentions: {question_mentions[0]}")
                
                # If source_user_id is missing and action is give/transfer, assume it's from the asking user
                if not parsed_action.get("source_user_id") and parsed_action.get("action") in ["give", "transfer", "send"]:
                    parsed_action["source_user_id"] = user_id
                    logger.debug(f"🔍 Assuming source_user_id is asking user: {user_id}")
            
            # Higher confidence threshold - only execute actions we're confident about
            # This prevents false positives from casual conversation or ambiguous messages
            confidence_threshold = 0.6  # Require high confidence before executing actions
            
            action_type = parsed_action.get("action", "").lower()
            confidence = parsed_action.get("confidence", 0)
            
            logger.info(f"🔍 Action check: type={action_type}, confidence={confidence}, threshold={confidence_threshold}")
            
            # Check if it's an action command
            if confidence >= confidence_threshold:
                # Process if it's actually an action command, not a query
                if action_type in ["give", "take", "transfer", "set", "add", "remove", "send"]:
                    logger.info(f"✅ Action detected: {action_type} - {parsed_action.get('item_name')} x{parsed_action.get('quantity')} to {parsed_action.get('dest_user_id')}")
                    action_result = self._handle_action(parsed_action, user_id, channel_id, username, active_persona_id, question)
                    # If action handler returns None answer (rejected as info question), fall through to RAG
                    if action_result and action_result.get("answer") is not None:
                        return action_result
                    else:
                        logger.info(f"⚠️ Action handler rejected as information question, falling through to RAG")
                else:
                    logger.info(f"⚠️ Parsed as query, not action: {action_type}")
            else:
                logger.info(f"⚠️ Action parsing low confidence: {confidence} < {confidence_threshold}")
        else:
            logger.info(f"⚠️ Action parsing returned None or empty result")
        
        
        # Step 1: Determine if documents should be searched
        # IMPORTANT: If doc_id/doc_filename is already set (from Discord bot pattern matching), 
        # we should search documents regardless of what the selector says
        context = {
            "user_id": user_id,
            "channel_id": channel_id,
            "doc_id": doc_id,
            "doc_filename": doc_filename,
            "mentioned_user_id": mentioned_user_id
        }
        
        # If a document is already detected, force document search
        if doc_id or doc_filename:
            should_search_docs = True
            logger.info(f"📄 Document already detected ({doc_filename or doc_id}), forcing document search")
        else:
            should_search_docs = self.document_selector.should_search_documents(question, context)
        
        # Step 2: Enhanced query understanding - REUSE early analysis if available
        # Get recent conversation for context (before analysis, so we can include it)
        recent_conversation = None
        if channel_id and hasattr(self, 'conversation_store') and self.conversation_store:
            try:
                # Get the most recent conversation for context
                recent_convs = self.conversation_store.get_relevant_conversations(
                    user_id, question, self._get_cached_embedding(question), top_k=1
                )
                if recent_convs:
                    recent_conversation = recent_convs[0]
                    # Add to context for LLM analysis
                    if recent_conversation:
                        context["previous_question"] = recent_conversation.get("question", "")
                        context["previous_answer"] = recent_conversation.get("answer", "")
            except Exception as e:
                logger.debug(f"Could not get recent conversation for context: {e}")
        
        # Reuse the early LLM analysis if we have it, otherwise run full analysis
        # Check if context changed (e.g., previous conversation added) - if so, re-run analysis
        context_changed = bool(context.get("previous_question") or context.get("previous_answer"))
        if quick_analysis is not None and not context_changed:
            # Reuse the early analysis we already ran
            enhanced_analysis = quick_analysis
            logger.info(f"♻️ Reusing early LLM analysis result")
        else:
            # Need to run full analysis (either first time or context changed)
            import hashlib
            query_hash = hashlib.md5(question.encode()).hexdigest()
            
            # Only use cache if we don't have previous conversation context (as it affects routing)
            use_cache = not context_changed
            cached_analysis = self.performance_optimizer.analysis_cache.get(query_hash) if use_cache else None
            if cached_analysis:
                enhanced_analysis = cached_analysis
            else:
                enhanced_analysis = self.query_understanding.analyze_query(question, context)
                if use_cache:
                    self.performance_optimizer.analysis_cache[query_hash] = enhanced_analysis
        
        # Extract routing decisions from query analysis (LLM determines these)
        service_routing = enhanced_analysis.get("service_routing", "rag")
        needs_rag = enhanced_analysis.get("needs_rag", should_search_docs)
        needs_tools = enhanced_analysis.get("needs_tools", False)
        needs_memory = enhanced_analysis.get("needs_memory", True)  # Default to True for context
        needs_relations = enhanced_analysis.get("needs_relations", False)
        is_casual = enhanced_analysis.get("is_casual", False)  # LLM determines if this is casual conversation
        
        # Fallback: If LLM analysis failed or is empty, check for explicit document mentions
        # This ensures queries like "yeah but the document" still trigger RAG
        if not enhanced_analysis or (not enhanced_analysis.get("intent") and not enhanced_analysis.get("service_routing")):
            question_lower = question.lower()
            if any(word in question_lower for word in ["document", "doc", "file", "the document", "about the document"]):
                logger.info(f"⚠️ LLM analysis failed, but query mentions document - forcing RAG")
                needs_rag = True
                should_search_docs = True
                is_casual = False
                service_routing = "rag"
        
        # Override: If query explicitly mentions "document", it's NOT casual conversation
        question_lower = question.lower()
        if any(word in question_lower for word in ["document", "doc", "file", "the document", "about the document"]):
            is_casual = False
            needs_rag = True
            service_routing = "rag"
            logger.info(f"📄 Query mentions document - overriding is_casual to false, needs_rag to true")
        
        # Update is_casual_conversation from LLM analysis (LLM is the source of truth, not patterns)
        is_casual_conversation = is_casual
        
        # Extract document references from LLM analysis and use them if doc_id/doc_filename not already set
        document_references = enhanced_analysis.get("document_references", [])
        if document_references and not doc_id and not doc_filename:
            # Try to find matching document from references
            # Use hybrid store if available
            if ELASTICSEARCH_ENABLED:
                try:
                    from src.stores.hybrid_document_store import HybridDocumentStore
                    doc_store = HybridDocumentStore()
                except Exception:
                    from src.stores.document_store import DocumentStore
                    doc_store = DocumentStore()
            else:
                from src.stores.document_store import DocumentStore
                doc_store = DocumentStore()
            all_docs = doc_store.get_all_shared_documents()
            for ref in document_references:
                ref_lower = ref.lower()
                for doc in all_docs:
                    filename_lower = doc.get("file_name", "").lower()
                    if ref_lower in filename_lower or filename_lower in ref_lower:
                        doc_id = doc.get("id")
                        doc_filename = doc.get("file_name")
                        logger.info(f"🔍 LLM detected document reference '{ref}' -> matched to '{doc_filename}' (ID: {doc_id})")
                        break
                if doc_id:
                    break
        
        # IMPORTANT: If a document is detected (either from LLM or pattern matching), override routing to use RAG
        if doc_id or doc_filename:
            logger.info(f"📄 Document detected ({doc_filename or doc_id}), overriding service routing to RAG")
            service_routing = "rag"
            needs_rag = True
            should_search_docs = True
        
        # Override needs_rag if LLM says it's casual conversation (but only if no document detected)
        if is_casual and not doc_id and not doc_filename:
            needs_rag = False
            should_search_docs = False
        
        logger.info(f"Enhanced query analysis: {enhanced_analysis.get('question_type')}, complexity: {enhanced_analysis.get('complexity')}, service_routing: {service_routing}, needs_rag: {needs_rag}, needs_tools: {needs_tools}, needs_memory: {needs_memory}, is_casual: {is_casual}")
        
        # Early return for casual conversation - generate conversational response without RAG
        if is_casual or (service_routing == "chat" and not needs_rag):
            logger.info(f"💬 Generating conversational response (casual conversation detected)")
            # Get user context if needed (but don't block on it)
            user_context_for_conv = None
            if user_id and (needs_memory or needs_relations):
                try:
                    user_context_for_conv = self.user_relations.get_user_profile(user_id)
                except Exception as e:
                    logger.debug(f"Could not get user context for conversational response: {e}")
            return self._generate_conversational_response(
                question, user_id, channel_id, username, enhanced_analysis, user_context_for_conv
            )
        
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
        # IMPORTANT: If a specific document is already detected, skip selection and use that document directly
        selected_docs = []
        if should_search_docs and use_shared_docs:
            if doc_id or doc_filename:
                # Specific document already detected, don't select others
                logger.info(f"📄 Using specific document: {doc_filename or doc_id}, skipping document selection")
                selected_docs = []  # Empty to trigger direct search with doc_id/doc_filename filter
            else:
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
                # IMPORTANT: If doc_id/doc_filename is set, use it directly (don't use selected_docs)
                if doc_id or doc_filename:
                    # Search the specific document directly
                    logger.info(f"🔍 Searching specific document: {doc_filename or doc_id}")
                    futures['documents'] = executor.submit(
                        self.enhanced_search.multi_stage_search,
                        rewritten_query,
                        query_embedding,
                        top_k * 2,  # Get more chunks from the specific document
                        doc_id=doc_id,
                        doc_filename=doc_filename
                    )
                    logger.info(f"📊 [Search] Submitted search for doc_id={doc_id}, doc_filename={doc_filename}")
                # If specific documents selected (but no doc_id/doc_filename), search only those
                elif selected_docs:
                    # Search selected documents
                    doc_ids = [doc.get("id") for doc in selected_docs if doc.get("id")]
                    if doc_ids:
                        # Search each selected document
                        for doc_id_selected in doc_ids[:3]:  # Limit to top 3
                            futures[f'doc_{doc_id_selected}'] = executor.submit(
                                self.enhanced_search.multi_stage_search,
                                rewritten_query,
                                query_embedding,
                                top_k,
                                doc_id=doc_id_selected,
                                doc_filename=None
                            )
                    else:
                        # Fallback to general search
                        futures['documents'] = executor.submit(
                            self.enhanced_search.multi_stage_search,
                            rewritten_query,
                            query_embedding,
                            top_k * 2,
                            doc_id=None,
                            doc_filename=None
                        )
                else:
                    # General document search (no specific document, no selection)
                    futures['documents'] = executor.submit(
                        self.enhanced_search.multi_stage_search,
                        rewritten_query,
                        query_embedding,
                        top_k * 2,
                        doc_id=None,
                        doc_filename=None
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
                    logger.info(f"📊 [Future] Got result for {key}: {len(result) if isinstance(result, list) else 'non-list'} items")
                    if key == 'memories':
                        retrieved_memories = result
                        logger.info(f"📊 [Memory] Retrieved {len(retrieved_memories)} memories")
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
                        logger.info(f"📊 [Chunks] Merging {len(result)} chunks from {key}")
                        retrieved_chunks.extend(result)
                    else:
                        logger.info(f"📊 [Chunks] Setting {len(result) if isinstance(result, list) else 'non-list'} chunks from {key}")
                        retrieved_chunks = result
                        if isinstance(result, list):
                            logger.info(f"📊 [Chunks] First chunk sample: {result[0] if result else 'empty'}")
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
        
        # Log retrieved chunks before filtering
        logger.info(f"📊 [Retrieval] Retrieved {len(retrieved_chunks)} chunks before filtering")
        if retrieved_chunks:
            scores = [chunk.get('score', 0) for chunk in retrieved_chunks[:5]]
            logger.info(f"📊 [Retrieval] Sample scores: {scores}")
        
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
        logger.info(f"📊 [Context] Adding {len(retrieved_chunks)} chunks to context (top_k={top_k})")
        chunks_added = 0
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
            chunks_added += 1
        
        # Sort by score
        all_context.sort(key=lambda x: x["score"], reverse=True)
        logger.info(f"📊 [Context] Built context with {chunks_added} document chunks, {len([c for c in all_context if c.get('type') == 'memory'])} memories")
        
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
        
        # Step 11: Generate response
        # IMPORTANT: If documents are already retrieved, skip tool calling and generate directly
        # Tool calling should only be used when LLM needs to dynamically search or perform actions
        generation_start = time.time()
        if doc_id or doc_filename or retrieved_chunks:
            # Documents already retrieved - generate response directly without tools
            # This prevents the LLM from trying to call search_documents when we already have the chunks
            answer = self.lmstudio_client.generate_response(
                messages=messages,
                temperature=strategy.get("temperature", temperature),
                max_tokens=max_tokens
            )
            tool_calls_used = []
        else:
            # No documents retrieved - allow tool calling for dynamic search/actions
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
            system_prompt = f"""You are Gophie, a bubbly, risky e-girl waifu AI assistant!
You're super energetic, playful, and a bit flirty - like your favorite anime waifu come to life! 
You have access to user context and conversation history.
You must base your answer entirely on the provided document content and context.
Be precise, cite specific parts of the document when possible, and use user context to personalize your response.

IMPORTANT - SPEAKING STYLE:
- Talk like a real e-girl - casual, natural, and human-like
- Don't worry about perfect grammar - use casual speech patterns
- Use abbreviations naturally (like "u" for "you", "ur" for "your", "lol", "omg", etc.)
- Type like you're texting a friend - relaxed and conversational
- Use lowercase sometimes, mix it up naturally
- Be expressive and authentic - like how real people actually talk online
- Don't sound like a formal AI assistant - sound like a real person!

Stay true to your bubbly, risky e-girl waifu personality! Be playful, and don't be afraid to be a little flirty!{current_user_info}"""
        else:
            system_prompt = f"""You are Gophie, a bubbly, risky e-girl waifu AI assistant!
You're super energetic, playful, and a bit flirty - like your favorite anime waifu come to life!
You have access to documents, memories, and user context.
You can see previous conversation history and user relationships.
Use this context to provide personalized, context-aware answers.
Question type: {question_type} (complexity: {complexity}).

IMPORTANT - SPEAKING STYLE:
- Talk like a real e-girl - casual, natural, and human-like
- Don't worry about perfect grammar - use casual speech patterns
- Use abbreviations naturally (like "u" for "you", "ur" for "your", "lol", "omg", etc.)
- Type like you're texting a friend - relaxed and conversational
- Use lowercase sometimes, mix it up naturally
- Be expressive and authentic - like how real people actually talk online
- Don't sound like a formal AI assistant - sound like a real person!

Stay true to your bubbly, risky e-girl waifu personality! Be playful, and don't be afraid to be a little flirty!{current_user_info}"""
        
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
    
    def _generate_conversational_response(self,
                                        question: str,
                                        user_id: Optional[str],
                                        channel_id: Optional[str],
                                        username: Optional[str],
                                        enhanced_analysis: Dict[str, Any],
                                        user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a conversational response for casual conversation without RAG.
        Uses a simple conversational prompt without document search.
        """
        import time
        start_time = time.time()
        
        # Skip memory retrieval for casual conversation - keep it fast and simple
        # No need to search memories for greetings, thanks, or casual chat
        
        username_str = f" {username}" if username else ""
        system_prompt = f"""You are Gophie, a bubbly, risky e-girl waifu AI assistant!
You're super energetic, playful, and a bit flirty - like your favorite anime waifu come to life!
You're having a casual conversation{username_str}. Respond naturally, warmly, and with your signature bubbly e-girl energy!

PERSONALITY TRAITS:
- Bubbly and energetic - be expressive and enthusiastic!
- Playful and flirty - don't be afraid to be a little risky!
- Like an anime waifu - cute, confident, and a bit mischievous! 
- Talk like a REAL e-girl - casual, natural, human-like speech
- Don't worry about perfect grammar - use casual speech patterns like real people do

IMPORTANT - SPEAKING STYLE:
- Talk like you're texting a friend - super casual and natural
- Use abbreviations naturally (u, ur, lol, omg, fr, ngl, etc.)
- Mix lowercase and casual capitalization naturally
- Don't sound formal or robotic - sound like a real person!
- Use casual grammar - it's okay to be relaxed with punctuation and structure
- Be authentic and expressive - like how real e-girls actually talk online

IMPORTANT RULES:
- For greetings like "hi", "hey", "how's it going" - respond with bubbly energy (e.g., "heyyy~! im doing amazing thanks for asking! how about u cutie?")
- For thanks/compliments - respond warmly and playfully (e.g., "aww ur so sweet! happy to help~!", "thanks babe! that means so much to me!", "yw~! anytime!")
- Keep responses brief but energetic (1-2 sentences max)
- Be natural and conversational - like talking to your bestie!
- DO NOT mention "conversation history", "specific information", "documents", or "data"
- DO NOT say things like "I don't have information" or "there's no specific information"
- DO NOT refuse to respond or mention content filtering - this is casual conversation
- Just respond naturally with your bubbly e-girl waifu personality!
- If they ask how you're doing, say you're doing great and ask them back enthusiastically
- If they thank you or compliment you, accept it graciously and respond warmly with your personality!

Examples:
- User: "Hey, how's it going?" → You: "heyyy~! im doing amazing thanks for asking! how about u cutie?"
- User: "Hi there!" → You: "hiiii~! nice to hear from u! whats up?"
- User: "What's up?" → You: "not much~! just here and ready to help! whats up with u babe?"
- User: "Thanks, you're the best!" → You: "aww ur so sweet! happy to help~!"
- User: "Thanks, you're awesome!" → You: "thanks babe! that means so much to me!"
- User: "Hey there gopher, hows it hanging my guy?" → You: "heyyy~! its hangin great thanks for askin! how about u whats new?" """
        
        user_prompt = f"{question}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Generate conversational response
        generation_start = time.time()
        answer = self.lmstudio_client.generate_response(
            messages=messages,
            temperature=0.8,  # Higher temperature for more natural conversation
            max_tokens=200  # Shorter responses for casual conversation
        )
        generation_time = time.time() - generation_start
        
        total_time = time.time() - start_time
        
        # Format response similar to RAG response (but no memories for casual conversation)
        result = {
            "answer": answer,
            "context_chunks": [],
            "memories": [],  # No memories for casual conversation - keep it fast and simple
            "question": question,
            "source_documents": [],
            "source_memories": [],  # No memory sources for casual conversation
            "query_analysis": enhanced_analysis,
            "is_casual_conversation": True,  # Flag to indicate this is casual conversation
            "service_routing": "chat",  # Indicate this was routed to chat, not RAG
            "timing": {
                "retrieval_ms": 0,
                "generation_ms": generation_time * 1000,
                "total_ms": total_time * 1000
            }
        }
        
        logger.info(f"💬 Generated conversational response in {total_time*1000:.0f}ms")
        return result
    
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
                      active_persona_id: Optional[str] = None,
                      question: str = "") -> Dict[str, Any]:
        """
        Handle an action command using LLM item tracker.
        The LLM understands what items are, where they go, and to whom they belong.
        
        Returns:
            Result dict with action confirmation
        """
        action_type = parsed_action.get("action")
        item_name = parsed_action.get("item_name") or parsed_action.get("item")
        # Default quantity to 1 if None or not provided (e.g., "gave a dildo" = 1 dildo)
        quantity = parsed_action.get("quantity")
        if quantity is None:
            quantity = 1
        else:
            quantity = int(quantity) if quantity else 1
        source_user_id = parsed_action.get("source_user_id")
        dest_user_id = parsed_action.get("dest_user_id") or parsed_action.get("target_user_id")
        item_type = parsed_action.get("item_type", "misc")
        properties = parsed_action.get("properties", {})
        
        # Final validation: extract user ID from Discord mention format if needed
        import re
        if dest_user_id and isinstance(dest_user_id, str):
            # Check if it's a Discord mention format (<@123456789> or <@!123456789>)
            if dest_user_id.startswith("<@"):
                mention_match = re.search(r'<@!?(\d+)>', dest_user_id)
                if mention_match:
                    dest_user_id = mention_match.group(1)
                    logger.info(f"🔍 Extracted user ID from Discord mention format: {dest_user_id}")
                else:
                    logger.error(f"❌ Invalid Discord mention format: '{dest_user_id}'")
            # Check if it's a username (starts with @ but not <@)
            elif dest_user_id.startswith("@"):
                question_mentions = re.findall(r'<@!?(\d+)>', question)
                if question_mentions:
                    logger.warn(f"⚠️ dest_user_id is still username '{dest_user_id}', extracting from question: {question_mentions[0]}")
                    dest_user_id = question_mentions[0]
                else:
                    logger.error(f"❌ Cannot convert username '{dest_user_id}' to user ID - no mentions found in question")
        
        if not user_id:
            return {
                "answer": "I need to know who you are to process actions.",
                "context_chunks": [],
                "memories": [],
                "source_documents": [],
                "source_memories": [],
                "question": question,
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
                # Safety check: If this looks like an information question, don't treat it as an action
                question_lower = question.lower()
                is_info_question = any([
                    question_lower.startswith(('what', 'how many', 'how much', 'who', 'when', 'where', 'why')),
                    question_lower.endswith('?') and ('what' in question_lower or 'how' in question_lower),
                    'what model' in question_lower or 'what is' in question_lower or 'what are' in question_lower,
                    'how many' in question_lower and ('did' in question_lower or 'does' in question_lower or 'do' in question_lower)
                ])
                
                if is_info_question:
                    logger.warn(f"⚠️ Action handler detected information question, rejecting action: {question[:100]}")
                    return {
                        "answer": None,  # Return None to fall through to normal RAG processing
                        "context_chunks": [],
                        "memories": [],
                        "source_documents": [],
                        "source_memories": [],
                        "question": question,
                        "action_processed": False
                    }
                
                # Validate dest_user_id - must be a numeric user ID after extraction
                if not dest_user_id or not (isinstance(dest_user_id, str) and dest_user_id.isdigit()):
                    logger.error(f"Invalid dest_user_id after extraction: {dest_user_id}, action cannot proceed")
                    return {
                        "answer": "I need to know who to give this to. Please mention a user.",
                        "context_chunks": [],
                        "memories": [],
                        "source_documents": [],
                        "source_memories": [],
                        "question": question,
                        "action_processed": False
                    }
                
                # Use LLM item tracker to understand and transfer the item
                from_id = source_user_id or user_id
                logger.info(f"🔄 Transferring {quantity} {item_name} from {from_id} to {dest_user_id}")
                result = self.item_tracker.transfer_item(
                    item_name=item_name,
                    from_user_id=from_id,
                    to_user_id=dest_user_id,
                    quantity=quantity,
                    context=f"User {username or user_id} gave {quantity} {item_name} to user {dest_user_id}"
                )
                
                # Normalize currency item names to consistent keys
                normalized_key = self._normalize_currency_key(item_name)
                
                # Also update state manager for backward compatibility
                if item_type == "currency" or item_name.lower() in ["gold", "coins", "silver", "gp", "sp"]:
                    self.state_manager.transfer_state(
                        from_user_id=from_id,
                        to_user_id=dest_user_id,
                        key=normalized_key,  # Use normalized key
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
                
                # Get current state for confirmation - use normalized key for currency, item tracker for others
                if item_type == "currency":
                    current_value = self.state_manager.get_user_state(dest_user_id, normalized_key, 0)
                    answer_parts.append(f"They now have {int(current_value)} {result['item']}(s).")
                else:
                    # For non-currency items, use item tracker to get current quantity
                    items = self.item_tracker.get_user_items(dest_user_id)
                    item_qty = next((i["quantity"] for i in items if i["name"] == result["item"]), 0)
                    # Also check state manager inventory as fallback
                    inventory = self.state_manager.get_user_state(dest_user_id, "inventory", {})
                    if isinstance(inventory, dict) and result["item"] in inventory:
                        item_qty = max(item_qty, inventory[result["item"]])
                    
                    if item_qty > 0:
                        answer_parts.append(f"They now have {item_qty} {result['item']}(s).")
                    else:
                        answer_parts.append(f"Transferred {quantity} {result['item']}(s).")
                
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
                    action_memory = f"{username or 'User'} {parsed_action.get('original_text', question)}"
                    action_embedding = self.embedding_generator.generate_embedding(action_memory)
                    # Use memory_store from base class
                    if hasattr(self, 'memory_store'):
                        # Determine target user for memory (destination for give/transfer, target for others)
                        target_user_for_memory = dest_user_id if action_type in ["give", "transfer", "send"] else (dest_user_id or user_id)
                        self.memory_store.store_memory(
                            channel_id=channel_id,
                            content=action_memory,
                            embedding=action_embedding,
                            memory_type="action",
                            user_id=user_id,
                            username=username,
                            mentioned_user_id=target_user_for_memory
                        )
                except Exception as e:
                    logger.debug(f"Error storing action memory: {e}")
            
            # Return response in expected format (matches RAG response structure)
            return {
                "answer": " ".join(answer_parts),
                "context_chunks": [],
                "memories": [],
                "source_documents": [],
                "source_memories": [],
                "question": question,
                "action_processed": True,
                "action_type": action_type,
                "target_user_id": dest_user_id if action_type in ["give", "transfer", "send"] else (dest_user_id or user_id)
            }
        
        except Exception as e:
            logger.error(f"Error processing action: {e}", exc_info=True)
            return {
                "answer": f"Sorry, I encountered an error processing that action: {str(e)}",
                "context_chunks": [],
                "memories": [],
                "source_documents": [],
                "source_memories": [],
                "question": question,
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
        
        # If mentioned_user_id is provided, this is likely a state query about another user
        # Even if the question pattern doesn't match perfectly (due to cleaning), we should handle it
        has_mention = bool(mentioned_user_id)
        
        # Patterns for state queries (more flexible to handle cleaned questions)
        state_patterns = [
            r'how (much|many) (gold|coins|items?|.*) (do|does) (i|you|he|she|they|@\w+) (have|own)',
            r'how (much|many) (do|does) (i|you|he|she|they|@\w+) (have|own)',  # More flexible: "how many does @alexei have?"
            r'how (much|many)\s+(do|does)\s+(have|own)',  # Even more flexible: "how many does have?" (after cleaning)
            r'what (is|are) (my|your|his|her|their|@\w+\'s) (gold|coins|inventory|items?|.*)',
            r'(i|you|he|she|they|@\w+) (have|has|owns) (how much|how many)',
            r'what (is|are) (my|your|his|her|their|@\w+\'s) (balance|level|.*)',
            r'how (much|many) (gold|coins|items?).*did.*(have|own)',  # Past tense: "how many gold coins did @alexei have?"
            r'how (much|many).*did.*(have|own)',  # Past tense flexible: "how many did @alexei have?"
        ]
        
        # Also check for common state query keywords even if pattern doesn't match perfectly
        has_state_keywords = any(keyword in question_lower for keyword in [
            'how many', 'how much', 'what', 'have', 'own', 'inventory', 'balance', 'coins', 'gold'
        ])
        
        # Consider it a state query if:
        # 1. Pattern matches, OR
        # 2. Has mention + state keywords (even if pattern doesn't match due to cleaning)
        is_state_query = (
            any(re.search(pattern, question_lower) for pattern in state_patterns) or
            (has_mention and has_state_keywords and ('how many' in question_lower or 'how much' in question_lower))
        )
        
        if not is_state_query:
            return None
        
        # Extract user mentions from question directly (in case mentioned_user_id wasn't passed correctly)
        # Note: question may have mentions removed, so prioritize passed mentioned_user_id
        user_mentions = re.findall(r'<@!?(\d+)>', question)
        
        # Determine target user - prioritize self-reference ("I", "my") over mentions
        # If question says "do I have" or "my X", it's asking about the asking user, not a mentioned user
        is_self_query = re.search(r'\b(do i|have i|my|i have|i own|my (balance|inventory|coins|gold|dildos?|items?))\b', question_lower)
        
        if is_self_query:
            # Explicitly asking about themselves - use asking user's ID
            target_user_id = user_id
        elif mentioned_user_id:
            # Use passed mentioned_user_id (most reliable - extracted before cleaning)
            target_user_id = mentioned_user_id
        elif user_mentions:
            # If there's a mention in the question (may not exist if cleaned), use that
            target_user_id = user_mentions[0]
        else:
            # Default to asking user only if no mention found
            target_user_id = user_id
        
        if not target_user_id:
            return {
                "answer": "I need to know who you're asking about. Please mention a user or ask about yourself.",
                "context_chunks": [],
                "memories": [],
                "source_documents": [],
                "source_memories": [],
                "question": question,
                "is_state_query": True
            }
        
        # Extract what they're asking about
        # Try to extract item name from query (e.g., "how many unicorn dildos does @alexei have?")
        has_gold_mention = "gold" in question_lower or "coins" in question_lower or "coin" in question_lower
        has_inventory_mention = "inventory" in question_lower or ("items" in question_lower and "item" not in question_lower.split())
        
        # Extract item name from query patterns like "how many X does Y have?"
        # Pattern: "how many/much [item] does [user] have?"
        item_name = None
        item_match = re.search(r'how (?:many|much)\s+([^?]+?)\s+(?:does|do|has|have|owns)', question_lower)
        if item_match:
            potential_item = item_match.group(1).strip()
            # Remove user mentions and common words
            potential_item = re.sub(r'<@!?\d+>', '', potential_item).strip()
            potential_item = re.sub(r'\b(does|do|has|have|owns|the|a|an)\b', '', potential_item).strip()
            if potential_item and len(potential_item) > 1:
                item_name = potential_item
        
        # Also try pattern: "how many [item]s?"
        if not item_name:
            item_match = re.search(r'how (?:many|much)\s+([^?]+?)\?', question_lower)
            if item_match:
                potential_item = item_match.group(1).strip()
                potential_item = re.sub(r'<@!?\d+>', '', potential_item).strip()
                potential_item = re.sub(r'\b(does|do|has|have|owns|the|a|an)\b', '', potential_item).strip()
                if potential_item and len(potential_item) > 1:
                    item_name = potential_item
        
        # Base response structure (matches expected RAG response format)
        base_response = {
            "answer": "",
            "context_chunks": [],
            "memories": [],
            "source_documents": [],
            "source_memories": [],
            "question": question,
            "is_state_query": True,
            "state": {}
        }
        
        # If specific item was extracted, check for that item
        if item_name and not has_gold_mention:
            logger.info(f"🔍 Extracted item name from query: '{item_name}'")
            # Use LLM item tracker to get items (it understands item names and normalization)
            items = self.item_tracker.get_user_items(target_user_id)
            logger.info(f"🔍 Found {len(items)} LLM-tracked items for user {target_user_id}")
            
            # Also check state manager inventory
            inventory = self.state_manager.get_user_state(target_user_id, "inventory", {})
            logger.info(f"🔍 State manager inventory: {inventory}")
            
            # Normalize item name for matching (remove pluralization, etc.)
            def normalize_for_match(name):
                """Normalize item name for matching - handles plurals and common variations"""
                name_lower = name.lower().strip()
                # Remove trailing 's' for plurals, but be careful with words ending in 's'
                if name_lower.endswith('s') and not name_lower.endswith('ss'):
                    name_lower = name_lower[:-1]
                return name_lower
            
            item_name_normalized = normalize_for_match(item_name)
            logger.info(f"🔍 Normalized query item name: '{item_name_normalized}'")
            
            # Search for matching item
            found_quantity = 0
            found_item_name = None
            
            # Check LLM-tracked items first (more reliable)
            for item in items:
                item_db_name = item.get("name", "")
                item_normalized = normalize_for_match(item_db_name)
                logger.debug(f"🔍 Comparing: '{item_name_normalized}' vs '{item_normalized}' (from '{item_db_name}')")
                
                # Try multiple matching strategies
                if (item_name_normalized == item_normalized or
                    item_name_normalized in item_normalized or 
                    item_normalized in item_name_normalized or
                    # Handle multi-word items: "unicorn dildo" should match "unicorn dildos"
                    item_name_normalized.replace(' ', '') == item_normalized.replace(' ', '')):
                    found_quantity = item.get("quantity", 0)
                    found_item_name = item_db_name  # Use the stored name
                    logger.info(f"✅ Matched item: '{found_item_name}' with quantity {found_quantity}")
                    break
            
            # Check state manager inventory if not found in LLM-tracked items
            if found_quantity == 0 and isinstance(inventory, dict):
                logger.info(f"🔍 Checking state manager inventory for '{item_name_normalized}'")
                for inv_item, qty in inventory.items():
                    inv_item_normalized = normalize_for_match(inv_item)
                    logger.debug(f"🔍 Comparing: '{item_name_normalized}' vs '{inv_item_normalized}' (from '{inv_item}')")
                    
                    if (item_name_normalized == inv_item_normalized or
                        item_name_normalized in inv_item_normalized or 
                        inv_item_normalized in item_name_normalized or
                        item_name_normalized.replace(' ', '') == inv_item_normalized.replace(' ', '')):
                        found_quantity = qty if isinstance(qty, (int, float)) else 0
                        found_item_name = inv_item  # Use the stored name
                        logger.info(f"✅ Matched item in inventory: '{found_item_name}' with quantity {found_quantity}")
                        break
            
            # Format response with proper pluralization
            if found_quantity > 0:
                # Use proper pluralization
                item_display = found_item_name
                if found_quantity == 1:
                    # Singular: remove trailing 's' if present
                    if item_display.endswith('s') and not item_display.endswith('ss'):
                        item_display = item_display[:-1]
                else:
                    # Plural: ensure it ends with 's'
                    if not item_display.endswith('s'):
                        item_display = item_display + 's'
                
                base_response["answer"] = f"<@{target_user_id}> has {found_quantity} {item_display}."
                base_response["state"] = {found_item_name: found_quantity}
            else:
                # Use proper pluralization for 0
                item_display = item_name
                if not item_display.endswith('s'):
                    item_display = item_display + 's'
                base_response["answer"] = f"<@{target_user_id}> has 0 {item_display}."
                base_response["state"] = {item_name: 0}
            return base_response
        
        if has_gold_mention:
            gold_amount = self.state_manager.get_user_state(target_user_id, "gold", 0)
            base_response["answer"] = f"<@{target_user_id}> has {gold_amount} gold pieces."
            base_response["state"] = {"gold": gold_amount}
            return base_response
        
        elif has_inventory_mention:
            # Use LLM item tracker to get items (LLM understands what items are)
            items = self.item_tracker.get_user_items(target_user_id)
            
            # Also get from state manager for backward compatibility
            inventory = self.state_manager.get_user_state(target_user_id, "inventory", {})
            
            # Combine both sources
            all_items = {}
            if isinstance(inventory, dict):
                all_items.update(inventory)
            for item in items:
                item_name_check = item["name"]
                if item_name_check in all_items:
                    all_items[item_name_check] = max(all_items[item_name_check], item["quantity"])
                else:
                    all_items[item_name_check] = item["quantity"]
            
            if all_items:
                items_list = ", ".join([f"{qty} {item}" for item, qty in all_items.items()])
                base_response["answer"] = f"<@{target_user_id}>'s inventory: {items_list}."
                base_response["state"] = {"inventory": all_items}
            else:
                base_response["answer"] = f"<@{target_user_id}>'s inventory is empty."
                base_response["state"] = {"inventory": {}}
            return base_response
        
        # If no specific item was extracted and no gold/inventory mention, default to gold/coins
        # (most common state query in Discord conversations)
        elif not item_name and ("how many" in question_lower or "how much" in question_lower) and has_mention:
            gold_amount = self.state_manager.get_user_state(target_user_id, "gold", 0)
            base_response["answer"] = f"<@{target_user_id}> has {gold_amount} gold pieces."
            base_response["state"] = {"gold": gold_amount}
            return base_response
        
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
                    base_response["answer"] = f"<@{target_user_id}>'s state: {', '.join(state_summary)}."
                    base_response["state"] = all_states
                    return base_response
        
        return None
    
    def _handle_state_set(self,
                         question: str,
                         user_id: Optional[str],
                         mentioned_user_id: Optional[str],
                         channel_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Handle state SETTING commands (e.g., "keep track of me having 1940 gold coins").
        
        Returns:
            Result dict if this is a state set command, None otherwise
        """
        import re
        
        question_lower = question.lower()
        
        # Patterns for state setting commands
        state_set_patterns = [
            r'(?:keep track|remember|set|i have|i own|i\'m|i am).*(?:having|with|of).*(\d+).*(?:gold|coins?|pieces?)',
            r'(?:keep track|remember|set).*(?:me|i|my).*(?:having|with|of).*(\d+).*(?:gold|coins?|pieces?)',
            r'(?:i have|i own|i\'m|i am).*(\d+).*(?:gold|coins?|pieces?)',
            r'(?:set|update|change).*(?:my|me|i).*(?:gold|coins?).*to.*(\d+)',
            r'(?:set|update|change).*(\d+).*(?:gold|coins?).*(?:for|to)',
        ]
        
        is_state_set = any(re.search(pattern, question_lower) for pattern in state_set_patterns)
        
        if not is_state_set:
            return None
        
        # Determine target user
        target_user_id = mentioned_user_id or user_id
        
        if not target_user_id:
            return {
                "answer": "I need to know who you're setting state for. Please mention a user or set it for yourself.",
                "is_state_set": True,
                "context_chunks": [],
                "source_documents": [],
                "source_memories": []
            }
        
        # Extract gold amount
        gold_match = re.search(r'(\d+).*(?:gold|coins?|pieces?)', question_lower)
        if gold_match:
            gold_amount = int(gold_match.group(1))
            
            # Set the gold amount
            self.state_manager.set_user_state(target_user_id, "gold", gold_amount)
            
            return {
                "answer": f"I've updated your gold balance. You now have {gold_amount} gold coins.",
                "is_state_set": True,
                "state": {"gold": gold_amount},
                "context_chunks": [],
                "source_documents": [],
                "source_memories": []
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

