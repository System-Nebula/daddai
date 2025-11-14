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
                path.join(__dirname, '..', '..', 'chat_api.py'),
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
            }, 30000);
            
            pythonProcess.stdout.on('data', (data) => {
                stdout += data.toString();
            });
            
            pythonProcess.stderr.on('data', (data) => {
                stderr += data.toString();
            });
            
            pythonProcess.on('close', (code) => {
                clearTimeout(timeout);
                
                if (code !== 0) {
                    console.error('Chat service error:', stderr);
                    reject(new Error(`Chat service error: ${stderr || 'Unknown error'}`));
                    return;
                }
                
                // Extract JSON from stdout (handle debug output)
                const jsonMatch = stdout.match(/\{[\s\S]*\}/);
                if (jsonMatch) {
                    try {
                        const response = JSON.parse(jsonMatch[0]);
                        resolve(response.answer || response.message || 'Sorry, I could not generate a response.');
                    } catch (error) {
                        console.error('Failed to parse chat response:', stdout);
                        reject(new Error('Invalid response from chat service'));
                    }
                } else {
                    // If no JSON found, try to use stdout as answer
                    const cleanOutput = stdout.trim();
                    if (cleanOutput) {
                        resolve(cleanOutput);
                    } else {
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

