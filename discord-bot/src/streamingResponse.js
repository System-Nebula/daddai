/**
 * Streaming response handler for long operations.
 * Uses Discord message editing to show progress for RAG queries, image generation, etc.
 */
const logger = require('./logger');

class StreamingResponse {
    /**
     * @param {Object} message - Discord message object
     * @param {Object} options - Streaming options
     * @param {number} options.updateInterval - Minimum interval between updates in ms (default: 1000)
     * @param {number} options.maxLength - Maximum message length before chunking (default: 2000)
     */
    constructor(message, options = {}) {
        this.message = message;
        this.updateInterval = options.updateInterval || 1000; // 1 second
        this.maxLength = options.maxLength || 2000;
        
        this.statusMessage = null;
        this.lastUpdate = 0;
        this.buffer = '';
        this.isComplete = false;
        this.chunks = [];
    }
    
    /**
     * Initialize streaming response with initial message
     * @param {string} initialText - Initial status text
     * @returns {Promise<void>}
     */
    async initialize(initialText = 'Processing...') {
        try {
            this.statusMessage = await this.message.reply({
                content: initialText,
                allowedMentions: { repliedUser: false }
            });
            logger.debug('[StreamingResponse] Initialized', {
                messageId: this.message.id,
                statusMessageId: this.statusMessage.id
            });
        } catch (error) {
            logger.error('[StreamingResponse] Failed to initialize', {
                error: error.message,
                messageId: this.message.id
            });
            // Continue without streaming if initialization fails
        }
    }
    
    /**
     * Update status message (throttled)
     * @param {string} text - Status text
     * @param {boolean} force - Force update even if within interval
     * @returns {Promise<void>}
     */
    async update(text, force = false) {
        if (this.isComplete || !this.statusMessage) return;
        
        const now = Date.now();
        if (!force && (now - this.lastUpdate) < this.updateInterval) {
            // Buffer the update
            this.buffer = text;
            return;
        }
        
        try {
            // Handle long messages by chunking
            if (text.length > this.maxLength) {
                await this._chunkAndSend(text);
            } else {
                await this.statusMessage.edit({
                    content: text,
                    allowedMentions: { repliedUser: false }
                });
            }
            
            this.lastUpdate = now;
            this.buffer = '';
        } catch (error) {
            logger.error('[StreamingResponse] Failed to update', {
                error: error.message,
                messageId: this.message.id,
                statusMessageId: this.statusMessage?.id
            });
        }
    }
    
    /**
     * Chunk long message and send as multiple messages
     * @param {string} text - Long text to chunk
     * @returns {Promise<void>}
     */
    async _chunkAndSend(text) {
        const chunks = this._splitIntoChunks(text, this.maxLength - 100); // Leave room for continuation markers
        
        for (let i = 0; i < chunks.length; i++) {
            const chunk = chunks[i];
            const isLast = i === chunks.length - 1;
            const chunkText = isLast ? chunk : `${chunk}\n\n*[Continued...]*`;
            
            if (i === 0) {
                // Update first message
                await this.statusMessage.edit({
                    content: chunkText,
                    allowedMentions: { repliedUser: false }
                });
            } else {
                // Send additional chunks as new messages
                try {
                    await this.message.channel.send({
                        content: chunkText,
                        allowedMentions: { repliedUser: false }
                    });
                } catch (error) {
                    logger.error('[StreamingResponse] Failed to send chunk', {
                        error: error.message,
                        chunkIndex: i
                    });
                }
            }
        }
    }
    
