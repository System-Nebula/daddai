/**
 * ToolDetector - Class-based tool detection and routing for Discord bot.
 * Replaces hardcoded pattern matching with a maintainable, extensible system.
 */
import { logger } from '../utils/logger';

export interface ToolDetectionResult {
    needsTools: boolean;
    needsRAG: boolean;
    toolType?: 'image_generation' | 'youtube' | 'website' | 'image_analysis' | 'code' | 'memory' | 'other';
    confidence: number;
    detectedPattern?: string;
}

export interface IntentResult {
    intent: string;
    should_respond: boolean;
    needs_rag: boolean;
    needs_tools: boolean;
    is_casual?: boolean;
}

export class ToolDetector {
    private imageGenerationPatterns: RegExp[];
    private urlPatterns: RegExp[];
    private youtubePatterns: RegExp[];
    private websitePatterns: RegExp[];
    private codePatterns: RegExp[];
    private memoryPatterns: RegExp[];

    constructor() {
        // Image generation patterns
        this.imageGenerationPatterns = [
            /generate.*image|create.*image|make.*image|draw.*image|image.*of|picture.*of|art.*of|visualize|illustrate/i,
            /(?:show|give|make|create|generate|draw).*me.*(?:a|an|the).*(?:image|picture|photo|art|illustration|visualization)/i,
            /(?:I want|I need|can you).*(?:a|an|the).*(?:image|picture|photo|art)/i,
            /(?:create|generate|make|draw).*(?:an?|the).*(?:image|picture|photo|art|illustration)/i
        ];

        // URL patterns
        this.urlPatterns = [
            /(?:https?:\/\/|www\.)/i,
            /youtube\.com|youtu\.be/i
        ];

        // YouTube-specific patterns
        this.youtubePatterns = [
            /youtube\.com|youtu\.be/i,
            /watch\?v=|youtu\.be\//
        ];

        // Website patterns (non-YouTube URLs)
        this.websitePatterns = [
            /https?:\/\/(?!.*youtube\.com|.*youtu\.be)/i
        ];

        // Code execution patterns
        this.codePatterns = [
            /calculate|compute|solve|math|equation|formula|code|program|script/i,
            /what is.*\d|how many|how much.*\d/
        ];

        // Memory patterns
        this.memoryPatterns = [
            /remember|recall|forget|memory|memories|what did.*say|what.*told.*you/i
        ];
    }

    /**
     * Detect if a message needs tools and what type.
     */
    detectTools(question: string, intent?: IntentResult): ToolDetectionResult {
        const cleanedQuestion = this.cleanQuestion(question);
        
        // Check image generation first (highest priority)
        const imageGen = this.detectImageGeneration(cleanedQuestion);
        if (imageGen.needsTools) {
            return imageGen;
        }

        // Check URLs (high priority)
        const url = this.detectURL(cleanedQuestion);
        if (url.needsTools) {
            return url;
        }

        // Check code execution
        const code = this.detectCodeExecution(cleanedQuestion);
        if (code.needsTools) {
            return code;
        }

        // Check memory operations
        const memory = this.detectMemoryOperation(cleanedQuestion);
        if (memory.needsTools) {
            return memory;
        }

        // Use intent if provided
        if (intent?.needs_tools) {
            return {
                needsTools: true,
                needsRAG: intent.needs_rag || false,
                toolType: 'other',
                confidence: 0.7
            };
        }

        return {
            needsTools: false,
            needsRAG: false,
            confidence: 0.0
        };
    }

    /**
     * Detect image generation requests.
     */
    detectImageGeneration(question: string): ToolDetectionResult {
        for (const pattern of this.imageGenerationPatterns) {
            if (pattern.test(question)) {
                logger.debug(`Image generation detected: "${question.substring(0, 100)}"`);
                return {
                    needsTools: true,
                    needsRAG: true,
                    toolType: 'image_generation',
                    confidence: 0.95,
                    detectedPattern: pattern.source
                };
            }
        }

        return {
            needsTools: false,
            needsRAG: false,
            confidence: 0.0
        };
    }

