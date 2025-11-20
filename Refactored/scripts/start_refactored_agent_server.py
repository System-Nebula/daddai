#!/usr/bin/env python3
"""
Startup script for Refactored Agent HTTP Server.
Provides a convenient way to start the server with proper configuration.
"""
import sys
import os
import argparse
from pathlib import Path

# Add parent directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from Refactored.src.api.refactored_agent_http_server import run_server
from Refactored.logger_config import logger


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Start Refactored Agent HTTP Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start on default host/port (localhost:8766)
  python -m Refactored.scripts.start_refactored_agent_server

  # Start on custom port
  python -m Refactored.scripts.start_refactored_agent_server --port 9000

  # Start on all interfaces
  python -m Refactored.scripts.start_refactored_agent_server --host 0.0.0.0
        """
    )
    
    parser.add_argument(
        '--host',
        default=os.getenv('REFACTORED_AGENT_HOST', 'localhost'),
        help='Host to bind to (default: localhost)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.getenv('REFACTORED_AGENT_PORT', '8766')),
        help='Port to bind to (default: 8766)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Refactored Agent HTTP Server")
    logger.info("=" * 60)
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    logger.info("=" * 60)
    
    try:
        run_server(args.host, args.port)
    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

