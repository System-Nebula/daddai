const express = require('express');
const path = require('path');
const MemoryService = require('./memoryService');
const DocumentService = require('./documentService');

/**
 * Professional Web Server for GopherBot Dashboard
 * Features: Caching, Error Handling, Request Logging, CORS Support
 */
class WebServer {
    constructor(memoryService, documentService, port = 3000) {
        this.app = express();
        this.port = port;
        this.memoryService = memoryService;
        this.documentService = documentService;
        
        // Enhanced cache configuration
        this.cache = {
            channels: null,
            channelsTimestamp: 0,
            documents: null,
            documentsTimestamp: 0
        };
        this.cacheTTL = 30000; // 30 seconds cache
        
        this.setupMiddleware();
        this.setupRoutes();
        this.setupErrorHandling();
    }
    
    /**
     * Setup middleware for request processing
     */
    setupMiddleware() {
        // Add compression middleware for faster responses
        const compression = require('compression');
        this.app.use(compression({ level: 6, threshold: 1024 }));
        
        // JSON body parser
        this.app.use(express.json());
        
        // Request logging middleware
        this.app.use((req, res, next) => {
            const start = Date.now();
            const timestamp = new Date().toISOString();
            
            // Log request
            console.log(`[${timestamp}] ${req.method} ${req.path} - ${req.ip}`);
            
            // Log response time
            res.on('finish', () => {
                const duration = Date.now() - start;
                const statusColor = res.statusCode >= 400 ? '\x1b[31m' : '\x1b[32m';
                console.log(`[${timestamp}] ${statusColor}${res.statusCode}\x1b[0m ${req.method} ${req.path} - ${duration}ms`);
            });
            
            next();
        });
        
        // CORS headers (if needed for cross-origin requests)
        this.app.use((req, res, next) => {
            res.header('Access-Control-Allow-Origin', '*');
            res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
            res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization');
            
            if (req.method === 'OPTIONS') {
                return res.sendStatus(200);
            }
            
            next();
        });
        
        // Security headers
        this.app.use((req, res, next) => {
            res.setHeader('X-Content-Type-Options', 'nosniff');
            res.setHeader('X-Frame-Options', 'DENY');
            res.setHeader('X-XSS-Protection', '1; mode=block');
            next();
        });
    }
    
    /**
     * Get cached channels or fetch fresh data
     */
    async getCachedChannels() {
        const now = Date.now();
        if (this.cache.channels && (now - this.cache.channelsTimestamp) < this.cacheTTL) {
            return Promise.resolve(this.cache.channels);
        }
        
        try {
            const channels = await this.memoryService.getAllChannels();
            this.cache.channels = channels;
            this.cache.channelsTimestamp = now;
            return channels;
        } catch (error) {
            console.error('[Cache] Error fetching channels:', error);
            // Return stale cache if available, otherwise throw
            if (this.cache.channels) {
                console.warn('[Cache] Returning stale channels cache');
                return this.cache.channels;
            }
            throw error;
        }
    }
    
    /**
     * Get cached documents or fetch fresh data
     */
    async getCachedDocuments() {
        const now = Date.now();
        if (this.cache.documents && (now - this.cache.documentsTimestamp) < this.cacheTTL) {
            return Promise.resolve(this.cache.documents);
        }
        
        try {
            const documents = await this.documentService.getAllDocuments();
            this.cache.documents = documents;
            this.cache.documentsTimestamp = now;
            return documents;
        } catch (error) {
            console.error('[Cache] Error fetching documents:', error);
            // Return stale cache if available, otherwise throw
            if (this.cache.documents) {
                console.warn('[Cache] Returning stale documents cache');
                return this.cache.documents;
            }
            throw error;
        }
    }
    
