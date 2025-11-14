const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

class DocumentService {
    constructor() {
        this.pythonPath = process.env.PYTHON_PATH || 'python';
    }

    /**
     * Upload and process a document
     */
    async uploadDocument(userId, filePath, fileName) {
        return new Promise((resolve, reject) => {
            const pythonProcess = spawn(this.pythonPath, [
                path.join(__dirname, '..', '..', 'src', 'api', 'document_api.py'),
                '--action', 'upload',
                '--user-id', userId,
                '--file-path', filePath,
                '--file-name', fileName
            ]);

            let stdout = '';
            let stderr = '';

            pythonProcess.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            pythonProcess.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            pythonProcess.on('close', (code) => {
                if (code !== 0) {
                    console.error('Document upload error - stderr:', stderr);
                    console.error('Document upload error - stdout:', stdout);
                    reject(new Error(`Document service error: ${stderr || 'Unknown error'}`));
                    return;
                }
                try {
                    // Extract JSON from stdout (handle debug output that might be printed)
                    let cleanedStdout = stdout.trim();
                    
                    // Find JSON object by finding first { and matching closing }
                    const firstBrace = cleanedStdout.indexOf('{');
                    if (firstBrace === -1) {
                        throw new Error('No JSON object found in stdout');
                    }
                    
                    // Find the matching closing brace by counting braces
                    let braceCount = 0;
                    let lastBrace = -1;
                    for (let i = firstBrace; i < cleanedStdout.length; i++) {
                        if (cleanedStdout[i] === '{') braceCount++;
                        if (cleanedStdout[i] === '}') {
                            braceCount--;
                            if (braceCount === 0) {
                                lastBrace = i;
                                break;
                            }
                        }
                    }
                    
                    if (lastBrace === -1) {
                        throw new Error('Incomplete JSON object in stdout');
                    }
                    
                    const jsonStr = cleanedStdout.substring(firstBrace, lastBrace + 1);
                    const response = JSON.parse(jsonStr);
                    resolve(response);
                } catch (error) {
                    console.error('Failed to parse document upload response:', error.message);
                    console.error('Raw stdout length:', stdout.length);
                    console.error('Raw stdout (first 2000 chars):', stdout.substring(0, 2000));
                    console.error('Raw stderr:', stderr.substring(0, 500));
                    reject(new Error('Invalid response from document service'));
                }
            });
        });
    }

    /**
     * Get all shared documents
     */
    async getAllDocuments() {
        return new Promise((resolve, reject) => {
            const pythonProcess = spawn(this.pythonPath, [
                path.join(__dirname, '..', '..', 'src', 'api', 'document_api.py'),
                '--action', 'list'
            ]);

            let stdout = '';
            let stderr = '';

            pythonProcess.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            pythonProcess.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            pythonProcess.on('close', (code) => {
                if (code !== 0) {
                    console.error('Document service error - stderr:', stderr);
                    console.error('Document service error - stdout:', stdout);
                    reject(new Error(`Document service error: ${stderr || 'Unknown error'}`));
                    return;
                }
                try {
                    // Extract JSON from stdout (handle debug output that might be printed)
                    let cleanedStdout = stdout.trim();
                    
                    // Find JSON object by finding first { and matching closing }
                    const firstBrace = cleanedStdout.indexOf('{');
                    if (firstBrace === -1) {
                        throw new Error('No JSON object found in stdout');
                    }
                    
                    // Find the matching closing brace by counting braces
                    let braceCount = 0;
                    let lastBrace = -1;
                    for (let i = firstBrace; i < cleanedStdout.length; i++) {
                        if (cleanedStdout[i] === '{') braceCount++;
                        if (cleanedStdout[i] === '}') {
                            braceCount--;
                            if (braceCount === 0) {
                                lastBrace = i;
                                break;
                            }
                        }
                    }
                    
                    if (lastBrace === -1) {
                        throw new Error('Incomplete JSON object in stdout');
                    }
                    
                    const jsonStr = cleanedStdout.substring(firstBrace, lastBrace + 1);
                    const response = JSON.parse(jsonStr);
                    resolve(response);
                } catch (error) {
                    console.error('Failed to parse document response:', error.message);
                    console.error('Raw stdout length:', stdout.length);
                    console.error('Raw stdout (first 2000 chars):', stdout.substring(0, 2000));
                    console.error('Raw stderr:', stderr.substring(0, 500));
                    reject(new Error('Invalid response from document service'));
                }
            });
        });
    }

    /**
     * Find relevant documents based on semantic similarity to a query
     */
    async findRelevantDocuments(query, topK = 3) {
        return new Promise((resolve, reject) => {
            const pythonProcess = spawn(this.pythonPath, [
                path.join(__dirname, '..', '..', 'src', 'api', 'document_api.py'),
                '--action', 'find-relevant',
                '--query', query,
                '--top-k', topK.toString()
            ]);

            let stdout = '';
            let stderr = '';

            pythonProcess.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            pythonProcess.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            pythonProcess.on('close', (code) => {
                if (code !== 0) {
                    console.error('Find relevant documents error - stderr:', stderr);
                    console.error('Find relevant documents error - stdout:', stdout);
                    reject(new Error(`Document service error: ${stderr || 'Unknown error'}`));
                    return;
                }
                try {
                    // Extract JSON from stdout (handle debug output that might be printed)
                    let cleanedStdout = stdout.trim();
                    
                    // Find JSON object by finding first { and matching closing }
                    const firstBrace = cleanedStdout.indexOf('{');
                    if (firstBrace === -1) {
                        throw new Error('No JSON object found in stdout');
                    }
                    
                    // Find the matching closing brace by counting braces
                    let braceCount = 0;
                    let lastBrace = -1;
                    for (let i = firstBrace; i < cleanedStdout.length; i++) {
                        if (cleanedStdout[i] === '{') braceCount++;
                        if (cleanedStdout[i] === '}') {
                            braceCount--;
                            if (braceCount === 0) {
                                lastBrace = i;
                                break;
                            }
                        }
                    }
                    
                    if (lastBrace === -1) {
                        throw new Error('Incomplete JSON object in stdout');
                    }
                    
                    const jsonStr = cleanedStdout.substring(firstBrace, lastBrace + 1);
                    const response = JSON.parse(jsonStr);
                    resolve(response);
                } catch (error) {
                    console.error('Failed to parse find relevant documents response:', error.message);
                    console.error('Raw stdout length:', stdout.length);
                    console.error('Raw stdout (first 2000 chars):', stdout.substring(0, 2000));
                    console.error('Raw stderr:', stderr.substring(0, 500));
                    reject(new Error('Invalid response from document service'));
                }
            });
        });
    }

