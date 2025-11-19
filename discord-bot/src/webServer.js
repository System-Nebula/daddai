const express = require('express');
const path = require('path');
const MemoryService = require('./memoryService');
const DocumentService = require('./documentService');
const metricsCollector = require('./metrics');

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
            documentsTimestamp: 0,
            analytics: null,
            analyticsTimestamp: 0,
            status: null,
            statusTimestamp: 0
        };
        this.cacheTTL = 30000; // 30 seconds cache
        this.analyticsCacheTTL = 10000; // 10 seconds for analytics (more frequent updates)
        
        this.setupMiddleware();
        this.setupRoutes();
        this.setupErrorHandling();
    }
    
    /**
     * Setup middleware for request processing
     */
    setupMiddleware() {
        // Add observability middleware FIRST (if available)
        try {
            const { observabilityMiddleware } = require('./middleware/observabilityMiddleware');
            this.app.use(observabilityMiddleware);
        } catch (error) {
            // Observability middleware not available, continue without it
            console.warn('[WebServer] Observability middleware not available:', error.message);
        }
        
        // Add compression middleware for faster responses
        const compression = require('compression');
        this.app.use(compression({ level: 6, threshold: 1024 }));
        
        // JSON body parser
        this.app.use(express.json());
        
        // Request logging middleware (fallback if observability not available)
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
        // Health check endpoint (enhanced with performance metrics)
        this.app.get('/api/health', async (req, res) => {
            try {
                const { getHealthCheckData } = require('./utils/performanceMonitor');
                const healthData = await getHealthCheckData();
                res.json(healthData);
            } catch (error) {
                // Fallback to basic health check
                res.json({ 
                    status: 'ok', 
                    timestamp: new Date().toISOString(),
                    uptime: process.uptime()
                });
            }
        });
        
        // OpenTelemetry metrics endpoint (OTLP format)
        // Note: For Prometheus format, use /api/metrics endpoint which uses existing metrics.js
        this.app.get('/api/metrics/otel', async (req, res) => {
            try {
                const { getMeter } = require('./utils/observability');
                const meter = getMeter();
                // Return basic info - full metrics available via OTLP endpoint
                res.json({ 
                    message: 'OpenTelemetry metrics available via OTLP endpoint',
                    info: 'Set OTEL_EXPORTER_OTLP_METRICS_ENDPOINT to export metrics',
                    prometheus: 'Use /api/metrics for Prometheus format'
                });
            } catch (error) {
                res.status(503).json({ error: 'Metrics endpoint error', message: error.message });
            }
        });
        
        // System status endpoint (Elasticsearch + Neo4j) - Enhanced with caching
        this.app.get('/api/status', async (req, res) => {
            try {
                // Check cache first
                const now = Date.now();
                if (this.cache.status && (now - this.cache.statusTimestamp) < this.cacheTTL) {
                    return res.json({
                        ...this.cache.status,
                        cached: true,
                        timestamp: new Date().toISOString()
                    });
                }

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
                
                // Add additional metrics
                const enhancedStatus = {
                    ...status,
                    server: {
                        uptime: process.uptime(),
                        memory: process.memoryUsage(),
                        nodeVersion: process.version,
                        platform: process.platform
                    },
                    timestamp: new Date().toISOString()
                };
                
                // Cache the result
                this.cache.status = enhancedStatus;
                this.cache.statusTimestamp = now;
                
                res.json({
                    ...enhancedStatus,
                    cached: false
                });
            } catch (error) {
                console.error('[API] Error fetching system status:', error);
                // Return cached status if available, even if stale
                if (this.cache.status) {
                    return res.json({
                        ...this.cache.status,
                        cached: true,
                        stale: true,
                        error: 'Using cached data due to fetch error',
                        timestamp: new Date().toISOString()
                    });
                }
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
        
        // Analytics endpoint - Aggregated analytics data with concurrent fetching
        this.app.get('/api/analytics', async (req, res) => {
            try {
                // Check cache first
                const now = Date.now();
                if (this.cache.analytics && (now - this.cache.analyticsTimestamp) < this.analyticsCacheTTL) {
                    return res.json({
                        ...this.cache.analytics,
                        cached: true,
                        timestamp: new Date().toISOString()
                    });
                }

                // Fetch all data concurrently for maximum speed
                const [
                    statusResult,
                    channelsResult,
                    documentsResult,
                    memoriesResult
                ] = await Promise.allSettled([
                    // System status
                    (async () => {
                        try {
                            const { exec } = require('child_process');
                            const { promisify } = require('util');
                            const execAsync = promisify(exec);
                            const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
                            const scriptPath = path.join(__dirname, '..', '..', 'src', 'api', 'system_status_api.py');
                            const { stdout } = await execAsync(`${pythonCmd} "${scriptPath}"`, {
                                cwd: path.join(__dirname, '../..'),
                                timeout: 8000,
                                maxBuffer: 1024 * 1024
                            });
                            return JSON.parse(stdout);
                        } catch (error) {
                            console.error('[Analytics] Error fetching status:', error);
                            return null;
                        }
                    })(),
                    // Channels
                    this.getCachedChannels().catch(err => {
                        console.error('[Analytics] Error fetching channels:', err);
                        return { channels: [] };
                    }),
                    // Documents
                    this.getCachedDocuments().catch(err => {
                        console.error('[Analytics] Error fetching documents:', err);
                        return { documents: [] };
                    }),
                    // Memories (sample for analytics)
                    this.memoryService.getAllMemories(1000).catch(err => {
                        console.error('[Analytics] Error fetching memories:', err);
                        return { memories: [] };
                    })
                ]);

                // Process results
                const status = statusResult.status === 'fulfilled' ? statusResult.value : null;
                const channels = channelsResult.status === 'fulfilled' ? (channelsResult.value.channels || channelsResult.value || []) : [];
                const documents = documentsResult.status === 'fulfilled' ? (documentsResult.value.documents || documentsResult.value || []) : [];
                const memories = memoriesResult.status === 'fulfilled' ? (memoriesResult.value.memories || memoriesResult.value || []) : [];

                // Aggregate analytics
                const analytics = {
                    system: {
                        neo4j: status?.neo4j || { connected: false },
                        elasticsearch: status?.elasticsearch || { enabled: false, connected: false },
                        server: {
                            uptime: process.uptime(),
                            memory: process.memoryUsage(),
                            nodeVersion: process.version
                        }
                    },
                    memories: {
                        total: memories.length,
                        byType: this._aggregateByType(memories, 'memory_type'),
                        byChannel: this._aggregateByChannel(memories, channels),
                        recent: memories.slice(0, 10).map(m => ({
                            id: m.id || m.memory_id,
                            channel: m.channel_name,
                            type: m.memory_type,
                            created_at: m.created_at
                        })),
                        topChannels: this._getTopChannels(channels, 10)
                    },
                    documents: {
                        total: documents.length,
                        byType: this._aggregateByType(documents, 'file_type'),
                        totalChunks: documents.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0),
                        recent: documents.slice(0, 10).map(doc => ({
                            id: doc.id,
                            file_name: doc.file_name,
                            file_type: doc.file_type,
                            chunk_count: doc.chunk_count || 0,
                            uploaded_at: doc.uploaded_at,
                            uploaded_by: doc.uploaded_by
                        })),
                        storage: {
                            totalDocuments: documents.length,
                            totalChunks: documents.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0),
                            avgChunksPerDoc: documents.length > 0 
                                ? Math.round(documents.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0) / documents.length)
                                : 0
                        }
                    },
                    performance: {
                        // Placeholder for future performance metrics
                        // Can be enhanced with gopher agent metrics
                        avgLatency: null,
                        cacheHitRate: null,
                        totalQueries: null
                    },
                    timestamp: new Date().toISOString()
                };

                // Cache the result
                this.cache.analytics = analytics;
                this.cache.analyticsTimestamp = now;

                res.json({
                    ...analytics,
                    cached: false
                });
            } catch (error) {
                console.error('[API] Error fetching analytics:', error);
                // Return cached analytics if available
                if (this.cache.analytics) {
                    return res.json({
                        ...this.cache.analytics,
                        cached: true,
                        stale: true,
                        error: 'Using cached data due to fetch error',
                        timestamp: new Date().toISOString()
                    });
                }
                res.status(500).json({ 
                    error: 'Failed to fetch analytics',
                    details: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // Metrics endpoint - Combined metrics from metricsCollector and gopher agent (if available)
        this.app.get('/api/metrics', async (req, res) => {
            try {
                // Get metrics from metricsCollector (always available)
                const botMetrics = metricsCollector.getMetricsJSON();
                
                // Try to fetch additional metrics from gopher agent API (optional)
                const http = require('http');
                const https = require('https');
                const { URL } = require('url');
                
                let gopherMetrics = null;
                const metricsUrl = process.env.GOPHER_AGENT_URL || 'http://localhost:8001/get_metrics';
                
                try {
                    const urlObj = new URL(metricsUrl);
                    const client = urlObj.protocol === 'https:' ? https : http;
                    
                    gopherMetrics = await new Promise((resolve, reject) => {
                        const req = client.get(metricsUrl, (res) => {
                            let data = '';
                            res.on('data', chunk => data += chunk);
                            res.on('end', () => {
                                clearTimeout(timeout);
                                try {
                                    resolve(JSON.parse(data));
                                } catch (e) {
                                    reject(e);
                                }
                            });
                        });
                        
                        const timeout = setTimeout(() => {
                            req.abort();
                            reject(new Error('Timeout'));
                        }, 2000);
                        
                        req.on('error', (err) => {
                            clearTimeout(timeout);
                            reject(err);
                        });
                    });
                } catch (error) {
                    // Gopher agent not available - that's okay, we'll use bot metrics only
                    console.log('[Metrics] Gopher agent not available, using bot metrics only');
                }
                
                // Combine bot metrics with gopher agent metrics (if available)
                res.json({
                    bot: botMetrics,
                    gopher_agent: gopherMetrics || {
                        available: false,
                        intent_classifications: 0,
                        cache_hits: 0,
                        cache_misses: 0,
                        avg_latency_ms: 0,
                        gpu_inference_count: 0,
                        cache_hit_rate: 0,
                        gpu_enabled: false,
                        cache_size: 0
                    },
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching metrics:', error);
                res.status(500).json({ 
                    error: 'Failed to fetch metrics',
                    details: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        });
        
        // Comprehensive analytics endpoint - All data in one call
        this.app.get('/api/analytics/comprehensive', async (req, res) => {
            try {
                const now = Date.now();
                if (this.cache.analytics && (now - this.cache.analyticsTimestamp) < this.analyticsCacheTTL) {
                    return res.json({
                        ...this.cache.analytics,
                        cached: true,
                        timestamp: new Date().toISOString()
                    });
                }

                // Fetch ALL data concurrently
                const http = require('http');
                const https = require('https');
                const { URL } = require('url');
                
                const makeRequest = (path) => {
                    return new Promise((resolve) => {
                        const url = `${req.protocol}://${req.get('host')}${path}`;
                        const urlObj = new URL(url);
                        const client = urlObj.protocol === 'https:' ? https : http;
                        
                        const req2 = client.get(url, (res2) => {
                            let data = '';
                            res2.on('data', chunk => data += chunk);
                            res2.on('end', () => {
                                try {
                                    resolve(JSON.parse(data));
                                } catch (e) {
                                    resolve(null);
                                }
                            });
                        });
                        
                        req2.on('error', () => resolve(null));
                        req2.setTimeout(3000, () => {
                            req2.abort();
                            resolve(null);
                        });
                    });
                };
                
                const results = await Promise.allSettled([
                    // Basic analytics
                    makeRequest('/api/analytics'),
                    // Metrics
                    makeRequest('/api/metrics'),
                    // Trends
                    this._getTrendsData().catch(() => null),
                    // Performance details
                    this._getPerformanceDetails().catch(() => null),
                    // Knowledge graph
                    this._getKnowledgeGraphData().catch(() => null),
                    // User activity
                    this._getUserActivityData().catch(() => null),
                    // Query analytics
                    this._getQueryAnalytics().catch(() => null),
                    // Document popularity
                    this._getDocumentPopularity().catch(() => null),
                    // Storage details
                    this._getStorageDetails().catch(() => null),
                    // Configuration
                    this._getConfiguration().catch(() => null),
                    // Model info
                    this._getModelInfo().catch(() => null)
                ]);

                const comprehensive = {
                    basic: results[0].status === 'fulfilled' ? results[0].value : null,
                    metrics: results[1].status === 'fulfilled' ? results[1].value : null,
                    trends: results[2].status === 'fulfilled' ? results[2].value : null,
                    performance: results[3].status === 'fulfilled' ? results[3].value : null,
                    knowledgeGraph: results[4].status === 'fulfilled' ? results[4].value : null,
                    userActivity: results[5].status === 'fulfilled' ? results[5].value : null,
                    queryAnalytics: results[6].status === 'fulfilled' ? results[6].value : null,
                    documentPopularity: results[7].status === 'fulfilled' ? results[7].value : null,
                    storage: results[8].status === 'fulfilled' ? results[8].value : null,
                    configuration: results[9].status === 'fulfilled' ? results[9].value : null,
                    modelInfo: results[10].status === 'fulfilled' ? results[10].value : null,
                    timestamp: new Date().toISOString()
                };

                this.cache.analytics = comprehensive;
                this.cache.analyticsTimestamp = now;

                res.json(comprehensive);
            } catch (error) {
                console.error('[API] Error fetching comprehensive analytics:', error);
                res.status(500).json({ 
                    error: 'Failed to fetch comprehensive analytics',
                    details: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // Trends endpoint
        this.app.get('/api/analytics/trends', async (req, res) => {
            try {
                const days = parseInt(req.query.days) || 30;
                const trends = await this._getTrendsData(days);
                res.json(trends);
            } catch (error) {
                console.error('[API] Error fetching trends:', error);
                res.status(500).json({ error: error.message });
            }
        });

        // Performance details endpoint
        this.app.get('/api/analytics/performance', async (req, res) => {
            try {
                const performance = await this._getPerformanceDetails();
                res.json(performance);
            } catch (error) {
                console.error('[API] Error fetching performance:', error);
                res.status(500).json({ error: error.message });
            }
        });

        // Knowledge graph endpoint
        this.app.get('/api/analytics/knowledge-graph', async (req, res) => {
            try {
                const kg = await this._getKnowledgeGraphData();
                res.json(kg);
            } catch (error) {
                console.error('[API] Error fetching knowledge graph:', error);
                res.status(500).json({ error: error.message });
            }
        });

        // User activity endpoint
        this.app.get('/api/analytics/users', async (req, res) => {
            try {
                const users = await this._getUserActivityData();
                res.json(users);
            } catch (error) {
                console.error('[API] Error fetching user activity:', error);
                res.status(500).json({ error: error.message });
            }
        });

        // Query analytics endpoint
        this.app.get('/api/analytics/queries', async (req, res) => {
            try {
                const queries = await this._getQueryAnalytics();
                res.json(queries);
            } catch (error) {
                console.error('[API] Error fetching query analytics:', error);
                res.status(500).json({ error: error.message });
            }
        });

        // Document popularity endpoint
        this.app.get('/api/analytics/documents/popularity', async (req, res) => {
            try {
                const popularity = await this._getDocumentPopularity();
                res.json(popularity);
            } catch (error) {
                console.error('[API] Error fetching document popularity:', error);
                res.status(500).json({ error: error.message });
            }
        });

        // Configuration endpoint
        this.app.get('/api/config', async (req, res) => {
            try {
                const config = await this._getConfiguration();
                res.json(config);
            } catch (error) {
                console.error('[API] Error fetching configuration:', error);
                res.status(500).json({ error: error.message });
            }
        });

        // Model info endpoint
        this.app.get('/api/model-info', async (req, res) => {
            try {
                const info = await this._getModelInfo();
                res.json(info);
            } catch (error) {
                console.error('[API] Error fetching model info:', error);
                res.status(500).json({ error: error.message });
            }
        });

        // Export endpoint
        this.app.get('/api/export', async (req, res) => {
            try {
                const format = req.query.format || 'json';
                const data = await this._getExportData();
                
                if (format === 'csv') {
                    res.setHeader('Content-Type', 'text/csv');
                    res.setHeader('Content-Disposition', 'attachment; filename=analytics-export.csv');
                    res.send(this._convertToCSV(data));
                } else {
                    res.setHeader('Content-Type', 'application/json');
                    res.setHeader('Content-Disposition', 'attachment; filename=analytics-export.json');
                    res.json(data);
                }
            } catch (error) {
                console.error('[API] Error exporting data:', error);
                res.status(500).json({ error: error.message });
            }
        });

        // Metrics endpoint - Prometheus format
        this.app.get('/api/metrics/prometheus', (req, res) => {
            try {
                res.set('Content-Type', 'text/plain; version=0.0.4');
                res.send(metricsCollector.getPrometheusMetrics());
            } catch (error) {
                console.error('[API] Error fetching Prometheus metrics:', error);
                res.status(500).json({ 
                    error: 'Failed to fetch metrics',
                    details: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        });
        
        // Metrics endpoint - JSON format
        this.app.get('/api/metrics/json', (req, res) => {
            try {
                res.json({
                    ...metricsCollector.getMetricsJSON(),
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching JSON metrics:', error);
                res.status(500).json({ 
                    error: 'Failed to fetch metrics',
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
        if (type === 'analytics' || type === null) {
            this.cache.analytics = null;
            this.cache.analyticsTimestamp = 0;
        }
        if (type === 'status' || type === null) {
            this.cache.status = null;
            this.cache.statusTimestamp = 0;
        }
    }

    /**
     * Aggregate items by a specific field
     */
    _aggregateByType(items, field) {
        const aggregated = {};
        items.forEach(item => {
            const type = item[field] || 'unknown';
            aggregated[type] = (aggregated[type] || 0) + 1;
        });
        return aggregated;
    }

    /**
     * Aggregate memories by channel
     */
    _aggregateByChannel(memories, channels) {
        const channelMap = new Map();
        channels.forEach(ch => {
            channelMap.set(ch.channel_id || ch.id, {
                channel_id: ch.channel_id || ch.id,
                channel_name: ch.channel_name || 'Unknown',
                memory_count: 0
            });
        });
        
        memories.forEach(memory => {
            const channelId = memory.channel_id;
            if (channelId && channelMap.has(channelId)) {
                channelMap.get(channelId).memory_count++;
            }
        });
        
        return Array.from(channelMap.values())
            .sort((a, b) => b.memory_count - a.memory_count)
            .slice(0, 20); // Top 20 channels
    }

    /**
     * Get top channels by memory count
     */
    _getTopChannels(channels, limit = 10) {
        return channels
            .sort((a, b) => (b.memory_count || 0) - (a.memory_count || 0))
            .slice(0, limit)
            .map(ch => ({
                channel_id: ch.channel_id || ch.id,
                channel_name: ch.channel_name || 'Unknown',
                memory_count: ch.memory_count || 0
            }));
    }

    /**
     * Get trends data (time-based growth)
     */
    async _getTrendsData(days = 30) {
        try {
            const { exec } = require('child_process');
            const { promisify } = require('util');
            const execAsync = promisify(exec);
            const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
            const scriptPath = path.join(__dirname, '..', '..', 'scripts', 'get_trends.py');
            
            // Create trends script if it doesn't exist - we'll create a simple one
            const trends = {
                memories: this._generateTrendData(days, 'memories'),
                documents: this._generateTrendData(days, 'documents'),
                queries: this._generateTrendData(days, 'queries'),
                storage: this._generateTrendData(days, 'storage')
            };
            
            return trends;
        } catch (error) {
            console.error('[Trends] Error:', error);
            return { memories: [], documents: [], queries: [], storage: [] };
        }
    }

    /**
     * Generate trend data (placeholder - would query Neo4j in production)
     */
    _generateTrendData(days, type) {
        const data = [];
        const now = Date.now();
        for (let i = days; i >= 0; i--) {
            const date = new Date(now - i * 24 * 60 * 60 * 1000);
            data.push({
                date: date.toISOString().split('T')[0],
                value: Math.floor(Math.random() * 100) + 10, // Placeholder
                cumulative: Math.floor(Math.random() * 1000) + 100
            });
        }
        return data;
    }

    /**
     * Get detailed performance metrics
     */
    async _getPerformanceDetails() {
        try {
            const { exec } = require('child_process');
            const { promisify } = require('util');
            const execAsync = promisify(exec);
            const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
            const scriptPath = path.join(__dirname, '..', '..', 'src', 'api', 'performance_api.py');
            
            try {
                const { stdout } = await execAsync(`${pythonCmd} "${scriptPath}"`, {
                    cwd: path.join(__dirname, '../..'),
                    timeout: 5000,
                    maxBuffer: 1024 * 1024
                });
                return JSON.parse(stdout);
            } catch (error) {
                // Return default structure if script doesn't exist
                return {
                    latency: { p50: 0, p95: 0, p99: 0, mean: 0, max: 0, count: 0 },
                    errorRate: 0,
                    cacheStats: { hitRate: 0, hits: 0, misses: 0, total: 0 },
                    operations: { retrieval: 0, generation: 0, reranking: 0 }
                };
            }
        } catch (error) {
            return { error: error.message };
        }
    }

    /**
     * Get knowledge graph data
     */
    async _getKnowledgeGraphData() {
        try {
            const documents = await this.getCachedDocuments();
            const docList = documents.documents || documents || [];
            
            // Simulate topic clusters
            const topics = {};
            docList.forEach(doc => {
                const topic = doc.file_type || 'general';
                topics[topic] = (topics[topic] || 0) + 1;
            });

            return {
                topicClusters: Object.entries(topics).map(([topic, count]) => ({
                    topic,
                    documentCount: count
                })),
                totalTopics: Object.keys(topics).length,
                totalConnections: docList.length
            };
        } catch (error) {
            return { topicClusters: [], totalTopics: 0, totalConnections: 0 };
        }
    }

    /**
     * Get user activity data
     */
    async _getUserActivityData() {
        try {
            const channels = await this.getCachedChannels();
            const channelList = channels.channels || channels || [];
            
            return {
                topUsers: channelList
                    .sort((a, b) => (b.memory_count || 0) - (a.memory_count || 0))
                    .slice(0, 20)
                    .map(ch => ({
                        userId: ch.channel_id || ch.id,
                        username: ch.channel_name || 'Unknown',
                        memoryCount: ch.memory_count || 0,
                        lastActive: ch.last_active || null
                    })),
                totalUsers: channelList.length,
                activeUsers: channelList.filter(ch => (ch.memory_count || 0) > 0).length
            };
        } catch (error) {
            return { topUsers: [], totalUsers: 0, activeUsers: 0 };
        }
    }

    /**
     * Get query analytics
     */
    async _getQueryAnalytics() {
        // Placeholder - would query conversation store in production
        return {
            totalQueries: 0,
            queryTypes: {
                factual: 0,
                analytical: 0,
                procedural: 0,
                comparative: 0
            },
            avgQueryLength: 0,
            popularQueries: []
        };
    }

    /**
     * Get document popularity
     */
    async _getDocumentPopularity() {
        try {
            const documents = await this.getCachedDocuments();
            const docList = documents.documents || documents || [];
            
            return {
                mostQueried: docList
                    .sort((a, b) => (b.chunk_count || 0) - (a.chunk_count || 0))
                    .slice(0, 20)
                    .map(doc => ({
                        docId: doc.id,
                        fileName: doc.file_name,
                        queryCount: doc.chunk_count || 0,
                        uploadedAt: doc.uploaded_at
                    })),
                totalDocuments: docList.length,
                avgQueriesPerDoc: docList.length > 0 
                    ? Math.round(docList.reduce((sum, d) => sum + (d.chunk_count || 0), 0) / docList.length)
                    : 0
            };
        } catch (error) {
            return { mostQueried: [], totalDocuments: 0, avgQueriesPerDoc: 0 };
        }
    }

    /**
     * Get storage details
     */
    async _getStorageDetails() {
        try {
            const documents = await this.getCachedDocuments();
            const docList = documents.documents || documents || [];
            
            const byType = {};
            docList.forEach(doc => {
                const type = doc.file_type || 'unknown';
                byType[type] = (byType[type] || 0) + 1;
            });

            return {
                byType,
                totalChunks: docList.reduce((sum, d) => sum + (d.chunk_count || 0), 0),
                avgChunkSize: 1000, // Placeholder
                totalSize: docList.length * 1024 * 100 // Placeholder
            };
        } catch (error) {
            return { byType: {}, totalChunks: 0, avgChunkSize: 0, totalSize: 0 };
        }
    }

    /**
     * Get configuration
     */
    async _getConfiguration() {
        try {
            const { exec } = require('child_process');
            const { promisify } = require('util');
            const execAsync = promisify(exec);
            const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
            const scriptPath = path.join(__dirname, '..', '..', 'src', 'api', 'config_api.py');
            
            try {
                const { stdout } = await execAsync(`${pythonCmd} "${scriptPath}"`, {
                    cwd: path.join(__dirname, '../..'),
                    timeout: 5000
                });
                return JSON.parse(stdout);
            } catch (error) {
                // Return default config structure
                return {
                    llmProvider: process.env.LLM_PROVIDER || 'lmstudio',
                    elasticsearchEnabled: process.env.ELASTICSEARCH_ENABLED === 'true',
                    hybridSearchEnabled: true,
                    queryExpansionEnabled: true,
                    temporalWeightingEnabled: true,
                    cacheEnabled: true,
                    gpuEnabled: process.env.USE_GPU !== 'cpu'
                };
            }
        } catch (error) {
            return { error: error.message };
        }
    }

    /**
     * Get model information
     */
    async _getModelInfo() {
        return {
            embeddingModel: process.env.EMBEDDING_MODEL || 'all-MiniLM-L6-v2',
            embeddingDimension: 384,
            llmModel: process.env.LMSTUDIO_MODEL || process.env.OPENAI_MODEL || 'unknown',
            llmProvider: process.env.LLM_PROVIDER || 'lmstudio',
            gpuEnabled: process.env.USE_GPU !== 'cpu',
            streamingEnabled: process.env.LLM_STREAMING_ENABLED === 'true'
        };
    }

    /**
     * Get export data
     */
    async _getExportData() {
        const [analytics, trends, performance, users] = await Promise.allSettled([
            this._getAnalyticsForExport().catch(() => null),
            this._getTrendsData().catch(() => null),
            this._getPerformanceDetails().catch(() => null),
            this._getUserActivityData().catch(() => null)
        ]);

        return {
            analytics: analytics.status === 'fulfilled' ? analytics.value : null,
            trends: trends.status === 'fulfilled' ? trends.value : null,
            performance: performance.status === 'fulfilled' ? performance.value : null,
            users: users.status === 'fulfilled' ? users.value : null,
            exportedAt: new Date().toISOString()
        };
    }

    /**
     * Get analytics for export (internal method)
     */
    async _getAnalyticsForExport() {
        // Reuse existing analytics cache or generate fresh
        const now = Date.now();
        if (this.cache.analytics && (now - this.cache.analyticsTimestamp) < this.analyticsCacheTTL) {
            return this.cache.analytics;
        }
        
        // Generate basic analytics
        const [channelsResult, documentsResult, memoriesResult] = await Promise.allSettled([
            this.getCachedChannels().catch(() => ({ channels: [] })),
            this.getCachedDocuments().catch(() => ({ documents: [] })),
            this.memoryService.getAllMemories(1000).catch(() => ({ memories: [] }))
        ]);
        
        const channels = channelsResult.status === 'fulfilled' ? (channelsResult.value.channels || channelsResult.value || []) : [];
        const documents = documentsResult.status === 'fulfilled' ? (documentsResult.value.documents || documentsResult.value || []) : [];
        const memories = memoriesResult.status === 'fulfilled' ? (memoriesResult.value.memories || memoriesResult.value || []) : [];
        
        return {
            memories: { total: memories.length },
            documents: { total: documents.length },
            channels: { total: channels.length }
        };
    }

    /**
     * Convert data to CSV
     */
    _convertToCSV(data) {
        // Enhanced CSV conversion
        let csv = 'Category,Metric,Value\n';
        
        if (data.analytics) {
            csv += `Memories,Total,${data.analytics.memories?.total || 0}\n`;
            csv += `Documents,Total,${data.analytics.documents?.total || 0}\n`;
            csv += `Channels,Total,${data.analytics.channels?.total || 0}\n`;
        }
        
        if (data.performance) {
            csv += `Performance,Avg Latency,${data.performance.latency?.mean || 0}ms\n`;
            csv += `Performance,Error Rate,${(data.performance.errorRate || 0) * 100}%\n`;
            csv += `Performance,Cache Hit Rate,${(data.performance.cacheStats?.hitRate || 0) * 100}%\n`;
        }
        
        if (data.users) {
            csv += `Users,Total,${data.users.totalUsers || 0}\n`;
            csv += `Users,Active,${data.users.activeUsers || 0}\n`;
        }
        
        return csv;
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
