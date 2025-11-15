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

from src.clients.lmstudio_client import LMStudioClient
from src.processors.embedding_generator import EmbeddingGenerator
from config import (
    LMSTUDIO_BASE_URL, LMSTUDIO_MODEL, USE_GPU, EMBEDDING_BATCH_SIZE,
    CACHE_ENABLED, CACHE_MAX_SIZE, CACHE_TTL_SECONDS, LMSTUDIO_TIMEOUT
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
                 llm_client: Optional[LMStudioClient] = None,
                 embedding_generator: Optional[EmbeddingGenerator] = None,
                 cache_ttl: int = 300):  # 5 minute cache
        """
        Initialize GopherAgent.
        
        Args:
            llm_client: LMStudio client (auto-created if None)
            embedding_generator: Embedding generator (auto-created if None)
            cache_ttl: Cache TTL in seconds (default: 5 minutes)
        """
        # Initialize LLM client
        if llm_client is None:
            self.llm_client = LMStudioClient()
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
        
        # Quick pattern-based check for common cases (faster than LLM)
        quick_result = self._quick_pattern_check(message, context)
        if quick_result:
            quick_result["latency_ms"] = (time.time() - start_time) * 1000
            quick_result["cached"] = False
            quick_result["pattern_match"] = True
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
        
        # Build context string
        context_str = ""
        if context:
            if context.get("recent_messages"):
                recent = context["recent_messages"][:3]  # Last 3 messages
                context_str += f"\nRecent messages: {json.dumps(recent, ensure_ascii=False)}"
            if context.get("has_attachments"):
                context_str += "\nMessage has file attachments."
            if context.get("is_mentioned"):
                context_str += "\nBot was mentioned in message."
        
        # OPTIMIZED: Fast LLM classification prompt (shorter for speed)
        # Truncate message if too long to reduce token usage
        message_truncated = message[:300] if len(message) > 300 else message  # Reduced from 500
        
        # Shorter context
        short_context_str = ""
        if context:
            if context.get("has_attachments"):
                short_context_str += "\nHas attachments."
            if context.get("is_mentioned"):
                short_context_str += "\nMentioned."
        
        # More concise prompt
        prompt = f"""Classify intent. JSON only.

"{message_truncated}"{short_context_str}

{{"intent":"question|command|casual|action|upload|ignore","should_respond":true|false,"confidence":0.0-1.0,"routing":"rag|chat|tools|memory|action","needs_rag":true|false,"needs_tools":true|false,"needs_memory":true|false,"is_casual":true|false}}"""
        
        # Create future for deduplication if cache enabled
        from concurrent.futures import Future
        future = None
        if use_cache and CACHE_ENABLED and cache_key:
            future = Future()
            self.pending_requests[cache_key] = future
        
        try:
            # OPTIMIZED: Fast LLM call (low temperature for consistency, reduced tokens for speed)
            # Use shorter timeout for faster responses
            try:
                response = self.llm_client.generate_response(
                    messages=[
                        {"role": "system", "content": "Fast intent classifier. JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,  # Low temperature for consistent classification
                    max_tokens=120  # OPTIMIZED: Reduced from 150 for faster generation
                )
            except Exception as e:
                logger.warning(f"LLM call failed in GopherAgent: {e}, using fallback")
                if future:
                    future.set_exception(e)
                    self.pending_requests.pop(cache_key, None)
                raise
            
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
            if future:
                future.set_result(result)
                self.pending_requests.pop(cache_key, None)
            
            return result
            
        except Exception as e:
            # Complete future with exception
            if future:
                future.set_exception(e)
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
        
        # Get intent if not provided
        if intent_result is None:
            intent_result = self.classify_intent(message, context)
        
        # Route based on intent with enhanced context awareness
        intent = intent_result.get("intent", "ignore")
        routing = intent_result.get("routing", "chat")
        should_respond = intent_result.get("should_respond", False)
        confidence = intent_result.get("confidence", 0.5)
        
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
        
        # Enhanced context analysis
        has_recent_context = context and context.get("recent_messages") and len(context.get("recent_messages", [])) > 0
        is_follow_up = has_recent_context and any(
            "?" in msg.get("content", "") for msg in context.get("recent_messages", [])[:2]
        )
        
        # Determine handler with smarter logic
        handler = None
        if not should_respond:
            handler = "ignore"
            reasoning_parts.append("should_respond=false")
        elif intent == "upload" or (context and context.get("hasAttachments")):
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
        # Enhanced: Check for document references in context
        elif routing == "rag" or intent_result.get("needs_rag", False):
            handler = "rag"
            reasoning_parts.append("document query detected")
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
        elif routing == "chat" or intent == "casual":
            handler = "chat"
            reasoning_parts.append("casual conversation")
        else:
            handler = "rag"  # Default to RAG for better information retrieval
            reasoning_parts.append("default to RAG for information retrieval")
        
        # Adjust confidence based on context
        if has_url and handler == "tools":
            confidence = max(confidence, 0.95)  # High confidence for URL routing
        elif context and context.get("hasAttachments") and handler == "upload":
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
            logger.warning(f"Failed to parse JSON from response: {response[:200]}")
            # Return default classification
            return {
                "intent": "question",
                "should_respond": True,
                "confidence": 0.5,
                "routing": "rag",
                "needs_rag": True,
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
        is_greeting = any(word in message_lower for word in ["hi", "hello", "hey", "greetings"])
        is_command = message_lower.startswith("/") or any(word in message_lower for word in ["do this", "please", "can you"])
        has_action_words = any(word in message_lower for word in ["give", "transfer", "set", "take"])
        
        intent = "question"
        should_respond = True
        routing = "rag"
        
        if context and context.get("has_attachments"):
            intent = "upload"
            routing = "upload"
        elif is_greeting and not has_question_mark:
            intent = "casual"
            routing = "chat"
            should_respond = False
        elif is_command:
            intent = "command"
            routing = "tools"
        elif has_action_words:
            intent = "action"
            routing = "action"
        elif not has_question_mark and len(message) < 20:
            intent = "casual"
            routing = "chat"
            should_respond = False
        
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
    
    def _quick_pattern_check(self, message: str, context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Quick pattern-based check for common intents (faster than LLM).
        Returns result if pattern match found, None otherwise.
        """
        message_lower = message.lower().strip()
        
        # Check for URLs (always need tools)
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
        
        # Check for file uploads
        if context and context.get("has_attachments"):
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
        
        # Check for simple greetings (don't need LLM)
        greetings = ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening"]
        if message_lower in greetings or any(message_lower.startswith(g + " ") for g in greetings):
            return {
                "intent": "casual",
                "should_respond": True,
                "confidence": 0.9,
                "routing": "chat",
                "needs_rag": False,
                "needs_tools": False,
                "needs_memory": False,
                "is_casual": True,
                "document_references": []
            }
        
        return None
    
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
            "has_attachments": context.get("has_attachments", False) if context else False,
            "is_mentioned": context.get("is_mentioned", False) if context else False,
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


def get_gopher_agent(llm_client: Optional[LMStudioClient] = None, embedding_generator: Optional[EmbeddingGenerator] = None) -> GopherAgent:
    """Get or create GopherAgent singleton instance."""
    global _gopher_agent_instance
    if _gopher_agent_instance is None:
        _gopher_agent_instance = GopherAgent(llm_client=llm_client, embedding_generator=embedding_generator)
    return _gopher_agent_instance

