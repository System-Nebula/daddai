/**
 * GopherBot Dashboard - Modern JavaScript Application
 * Professional, organized, and performant
 */

const API_BASE = '';

// Application State
const AppState = {
    memories: [],
    channels: [],
    documents: [],
    currentTab: 'memories',
    currentViewMode: 'grid',
    memoriesOffset: 0,
    memoriesLimit: 25,
    hasMoreMemories: true,
    isLoadingMemories: false,
    filteredMemories: [],
    filteredDocuments: [],
    searchTimeout: null,
    selectedStore: 'both',
    semanticSearchResults: null,
    selectedViewStore: null
};

// ============================================
// Performance Optimizations
// ============================================

// Virtual scrolling and lazy loading
let visibleItems = 50; // Render first 50 items
let intersectionObserver = null;

function setupLazyLoading() {
    if (!window.IntersectionObserver) return;
    
    intersectionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const card = entry.target;
                if (card.dataset.loaded !== 'true') {
                    card.dataset.loaded = 'true';
                    // Card is already rendered, just mark as loaded
                }
            }
        });
    }, { rootMargin: '100px' });
}

function observeCards() {
    if (!intersectionObserver) return;
    document.querySelectorAll('.memory-card, .document-card').forEach(card => {
        intersectionObserver.observe(card);
    });
}

// Debounce search input
let searchDebounceTimer;
function debounceSearch(callback, delay = 200) {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(callback, delay);
}

// ============================================
// Initialization
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    loadInitialData();
    setupEventListeners();
    setupKeyboardShortcuts();
    initializeViewMode();
    updatePageTitle();
    setupLazyLoading(); // NEW: Setup lazy loading
}

async function loadInitialData() {
    try {
        // Load critical data first (system status, channels)
        await Promise.all([
            loadSystemStatus(),
            loadChannels()
        ]);
        
        // Then load data-heavy content (can be deferred)
        // Use requestIdleCallback if available, otherwise setTimeout
        const loadHeavyData = () => {
            Promise.all([
                loadAllMemories(true),
                loadAllDocuments()
            ]).catch(error => {
                console.error('Error loading heavy data:', error);
            });
        };
        
        if (window.requestIdleCallback) {
            requestIdleCallback(loadHeavyData, { timeout: 2000 });
        } else {
            setTimeout(loadHeavyData, 100);
        }
    } catch (error) {
        console.error('Error loading initial data:', error);
        showToast('Failed to load initial data', 'error');
    }
}

// ============================================
// System Status
// ============================================

