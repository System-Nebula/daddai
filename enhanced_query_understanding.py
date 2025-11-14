"""
Enhanced query understanding using LLM-based intent analysis.
Falls back to pattern-based analysis if LLM is unavailable.
"""
from typing import Dict, List, Any, Optional
import json
import re
from query_analyzer import QueryAnalyzer
from lmstudio_client import LMStudioClient
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
        if self.use_llm and use_llm:
            # Skip LLM for very short queries (likely simple)
            if len(query.split()) < 4:
                enhanced = base_analysis
            else:
                try:
                    llm_analysis = self._llm_analyze(query, context)
                    # Merge LLM insights with pattern-based analysis
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
        prompt = f"""Analyze the following query and provide structured analysis:

Query: "{query}"

Provide a JSON response with:
1. "intent": Primary intent (factual, analytical, comparative, procedural, conversational, action, state_query)
2. "entities": List of entities mentioned (people, places, concepts, items, etc.)
3. "relationships": Relationships between entities (if any)
4. "key_concepts": Main concepts/topics
5. "query_type": Specific type (question, command, statement, etc.)
6. "needs_context": Whether this query needs conversation context (true/false)
7. "suggested_rewrite": Improved version of the query for better retrieval
8. "complexity": Simple, moderate, or complex
9. "answer_format": Expected answer format (list, paragraph, number, etc.)
10. "service_routing": Which service to use - one of: "rag" (needs document search), "chat" (general conversation), "tools" (needs tool calls), "memory" (needs past conversations), "state" (user state query), "action" (state modification)
11. "needs_rag": Whether RAG/document search is needed (true/false)
12. "needs_tools": Whether tool calls are likely needed (true/false)
13. "needs_memory": Whether past conversations are needed (true/false)
14. "needs_relations": Whether user relations are relevant (true/false)

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
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                llm_result = json.loads(json_match.group())
                return llm_result
            else:
                logger.warning("Could not extract JSON from LLM response")
                return {}
        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
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

