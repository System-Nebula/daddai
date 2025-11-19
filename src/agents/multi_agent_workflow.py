"""
Multi-Agent Workflow with LangGraph - Reflection Pattern Implementation.
Orchestrates SearchAgent, AnalyserAgent, and ReflectionAgent in a cyclical workflow.
"""
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime
import operator

from logger_config import logger

try:
    from langgraph.graph import StateGraph, END
    from langgraph.graph.message import add_messages
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph not available. Install with: pip install langgraph>=0.2.0")

from src.agents.search_agent import SearchAgent
from src.agents.analyser_agent import AnalyserAgent
from src.agents.reflection_agent import ReflectionAgent


class IncidentState(TypedDict):
    """State shared between agents in the workflow."""
    query: str
    search_results: List[Dict[str, Any]]
    analysis: str
    quality_score: float
    feedback: str
    iteration: int
    past_memories: List[Dict[str, Any]]
    final_analysis: Optional[str]
    max_iterations: int
    quality_threshold: float
    sources_used: List[str]
    metadata: Dict[str, Any]


class MultiAgentWorkflow:
    """
    Multi-agent workflow implementing the reflection pattern.
    Orchestrates SearchAgent, AnalyserAgent, and ReflectionAgent.
    """
    
    def __init__(self,
                 search_agent: Optional[SearchAgent] = None,
                 analyser_agent: Optional[AnalyserAgent] = None,
                 reflection_agent: Optional[ReflectionAgent] = None,
                 max_iterations: int = 3,
                 quality_threshold: float = 0.8):
        """
        Initialize multi-agent workflow.
        
        Args:
            search_agent: SearchAgent instance (auto-created if None)
            analyser_agent: AnalyserAgent instance (auto-created if None)
            reflection_agent: ReflectionAgent instance (auto-created if None)
            max_iterations: Maximum number of reflection iterations
            quality_threshold: Minimum quality score to accept (0.0-1.0)
        """
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("LangGraph is required. Install with: pip install langgraph>=0.2.0")
        
        self.search_agent = search_agent or SearchAgent()
        self.analyser_agent = analyser_agent or AnalyserAgent()
        self.reflection_agent = reflection_agent or ReflectionAgent(quality_threshold=quality_threshold)
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        
        # Build workflow graph
        self.workflow = self._build_workflow()
        logger.info(f"🔄 MultiAgentWorkflow initialized (max_iterations={max_iterations}, threshold={quality_threshold})")
    
    def _build_workflow(self) -> StateGraph:
        """Build LangGraph workflow with reflection pattern."""
        workflow = StateGraph(IncidentState)
        
        # Add nodes
        workflow.add_node("search", self._search_node)
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("reflect", self._reflect_node)
        workflow.add_node("increment", self._increment_node)
        workflow.add_node("finalize", self._finalize_node)
        
        # Set entry point
        workflow.set_entry_point("search")
        
        # Add edges
        workflow.add_edge("search", "analyze")
        workflow.add_edge("analyze", "reflect")
        
        # Conditional edge: reflect -> increment (if quality < threshold) or finalize
        workflow.add_conditional_edges(
            "reflect",
            self._should_continue,
            {
                "increment": "increment",
                "finalize": "finalize"
            }
        )
        
        # Feedback loop: increment -> analyze
        workflow.add_edge("increment", "analyze")
        
        # Finalize -> END
        workflow.add_edge("finalize", END)
        
        return workflow.compile()
    
    def _search_node(self, state: IncidentState) -> IncidentState:
        """SearchAgent node - performs hybrid search."""
        logger.info(f"🔍 SearchAgent: Searching for '{state['query']}'")
        
        try:
            search_result = self.search_agent.search(
                query=state["query"],
                top_k=15
            )
            
            state["search_results"] = search_result.get("results", [])
            state["metadata"] = state.get("metadata", {})
            state["metadata"]["search_count"] = len(state["search_results"])
            
            logger.info(f"🔍 SearchAgent found {len(state['search_results'])} results")
        except Exception as e:
            logger.error(f"Error in search node: {e}", exc_info=True)
            state["search_results"] = []
        
        return state
    
    def _analyze_node(self, state: IncidentState) -> IncidentState:
        """AnalyserAgent node - generates analysis."""
        iteration = state.get("iteration", 1)
        feedback = state.get("feedback", None)
        
        logger.info(f"🧠 AnalyserAgent: Generating analysis (iteration {iteration})")
        
        try:
            analysis_result = self.analyser_agent.analyze(
                query=state["query"],
                search_results=state.get("search_results", []),
                past_memories=state.get("past_memories", []),
                feedback=feedback,
                iteration=iteration
            )
            
            state["analysis"] = analysis_result.get("analysis", "")
            state["sources_used"] = analysis_result.get("sources_used", [])
            state["metadata"] = state.get("metadata", {})
            state["metadata"][f"analysis_iteration_{iteration}"] = {
                "confidence": analysis_result.get("confidence", 0.0),
                "context_length": analysis_result.get("context_length", 0)
            }
            
            logger.info(f"🧠 AnalyserAgent generated analysis (iteration {iteration})")
        except Exception as e:
            logger.error(f"Error in analyze node: {e}", exc_info=True)
            state["analysis"] = f"Error generating analysis: {str(e)}"
        
        return state
    
    def _reflect_node(self, state: IncidentState) -> IncidentState:
        """ReflectionAgent node - evaluates quality."""
        iteration = state.get("iteration", 1)
        
        logger.info(f"🔍 ReflectionAgent: Evaluating quality (iteration {iteration})")
        
        try:
            evaluation = self.reflection_agent.evaluate(
                query=state["query"],
                analysis=state.get("analysis", ""),
                search_results=state.get("search_results", []),
                iteration=iteration
            )
            
            state["quality_score"] = evaluation.get("quality_score", 0.0)
            state["feedback"] = evaluation.get("feedback", "")
            state["metadata"] = state.get("metadata", {})
            state["metadata"][f"evaluation_iteration_{iteration}"] = {
                "quality_score": state["quality_score"],
                "strengths": evaluation.get("strengths", []),
                "weaknesses": evaluation.get("weaknesses", [])
            }
            
            logger.info(f"🔍 ReflectionAgent: quality={state['quality_score']:.2f}, meets_threshold={evaluation.get('meets_threshold', False)}")
        except Exception as e:
            logger.error(f"Error in reflect node: {e}", exc_info=True)
            # Default to moderate quality, allow continuation
            state["quality_score"] = 0.6
            state["feedback"] = f"Evaluation error: {str(e)}"
        
        return state
    
    def _increment_node(self, state: IncidentState) -> IncidentState:
        """Increment iteration counter for feedback loop."""
        current_iteration = state.get("iteration", 1)
        state["iteration"] = current_iteration + 1
        
        logger.info(f"🔄 Incrementing iteration: {current_iteration} -> {state['iteration']}")
        return state
    
    def _finalize_node(self, state: IncidentState) -> IncidentState:
        """Finalize workflow - prepare final result."""
        state["final_analysis"] = state.get("analysis", "")
        state["metadata"] = state.get("metadata", {})
        state["metadata"]["finalized_at"] = datetime.utcnow().isoformat()
        state["metadata"]["total_iterations"] = state.get("iteration", 1)
        state["metadata"]["final_quality_score"] = state.get("quality_score", 0.0)
        
        logger.info(f"✅ Workflow finalized after {state['iteration']} iterations (quality: {state.get('quality_score', 0.0):.2f})")
        return state
    
    def _should_continue(self, state: IncidentState) -> str:
        """
        Decision function: should we continue iterating or finalize?
        
        Returns:
            "increment" if should continue, "finalize" if should stop
        """
        quality_score = state.get("quality_score", 0.0)
        iteration = state.get("iteration", 1)
        max_iterations = state.get("max_iterations", self.max_iterations)
        
        # Finalize if:
        # 1. Quality meets threshold, OR
        # 2. Max iterations reached
        if quality_score >= self.quality_threshold:
            logger.info(f"✅ Quality threshold met ({quality_score:.2f} >= {self.quality_threshold})")
            return "finalize"
        
        if iteration >= max_iterations:
            logger.info(f"⏱️ Max iterations reached ({iteration} >= {max_iterations})")
            return "finalize"
        
        # Otherwise, continue iterating
        logger.info(f"🔄 Continuing iteration ({iteration} < {max_iterations}, quality: {quality_score:.2f} < {self.quality_threshold})")
        return "increment"
    
    def run(self,
            query: str,
            past_memories: Optional[List[Dict[str, Any]]] = None,
            max_iterations: Optional[int] = None,
            quality_threshold: Optional[float] = None) -> Dict[str, Any]:
        """
        Run the multi-agent workflow.
        
        Args:
            query: User query to analyze
            past_memories: Optional past successful analyses (for learning)
            max_iterations: Override max iterations (optional)
            quality_threshold: Override quality threshold (optional)
            
        Returns:
            {
                "query": str,
                "final_analysis": str,
                "quality_score": float,
                "iteration": int,
                "sources_used": List[str],
                "search_results_count": int,
                "metadata": Dict[str, Any]
            }
        """
        # Initialize state
        initial_state: IncidentState = {
            "query": query,
            "search_results": [],
            "analysis": "",
            "quality_score": 0.0,
            "feedback": "",
            "iteration": 1,
            "past_memories": past_memories or [],
            "final_analysis": None,
            "max_iterations": max_iterations or self.max_iterations,
            "quality_threshold": quality_threshold or self.quality_threshold,
            "sources_used": [],
            "metadata": {}
        }
        
        logger.info(f"🚀 Starting multi-agent workflow for query: {query[:50]}...")
        
        try:
            # Run workflow
            final_state = self.workflow.invoke(initial_state)
            
            result = {
                "query": final_state["query"],
                "final_analysis": final_state.get("final_analysis", final_state.get("analysis", "")),
                "quality_score": final_state.get("quality_score", 0.0),
                "iteration": final_state.get("iteration", 1),
                "sources_used": final_state.get("sources_used", []),
                "search_results_count": len(final_state.get("search_results", [])),
                "metadata": final_state.get("metadata", {})
            }
            
            logger.info(f"✅ Multi-agent workflow completed: {result['iteration']} iterations, quality: {result['quality_score']:.2f}")
            return result
        except Exception as e:
            logger.error(f"Error running workflow: {e}", exc_info=True)
            return {
                "query": query,
                "final_analysis": f"Error in workflow: {str(e)}",
                "quality_score": 0.0,
                "iteration": 1,
                "sources_used": [],
                "search_results_count": 0,
                "metadata": {"error": str(e)}
            }
    
    def close(self):
        """Close all agent connections."""
        if self.search_agent:
            self.search_agent.close()

