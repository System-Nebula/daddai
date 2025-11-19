import express, { Express, Request, Response, NextFunction } from 'express';
import { Server as HttpServer } from 'http';
import { Server as SocketIOServer, Socket } from 'socket.io';
import path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import * as http from 'http';
import * as https from 'https';
import { URL, fileURLToPath } from 'url';
import compression from 'compression';
import { createRequire } from 'module';
import memoryService from './memoryService';
import DocumentService from './documentService';

// Get __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Import CommonJS module using createRequire
const require = createRequire(import.meta.url);
const metricsCollector = require('./metrics.js');

const execAsync = promisify(exec);

interface CacheEntry<T> {
    data: T | null;
    timestamp: number;
}

interface Cache {
    channels: CacheEntry<unknown>;
    documents: CacheEntry<unknown>;
    analytics: CacheEntry<unknown>;
    status: CacheEntry<unknown>;
}

interface WebSocketClient {
    id: string;
    lastPing: number;
}

/**
 * Modern Web Server for GopherBot Dashboard
 * Features: WebSocket real-time updates, advanced caching, streaming, performance monitoring
 */
class WebServer {
    private app: Express;
    private httpServer: HttpServer | null = null;
    private io: SocketIOServer | null = null;
    private port: number;
    private memoryService: typeof memoryService;
    private documentService: DocumentService;
    private cache: Cache;
    private cacheTTL: number;
    private analyticsCacheTTL: number;
    private clients: Map<string, WebSocketClient> = new Map();
    private broadcastInterval: NodeJS.Timeout | null = null;
    private performanceMetrics: {
        requestCount: number;
        cacheHits: number;
        cacheMisses: number;
        avgResponseTime: number;
        responseTimes: number[];
    } = {
        requestCount: 0,
        cacheHits: 0,
        cacheMisses: 0,
        avgResponseTime: 0,
        responseTimes: []
    };

    constructor(memoryService: typeof memoryService, documentService: DocumentService, port = 3000) {
        this.app = express();
        this.port = port;
        this.memoryService = memoryService;
        this.documentService = documentService;
        
        // Enhanced cache configuration
        this.cache = {
            channels: { data: null, timestamp: 0 },
            documents: { data: null, timestamp: 0 },
            analytics: { data: null, timestamp: 0 },
            status: { data: null, timestamp: 0 }
        };
        this.cacheTTL = 30000; // 30 seconds cache
        this.analyticsCacheTTL = 10000; // 10 seconds for analytics
        
        this.setupMiddleware();
        this.setupRoutes();
        this.setupErrorHandling();
    }
    
    /**
     * Setup middleware for request processing
     */
    setupMiddleware(): void {
        // Add observability middleware FIRST (if available)
        try {
            const { observabilityMiddleware } = require('./middleware/observabilityMiddleware');
            this.app.use(observabilityMiddleware);
        } catch (error) {
            // Observability middleware not available, continue without it
            const err = error as Error;
            console.warn('[WebServer] Observability middleware not available:', err.message);
        }
        
        // Add compression middleware for faster responses
        this.app.use(compression({ 
            level: 6, 
            threshold: 1024,
            filter: (req: Request, res: Response) => {
                // Don't compress WebSocket upgrade requests
                if (req.headers.upgrade === 'websocket') {
                    return false;
                }
                return compression.filter(req, res);
            }
        }));
        
        // JSON body parser with size limit
        this.app.use(express.json({ limit: '10mb' }));
        this.app.use(express.urlencoded({ extended: true, limit: '10mb' }));
        
        // Request logging middleware with performance tracking
        this.app.use((req: Request, res: Response, next: NextFunction) => {
            const start = Date.now();
            const timestamp = new Date().toISOString();
            
            // Log request
            console.log(`[${timestamp}] ${req.method} ${req.path} - ${req.ip}`);
            
            // Track response time
            res.on('finish', () => {
                const duration = Date.now() - start;
                this.performanceMetrics.requestCount++;
                this.performanceMetrics.responseTimes.push(duration);
                
                // Keep only last 1000 response times for average calculation
                if (this.performanceMetrics.responseTimes.length > 1000) {
                    this.performanceMetrics.responseTimes.shift();
                }
                
                // Calculate average
                const sum = this.performanceMetrics.responseTimes.reduce((a, b) => a + b, 0);
                this.performanceMetrics.avgResponseTime = sum / this.performanceMetrics.responseTimes.length;
                
                const statusColor = res.statusCode >= 400 ? '\x1b[31m' : '\x1b[32m';
                console.log(`[${timestamp}] ${statusColor}${res.statusCode}\x1b[0m ${req.method} ${req.path} - ${duration}ms`);
            });
            
            next();
        });
        
        // CORS headers (if needed for cross-origin requests)
        this.app.use((req: Request, res: Response, next: NextFunction) => {
            res.header('Access-Control-Allow-Origin', '*');
            res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
            res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization');
            
            if (req.method === 'OPTIONS') {
                return res.sendStatus(200);
            }
            
            next();
        });
        
        // Security headers
        this.app.use((req: Request, res: Response, next: NextFunction) => {
            res.setHeader('X-Content-Type-Options', 'nosniff');
            res.setHeader('X-Frame-Options', 'DENY');
            res.setHeader('X-XSS-Protection', '1; mode=block');
            res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
            next();
        });
    }
    