async function loadSystemStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/status`);
        if (!response.ok) {
            throw new Error('Failed to fetch system status');
        }
        
        const status = await response.json();
        updateSystemStatus(status);
        
        // Refresh status every 30 seconds
        setTimeout(loadSystemStatus, 30000);
    } catch (error) {
        console.error('Error loading system status:', error);
        // Set error state
        updateSystemStatus({
            neo4j: { connected: false },
            elasticsearch: { enabled: false, connected: false }
        });
    }
}

function updateSystemStatus(status) {
    // Update Neo4j status
    const neo4jIndicator = document.getElementById('neo4jStatus');
    if (neo4jIndicator) {
        if (status.neo4j && status.neo4j.connected) {
            neo4jIndicator.className = 'status-indicator status-connected';
            neo4jIndicator.title = 'Neo4j: Connected';
        } else {
            neo4jIndicator.className = 'status-indicator status-disconnected';
            neo4jIndicator.title = 'Neo4j: Disconnected';
        }
    }
    
    // Update Elasticsearch status
    const esIndicator = document.getElementById('elasticsearchStatus');
    if (esIndicator) {
        if (status.elasticsearch) {
            if (status.elasticsearch.enabled && status.elasticsearch.connected) {
                esIndicator.className = 'status-indicator status-connected';
                const version = status.elasticsearch.version || '';
                const docCount = status.elasticsearch.indices?.documents?.count || 0;
                const chunkCount = status.elasticsearch.indices?.chunks?.count || 0;
                esIndicator.title = `Elasticsearch: Connected (v${version})\nDocuments: ${docCount}, Chunks: ${chunkCount}`;
            } else if (status.elasticsearch.enabled && !status.elasticsearch.connected) {
                esIndicator.className = 'status-indicator status-warning';
                esIndicator.title = `Elasticsearch: Enabled but disconnected\n${status.elasticsearch.message || ''}`;
            } else {
                esIndicator.className = 'status-indicator status-disabled';
                esIndicator.title = 'Elasticsearch: Disabled';
            }
        } else {
            esIndicator.className = 'status-indicator status-disabled';
            esIndicator.title = 'Elasticsearch: Unknown';
        }
    }
}

// ============================================
// Event Listeners Setup
// ============================================

function setupEventListeners() {
    // Memory filters
    const searchInput = document.getElementById('searchInput');
    const channelFilter = document.getElementById('channelFilter');
    const typeFilter = document.getElementById('typeFilter');
    const sortFilter = document.getElementById('sortFilter');
    
    // Document filters
    const documentSearchInput = document.getElementById('documentSearchInput');
    const docSortFilter = document.getElementById('docSortFilter');
    
    // Global search
    const globalSearch = document.getElementById('globalSearch');
    
    // Clear buttons
    const clearSearch = document.getElementById('clearSearch');
    const clearDocSearch = document.getElementById('clearDocSearch');

    if (searchInput) {
        searchInput.addEventListener('input', () => {
            filterMemories();
            updateClearButton(clearSearch, searchInput.value);
        });
    }
    
    if (channelFilter) {
        channelFilter.addEventListener('change', () => filterMemories());
    }
    
    if (typeFilter) {
        typeFilter.addEventListener('change', () => filterMemories());
    }
    
    if (sortFilter) {
        sortFilter.addEventListener('change', () => filterMemories());
    }
    
    if (documentSearchInput) {
        documentSearchInput.addEventListener('input', () => {
            filterDocuments();
            updateClearButton(clearDocSearch, documentSearchInput.value);
        });
        
        // Allow Enter key to trigger semantic search if semantic search section is visible
        documentSearchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.ctrlKey) {
                e.preventDefault();
                toggleSemanticSearch();
            }
        });
    }
    
    // Semantic search input Enter key handler
    const semanticSearchInput = document.getElementById('semanticSearchInput');
    if (semanticSearchInput) {
        semanticSearchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                performSemanticSearch();
            }
        });
    }
    
    if (docSortFilter) {
        docSortFilter.addEventListener('change', () => filterDocuments());
    }
    
    if (globalSearch) {
        globalSearch.addEventListener('input', () => handleGlobalSearch());
    }
}

// ============================================
// Keyboard Shortcuts
// ============================================

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+K or Cmd+K for global search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const globalSearch = document.getElementById('globalSearch');
            if (globalSearch) {
                globalSearch.focus();
                globalSearch.select();
            }
        }
        
        // Ctrl+R or Cmd+R for refresh
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            if (!e.shiftKey) {
                e.preventDefault();
                refreshAll();
            }
        }
        
        // Escape to clear search
        if (e.key === 'Escape') {
            const activeInput = document.activeElement;
            if (activeInput && (
                activeInput.id === 'searchInput' || 
                activeInput.id === 'documentSearchInput' || 
                activeInput.id === 'globalSearch'
            )) {
                activeInput.value = '';
                activeInput.blur();
                if (activeInput.id === 'searchInput' || activeInput.id === 'globalSearch') {
                    filterMemories();
                } else if (activeInput.id === 'documentSearchInput') {
                    filterDocuments();
                }
            }
        }
    });
}

// ============================================
// View Mode Management
// ============================================

function initializeViewMode() {
    const savedMode = localStorage.getItem('viewMode') || 'grid';
    setViewMode(savedMode);
}

function setViewMode(mode) {
    AppState.currentViewMode = mode;
    localStorage.setItem('viewMode', mode);
    
    const memoriesList = document.getElementById('memoriesList');
    const documentsList = document.getElementById('documentsList');
    
    if (memoriesList) {
        memoriesList.setAttribute('data-view-mode', mode);
    }
    if (documentsList) {
        documentsList.setAttribute('data-view-mode', mode);
    }
    
    // Update toggle buttons
    document.querySelectorAll('.view-toggle-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('data-view') === mode) {
            btn.classList.add('active');
        }
    });
    
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('data-tab') === AppState.currentTab) {
            item.classList.add('active');
        }
    });
    
    // Re-render current tab
    if (AppState.currentTab === 'memories') {
        renderMemories(AppState.filteredMemories.length > 0 ? AppState.filteredMemories : AppState.memories);
    } else {
        renderDocuments(AppState.filteredDocuments.length > 0 ? AppState.filteredDocuments : AppState.documents);
    }
}

// ============================================
// Tab Management
// ============================================

function switchTab(tabName) {
    AppState.currentTab = tabName;
    
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('data-tab') === tabName) {
            item.classList.add('active');
        }
    });
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    const activeTab = document.getElementById(`${tabName}Tab`);
    if (activeTab) {
        activeTab.classList.add('active');
    }
    
    // Clear global search when switching tabs
    const globalSearch = document.getElementById('globalSearch');
    if (globalSearch) {
        globalSearch.value = '';
    }
    
    // Update page title
    updatePageTitle();
    
    // Re-render with current view mode
    if (tabName === 'memories') {
        renderMemories(AppState.filteredMemories.length > 0 ? AppState.filteredMemories : AppState.memories);
    } else {
        renderDocuments(AppState.filteredDocuments.length > 0 ? AppState.filteredDocuments : AppState.documents);
    }
}

function updatePageTitle() {
    const pageTitle = document.getElementById('pageTitle');
    const pageSubtitle = document.getElementById('pageSubtitle');
    
    if (AppState.currentTab === 'memories') {
        if (pageTitle) pageTitle.textContent = 'Memories';
        if (pageSubtitle) pageSubtitle.textContent = 'View and manage conversation memories';
    } else {
        if (pageTitle) pageTitle.textContent = 'Documents';
        if (pageSubtitle) pageSubtitle.textContent = 'Browse and explore uploaded documents';
    }
}

// ============================================
// Data Loading Functions
// ============================================

async function loadChannels() {
    try {
        const response = await fetch(`${API_BASE}/api/channels`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        AppState.channels = data.channels || [];
        
        // Update channel filter dropdown
        const channelFilter = document.getElementById('channelFilter');
        if (channelFilter) {
            channelFilter.innerHTML = '<option value="">All Channels</option>';
            
            AppState.channels.forEach(channel => {
                const option = document.createElement('option');
                option.value = channel.channel_id || channel.id;
                option.textContent = `${channel.channel_name || 'Unknown'} (${channel.memory_count || 0})`;
                channelFilter.appendChild(option);
            });
        }

        // Update stats
        updateStat('totalChannels', AppState.channels.length);
    } catch (error) {
        console.error('Error loading channels:', error);
        showToast('Failed to load channels', 'error');
    }
}

async function loadAllMemories(reset = false) {
    if (AppState.isLoadingMemories) return;
    
    const memoriesList = document.getElementById('memoriesList');
    
    if (reset) {
        AppState.memoriesOffset = 0;
        AppState.memories = [];
        AppState.filteredMemories = [];
        if (memoriesList) {
            memoriesList.innerHTML = '<div class="loading-state"><div class="spinner"></div><p class="loading-text">Loading memories...</p></div>';
        }
    } else if (AppState.memoriesOffset === 0 && memoriesList) {
        memoriesList.innerHTML = '<div class="loading-state"><div class="spinner"></div><p class="loading-text">Loading memories...</p></div>';
    }
    
    AppState.isLoadingMemories = true;

    try {
        const response = await fetch(`${API_BASE}/api/memories/all?limit=${AppState.memoriesLimit}&offset=${AppState.memoriesOffset}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        const newMemories = data.memories || [];
        AppState.hasMoreMemories = data.hasMore || false;
        
        if (reset) {
            AppState.memories = newMemories;
        } else {
            AppState.memories = [...AppState.memories, ...newMemories];
        }
        
        AppState.memoriesOffset += newMemories.length;
        
        // Update stats
        const totalCount = data.total || AppState.memories.length;
        updateStat('totalMemories', totalCount);
        updateStat('memoriesCount', AppState.memories.length);
        
        // Apply filters and render
        filterMemories();
        updateLoadMoreButton();
        
    } catch (error) {
        console.error('Error loading memories:', error);
        showToast('Failed to load memories', 'error');
        if (reset && memoriesList) {
            memoriesList.innerHTML = `<div class="error">Failed to load memories: ${error.message}<br>Check console for details.</div>`;
        }
    } finally {
        AppState.isLoadingMemories = false;
    }
}

