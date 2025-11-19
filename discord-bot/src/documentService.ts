import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import { fileURLToPath } from 'url';

// Get __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface DocumentUploadResponse {
    success?: boolean;
    doc_id?: string;
    chunks?: number;
    error?: string;
    [key: string]: unknown;
}

interface Document {
    id: string;
    file_name: string;
    uploaded_by?: string;
    uploaded_at?: string;
    chunk_count?: number;
    [key: string]: unknown;
}

interface AllDocumentsResponse {
    documents?: Document[];
    [key: string]: unknown;
}

interface DocumentChunk {
    text?: string;
    [key: string]: unknown;
}

interface DocumentChunksResponse {
    chunks?: DocumentChunk[];
    [key: string]: unknown;
}

interface FindRelevantResponse {
    documents?: Document[];
    [key: string]: unknown;
}

class DocumentService {
    private pythonPath: string;

    constructor() {
        this.pythonPath = process.env.PYTHON_PATH || 'python';
    }

    /**
     * Extract JSON from stdout, handling debug output
     */
    private extractJSON(stdout: string): unknown {
        const cleanedStdout = stdout.trim();
        
        // Try regex approach first (more robust for large JSON with embedded braces)
        const jsonMatch = cleanedStdout.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
            try {
                return JSON.parse(jsonMatch[0]);
            } catch (parseError) {
                // If regex match fails, try the brace-counting method
                console.warn('Regex JSON parse failed, trying brace-counting method:', (parseError as Error).message);
            }
        }
        
        // Fallback: Find JSON object by finding first { and matching closing }
        const firstBrace = cleanedStdout.indexOf('{');
        if (firstBrace === -1) {
            throw new Error('No JSON object found in stdout');
        }
        
        // Use a more robust method: find the last complete JSON object
        const lines = cleanedStdout.split('\n');
        let jsonStartLine = -1;
        for (let i = lines.length - 1; i >= 0; i--) {
            if (lines[i].trim().startsWith('{')) {
                jsonStartLine = i;
                break;
            }
        }
        