    /**
     * Setup WebSocket server for real-time updates
     */
    setupWebSocket(): void {
        if (!this.httpServer) {
            throw new Error('HTTP server must be started before WebSocket');
        }
        
        this.io = new SocketIOServer(this.httpServer, {
            cors: {
                origin: '*',
                methods: ['GET', 'POST']
            },
            transports: ['websocket', 'polling'],
            pingTimeout: 60000,
            pingInterval: 25000
        });
        
        this.io.on('connection', (socket) => {
            const clientId = socket.id;
            this.clients.set(clientId, {
                id: clientId,
                lastPing: Date.now()
            });
            
            console.log(`[WebSocket] Client connected: ${clientId} (Total: ${this.clients.size})`);
            
            // Send initial data
            this.sendInitialData(socket);
            
            // Handle ping/pong for keepalive
            socket.on('ping', () => {
                const client = this.clients.get(clientId);
                if (client) {
                    client.lastPing = Date.now();
                }
                socket.emit('pong');
            });
            
            // Handle client subscriptions
            socket.on('subscribe', (channels: string[]) => {
                socket.join(channels);
                console.log(`[WebSocket] Client ${clientId} subscribed to:`, channels);
            });
            
            socket.on('unsubscribe', (channels: string[]) => {
                socket.leave(channels);
                console.log(`[WebSocket] Client ${clientId} unsubscribed from:`, channels);
            });
            
            // Handle disconnection
            socket.on('disconnect', () => {
                this.clients.delete(clientId);
                console.log(`[WebSocket] Client disconnected: ${clientId} (Total: ${this.clients.size})`);
            });
        });
        
        // Start broadcasting updates
        this.startBroadcasting();
    }
    
    /**
     * Send initial data to newly connected client
     */
    private async sendInitialData(socket: Socket): Promise<void> {
        try {
            const [channels, documents, status] = await Promise.allSettled([
                this.getCachedChannels(),
                this.getCachedDocuments(),
                this.getCachedStatus()
            ]);
            
            socket.emit('initial-data', {
                channels: channels.status === 'fulfilled' ? channels.value : null,
                documents: documents.status === 'fulfilled' ? documents.value : null,
                status: status.status === 'fulfilled' ? status.value : null,
                timestamp: new Date().toISOString()
            });
        } catch (error) {
            console.error('[WebSocket] Error sending initial data:', error);
        }
    }
    
