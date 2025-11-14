const express = require('express');
const path = require('path');
const MemoryService = require('./memoryService');
const DocumentService = require('./documentService');

class WebServer {
    constructor(memoryService, documentService, port = 3000) {
        this.app = express();
        this.port = port;
        this.memoryService = memoryService;
        this.documentService = documentService;
        
        // Cache for frequently accessed data
        this.cache = {
            channels: null,
            channelsTimestamp: 0,
            documents: null,
            documentsTimestamp: 0
        };
        this.cacheTTL = 30000; // 30 seconds cache
        
        this.setupRoutes();
    }
    
    getCachedChannels() {
        const now = Date.now();
        if (this.cache.channels && (now - this.cache.channelsTimestamp) < this.cacheTTL) {
            return Promise.resolve(this.cache.channels);
        }
        return this.memoryService.getAllChannels().then(channels => {
            this.cache.channels = channels;
            this.cache.channelsTimestamp = now;
            return channels;
        });
    }
    
    getCachedDocuments() {
        const now = Date.now();
        if (this.cache.documents && (now - this.cache.documentsTimestamp) < this.cacheTTL) {
            return Promise.resolve(this.cache.documents);
        }
        return this.documentService.getAllDocuments().then(docs => {
            this.cache.documents = docs;
            this.cache.documentsTimestamp = now;
            return docs;
        });
    }

    setupRoutes() {
        // Add request logging middleware
        this.app.use((req, res, next) => {
            console.log(`[WebServer] ${req.method} ${req.path}`);
            next();
        });
        
        // API routes MUST come before static file serving
        // Otherwise static file middleware might intercept API requests
        
        // API endpoint to get all channels with memories (cached)
        this.app.get('/api/channels', async (req, res) => {
            try {
                const channels = await this.getCachedChannels();
                const channelList = channels.channels || channels;
                res.json({ channels: channelList });
            } catch (error) {
                console.error('Error fetching channels:', error);
                res.status(500).json({ error: 'Failed to fetch channels', details: error.message });
            }
        });
        
        // Keep /api/users for backward compatibility (returns channels)
        this.app.get('/api/users', async (req, res) => {
            try {
                const channels = await this.getCachedChannels();
                const channelList = channels.channels || channels;
                res.json({ users: channelList }); // Return as "users" for backward compat
            } catch (error) {
                console.error('Error fetching channels:', error);
                res.status(500).json({ error: 'Failed to fetch channels', details: error.message });
            }
        });

        // API endpoint to get all memories across all users (with pagination)
        // MUST come before parameterized routes like /api/memories/:userId
        this.app.get('/api/memories/all', async (req, res) => {
            try {
                const limit = parseInt(req.query.limit) || 25; // Reduced to 25 for faster initial load
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
                const paginatedMemories = allMemories.slice(0, limit); // First 'limit' items
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
                    limit: limit
                });
            } catch (error) {
                console.error('[API] Error fetching all memories:', error.message);
                res.status(500).json({ error: 'Failed to fetch all memories', details: error.message });
            }
        });

        // API endpoint to get memories for a specific channel
        // Must come AFTER /api/memories/all to avoid route conflicts
        this.app.get('/api/memories/:channelId', async (req, res) => {
            try {
                const { channelId } = req.params;
                const limit = parseInt(req.query.limit) || 100;
                const memories = await this.memoryService.getChannelMemories(channelId, limit);
                res.json(memories);
            } catch (error) {
                console.error('Error fetching memories:', error);
                res.status(500).json({ error: 'Failed to fetch memories' });
            }
        });

        // API endpoint to search memories by channel name
        this.app.get('/api/memories/search/:channelName', async (req, res) => {
            try {
                const { channelName } = req.params;
                const limit = parseInt(req.query.limit) || 100;
                const memories = await this.memoryService.getChannelMemories(null, limit, channelName);
                res.json(memories);
            } catch (error) {
                console.error('Error searching memories:', error);
                res.status(500).json({ error: 'Failed to search memories' });
            }
        });

        // API endpoint to get all shared documents (cached)
        this.app.get('/api/documents', async (req, res) => {
            try {
                const result = await this.getCachedDocuments();
                const documents = result.documents || result || [];
                res.json({ documents: documents, count: documents.length });
            } catch (error) {
                console.error('Error fetching documents:', error);
                res.status(500).json({ error: 'Failed to fetch documents', details: error.message });
            }
        });

        // API endpoint to get chunks for a specific document
        this.app.get('/api/documents/:docId/chunks', async (req, res) => {
            console.log(`[API] /api/documents/${req.params.docId}/chunks endpoint hit`);
            try {
                const result = await this.documentService.getDocumentChunks(req.params.docId);
                res.json(result);
            } catch (error) {
                console.error('Error fetching document chunks:', error);
                res.status(500).json({ error: 'Failed to fetch document chunks', details: error.message });
            }
        });

        // Test endpoint
        this.app.get('/api/test', (req, res) => {
            console.log('[WebServer] Test endpoint hit!');
            res.json({ status: 'ok', message: 'Web server is working' });
        });
        
        // Serve static files AFTER API routes
        this.app.use(express.static(path.join(__dirname, '..', 'public')));
        
        // Serve main page (fallback if static file doesn't exist)
        this.app.get('/', (req, res) => {
            console.log('[WebServer] Serving index.html');
            res.sendFile(path.join(__dirname, '..', 'public', 'index.html'));
        });
    }

    start() {
        this.app.listen(this.port, () => {
            console.log(`🌐 Web interface running at http://localhost:${this.port}`);
            console.log(`🌐 Test endpoint: http://localhost:${this.port}/api/test`);
        });
        
        // Add error handler
        this.app.on('error', (error) => {
            console.error('[WebServer] Server error:', error);
        });
    }
}

module.exports = WebServer;

