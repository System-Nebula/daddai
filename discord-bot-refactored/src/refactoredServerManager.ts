/**
 * Manages refactored A2A and RAG HTTP servers.
 * Starts and monitors both servers when the Discord bot starts.
 */
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import * as http from 'http';
import * as https from 'https';
import { URL } from 'url';
import logger from './logger.js';

// Get __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface ServerInfo {
    name: string;
    process: ChildProcess | null;
    host: string;
    port: number;
    healthEndpoint: string;
    isReady: boolean;
    startupScript: string;
}

class RefactoredServerManager {
    private pythonPath: string;
    private agentServer: ServerInfo;
    private ragServer: ServerInfo;
    private healthCheckInterval: NodeJS.Timeout | null = null;
    private maxStartupWaitTime = 60000; // 60 seconds
    private healthCheckIntervalMs = 10000; // Check every 10 seconds

    constructor() {
        this.pythonPath = process.env.PYTHON_PATH || 'python';
        
        // Agent Server (A2A) configuration
        this.agentServer = {
            name: 'Refactored Agent Server (A2A)',
            process: null,
            host: process.env.REFACTORED_AGENT_HOST || 'localhost',
            port: parseInt(process.env.REFACTORED_AGENT_PORT || '8766', 10),
            healthEndpoint: '/health',
            isReady: false,
            startupScript: 'Refactored.scripts.start_refactored_agent_server' // Python module path
        };
        
        // RAG Server configuration
        this.ragServer = {
            name: 'Refactored RAG Server',
            process: null,
            host: process.env.REFACTORED_RAG_HOST || 'localhost',
            port: parseInt(process.env.REFACTORED_RAG_PORT || '8767', 10),
            healthEndpoint: '/health',
            isReady: false,
            startupScript: 'Refactored.scripts.start_refactored_rag_server' // Python module path
        };
    }

    /**
     * Start both servers
     */
    async startAll(): Promise<void> {
        logger.info('🚀 Starting refactored servers...');
        
        // Start both servers in parallel
        const [agentReady, ragReady] = await Promise.all([
            this.startServer(this.agentServer),
            this.startServer(this.ragServer)
        ]);

        if (!agentReady) {
            throw new Error('Failed to start Refactored Agent Server');
        }
        if (!ragReady) {
            throw new Error('Failed to start Refactored RAG Server');
        }

        logger.info('✅ All refactored servers started successfully');
        
        // Start health check monitoring
        this.startHealthChecks();
    }

    /**
     * Start a single server
     */
    private async startServer(server: ServerInfo): Promise<boolean> {
        return new Promise((resolve) => {
            // Prevent concurrent starts
            if (server.process !== null) {
                logger.debug(`${server.name} is already starting/running, skipping...`);
                resolve(server.isReady);
                return;
            }

            logger.info(`Starting ${server.name}...`);
            
            // Check if server is already running
            this.checkServerHealth(server).then((isHealthy) => {
                if (isHealthy) {
                    logger.info(`✅ ${server.name} is already running`);
                    server.isReady = true;
                    resolve(true);
                    return;
                }

                // Start the server process using Python module syntax
                try {
                    const projectRoot = path.join(__dirname, '..', '..');
                    server.process = spawn(this.pythonPath, ['-m', server.startupScript], {
                        stdio: ['pipe', 'pipe', 'pipe'],
                        cwd: projectRoot,
                        env: {
                            ...process.env,
                            REFACTORED_AGENT_HOST: this.agentServer.host,
                            REFACTORED_AGENT_PORT: this.agentServer.port.toString(),
                            REFACTORED_RAG_HOST: this.ragServer.host,
                            REFACTORED_RAG_PORT: this.ragServer.port.toString()
                        }
                    });

                    let startupOutput = '';
                    let startupTimeout: NodeJS.Timeout;

                    // Handle stderr (debug output)
                    server.process.stderr?.on('data', (data: Buffer) => {
                        const output = data.toString();
                        startupOutput += output;
                        console.log(`[${server.name}] ${output.trim()}`);
                    });

                    // Handle stdout
                    server.process.stdout?.on('data', (data: Buffer) => {
                        const output = data.toString();
                        console.log(`[${server.name}] ${output.trim()}`);
                    });

                    // Handle process exit
                    server.process.on('exit', (code) => {
                        if (code !== 0 && code !== null) {
                            logger.error(`❌ ${server.name} exited with code ${code}`);
                            server.isReady = false;
                            server.process = null;
                        }
                    });

                    // Handle process errors
                    server.process.on('error', (error) => {
                        logger.error(`❌ Failed to start ${server.name}:`, error);
                        server.isReady = false;
                        server.process = null;
                        resolve(false);
                    });

                    // Wait for server to be ready
                    startupTimeout = setTimeout(() => {
                        logger.warn(`⏱️  ${server.name} startup timeout, checking health...`);
                        this.checkServerHealth(server).then((isHealthy) => {
                            if (isHealthy) {
                                server.isReady = true;
                                resolve(true);
                            } else {
                                logger.error(`❌ ${server.name} failed to start within timeout`);
                                resolve(false);
                            }
                        });
                    }, this.maxStartupWaitTime);

                    // Poll for server readiness
                    const checkInterval = setInterval(async () => {
                        const isHealthy = await this.checkServerHealth(server);
                        if (isHealthy) {
                            clearInterval(checkInterval);
                            clearTimeout(startupTimeout);
                            server.isReady = true;
                            logger.info(`✅ ${server.name} is ready!`);
                            resolve(true);
                        }
                    }, 2000); // Check every 2 seconds

                } catch (error) {
                    logger.error(`❌ Error starting ${server.name}:`, error);
                    resolve(false);
                }
            });
        });
    }