        if (jsonStartLine !== -1) {
            const jsonCandidate = lines.slice(jsonStartLine).join('\n');
            try {
                return JSON.parse(jsonCandidate);
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
        return JSON.parse(jsonStr);
    }

    /**
     * Upload and process a document
     */
    async uploadDocument(userId: string, filePath: string, fileName: string): Promise<DocumentUploadResponse> {
        return new Promise((resolve, reject) => {
            const dirname = __dirname;
            
            const pythonProcess: ChildProcess = spawn(this.pythonPath, [
                path.join(dirname, '..', '..', 'src', 'api', 'document_api.py'),
                '--action', 'upload',
                '--user-id', userId,
                '--file-path', filePath,
                '--file-name', fileName
            ], {
                stdio: ['pipe', 'pipe', 'pipe']
            });

            let stdout = '';
            let stderr = '';

            pythonProcess.stdout?.on('data', (data: Buffer) => {
                stdout += data.toString();
            });

            pythonProcess.stderr?.on('data', (data: Buffer) => {
                stderr += data.toString();
            });

            pythonProcess.on('close', (code: number | null) => {
                if (code !== 0) {
                    console.error('Document upload error - stderr:', stderr);
                    console.error('Document upload error - stdout:', stdout);
                    reject(new Error(`Document service error: ${stderr || 'Unknown error'}`));
                    return;
                }
                try {
                    const response = this.extractJSON(stdout) as DocumentUploadResponse;
                    resolve(response);
                } catch (error) {
                    const err = error as Error;
                    console.error('Failed to parse document upload response:', err.message);
                    console.error('Raw stdout length:', stdout.length);
                    console.error('Raw stdout (first 2000 chars):', stdout.substring(0, 2000));
                    console.error('Raw stderr:', stderr.substring(0, 500));
                    reject(new Error('Invalid response from document service'));
                }
            });

            pythonProcess.on('error', (error: Error) => {
                reject(new Error(`Failed to start document service: ${error.message}`));
            });
        });
    }

    /**
     * Get all shared documents
     */
    async getAllDocuments(): Promise<AllDocumentsResponse> {
        return new Promise((resolve, reject) => {
            const dirname = __dirname;
            
            const pythonProcess: ChildProcess = spawn(this.pythonPath, [
                path.join(dirname, '..', '..', 'src', 'api', 'document_api.py'),
                '--action', 'list'
            ]);

            let stdout = '';
            let stderr = '';

            pythonProcess.stdout?.on('data', (data: Buffer) => {
                stdout += data.toString();
            });

            pythonProcess.stderr?.on('data', (data: Buffer) => {
                stderr += data.toString();
            });

            pythonProcess.on('close', (code: number | null) => {
                if (code !== 0) {
                    console.error('Document service error - stderr:', stderr);
                    console.error('Document service error - stdout:', stdout);
                    reject(new Error(`Document service error: ${stderr || 'Unknown error'}`));
                    return;
                }
                try {
                    const response = this.extractJSON(stdout) as AllDocumentsResponse;
                    resolve(response);
                } catch (error) {
                    const err = error as Error;
                    console.error('Failed to parse document response:', err.message);
                    console.error('Raw stdout length:', stdout.length);
                    console.error('Raw stdout (first 2000 chars):', stdout.substring(0, 2000));
                    console.error('Raw stderr:', stderr.substring(0, 500));
                    reject(new Error('Invalid response from document service'));
                }
            });

            pythonProcess.on('error', (error: Error) => {
                reject(new Error(`Failed to start document service: ${error.message}`));
            });
        });
    }

    /**
     * Find relevant documents based on semantic similarity to a query
     */
    async findRelevantDocuments(query: string, topK: number = 3): Promise<FindRelevantResponse> {
        return new Promise((resolve, reject) => {
            const dirname = __dirname;
            
            const pythonProcess: ChildProcess = spawn(this.pythonPath, [
                path.join(dirname, '..', '..', 'src', 'api', 'document_api.py'),
                '--action', 'find-relevant',
                '--query', query,
                '--top-k', topK.toString()
            ]);

            let stdout = '';
            let stderr = '';

            pythonProcess.stdout?.on('data', (data: Buffer) => {
                stdout += data.toString();
            });

            pythonProcess.stderr?.on('data', (data: Buffer) => {
                stderr += data.toString();
            });

            pythonProcess.on('close', (code: number | null) => {
                if (code !== 0) {
                    console.error('Find relevant documents error - stderr:', stderr);
                    console.error('Find relevant documents error - stdout:', stdout);
                    reject(new Error(`Document service error: ${stderr || 'Unknown error'}`));
                    return;
                }
                try {
                    const response = this.extractJSON(stdout) as FindRelevantResponse;
                    resolve(response);
                } catch (error) {
                    const err = error as Error;
                    console.error('Failed to parse find relevant documents response:', err.message);
                    console.error('Raw stdout length:', stdout.length);
                    console.error('Raw stdout (first 2000 chars):', stdout.substring(0, 2000));
                    console.error('Raw stderr:', stderr.substring(0, 500));
                    reject(new Error('Invalid response from document service'));
                }
            });

            pythonProcess.on('error', (error: Error) => {
                reject(new Error(`Failed to start document service: ${error.message}`));
            });
        });
    }

    /**
     * Get chunks for a specific document
     */
    async getDocumentChunks(docId: string, limit: number = 100): Promise<DocumentChunksResponse> {
        return new Promise((resolve, reject) => {
            const dirname = __dirname;
            
            const pythonProcess: ChildProcess = spawn(this.pythonPath, [
                path.join(dirname, '..', '..', 'src', 'api', 'document_api.py'),
                '--action', 'get-chunks',
                '--doc-id', docId,
                '--limit', limit.toString()
            ]);

            let stdout = '';
            let stderr = '';

            pythonProcess.stdout?.on('data', (data: Buffer) => {
                stdout += data.toString();
            });

            pythonProcess.stderr?.on('data', (data: Buffer) => {
                stderr += data.toString();
            });

            pythonProcess.on('close', (code: number | null) => {
                if (code !== 0) {
                    console.error('Document chunks error - stderr:', stderr);
                    console.error('Document chunks error - stdout:', stdout);
                    reject(new Error(`Document service error: ${stderr || 'Unknown error'}`));
                    return;
                }
                try {
                    const response = this.extractJSON(stdout) as DocumentChunksResponse;
                    resolve(response);
                } catch (error) {
                    const err = error as Error;
                    console.error('Failed to parse document chunks response:', err.message);
                    console.error('Raw stdout length:', stdout.length);
                    console.error('Raw stdout (first 2000 chars):', stdout.substring(0, 2000));
                    console.error('Raw stderr:', stderr.substring(0, 500));
                    
                    // For very large responses, try to return a limited subset
                    if (stdout.length > 100000) {
                        console.warn('Response too large, attempting to extract partial chunks');
                        try {
                            const partialMatch = stdout.match(/\{"chunks":\s*\[/);
                            if (partialMatch) {
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

            pythonProcess.on('error', (error: Error) => {
                reject(new Error(`Failed to start document service: ${error.message}`));
            });
        });
    }
}

export default DocumentService;

