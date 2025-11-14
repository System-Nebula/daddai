#!/usr/bin/env python3
"""
GopherAgent API - Command-line interface for GopherAgent
Used by Discord bot to call GopherAgent functions.
"""
import sys
import json
import argparse
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Now import modules
from src.agents.gopher_agent import get_gopher_agent
from logger_config import logger


def main():
    parser = argparse.ArgumentParser(description='GopherAgent API')
    parser.add_argument('--method', required=True, help='Method to call')
    parser.add_argument('--params', required=True, help='JSON parameters')
    
    args = parser.parse_args()
    
    try:
        # Parse parameters
        params = json.loads(args.params)
        
        # Get GopherAgent instance (singleton, cached)
        agent = get_gopher_agent()
        
        # Call method with timeout handling
        result = None
        if args.method == 'classify_intent':
            message = params.get('message', '')
            context = params.get('context', {})
            # Use cache aggressively for speed
            result = agent.classify_intent(message, context, use_cache=True)
            
        elif args.method == 'route_message':
            message = params.get('message', '')
            context = params.get('context', {})
            intent_result = params.get('intent_result')
            # If intent_result provided, use it (already cached)
            if intent_result:
                result = agent.route_message(message, context, intent_result)
            else:
                # Get intent first (will use cache)
                intent = agent.classify_intent(message, context, use_cache=True)
                result = agent.route_message(message, context, intent)
            
        elif args.method == 'batch_classify':
            messages = params.get('messages', [])
            # Convert to list of tuples
            message_tuples = [(msg.get('message', ''), msg.get('context', {})) 
                             for msg in messages]
            results = agent.batch_classify(message_tuples)
            result = {'results': results}
            
        elif args.method == 'get_metrics':
            result = agent.get_metrics()
            
        else:
            result = {'error': f'Unknown method: {args.method}'}
        
        # Output JSON result immediately (flush for faster response)
        output = json.dumps(result, ensure_ascii=False)
        print(output, flush=True)
        
    except Exception as e:
        logger.error(f"GopherAgent API error: {e}", exc_info=True)
        error_result = {
            'error': str(e),
            'error_type': type(e).__name__
        }
        print(json.dumps(error_result, ensure_ascii=False), flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

