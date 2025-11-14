"""
Centralized logging configuration for the RAG system.
"""
import logging
import sys
from pathlib import Path
from config import LOG_LEVEL, LOG_FILE

def setup_logger(name: str = "rag_system") -> logging.Logger:
    """
    Set up a logger with consistent formatting.
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if configured)
    if LOG_FILE:
        log_path = Path(LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# Global logger instance
logger = setup_logger()