    /**
     * Start broadcasting updates to connected clients
     */
    private startBroadcasting(): void {
        if (this.broadcastInterval) {
            clearInterval(this.broadcastInterval);
        }
        
        // Broadcast updates every 5 seconds
        this.broadcastInterval = setInterval(async () => {
            if (!this.io || this.clients.size === 0) {
                return;
            }
            
            try {
                // Broadcast system status updates
                const status = await this.getCachedStatus();
                this.io.emit('status-update', {
                    ...status,
                    timestamp: new Date().toISOString()
                });
                
                // Broadcast performance metrics
                this.io.emit('performance-update', {
                    ...this.performanceMetrics,
                    cacheHitRate: this.performanceMetrics.requestCount > 0
                        ? (this.performanceMetrics.cacheHits / this.performanceMetrics.requestCount) * 100
                        : 0,
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[WebSocket] Error broadcasting updates:', error);
            }
        }, 5000);
    }
    
    /**
     * Broadcast data update to all clients
     */
    private broadcastUpdate(channel: string, data: unknown): void {
        if (this.io) {
            this.io.to(channel).emit('data-update', {
                channel,
                data,
                timestamp: new Date().toISOString()
            });
        }
    }
    
    /**
     * Get cached channels or fetch fresh data
     */
    async getCachedChannels(): Promise<unknown> {
        const now = Date.now();
        if (this.cache.channels.data && (now - this.cache.channels.timestamp) < this.cacheTTL) {
            this.performanceMetrics.cacheHits++;
            return Promise.resolve(this.cache.channels.data);
        }
        
        this.performanceMetrics.cacheMisses++;
        try {
            const channels = await this.memoryService.getAllChannels();
            this.cache.channels.data = channels;
            this.cache.channels.timestamp = now;
            
            // Broadcast update
            this.broadcastUpdate('channels', channels);
            
            return channels;
        } catch (error) {
            console.error('[Cache] Error fetching channels:', error);
            // Return stale cache if available, otherwise throw
            if (this.cache.channels.data) {
                console.warn('[Cache] Returning stale channels cache');
                return this.cache.channels.data;
            }
            throw error;
        }
    }
    
    /**
     * Get cached documents or fetch fresh data
     */
    async getCachedDocuments(): Promise<unknown> {
        const now = Date.now();
        if (this.cache.documents.data && (now - this.cache.documents.timestamp) < this.cacheTTL) {
            this.performanceMetrics.cacheHits++;
            return Promise.resolve(this.cache.documents.data);
        }
        
        this.performanceMetrics.cacheMisses++;
        try {
            const documents = await this.documentService.getAllDocuments();
            this.cache.documents.data = documents;
            this.cache.documents.timestamp = now;
            
            // Broadcast update
            this.broadcastUpdate('documents', documents);
            
            return documents;
        } catch (error) {
            console.error('[Cache] Error fetching documents:', error);
            // Return stale cache if available, otherwise throw
            if (this.cache.documents.data) {
                console.warn('[Cache] Returning stale documents cache');
                return this.cache.documents.data;
            }
            throw error;
        }
    }
    
    /**
     * Get cached status or fetch fresh data
     */
    private async getCachedStatus(): Promise<unknown> {
        const now = Date.now();
        if (this.cache.status.data && (now - this.cache.status.timestamp) < this.cacheTTL) {
            return Promise.resolve(this.cache.status.data);
        }
        
        try {
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
                    platform: process.platform,
                    performance: {
                        avgResponseTime: this.performanceMetrics.avgResponseTime,
                        cacheHitRate: this.performanceMetrics.requestCount > 0
                            ? (this.performanceMetrics.cacheHits / this.performanceMetrics.requestCount) * 100
                            : 0,
                        totalRequests: this.performanceMetrics.requestCount
                    }
                },
                timestamp: new Date().toISOString()
            };
            
            // Cache the result
            this.cache.status.data = enhancedStatus;
            this.cache.status.timestamp = now;
            
            return enhancedStatus;
        } catch (error) {
            console.error('[Cache] Error fetching status:', error);
            // Return cached status if available, even if stale
            if (this.cache.status.data) {
                return this.cache.status.data;
            }
            throw error;
        }
    }
    
