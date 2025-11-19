"""
Simple test to verify multi-agent components can be imported and initialized.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logger_config import logger

def test_imports():
    """Test that all components can be imported."""
    logger.info("Testing imports...")
    
    try:
        from src.agents.search_agent import SearchAgent
        logger.info("✅ SearchAgent imported")
    except Exception as e:
        logger.error(f"❌ SearchAgent import failed: {e}")
        return False
    
    try:
        from src.agents.analyser_agent import AnalyserAgent
        logger.info("✅ AnalyserAgent imported")
    except Exception as e:
        logger.error(f"❌ AnalyserAgent import failed: {e}")
        return False
    
    try:
        from src.agents.reflection_agent import ReflectionAgent
        logger.info("✅ ReflectionAgent imported")
    except Exception as e:
        logger.error(f"❌ ReflectionAgent import failed: {e}")
        return False
    
    try:
        from src.agents.multi_agent_workflow import MultiAgentWorkflow
        logger.info("✅ MultiAgentWorkflow imported")
    except Exception as e:
        logger.error(f"❌ MultiAgentWorkflow import failed: {e}")
        return False
    
    try:
        from src.memory.agent_memory_store import AgentMemoryStore
        logger.info("✅ AgentMemoryStore imported")
    except Exception as e:
        logger.error(f"❌ AgentMemoryStore import failed: {e}")
        return False
    
    return True

def test_langgraph():
    """Test LangGraph availability."""
    logger.info("Testing LangGraph...")
    
    try:
        from langgraph.graph import StateGraph, END
        logger.info("✅ LangGraph imported successfully")
        return True
    except ImportError as e:
        logger.error(f"❌ LangGraph not available: {e}")
        return False

def test_elasticsearch_config():
    """Test Elasticsearch configuration."""
    logger.info("Testing Elasticsearch configuration...")
    
    from config import ELASTICSEARCH_ENABLED, ELASTICSEARCH_HOST, ELASTICSEARCH_PORT
    
    logger.info(f"Elasticsearch Enabled: {ELASTICSEARCH_ENABLED}")
    logger.info(f"Elasticsearch Host: {ELASTICSEARCH_HOST}")
    logger.info(f"Elasticsearch Port: {ELASTICSEARCH_PORT}")
    
    if not ELASTICSEARCH_ENABLED:
        logger.warning("⚠️ Elasticsearch is not enabled. Multi-agent workflow requires Elasticsearch.")
        return False
    
    return True

if __name__ == "__main__":
    logger.info("="*80)
    logger.info("🧪 Multi-Agent System Component Tests")
    logger.info("="*80)
    
    all_passed = True
    
    # Test LangGraph
    if not test_langgraph():
        all_passed = False
    
    # Test Elasticsearch config
    if not test_elasticsearch_config():
        all_passed = False
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    logger.info("="*80)
    if all_passed:
        logger.info("✅ All component tests passed!")
    else:
        logger.warning("⚠️ Some tests failed. Check the logs above.")
    logger.info("="*80)