    /**
     * Check server health
     */
    private async checkServerHealth(server: ServerInfo): Promise<boolean> {
        return new Promise((resolve) => {
            const url = new URL(`http://${server.host}:${server.port}${server.healthEndpoint}`);
            const options = {
                hostname: url.hostname,
                port: url.port,
                path: url.pathname,
                method: 'GET',
                timeout: 5000
            };

            const req = http.request(options, (res) => {
                let data = '';
                res.on('data', (chunk) => {
                    data += chunk.toString();
                });
                res.on('end', () => {
                    if (res.statusCode === 200) {
                        try {
                            const result = JSON.parse(data);
                            resolve(result.status === 'ok' && result.initialized !== false);
                        } catch {
                            resolve(false);
                        }
                    } else {
                        resolve(false);
                    }
                });
            });

            req.on('error', () => {
                resolve(false);
            });

            req.on('timeout', () => {
                req.destroy();
                resolve(false);
            });

            req.end();
        });
    }

    /**
     * Start periodic health checks
     */
    private startHealthChecks(): void {
        this.healthCheckInterval = setInterval(async () => {
            const agentHealthy = await this.checkServerHealth(this.agentServer);
            const ragHealthy = await this.checkServerHealth(this.ragServer);

            if (!agentHealthy && this.agentServer.isReady) {
                logger.warn(`⚠️  ${this.agentServer.name} health check failed`);
                this.agentServer.isReady = false;
            }

            if (!ragHealthy && this.ragServer.isReady) {
                logger.warn(`⚠️  ${this.ragServer.name} health check failed`);
                this.ragServer.isReady = false;
            }

            // Attempt to restart if servers are down (but not if already starting)
            if (!agentHealthy && !this.agentServer.process && !this.agentServer.isReady) {
                logger.warn(`⚠️  ${this.agentServer.name} is not healthy, attempting restart...`);
                this.startServer(this.agentServer).catch((err) => {
                    logger.error(`Failed to restart ${this.agentServer.name}:`, err);
                });
            }

            if (!ragHealthy && !this.ragServer.process && !this.ragServer.isReady) {
                logger.warn(`⚠️  ${this.ragServer.name} is not healthy, attempting restart...`);
                this.startServer(this.ragServer).catch((err) => {
                    logger.error(`Failed to restart ${this.ragServer.name}:`, err);
                });
            }
        }, this.healthCheckIntervalMs);
    }

    /**
     * Stop all servers
     */
    async stopAll(): Promise<void> {
        logger.info('🛑 Stopping refactored servers...');

        if (this.healthCheckInterval) {
            clearInterval(this.healthCheckInterval);
            this.healthCheckInterval = null;
        }

        const stopPromises: Promise<void>[] = [];

        // Stop agent server
        if (this.agentServer.process) {
            const stopPromise = new Promise<void>((resolve) => {
                const process = this.agentServer.process!;
                
                // Set up exit handler
                const onExit = () => {
                    logger.info(`✅ ${this.agentServer.name} stopped`);
                    resolve();
                };
                
                process.on('exit', onExit);
                process.on('close', onExit);
                
                // Send SIGTERM for graceful shutdown
                try {
                    process.kill('SIGTERM');
                    
                    // Force kill after 5 seconds if still running
                    setTimeout(() => {
                        if (process && !process.killed) {
                            logger.warn(`⚠️  ${this.agentServer.name} didn't stop gracefully, forcing kill...`);
                            try {
                                process.kill('SIGKILL');
                            } catch (e) {
                                // Process already dead
                            }
                            resolve();
                        }
                    }, 5000);
                } catch (error) {
                    logger.warn(`Error stopping ${this.agentServer.name}:`, error);
                    resolve();
                }
            });
            
            stopPromises.push(stopPromise);
            this.agentServer.process = null;
            this.agentServer.isReady = false;
        }

        // Stop RAG server
        if (this.ragServer.process) {
            const stopPromise = new Promise<void>((resolve) => {
                const process = this.ragServer.process!;
                
                // Set up exit handler
                const onExit = () => {
                    logger.info(`✅ ${this.ragServer.name} stopped`);
                    resolve();
                };
                
                process.on('exit', onExit);
                process.on('close', onExit);
                
                // Send SIGTERM for graceful shutdown
                try {
                    process.kill('SIGTERM');
                    
                    // Force kill after 5 seconds if still running
                    setTimeout(() => {
                        if (process && !process.killed) {
                            logger.warn(`⚠️  ${this.ragServer.name} didn't stop gracefully, forcing kill...`);
                            try {
                                process.kill('SIGKILL');
                            } catch (e) {
                                // Process already dead
                            }
                            resolve();
                        }
                    }, 5000);
                } catch (error) {
                    logger.warn(`Error stopping ${this.ragServer.name}:`, error);
                    resolve();
                }
            });
            
            stopPromises.push(stopPromise);
            this.ragServer.process = null;
            this.ragServer.isReady = false;
        }

        // Wait for all servers to stop (with timeout)
        if (stopPromises.length > 0) {
            await Promise.race([
                Promise.all(stopPromises),
                new Promise<void>((resolve) => setTimeout(resolve, 6000)) // 6 second max wait
            ]);
        }
        
        logger.info('✅ All refactored servers stopped');
    }

    /**
     * Check if all servers are ready
     */
    areAllReady(): boolean {
        return this.agentServer.isReady && this.ragServer.isReady;
    }

    /**
     * Get server status
     */
    getStatus(): { agent: boolean; rag: boolean } {
        return {
            agent: this.agentServer.isReady,
            rag: this.ragServer.isReady
        };
    }
}

// Export singleton instance
const serverManager = new RefactoredServerManager();
export default serverManager;