    /**
     * Setup API routes
     */
    setupRoutes(): void {
        // Health check endpoint (enhanced with performance metrics)
        this.app.get('/api/health', async (req: Request, res: Response) => {
            try {
                const { getHealthCheckData } = require('./utils/performanceMonitor');
                const healthData = await getHealthCheckData();
                res.json({
                    ...healthData,
                    websocket: {
                        connected: this.clients.size,
                        enabled: this.io !== null
                    },
                    performance: {
                        avgResponseTime: this.performanceMetrics.avgResponseTime,
                        cacheHitRate: this.performanceMetrics.requestCount > 0
                            ? (this.performanceMetrics.cacheHits / this.performanceMetrics.requestCount) * 100
                            : 0,
                        totalRequests: this.performanceMetrics.requestCount
                    }
                });
            } catch (error) {
                // Fallback to basic health check
                res.json({ 
                    status: 'ok', 
                    timestamp: new Date().toISOString(),
                    uptime: process.uptime(),
                    websocket: {
                        connected: this.clients.size,
                        enabled: this.io !== null
                    }
                });
            }
        });
        
        // System status endpoint (Elasticsearch + Neo4j) - Enhanced with caching
        this.app.get('/api/status', async (req: Request, res: Response) => {
            try {
                const status = await this.getCachedStatus();
                res.json({
                    ...(status as Record<string, unknown>),
                    cached: this.isCacheValid('status')
                });
            } catch (error) {
                console.error('[API] Error fetching system status:', error);
                const err = error as Error;
                res.status(500).json({ 
                    error: 'Failed to fetch system status',
                    details: err.message,
                    timestamp: new Date().toISOString()
                });
            }
        });
        
        // API endpoint to get all channels with memories (cached)
        this.app.get('/api/channels', async (req: Request, res: Response) => {
            try {
                const channels = await this.getCachedChannels();
                const channelList = (channels as { channels?: unknown[] })?.channels || (channels as unknown[]);
                res.json({ 
                    channels: channelList,
                    cached: this.isCacheValid('channels'),
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching channels:', error);
                const err = error as Error;
                res.status(500).json({ 
                    error: 'Failed to fetch channels', 
                    details: err.message,
                    timestamp: new Date().toISOString()
                });
            }
        });
        
        // Keep /api/users for backward compatibility (returns channels)
        this.app.get('/api/users', async (req: Request, res: Response) => {
            try {
                const channels = await this.getCachedChannels();
                const channelList = (channels as { channels?: unknown[] })?.channels || (channels as unknown[]);
                res.json({ 
                    users: channelList, // Return as "users" for backward compat
                    cached: this.isCacheValid('channels'),
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching channels:', error);
                const err = error as Error;
                res.status(500).json({ 
                    error: 'Failed to fetch channels', 
                    details: err.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // API endpoint to get all memories across all users (with pagination)
        this.app.get('/api/memories/all', async (req: Request, res: Response) => {
            try {
                const limit = Math.min(parseInt(req.query.limit as string) || 25, 100);
                const offset = parseInt(req.query.offset as string) || 0;
                const skip = parseInt(req.query.skip as string) || offset;
                
                const fetchLimit = Math.min(limit + 1, 1000);
                const result = await this.memoryService.getAllMemories(fetchLimit + skip) as { memories?: unknown[] };
                
                let allMemories: unknown[] = [];
                if (result && result.memories && Array.isArray(result.memories)) {
                    allMemories = result.memories;
                } else if (Array.isArray(result)) {
                    allMemories = result;
                }
                
                const paginatedMemories = allMemories.slice(0, limit);
                const hasMore = allMemories.length > limit;
                const estimatedTotal = hasMore ? skip + allMemories.length + 1 : skip + allMemories.length;
                
                res.json({
                    memories: paginatedMemories,
                    count: paginatedMemories.length,
                    total: estimatedTotal,
                    hasMore: hasMore,
                    offset: skip,
                    limit: limit,
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching all memories:', (error as Error).message);
                const err = error as Error;
                res.status(500).json({ 
                    error: 'Failed to fetch all memories', 
                    details: err.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // API endpoint to get memories for a specific channel
        this.app.get('/api/memories/:channelId', async (req: Request, res: Response) => {
            try {
                const { channelId } = req.params;
                const limit = Math.min(parseInt(req.query.limit as string) || 100, 500);
                const memories = await this.memoryService.getChannelMemories(channelId, limit);
                res.json({
                    ...(memories as Record<string, unknown>),
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching memories:', error);
                const err = error as Error;
                res.status(500).json({ 
                    error: 'Failed to fetch memories',
                    details: err.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // API endpoint to search memories by channel name
        this.app.get('/api/memories/search/:channelName', async (req: Request, res: Response) => {
            try {
                const { channelName } = req.params;
                const limit = Math.min(parseInt(req.query.limit as string) || 100, 500);
                const memories = await this.memoryService.getChannelMemories(null, limit, channelName);
                res.json({
                    ...(memories as Record<string, unknown>),
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error searching memories:', error);
                const err = error as Error;
                res.status(500).json({ 
                    error: 'Failed to search memories',
                    details: err.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // API endpoint to get all shared documents (cached)
        this.app.get('/api/documents', async (req: Request, res: Response) => {
            try {
                const result = await this.getCachedDocuments();
                const documents = (result as { documents?: unknown[] })?.documents || (result as unknown[]) || [];
                res.json({ 
                    documents: documents, 
                    count: Array.isArray(documents) ? documents.length : 0,
                    cached: this.isCacheValid('documents'),
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching documents:', error);
                const err = error as Error;
                res.status(500).json({ 
                    error: 'Failed to fetch documents', 
                    details: err.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // API endpoint to get chunks for a specific document
        this.app.get('/api/documents/:docId/chunks', async (req: Request, res: Response) => {
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
                    ...(result as Record<string, unknown>),
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching document chunks:', error);
                const err = error as Error;
                res.status(500).json({ 
                    error: 'Failed to fetch document chunks', 
                    details: err.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // API endpoint to search documents in specific store
        this.app.get('/api/search/documents', async (req: Request, res: Response) => {
            try {
                const { query, store, top_k, doc_id, doc_filename } = req.query;
                
                if (!query) {
                    return res.status(400).json({ 
                        error: 'Query parameter is required',
                        timestamp: new Date().toISOString()
                    });
                }
                
                if (!store || !['elasticsearch', 'neo4j', 'both'].includes(store as string)) {
                    return res.status(400).json({ 
                        error: 'Store parameter must be "elasticsearch", "neo4j", or "both"',
                        timestamp: new Date().toISOString()
                    });
                }
                
                const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
                const args = [
                    path.join(__dirname, '..', '..', 'src', 'api', 'search_api.py'),
                    '--query', query as string,
                    '--store', store as string,
                    '--top-k', (top_k || 10).toString()
                ];
                
                if (doc_id) {
                    args.push('--doc-id', doc_id as string);
                }
                if (doc_filename) {
                    args.push('--doc-filename', doc_filename as string);
                }
                
                const { stdout, stderr } = await execAsync(`${pythonCmd} ${args.join(' ')}`, {
                    cwd: path.join(__dirname, '../..'),
                    timeout: 15000,
                    maxBuffer: 1024 * 1024 * 5 // 5MB buffer
                });
                
                if (stderr && !stdout) {
                    throw new Error(stderr);
                }
                
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
                const err = error as Error;
                res.status(500).json({ 
                    error: 'Failed to search documents',
                    details: err.message,
                    timestamp: new Date().toISOString()
                });
            }
        });
        
        // Analytics endpoint - Aggregated analytics data with concurrent fetching
        this.app.get('/api/analytics', async (req: Request, res: Response) => {
            try {
                // Check cache first
                const now = Date.now();
                if (this.cache.analytics.data && (now - this.cache.analytics.timestamp) < this.analyticsCacheTTL) {
                    return res.json({
                        ...(this.cache.analytics.data as Record<string, unknown>),
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
                    this.getCachedStatus(),
                    // Channels
                    this.getCachedChannels().catch(() => ({ channels: [] })),
                    // Documents
                    this.getCachedDocuments().catch(() => ({ documents: [] })),
                    // Memories (sample for analytics)
                    this.memoryService.getAllMemories(1000).catch(() => ({ memories: [] }))
                ]);

                // Process results
                const status = statusResult.status === 'fulfilled' ? statusResult.value : null;
                const channels = channelsResult.status === 'fulfilled' ? ((channelsResult.value as { channels?: unknown[] })?.channels || channelsResult.value || []) : [];
                const documents = documentsResult.status === 'fulfilled' ? ((documentsResult.value as { documents?: unknown[] })?.documents || documentsResult.value || []) : [];
                const memories = memoriesResult.status === 'fulfilled' ? ((memoriesResult.value as { memories?: unknown[] })?.memories || memoriesResult.value || []) : [];

                // Aggregate analytics
                const analytics = {
                    system: {
                        neo4j: (status as { neo4j?: unknown })?.neo4j || { connected: false },
                        elasticsearch: (status as { elasticsearch?: unknown })?.elasticsearch || { enabled: false, connected: false },
                        server: {
                            uptime: process.uptime(),
                            memory: process.memoryUsage(),
                            nodeVersion: process.version,
                            performance: {
                                avgResponseTime: this.performanceMetrics.avgResponseTime,
                                cacheHitRate: this.performanceMetrics.requestCount > 0
                                    ? (this.performanceMetrics.cacheHits / this.performanceMetrics.requestCount) * 100
                                    : 0,
                                totalRequests: this.performanceMetrics.requestCount
                            }
                        }
                    },
                    memories: {
                        total: Array.isArray(memories) ? memories.length : 0,
                        byType: this._aggregateByType(memories as Array<Record<string, unknown>>, 'memory_type'),
                        byChannel: this._aggregateByChannel(memories as Array<Record<string, unknown>>, channels as Array<Record<string, unknown>>),
                        recent: (memories as Array<Record<string, unknown>>).slice(0, 10).map(m => ({
                            id: m.id || m.memory_id,
                            channel: m.channel_name,
                            type: m.memory_type,
                            created_at: m.created_at
                        })),
                        topChannels: this._getTopChannels(channels as Array<Record<string, unknown>>, 10)
                    },
                    documents: {
                        total: Array.isArray(documents) ? documents.length : 0,
                        byType: this._aggregateByType(documents as Array<Record<string, unknown>>, 'file_type'),
                        totalChunks: (documents as Array<Record<string, unknown>>).reduce((sum: number, doc: Record<string, unknown>) => sum + ((doc.chunk_count as number) || 0), 0),
                        recent: (documents as Array<Record<string, unknown>>).slice(0, 10).map(doc => ({
                            id: doc.id,
                            file_name: doc.file_name,
                            file_type: doc.file_type,
                            chunk_count: doc.chunk_count || 0,
                            uploaded_at: doc.uploaded_at,
                            uploaded_by: doc.uploaded_by
                        })),
                        storage: {
                            totalDocuments: Array.isArray(documents) ? documents.length : 0,
                            totalChunks: (documents as Array<Record<string, unknown>>).reduce((sum: number, doc: Record<string, unknown>) => sum + ((doc.chunk_count as number) || 0), 0),
                            avgChunksPerDoc: Array.isArray(documents) && documents.length > 0 
                                ? Math.round((documents as Array<Record<string, unknown>>).reduce((sum: number, doc: Record<string, unknown>) => sum + ((doc.chunk_count as number) || 0), 0) / documents.length)
                                : 0
                        }
                    },
                    performance: {
                        avgLatency: this.performanceMetrics.avgResponseTime,
                        cacheHitRate: this.performanceMetrics.requestCount > 0
                            ? (this.performanceMetrics.cacheHits / this.performanceMetrics.requestCount) * 100
                            : 0,
                        totalQueries: this.performanceMetrics.requestCount,
                        websocket: {
                            connected: this.clients.size,
                            enabled: this.io !== null
                        }
                    },
                    timestamp: new Date().toISOString()
                };

                // Cache the result
                this.cache.analytics.data = analytics;
                this.cache.analytics.timestamp = now;

                res.json({
                    ...analytics,
                    cached: false
                });
            } catch (error) {
                console.error('[API] Error fetching analytics:', error);
                // Return cached analytics if available
                if (this.cache.analytics.data) {
                    return res.json({
                        ...(this.cache.analytics.data as Record<string, unknown>),
                        cached: true,
                        stale: true,
                        error: 'Using cached data due to fetch error',
                        timestamp: new Date().toISOString()
                    });
                }
                const err = error as Error;
                res.status(500).json({ 
                    error: 'Failed to fetch analytics',
                    details: err.message,
                    timestamp: new Date().toISOString()
                });
            }
        });

        // Metrics endpoint - Combined metrics from metricsCollector and gopher agent (if available)
        this.app.get('/api/metrics', async (req: Request, res: Response) => {
            try {
                const botMetrics = metricsCollector.getMetricsJSON();
                
                let gopherMetrics: Record<string, unknown> | null = null;
                const metricsUrl = process.env.GOPHER_AGENT_URL || 'http://localhost:8001/get_metrics';
                
                try {
                    const urlObj = new URL(metricsUrl);
                    const client = urlObj.protocol === 'https:' ? https : http;
                    
                    gopherMetrics = await new Promise<Record<string, unknown>>((resolve, reject) => {
                        const req = client.get(metricsUrl, (res) => {
                            let data = '';
                            res.on('data', (chunk: Buffer) => data += chunk.toString());
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
                        
                        req.on('error', (err: Error) => {
                            clearTimeout(timeout);
                            reject(err);
                        });
                    });
                } catch (error) {
                    // Gopher agent not available - that's okay, we'll use bot metrics only
                    console.log('[Metrics] Gopher agent not available, using bot metrics only');
                }
                
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
                    websocket: {
                        connected: this.clients.size,
                        enabled: this.io !== null
                    },
                    performance: {
                        avgResponseTime: this.performanceMetrics.avgResponseTime,
                        cacheHitRate: this.performanceMetrics.requestCount > 0
                            ? (this.performanceMetrics.cacheHits / this.performanceMetrics.requestCount) * 100
                            : 0,
                        totalRequests: this.performanceMetrics.requestCount
                    },
                    timestamp: new Date().toISOString()
                });
            } catch (error) {
                console.error('[API] Error fetching metrics:', error);
                const err = error as Error;
                res.status(500).json({ 
                    error: 'Failed to fetch metrics',
                    details: err.message,
                    timestamp: new Date().toISOString()
                });
            }
        });
        
        // Cache control endpoint
        this.app.post('/api/cache/clear', (req: Request, res: Response) => {
            const { type } = req.body;
            this.clearCache(type);
            res.json({ 
                success: true, 
                message: `Cache cleared: ${type || 'all'}`,
                timestamp: new Date().toISOString()
            });
        });
        
        // Test endpoint
        this.app.get('/api/test', (req: Request, res: Response) => {
            res.json({ 
                status: 'ok', 
                message: 'Web server is working',
                websocket: {
                    connected: this.clients.size,
                    enabled: this.io !== null
                },
                timestamp: new Date().toISOString()
            });
        });
        
        // Serve static files AFTER API routes
        this.app.use(express.static(path.join(__dirname, '..', 'public'), {
            maxAge: '1d',
            etag: true,
            lastModified: true,
            setHeaders: (res: Response, path: string) => {
                // Add cache headers for static assets
                if (path.endsWith('.html')) {
                    res.setHeader('Cache-Control', 'no-cache');
                } else if (path.endsWith('.js') || path.endsWith('.css')) {
                    res.setHeader('Cache-Control', 'public, max-age=31536000, immutable');
                }
            }
        }));
        
        // Serve main page (fallback if static file doesn't exist)
        this.app.get('/', (req: Request, res: Response) => {
            res.sendFile(path.join(__dirname, '..', 'public', 'index.html'));
        });
        
        // 404 handler for API routes
        this.app.use('/api/*', (req: Request, res: Response) => {
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
    setupErrorHandling(): void {
        // Global error handler
        this.app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
            console.error('[Error]', err);
            
            const isDevelopment = process.env.NODE_ENV === 'development';
            
            res.status((err as Error & { status?: number }).status || 500).json({
                error: err.message || 'Internal server error',
                details: isDevelopment ? err.stack : undefined,
                timestamp: new Date().toISOString()
            });
        });
        
        // Handle unhandled promise rejections
        process.on('unhandledRejection', (reason: unknown) => {
            console.error('[Unhandled Rejection]', reason);
        });
        
        // Handle uncaught exceptions
        process.on('uncaughtException', (error: Error) => {
            console.error('[Uncaught Exception]', error);
            if (process.env.NODE_ENV === 'production') {
                process.exit(1);
            }
        });
    }
    
    /**
     * Check if cache is still valid
     */
    isCacheValid(type: 'channels' | 'documents' | 'analytics' | 'status'): boolean {
        const now = Date.now();
        const cacheEntry = this.cache[type];
        return cacheEntry.data !== null && (now - cacheEntry.timestamp) < this.cacheTTL;
    }
    
    /**
     * Clear cache (useful for manual refresh)
     */
    clearCache(type: 'channels' | 'documents' | 'analytics' | 'status' | null = null): void {
        if (type === 'channels' || type === null) {
            this.cache.channels.data = null;
            this.cache.channels.timestamp = 0;
        }
        if (type === 'documents' || type === null) {
            this.cache.documents.data = null;
            this.cache.documents.timestamp = 0;
        }
        if (type === 'analytics' || type === null) {
            this.cache.analytics.data = null;
            this.cache.analytics.timestamp = 0;
        }
        if (type === 'status' || type === null) {
            this.cache.status.data = null;
            this.cache.status.timestamp = 0;
        }
        
        // Broadcast cache clear event
        if (this.io) {
            this.io.emit('cache-cleared', { type: type || 'all' });
        }
    }

    /**
     * Aggregate items by a specific field
     */
    private _aggregateByType(items: Array<Record<string, unknown>>, field: string): Record<string, number> {
        const aggregated: Record<string, number> = {};
        items.forEach(item => {
            const type = (item[field] as string) || 'unknown';
            aggregated[type] = (aggregated[type] || 0) + 1;
        });
        return aggregated;
    }

    /**
     * Aggregate memories by channel
     */
    private _aggregateByChannel(memories: Array<Record<string, unknown>>, channels: Array<Record<string, unknown>>): Array<Record<string, unknown>> {
        const channelMap = new Map<string, Record<string, unknown>>();
        channels.forEach(ch => {
            const channelId = (ch.channel_id || ch.id) as string;
            channelMap.set(channelId, {
                channel_id: channelId,
                channel_name: (ch.channel_name as string) || 'Unknown',
                memory_count: 0
            });
        });
        
        memories.forEach(memory => {
            const channelId = memory.channel_id as string;
            if (channelId && channelMap.has(channelId)) {
                const channel = channelMap.get(channelId)!;
                channel.memory_count = ((channel.memory_count as number) || 0) + 1;
            }
        });
        
        return Array.from(channelMap.values())
            .sort((a, b) => ((b.memory_count as number) || 0) - ((a.memory_count as number) || 0))
            .slice(0, 20);
    }

    /**
     * Get top channels by memory count
     */
    private _getTopChannels(channels: Array<Record<string, unknown>>, limit = 10): Array<Record<string, unknown>> {
        return channels
            .sort((a, b) => ((b.memory_count as number) || 0) - ((a.memory_count as number) || 0))
            .slice(0, limit)
            .map(ch => ({
                channel_id: ch.channel_id || ch.id,
                channel_name: ch.channel_name || 'Unknown',
                memory_count: ch.memory_count || 0
            }));
    }
    
    /**
     * Start the web server
     */
    start(): Promise<void> {
        return new Promise((resolve, reject) => {
            try {
                this.httpServer = this.app.listen(this.port, () => {
                    console.log(`🌐 Web interface running at http://localhost:${this.port}`);
                    console.log(`🌐 Health check: http://localhost:${this.port}/api/health`);
                    console.log(`🌐 Test endpoint: http://localhost:${this.port}/api/test`);
                    
                    // Setup WebSocket after HTTP server is ready
                    this.setupWebSocket();
                    
                    resolve();
                });
                
                this.httpServer.on('error', (error: Error) => {
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
    stop(): Promise<void> {
        return new Promise((resolve) => {
            // Stop broadcasting
            if (this.broadcastInterval) {
                clearInterval(this.broadcastInterval);
                this.broadcastInterval = null;
            }
            
            // Close WebSocket connections
            if (this.io) {
                this.io.close();
                this.io = null;
            }
            
            // Close HTTP server
            if (this.httpServer) {
                this.httpServer.close(() => {
                    console.log('[WebServer] Server stopped');
                    resolve();
                });
            } else {
                resolve();
            }
        });
    }
}

export default WebServer;
