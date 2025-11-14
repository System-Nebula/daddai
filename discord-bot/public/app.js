const API_BASE = '';

let allMemories = [];
let allChannels = [];
let allDocuments = [];
let currentTab = 'memories';
let memoriesOffset = 0;
let memoriesLimit = 25;
let hasMoreMemories = true;
let isLoadingMemories = false;

// Load data on page load
document.addEventListener('DOMContentLoaded', () => {
    loadAllMemories();
    loadChannels();
    loadAllDocuments();
    setupEventListeners();
});

function setupEventListeners() {
    const searchInput = document.getElementById('searchInput');
    const channelFilter = document.getElementById('channelFilter');
    const typeFilter = document.getElementById('typeFilter');
    const documentSearchInput = document.getElementById('documentSearchInput');

    if (searchInput) searchInput.addEventListener('input', () => filterMemories());
    if (channelFilter) channelFilter.addEventListener('change', () => filterMemories());
    if (typeFilter) typeFilter.addEventListener('change', () => filterMemories());
    if (documentSearchInput) documentSearchInput.addEventListener('input', () => filterDocuments());
}

function switchTab(tabName) {
    currentTab = tabName;
    
    // Update tab buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
        if (btn.textContent.toLowerCase().includes(tabName)) {
            btn.classList.add('active');
        }
    });
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`${tabName}Tab`).classList.add('active');
}

async function loadChannels() {
    try {
        const response = await fetch(`${API_BASE}/api/channels`);
        const data = await response.json();
        allChannels = data.channels || [];
        
        // Update channel filter dropdown
        const channelFilter = document.getElementById('channelFilter');
        if (channelFilter) {
            channelFilter.innerHTML = '<option value="">All Channels</option>';
            
            allChannels.forEach(channel => {
                const option = document.createElement('option');
                option.value = channel.channel_id || channel.id;
                option.textContent = `${channel.channel_name || 'Unknown'} (${channel.memory_count || 0})`;
                channelFilter.appendChild(option);
            });
        }

        // Update stats
        document.getElementById('totalChannels').textContent = allChannels.length;
    } catch (error) {
        console.error('Error loading channels:', error);
    }
}

