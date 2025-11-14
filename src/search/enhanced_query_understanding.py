"""
Enhanced query understanding using LLM-based intent analysis.
Falls back to pattern-based analysis if LLM is unavailable.
"""
from typing import Dict, List, Any, Optional
import json
import re
from src.search.query_analyzer import QueryAnalyzer
from src.clients.lmstudio_client import LMStudioClient
from logger_config import logger


class EnhancedQueryUnderstanding:
    """
    Advanced query understanding that combines:
    - LLM-based intent analysis (when available)
    - Pattern-based fallback
    - Entity extraction and relationship detection
    - Query rewriting for better retrieval
    """
    
    def __init__(self):
        """Initialize enhanced query understanding."""
        self.query_analyzer = QueryAnalyzer()
        self.lmstudio_client = LMStudioClient()
        self.use_llm = self._check_llm_availability()
    
    def _check_llm_availability(self) -> bool:
        """Check if LLM is available for advanced analysis."""
        try:
            return self.lmstudio_client.check_connection()
        except:
            return False
    
    def analyze_query(self, query: str, context: Dict[str, Any] = None, use_llm: bool = True) -> Dict[str, Any]:
        """
        Analyze query with enhanced understanding.
        Optimized: Can skip LLM for simple queries.
        
        Args:
            query: User query
            context: Optional context (channel_id, user_id, etc.)
            use_llm: Whether to use LLM analysis (default: True, but can be disabled for speed)
            
        Returns:
            Enhanced analysis dictionary
        """
        # Start with pattern-based analysis (fast)
        base_analysis = self.query_analyzer.analyze(query)
        
        # Enhance with LLM if available and requested
        # IMPORTANT: Always use LLM for analysis - it's better at understanding intent than patterns
        if self.use_llm and use_llm:
            try:
                llm_analysis = self._llm_analyze(query, context)
                # Merge LLM insights with pattern-based analysis (LLM takes precedence for is_casual)
                enhanced = self._merge_analyses(base_analysis, llm_analysis)
            except Exception as e:
                logger.warning(f"LLM analysis failed, using pattern-based: {e}")
                enhanced = base_analysis
        else:
            enhanced = base_analysis
        
        # Add context-aware enhancements (fast, no LLM)
        if context:
            enhanced = self._add_context_insights(enhanced, context)
        
        return enhanced
    
    def _llm_analyze(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Use LLM to analyze query intent, entities, and relationships.
        """
        # Build context information for document reference detection
        context_info = ""
        if context:
            if context.get("doc_id") or context.get("doc_filename"):
                context_info += f"\n\nCONTEXT: The user is asking about a specific document: {context.get('doc_filename') or context.get('doc_id')}"
            if context.get("channel_id"):
                context_info += f"\n\nCONTEXT: This is in channel {context.get('channel_id')} - previous messages may reference documents."
            # Add previous conversation context if available (for follow-up questions)
            if context.get("previous_question") or context.get("previous_answer"):
                prev_q = context.get("previous_question", "")
                prev_a = context.get("previous_answer", "")
                if prev_q or prev_a:
                    context_info += f"\n\nPREVIOUS CONVERSATION:\n"
                    if prev_q:
                        context_info += f"Previous Question: {prev_q}\n"
                    if prev_a:
                        context_info += f"Previous Answer: {prev_a}\n"
                    context_info += "\nIMPORTANT: If the current query references 'the document', 'that', 'it', etc., it likely refers to the document mentioned in the previous conversation. Set needs_rag=true, needs_memory=true, and include document references from the previous conversation."
        
        prompt = f"""Analyze the following query and provide structured analysis:

Query: "{query}"{context_info}

Provide a JSON response with:
1. "intent": Primary intent (factual, analytical, comparative, procedural, conversational, action, state_query)
2. "entities": List of entities mentioned (people, places, concepts, items, document names, etc.)
3. "relationships": Relationships between entities (if any)
4. "key_concepts": Main concepts/topics
5. "query_type": Specific type (question, command, statement, etc.)
6. "needs_context": Whether this query needs conversation context (true/false)
7. "suggested_rewrite": Improved version of the query for better retrieval
8. "complexity": Simple, moderate, or complex
9. "answer_format": Expected answer format (list, paragraph, number, etc.)
10. "service_routing": Which service to use - one of: "rag" (needs document search), "chat" (general conversation/casual), "tools" (needs tool calls), "memory" (needs past conversations), "state" (user state query), "action" (state modification)
11. "needs_rag": Whether RAG/document search is needed (true/false). Set to false for casual conversation, greetings, or simple statements.
12. "needs_tools": Whether tool calls are likely needed (true/false)
13. "needs_memory": Whether past conversations are needed (true/false) - set to true if query references previous conversation or documents mentioned earlier
14. "needs_relations": Whether user relations are relevant (true/false)
15. "is_casual": Whether this is casual conversation that doesn't need data retrieval (true/false). Examples: greetings, small talk, simple acknowledgments, invitations like "lets go", "help me", "want to go".
16. "document_references": List of document names or identifiers mentioned in the query (e.g., ["kohya", "kohya-ss-gui_logs1.txt"]). Include partial names like "kohya" if they likely refer to a document from context.

IMPORTANT ROUTING RULES:
- If query explicitly mentions "document", "doc", "file", or asks about documents, set needs_rag to true and is_casual to false
- If query is a follow-up that mentions "document" or "the document" (e.g., "yeah but the document", "what about the document"), set needs_rag to true, needs_memory to true, and is_casual to false - these are asking about documents, not casual conversation
- If query is casual conversation (greetings, "just felt like it", "yeah sure", "lets go", "help me", "pick out", "want to go" WITHOUT mentioning documents), set service_routing to "chat" and needs_rag to false and is_casual to true
- Phrases like "lets go to the store", "help me pick out", "want to go shopping" are CASUAL CONVERSATION, not action commands - set is_casual=true, service_routing="chat", needs_rag=false
- If query asks about user state (gold, inventory, etc.), set service_routing to "state" and needs_rag to false
- If query is an action command (give, transfer, etc.) AND clearly an action (not casual conversation), set service_routing to "action" and needs_rag to false
- If query mentions a document name (even partially like "kohya"), set needs_rag to true and include the document name in "document_references"
- If query is a follow-up question that might reference a document from previous conversation (e.g., "what model is kohya training?"), set needs_memory to true and needs_rag to true
- Only set needs_rag to true if the query explicitly needs information from documents or knowledge base
- If query is a simple statement or acknowledgment WITHOUT mentioning documents, set is_casual to true
- CRITICAL: "yeah but the document" or "what about the document" are NOT casual - they're asking about documents, so set needs_rag=true, is_casual=false

Respond ONLY with valid JSON, no other text."""

        messages = [
            {"role": "system", "content": "You are a query analysis expert. Provide precise, structured analysis in JSON format."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.lmstudio_client.generate_response(
                messages=messages,
                temperature=0.3,
                max_tokens=300
            )
            
            # Try multiple methods to extract JSON
            llm_result = {}
            
            # Method 1: Try to find JSON object with balanced braces
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if json_match:
                try:
                    llm_result = json.loads(json_match.group())
                    return llm_result
                except json.JSONDecodeError:
                    pass
            
            # Method 2: Try to find JSON between ```json and ``` markers
            json_block_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_block_match:
                try:
                    llm_result = json.loads(json_block_match.group(1))
                    return llm_result
                except json.JSONDecodeError:
                    pass
            
            # Method 3: Try to find JSON between ``` and ``` markers
            code_block_match = re.search(r'```\s*(\{.*?\})\s*```', response, re.DOTALL)
            if code_block_match:
                try:
                    llm_result = json.loads(code_block_match.group(1))
                    return llm_result
                except json.JSONDecodeError:
                    pass
            
            # Method 4: Try to extract and fix common JSON issues
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                # Try to fix common issues: trailing commas, unquoted keys
                json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas before }
                json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas before ]
                try:
                    llm_result = json.loads(json_str)
                    return llm_result
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not parse JSON after fixes: {e}, response: {response[:200]}")
            
            logger.warning(f"Could not extract valid JSON from LLM response: {response[:200]}")
            return {}
        except Exception as e:
            logger.error(f"LLM analysis error: {e}", exc_info=True)
            return {}
    
    def _merge_analyses(self,
                       pattern_analysis: Dict[str, Any],
                       llm_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Merge pattern-based and LLM analyses."""
        merged = pattern_analysis.copy()
        
        # Use LLM intent if available and more specific
        if llm_analysis.get("intent"):
            merged["question_type"] = llm_analysis["intent"]
        
        # Merge entities (LLM often finds more)
        if llm_analysis.get("entities"):
            if "entities" not in merged:
                merged["entities"] = {}
            # Add LLM entities
            for entity in llm_analysis["entities"]:
                entity_type = "general"  # LLM doesn't always provide types
                if entity_type not in merged["entities"]:
                    merged["entities"][entity_type] = []
                if entity not in merged["entities"][entity_type]:
                    merged["entities"][entity_type].append(entity)
        
        # Add LLM-specific insights
        if llm_analysis.get("key_concepts"):
            merged["key_concepts"] = llm_analysis["key_concepts"]
        
        if llm_analysis.get("relationships"):
            merged["relationships"] = llm_analysis["relationships"]
        
        if llm_analysis.get("suggested_rewrite"):
            merged["suggested_rewrite"] = llm_analysis["suggested_rewrite"]
        
        if llm_analysis.get("complexity"):
            merged["complexity"] = llm_analysis["complexity"]
        
        if llm_analysis.get("needs_context"):
            merged["needs_context"] = llm_analysis["needs_context"]
        
        # Merge LLM-specific flags (preserve pattern-based is_casual if LLM doesn't override)
        if llm_analysis.get("is_casual") is not None:
            merged["is_casual"] = llm_analysis["is_casual"]
        elif pattern_analysis.get("is_casual"):
            merged["is_casual"] = True
        
        if llm_analysis.get("service_routing"):
            merged["service_routing"] = llm_analysis["service_routing"]
        elif pattern_analysis.get("is_casual"):
            merged["service_routing"] = "chat"
        
        if llm_analysis.get("needs_rag") is not None:
            merged["needs_rag"] = llm_analysis["needs_rag"]
        elif pattern_analysis.get("is_casual"):
            merged["needs_rag"] = False
        
        # Extract document references from LLM analysis
        if llm_analysis.get("document_references"):
            merged["document_references"] = llm_analysis["document_references"]
        
        return merged
    
    def _add_context_insights(self,
                              analysis: Dict[str, Any],
                              context: Dict[str, Any]) -> Dict[str, Any]:
        """Add context-aware insights to analysis."""
        enhanced = analysis.copy()
        
        # Detect if query is about a specific user
        if context.get("user_id") and context.get("mentioned_user_id"):
            enhanced["is_user_query"] = True
            enhanced["target_user_id"] = context["mentioned_user_id"]
        
        # Detect if query is about a specific document
        if context.get("doc_id") or context.get("doc_filename"):
            enhanced["is_document_query"] = True
            enhanced["target_doc_id"] = context.get("doc_id")
            enhanced["target_doc_filename"] = context.get("doc_filename")
        
        # Add channel context
        if context.get("channel_id"):
            enhanced["channel_context"] = context["channel_id"]
        
        return enhanced
    
    def rewrite_query(self,
                     query: str,
                     analysis: Dict[str, Any] = None,
                     use_llm_rewrite: bool = True) -> str:
        """
        Rewrite query for better retrieval.
        Uses LLM-based rewriting for state-of-the-art query improvement.
        
        Args:
            query: Original query
            analysis: Optional pre-computed analysis
            use_llm_rewrite: Whether to use LLM for rewriting (default: True)
        """
        if analysis is None:
            analysis = self.analyze_query(query)
        
        # Use LLM-suggested rewrite if available
        if analysis.get("suggested_rewrite"):
            return analysis["suggested_rewrite"]
        
        # Enhanced LLM-based rewriting
        if use_llm_rewrite and self.use_llm:
            try:
                rewrite_prompt = f"""Rewrite the following query to improve retrieval accuracy.
The rewritten query should:
- Be more specific and clear
- Include key concepts and entities
- Use synonyms and related terms
- Maintain the original intent

Original query: "{query}"

Provide ONLY the rewritten query, no explanation."""
                
                response = self.lmstudio_client.generate_response(
                    messages=[{"role": "user", "content": rewrite_prompt}],
                    temperature=0.3,
                    max_tokens=150
                )
                
                rewritten = response.strip().strip('"').strip("'")
                if rewritten and len(rewritten) > 10:
                    logger.debug(f"LLM rewrote query: {query} -> {rewritten}")
                    return rewritten
            except Exception as e:
                logger.warning(f"LLM query rewriting failed: {e}")
        
        # Rule-based rewriting (fallback)
        rewritten = query
        
        # Expand abbreviations
        abbreviations = {
            "doc": "document",
            "info": "information",
            "req": "requirement",
            "spec": "specification"
        }
        
        for abbrev, full in abbreviations.items():
            rewritten = re.sub(rf'\b{abbrev}\b', full, rewritten, flags=re.IGNORECASE)
        
        # Add context from entities
        if analysis.get("entities"):
            entity_texts = []
            for entity_list in analysis["entities"].values():
                entity_texts.extend(entity_list)
            
            if entity_texts:
                # Add entities to query for better matching
                rewritten = f"{rewritten} {' '.join(entity_texts[:3])}"
        
        return rewritten.strip()
    
    def extract_user_mentions(self, query: str) -> List[str]:
        """Extract user mentions from query (Discord format: <@123456>)."""
        mentions = re.findall(r'<@!?(\d+)>', query)
        return mentions
    
    def extract_document_references(self, query: str) -> Dict[str, str]:
        """
        Extract document references from query.
        Looks for patterns like "in document X", "from file Y", etc.
        
        Returns:
            Dict with 'doc_id' and/or 'doc_filename'
        """
        references = {}
        
        # Pattern: "in document X", "from file Y", "document named X"
        doc_patterns = [
            r'(?:in|from|document|file|doc)\s+(?:named|called|titled)?\s+["\']?([^"\']+)["\']?',
            r'document\s+["\']([^"\']+)["\']',
            r'file\s+["\']([^"\']+)["\']'
        ]
        
        for pattern in doc_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            if matches:
                references["doc_filename"] = matches[0].strip()
                break
        
        return references
    
    def determine_retrieval_strategy(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine optimal retrieval strategy based on query analysis.
        
        Returns:
            Strategy configuration dict
        """
        question_type = analysis.get("question_type", "general")
        complexity = analysis.get("complexity", "moderate")
        is_complex = analysis.get("is_complex", False)
        
        strategy = {
            "use_hybrid_search": True,
            "use_query_expansion": complexity in ["moderate", "complex"] or is_complex,
            "use_mmr": question_type in ["comparative", "analytical"],
            "use_temporal_weighting": True,
            "top_k": self._determine_top_k(question_type, complexity),
            "temperature": self._determine_temperature(question_type),
            "focus": self._determine_focus(question_type)
        }
        
        return strategy
    
    def _determine_top_k(self, question_type: str, complexity: str) -> int:
        """Determine optimal top_k based on query characteristics."""
        base_k = 10
        
        if question_type == "comparative":
            return base_k * 2
        elif question_type == "analytical":
            return int(base_k * 1.5)
        elif complexity == "complex":
            return int(base_k * 1.5)
        else:
            return base_k
    
    def _determine_temperature(self, question_type: str) -> float:
        """Determine optimal temperature."""
        temps = {
            "factual": 0.3,
            "analytical": 0.8,
            "comparative": 0.7,
            "procedural": 0.5,
            "conversational": 0.9
        }
        return temps.get(question_type, 0.7)
    
    def _determine_focus(self, question_type: str) -> str:
        """Determine retrieval focus."""
        focus_map = {
            "factual": "precision",
            "analytical": "diversity",
            "comparative": "diversity",
            "procedural": "precision",
            "conversational": "relevance"
        }
        return focus_map.get(question_type, "balanced")

