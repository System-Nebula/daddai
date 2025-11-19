"""
AnalyserAgent - Specialized agent for reasoning and analysis generation.
Part of the multi-agent reflection pattern system.
"""
from typing import List, Dict, Any, Optional
from src.clients.llm_client_factory import get_default_llm_client
from config import RAG_TEMPERATURE, RAG_MAX_TOKENS
from logger_config import logger


class AnalyserAgent:
    """
    Specialized agent for generating analysis and reasoning based on retrieved context.
    Uses LLM to synthesize information from search results.
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize AnalyserAgent.
        
        Args:
            llm_client: LLM client (auto-created if None)
        """
        self.llm_client = llm_client or get_default_llm_client()
        logger.info("🧠 AnalyserAgent initialized")
    
    def analyze(self,
                query: str,
                search_results: List[Dict[str, Any]],
                past_memories: Optional[List[Dict[str, Any]]] = None,
                feedback: Optional[str] = None,
                iteration: int = 1) -> Dict[str, Any]:
        """
        Generate analysis based on search results and optional feedback.
        
        Args:
            query: Original user query
            search_results: Results from SearchAgent
            past_memories: Optional past successful analyses (for learning)
            feedback: Optional feedback from ReflectionAgent (for iteration)
            iteration: Current iteration number
            
        Returns:
            {
                "analysis": str,
                "query": str,
                "iteration": int,
                "sources_used": List[str],
                "confidence": float
            }
        """
        try:
            # Build context from search results
            context_chunks = []
            sources_used = []
            
            for result in search_results[:10]:  # Use top 10 results
                text = result.get("text", "")
                file_name = result.get("file_name", "unknown")
                chunk_id = result.get("chunk_id", "")
                
                if text:
                    context_chunks.append(f"[From {file_name}]: {text}")
                    if file_name not in sources_used:
                        sources_used.append(file_name)
            
            context_text = "\n\n".join(context_chunks)
            
            # Build prompt with optional past memories
            memory_context = ""
            if past_memories:
                memory_context = "\n\n## Similar Past Solutions:\n"
                for i, memory in enumerate(past_memories[:3], 1):  # Top 3 similar memories
                    memory_context += f"\n{i}. {memory.get('content', '')[:300]}...\n"
            
            # Build feedback context if iterating
            feedback_context = ""
            if feedback and iteration > 1:
                feedback_context = f"\n\n## Feedback from Previous Iteration:\n{feedback}\n\nPlease address this feedback and improve your analysis."
            
            # Build system prompt
            system_prompt = """You are an expert analyst specializing in document analysis and root cause analysis.
Your task is to analyze information from documents and provide clear, accurate, and well-reasoned analysis.

Guidelines:
- Base your analysis strictly on the provided context
- Be specific and cite sources when possible
- If information is missing, acknowledge it rather than guessing
- Structure your analysis logically
- Provide actionable insights when possible"""
            
            # Build user prompt
            user_prompt = f"""## Query:
{query}

## Context from Documents:
{context_text[:3000]}  # Limit context size
{memory_context}
{feedback_context}

## Instructions:
Analyze the query based on the provided context. If you're iterating (iteration {iteration}), incorporate the feedback to improve your analysis.

Provide a clear, well-structured analysis that directly addresses the query."""

            # Generate analysis
            response = self.llm_client.generate_response(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=RAG_TEMPERATURE,
                max_tokens=RAG_MAX_TOKENS * 2  # More tokens for analysis
            )
            
            analysis = response if isinstance(response, str) else response.get("content", str(response))
            
            # Estimate confidence based on context quality
            confidence = min(0.95, 0.5 + (len(search_results) / 20.0))
            
            logger.info(f"🧠 AnalyserAgent generated analysis (iteration {iteration}, confidence: {confidence:.2f})")
            
            return {
                "analysis": analysis,
                "query": query,
                "iteration": iteration,
                "sources_used": sources_used,
                "confidence": confidence,
                "context_length": len(context_text)
            }
        except Exception as e:
            logger.error(f"Error in AnalyserAgent.analyze: {e}", exc_info=True)
            return {
                "analysis": f"Error generating analysis: {str(e)}",
                "query": query,
                "iteration": iteration,
                "sources_used": [],
                "confidence": 0.0,
                "error": str(e)
            }