    /**
     * Get chunks for a specific document
     */
    async getDocumentChunks(docId, limit = 100) {
        return new Promise((resolve, reject) => {
            const pythonProcess = spawn(this.pythonPath, [
                path.join(__dirname, '..', '..', 'src', 'api', 'document_api.py'),
                '--action', 'get-chunks',
                '--doc-id', docId,
                '--limit', limit.toString()
            ]);

            let stdout = '';
            let stderr = '';

            pythonProcess.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            pythonProcess.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            pythonProcess.on('close', (code) => {
                if (code !== 0) {
                    console.error('Document chunks error - stderr:', stderr);
                    console.error('Document chunks error - stdout:', stdout);
                    reject(new Error(`Document service error: ${stderr || 'Unknown error'}`));
                    return;
                }
                try {
                    // Extract JSON from stdout (handle debug output that might be printed)
                    let cleanedStdout = stdout.trim();
                    
                    // Try regex approach first (more robust for large JSON with embedded braces)
                    const jsonMatch = cleanedStdout.match(/\{[\s\S]*\}/);
                    if (jsonMatch) {
                        try {
                            const response = JSON.parse(jsonMatch[0]);
                            resolve(response);
                            return;
                        } catch (parseError) {
                            // If regex match fails, try the brace-counting method
                            console.warn('Regex JSON parse failed, trying brace-counting method:', parseError.message);
                        }
                    }
                    
                    // Fallback: Find JSON object by finding first { and matching closing }
                    // This method accounts for braces inside JSON strings
                    const firstBrace = cleanedStdout.indexOf('{');
                    if (firstBrace === -1) {
                        throw new Error('No JSON object found in stdout');
                    }
                    
                    // Use a more robust method: find the last complete JSON object
                    // Look for the last line that starts with { and try to parse from there
                    const lines = cleanedStdout.split('\n');
                    let jsonStartLine = -1;
                    for (let i = lines.length - 1; i >= 0; i--) {
                        if (lines[i].trim().startsWith('{')) {
                            jsonStartLine = i;
                            break;
                        }
                    }
                    
                    if (jsonStartLine !== -1) {
                        // Try parsing from this line onwards
                        const jsonCandidate = lines.slice(jsonStartLine).join('\n');
                        try {
                            const response = JSON.parse(jsonCandidate);
                            resolve(response);
                            return;
                        } catch (e) {
                            // Fall through to brace counting
                        }
                    }
                    
                    // Last resort: brace counting (may fail with embedded braces in strings)
                    let braceCount = 0;
                    let inString = false;
                    let escapeNext = false;
                    let lastBrace = -1;
                    
                    for (let i = firstBrace; i < cleanedStdout.length; i++) {
                        const char = cleanedStdout[i];
                        
                        if (escapeNext) {
                            escapeNext = false;
                            continue;
                        }
                        
                        if (char === '\\') {
                            escapeNext = true;
                            continue;
                        }
                        
                        if (char === '"' && !escapeNext) {
                            inString = !inString;
                            continue;
                        }
                        
                        if (!inString) {
                            if (char === '{') braceCount++;
                            if (char === '}') {
                                braceCount--;
                                if (braceCount === 0) {
                                    lastBrace = i;
                                    break;
                                }
                            }
                        }
                    }
                    
                    if (lastBrace === -1) {
                        throw new Error('Incomplete JSON object in stdout');
                    }
                    
                    const jsonStr = cleanedStdout.substring(firstBrace, lastBrace + 1);
                    const response = JSON.parse(jsonStr);
                    resolve(response);
                } catch (error) {
                    console.error('Failed to parse document chunks response:', error.message);
                    console.error('Raw stdout length:', stdout.length);
                    console.error('Raw stdout (first 2000 chars):', stdout.substring(0, 2000));
                    console.error('Raw stderr:', stderr.substring(0, 500));
                    
                    // For very large responses, try to return a limited subset
                    if (stdout.length > 100000) {
                        console.warn('Response too large, attempting to extract partial chunks');
                        try {
                            // Try to extract just the structure without all chunk text
                            const partialMatch = stdout.match(/\{"chunks":\s*\[/);
                            if (partialMatch) {
                                // Return error with suggestion to limit chunks
                                reject(new Error('Document chunks response too large. Consider limiting chunk count in document_api.py'));
                                return;
                            }
                        } catch (e) {
                            // Ignore
                        }
                    }
                    
                    reject(new Error('Invalid response from document service'));
                }
            });
        });
    }
}

module.exports = DocumentService;

