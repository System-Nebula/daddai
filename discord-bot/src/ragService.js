const { spawn } = require('child_process');
const path = require('path');

class RAGService {
    constructor() {
        this.pythonPath = process.env.PYTHON_PATH || 'python';
        this.ragScriptPath = path.join(__dirname, '..', '..', 'src', 'api', 'rag_api.py');
    }

    /**
     * Query RAG system with conversation context
     * @param {string} question - User's question
     * @param {Array} conversationHistory - Previous conversation messages
     * @param {string} userId - Discord user ID
     * @returns {Promise<Object>} RAG response with answer and context
     */
    async queryWithContext(question, conversationHistory = [], userId = null) {
        return new Promise((resolve, reject) => {
            // Build context from conversation history
            const contextPrompt = this.buildContextPrompt(question, conversationHistory);
            
            // Build command arguments
            const args = [
                path.join(__dirname, '..', '..', 'src', 'api', 'rag_api.py'),
                '--question', contextPrompt,
                '--top-k', '10',
                '--use-memory', 'true',
                '--use-shared-docs', 'true'
            ];
            
            if (userId) {
                args.push('--user-id', userId);
            }
            
            // Call Python RAG script
            const pythonProcess = spawn(this.pythonPath, args);

            let stdout = '';
            let stderr = '';

            pythonProcess.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            pythonProcess.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            // Set timeout (60 seconds for RAG)
            const timeout = setTimeout(() => {
                pythonProcess.kill();
                reject(new Error('RAG service timeout'));
            }, 60000);
            
            pythonProcess.on('close', (code) => {
                clearTimeout(timeout);
                
                if (code !== 0) {
                    console.error('Python script error:', stderr);
                    reject(new Error(`RAG service error: ${stderr || 'Unknown error'}`));
                    return;
                }

                try {
                    // Extract JSON from stdout (handle debug output that might be printed)
                    // Look for JSON object in stdout
                    const jsonMatch = stdout.match(/\{[\s\S]*\}/);
                    if (jsonMatch) {
                        const response = JSON.parse(jsonMatch[0]);
                        resolve(response);
                    } else {
                        // Try parsing entire stdout as JSON
                        const response = JSON.parse(stdout.trim());
                        resolve(response);
                    }
                } catch (error) {
                    console.error('Failed to parse RAG response:', stdout);
                    reject(new Error('Invalid response from RAG service'));
                }
            });

            pythonProcess.on('error', (error) => {
                reject(new Error(`Failed to start RAG service: ${error.message}`));
            });
        });
    }

    /**
     * Build context-aware prompt from conversation history
     * @param {string} currentQuestion - Current question
     * @param {Array} conversationHistory - Previous messages
     * @returns {string} Enhanced prompt with context
     */
    buildContextPrompt(currentQuestion, conversationHistory) {
        if (!conversationHistory || conversationHistory.length === 0) {
            return currentQuestion;
        }

        // Get recent conversation (last 5 exchanges)
        const recentHistory = conversationHistory.slice(-5);
        
        let contextPrompt = currentQuestion;
        
        // Add conversation context if relevant
        if (recentHistory.length > 0) {
            const contextParts = recentHistory.map(msg => {
                return `Previous Q: ${msg.question}\nPrevious A: ${msg.answer}`;
            }).join('\n\n');
            
            contextPrompt = `[Conversation Context]\n${contextParts}\n\n[Current Question]\n${currentQuestion}`;
        }

        return contextPrompt;
    }

    /**
     * Simple query without context (for testing)
     */
    async query(question, topK = 10) {
        return this.queryWithContext(question, [], null);
    }
}

module.exports = RAGService;

