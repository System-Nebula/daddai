/**
 * Message handlers extracted from index.js for better organization.
 * Handles question processing and document uploads.
 */

const logger = require('../logger');

/**
 * Check if a question likely needs RAG (document search)
 * Extracted from index.js for better organization
 */
function needsRAG(question) {
    const lowerQuestion = question.toLowerCase();
    
    // Check for state queries about OTHER users (with mentions) - these need RAG for state query handler
    const hasUserMention = /<@!?\d+>/.test(question);
    const isStateQueryAboutOther = hasUserMention && /(?:how many|how much|what).*(?:gold|coins?|inventory|items?|balance).*(?:does|do|has|have|owns)/i.test(question);
    
    // If query has mentions, route through RAG so LLM can detect actions, state queries, etc.
    if (hasUserMention && !isStateQueryAboutOther) {
        const isSelfQuery = /(?:how many|how much|what).*(?:do i|have i|do you know).*(?:gold|coins?|inventory|items?)/i.test(question);
        if (!isSelfQuery) {
            return true;
        }
    }
    
    // EXCLUDE: User fact questions about SELF that should use memory, not RAG
    const userFactPatterns = [
        /(?:what do i have|what's in my|my inventory|my coins|my gold|i have|i own|i gave|i'm going|i'm leaving)/i,
        /(?:inventory|coins?|gold|pieces?|apples?|items?|things?)\s+(?:do i have|in my|i have|i own)/i,
        /(?:i've given|i gave|i'm going to give)/i,
        /(?:how many|how much)\s+(?:do i|have i|do you know).*(?:gold|coins?|inventory|items?)/i,
        /(?:keep track|remember|set).*(?:me|i|my).*(?:having|with|of).*\d+.*(?:gold|coins?|pieces?)/i,
        /(?:i have|i own|i'm|i am).*\d+.*(?:gold|coins?|pieces?)/i,
        /(?:set|update|change).*(?:my|me|i).*(?:gold|coins?).*to.*\d+/i,
    ];
    
    if (isStateQueryAboutOther) {
        return true;
    }
    
    for (const pattern of userFactPatterns) {
        if (pattern.test(question)) {
            return false;
        }
    }
    
    // Always use RAG for questions that mention specific files/documents
    const documentKeywords = [
        'document', 'file', 'pdf', 'text', 'content', 'chapter', 'section',
        'paper', 'article', 'title', 'author', 'contributed', 'contributor',
        'uploaded', 'upload', 'new document', 'build log', 'build logs',
        'report', 'reports', 'study', 'studies', 'analysis', 'analyses',
        'whitepaper', 'white paper', 'guide', 'manual', 'handbook'
    ];
    
    for (const keyword of documentKeywords) {
        if (lowerQuestion.includes(keyword)) {
            return true;
        }
    }
    
    // Check if question mentions a filename pattern
    if (/\b[\w\-\.]+\.(pdf|docx?|txt|md|log|csv)\b/i.test(question) || 
        /\b\d{4}\.\d{5}/.test(question)) {
        return true;
    }
    
    // Check for factual questions that likely need document search
    const factualPatterns = [
        /^what (is|are|was|were|does|do|did|will|can|could)/i,
        /^who (is|are|was|were|did|does|do|will|can|could)/i,
        /^when (is|are|was|were|did|does|do|will|can|could)/i,
        /^where (is|are|was|were|did|does|do|will|can|could)/i,
        /^how (is|are|was|were|did|does|do|will|can|could)/i,
        /^tell me (about|what|who|when|where|how)/i,
        /^explain/i,
        /^describe/i,
        /^according to/i,
        /^based on/i,
        /^from the/i,
        /^in the/i
    ];
    
    for (const pattern of factualPatterns) {
        if (pattern.test(question.trim())) {
            return true;
        }
    }
    
    // EXCLUDE: Casual conversation
    const casualPatterns = [
        /^(hi|hello|hey|hiya|greetings|good morning|good afternoon|good evening)[\s!.,]*$/i,
        /^(hi|hello|hey)\s+(there|everyone|all|guys|folks)[\s!.,]*$/i,
        /^(hi|hello|hey),?\s*(i'?m|i am|my name is|this is)\s+/i,
        /^(i'?m|i am|my name is|this is)\s+[\w\s]+$/i,
        /^(how are you|how's it going|what's up|sup|wassup|howdy)[\s!.,]*$/i,
        /^(thanks|thank you|thx|ty|bye|goodbye|see ya|cya|ok|okay|yes|no|yep|nope|sure|alright)[\s!.,]*$/i,
        /^(lol|haha|hehe|rofl|lmao|nice|cool|awesome|great)[\s!.,]*$/i,
        /^(just|yeah|yep|nope|sure|ok|okay|alright|fine|good|nice|cool|awesome|great)[\s!.,]*$/i,
        /^.{1,30}$/i
    ];
    
    for (const pattern of casualPatterns) {
        if (pattern.test(question.trim())) {
            return false;
        }
    }
    
    // EXCLUDE: Personal statements without questions
    if (!question.includes('?') && 
        !/^(what|who|when|where|how|why|tell|explain|describe|show|list|find|search|get|give)/i.test(question.trim()) &&
        /^(i|i'm|i am|my|me|we|we're|we are)/i.test(question.trim())) {
        return false;
    }
    
    // Default to RAG for questions
    return true;
}

module.exports = {
    needsRAG
};

