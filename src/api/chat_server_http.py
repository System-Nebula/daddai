#!/usr/bin/env python3
"""
Chat HTTP Server - REST API for Discord bot
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

from src.api.chat_server import ChatServer
from logger_config import logger

app = Flask(__name__)
CORS(app)

# Initialize server instance
server = None

def get_server():
    """Get or create server instance."""
    global server
    if server is None:
        server = ChatServer()
    return server

@app.route('/chat', methods=['POST'])
def chat():
    """Chat endpoint."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        message = data.get('message', '')
        if not message:
            return jsonify({'error': 'message required'}), 400
        
        s = get_server()
        result = s.handle_request({
            'id': 0,
            'method': 'chat',
            'params': {
                'message': message,
                'history': data.get('history', []),
                'temperature': data.get('temperature', 0.85),
                'max_tokens': data.get('max_tokens', 500),
                'stream': data.get('stream', False)
            }
        })
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify(result.get('result', {}))
    except Exception as e:
        logger.error(f"Chat HTTP API error: {e}", exc_info=True)
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
        logger.error(f"Chat HTTP API error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'service': 'chat'})

if __name__ == '__main__':
    port = int(os.getenv('CHAT_SERVER_PORT', '8767'))
    logger.info(f"🚀 Chat HTTP server starting on port {port}")
    app.run(host='0.0.0.0', port=port, threaded=True)

