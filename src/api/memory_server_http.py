#!/usr/bin/env python3
"""
Memory HTTP Server - REST API for Discord bot
Provides persistent HTTP endpoint as an alternative to stdin/stdout for better flexibility.
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.api.memory_server import MemoryServer
from logger_config import logger

app = Flask(__name__)
CORS(app)

# Initialize server instance
server = None

def get_server():
    """Get or create server instance."""
    global server
    if server is None:
        server = MemoryServer()
    return server

@app.route('/store', methods=['POST'])
def store_memory():
    """Store a memory."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        s = get_server()
        result = s.handle_request({
            'id': 0,
            'method': 'store',
            'params': {
                'channel_id': data.get('channel_id'),
                'content': data.get('content'),
                'memory_type': data.get('memory_type', 'conversation'),
                'metadata': data.get('metadata', {}),
                'channel_name': data.get('channel_name'),
                'user_id': data.get('user_id'),
                'username': data.get('username'),
                'mentioned_user_id': data.get('mentioned_user_id')
            }
        })
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify(result.get('result', {}))
    except Exception as e:
        logger.error(f"Memory HTTP API error: {e}", exc_info=True)
        return jsonify({'error': str(e), 'error_type': type(e).__name__}), 500

@app.route('/get', methods=['POST'])
def get_memories():
    """Get memories for a channel."""
    try:
        data = request.json or {}
        s = get_server()
        result = s.handle_request({
            'id': 0,
            'method': 'get',
            'params': {
                'channel_id': data.get('channel_id'),
                'channel_name': data.get('channel_name'),
                'limit': data.get('limit', 100)
            }
        })
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify(result.get('result', {}))
    except Exception as e:
        logger.error(f"Memory HTTP API error: {e}", exc_info=True)
        return jsonify({'error': str(e), 'error_type': type(e).__name__}), 500

@app.route('/list-channels', methods=['GET'])
def list_channels():
    """List all channels."""
    try:
        s = get_server()
        result = s.handle_request({
            'id': 0,
            'method': 'list-channels',
            'params': {}
        })
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify(result.get('result', {}))
    except Exception as e:
        logger.error(f"Memory HTTP API error: {e}", exc_info=True)
        return jsonify({'error': str(e), 'error_type': type(e).__name__}), 500

@app.route('/get-all', methods=['GET', 'POST'])
def get_all_memories():
    """Get all memories."""
    try:
        data = request.json or {} if request.method == 'POST' else {}
        s = get_server()
        result = s.handle_request({
            'id': 0,
            'method': 'get-all',
            'params': {
                'limit': data.get('limit', 1000)
            }
        })
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify(result.get('result', {}))
    except Exception as e:
        logger.error(f"Memory HTTP API error: {e}", exc_info=True)
        return jsonify({'error': str(e), 'error_type': type(e).__name__}), 500

@app.route('/search', methods=['POST'])
def search_memories():
    """Search memories."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        s = get_server()
        result = s.handle_request({
            'id': 0,
            'method': 'search',
            'params': {
                'channel_id': data.get('channel_id'),
                'query': data.get('query'),
                'top_k': data.get('top_k', 5),
                'mentioned_user_id': data.get('mentioned_user_id')
            }
        })
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify(result.get('result', {}))
    except Exception as e:
        logger.error(f"Memory HTTP API error: {e}", exc_info=True)
        return jsonify({'error': str(e), 'error_type': type(e).__name__}), 500

@app.route('/ping', methods=['GET'])
def ping():
    """Health check."""
    try:
        s = get_server()
        result = s.handle_request({
            'id': 0,
            'method': 'ping',
            'params': {}
        })
        return jsonify(result.get('result', {'status': 'ok'}))
    except Exception as e:
        logger.error(f"Memory HTTP API error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'service': 'memory'})

if __name__ == '__main__':
    port = int(os.getenv('MEMORY_SERVER_PORT', '8766'))
    logger.info(f"🚀 Memory HTTP server starting on port {port}")
    app.run(host='0.0.0.0', port=port, threaded=True)