async function loadAllMemories(reset = false) {
    if (isLoadingMemories) return;
    
    const memoriesList = document.getElementById('memoriesList');
    
    if (reset) {
        memoriesOffset = 0;
        allMemories = [];
        memoriesList.innerHTML = '<div class="loading"><span class="code-comment">// Loading memories...</span></div>';
    } else if (memoriesOffset === 0) {
        memoriesList.innerHTML = '<div class="loading"><span class="code-comment">// Loading memories...</span></div>';
    }
    
    isLoadingMemories = true;

    try {
        const response = await fetch(`${API_BASE}/api/memories/all?limit=${memoriesLimit}&offset=${memoriesOffset}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Handle paginated response
        const newMemories = data.memories || [];
        hasMoreMemories = data.hasMore || false;
        
        if (reset) {
            allMemories = newMemories;
        } else {
            allMemories = [...allMemories, ...newMemories];
        }
        
        memoriesOffset += newMemories.length;
        
        // Update stats (show total if available)
        const totalCount = data.total || allMemories.length;
        document.getElementById('totalMemories').textContent = totalCount;
        
        // Render memories
        renderMemories(allMemories);
        
        // Show/hide "Load More" button
        updateLoadMoreButton();
        
    } catch (error) {
        console.error('Error loading memories:', error);
        if (reset) {
            memoriesList.innerHTML = `<div class="error">Failed to load memories: ${error.message}<br>Check console for details.</div>`;
        }
    } finally {
        isLoadingMemories = false;
    }
}

function updateLoadMoreButton() {
    let loadMoreBtn = document.getElementById('loadMoreBtn');
    if (!loadMoreBtn) {
        // Create button if it doesn't exist
        const memoriesContainer = document.querySelector('.memories-container');
        if (memoriesContainer) {
            loadMoreBtn = document.createElement('button');
            loadMoreBtn.id = 'loadMoreBtn';
            loadMoreBtn.className = 'btn-primary';
            loadMoreBtn.textContent = 'Load More';
            loadMoreBtn.onclick = () => loadAllMemories(false);
            loadMoreBtn.style.marginTop = '20px';
            loadMoreBtn.style.width = '100%';
            memoriesContainer.appendChild(loadMoreBtn);
        }
    }
    
    if (loadMoreBtn) {
        loadMoreBtn.style.display = hasMoreMemories ? 'block' : 'none';
        loadMoreBtn.disabled = isLoadingMemories;
        loadMoreBtn.textContent = isLoadingMemories ? 'Loading...' : 'Load More';
    }
}

// Debounce function for search
let searchTimeout;
       function filterMemories() {
           clearTimeout(searchTimeout);
           searchTimeout = setTimeout(() => {
               const searchTerm = document.getElementById('searchInput').value.toLowerCase();
               const selectedChannelId = document.getElementById('channelFilter').value;
               const selectedType = document.getElementById('typeFilter').value;

               let filtered = allMemories.filter(memory => {
                   // Search filter
                   if (searchTerm && !memory.content.toLowerCase().includes(searchTerm) &&
                       !memory.channel_name?.toLowerCase().includes(searchTerm)) {
                       return false;
                   }

                   // Channel filter
                   if (selectedChannelId && memory.channel_id !== selectedChannelId) {
                       return false;
                   }

                   // Type filter
                   if (selectedType && memory.memory_type !== selectedType) {
                       return false;
                   }

                   return true;
               });

               renderMemories(filtered);
           }, 300); // 300ms debounce
       }

function renderMemories(memories) {
    const memoriesList = document.getElementById('memoriesList');
    
    if (!memories || memories.length === 0) {
        memoriesList.innerHTML = `
            <div class="empty-state">
                <h3>// No memories found</h3>
                <p>Try adjusting your filters or check back later.</p>
            </div>
        `;
        // Remove load more button if no memories
        const loadMoreBtn = document.getElementById('loadMoreBtn');
        if (loadMoreBtn) loadMoreBtn.style.display = 'none';
        return;
    }

    // Use document fragment for faster rendering
    const fragment = document.createDocumentFragment();
    const tempDiv = document.createElement('div');
    
    tempDiv.innerHTML = memories.map((memory, index) => {
        if (!memory || typeof memory !== 'object') {
            return '';
        }
        
        // Truncate long content for performance (show first 500 chars)
        const content = memory.content || 'No content';
        const truncatedContent = content.length > 500 ? content.substring(0, 500) + '...' : content;
        
        return `
        <div class="memory-card">
            <div class="memory-header">
                <div class="memory-channel">
                    <span class="channel-badge">${escapeHtml(memory.channel_name || 'Unknown Channel')}</span>
                    <span class="channel-id">${escapeHtml(memory.channel_id || 'N/A')}</span>
                </div>
                <div class="memory-meta">
                    <span class="memory-type">${escapeHtml(memory.memory_type || 'conversation')}</span>
                    <span class="memory-date">${formatDate(memory.created_at)}</span>
                </div>
            </div>
            <div class="memory-content">${escapeHtml(truncatedContent)}</div>
        </div>
        `;
    }).filter(html => html).join('');
    
    // Clear and append (faster than innerHTML for large lists)
    memoriesList.innerHTML = '';
    while (tempDiv.firstChild) {
        fragment.appendChild(tempDiv.firstChild);
    }
    memoriesList.appendChild(fragment);
    
    // Update load more button position
    updateLoadMoreButton();
}

       function refreshMemories() {
           loadAllMemories(true); // Reset and reload
           loadChannels();
       }

async function loadAllDocuments() {
    const documentsList = document.getElementById('documentsList');
    if (!documentsList) return;
    
    documentsList.innerHTML = '<div class="loading"><span class="code-comment">// Loading documents...</span></div>';

    try {
        const response = await fetch(`${API_BASE}/api/documents`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Received documents data:', data);
        
        allDocuments = data.documents || data || [];
        
        if (!Array.isArray(allDocuments)) {
            console.error('Expected array but got:', typeof allDocuments, allDocuments);
            allDocuments = [];
        }
        
        console.log(`Loaded ${allDocuments.length} documents`);
        
        // Update stats
        document.getElementById('totalDocuments').textContent = allDocuments.length;
        
        // Render documents
        renderDocuments(allDocuments);
    } catch (error) {
        console.error('Error loading documents:', error);
        documentsList.innerHTML = `<div class="error">Failed to load documents: ${error.message}<br>Check console for details.</div>`;
    }
}

function filterDocuments() {
    const searchTerm = document.getElementById('documentSearchInput').value.toLowerCase();
    
    let filtered = allDocuments.filter(doc => {
        if (searchTerm && !doc.file_name?.toLowerCase().includes(searchTerm)) {
            return false;
        }
        return true;
    });
    
    renderDocuments(filtered);
}

function renderDocuments(documents) {
    const documentsList = document.getElementById('documentsList');
    if (!documentsList) return;
    
    if (!documents || documents.length === 0) {
        documentsList.innerHTML = `
            <div class="empty-state">
                <h3>// No documents found</h3>
                <p>Upload documents via Discord to see them here.</p>
            </div>
        `;
        return;
    }
    
    documentsList.innerHTML = documents.map((doc, index) => {
        return `
        <div class="document-card" data-doc-id="${escapeHtml(doc.id || '')}">
            <div class="document-header">
                <div class="document-info">
                    <span class="document-name">${escapeHtml(doc.file_name || 'Unknown')}</span>
                    <span class="document-id">${escapeHtml(doc.id || 'N/A')}</span>
                </div>
                <div class="document-meta">
                    <span class="document-chunks">${doc.chunk_count || 0} chunks</span>
                    <span class="document-date">${formatDate(doc.uploaded_at)}</span>
                    <button class="toggle-chunks-btn" onclick="toggleDocumentChunks('${escapeHtml(doc.id || '')}')">
                        <span class="toggle-icon">▼</span>
                        <span class="toggle-text">View Content</span>
                    </button>
                </div>
            </div>
            <div class="document-footer">
                <span class="document-uploader">Uploaded by: ${escapeHtml(doc.uploaded_by || 'Unknown')}</span>
            </div>
            <div class="document-chunks-container" id="chunks-${escapeHtml(doc.id || '')}" style="display: none;">
                <div class="chunks-loading">
                    <span class="code-comment">// Loading document content...</span>
                </div>
            </div>
        </div>
        `;
    }).join('');
}

async function toggleDocumentChunks(docId) {
    const chunksContainer = document.getElementById(`chunks-${docId}`);
    const toggleBtn = event.target.closest('.toggle-chunks-btn');
    const toggleIcon = toggleBtn.querySelector('.toggle-icon');
    
    if (!chunksContainer) return;
    
    // Toggle visibility
    const isVisible = chunksContainer.style.display !== 'none';
    
    if (isVisible) {
        // Collapse
        chunksContainer.style.display = 'none';
        toggleIcon.textContent = '▼';
        const toggleText = toggleBtn.querySelector('.toggle-text');
        if (toggleText) toggleText.textContent = 'View Content';
    } else {
        // Expand - load chunks if not already loaded
        chunksContainer.style.display = 'block';
        toggleIcon.textContent = '▲';
        const toggleText = toggleBtn.querySelector('.toggle-text');
        if (toggleText) toggleText.textContent = 'Hide Content';
        
        // Check if chunks are already loaded
        if (chunksContainer.querySelector('.chunks-content')) {
            return; // Already loaded
        }
        
        // Load chunks
        chunksContainer.innerHTML = '<div class="chunks-loading"><span class="code-comment">// Loading document content...</span></div>';
        
        try {
            const response = await fetch(`${API_BASE}/api/documents/${docId}/chunks`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            const chunks = data.chunks || [];
            
            if (chunks.length === 0) {
                chunksContainer.innerHTML = '<div class="empty-state"><p>No chunks found for this document.</p></div>';
                return;
            }
            
            // Render chunks
            chunksContainer.innerHTML = `
                <div class="chunks-content">
                    <div class="chunks-header">
                        <span class="code-comment">// ${chunks.length} chunks found</span>
                    </div>
                    ${chunks.map((chunk, index) => `
                        <div class="chunk-item">
                            <div class="chunk-header">
                                <span class="chunk-index">Chunk ${chunk.chunk_index !== undefined ? chunk.chunk_index : index + 1}</span>
                                <span class="chunk-id">${escapeHtml(chunk.chunk_id || 'N/A')}</span>
                            </div>
                            <div class="chunk-content">${escapeHtml(chunk.text || 'No content')}</div>
                        </div>
                    `).join('')}
                </div>
            `;
        } catch (error) {
            console.error('Error loading document chunks:', error);
            chunksContainer.innerHTML = `<div class="error">Failed to load document content: ${error.message}</div>`;
        }
    }
}

function refreshDocuments() {
    loadAllDocuments();
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    try {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;

        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (error) {
        return dateString;
    }
}