    /**
     * Split text into chunks at word boundaries
     * @param {string} text - Text to split
     * @param {number} maxChunkSize - Maximum chunk size
     * @returns {Array<string>} Array of chunks
     */
    _splitIntoChunks(text, maxChunkSize) {
        const chunks = [];
        let currentChunk = '';
        
        // Split by paragraphs first
        const paragraphs = text.split(/\n\n+/);
        
        for (const paragraph of paragraphs) {
            if (currentChunk.length + paragraph.length + 2 <= maxChunkSize) {
                // Add to current chunk
                if (currentChunk) {
                    currentChunk += '\n\n' + paragraph;
                } else {
                    currentChunk = paragraph;
                }
            } else {
                // Save current chunk and start new one
                if (currentChunk) {
                    chunks.push(currentChunk);
                }
                
                // If paragraph itself is too long, split by sentences
                if (paragraph.length > maxChunkSize) {
                    const sentences = paragraph.split(/[.!?]+\s+/);
                    for (const sentence of sentences) {
                        if (currentChunk.length + sentence.length + 2 <= maxChunkSize) {
                            currentChunk += (currentChunk ? ' ' : '') + sentence;
                        } else {
                            if (currentChunk) {
                                chunks.push(currentChunk);
                            }
                            currentChunk = sentence;
                        }
                    }
                } else {
                    currentChunk = paragraph;
                }
            }
        }
        
        if (currentChunk) {
            chunks.push(currentChunk);
        }
        
        return chunks.length > 0 ? chunks : [text];
    }
    
    /**
     * Stream text incrementally (for LLM responses)
     * @param {string} text - Text to stream
     * @param {number} chunkSize - Size of each chunk (default: 50)
     * @returns {Promise<void>}
     */
    async streamText(text, chunkSize = 50) {
        let position = 0;
        
        while (position < text.length) {
            const chunk = text.substring(position, position + chunkSize);
            position += chunkSize;
            
            // Update with accumulated text
            await this.update(text.substring(0, position) + (position < text.length ? '...' : ''), false);
            
            // Small delay to prevent rate limiting
            await new Promise(resolve => setTimeout(resolve, 100));
        }
    }
    
    /**
     * Update with progress indicator
     * @param {string} status - Status text
     * @param {number} progress - Progress percentage (0-100)
     * @returns {Promise<void>}
     */
    async updateProgress(status, progress) {
        const progressBar = this._createProgressBar(progress);
        const text = `${status}\n${progressBar} ${progress}%`;
        await this.update(text);
    }
    
    /**
     * Create ASCII progress bar
     * @param {number} progress - Progress percentage (0-100)
     * @param {number} width - Bar width (default: 20)
     * @returns {string} Progress bar string
     */
    _createProgressBar(progress, width = 20) {
        const filled = Math.round((progress / 100) * width);
        const empty = width - filled;
        return `[${'█'.repeat(filled)}${'░'.repeat(empty)}]`;
    }
    
    /**
     * Finalize streaming response
     * @param {string} finalText - Final response text
     * @returns {Promise<void>}
     */
    async finalize(finalText) {
        this.isComplete = true;
        
        // Flush any buffered updates
        if (this.buffer) {
            await this.update(this.buffer, true);
        }
        
        // Send final message
        if (this.statusMessage) {
            try {
                if (finalText.length > this.maxLength) {
                    await this._chunkAndSend(finalText);
                } else {
                    await this.statusMessage.edit({
                        content: finalText,
                        allowedMentions: { repliedUser: false }
                    });
                }
            } catch (error) {
                logger.error('[StreamingResponse] Failed to finalize', {
                    error: error.message,
                    messageId: this.message.id
                });
            }
        }
    }
    
    /**
     * Cancel streaming response
     * @param {string} cancelText - Cancellation message
     * @returns {Promise<void>}
     */
    async cancel(cancelText = 'Operation cancelled') {
        this.isComplete = true;
        
        if (this.statusMessage) {
            try {
                await this.statusMessage.edit({
                    content: cancelText,
                    allowedMentions: { repliedUser: false }
                });
            } catch (error) {
                logger.error('[StreamingResponse] Failed to cancel', {
                    error: error.message
                });
            }
        }
    }
}

module.exports = StreamingResponse;

