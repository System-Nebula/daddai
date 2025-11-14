const { spawn } = require('child_process');
const path = require('path');

class MemoryService {
    constructor() {
        this.pythonPath = process.env.PYTHON_PATH || 'python';
    }

    /**
     * Store a memory for a channel (channel-based memories)
     */
    async storeMemory(channelId, content, memoryType = 'conversation', metadata = {}, channelName = null, userId = null, username = null, mentionedUserId = null) {
        return new Promise((resolve, reject) => {
            const args = [
                path.join(__dirname, '..', '..', 'src', 'api', 'memory_api.py'),
                '--action', 'store',
                '--channel-id', channelId,
                '--content', content,
                '--memory-type', memoryType,
                '--metadata', JSON.stringify(metadata)
            ];
            
            // Add channel name if provided
            if (channelName) {
                args.push('--channel-name', channelName);
            }
            
            // Add user info if provided
            if (userId) {
                args.push('--user-id', userId);
            }
            if (username) {
                args.push('--username', username);
            }
            if (mentionedUserId) {
                args.push('--mentioned-user-id', mentionedUserId);
            }
            
            const pythonProcess = spawn(this.pythonPath, args);

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
                    console.error('Memory service error - stderr:', stderr);
                    console.error('Memory service error - stdout:', stdout);
                    reject(new Error(`Memory service error: ${stderr || 'Unknown error'}`));
                    return;
                }
                try {
                    // Extract JSON from stdout (handle debug output)
                    const jsonMatch = stdout.match(/\{[\s\S]*\}/);
                    if (jsonMatch) {
                        resolve(JSON.parse(jsonMatch[0]));
                    } else {
                        resolve(JSON.parse(stdout.trim()));
                    }
                } catch (error) {
                    console.error('Failed to parse memory response:', stdout);
                    // Still resolve as success if we can't parse (might be empty)
                    resolve({ success: true, raw_output: stdout });
                }
            });
        });
    }

    /**
     * Get channel memories (for admin view)
     * Can search by channelId or channelName
     */
    async getChannelMemories(channelId = null, limit = 100, channelName = null) {
        return new Promise((resolve, reject) => {
            const args = [
                path.join(__dirname, '..', '..', 'src', 'api', 'memory_api.py'),
                '--action', 'get',
                '--limit', limit.toString()
            ];
            
            // Add identifier (prefer channel ID, fallback to channel name)
            if (channelId) {
                args.push('--channel-id', channelId);
            } else if (channelName) {
                args.push('--channel-name', channelName);
            } else {
                reject(new Error('Must provide channelId or channelName'));
                return;
            }
            
            const pythonProcess = spawn(this.pythonPath, args);

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
                    reject(new Error(`Memory service error: ${stderr}`));
                    return;
                }
                try {
                    resolve(JSON.parse(stdout));
                } catch (error) {
                    reject(new Error('Invalid response from memory service'));
                }
            });
        });
    }

    /**
     * Get all channels with memory counts (for admin)
     */
    async getAllChannels() {
        return new Promise((resolve, reject) => {
            const pythonProcess = spawn(this.pythonPath, [
                path.join(__dirname, '..', '..', 'src', 'api', 'memory_api.py'),
                '--action', 'list-channels'
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
                    console.error('Memory service error - stderr:', stderr);
                    console.error('Memory service error - stdout:', stdout);
                    reject(new Error(`Memory service error: ${stderr || 'Unknown error'}`));
                    return;
                }
                try {
                    // Extract JSON from stdout (handle debug output)
                    const jsonMatch = stdout.match(/\{[\s\S]*\}/);
                    if (jsonMatch) {
                        resolve(JSON.parse(jsonMatch[0]));
                    } else {
                        resolve(JSON.parse(stdout.trim()));
                    }
                } catch (error) {
                    console.error('Failed to parse memory response:', stdout);
                    reject(new Error('Invalid response from memory service'));
                }
            });
        });
    }

    /**
     * Get relevant memories for a channel based on a query (semantic search)
     */
    async getUserMemories(channelId, query, topK = 5, mentionedUserId = null) {
        return new Promise((resolve, reject) => {
            const args = [
                path.join(__dirname, '..', '..', 'src', 'api', 'memory_api.py'),
                '--action', 'search',
                '--channel-id', channelId,
                '--query', query,
                '--top-k', topK.toString()
            ];
            
            // Add mentioned user ID if provided (for boosting relevant memories)
            if (mentionedUserId) {
                args.push('--mentioned-user-id', mentionedUserId);
            }
            
            const pythonProcess = spawn(this.pythonPath, args);

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
                    console.error('Memory search error - stderr:', stderr);
                    console.error('Memory search error - stdout:', stdout);
                    reject(new Error(`Memory search error: ${stderr || 'Unknown error'}`));
                    return;
                }
                try {
                    // Extract JSON from stdout (handle debug output)
                    const jsonMatch = stdout.match(/\{[\s\S]*\}/);
                    if (jsonMatch) {
                        const response = JSON.parse(jsonMatch[0]);
                        resolve(response.memories || []);
                    } else {
                        resolve([]);
                    }
                } catch (error) {
                    console.error('Failed to parse memory search response:', stdout);
                    resolve([]); // Return empty array on parse error
                }
            });
            
            pythonProcess.on('error', (error) => {
                reject(new Error(`Failed to start memory search service: ${error.message}`));
            });
        });
    }

    /**
     * Get all memories across all users (for admin view)
     */
    async getAllMemories(limit = 1000) {
        return new Promise((resolve, reject) => {
            const args = [
                path.join(__dirname, '..', '..', 'src', 'api', 'memory_api.py'),
                '--action', 'get-all',
                '--limit', limit.toString()
            ];
            
            const pythonProcess = spawn(this.pythonPath, args);
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
                    console.error('Memory service error - stderr:', stderr);
                    console.error('Memory service error - stdout:', stdout);
                    reject(new Error(`Memory service error: ${stderr || 'Unknown error'}`));
                    return;
                }
                
                try {
                    // Clean stdout - remove any non-JSON content
                    let cleanedStdout = stdout.trim();
                    
                    console.log(`getAllMemories stdout length: ${cleanedStdout.length}`);
                    console.log(`getAllMemories stdout preview: ${cleanedStdout.substring(0, 200)}`);
                    
                    // Try to parse the entire stdout as JSON first
                    let response;
                    try {
                        response = JSON.parse(cleanedStdout);
                        console.log(`getAllMemories parsed directly: ${response.memories?.length || 0} memories found`);
                        resolve(response);
                        return;
                    } catch (directParseError) {
                        // If direct parse fails, try to extract JSON more intelligently
                        console.log('Direct parse failed, trying to extract JSON...');
                    }
                    
                    // Find JSON object by finding first { and matching closing }
                    const firstBrace = cleanedStdout.indexOf('{');
                    if (firstBrace === -1) {
                        console.error('No JSON object found - stdout:', cleanedStdout.substring(0, 500));
                        throw new Error('No JSON object found in stdout');
                    }
                    
                    // Find the matching closing brace by counting braces and brackets
                    // Need to handle nested objects and arrays
                    let braceCount = 0;
                    let bracketCount = 0;
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
                        
                        if (inString) {
                            continue;
                        }
                        
                        if (char === '{') braceCount++;
                        if (char === '}') {
                            braceCount--;
                            if (braceCount === 0 && bracketCount === 0) {
                                lastBrace = i;
                                break;
                            }
                        }
                        if (char === '[') bracketCount++;
                        if (char === ']') bracketCount--;
                    }
                    
                    if (lastBrace === -1) {
                        console.error('Incomplete JSON - firstBrace:', firstBrace, 'stdout length:', cleanedStdout.length);
                        console.error('Brace count at end:', braceCount, 'Bracket count:', bracketCount);
                        // Try to parse what we have anyway (might be valid JSON with trailing content)
                        const partialJson = cleanedStdout.substring(firstBrace);
                        try {
                            response = JSON.parse(partialJson);
                            console.log(`getAllMemories parsed partial JSON: ${response.memories?.length || 0} memories found`);
                            resolve(response);
                            return;
                        } catch (partialError) {
                            throw new Error('Incomplete JSON object in stdout');
                        }
                    }
                    
                    const jsonStr = cleanedStdout.substring(firstBrace, lastBrace + 1);
                    console.log(`Extracted JSON length: ${jsonStr.length}`);
                    response = JSON.parse(jsonStr);
                    console.log(`getAllMemories parsed: ${response.memories?.length || 0} memories found`);
                    console.log(`Response keys: ${Object.keys(response).join(', ')}`);
                    resolve(response);
                } catch (error) {
                    console.error('Failed to parse memory response:', error.message);
                    console.error('Error stack:', error.stack);
                    console.error('Raw stdout length:', stdout.length);
                    console.error('Raw stdout (first 2000 chars):', stdout.substring(0, 2000));
                    console.error('Raw stderr:', stderr.substring(0, 500));
                    
                    // If we can't parse, return empty rather than failing
                    console.warn('Returning empty memories due to parse error');
                    resolve({ memories: [], count: 0 });
                }
            });
            
            pythonProcess.on('error', (error) => {
                reject(new Error(`Failed to start memory service: ${error.message}`));
            });
        });
    }
}

module.exports = MemoryService;

