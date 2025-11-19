"""
GopherAgent - Smart agentic system for intelligent message routing and decision-making.
Optimized for RTX 3080 GPU with fast inference, batching, and caching.
"""
import time
import hashlib
import json
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from cachetools import TTLCache
from concurrent.futures import ThreadPoolExecutor
import torch

from src.clients.llm_client_factory import get_default_llm_client
from src.processors.embedding_generator import EmbeddingGenerator
from src.agents.react_agent import ReActAgent
from config import (
    USE_GPU, EMBEDDING_BATCH_SIZE,
    CACHE_ENABLED, CACHE_MAX_SIZE, CACHE_TTL_SECONDS
)
from logger_config import logger


class GopherAgent:
    """
    GopherAgent - Intelligent agentic system for message routing and decision-making.
    Optimized for RTX 3080 GPU with:
    - Fast LLM inference via LMStudio
    - GPU-accelerated embeddings for similarity
    - Aggressive caching for speed
    - Batch processing when possible
    - Smart routing decisions
    """
    
    def __init__(self, 
                 llm_client = None,  # Can be any LLM client (LMStudioClient, OpenAICompatibleClient, etc.)
                 embedding_generator: Optional[EmbeddingGenerator] = None,
                 cache_ttl: int = 300):  # 5 minute cache
        """
        Initialize GopherAgent.
        
        Args:
            llm_client: LLM client (auto-created using factory if None, supports multiple providers)
            embedding_generator: Embedding generator (auto-created if None)
            cache_ttl: Cache TTL in seconds (default: 5 minutes)
        """
        # Initialize LLM client (use factory to support multiple providers)
        if llm_client is None:
            self.llm_client = get_default_llm_client()
        else:
            self.llm_client = llm_client
        
        # Initialize embedding generator (GPU-optimized for RTX 3080)
        if embedding_generator is None:
            device = USE_GPU if USE_GPU != 'auto' else None
            self.embedding_generator = EmbeddingGenerator(
                device=device,
                batch_size=EMBEDDING_BATCH_SIZE
            )
        else:
            self.embedding_generator = embedding_generator
        
        # Aggressive caching for speed
        self.intent_cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=cache_ttl)
        self.routing_cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=cache_ttl)
        
        # Request deduplication - prevent duplicate concurrent requests
        self.pending_requests = {}  # cache_key -> future
        
        # Batch processing queue
        self.batch_queue = []
        self.batch_executor = ThreadPoolExecutor(max_workers=2)
        
        # Pattern cache for common intents (faster than LLM)
        self.pattern_cache = {}
        
        # Initialize ReAct Agent for complex tasks
        try:
            self.react_agent = ReActAgent()
            logger.info("✅ ReAct Agent initialized")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize ReAct Agent: {e}")
            self.react_agent = None
        
        # GPU status
        self.use_gpu = self.embedding_generator.device == 'cuda' and torch.cuda.is_available()
        if self.use_gpu:
            logger.info(f"🚀 GopherAgent initialized with GPU acceleration (RTX 3080)")
        else:
            logger.info(f"⚠️ GopherAgent initialized without GPU (using CPU)")
        
        # Performance metrics
        self.metrics = {
            "intent_classifications": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_latency_ms": 0,
            "gpu_inference_count": 0
        }
    
    def classify_intent(self, 
                        message: str,
                        context: Optional[Dict[str, Any]] = None,
                        use_cache: bool = True) -> Dict[str, Any]:
        """
        Classify message intent using LLM (fast, cached).
        
        Args:
            message: Message text to classify
            context: Optional context (recent messages, user info, etc.)
            use_cache: Whether to use cache (default: True)
            
        Returns:
            {
                "intent": str,  # "question", "command", "casual", "action", "upload", "ignore"
                "should_respond": bool,
                "confidence": float,
                "routing": str,  # "rag", "chat", "tools", "memory", "action"
                "needs_rag": bool,
                "needs_tools": bool,
                "needs_memory": bool,
                "is_casual": bool,
                "document_references": List[str],
                "latency_ms": float
            }
        """
        start_time = time.time()
        
        # ⚡ FAST PATH: Only for truly unambiguous cases (URLs, attachments, image generation)
        # Let LLM handle natural language (greetings, questions, etc.)
        quick_result = self._quick_pattern_check_unambiguous(message, context)
        if quick_result:
            quick_result["latency_ms"] = (time.time() - start_time) * 1000
            quick_result["fast_path"] = True
            logger.debug(f"⚡ Fast path: {quick_result.get('routing')} for message: {message[:50]}...")
            return quick_result
        
        # Check cache first
        cache_key = None
        if use_cache and CACHE_ENABLED:
            cache_key = self._get_cache_key(message, context)
            if cache_key in self.intent_cache:
                self.metrics["cache_hits"] += 1
                cached_result = self.intent_cache[cache_key].copy()
                cached_result["latency_ms"] = (time.time() - start_time) * 1000
                cached_result["cached"] = True
                return cached_result
            
            # Check for pending request (deduplication)
            if cache_key in self.pending_requests:
                # Wait for existing request to complete
                try:
                    result = self.pending_requests[cache_key].result(timeout=5.0)
                    result["latency_ms"] = (time.time() - start_time) * 1000
                    result["cached"] = True
                    result["deduplicated"] = True
                    return result
                except Exception as e:
                    logger.debug(f"Pending request failed: {e}, making new request")
                    # Remove failed pending request
                    self.pending_requests.pop(cache_key, None)
        
        self.metrics["cache_misses"] += 1
        
        # Normalize attachment detection (handle both camelCase and snake_case)
        has_attachments = context and (context.get("hasAttachments") or context.get("has_attachments") or False)
        has_images = context and (context.get("imageUrls") or context.get("image_urls") or [])
        has_images = len(has_images) > 0 if isinstance(has_images, list) else False
        
        # Build context string
        context_str = ""
        if context:
            if context.get("recent_messages"):
                recent = context["recent_messages"][:3]  # Last 3 messages
                context_str += f"\nRecent messages: {json.dumps(recent, ensure_ascii=False)}"
            if has_attachments:
                context_str += "\nMessage has file attachments."
            if has_images:
                image_count = len(context.get("imageUrls") or context.get("image_urls") or [])
                context_str += f"\nMessage has {image_count} image attachment(s)."
            if context.get("is_mentioned") or context.get("isMentioned"):
                context_str += "\nBot was mentioned in message."
        
        # OPTIMIZED: Concise LLM prompt for natural language understanding
        # Truncate message if too long to reduce token usage
        message_truncated = message[:400] if len(message) > 400 else message  # Slightly longer for better context
        
        # Build minimal context
        context_parts = []
        if has_attachments:
            context_parts.append("Has attachments")
        if has_images:
            image_count = len(context.get("imageUrls") or context.get("image_urls") or []) if context else 0
            context_parts.append(f"Has {image_count} image(s)")
        if context and (context.get("is_mentioned") or context.get("isMentioned")):
            context_parts.append("Bot mentioned")
        if context and context.get("recent_messages"):
            context_parts.append(f"{len(context['recent_messages'])} recent messages")
        
        context_str = ". ".join(context_parts) if context_parts else ""
        context_line = f"\nContext: {context_str}." if context_str else ""
        
        # Natural language prompt - let LLM understand intent naturally
        prompt = f"""Classify the intent of this message naturally. Respond with JSON only.

Message: "{message_truncated}"{context_line}

Classify as:
- intent: "question" (asking something), "command" (telling bot to do something), "casual" (greeting/conversation), "action" (state change), "upload" (file), "ignore" (not for bot)
- should_respond: true/false
- confidence: 0.0-1.0
- routing: "rag" (needs document search), "chat" (casual conversation), "tools" (needs tool execution), "memory" (needs memory), "action" (state change)
- needs_rag: true if needs document search
- needs_tools: true if needs tool execution
- needs_memory: true if needs memory retrieval
- is_casual: true if casual conversation/greeting

{{"intent":"question|command|casual|action|upload|ignore","should_respond":true|false,"confidence":0.0-1.0,"routing":"rag|chat|tools|memory|action","needs_rag":true|false,"needs_tools":true|false,"needs_memory":true|false,"is_casual":true|false}}"""
        
        # Create future for deduplication if cache enabled
        from concurrent.futures import Future
        future = None
        if use_cache and CACHE_ENABLED and cache_key:
            future = Future()
            self.pending_requests[cache_key] = future
        
        try:
            # OPTIMIZED: Fast LLM call (low temperature for consistency, reduced tokens for speed)
            # Use reasonable timeout (15s for classification - thinking models may need more time)
            try:
                # Temporarily adjust timeout for classification
                original_timeout = getattr(self.llm_client, 'timeout', 30)
                if hasattr(self.llm_client, 'timeout'):
                    self.llm_client.timeout = 30  # Increased to 30s for GLM-4.6 thinking model (needs more time for reasoning)
                
                try:
                    response = self.llm_client.generate_response(
                        messages=[
                            {"role": "system", "content": "Fast intent classifier. JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.1,  # Low temperature for consistent classification
                        max_tokens=1500  # Increased significantly for GLM-4.6 thinking model (reasoning uses ~500-800 tokens, then needs ~100-200 for JSON)
                    )
                finally:
                    # Restore original timeout
                    if hasattr(self.llm_client, 'timeout'):
                        self.llm_client.timeout = original_timeout
            except Exception as e:
                logger.warning(f"LLM call failed in GopherAgent: {e}, using fallback")
                if future and not future.done():
                    try:
                        future.set_exception(e)
                    except Exception:
                        pass  # Future might already be done
                    self.pending_requests.pop(cache_key, None)
                raise
            
            # Handle empty or None responses (common with thinking models)
            # Retry once with a slightly longer prompt if we get empty response
            if not response or (isinstance(response, str) and not response.strip()):
                logger.warning(f"Empty response from LLM, retrying with more explicit prompt")
                # Retry with a more explicit prompt
                retry_prompt = f"""You must classify this message intent. Respond with ONLY valid JSON, no other text.

Rules:
- Greetings (hi, hello, hey, how are you, etc.) → routing:"chat", needs_rag:false, is_casual:true
- Questions about documents/files → routing:"rag", needs_rag:true
- Only use RAG if explicitly asking about documents or information retrieval is needed

Message: "{message_truncated}"{short_context_str}

Required JSON format:
{{"intent":"question|command|casual|action|upload|ignore","should_respond":true|false,"confidence":0.0-1.0,"routing":"rag|chat|tools|memory|action","needs_rag":true|false,"needs_tools":true|false,"needs_memory":true|false,"is_casual":true|false}}

Respond now with JSON only:"""
                
                try:
                    original_timeout = getattr(self.llm_client, 'timeout', 30)
                    if hasattr(self.llm_client, 'timeout'):
                        self.llm_client.timeout = 15
                    try:
                        response = self.llm_client.generate_response(
                            messages=[
                                {"role": "system", "content": "You are a fast intent classifier. You MUST respond with valid JSON only. No thinking, no explanation, just JSON."},
                                {"role": "user", "content": retry_prompt}
                            ],
                            temperature=0.1,
                            max_tokens=100
                        )
                    finally:
                        if hasattr(self.llm_client, 'timeout'):
                            self.llm_client.timeout = original_timeout
                    
                    # Check if retry worked
                    if response and isinstance(response, str) and response.strip():
                        logger.info(f"Retry succeeded, got response: {response[:100]}")
                    else:
                        logger.warning(f"Retry also returned empty response, using fallback")
                        return self._fallback_classify(message, context, start_time)
                except Exception as retry_error:
                    logger.warning(f"Retry failed: {retry_error}, using fallback")
                    return self._fallback_classify(message, context, start_time)
            
            # For Chutes thinking models, the response might be in reasoning_content
            # Try to extract JSON from reasoning if it's a long reasoning response
            if isinstance(response, str) and len(response) > 500 and 'reasoning' in response.lower():
                # This might be reasoning_content - try to extract JSON from it
                import re
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
                if json_match:
                    try:
                        parsed_json = json.loads(json_match.group(0))
                        logger.info(f"Extracted JSON from reasoning_content")
                        return parsed_json
                    except json.JSONDecodeError:
                        pass  # Fall through to normal parsing
            
            # Parse JSON response
            result = self._parse_json_response(response)
            
            # Add metadata
            latency_ms = (time.time() - start_time) * 1000
            result["latency_ms"] = latency_ms
            result["cached"] = False
            
            # Update metrics
            self.metrics["intent_classifications"] += 1
            total_latency = self.metrics["avg_latency_ms"] * (self.metrics["intent_classifications"] - 1)
            self.metrics["avg_latency_ms"] = (total_latency + latency_ms) / self.metrics["intent_classifications"]
            
            # Cache result
            if use_cache and CACHE_ENABLED and cache_key:
                self.intent_cache[cache_key] = result.copy()
            
            # Complete future for deduplication
            if future and not future.done():
                try:
                    future.set_result(result)
                except Exception:
                    pass  # Future might already be done
                self.pending_requests.pop(cache_key, None)
            
            return result
            
        except Exception as e:
            # Complete future with exception (only if not already done)
            if future and not future.done():
                try:
                    future.set_exception(e)
                except Exception:
                    pass  # Future might already be done or set
                self.pending_requests.pop(cache_key, None)
            
            logger.error(f"Error classifying intent: {e}", exc_info=True)
            # Fallback to pattern-based classification
            return self._fallback_classify(message, context, start_time)
    
    def route_message(self,
                     message: str,
                     context: Optional[Dict[str, Any]] = None,
                     intent_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Route message to appropriate handler based on intent with enhanced context awareness.
        
        Args:
            message: Message text
            context: Optional context (recent messages, user info, etc.)
            intent_result: Pre-computed intent (if available)
            
        Returns:
            {
                "handler": str,  # "rag", "chat", "tools", "memory", "action", "upload", "ignore"
                "intent": Dict[str, Any],
                "routing_confidence": float,
                "latency_ms": float,
                "reasoning": str  # Explanation of routing decision
            }
        """
        start_time = time.time()
        reasoning_parts = []
        
        # Normalize attachment detection (handle both camelCase and snake_case)
        has_attachments = context and (context.get("hasAttachments") or context.get("has_attachments") or False)
        has_images = context and (context.get("imageUrls") or context.get("image_urls") or [])
        has_images = len(has_images) > 0 if isinstance(has_images, list) else False
        
        # Check for image attachments - these need vision/tools
        if has_images:
            return {
                "handler": "tools",
                "intent": {
                    "intent": "question",
                    "should_respond": True,
                    "needs_tools": True,
                    "needs_rag": False,
                    "is_casual": False
                },
                "routing_confidence": 0.95,
                "latency_ms": (time.time() - start_time) * 1000,
                "reasoning": "image attachment detected - requires vision processing"
            }
        
        # ⚡ FAST PATH: Only for truly unambiguous cases (URLs, attachments, image generation)
        # Everything else uses LLM for natural language understanding
        quick_result = self._quick_pattern_check_unambiguous(message, context)
        if quick_result:
            # Fast path result - convert to routing format
            routing = quick_result.get("routing", "chat")
            handler_map = {
                "tools": "tools",
                "upload": "upload",
                "chat": "chat",
                "rag": "rag"
            }
            handler = handler_map.get(routing, "chat")
            
            latency_ms = (time.time() - start_time) * 1000
            return {
                "handler": handler,
                "intent": quick_result,
                "routing_confidence": quick_result.get("confidence", 0.95),
                "latency_ms": latency_ms,
                "reasoning": f"fast_path: {routing}",
                "fast_path": True
            }
        
        # Get intent if not provided
        if intent_result is None:
            intent_result = self.classify_intent(message, context)
        
        # Route based on intent with enhanced context awareness
        intent = intent_result.get("intent", "ignore")
        routing = intent_result.get("routing", "chat")
        should_respond = intent_result.get("should_respond", False)
        confidence = intent_result.get("confidence", 0.5)
        is_casual = intent_result.get("is_casual", False)
        needs_rag = intent_result.get("needs_rag", False)
        
        # Enhanced URL detection with better patterns
        message_lower = message.lower()
        has_url = any([
            "http://" in message or "https://" in message,
            "www." in message and ("." in message.split("www.")[1][:50] if "www." in message else False),
            "youtube.com" in message_lower or "youtu.be" in message_lower,
            re.search(r'\b[a-zA-Z0-9-]+\.[a-zA-Z]{2,}\b', message) is not None  # Domain pattern
        ])
        
        # Check for image generation requests (always need tools)
        image_generation_keywords = [
            "generate an image", "generate image", "generate a image",
            "create an image", "create image", "create a image",
            "make an image", "make image", "make a image",
            "draw an image", "draw image", "draw a image",
            "generate a picture", "generate picture", "generate an picture",
            "create a picture", "create picture", "create an picture",
            "make a picture", "make picture", "make an picture",
            "draw a picture", "draw picture", "draw an picture",
            "generate artwork", "create artwork", "make artwork",
            "generate art", "create art", "make art"
        ]
        has_image_generation = any(keyword in message_lower for keyword in image_generation_keywords)
        
        # Check for greetings explicitly (greetings should ALWAYS go to chat, not RAG)
        greeting_keywords = ["hi", "hello", "hey", "greetings", "hiya", "howdy", "sup", "yo", "wassup", "what's up", "whats up", "how are you", "how are u", "how r u", "how's it going", "hows it going"]
        is_greeting = any(greeting in message_lower for greeting in greeting_keywords)
        bot_name_patterns = ["gophie", "gopher", "bot", "gopherbot"]
        has_bot_name = any(name in message_lower for name in bot_name_patterns)
        is_greeting_with_bot = has_bot_name and is_greeting
        
        # Enhanced context analysis
        has_recent_context = context and context.get("recent_messages") and len(context.get("recent_messages", [])) > 0
        is_follow_up = has_recent_context and any(
            "?" in msg.get("content", "") for msg in context.get("recent_messages", [])[:2]
        )
        
        # Determine handler with smarter logic
        # PRIORITY: Chat/casual/greetings BEFORE RAG (greetings should never trigger RAG)
        handler = None
        if not should_respond:
            handler = "ignore"
            reasoning_parts.append("should_respond=false")
        elif intent == "upload" or has_attachments:
            handler = "upload"
            reasoning_parts.append("file attachment detected")
        elif intent == "action" or routing == "action":
            handler = "action"
            reasoning_parts.append("action intent detected")
        # CRITICAL: Image generation requests always need tools (override casual/chat routing)
        elif has_image_generation:
            handler = "tools"
            intent_result["needs_tools"] = True
            intent_result["needs_rag"] = False  # Image generation doesn't need RAG
            intent_result["is_casual"] = False  # Image generation is not casual
            reasoning_parts.append("image generation detected - requires tool execution")
            logger.info(f"🎨 Image generation detected in message - forcing tools handler")
        # CRITICAL: URLs always need tools (override casual/chat routing)
        elif has_url:
            handler = "tools"
            intent_result["needs_tools"] = True
            intent_result["needs_rag"] = False  # URL tools handle content fetching
            intent_result["is_casual"] = False  # URLs are not casual
            reasoning_parts.append("URL detected - requires tool execution")
            logger.info(f"🌐 URL detected in message - forcing tools handler")
        # CRITICAL: Greetings ALWAYS go to chat (never RAG) - check this BEFORE RAG check
        elif is_greeting or is_greeting_with_bot or is_casual or routing == "chat" or intent == "casual":
            handler = "chat"
            intent_result["needs_rag"] = False  # Force needs_rag to False for greetings/casual
            intent_result["is_casual"] = True  # Ensure is_casual is True
            reasoning_parts.append("greeting/casual conversation - using chat handler")
            logger.info(f"💬 Greeting/casual message detected - routing to chat (not RAG)")
        # Enhanced: Check for tool-related keywords
        elif routing == "tools" or intent_result.get("needs_tools", False):
            handler = "tools"
            reasoning_parts.append("tool usage required")
        # Enhanced: Memory queries - check for user fact patterns
        elif routing == "memory" or intent_result.get("needs_memory", False):
            handler = "memory"
            reasoning_parts.append("memory retrieval needed")
        # Enhanced: Follow-up questions might need RAG if previous was RAG
        elif is_follow_up and has_recent_context:
            # Check if recent messages suggest RAG context
            recent_content = " ".join([msg.get("content", "") for msg in context.get("recent_messages", [])[:2]])
            if any(keyword in recent_content.lower() for keyword in ["document", "file", "pdf", "article", "paper"]):
                handler = "rag"
                reasoning_parts.append("follow-up to document query")
            else:
                handler = "chat"
                reasoning_parts.append("follow-up conversation")
        # RAG only if explicitly needed (needs_rag=True or routing="rag")
        # AND not a greeting/casual message (double-check)
        elif (routing == "rag" or needs_rag) and not is_greeting and not is_casual:
            handler = "rag"
            reasoning_parts.append("document query detected")
        else:
            # Default to chat (not RAG) - greetings and casual messages should go through LLM
            handler = "chat"
            intent_result["needs_rag"] = False
            reasoning_parts.append("default to chat handler")
            logger.info(f"💬 Default routing to chat (not RAG)")
        
        # Adjust confidence based on context
        if has_url and handler == "tools":
            confidence = max(confidence, 0.95)  # High confidence for URL routing
        elif has_attachments and handler == "upload":
            confidence = max(confidence, 0.95)  # High confidence for upload routing
        
        latency_ms = (time.time() - start_time) * 1000
        
        result = {
            "handler": handler,
            "intent": intent_result,
            "routing_confidence": confidence,
            "latency_ms": latency_ms,
            "reasoning": "; ".join(reasoning_parts) if reasoning_parts else "default routing"
        }
        
        return result
    
    def batch_classify(self, messages: List[Tuple[str, Optional[Dict[str, Any]]]]) -> List[Dict[str, Any]]:
        """
        Classify multiple messages in batch (GPU-optimized).
        
        Args:
            messages: List of (message, context) tuples
            
        Returns:
            List of intent classification results
        """
        if not messages:
            return []
        
        # Check cache for each message
        results = []
        uncached_messages = []
        uncached_indices = []
        
        for idx, (message, context) in enumerate(messages):
            if CACHE_ENABLED:
                cache_key = self._get_cache_key(message, context)
                if cache_key in self.intent_cache:
                    cached_result = self.intent_cache[cache_key].copy()
                    cached_result["cached"] = True
                    results.append((idx, cached_result))
                    self.metrics["cache_hits"] += 1
                    continue
            
            uncached_messages.append((message, context))
            uncached_indices.append(idx)
            self.metrics["cache_misses"] += 1
        
        # Classify uncached messages
        if uncached_messages:
            # Use GPU-accelerated batch processing if available
            if self.use_gpu and len(uncached_messages) > 1:
                # Batch LLM calls (if LMStudio supports batching)
                batch_results = self._batch_llm_classify(uncached_messages)
            else:
                # Sequential processing
                batch_results = [self.classify_intent(msg, ctx, use_cache=False) 
                                for msg, ctx in uncached_messages]
            
            # Add results
            for idx, result in zip(uncached_indices, batch_results):
                results.append((idx, result))
        
        # Sort by original index and return
        results.sort(key=lambda x: x[0])
        return [result for _, result in results]
    
    def _batch_llm_classify(self, messages: List[Tuple[str, Optional[Dict[str, Any]]]]) -> List[Dict[str, Any]]:
        """
        Batch LLM classification (optimized for GPU).
        Uses parallel processing when possible.
        """
        if len(messages) == 1:
            # Single message - no need for batching
            return [self.classify_intent(messages[0][0], messages[0][1], use_cache=False)]
        
        # For multiple messages, process in parallel (up to 4 at a time)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = [None] * len(messages)
        
        with ThreadPoolExecutor(max_workers=min(4, len(messages))) as executor:
            futures = {
                executor.submit(self.classify_intent, msg, ctx, use_cache=False): idx
                for idx, (msg, ctx) in enumerate(messages)
            }
            
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error(f"Error in batch classification for message {idx}: {e}")
                    # Fallback to pattern-based classification
                    msg, ctx = messages[idx]
                    results[idx] = self._fallback_classify(msg, ctx, time.time())
        
        return results
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response (handles markdown code blocks)."""
        # Handle None or empty responses
        if not response:
            logger.warning(f"Empty response received, using default classification")
            return self._get_default_classification()
        
        # Try to extract JSON from response
        import re
        
        # Remove markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object directly
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from response: {response[:200] if response else 'None'}")
            # Return default classification
            return self._get_default_classification()
    
    def _get_default_classification(self) -> Dict[str, Any]:
        """Get default classification when parsing fails."""
        # Default to chat (not RAG) - let the LLM handle it
        return {
            "intent": "question",
            "should_respond": True,
            "confidence": 0.5,
            "routing": "chat",
            "needs_rag": False,
            "needs_tools": False,
            "needs_memory": False,
            "is_casual": False,
            "document_references": []
        }
    
    def _fallback_classify(self, message: str, context: Optional[Dict[str, Any]], start_time: float) -> Dict[str, Any]:
        """Fallback pattern-based classification when LLM fails."""
        message_lower = message.lower().strip()
        
        # Pattern matching
        has_question_mark = "?" in message
        is_greeting = any(word in message_lower for word in ["hi", "hello", "hey", "greetings", "hiya", "howdy", "sup", "yo"])
        
        # Check for bot name in greeting (e.g., "hey gophie", "hi gopher")
        bot_name_patterns = ["gophie", "gopher", "bot", "gopherbot"]
        has_bot_name = any(name in message_lower for name in bot_name_patterns)
        is_greeting_with_bot = has_bot_name and is_greeting
        
        # Check for casual greeting questions (e.g., "how are you", "what's up")
        casual_questions = ["how are you", "how are u", "how r u", "what's up", "whats up", "wassup", "how's it going", "hows it going"]
        is_casual_question = any(q in message_lower for q in casual_questions)
        
        is_command = message_lower.startswith("/") or any(word in message_lower for word in ["do this", "please", "can you"])
        has_action_words = any(word in message_lower for word in ["give", "transfer", "set", "take"])
        
        intent = "question"
        should_respond = True
        routing = "rag"
        
        # Normalize attachment detection (handle both camelCase and snake_case)
        has_attachments = context and (context.get("hasAttachments") or context.get("has_attachments") or False)
        
        if has_attachments:
            intent = "upload"
            routing = "upload"
        elif is_greeting_with_bot or (is_greeting and is_casual_question):
            # Greetings with bot name or casual greeting questions should go to chat
            intent = "casual"
            routing = "chat"
            should_respond = True  # Should respond to greetings
        elif is_greeting and not has_question_mark:
            intent = "casual"
            routing = "chat"
            should_respond = True  # Should respond to greetings
        elif is_command:
            intent = "command"
            routing = "tools"
        elif has_action_words:
            intent = "action"
            routing = "action"
        elif not has_question_mark and len(message) < 20:
            intent = "casual"
            routing = "chat"
            should_respond = True  # Should respond to casual messages
        
        latency_ms = (time.time() - start_time) * 1000
        
        return {
            "intent": intent,
            "should_respond": should_respond,
            "confidence": 0.6,  # Lower confidence for fallback
            "routing": routing,
            "needs_rag": routing == "rag",
            "needs_tools": routing == "tools",
            "needs_memory": False,
            "is_casual": intent == "casual",
            "document_references": [],
            "latency_ms": latency_ms,
            "cached": False,
            "fallback": True
        }

    def run_agentic_task(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run a complex task using the ReAct agent (Tools, Reasoning, etc.).
        Implements Thought -> Action -> Observation loop.
        
        Args:
            message: The user message/task.
            context: Context dictionary.
            
        Returns:
            Dict with 'result', 'status', 'error', 'steps', 'tool_calls'.
        """
        if not self.react_agent:
            return {
                "status": "error",
                "error": "ReAct Agent not initialized",
                "result": None
            }
            
        try:
            logger.info(f"🤖 Running Agentic Task (ReAct): {message[:50]}...")
            start_time = time.time()
            
            # Run the ReAct agent
            response = self.react_agent.run(message, context)
            
            duration = time.time() - start_time
            logger.info(f"✅ Agentic Task Complete ({duration:.2f}s)")
            
            # Extract tool calls and steps from the agent if available
            tool_calls = []
            steps = []
            if hasattr(self.react_agent, 'last_execution'):
                execution = self.react_agent.last_execution
                tool_calls = execution.get('tool_calls', [])
                steps = execution.get('steps', [])
            
            return {
                "status": "success",
                "result": response,
                "duration_ms": duration * 1000,
                "tool_calls": tool_calls,
                "steps": steps
            }
        except Exception as e:
            logger.error(f"❌ Agentic Task Failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "result": None
            }
    
    def should_use_agentic_mode(self, message: str, intent_result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Determine if a message should use agentic (ReAct) mode.
        
        Agentic mode is used for:
        - Complex multi-step tasks
        - Tasks requiring tool chaining
        - Math/logic problems
        - Tasks requiring planning
        
        Args:
            message: User message
            intent_result: Optional pre-computed intent
            
        Returns:
            True if agentic mode should be used
        """
        if not self.react_agent:
            return False
        
        # Check for complex task indicators
        message_lower = message.lower()
        
        # Math/logic problems
        math_indicators = ["calculate", "solve", "compute", "what is", "how many", "how much"]
        if any(indicator in message_lower for indicator in math_indicators):
            # Check if it's a simple question (not complex)
            if "?" in message and len(message.split()) < 10:
                return False  # Simple question, use regular mode
            return True
        
        # Multi-step tasks
        multi_step_indicators = ["then", "after that", "next", "first", "second", "finally"]
        if any(indicator in message_lower for indicator in multi_step_indicators):
            return True
        
        # Planning tasks
        planning_indicators = ["plan", "strategy", "approach", "how to", "steps"]
        if any(indicator in message_lower for indicator in planning_indicators):
            return True
        
        # Code execution requests
        code_indicators = ["code", "python", "script", "program", "function"]
        if any(indicator in message_lower for indicator in code_indicators):
            return True
        
        # Check intent result
        if intent_result:
            needs_tools = intent_result.get("needs_tools", False)
            if needs_tools and len(message.split()) > 15:  # Complex tool-using task
                return True
        
        return False
    
    def _quick_pattern_check_unambiguous(self, message: str, context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Quick pattern check ONLY for truly unambiguous cases (URLs, attachments, image generation).
        Everything else (greetings, questions, casual) goes to LLM for natural language understanding.
        Returns result if unambiguous pattern found, None otherwise.
        """
        message_lower = message.lower().strip()
        
        # Check for URLs (unambiguous - always need tools)
        if any(x in message for x in ["http://", "https://", "www.", "youtube.com", "youtu.be"]):
            return {
                "intent": "question",
                "should_respond": True,
                "confidence": 0.95,
                "routing": "tools",
                "needs_rag": False,
                "needs_tools": True,
                "needs_memory": False,
                "is_casual": False,
                "document_references": []
            }
        
        # Check for image generation requests (unambiguous - always need tools)
        image_generation_keywords = [
            "generate an image", "generate image", "generate a image",
            "create an image", "create image", "create a image",
            "make an image", "make image", "make a image",
            "draw an image", "draw image", "draw a image",
            "generate a picture", "generate picture", "generate an picture",
            "create a picture", "create picture", "create an picture",
            "make a picture", "make picture", "make an picture",
            "draw a picture", "draw picture", "draw an picture",
            "generate artwork", "create artwork", "make artwork",
            "generate art", "create art", "make art"
        ]
        if any(keyword in message_lower for keyword in image_generation_keywords):
            return {
                "intent": "command",
                "should_respond": True,
                "confidence": 0.95,
                "routing": "tools",
                "needs_rag": False,
                "needs_tools": True,
                "needs_memory": False,
                "is_casual": False,
                "document_references": []
            }
        
        # Check for file uploads (unambiguous)
        has_attachments = context and (context.get("hasAttachments") or context.get("has_attachments") or False)
        if has_attachments:
            return {
                "intent": "upload",
                "should_respond": True,
                "confidence": 0.95,
                "routing": "upload",
                "needs_rag": False,
                "needs_tools": False,
                "needs_memory": False,
                "is_casual": False,
                "document_references": []
            }
        
        # Everything else (greetings, questions, casual conversation) goes to LLM
        # This allows natural language understanding without fixed patterns
        return None
    
    def _quick_pattern_check(self, message: str, context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Legacy method - kept for compatibility. Now delegates to unambiguous check.
        """
        return self._quick_pattern_check_unambiguous(message, context)
    
    def _get_cache_key(self, message: str, context: Optional[Dict[str, Any]]) -> str:
        """
        Generate cache key for message with improved context awareness.
        Includes more context for better cache hit rates.
        """
        # Normalize message (lowercase, strip, limit length)
        message_normalized = message.lower().strip()[:200]  # Limit length for cache key
        
        # Create hash of message + relevant context
        key_data = {
            "message": message_normalized,
            "has_attachments": (context.get("hasAttachments") or context.get("has_attachments") or False) if context else False,
            "is_mentioned": (context.get("isMentioned") or context.get("is_mentioned") or False) if context else False,
            # Include user_id if available (for user-specific caching)
            "user_id": context.get("userId", "") if context else "",
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        cache_hit_rate = 0.0
        total_requests = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        if total_requests > 0:
            cache_hit_rate = self.metrics["cache_hits"] / total_requests
        
        return {
            **self.metrics,
            "cache_hit_rate": cache_hit_rate,
            "gpu_enabled": self.use_gpu,
            "cache_size": len(self.intent_cache)
        }
    
    def clear_cache(self):
        """Clear all caches."""
        self.intent_cache.clear()
        self.routing_cache.clear()
        logger.info("GopherAgent caches cleared")


# Singleton instance (lazy-loaded)
_gopher_agent_instance: Optional[GopherAgent] = None


def get_gopher_agent(llm_client = None, embedding_generator: Optional[EmbeddingGenerator] = None) -> GopherAgent:
    """Get or create GopherAgent singleton instance."""
    global _gopher_agent_instance
    if _gopher_agent_instance is None:
        _gopher_agent_instance = GopherAgent(llm_client=llm_client, embedding_generator=embedding_generator)
    return _gopher_agent_instance