async function loadAllDocuments() {
    const documentsList = document.getElementById('documentsList');
    if (!documentsList) return;
    
    documentsList.innerHTML = '<div class="loading-state"><div class="spinner"></div><p class="loading-text">Loading documents...</p></div>';

    try {
        const response = await fetch(`${API_BASE}/api/documents`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        AppState.documents = data.documents || data || [];
        
        if (!Array.isArray(AppState.documents)) {
            console.error('Expected array but got:', typeof AppState.documents, AppState.documents);
            AppState.documents = [];
        }
        
        // Update stats
        updateStat('totalDocuments', AppState.documents.length);
        updateStat('documentsCount', AppState.documents.length);
        
        // Apply filters and render
        filterDocuments();
    } catch (error) {
        console.error('Error loading documents:', error);
        showToast('Failed to load documents', 'error');
        if (documentsList) {
            documentsList.innerHTML = `<div class="error">Failed to load documents: ${error.message}<br>Check console for details.</div>`;
        }
    }
}

// ============================================
// Filtering Functions
// ============================================

function filterMemories() {
    debounceSearch(() => {
        const searchTerm = document.getElementById('searchInput')?.value.toLowerCase() || '';
        const selectedChannelId = document.getElementById('channelFilter')?.value || '';
        const selectedType = document.getElementById('typeFilter')?.value || '';
        const sortBy = document.getElementById('sortFilter')?.value || 'newest';

        AppState.filteredMemories = AppState.memories.filter(memory => {
            // Search filter
            if (searchTerm && 
                !memory.content?.toLowerCase().includes(searchTerm) &&
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
        
        // Sort
        AppState.filteredMemories.sort((a, b) => {
            if (sortBy === 'newest') {
                return new Date(b.created_at || 0) - new Date(a.created_at || 0);
            } else if (sortBy === 'oldest') {
                return new Date(a.created_at || 0) - new Date(b.created_at || 0);
            }
            return 0;
        });
        
        // Reset visible items for new filter
        visibleItems = 50;
        
        // Update count
        updateStat('filteredCount', AppState.filteredMemories.length);
        renderMemories(AppState.filteredMemories);
    }, 200);
}

function filterDocuments() {
    const searchTerm = document.getElementById('documentSearchInput')?.value.toLowerCase() || '';
    const sortBy = document.getElementById('docSortFilter')?.value || 'newest';
    
    AppState.filteredDocuments = AppState.documents.filter(doc => {
        if (searchTerm && !doc.file_name?.toLowerCase().includes(searchTerm)) {
            return false;
        }
        return true;
    });
    
    // Sort
    AppState.filteredDocuments.sort((a, b) => {
        if (sortBy === 'newest') {
            return new Date(b.uploaded_at || 0) - new Date(a.uploaded_at || 0);
        } else if (sortBy === 'oldest') {
            return new Date(a.uploaded_at || 0) - new Date(b.uploaded_at || 0);
        } else if (sortBy === 'name') {
            return (a.file_name || '').localeCompare(b.file_name || '');
        } else if (sortBy === 'chunks') {
            return (b.chunk_count || 0) - (a.chunk_count || 0);
        }
        return 0;
    });
    
    // Update count
    updateStat('filteredDocCount', AppState.filteredDocuments.length);
    renderDocuments(AppState.filteredDocuments);
}

function handleGlobalSearch() {
    const query = document.getElementById('globalSearch')?.value.toLowerCase() || '';
    
    if (!query) {
        // Clear global search - restore normal view
        if (AppState.currentTab === 'memories') {
            renderMemories(AppState.filteredMemories.length > 0 ? AppState.filteredMemories : AppState.memories);
        } else {
            renderDocuments(AppState.filteredDocuments.length > 0 ? AppState.filteredDocuments : AppState.documents);
        }
        return;
    }
    
    // Search across current tab
    if (AppState.currentTab === 'memories') {
        const results = AppState.memories.filter(m => 
            m.content?.toLowerCase().includes(query) ||
            m.channel_name?.toLowerCase().includes(query) ||
            m.memory_type?.toLowerCase().includes(query)
        );
        renderMemories(results);
    } else {
        const results = AppState.documents.filter(d => 
            d.file_name?.toLowerCase().includes(query) ||
            d.id?.toLowerCase().includes(query) ||
            d.uploaded_by?.toLowerCase().includes(query)
        );
        renderDocuments(results);
    }
}

// ============================================
// Rendering Functions
// ============================================

function renderMemories(memories) {
    const memoriesList = document.getElementById('memoriesList');
    if (!memoriesList) return;
    
    if (!memories || memories.length === 0) {
        memoriesList.innerHTML = `
            <div class="empty-state">
                <h3>No memories found</h3>
                <p>Try adjusting your filters or check back later.</p>
            </div>
        `;
        const loadMoreBtn = document.getElementById('loadMoreBtn');
        if (loadMoreBtn) loadMoreBtn.style.display = 'none';
        return;
    }

    // Use requestAnimationFrame for smooth rendering
    requestAnimationFrame(() => {
        const fragment = document.createDocumentFragment();
        const renderCount = Math.min(memories.length, visibleItems);
        
        for (let i = 0; i < renderCount; i++) {
            const memory = memories[i];
            if (!memory || typeof memory !== 'object') continue;
            
            const card = createMemoryCard(memory, i);
            fragment.appendChild(card);
        }
        
        memoriesList.innerHTML = '';
        memoriesList.appendChild(fragment);
        
        // Observe cards for lazy loading
        observeCards();
        
        // Load remaining items progressively
        if (memories.length > renderCount) {
            setTimeout(() => {
                loadRemainingMemories(memories.slice(renderCount));
            }, 0);
        }
        
        updateLoadMoreButton();
    });
}

function loadRemainingMemories(remainingMemories) {
    const memoriesList = document.getElementById('memoriesList');
    if (!memoriesList) return;
    
    const fragment = document.createDocumentFragment();
    const batchSize = 25;
    const batch = remainingMemories.slice(0, batchSize);
    
    batch.forEach((memory, index) => {
        const card = createMemoryCard(memory, visibleItems + index);
        fragment.appendChild(card);
    });
    
    memoriesList.appendChild(fragment);
    visibleItems += batch.length;
    observeCards();
    
    // Continue loading if more remain
    if (remainingMemories.length > batchSize) {
        if (window.requestIdleCallback) {
            requestIdleCallback(() => {
                loadRemainingMemories(remainingMemories.slice(batchSize));
            }, { timeout: 100 });
        } else {
            setTimeout(() => {
                loadRemainingMemories(remainingMemories.slice(batchSize));
            }, 50);
        }
    }
}

function createMemoryCard(memory, index) {
    const card = document.createElement('div');
    card.className = 'memory-card';
    card.setAttribute('data-index', index);
    
    const content = memory.content || 'No content';
    const truncatedContent = content.length > 300 ? content.substring(0, 300) + '...' : content;
    const isLong = content.length > 300;
    const displayIndex = String(index + 1).padStart(2, '0');
    
    card.innerHTML = `
        <div class="memory-index">${displayIndex}</div>
        <div class="memory-content-wrapper">
            <div class="memory-header">
                <div class="memory-header-left">
                    <div class="memory-channel">
                        <span class="channel-badge">${escapeHtml(memory.channel_name || 'Unknown Channel')}</span>
                        <span class="channel-id">${escapeHtml(memory.channel_id || 'N/A')}</span>
                    </div>
                </div>
                <div class="memory-header-right">
                    <span class="memory-type">${escapeHtml(memory.memory_type || 'conversation')}</span>
                    <span class="memory-date">${formatDate(memory.created_at)}</span>
                </div>
            </div>
            <div class="memory-content" ${isLong ? 'onclick="expandMemory(this)"' : ''}>
                ${escapeHtml(truncatedContent)}
            </div>
            ${isLong ? '<div class="memory-expand-indicator" onclick="expandMemory(this.previousElementSibling)">Show more...</div>' : ''}
        </div>
        <div></div>
    `;
    
    return card;
}

function renderDocuments(documents) {
    const documentsList = document.getElementById('documentsList');
    if (!documentsList) return;
    
    if (!documents || documents.length === 0) {
        documentsList.innerHTML = `
            <div class="empty-state">
                <h3>No documents found</h3>
                <p>Upload documents via Discord to see them here.</p>
            </div>
        `;
        return;
    }
    
    requestAnimationFrame(() => {
        const fragment = document.createDocumentFragment();
        
        documents.forEach((doc, index) => {
            const card = createDocumentCard(doc, index);
            fragment.appendChild(card);
        });
        
        documentsList.innerHTML = '';
        documentsList.appendChild(fragment);
    });
}

function createDocumentCard(doc, index) {
    const card = document.createElement('div');
    card.className = 'document-card';
    card.setAttribute('data-doc-id', escapeHtml(doc.id || ''));
    
    const displayIndex = String(index + 1).padStart(2, '0');
    
    card.innerHTML = `
        <div class="document-index">${displayIndex}</div>
        <div class="document-content-wrapper">
            <div class="document-header">
                <div class="document-header-left">
                    <div class="document-info">
                        <span class="document-name">${escapeHtml(doc.file_name || 'Unknown')}</span>
                        <span class="document-id">${escapeHtml(doc.id || 'N/A')}</span>
                    </div>
                </div>
                <div class="document-header-right">
                    <div class="document-meta">
                        <span class="document-chunks">${doc.chunk_count || 0} chunks</span>
                        <span class="document-date">${formatDate(doc.uploaded_at)}</span>
                    </div>
                </div>
            </div>
            <div class="document-footer">
                <span class="document-uploader">Uploaded by: ${escapeHtml(doc.uploaded_by || 'Unknown')}</span>
            </div>
            <div class="document-chunks-container" id="chunks-${escapeHtml(doc.id || '')}" style="display: none;">
                <div class="chunks-loading">
                    <div class="spinner"></div>
                    <p class="loading-text">Loading document content...</p>
                </div>
            </div>
        </div>
        <div class="document-header-right">
            <button class="toggle-chunks-btn" onclick="toggleDocumentChunks('${escapeHtml(doc.id || '')}')">
                <span class="toggle-icon">▼</span>
                <span class="toggle-text">View</span>
            </button>
        </div>
    `;
    
    return card;
}

// ============================================
// Utility Functions
// ============================================

function updateStat(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = typeof value === 'number' ? value.toLocaleString() : value;
    }
}

function updateClearButton(btn, value) {
    if (btn) {
        btn.style.display = value ? 'flex' : 'none';
    }
}

function clearSearch() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.value = '';
        filterMemories();
        updateClearButton(document.getElementById('clearSearch'), '');
    }
}

function clearDocSearch() {
    const documentSearchInput = document.getElementById('documentSearchInput');
    if (documentSearchInput) {
        documentSearchInput.value = '';
        filterDocuments();
        updateClearButton(document.getElementById('clearDocSearch'), '');
    }
}

// ============================================
// Semantic Search Functions
// ============================================

function toggleSemanticSearch() {
    const section = document.getElementById('semanticSearchSection');
    if (section) {
        const isVisible = section.style.display !== 'none';
        section.style.display = isVisible ? 'none' : 'block';
        if (!isVisible) {
            document.getElementById('semanticSearchInput')?.focus();
        }
    }
}

function closeSemanticSearch() {
    const section = document.getElementById('semanticSearchSection');
    if (section) {
        section.style.display = 'none';
    }
    const input = document.getElementById('semanticSearchInput');
    if (input) {
        input.value = '';
    }
    const results = document.getElementById('semanticSearchResults');
    if (results) {
        results.innerHTML = '';
    }
    AppState.semanticSearchResults = null;
    AppState.selectedViewStore = null;
}

function selectStore(store) {
    AppState.selectedStore = store;
    document.querySelectorAll('.store-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('data-store') === store) {
            btn.classList.add('active');
        }
    });
}

