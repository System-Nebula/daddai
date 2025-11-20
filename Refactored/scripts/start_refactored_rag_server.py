"""
Startup script for Refactored RAG HTTP Server.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Refactored.src.api.refactored_rag_http_server import run_server
import os

if __name__ == "__main__":
    host = os.getenv("REFACTORED_RAG_HOST", "localhost")
    port = int(os.getenv("REFACTORED_RAG_PORT", "8767"))
    
    run_server(host=host, port=port)

