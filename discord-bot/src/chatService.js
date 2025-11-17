const { spawn } = require('child_process');
const path = require('path');

class ChatService {
    constructor() {
        this.pythonPath = process.env.PYTHON_PATH || 'python';
    }

    /**
     * Simple chat without RAG - direct LMStudio call
     * @param {string} message - User's message
     * @param {Array} conversationHistory - Previous conversation messages
     * @returns {Promise<string>} Response from LMStudio
     */
    async chat(message, conversationHistory = []) {
        return new Promise((resolve, reject) => {
            const args = [
                path.join(__dirname, '..', '..', 'src', 'api', 'chat_api.py'),
                '--message', message
            ];
            
            // Add conversation history if available
            if (conversationHistory && conversationHistory.length > 0) {
                const historyJson = JSON.stringify(conversationHistory.slice(-5)); // Last 5 messages
                args.push('--history', historyJson);
            }
            
            const pythonProcess = spawn(this.pythonPath, args);
            
            let stdout = '';
            let stderr = '';
            
            // Set timeout (30 seconds)
            const timeout = setTimeout(() => {
                pythonProcess.kill();
                reject(new Error('Chat service timeout'));
            }, 60000); // Increased to 60s for GLM-4.6 thinking model
            
            pythonProcess.stdout.on('data', (data) => {
                const output = data.toString();
                stdout += output;
                // Log stdout for debugging (but don't spam)
                if (output.length < 500) {
                    console.log(`[ChatService] stdout: ${output.trim()}`);
                }
            });
            
            pythonProcess.stderr.on('data', (data) => {
                const output = data.toString();
                stderr += output;
                // Log stderr for debugging
                console.log(`[ChatService] stderr: ${output.trim()}`);
            });
            
            pythonProcess.on('close', (code) => {
                clearTimeout(timeout);
                
                if (code !== 0) {
                    console.error('Chat service error:', stderr);
                    reject(new Error(`Chat service error: ${stderr || 'Unknown error'}`));
                    return;
                }
                
                // Extract JSON from stdout (handle debug output)
                console.log(`[ChatService] Process exited with code ${code}`);
                console.log(`[ChatService] stdout length: ${stdout.length}, stderr length: ${stderr.length}`);
                
                const jsonMatch = stdout.match(/\{[\s\S]*\}/);
                if (jsonMatch) {
                    try {
                        const response = JSON.parse(jsonMatch[0]);
                        console.log(`[ChatService] Parsed response:`, {
                            hasAnswer: !!response.answer,
                            answerLength: response.answer ? response.answer.length : 0,
                            answerPreview: response.answer ? response.answer.substring(0, 100) : 'none',
                            hasError: !!response.error,
                            error: response.error
                        });
                        resolve(response.answer || response.message || 'Sorry, I could not generate a response.');
                    } catch (error) {
                        console.error('[ChatService] Failed to parse chat response:', error.message);
                        console.error('[ChatService] stdout:', stdout.substring(0, 500));
                        reject(new Error('Invalid response from chat service'));
                    }
                } else {
                    console.warn('[ChatService] No JSON found in stdout');
                    console.log('[ChatService] stdout:', stdout.substring(0, 500));
                    // If no JSON found, try to use stdout as answer
                    const cleanOutput = stdout.trim();
                    if (cleanOutput) {
                        console.log('[ChatService] Using stdout as answer:', cleanOutput.substring(0, 100));
                        resolve(cleanOutput);
                    } else {
                        console.error('[ChatService] Empty stdout');
                        reject(new Error('Empty response from chat service'));
                    }
                }
            });
            
            pythonProcess.on('error', (error) => {
                clearTimeout(timeout);
                reject(new Error(`Failed to start chat service: ${error.message}`));
            });
        });
    }
}

module.exports = ChatService;