function selectViewStore(store) {
    AppState.selectedViewStore = store;
    document.querySelectorAll('.view-store-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('data-view-store') === store) {
            btn.classList.add('active');
        }
    });
    // Re-render results with the selected view
    if (AppState.semanticSearchResults) {
        renderSemanticSearchResults(AppState.semanticSearchResults);
    }
}

async function performSemanticSearch() {
    const query = document.getElementById('semanticSearchInput')?.value.trim();
    if (!query) {
        showToast('Please enter a search query', 'warning');
        return;
    }
    
    const resultsDiv = document.getElementById('semanticSearchResults');
    if (!resultsDiv) return;
    
    resultsDiv.innerHTML = '<div class="loading-state"><div class="spinner"></div><p class="loading-text">Searching...</p></div>';
    
    try {
        const store = AppState.selectedStore || 'both';
        const response = await fetch(`${API_BASE}/api/search/documents?query=${encodeURIComponent(query)}&store=${store}&top_k=10`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        AppState.semanticSearchResults = data;
        AppState.selectedViewStore = null; // Reset view store when new search
        
        if (data.error) {
            resultsDiv.innerHTML = `<div class="error">Error: ${data.error}</div>`;
            return;
        }
        
        renderSemanticSearchResults(data);
    } catch (error) {
        console.error('Error performing semantic search:', error);
        resultsDiv.innerHTML = `<div class="error">Failed to search: ${error.message}</div>`;
        showToast('Search failed', 'error');
    }
}

function renderSemanticSearchResults(data) {
    const resultsDiv = document.getElementById('semanticSearchResults');
    if (!resultsDiv) return;
    
    let html = '';
    
    if (data.store === 'both') {
        // Show view toggle buttons
        const viewStore = AppState.selectedViewStore || 'both';
        html += '<div class="view-store-selector">';
        html += '<label>View:</label>';
        html += '<div class="view-store-buttons">';
        html += `<button class="view-store-btn ${viewStore === 'both' ? 'active' : ''}" data-view-store="both" onclick="selectViewStore('both')">Both</button>`;
        html += `<button class="view-store-btn ${viewStore === 'elasticsearch' ? 'active' : ''}" data-view-store="elasticsearch" onclick="selectViewStore('elasticsearch')">⚡ Elasticsearch</button>`;
        html += `<button class="view-store-btn ${viewStore === 'neo4j' ? 'active' : ''}" data-view-store="neo4j" onclick="selectViewStore('neo4j')">🕸️ Neo4j</button>`;
        html += '</div>';
        html += '</div>';
        
        if (viewStore === 'both') {
            // Show results from both stores side by side
            html += '<div class="search-results-comparison">';
            
            // Elasticsearch results
            html += '<div class="search-results-column">';
            html += '<h4 class="store-header elasticsearch-header">⚡ Elasticsearch Results</h4>';
            if (data.elasticsearch?.error) {
                html += `<div class="error">${data.elasticsearch.error}</div>`;
            } else if (data.elasticsearch?.results && data.elasticsearch.results.length > 0) {
                html += `<div class="results-count-badge">${data.elasticsearch.count} results</div>`;
                data.elasticsearch.results.forEach((result, idx) => {
                    html += createSearchResultCard(result, 'elasticsearch', idx);
                });
            } else {
                html += '<div class="empty-state">No results found</div>';
            }
            html += '</div>';
            
            // Neo4j results
            html += '<div class="search-results-column">';
            html += '<h4 class="store-header neo4j-header">🕸️ Neo4j Results</h4>';
            if (data.neo4j?.error) {
                html += `<div class="error">${data.neo4j.error}</div>`;
            } else if (data.neo4j?.results && data.neo4j.results.length > 0) {
                html += `<div class="results-count-badge">${data.neo4j.count} results</div>`;
                data.neo4j.results.forEach((result, idx) => {
                    html += createSearchResultCard(result, 'neo4j', idx);
                });
            } else {
                html += '<div class="empty-state">No results found</div>';
            }
            html += '</div>';
            
            html += '</div>';
        } else if (viewStore === 'elasticsearch') {
            // Show only Elasticsearch results
            html += '<div class="search-results-single">';
            html += '<h4 class="store-header elasticsearch-header">⚡ Elasticsearch Results</h4>';
            if (data.elasticsearch?.error) {
                html += `<div class="error">${data.elasticsearch.error}</div>`;
            } else if (data.elasticsearch?.results && data.elasticsearch.results.length > 0) {
                html += `<div class="results-count-badge">${data.elasticsearch.count} results</div>`;
                data.elasticsearch.results.forEach((result, idx) => {
                    html += createSearchResultCard(result, 'elasticsearch', idx);
                });
            } else {
                html += '<div class="empty-state">No results found</div>';
            }
            html += '</div>';
        } else if (viewStore === 'neo4j') {
            // Show only Neo4j results
            html += '<div class="search-results-single">';
            html += '<h4 class="store-header neo4j-header">🕸️ Neo4j Results</h4>';
            if (data.neo4j?.error) {
                html += `<div class="error">${data.neo4j.error}</div>`;
            } else if (data.neo4j?.results && data.neo4j.results.length > 0) {
                html += `<div class="results-count-badge">${data.neo4j.count} results</div>`;
                data.neo4j.results.forEach((result, idx) => {
                    html += createSearchResultCard(result, 'neo4j', idx);
                });
            } else {
                html += '<div class="empty-state">No results found</div>';
            }
            html += '</div>';
        }
    } else {
        // Single store results
        const storeData = data.store === 'elasticsearch' ? data : data;
        const storeName = data.store === 'elasticsearch' ? 'Elasticsearch' : 'Neo4j';
        const storeIcon = data.store === 'elasticsearch' ? '⚡' : '🕸️';
        
        html += `<h4 class="store-header ${data.store}-header">${storeIcon} ${storeName} Results</h4>`;
        
        if (data.error) {
            html += `<div class="error">${data.error}</div>`;
        } else if (data.results && data.results.length > 0) {
            html += `<div class="results-count-badge">${data.count} results</div>`;
            data.results.forEach((result, idx) => {
                html += createSearchResultCard(result, data.store, idx);
            });
        } else {
            html += '<div class="empty-state">No results found</div>';
        }
    }
    
    resultsDiv.innerHTML = html;
}

function createSearchResultCard(result, store, index) {
    const text = result.text || result.content || '';
    const truncatedText = text.length > 300 ? text.substring(0, 300) + '...' : text;
    const score = result.score || 0;
    const fileName = result.file_name || 'Unknown';
    const docId = result.doc_id || result.id || '';
    
    return `
        <div class="search-result-card" data-store="${store}">
            <div class="result-header">
                <span class="result-index">#${index + 1}</span>
                <span class="result-store-badge store-${store}">${store === 'elasticsearch' ? '⚡ ES' : '🕸️ Neo4j'}</span>
                <span class="result-score">Score: ${score.toFixed(4)}</span>
            </div>
            <div class="result-file">📄 ${escapeHtml(fileName)}</div>
            <div class="result-text">${escapeHtml(truncatedText)}</div>
            ${text.length > 300 ? '<div class="result-expand">Show more...</div>' : ''}
        </div>
    `;
}

function expandMemory(element) {
    const card = element.closest('.memory-card');
    if (card) {
        card.classList.toggle('expanded');
        const content = card.querySelector('.memory-content');
        if (content && card.classList.contains('expanded')) {
            const memoryIndex = parseInt(card.getAttribute('data-index'));
            const fullMemory = AppState.memories[memoryIndex];
            if (fullMemory) {
                content.textContent = fullMemory.content;
            }
        }
    }
}

async function toggleDocumentChunks(docId) {
    const chunksContainer = document.getElementById(`chunks-${docId}`);
    const card = document.querySelector(`[data-doc-id="${docId}"]`);
    const toggleBtn = event.target.closest('.toggle-chunks-btn');
    const toggleIcon = toggleBtn?.querySelector('.toggle-icon');
    const toggleText = toggleBtn?.querySelector('.toggle-text');
    
    if (!chunksContainer || !card) return;
    
    const isVisible = chunksContainer.style.display !== 'none';
    
    if (isVisible) {
        chunksContainer.style.display = 'none';
        card.classList.remove('expanded');
        if (toggleIcon) toggleIcon.textContent = '▼';
        if (toggleText) toggleText.textContent = 'View Content';
    } else {
        chunksContainer.style.display = 'block';
        card.classList.add('expanded');
        if (toggleIcon) toggleIcon.textContent = '▲';
        if (toggleText) toggleText.textContent = 'Hide Content';
        
        if (chunksContainer.querySelector('.chunks-content')) {
            return;
        }
        
        chunksContainer.innerHTML = '<div class="chunks-loading"><div class="spinner"></div><p class="loading-text">Loading document content...</p></div>';
        
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
            
            const chunksContent = document.createElement('div');
            chunksContent.className = 'chunks-content';
            
            chunks.forEach((chunk, index) => {
                const chunkItem = document.createElement('div');
                chunkItem.className = 'chunk-item';
                chunkItem.innerHTML = `
                    <div class="chunk-header">
                        <span class="chunk-index">Chunk ${chunk.chunk_index !== undefined ? chunk.chunk_index : index + 1}</span>
                        <span class="chunk-id">${escapeHtml(chunk.chunk_id || 'N/A')}</span>
                    </div>
                    <div class="chunk-content">${escapeHtml(chunk.text || 'No content')}</div>
                `;
                chunksContent.appendChild(chunkItem);
            });
            
            chunksContainer.innerHTML = '';
            chunksContainer.appendChild(chunksContent);
        } catch (error) {
            console.error('Error loading document chunks:', error);
            chunksContainer.innerHTML = `<div class="error">Failed to load document content: ${error.message}</div>`;
            showToast('Failed to load document chunks', 'error');
        }
    }
}

