"""
ReflectionAgent - Specialized agent for quality evaluation and feedback.
Part of the multi-agent reflection pattern system.
"""
from typing import List, Dict, Any, Optional
from src.clients.llm_client_factory import get_default_llm_client
from logger_config import logger


class ReflectionAgent:
    """
    Specialized agent for evaluating output quality and providing feedback.
    Implements the reflection pattern for self-correcting agents.
    """
    
    def __init__(self, llm_client=None, quality_threshold: float = 0.8):
        """
        Initialize ReflectionAgent.
        
        Args:
            llm_client: LLM client (auto-created if None)
            quality_threshold: Minimum quality score to accept (0.0-1.0)
        """
        self.llm_client = llm_client or get_default_llm_client()
        self.quality_threshold = quality_threshold
        logger.info(f"🔍 ReflectionAgent initialized (threshold: {quality_threshold})")
    
    def evaluate(self,
                 query: str,
                 analysis: str,
                 search_results: List[Dict[str, Any]],
                 iteration: int = 1) -> Dict[str, Any]:
        """
        Evaluate the quality of an analysis and provide feedback.
        
        Args:
            query: Original user query
            analysis: Analysis to evaluate
            search_results: Search results used for analysis
            iteration: Current iteration number
            
        Returns:
            {
                "quality_score": float,  # 0.0-1.0
                "meets_threshold": bool,
                "feedback": str,  # Feedback for improvement (if quality < threshold)
                "strengths": List[str],
                "weaknesses": List[str],
                "iteration": int
            }
        """
        try:
            # Build context summary
            context_summary = f"Found {len(search_results)} relevant document chunks"
            if search_results:
                top_result = search_results[0]
                context_summary += f" from {top_result.get('file_name', 'unknown')}"
            
            # Build evaluation prompt
            system_prompt = """You are a quality evaluator for document analysis.
Your task is to evaluate the quality of analyses and provide constructive feedback.

Evaluation Criteria:
1. Accuracy: Does the analysis correctly interpret the source material?
2. Completeness: Does it address all aspects of the query?
3. Clarity: Is the analysis well-structured and easy to understand?
4. Relevance: Does it stay focused on the query?
5. Evidence: Does it cite sources appropriately?

Provide a quality score (0.0-1.0) and specific feedback for improvement if needed."""
            
            user_prompt = f"""## Query:
{query}

## Context Available:
{context_summary}

## Analysis to Evaluate:
{analysis}

## Instructions:
Evaluate this analysis on a scale of 0.0 to 1.0 based on:
- Accuracy (0.2): Correct interpretation of sources
- Completeness (0.2): Addresses all aspects of query
- Clarity (0.2): Well-structured and clear
- Relevance (0.2): Stays focused on query
- Evidence (0.2): Properly cites sources

Respond in JSON format:
{{
    "quality_score": 0.0-1.0,
    "meets_threshold": true/false,
    "feedback": "Specific feedback for improvement (if quality < 0.8)",
    "strengths": ["strength1", "strength2"],
    "weaknesses": ["weakness1", "weakness2"]
}}"""

            # Generate evaluation
            response = self.llm_client.generate_response(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent evaluation
                max_tokens=500
            )
            
            # Parse response (try JSON first, fallback to text parsing)
            evaluation = self._parse_evaluation(response)
            
            # Ensure quality_score is in valid range
            quality_score = max(0.0, min(1.0, evaluation.get("quality_score", 0.5)))
            meets_threshold = quality_score >= self.quality_threshold
            
            result = {
                "quality_score": quality_score,
                "meets_threshold": meets_threshold,
                "feedback": evaluation.get("feedback", ""),
                "strengths": evaluation.get("strengths", []),
                "weaknesses": evaluation.get("weaknesses", []),
                "iteration": iteration
            }
            
            logger.info(f"🔍 ReflectionAgent evaluation: quality={quality_score:.2f}, meets_threshold={meets_threshold}")
            
            return result
        except Exception as e:
            logger.error(f"Error in ReflectionAgent.evaluate: {e}", exc_info=True)
            # Fallback: moderate quality score, allow continuation
            return {
                "quality_score": 0.6,
                "meets_threshold": False,
                "feedback": f"Evaluation error: {str(e)}. Please review the analysis manually.",
                "strengths": [],
                "weaknesses": ["Evaluation system error"],
                "iteration": iteration,
                "error": str(e)
            }
    
    def _parse_evaluation(self, response: str) -> Dict[str, Any]:
        """Parse evaluation response (handles JSON or text)."""
        import json
        import re
        
        if not response:
            return {"quality_score": 0.5, "feedback": "", "strengths": [], "weaknesses": []}
        
        # Try to extract JSON
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Fallback: try to extract score from text
        score_match = re.search(r'(?:quality[_\s]*score|score)[:\s]*([0-9.]+)', response, re.IGNORECASE)
        if score_match:
            try:
                score = float(score_match.group(1))
                # Normalize if score is out of range
                if score > 1.0:
                    score = score / 100.0
                return {
                    "quality_score": max(0.0, min(1.0, score)),
                    "feedback": response[:200],
                    "strengths": [],
                    "weaknesses": []
                }
            except ValueError:
                pass
        
        # Default fallback
        return {
            "quality_score": 0.5,
            "feedback": response[:200] if response else "",
            "strengths": [],
            "weaknesses": []
        }

