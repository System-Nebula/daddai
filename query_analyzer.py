"""
Smart query analyzer for understanding user intent and improving retrieval.
"""
from typing import Dict, List, Any, Optional
import re
from logger_config import logger


class QueryAnalyzer:
    """Analyze queries to understand intent and improve retrieval."""
    
    # Question type patterns
    QUESTION_PATTERNS = {
        'factual': [
            r'what (is|are|was|were)',
            r'who (is|are|was|were)',
            r'when (did|does|was|is)',
            r'where (is|are|was|were|did|does)',
            r'which',
            r'how many',
            r'how much'
        ],
        'analytical': [
            r'why',
            r'how (does|did|can|will)',
            r'explain',
            r'analyze',
            r'compare',
            r'difference',
            r'similarity'
        ],
        'procedural': [
            r'how to',
            r'steps? to',
            r'process',
            r'procedure',
            r'method'
        ],
        'comparative': [
            r'compare',
            r'difference',
            r'similar',
            r'better',
            r'best',
            r'versus',
            r'vs'
        ],
        'temporal': [
            r'when',
            r'timeline',
            r'history',
            r'before',
            r'after',
            r'chronology'
        ],
        'quantitative': [
            r'how many',
            r'how much',
            r'number',
            r'count',
            r'percentage',
            r'statistics',
            r'data'
        ]
    }
    
    # Entity extraction patterns
    ENTITY_PATTERNS = {
        'person': r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b',  # Simple name pattern
        'organization': r'\b([A-Z][a-z]+ (?:Inc|Corp|LLC|Ltd|Company|Corporation))\b',
        'date': r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4})\b',
        'number': r'\b(\d+(?:\.\d+)?)\b',
        'acronym': r'\b([A-Z]{2,})\b'
    }
    
    def analyze(self, query: str) -> Dict[str, Any]:
        """
        Analyze a query to extract intent, entities, and characteristics.
        
        Args:
            query: User query string
            
        Returns:
            Dictionary with analysis results
        """
        query_lower = query.lower().strip()
        
        # Detect question type
        question_type = self._detect_question_type(query_lower)
        
        # Extract entities
        entities = self._extract_entities(query)
        
        # Detect query characteristics
        is_complex = len(query.split()) > 10
        has_negation = any(word in query_lower for word in ['not', 'no', 'never', 'none', "don't", "doesn't"])
        is_multi_part = '?' in query and query.count('?') > 1
        
        # Determine expected answer type
        answer_type = self._determine_answer_type(question_type, query_lower)
        
        # Determine retrieval strategy
        retrieval_strategy = self._determine_retrieval_strategy(question_type, is_complex)
        
        analysis = {
            'original_query': query,
            'question_type': question_type,
            'answer_type': answer_type,
            'entities': entities,
            'is_complex': is_complex,
            'has_negation': has_negation,
            'is_multi_part': is_multi_part,
            'retrieval_strategy': retrieval_strategy,
            'suggested_top_k': self._suggest_top_k(question_type, is_complex),
            'suggested_temperature': self._suggest_temperature(question_type)
        }
        
        logger.debug(f"Query analysis: {analysis}")
        return analysis
    
    def _detect_question_type(self, query_lower: str) -> str:
        """Detect the type of question."""
        scores = {}
        
        for qtype, patterns in self.QUESTION_PATTERNS.items():
            score = sum(1 for pattern in patterns if re.search(pattern, query_lower))
            if score > 0:
                scores[qtype] = score
        
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        
        return 'general'
    
    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract entities from query."""
        entities = {}
        
        for entity_type, pattern in self.ENTITY_PATTERNS.items():
            matches = re.findall(pattern, query)
            if matches:
                entities[entity_type] = list(set(matches))
        
        return entities
    
    def _determine_answer_type(self, question_type: str, query_lower: str) -> str:
        """Determine expected answer type."""
        if question_type == 'quantitative':
            return 'number'
        elif question_type == 'temporal':
            return 'date_or_time'
        elif question_type == 'comparative':
            return 'comparison'
        elif question_type == 'procedural':
            return 'steps'
        elif question_type == 'analytical':
            return 'explanation'
        elif 'list' in query_lower or 'all' in query_lower:
            return 'list'
        else:
            return 'factual'
    
    def _determine_retrieval_strategy(self, question_type: str, is_complex: bool) -> str:
        """Determine best retrieval strategy."""
        if is_complex:
            return 'hybrid_expanded'  # Use hybrid search with query expansion
        elif question_type == 'comparative':
            return 'diverse'  # Use MMR for diversity
        elif question_type == 'factual':
            return 'precise'  # Focus on precision
        else:
            return 'balanced'
    
    def _suggest_top_k(self, question_type: str, is_complex: bool) -> int:
        """Suggest optimal top_k based on query characteristics."""
        base_k = 10
        
        if question_type == 'comparative':
            return base_k * 2  # Need more context for comparisons
        elif question_type == 'analytical':
            return int(base_k * 1.5)  # Need more context for analysis
        elif is_complex:
            return int(base_k * 1.5)
        else:
            return base_k
    
    def _suggest_temperature(self, question_type: str) -> float:
        """Suggest optimal temperature based on question type."""
        if question_type == 'factual':
            return 0.3  # Lower temperature for factual answers
        elif question_type == 'analytical':
            return 0.8  # Higher temperature for creative analysis
        elif question_type == 'procedural':
            return 0.5  # Medium temperature for step-by-step
        else:
            return 0.7  # Default
    
    def enhance_query(self, query: str, analysis: Dict[str, Any]) -> str:
        """
        Enhance query based on analysis for better retrieval.
        
        Args:
            query: Original query
            analysis: Query analysis results
            
        Returns:
            Enhanced query string
        """
        # Ensure query is a string
        if not isinstance(query, str):
            query = str(query) if query is not None else ""
        
        if not query or not query.strip():
            return ""
        
        enhanced = query.strip()
        
        # Add entity context if entities found
        if analysis and isinstance(analysis, dict) and 'entities' in analysis:
            entities_dict = analysis.get('entities', {})
            if entities_dict and isinstance(entities_dict, dict):
                entity_context = []
                for entity_type, entities in entities_dict.items():
                    if isinstance(entities, (list, tuple)):
                        # Filter and convert to strings
                        for entity in entities:
                            if entity is not None:
                                entity_str = str(entity).strip()
                                if entity_str and entity_str not in entity_context:
                                    entity_context.append(entity_str)
                
                if entity_context:
                    # Join entities and append to query
                    entity_text = ' '.join(entity_context)
                    enhanced = f"{enhanced} {entity_text}".strip()
        
        # Final validation - ensure we return a valid string
        if not isinstance(enhanced, str):
            enhanced = str(enhanced) if enhanced is not None else query
        
        # Remove any null bytes
        enhanced = enhanced.replace('\x00', '').strip()
        
        return enhanced if enhanced else query