function updateLoadMoreButton() {
    let loadMoreBtn = document.getElementById('loadMoreBtn');
    if (!loadMoreBtn && AppState.hasMoreMemories) {
        const memoriesContainer = document.getElementById('memoriesContainer');
        if (memoriesContainer) {
            loadMoreBtn = document.createElement('button');
            loadMoreBtn.id = 'loadMoreBtn';
            loadMoreBtn.className = 'btn-primary';
            loadMoreBtn.textContent = 'Load More';
            loadMoreBtn.onclick = () => loadAllMemories(false);
            loadMoreBtn.style.cssText = 'margin-top: 20px; width: 100%; padding: 12px; background: var(--accent); color: var(--crust); border: none; border-radius: var(--radius-md); font-weight: 600; cursor: pointer; transition: all var(--transition-base);';
            loadMoreBtn.onmouseover = function() { this.style.background = 'var(--accent-hover)'; };
            loadMoreBtn.onmouseout = function() { this.style.background = 'var(--accent)'; };
            memoriesContainer.appendChild(loadMoreBtn);
        }
    }
    
    if (loadMoreBtn) {
        loadMoreBtn.style.display = AppState.hasMoreMemories ? 'block' : 'none';
        loadMoreBtn.disabled = AppState.isLoadingMemories;
        loadMoreBtn.textContent = AppState.isLoadingMemories ? 'Loading...' : 'Load More';
    }
}

function refreshMemories() {
    showToast('Refreshing memories...', 'info');
    loadAllMemories(true);
    loadChannels();
}

function refreshDocuments() {
    showToast('Refreshing documents...', 'info');
    loadAllDocuments();
}

function refreshAll() {
    showToast('Refreshing all data...', 'info');
    refreshMemories();
    refreshDocuments();
    loadChannels();
}

function exportData() {
    const data = {
        memories: AppState.memories,
        documents: AppState.documents,
        channels: AppState.channels,
        exportedAt: new Date().toISOString()
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `gopherbot-export-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast('Data exported successfully', 'success');
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

// ============================================
// UI Feedback Functions
// ============================================

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span>${escapeHtml(message)}</span>
        <button onclick="this.parentElement.remove()" aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </button>
    `;
    
    container.appendChild(toast);
    
    // Auto remove after 4 seconds
    setTimeout(() => {
        toast.style.animation = 'slideInRight 0.3s ease-out reverse';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function showLoadingOverlay(show = true) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.style.display = show ? 'flex' : 'none';
    }
}
