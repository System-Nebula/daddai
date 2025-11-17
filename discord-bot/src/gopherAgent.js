const { spawn } = require('child_process');
const http = require('http');
const path = require('path');

class GopherAgent {
    constructor() {
        this.pythonPath = process.env.PYTHON_PATH || 'python';
        this.useHttp = process.env.GOPHER_AGENT_HTTP === 'true';
        this.httpHost = process.env.GOPHER_AGENT_HOST || 'localhost';
        this.httpPort = process.env.GOPHER_AGENT_PORT || '8765';
        this.timeout = 15000; // 15 second timeout
    }

    /**
     * Route message to appropriate handler
     * @param {string} message - User's message
     * @param {Object} context - Context object (has_attachments, is_mentioned, etc.)
     * @returns {Promise<Object>} Routing result with handler, intent, etc.
     */
    async routeMessage(message, context = {}) {
        if (this.useHttp) {
            return this._routeMessageHttp(message, context);
        } else {
            return this._routeMessageProcess(message, context);
        }
    }

    /**
     * Classify message intent
     * @param {string} message - User's message
     * @param {Object} context - Context object
     * @param {boolean} useCache - Whether to use cache
     * @returns {Promise<Object>} Intent classification result
     */
    async classifyIntent(message, context = {}, useCache = true) {
        if (this.useHttp) {
            return this._classifyIntentHttp(message, context, useCache);
        } else {
            return this._classifyIntentProcess(message, context, useCache);
        }
    }