    /**
     * Detect URL presence (YouTube or website).
     */
    detectURL(question: string): ToolDetectionResult {
        // Check YouTube first
        for (const pattern of this.youtubePatterns) {
            if (pattern.test(question)) {
                logger.debug(`YouTube URL detected: "${question.substring(0, 100)}"`);
                return {
                    needsTools: true,
                    needsRAG: false,
                    toolType: 'youtube',
                    confidence: 0.98,
                    detectedPattern: pattern.source
                };
            }
        }

        // Check other websites
        for (const pattern of this.websitePatterns) {
            if (pattern.test(question)) {
                logger.debug(`Website URL detected: "${question.substring(0, 100)}"`);
                return {
                    needsTools: true,
                    needsRAG: false,
                    toolType: 'website',
                    confidence: 0.98,
                    detectedPattern: pattern.source
                };
            }
        }

        // Generic URL pattern
        for (const pattern of this.urlPatterns) {
            if (pattern.test(question)) {
                logger.debug(`Generic URL detected: "${question.substring(0, 100)}"`);
                return {
                    needsTools: true,
                    needsRAG: false,
                    toolType: 'website',
                    confidence: 0.90,
                    detectedPattern: pattern.source
                };
            }
        }

        return {
            needsTools: false,
            needsRAG: false,
            confidence: 0.0
        };
    }

    /**
     * Detect code execution needs.
     */
    detectCodeExecution(question: string): ToolDetectionResult {
        for (const pattern of this.codePatterns) {
            if (pattern.test(question)) {
                return {
                    needsTools: true,
                    needsRAG: false,
                    toolType: 'code',
                    confidence: 0.75,
                    detectedPattern: pattern.source
                };
            }
        }

        return {
            needsTools: false,
            needsRAG: false,
            confidence: 0.0
        };
    }

    /**
     * Detect memory operations.
     */
    detectMemoryOperation(question: string): ToolDetectionResult {
        for (const pattern of this.memoryPatterns) {
            if (pattern.test(question)) {
                return {
                    needsTools: true,
                    needsRAG: false,
                    toolType: 'memory',
                    confidence: 0.80,
                    detectedPattern: pattern.source
                };
            }
        }

        return {
            needsTools: false,
            needsRAG: false,
            confidence: 0.0
        };
    }

    /**
     * Clean question for pattern matching.
     */
    private cleanQuestion(question: string): string {
        return question
            .replace(/<@!?\d+>/g, '')  // User mentions
            .replace(/<@&\d+>/g, '')   // Role mentions
            .replace(/<#\d+>/g, '')    // Channel mentions
            .replace(/\s+/g, ' ')      // Normalize whitespace
            .trim();
    }

    /**
     * Update intent based on tool detection (overrides GopherAgent routing if needed).
     */
    updateIntentWithToolDetection(intent: IntentResult, question: string): IntentResult {
        const detection = this.detectTools(question, intent);

        if (detection.needsTools && !intent.needs_tools) {
            logger.info(`Tool detection overriding intent: ${detection.toolType} detected`);
            return {
                ...intent,
                needs_tools: true,
                needs_rag: detection.needsRAG || intent.needs_rag,
                is_casual: false
            };
        }

        return intent;
    }

    /**
     * Check if message should use agentic mode based on tool detection.
     */
    shouldUseAgenticMode(question: string, intent?: IntentResult): boolean {
        const detection = this.detectTools(question, intent);
        
        // Use agentic mode for complex tool-using tasks
        if (detection.needsTools && question.split(/\s+/).length > 15) {
            return true;
        }

        // Use agentic mode for image generation
        if (detection.toolType === 'image_generation') {
            return true;
        }

        // Use agentic mode if intent says so
        if (intent?.needs_tools && intent.needs_rag) {
            return true;
        }

        return false;
    }
}

// Singleton instance
let toolDetectorInstance: ToolDetector | null = null;

export function getToolDetector(): ToolDetector {
    if (!toolDetectorInstance) {
        toolDetectorInstance = new ToolDetector();
    }
    return toolDetectorInstance;
}