    /**
     * Setup API routes
     */
    setupRoutes() {
        // Health check endpoint
        this.app.get('/api/health', (req, res) => {
            res.json({ 
                status: 'ok', 
                timestamp: new Date().toISOString(),
                uptime: process.uptime()
            });
        });
        
        // System status endpoint (Elasticsearch + Neo4j)
        this.app.get('/api/status', async (req, res) => {
            try {
                const { exec } = require('child_process');
                const { promisify } = require('util');
                const execAsync = promisify(exec);
                
                // Call Python status API
                // Use python3 on Unix, python on Windows
                const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
                const scriptPath = path.join(__dirname, '..', '..', 'src', 'api', 'system_status_api.py');
                const { stdout, stderr } = await execAsync(`${pythonCmd} "${scriptPath}"`, {
                    cwd: path.join(__dirname, '../..'),
                    timeout: 10000,
                    maxBuffer: 1024 * 1024 // 1MB buffer
                });
                
                if (stderr && !stdout) {
                    throw new Error(stderr);
                }
                
                const status = JSON.parse(stdout);
                res.json({
                    ...status,
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching system status:', error);
                res.status(500).json({ 
                    error: 'Failed to fetch system status',
                    details: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        });
        
        // API endpoint to get all channels with memories (cached)
        this.app.get('/api/channels', async (req, res) => {
            try {
                const channels = await this.getCachedChannels();
                const channelList = channels.channels || channels;
                res.json({ 
                    channels: channelList,
                    cached: this.isCacheValid('channels'),
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching channels:', error);
                res.status(500).json({ 
                    error: 'Failed to fetch channels', 
                    details: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        });
        
        // Keep /api/users for backward compatibility (returns channels)
        this.app.get('/api/users', async (req, res) => {
            try {
                const channels = await this.getCachedChannels();
                const channelList = channels.channels || channels;
                res.json({ 
                    users: channelList, // Return as "users" for backward compat
                    cached: this.isCacheValid('channels'),
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching channels:', error);
                res.status(500).json({ 
                    error: 'Failed to fetch channels', 
                    details: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // API endpoint to get all memories across all users (with pagination)
        // MUST come before parameterized routes like /api/memories/:userId
        this.app.get('/api/memories/all', async (req, res) => {
            try {
                const limit = Math.min(parseInt(req.query.limit) || 25, 100); // Cap at 100 for safety
                const offset = parseInt(req.query.offset) || 0;
                const skip = parseInt(req.query.skip) || offset; // Support both offset and skip
                
                // Fetch enough to check if there are more (limit + 1 to detect hasMore)
                const fetchLimit = Math.min(limit + 1, 1000); // Cap at 1000 for safety
                const result = await this.memoryService.getAllMemories(fetchLimit + skip);
                
                // Handle response format
                let allMemories = [];
                if (result && result.memories && Array.isArray(result.memories)) {
                    allMemories = result.memories;
                } else if (Array.isArray(result)) {
                    allMemories = result;
                }
                
                // Apply pagination - get the slice we need
                const paginatedMemories = allMemories.slice(0, limit);
                const hasMore = allMemories.length > limit;
                
                // For total count, we'd need to fetch all, but that's slow
                // Instead, estimate: if we got limit+1, there might be more
                const estimatedTotal = hasMore ? skip + allMemories.length + 1 : skip + allMemories.length;
                
                res.json({
                    memories: paginatedMemories,
                    count: paginatedMemories.length,
                    total: estimatedTotal, // Estimated total
                    hasMore: hasMore,
                    offset: skip,
                    limit: limit,
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching all memories:', error.message);
                res.status(500).json({ 
                    error: 'Failed to fetch all memories', 
                    details: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // API endpoint to get memories for a specific channel
        // Must come AFTER /api/memories/all to avoid route conflicts
        this.app.get('/api/memories/:channelId', async (req, res) => {
            try {
                const { channelId } = req.params;
                const limit = Math.min(parseInt(req.query.limit) || 100, 500); // Cap at 500
                const memories = await this.memoryService.getChannelMemories(channelId, limit);
                res.json({
                    ...memories,
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching memories:', error);
                res.status(500).json({ 
                    error: 'Failed to fetch memories',
                    details: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // API endpoint to search memories by channel name
        this.app.get('/api/memories/search/:channelName', async (req, res) => {
            try {
                const { channelName } = req.params;
                const limit = Math.min(parseInt(req.query.limit) || 100, 500); // Cap at 500
                const memories = await this.memoryService.getChannelMemories(null, limit, channelName);
                res.json({
                    ...memories,
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error searching memories:', error);
                res.status(500).json({ 
                    error: 'Failed to search memories',
                    details: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // API endpoint to get all shared documents (cached)
        this.app.get('/api/documents', async (req, res) => {
            try {
                const result = await this.getCachedDocuments();
                const documents = result.documents || result || [];
                res.json({ 
                    documents: documents, 
                    count: documents.length,
                    cached: this.isCacheValid('documents'),
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching documents:', error);
                res.status(500).json({ 
                    error: 'Failed to fetch documents', 
                    details: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // API endpoint to get chunks for a specific document
        this.app.get('/api/documents/:docId/chunks', async (req, res) => {
            const { docId } = req.params;
            console.log(`[API] /api/documents/${docId}/chunks endpoint hit`);
            
            if (!docId || docId === 'undefined') {
                return res.status(400).json({ 
                    error: 'Invalid document ID',
                    timestamp: new Date().toISOString()
                });
            }
            
            try {
                const result = await this.documentService.getDocumentChunks(docId);
                res.json({
                    ...result,
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching document chunks:', error);
                res.status(500).json({ 
                    error: 'Failed to fetch document chunks', 
                    details: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // API endpoint to search documents in specific store
        this.app.get('/api/search/documents', async (req, res) => {
            try {
                const { query, store, top_k, doc_id, doc_filename } = req.query;
                
                if (!query) {
                    return res.status(400).json({ 
                        error: 'Query parameter is required',
                        timestamp: new Date().toISOString()
                    });
                }
                
                if (!store || !['elasticsearch', 'neo4j', 'both'].includes(store)) {
                    return res.status(400).json({ 
                        error: 'Store parameter must be "elasticsearch", "neo4j", or "both"',
                        timestamp: new Date().toISOString()
                    });
                }
                
                const { exec } = require('child_process');
                const { promisify } = require('util');
                const execAsync = promisify(exec);
                
                const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
                const args = [
                    path.join(__dirname, '..', '..', 'src', 'api', 'search_api.py'),
                    '--query', query,
                    '--store', store,
                    '--top-k', (top_k || 10).toString()
                ];
                
                if (doc_id) {
                    args.push('--doc-id', doc_id);
                }
                if (doc_filename) {
                    args.push('--doc-filename', doc_filename);
                }
                
                const { stdout, stderr } = await execAsync(`${pythonCmd} ${args.join(' ')}`, {
                    cwd: path.join(__dirname, '../..'),
                    timeout: 15000,
                    maxBuffer: 1024 * 1024 * 5 // 5MB buffer
                });
                
                if (stderr && !stdout) {
                    throw new Error(stderr);
                }
                
                // Extract JSON from stdout
                let cleanedStdout = stdout.trim();
                const firstBrace = cleanedStdout.indexOf('{');
                if (firstBrace !== -1) {
                    cleanedStdout = cleanedStdout.substring(firstBrace);
                }
                
                const result = JSON.parse(cleanedStdout);
                res.json({
                    ...result,
                    query: query,
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error searching documents:', error);
                res.status(500).json({ 
                    error: 'Failed to search documents',
                    details: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        });
        
        // Test endpoint
        this.app.get('/api/test', (req, res) => {
            res.json({ 
                status: 'ok', 
                message: 'Web server is working',
                timestamp: new Date().toISOString()
            });
        });
        
        // Serve static files AFTER API routes
        this.app.use(express.static(path.join(__dirname, '..', 'public'), {
            maxAge: '1d', // Cache static files for 1 day
            etag: true,
            lastModified: true
        }));
        
        // Serve main page (fallback if static file doesn't exist)
        this.app.get('/', (req, res) => {
            res.sendFile(path.join(__dirname, '..', 'public', 'index.html'));
        });
        
        // 404 handler for API routes
        this.app.use('/api/*', (req, res) => {
            res.status(404).json({ 
                error: 'API endpoint not found',
                path: req.path,
                timestamp: new Date().toISOString()
            });
        });
    }
    
    /**
     * Setup error handling middleware
     */
    setupErrorHandling() {
        // Global error handler
        this.app.use((err, req, res, next) => {
            console.error('[Error]', err);
            
            // Don't leak error details in production
            const isDevelopment = process.env.NODE_ENV === 'development';
            
            res.status(err.status || 500).json({
                error: err.message || 'Internal server error',
                details: isDevelopment ? err.stack : undefined,
                timestamp: new Date().toISOString()
            });
        });
        
        // Handle unhandled promise rejections
        process.on('unhandledRejection', (reason, promise) => {
            console.error('[Unhandled Rejection]', reason);
        });
        
        // Handle uncaught exceptions
        process.on('uncaughtException', (error) => {
            console.error('[Uncaught Exception]', error);
            // In production, you might want to gracefully shutdown
            if (process.env.NODE_ENV === 'production') {
                process.exit(1);
            }
        });
    }
    
    /**
     * Check if cache is still valid
     */
    isCacheValid(type) {
        const now = Date.now();
        if (type === 'channels') {
            return this.cache.channels && (now - this.cache.channelsTimestamp) < this.cacheTTL;
        } else if (type === 'documents') {
            return this.cache.documents && (now - this.cache.documentsTimestamp) < this.cacheTTL;
        }
        return false;
    }
    
    /**
     * Clear cache (useful for manual refresh)
     */
    clearCache(type = null) {
        if (type === 'channels' || type === null) {
            this.cache.channels = null;
            this.cache.channelsTimestamp = 0;
        }
        if (type === 'documents' || type === null) {
            this.cache.documents = null;
            this.cache.documentsTimestamp = 0;
        }
    }
    
    /**
     * Start the web server
     */
    start() {
        return new Promise((resolve, reject) => {
            try {
                this.server = this.app.listen(this.port, () => {
                    console.log(`🌐 Web interface running at http://localhost:${this.port}`);
                    console.log(`🌐 Health check: http://localhost:${this.port}/api/health`);
                    console.log(`🌐 Test endpoint: http://localhost:${this.port}/api/test`);
                    resolve();
                });
                
                // Handle server errors
                this.server.on('error', (error) => {
                    console.error('[WebServer] Server error:', error);
                    reject(error);
                });
            } catch (error) {
                console.error('[WebServer] Failed to start server:', error);
                reject(error);
            }
        });
    }
    
    /**
     * Stop the web server gracefully
     */
    stop() {
        return new Promise((resolve) => {
            if (this.server) {
                this.server.close(() => {
                    console.log('[WebServer] Server stopped');
                    resolve();
                });
            } else {
                resolve();
            }
        });
    }
}

module.exports = WebServer;
