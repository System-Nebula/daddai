"""
Basic test of multi-agent workflow initialization and basic functionality.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logger_config import logger
from config import ELASTICSEARCH_ENABLED

def test_workflow_initialization():
    """Test that the workflow can be initialized."""
    logger.info("Testing workflow initialization...")
    
    try:
        from src.agents.multi_agent_workflow import MultiAgentWorkflow
        
        if not ELASTICSEARCH_ENABLED:
            logger.warning("⚠️ Elasticsearch not enabled, skipping workflow test")
            return False
        
        workflow = MultiAgentWorkflow(
            max_iterations=3,
            quality_threshold=0.8
        )
        
        logger.info("✅ Workflow initialized successfully")
        workflow.close()
        return True
    except Exception as e:
        logger.error(f"❌ Workflow initialization failed: {e}", exc_info=True)
        return False

def test_agents_initialization():
    """Test that individual agents can be initialized."""
    logger.info("Testing agent initialization...")
    
    if not ELASTICSEARCH_ENABLED:
        logger.warning("⚠️ Elasticsearch not enabled, skipping agent tests")
        return False
    
    try:
        from src.agents.search_agent import SearchAgent
        from src.agents.analyser_agent import AnalyserAgent
        from src.agents.reflection_agent import ReflectionAgent
        
        # Test SearchAgent
        search_agent = SearchAgent()
        logger.info("✅ SearchAgent initialized")
        search_agent.close()
        
        # Test AnalyserAgent
        analyser_agent = AnalyserAgent()
        logger.info("✅ AnalyserAgent initialized")
        
        # Test ReflectionAgent
        reflection_agent = ReflectionAgent()
        logger.info("✅ ReflectionAgent initialized")
        
        return True
    except Exception as e:
        logger.error(f"❌ Agent initialization failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("="*80)
    logger.info("🧪 Basic Multi-Agent System Tests")
    logger.info("="*80)
    
    all_passed = True
    
    if not test_agents_initialization():
        all_passed = False
    
    if not test_workflow_initialization():
        all_passed = False
    
    logger.info("="*80)
    if all_passed:
        logger.info("✅ All basic tests passed!")
        logger.info("💡 Ready to run full workflow test with actual queries")
    else:
        logger.warning("⚠️ Some tests failed. Check the logs above.")
    logger.info("="*80)