    /**
     * Route message via HTTP API
     */
    async _routeMessageHttp(message, context) {
        return new Promise((resolve, reject) => {
            const postData = JSON.stringify({
                message: message,
                context: context
            });

            const options = {
                hostname: this.httpHost,
                port: this.httpPort,
                path: '/route_message',
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(postData)
                },
                timeout: this.timeout
            };

            const req = http.request(options, (res) => {
                let data = '';

                res.on('data', (chunk) => {
                    data += chunk;
                });

                res.on('end', () => {
                    if (res.statusCode !== 200) {
                        try {
                            const error = JSON.parse(data);
                            reject(new Error(error.error || `HTTP ${res.statusCode}: ${data}`));
                        } catch {
                            reject(new Error(`HTTP ${res.statusCode}: ${data}`));
                        }
                        return;
                    }

                    try {
                        const result = JSON.parse(data);
                        resolve(result);
                    } catch (error) {
                        reject(new Error(`Failed to parse response: ${error.message}`));
                    }
                });
            });

            req.on('error', (error) => {
                reject(new Error(`HTTP request failed: ${error.message}`));
            });

            req.on('timeout', () => {
                req.destroy();
                reject(new Error('GopherAgent HTTP request timeout'));
            });

            req.write(postData);
            req.end();
        });
    }

    /**
     * Classify intent via HTTP API
     */
    async _classifyIntentHttp(message, context, useCache) {
        return new Promise((resolve, reject) => {
            const postData = JSON.stringify({
                message: message,
                context: context,
                use_cache: useCache
            });

            const options = {
                hostname: this.httpHost,
                port: this.httpPort,
                path: '/classify_intent',
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(postData)
                },
                timeout: this.timeout
            };

            const req = http.request(options, (res) => {
                let data = '';

                res.on('data', (chunk) => {
                    data += chunk;
                });

                res.on('end', () => {
                    if (res.statusCode !== 200) {
                        try {
                            const error = JSON.parse(data);
                            reject(new Error(error.error || `HTTP ${res.statusCode}: ${data}`));
                        } catch {
                            reject(new Error(`HTTP ${res.statusCode}: ${data}`));
                        }
                        return;
                    }

                    try {
                        const result = JSON.parse(data);
                        resolve(result);
                    } catch (error) {
                        reject(new Error(`Failed to parse response: ${error.message}`));
                    }
                });
            });

            req.on('error', (error) => {
                reject(new Error(`HTTP request failed: ${error.message}`));
            });

            req.on('timeout', () => {
                req.destroy();
                reject(new Error('GopherAgent HTTP request timeout'));
            });

            req.write(postData);
            req.end();
        });
    }

    /**
     * Route message via Python process
     */
    async _routeMessageProcess(message, context) {
        return new Promise((resolve, reject) => {
            // Create a temporary Python script to call route_message
            const scriptPath = path.join(__dirname, '..', '..', 'src', 'api', 'gopher_agent_server.py');
            
            // Calculate project root from current file location
            const projectRoot = path.resolve(path.join(__dirname, '..', '..'));
            
            // We'll use a Python script that calls the agent directly
            const pythonScript = `
import sys
import json
import os
from pathlib import Path

# Add project root to path (passed as environment variable)
project_root = os.environ.get('DOCLING_PROJECT_ROOT')
if project_root:
    project_root = Path(project_root).resolve()
    if project_root.exists() and str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.agents.gopher_agent import get_gopher_agent

try:
    message = sys.argv[1]
    context_str = sys.argv[2] if len(sys.argv) > 2 else '{}'
    context = json.loads(context_str)
    
    agent = get_gopher_agent()
    result = agent.route_message(message, context)
    
    print(json.dumps(result))
except Exception as e:
    print(json.dumps({'error': str(e), 'error_type': type(e).__name__}), file=sys.stderr)
    sys.exit(1)
`;

            const args = [
                '-c',
                pythonScript,
                message,
                JSON.stringify(context)
            ];

            const pythonProcess = spawn(this.pythonPath, args, {
                env: {
                    ...process.env,
                    DOCLING_PROJECT_ROOT: projectRoot
                }
            });

            let stdout = '';
            let stderr = '';

            const timeout = setTimeout(() => {
                pythonProcess.kill();
                reject(new Error('GopherAgent timeout'));
            }, this.timeout);

            pythonProcess.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            pythonProcess.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            pythonProcess.on('close', (code) => {
                clearTimeout(timeout);

                if (code !== 0) {
                    reject(new Error(`GopherAgent error: ${stderr || 'Unknown error'}`));
                    return;
                }

                try {
                    // Extract JSON from stdout
                    const jsonMatch = stdout.match(/\{[\s\S]*\}/);
                    if (jsonMatch) {
                        const result = JSON.parse(jsonMatch[0]);
                        if (result.error) {
                            reject(new Error(result.error));
                        } else {
                            resolve(result);
                        }
                    } else {
                        reject(new Error('Invalid response from GopherAgent'));
                    }
                } catch (error) {
                    reject(new Error(`Failed to parse response: ${error.message}`));
                }
            });

            pythonProcess.on('error', (error) => {
                clearTimeout(timeout);
                reject(new Error(`Failed to start GopherAgent: ${error.message}`));
            });
        });
    }

    /**
     * Classify intent via Python process
     */
    async _classifyIntentProcess(message, context, useCache) {
        return new Promise((resolve, reject) => {
            // Calculate project root from current file location
            const projectRoot = path.resolve(path.join(__dirname, '..', '..'));
            
            const pythonScript = `
import sys
import json
import os
from pathlib import Path

# Add project root to path (passed as environment variable)
project_root = os.environ.get('DOCLING_PROJECT_ROOT')
if project_root:
    project_root = Path(project_root).resolve()
    if project_root.exists() and str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.agents.gopher_agent import get_gopher_agent

try:
    message = sys.argv[1]
    context_str = sys.argv[2] if len(sys.argv) > 2 else '{}'
    context = json.loads(context_str)
    use_cache = sys.argv[3].lower() == 'true' if len(sys.argv) > 3 else True
    
    agent = get_gopher_agent()
    result = agent.classify_intent(message, context, use_cache=use_cache)
    
    print(json.dumps(result))
except Exception as e:
    print(json.dumps({'error': str(e), 'error_type': type(e).__name__}), file=sys.stderr)
    sys.exit(1)
`;

            const args = [
                '-c',
                pythonScript,
                message,
                JSON.stringify(context),
                useCache.toString()
            ];

            const pythonProcess = spawn(this.pythonPath, args, {
                env: {
                    ...process.env,
                    DOCLING_PROJECT_ROOT: projectRoot
                }
            });

            let stdout = '';
            let stderr = '';

            const timeout = setTimeout(() => {
                pythonProcess.kill();
                reject(new Error('GopherAgent timeout'));
            }, this.timeout);

            pythonProcess.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            pythonProcess.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            pythonProcess.on('close', (code) => {
                clearTimeout(timeout);

                if (code !== 0) {
                    reject(new Error(`GopherAgent error: ${stderr || 'Unknown error'}`));
                    return;
                }

                try {
                    // Extract JSON from stdout
                    const jsonMatch = stdout.match(/\{[\s\S]*\}/);
                    if (jsonMatch) {
                        const result = JSON.parse(jsonMatch[0]);
                        if (result.error) {
                            reject(new Error(result.error));
                        } else {
                            resolve(result);
                        }
                    } else {
                        reject(new Error('Invalid response from GopherAgent'));
                    }
                } catch (error) {
                    reject(new Error(`Failed to parse response: ${error.message}`));
                }
            });

            pythonProcess.on('error', (error) => {
                clearTimeout(timeout);
                reject(new Error(`Failed to start GopherAgent: ${error.message}`));
            });
        });
    }
}

// Export singleton instance
module.exports = new GopherAgent();
