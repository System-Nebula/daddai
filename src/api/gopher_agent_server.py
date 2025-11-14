#!/usr/bin/env python3
"""
GopherAgent HTTP Server - Fast API for Discord bot
Provides persistent HTTP endpoint instead of subprocess calls for better performance.
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.agents.gopher_agent import get_gopher_agent
from logger_config import logger

app = Flask(__name__)
CORS(app)

# Get singleton GopherAgent instance
agent = get_gopher_agent()

@app.route('/classify_intent', methods=['POST'])
def classify_intent():
    """Classify message intent."""
    try:
        data = request.json
        message = data.get('message', '')
        context = data.get('context', {})
        
        result = agent.classify_intent(message, context, use_cache=True)
        return jsonify(result)
    except Exception as e:
        logger.error(f"GopherAgent API error: {e}", exc_info=True)
        return jsonify({'error': str(e), 'error_type': type(e).__name__}), 500

@app.route('/route_message', methods=['POST'])
def route_message():
    """Route message to appropriate handler."""
    try:
        data = request.json
        message = data.get('message', '')
        context = data.get('context', {})
        intent_result = data.get('intent_result')
        
        if intent_result:
            result = agent.route_message(message, context, intent_result)
        else:
            intent = agent.classify_intent(message, context, use_cache=True)
            result = agent.route_message(message, context, intent)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"GopherAgent API error: {e}", exc_info=True)
        return jsonify({'error': str(e), 'error_type': type(e).__name__}), 500

@app.route('/get_metrics', methods=['GET'])
def get_metrics():
    """Get performance metrics."""
    try:
        metrics = agent.get_metrics()
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"GopherAgent API error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check."""
    return jsonify({'status': 'ok', 'gpu_enabled': agent.use_gpu})

if __name__ == '__main__':
    import os
    port = int(os.getenv('GOPHER_AGENT_PORT', '8765'))
    logger.info(f"🚀 GopherAgent HTTP server starting on port {port}")
    app.run(host='0.0.0.0', port=port, threaded=True)

