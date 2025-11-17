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
    startAnalyticsAutoRefresh(); // Start auto-refresh for analytics
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
    } else if (tabName === 'analytics') {
        loadAnalytics();
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
    } else if (AppState.currentTab === 'analytics') {
        if (pageTitle) pageTitle.textContent = 'Analytics';
        if (pageSubtitle) pageSubtitle.textContent = 'System status, metrics, and insights';
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

// ============================================
// Analytics Dashboard Functions
// ============================================

// Chart instances
let memoryTypesChart = null;
let documentTypesChart = null;
let topChannelsChart = null;
let memoryGrowthChart = null;
let documentGrowthChart = null;
let queryVolumeChart = null;
let storageGrowthChart = null;
let latencyDistributionChart = null;
let cachePerformanceChart = null;
let operationBreakdownChart = null;
let errorRateChart = null;
let retrievalQualityChart = null;
let generationQualityChart = null;
let topicClustersChart = null;
let topUsersChart = null;
let engagementChart = null;
let queryTypesChart = null;
let documentAccessChart = null;
let storageByTypeChart = null;
let chunkDistributionChart = null;
let systemLoadChart = null;

// Analytics cache
let analyticsCache = {
    data: null,
    timestamp: 0,
    ttl: 10000 // 10 seconds
};

// Auto-refresh interval
let analyticsRefreshInterval = null;

// Alerts system
let alerts = [];
let alertsCheckInterval = null;

// Load analytics data concurrently - COMPREHENSIVE
async function loadAnalytics() {
    try {
        // Check cache first
        const now = Date.now();
        if (analyticsCache.data && (now - analyticsCache.timestamp) < analyticsCache.ttl) {
            renderComprehensiveAnalytics(analyticsCache.data);
            return;
        }

        // Fetch ALL data concurrently for maximum speed with timeouts
        const fetchWithTimeout = (url, timeout = 5000) => {
            return Promise.race([
                fetch(url).then(r => {
                    if (!r.ok) throw new Error(`HTTP ${r.status}`);
                    return r.json();
                }),
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Timeout')), timeout)
                )
            ]).catch(err => {
                console.warn(`[Analytics] Failed to fetch ${url}:`, err.message);
                return null;
            });
        };

        const [
            comprehensiveResult,
            trendsResult,
            performanceResult,
            knowledgeGraphResult,
            userActivityResult,
            queryAnalyticsResult,
            documentPopularityResult,
            storageResult,
            configResult,
            modelInfoResult,
            metricsResult
        ] = await Promise.allSettled([
            fetchWithTimeout(`${API_BASE}/api/analytics`, 10000),
            fetchWithTimeout(`${API_BASE}/api/analytics/trends?days=30`, 5000),
            fetchWithTimeout(`${API_BASE}/api/analytics/performance`, 5000),
            fetchWithTimeout(`${API_BASE}/api/analytics/knowledge-graph`, 5000),
            fetchWithTimeout(`${API_BASE}/api/analytics/users`, 5000),
            fetchWithTimeout(`${API_BASE}/api/analytics/queries`, 5000),
            fetchWithTimeout(`${API_BASE}/api/analytics/documents/popularity`, 5000),
            fetchWithTimeout(`${API_BASE}/api/analytics`, 5000).then(d => d?.documents?.storage || null),
            fetchWithTimeout(`${API_BASE}/api/config`, 5000),
            fetchWithTimeout(`${API_BASE}/api/model-info`, 5000),
            fetchWithTimeout(`${API_BASE}/api/metrics`, 5000)
        ]);

        const comprehensive = {
            basic: comprehensiveResult.status === 'fulfilled' ? comprehensiveResult.value : null,
            trends: trendsResult.status === 'fulfilled' ? trendsResult.value : null,
            performance: performanceResult.status === 'fulfilled' ? performanceResult.value : null,
            knowledgeGraph: knowledgeGraphResult.status === 'fulfilled' ? knowledgeGraphResult.value : null,
            userActivity: userActivityResult.status === 'fulfilled' ? userActivityResult.value : null,
            queryAnalytics: queryAnalyticsResult.status === 'fulfilled' ? queryAnalyticsResult.value : null,
            documentPopularity: documentPopularityResult.status === 'fulfilled' ? documentPopularityResult.value : null,
            storage: storageResult.status === 'fulfilled' ? storageResult.value : null,
            configuration: configResult.status === 'fulfilled' ? configResult.value : null,
            modelInfo: modelInfoResult.status === 'fulfilled' ? modelInfoResult.value : null,
            metrics: metricsResult.status === 'fulfilled' ? metricsResult.value : null
        };

        // Cache the result
        analyticsCache.data = comprehensive;
        analyticsCache.timestamp = now;

        // Only render if we have at least basic data
        if (comprehensive.basic || comprehensive.metrics) {
            renderComprehensiveAnalytics(comprehensive);
            checkAlerts(comprehensive);
        } else {
            console.warn('[Analytics] No data available to render');
            // Show error message in UI
            const analyticsTab = document.getElementById('analyticsTab');
            if (analyticsTab) {
                analyticsTab.innerHTML = `
                    <div style="padding: 2rem; text-align: center;">
                        <h2 style="color: var(--text-primary); margin-bottom: 1rem;">Unable to Load Analytics</h2>
                        <p style="color: var(--text-secondary); margin-bottom: 1rem;">
                            The analytics server may not be running or endpoints are unavailable.
                        </p>
                        <p style="color: var(--text-muted); font-size: 0.875rem;">
                            Make sure the Discord bot server is running and try refreshing.
                        </p>
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
        showToast('Error loading analytics - some data may be unavailable', 'warning');
        
        // Try to render with whatever we have
        if (analyticsCache.data) {
            renderComprehensiveAnalytics(analyticsCache.data);
        }
    }
}

// Render comprehensive analytics dashboard
function renderComprehensiveAnalytics(data) {
    if (!data) {
        console.warn('[Analytics] No data to render');
        return;
    }

    const basic = data.basic || data;
    
    // Show loading state removal
    document.querySelectorAll('.loading-state').forEach(el => {
        if (el.parentElement) {
            el.style.display = 'none';
        }
    });

    // Render system health
    renderSystemHealth(basic.system);

    // Render statistics
    renderStatistics(basic);

    // Render basic charts
    renderCharts(basic);

    // Render trends
    if (data.trends) {
        renderTrends(data.trends);
    }

    // Render detailed performance
    if (data.performance) {
        renderDetailedPerformance(data.performance);
    }

    // Render knowledge graph
    if (data.knowledgeGraph) {
        renderKnowledgeGraph(data.knowledgeGraph);
    }

    // Render user activity
    if (data.userActivity) {
        renderUserActivity(data.userActivity);
    }

    // Render LLM info
    if (data.modelInfo) {
        renderLLMInfo(data.modelInfo);
    }

    // Render query analytics
    if (data.queryAnalytics) {
        renderQueryAnalytics(data.queryAnalytics);
    }

    // Render document popularity
    if (data.documentPopularity) {
        renderDocumentPopularity(data.documentPopularity);
    }

    // Render storage details
    if (data.storage || basic.documents?.storage) {
        renderStorageDetails(data.storage || basic.documents.storage);
    }

    // Render configuration
    if (data.configuration) {
        renderConfiguration(data.configuration);
    }

    // Render activity
    renderActivity(basic);

    // Render performance metrics
    renderPerformanceMetrics(basic.performance || data.metrics);

    // Render real-time monitor
    renderRealtimeMonitor(data);
}

// Render system health cards
function renderSystemHealth(system) {
    // Neo4j
    const neo4j = system?.neo4j || {};
    const neo4jStatus = neo4j.connected ? 'Connected' : 'Disconnected';
    const neo4jStatusEl = document.getElementById('neo4jHealthStatus');
    if (neo4jStatusEl) {
        neo4jStatusEl.textContent = neo4jStatus;
        neo4jStatusEl.className = `health-status ${neo4j.connected ? 'status-connected' : 'status-disconnected'}`;
    }
    updateElement('neo4jStatusValue', neo4jStatus);
    updateElement('neo4jVersion', neo4j.version || 'N/A');

    // Elasticsearch
    const es = system?.elasticsearch || {};
    const esStatus = es.enabled && es.connected ? 'Connected' : es.enabled ? 'Disconnected' : 'Disabled';
    const esStatusEl = document.getElementById('elasticsearchHealthStatus');
    if (esStatusEl) {
        esStatusEl.textContent = esStatus;
        if (es.enabled && es.connected) {
            esStatusEl.className = 'health-status status-connected';
        } else if (es.enabled) {
            esStatusEl.className = 'health-status status-warning';
        } else {
            esStatusEl.className = 'health-status status-disconnected';
        }
    }
    updateElement('elasticsearchStatusValue', esStatus);
    updateElement('elasticsearchVersion', es.version || 'N/A');
    updateElement('elasticsearchDocCount', es.indices?.documents?.count?.toLocaleString() || '0');
    updateElement('elasticsearchChunkCount', es.indices?.chunks?.count?.toLocaleString() || '0');

    // Server
    const server = system?.server || {};
    updateElement('serverUptime', formatUptime(server.uptime || 0));
    updateElement('serverMemory', formatBytes(server.memory?.heapUsed || 0));
    updateElement('serverNodeVersion', server.nodeVersion || 'N/A');
}

// Render statistics cards
function renderStatistics(data) {
    const memories = data.memories || {};
    const documents = data.documents || {};
    const channels = data.memories?.topChannels || [];

    updateElement('analyticsTotalMemories', memories.total?.toLocaleString() || '0');
    updateElement('analyticsTotalDocuments', documents.total?.toLocaleString() || '0');
    updateElement('analyticsTotalChannels', channels.length?.toLocaleString() || '0');
    updateElement('analyticsTotalChunks', documents.storage?.totalChunks?.toLocaleString() || '0');

    // Memory breakdown
    const memoryBreakdown = Object.entries(memories.byType || {})
        .map(([type, count]) => `${type}: ${count}`)
        .join(', ');
    updateElement('analyticsMemoryBreakdown', memoryBreakdown || 'No data');

    // Document breakdown
    const docBreakdown = Object.entries(documents.byType || {})
        .map(([type, count]) => `${type}: ${count}`)
        .join(', ');
    updateElement('analyticsDocumentBreakdown', docBreakdown || 'No data');

    // Chunk breakdown
    const avgChunks = documents.storage?.avgChunksPerDoc || 0;
    updateElement('analyticsChunkBreakdown', `Avg: ${avgChunks} chunks/doc`);
}

// Render charts
function renderCharts(data) {
    const memories = data.memories || {};
    const documents = data.documents || {};

    // Memory Types Chart (Pie)
    renderMemoryTypesChart(memories.byType || {});

    // Document Types Chart (Pie)
    renderDocumentTypesChart(documents.byType || {});

    // Top Channels Chart (Bar)
    renderTopChannelsChart(memories.topChannels || []);
}

// Render memory types pie chart
function renderMemoryTypesChart(byType) {
    const ctx = document.getElementById('memoryTypesChart');
    if (!ctx) return;

    const labels = Object.keys(byType);
    const values = Object.values(byType);

    if (memoryTypesChart) {
        memoryTypesChart.destroy();
    }

    memoryTypesChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: [
                    'rgba(138, 173, 244, 0.8)',
                    'rgba(198, 160, 246, 0.8)',
                    'rgba(139, 233, 253, 0.8)',
                    'rgba(166, 218, 149, 0.8)',
                    'rgba(238, 212, 159, 0.8)',
                    'rgba(245, 169, 127, 0.8)'
                ],
                borderColor: 'var(--bg-primary)',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: 'var(--text-primary)',
                        font: {
                            family: 'var(--font-sans)',
                            size: 12
                        }
                    }
                }
            }
        }
    });
}

// Render document types pie chart
function renderDocumentTypesChart(byType) {
    const ctx = document.getElementById('documentTypesChart');
    if (!ctx) return;

    const labels = Object.keys(byType);
    const values = Object.values(byType);

    if (documentTypesChart) {
        documentTypesChart.destroy();
    }

    documentTypesChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: [
                    'rgba(138, 173, 244, 0.8)',
                    'rgba(198, 160, 246, 0.8)',
                    'rgba(139, 233, 253, 0.8)',
                    'rgba(166, 218, 149, 0.8)',
                    'rgba(238, 212, 159, 0.8)'
                ],
                borderColor: 'var(--bg-primary)',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: 'var(--text-primary)',
                        font: {
                            family: 'var(--font-sans)',
                            size: 12
                        }
                    }
                }
            }
        }
    });
}

// Render top channels bar chart
function renderTopChannelsChart(topChannels) {
    const ctx = document.getElementById('topChannelsChart');
    if (!ctx) return;

    const sorted = topChannels.slice(0, 10).sort((a, b) => b.memory_count - a.memory_count);
    const labels = sorted.map(ch => ch.channel_name || 'Unknown').slice(0, 10);
    const values = sorted.map(ch => ch.memory_count).slice(0, 10);

    if (topChannelsChart) {
        topChannelsChart.destroy();
    }

    topChannelsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Memories',
                data: values,
                backgroundColor: 'rgba(138, 173, 244, 0.8)',
                borderColor: 'var(--accent)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: 'var(--text-muted)',
                        font: {
                            family: 'var(--font-sans)',
                            size: 11
                        }
                    },
                    grid: {
                        color: 'var(--border-color)'
                    }
                },
                y: {
                    ticks: {
                        color: 'var(--text-muted)',
                        font: {
                            family: 'var(--font-sans)',
                            size: 11
                        }
                    },
                    grid: {
                        color: 'var(--border-color)'
                    }
                }
            }
        }
    });
}

// Render activity list
function renderActivity(data) {
    const activityList = document.getElementById('recentActivityList');
    if (!activityList) return;

    const memories = data.memories?.recent || [];
    const documents = data.documents?.recent || [];

    // Combine and sort by date
    const activities = [
        ...memories.map(m => ({
            type: 'memory',
            icon: '🧠',
            text: `Memory created in ${m.channel || 'unknown'}`,
            date: m.created_at
        })),
        ...documents.map(d => ({
            type: 'document',
            icon: '📄',
            text: `Document uploaded: ${d.file_name || 'unknown'}`,
            date: d.uploaded_at
        }))
    ].sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 20);

    if (activities.length === 0) {
        activityList.innerHTML = '<div class="empty-state"><p>No recent activity</p></div>';
        return;
    }

    activityList.innerHTML = activities.map(activity => `
        <div class="activity-item">
            <div class="activity-icon">${activity.icon}</div>
            <div class="activity-content">
                <div class="activity-text">${escapeHtml(activity.text)}</div>
                <div class="activity-meta">${formatDate(activity.date)}</div>
            </div>
        </div>
    `).join('');
}

// Render performance metrics
function renderPerformanceMetrics(performance) {
    const metricsContainer = document.getElementById('performanceMetrics');
    if (!metricsContainer) return;

    if (!performance || !performance.avgLatency && !performance.cacheHitRate) {
        metricsContainer.innerHTML = '<div class="empty-state"><p>Performance metrics not available</p></div>';
        return;
    }

    const metrics = [];
    if (performance.avgLatency !== null) {
        metrics.push({
            label: 'Avg Latency',
            value: `${performance.avgLatency.toFixed(2)}ms`,
            class: performance.avgLatency < 100 ? 'success' : performance.avgLatency < 500 ? 'warning' : 'error'
        });
    }
    if (performance.cacheHitRate !== null) {
        metrics.push({
            label: 'Cache Hit Rate',
            value: `${(performance.cacheHitRate * 100).toFixed(1)}%`,
            class: performance.cacheHitRate > 0.7 ? 'success' : performance.cacheHitRate > 0.4 ? 'warning' : 'error'
        });
    }
    if (performance.totalQueries) {
        metrics.push({
            label: 'Total Queries',
            value: performance.totalQueries.toLocaleString(),
            class: ''
        });
    }
    if (performance.intentClassifications) {
        metrics.push({
            label: 'Intent Classifications',
            value: performance.intentClassifications.toLocaleString(),
            class: ''
        });
    }

    metricsContainer.innerHTML = metrics.map(m => `
        <div class="performance-metric">
            <span class="performance-metric-label">${m.label}</span>
            <span class="performance-metric-value ${m.class}">${m.value}</span>
        </div>
    `).join('');
}

// Utility functions for analytics
function updateElement(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Start analytics auto-refresh
function startAnalyticsAutoRefresh() {
    if (analyticsRefreshInterval) {
        clearInterval(analyticsRefreshInterval);
    }
    
    analyticsRefreshInterval = setInterval(() => {
        if (AppState.currentTab === 'analytics') {
            loadAnalytics();
        }
    }, 30000); // Refresh every 30 seconds
}

// Stop analytics auto-refresh
function stopAnalyticsAutoRefresh() {
    if (analyticsRefreshInterval) {
        clearInterval(analyticsRefreshInterval);
        analyticsRefreshInterval = null;
    }
}

// ============================================
// Comprehensive Analytics Rendering Functions
// ============================================

// Render trends charts
function renderTrends(trends) {
    if (!trends) {
        console.warn('[Analytics] No trends data');
        return;
    }

    // Only render if Chart.js is available
    if (typeof Chart === 'undefined') {
        console.error('[Analytics] Chart.js not loaded');
        return;
    }

    // Memory Growth
    if (trends.memories && trends.memories.length > 0) {
        renderTrendChart('memoryGrowthChart', trends.memories, 'Memory Growth', 'rgba(138, 173, 244, 0.8)');
    }
    
    // Document Growth
    if (trends.documents && trends.documents.length > 0) {
        renderTrendChart('documentGrowthChart', trends.documents, 'Document Growth', 'rgba(198, 160, 246, 0.8)');
    }
    
    // Query Volume
    if (trends.queries && trends.queries.length > 0) {
        renderTrendChart('queryVolumeChart', trends.queries, 'Query Volume', 'rgba(166, 218, 149, 0.8)');
    }
    
    // Storage Growth
    if (trends.storage && trends.storage.length > 0) {
        renderTrendChart('storageGrowthChart', trends.storage, 'Storage Growth', 'rgba(238, 212, 159, 0.8)');
    }
}

// Render trend line chart
function renderTrendChart(canvasId, data, label, color) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || !data || data.length === 0) return;

    // Destroy existing chart if it exists
    const chartMap = {
        'memoryGrowthChart': memoryGrowthChart,
        'documentGrowthChart': documentGrowthChart,
        'queryVolumeChart': queryVolumeChart,
        'storageGrowthChart': storageGrowthChart
    };
    
    const existingChart = chartMap[canvasId];
    if (existingChart && typeof existingChart.destroy === 'function') {
        try {
            existingChart.destroy();
        } catch (e) {
            console.warn('Error destroying chart:', e);
        }
    }

    // Check if Chart.js is available
    if (typeof Chart === 'undefined') {
        console.error('[Analytics] Chart.js not loaded');
        return;
    }

    const labels = data.map(d => {
        const date = new Date(d.date);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });
    const values = data.map(d => d.cumulative || d.value || 0);

    // Create and store chart instance
    let newChart;
    try {
        newChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: values,
                borderColor: color,
                backgroundColor: color.replace('0.8', '0.1'),
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: 'var(--text-muted)',
                        font: { family: 'var(--font-sans)', size: 11 }
                    },
                    grid: { color: 'var(--border-color)' }
                },
                y: {
                    ticks: {
                        color: 'var(--text-muted)',
                        font: { family: 'var(--font-sans)', size: 11 }
                    },
                    grid: { color: 'var(--border-color)' }
                }
            }
        }
    });
    
    // Store chart instance
    if (canvasId === 'memoryGrowthChart') memoryGrowthChart = newChart;
    else if (canvasId === 'documentGrowthChart') documentGrowthChart = newChart;
    else if (canvasId === 'queryVolumeChart') queryVolumeChart = newChart;
    else if (canvasId === 'storageGrowthChart') storageGrowthChart = newChart;
    } catch (error) {
        console.error(`[Analytics] Error creating chart ${canvasId}:`, error);
    }
}

// Render detailed performance metrics
function renderDetailedPerformance(performance) {
    if (!performance) return;

    // Latency metrics
    const latencyEl = document.getElementById('latencyMetrics');
    if (latencyEl && performance.latency) {
        const lat = performance.latency;
        latencyEl.innerHTML = `
            <div class="performance-metric">
                <span class="performance-metric-label">P50</span>
                <span class="performance-metric-value">${lat.p50?.toFixed(2) || 0}ms</span>
            </div>
            <div class="performance-metric">
                <span class="performance-metric-label">P95</span>
                <span class="performance-metric-value">${lat.p95?.toFixed(2) || 0}ms</span>
            </div>
            <div class="performance-metric">
                <span class="performance-metric-label">P99</span>
                <span class="performance-metric-value">${lat.p99?.toFixed(2) || 0}ms</span>
            </div>
            <div class="performance-metric">
                <span class="performance-metric-label">Mean</span>
                <span class="performance-metric-value">${lat.mean?.toFixed(2) || 0}ms</span>
            </div>
            <div class="performance-metric">
                <span class="performance-metric-label">Max</span>
                <span class="performance-metric-value">${lat.max?.toFixed(2) || 0}ms</span>
            </div>
        `;
        
        // Latency distribution chart
        renderLatencyDistributionChart([lat.p50 || 0, lat.p95 || 0, lat.p99 || 0, lat.mean || 0]);
    }

    // Cache metrics
    const cacheEl = document.getElementById('cacheMetrics');
    if (cacheEl && performance.cacheStats) {
        const cache = performance.cacheStats;
        cacheEl.innerHTML = `
            <div class="performance-metric">
                <span class="performance-metric-label">Hit Rate</span>
                <span class="performance-metric-value ${cache.hitRate > 0.7 ? 'success' : ''}">${((cache.hitRate || 0) * 100).toFixed(1)}%</span>
            </div>
            <div class="performance-metric">
                <span class="performance-metric-label">Hits</span>
                <span class="performance-metric-value">${(cache.hits || 0).toLocaleString()}</span>
            </div>
            <div class="performance-metric">
                <span class="performance-metric-label">Misses</span>
                <span class="performance-metric-value">${(cache.misses || 0).toLocaleString()}</span>
            </div>
        `;
        
        // Cache performance chart
        renderCachePerformanceChart(cache);
    }

    // Operation metrics
    const opEl = document.getElementById('operationMetrics');
    if (opEl && performance.operations) {
        const ops = performance.operations;
        opEl.innerHTML = `
            <div class="performance-metric">
                <span class="performance-metric-label">Retrieval</span>
                <span class="performance-metric-value">${(ops.retrieval || 0).toLocaleString()}</span>
            </div>
            <div class="performance-metric">
                <span class="performance-metric-label">Generation</span>
                <span class="performance-metric-value">${(ops.generation || 0).toLocaleString()}</span>
            </div>
            <div class="performance-metric">
                <span class="performance-metric-label">Reranking</span>
                <span class="performance-metric-value">${(ops.reranking || 0).toLocaleString()}</span>
            </div>
        `;
        
        renderOperationBreakdownChart(ops);
    }

    // Error metrics
    const errorEl = document.getElementById('errorMetrics');
    if (errorEl) {
        const errorRate = performance.errorRate || 0;
        errorEl.innerHTML = `
            <div class="performance-metric">
                <span class="performance-metric-label">Error Rate</span>
                <span class="performance-metric-value ${errorRate > 0.1 ? 'error' : errorRate > 0.05 ? 'warning' : 'success'}">${(errorRate * 100).toFixed(2)}%</span>
            </div>
        `;
    }
}

// Render latency distribution chart
function renderLatencyDistributionChart(values) {
    const ctx = document.getElementById('latencyDistributionChart');
    if (!ctx) return;

    if (latencyDistributionChart) {
        latencyDistributionChart.destroy();
    }

    latencyDistributionChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['P50', 'P95', 'P99', 'Mean'],
            datasets: [{
                label: 'Latency (ms)',
                data: values,
                backgroundColor: [
                    'rgba(138, 173, 244, 0.8)',
                    'rgba(198, 160, 246, 0.8)',
                    'rgba(139, 233, 253, 0.8)',
                    'rgba(166, 218, 149, 0.8)'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    ticks: { color: 'var(--text-muted)', font: { family: 'var(--font-sans)', size: 11 } },
                    grid: { color: 'var(--border-color)' }
                },
                x: {
                    ticks: { color: 'var(--text-muted)', font: { family: 'var(--font-sans)', size: 11 } },
                    grid: { color: 'var(--border-color)' }
                }
            }
        }
    });
}

// Render cache performance chart
function renderCachePerformanceChart(cache) {
    const ctx = document.getElementById('cachePerformanceChart');
    if (!ctx) return;

    if (cachePerformanceChart) {
        cachePerformanceChart.destroy();
    }

    cachePerformanceChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Hits', 'Misses'],
            datasets: [{
                data: [cache.hits || 0, cache.misses || 0],
                backgroundColor: [
                    'rgba(166, 218, 149, 0.8)',
                    'rgba(237, 135, 150, 0.8)'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: 'var(--text-primary)', font: { family: 'var(--font-sans)', size: 12 } }
                }
            }
        }
    });
}

// Render operation breakdown chart
function renderOperationBreakdownChart(ops) {
    const ctx = document.getElementById('operationBreakdownChart');
    if (!ctx) return;

    if (operationBreakdownChart) {
        operationBreakdownChart.destroy();
    }

    operationBreakdownChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['Retrieval', 'Generation', 'Reranking'],
            datasets: [{
                data: [ops.retrieval || 0, ops.generation || 0, ops.reranking || 0],
                backgroundColor: [
                    'rgba(138, 173, 244, 0.8)',
                    'rgba(198, 160, 246, 0.8)',
                    'rgba(139, 233, 253, 0.8)'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: 'var(--text-primary)', font: { family: 'var(--font-sans)', size: 12 } }
                }
            }
        }
    });
}

// Render knowledge graph
function renderKnowledgeGraph(kg) {
    if (!kg) return;

    // Topic clusters
    const topicsEl = document.getElementById('topicClusters');
    if (topicsEl && kg.topicClusters) {
        if (kg.topicClusters.length === 0) {
            topicsEl.innerHTML = '<div class="empty-state"><p>No topic clusters found</p></div>';
        } else {
            topicsEl.innerHTML = kg.topicClusters.map(topic => `
                <div class="topic-item">
                    <span>${escapeHtml(topic.topic || 'Unknown')}</span>
                    <span class="metric-value">${topic.documentCount || 0}</span>
                </div>
            `).join('');
        }
        
        // Topic clusters chart
        renderTopicClustersChart(kg.topicClusters);
    }

    // KG stats
    const statsEl = document.getElementById('kgStats');
    if (statsEl) {
        statsEl.innerHTML = `
            <div class="kg-stat-item">
                <span class="metric-label">Total Topics</span>
                <span class="metric-value">${kg.totalTopics || 0}</span>
            </div>
            <div class="kg-stat-item">
                <span class="metric-label">Total Connections</span>
                <span class="metric-value">${kg.totalConnections || 0}</span>
            </div>
        `;
    }
}

// Render topic clusters chart
function renderTopicClustersChart(topics) {
    const ctx = document.getElementById('topicClustersChart');
    if (!ctx || !topics || topics.length === 0) return;

    if (topicClustersChart) {
        topicClustersChart.destroy();
    }

    const sorted = topics.slice(0, 10).sort((a, b) => b.documentCount - a.documentCount);
    topicClustersChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted.map(t => t.topic),
            datasets: [{
                label: 'Documents',
                data: sorted.map(t => t.documentCount),
                backgroundColor: 'rgba(138, 173, 244, 0.8)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            indexAxis: 'y',
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    ticks: { color: 'var(--text-muted)', font: { family: 'var(--font-sans)', size: 11 } },
                    grid: { color: 'var(--border-color)' }
                },
                y: {
                    ticks: { color: 'var(--text-muted)', font: { family: 'var(--font-sans)', size: 11 } },
                    grid: { color: 'var(--border-color)' }
                }
            }
        }
    });
}

// Render user activity
function renderUserActivity(users) {
    if (!users) return;

    // Top users list
    const usersEl = document.getElementById('topUsersList');
    if (usersEl && users.topUsers) {
        if (users.topUsers.length === 0) {
            usersEl.innerHTML = '<div class="empty-state"><p>No user data available</p></div>';
        } else {
            usersEl.innerHTML = users.topUsers.map((user, idx) => `
                <div class="user-item">
                    <div>
                        <div style="font-weight: 600; color: var(--text-primary);">#${idx + 1} ${escapeHtml(user.username || 'Unknown')}</div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">${user.userId || 'N/A'}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-weight: 600; color: var(--accent);">${(user.memoryCount || 0).toLocaleString()}</div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">memories</div>
                    </div>
                </div>
            `).join('');
        }
        
        // Top users chart
        renderTopUsersChart(users.topUsers);
    }

    // Engagement metrics
    const engagementEl = document.getElementById('engagementMetrics');
    if (engagementEl) {
        engagementEl.innerHTML = `
            <div class="performance-metric">
                <span class="performance-metric-label">Total Users</span>
                <span class="performance-metric-value">${(users.totalUsers || 0).toLocaleString()}</span>
            </div>
            <div class="performance-metric">
                <span class="performance-metric-label">Active Users</span>
                <span class="performance-metric-value success">${(users.activeUsers || 0).toLocaleString()}</span>
            </div>
        `;
    }
}

// Render top users chart
function renderTopUsersChart(users) {
    const ctx = document.getElementById('topUsersChart');
    if (!ctx || !users || users.length === 0) return;

    if (topUsersChart) {
        topUsersChart.destroy();
    }

    const top10 = users.slice(0, 10);
    topUsersChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: top10.map(u => u.username || 'Unknown'),
            datasets: [{
                label: 'Memories',
                data: top10.map(u => u.memoryCount || 0),
                backgroundColor: 'rgba(138, 173, 244, 0.8)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            indexAxis: 'y',
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    ticks: { color: 'var(--text-muted)', font: { family: 'var(--font-sans)', size: 11 } },
                    grid: { color: 'var(--border-color)' }
                },
                y: {
                    ticks: { color: 'var(--text-muted)', font: { family: 'var(--font-sans)', size: 11 } },
                    grid: { color: 'var(--border-color)' }
                }
            }
        }
    });
}

// Render LLM info
function renderLLMInfo(modelInfo) {
    if (!modelInfo) return;

    // LLM Provider
    const llmEl = document.getElementById('llmDetails');
    if (llmEl) {
        const provider = modelInfo.llmProvider || 'unknown';
        const statusEl = document.getElementById('llmProviderStatus');
        if (statusEl) {
            statusEl.textContent = provider.toUpperCase();
            statusEl.className = 'llm-status status-connected';
        }
        
        llmEl.innerHTML = `
            <div class="llm-detail-item">
                <span class="metric-label">Model</span>
                <span class="metric-value">${escapeHtml(modelInfo.llmModel || 'N/A')}</span>
            </div>
            <div class="llm-detail-item">
                <span class="metric-label">Streaming</span>
                <span class="metric-value ${modelInfo.streamingEnabled ? 'enabled' : 'disabled'}">${modelInfo.streamingEnabled ? 'Enabled' : 'Disabled'}</span>
            </div>
        `;
    }

    // Embedding model
    const embEl = document.getElementById('embeddingDetails');
    if (embEl) {
        embEl.innerHTML = `
            <div class="llm-detail-item">
                <span class="metric-label">Model</span>
                <span class="metric-value">${escapeHtml(modelInfo.embeddingModel || 'N/A')}</span>
            </div>
            <div class="llm-detail-item">
                <span class="metric-label">Dimensions</span>
                <span class="metric-value">${modelInfo.embeddingDimension || 0}</span>
            </div>
            <div class="llm-detail-item">
                <span class="metric-label">GPU</span>
                <span class="metric-value ${modelInfo.gpuEnabled ? 'enabled' : 'disabled'}">${modelInfo.gpuEnabled ? 'Enabled' : 'Disabled'}</span>
            </div>
        `;
    }
}

// Render query analytics
function renderQueryAnalytics(queries) {
    if (!queries) return;

    // Query types chart
    const ctx = document.getElementById('queryTypesChart');
    if (ctx && queries.queryTypes) {
        if (queryTypesChart) {
            queryTypesChart.destroy();
        }
        queryTypesChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(queries.queryTypes),
                datasets: [{
                    data: Object.values(queries.queryTypes),
                    backgroundColor: [
                        'rgba(138, 173, 244, 0.8)',
                        'rgba(198, 160, 246, 0.8)',
                        'rgba(139, 233, 253, 0.8)',
                        'rgba(166, 218, 149, 0.8)'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: 'var(--text-primary)', font: { family: 'var(--font-sans)', size: 12 } }
                    }
                }
            }
        });
    }

    // Query stats
    const statsEl = document.getElementById('queryStats');
    if (statsEl) {
        statsEl.innerHTML = `
            <div class="performance-metric">
                <span class="performance-metric-label">Total Queries</span>
                <span class="performance-metric-value">${(queries.totalQueries || 0).toLocaleString()}</span>
            </div>
            <div class="performance-metric">
                <span class="performance-metric-label">Avg Length</span>
                <span class="performance-metric-value">${(queries.avgQueryLength || 0).toFixed(0)} chars</span>
            </div>
        `;
    }

    // Popular queries
    const popularEl = document.getElementById('popularQueries');
    if (popularEl && queries.popularQueries) {
        if (queries.popularQueries.length === 0) {
            popularEl.innerHTML = '<div class="empty-state"><p>No query data available</p></div>';
        } else {
            popularEl.innerHTML = queries.popularQueries.slice(0, 10).map(q => `
                <div class="query-item">${escapeHtml(q.query || q)}</div>
            `).join('');
        }
    }
}

// Render document popularity
function renderDocumentPopularity(popularity) {
    if (!popularity) return;

    // Popular documents list
    const listEl = document.getElementById('popularDocumentsList');
    if (listEl && popularity.mostQueried) {
        if (popularity.mostQueried.length === 0) {
            listEl.innerHTML = '<div class="empty-state"><p>No document data available</p></div>';
        } else {
            listEl.innerHTML = popularity.mostQueried.map((doc, idx) => `
                <div class="popular-doc-item">
                    <div>
                        <div style="font-weight: 600; color: var(--text-primary);">#${idx + 1} ${escapeHtml(doc.fileName || 'Unknown')}</div>
                        <div style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">${escapeHtml(doc.docId || 'N/A')}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-weight: 600; color: var(--accent);">${(doc.queryCount || 0).toLocaleString()}</div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">queries</div>
                    </div>
                </div>
            `).join('');
        }
    }
}

// Render storage details
function renderStorageDetails(storage) {
    if (!storage) return;

    const detailsEl = document.getElementById('storageDetails');
    if (detailsEl) {
        detailsEl.innerHTML = `
            <div class="storage-detail-item">
                <span class="metric-label">Total Chunks</span>
                <span class="metric-value">${(storage.totalChunks || 0).toLocaleString()}</span>
            </div>
            <div class="storage-detail-item">
                <span class="metric-label">Avg Chunk Size</span>
                <span class="metric-value">${(storage.avgChunkSize || 0).toLocaleString()} bytes</span>
            </div>
            <div class="storage-detail-item">
                <span class="metric-label">Total Size</span>
                <span class="metric-value">${formatBytes(storage.totalSize || 0)}</span>
            </div>
        `;
    }

    // Storage by type chart
    const ctx = document.getElementById('storageByTypeChart');
    if (ctx && storage.byType) {
        if (storageByTypeChart) {
            storageByTypeChart.destroy();
        }
        storageByTypeChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: Object.keys(storage.byType),
                datasets: [{
                    data: Object.values(storage.byType),
                    backgroundColor: [
                        'rgba(138, 173, 244, 0.8)',
                        'rgba(198, 160, 246, 0.8)',
                        'rgba(139, 233, 253, 0.8)',
                        'rgba(166, 218, 149, 0.8)'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: 'var(--text-primary)', font: { family: 'var(--font-sans)', size: 12 } }
                    }
                }
            }
        });
    }
}

// Render configuration
function renderConfiguration(config) {
    if (!config) return;

    // Feature flags
    const flagsEl = document.getElementById('featureFlags');
    if (flagsEl) {
        flagsEl.innerHTML = `
            <div class="config-item">
                <span class="config-item-label">Elasticsearch</span>
                <span class="config-item-value ${config.elasticsearchEnabled ? 'enabled' : 'disabled'}">${config.elasticsearchEnabled ? 'Enabled' : 'Disabled'}</span>
            </div>
            <div class="config-item">
                <span class="config-item-label">Hybrid Search</span>
                <span class="config-item-value ${config.hybridSearchEnabled ? 'enabled' : 'disabled'}">${config.hybridSearchEnabled ? 'Enabled' : 'Disabled'}</span>
            </div>
            <div class="config-item">
                <span class="config-item-label">Query Expansion</span>
                <span class="config-item-value ${config.queryExpansionEnabled ? 'enabled' : 'disabled'}">${config.queryExpansionEnabled ? 'Enabled' : 'Disabled'}</span>
            </div>
            <div class="config-item">
                <span class="config-item-label">Temporal Weighting</span>
                <span class="config-item-value ${config.temporalWeightingEnabled ? 'enabled' : 'disabled'}">${config.temporalWeightingEnabled ? 'Enabled' : 'Disabled'}</span>
            </div>
            <div class="config-item">
                <span class="config-item-label">Cache</span>
                <span class="config-item-value ${config.cacheEnabled ? 'enabled' : 'disabled'}">${config.cacheEnabled ? 'Enabled' : 'Disabled'}</span>
            </div>
            <div class="config-item">
                <span class="config-item-label">GPU</span>
                <span class="config-item-value ${config.gpuEnabled ? 'enabled' : 'disabled'}">${config.gpuEnabled ? 'Enabled' : 'Disabled'}</span>
            </div>
        `;
    }

    // Search config
    const searchEl = document.getElementById('searchConfig');
    if (searchEl) {
        searchEl.innerHTML = `
            <div class="config-item">
                <span class="config-item-label">LLM Provider</span>
                <span class="config-item-value">${escapeHtml(config.llmProvider || 'N/A')}</span>
            </div>
        `;
    }

    // RAG config
    const ragEl = document.getElementById('ragConfig');
    if (ragEl) {
        ragEl.innerHTML = `
            <div class="config-item">
                <span class="config-item-label">Hybrid Search</span>
                <span class="config-item-value ${config.hybridSearchEnabled ? 'enabled' : 'disabled'}">${config.hybridSearchEnabled ? 'Enabled' : 'Disabled'}</span>
            </div>
        `;
    }
}

// Render real-time monitor
function renderRealtimeMonitor(data) {
    const liveEl = document.getElementById('liveActivity');
    if (liveEl) {
        // Simulate live activity
        const activities = [
            { type: 'query', text: 'New query processed', time: 'just now' },
            { type: 'memory', text: 'Memory created', time: '2s ago' },
            { type: 'document', text: 'Document indexed', time: '5s ago' }
        ];
        
        liveEl.innerHTML = activities.map(a => `
            <div class="activity-item">
                <div class="activity-icon">${a.type === 'query' ? '🔍' : a.type === 'memory' ? '🧠' : '📄'}</div>
                <div class="activity-content">
                    <div class="activity-text">${escapeHtml(a.text)}</div>
                    <div class="activity-meta">${a.time}</div>
                </div>
            </div>
        `).join('');
    }

    // System load chart
    const loadCtx = document.getElementById('systemLoadChart');
    if (loadCtx) {
        if (systemLoadChart) {
            systemLoadChart.destroy();
        }
        
        // Simulate system load data
        const loadData = Array.from({ length: 20 }, () => Math.random() * 100);
        systemLoadChart = new Chart(loadCtx, {
            type: 'line',
            data: {
                labels: Array.from({ length: 20 }, (_, i) => i),
                datasets: [{
                    label: 'CPU %',
                    data: loadData,
                    borderColor: 'rgba(138, 173, 244, 0.8)',
                    backgroundColor: 'rgba(138, 173, 244, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        min: 0,
                        max: 100,
                        ticks: { color: 'var(--text-muted)', font: { family: 'var(--font-sans)', size: 11 } },
                        grid: { color: 'var(--border-color)' }
                    },
                    x: {
                        ticks: { color: 'var(--text-muted)', font: { family: 'var(--font-sans)', size: 11 } },
                        grid: { color: 'var(--border-color)' }
                    }
                }
            }
        });
    }
}

// Update trends time range
function updateTrendsTimeRange() {
    const days = parseInt(document.getElementById('trendsTimeRange')?.value || 30);
    loadTrendsData(days);
}

// Load trends data
async function loadTrendsData(days) {
    try {
        const response = await fetch(`${API_BASE}/api/analytics/trends?days=${days}`);
        const trends = await response.json();
        renderTrends(trends);
    } catch (error) {
        console.error('Error loading trends:', error);
    }
}

// Refresh activity
function refreshActivity() {
    loadAnalytics();
}

// Export data
async function exportData(format = 'json') {
    try {
        if (format === 'pdf') {
            showToast('PDF export coming soon', 'info');
            return;
        }
        
        const response = await fetch(`${API_BASE}/api/export?format=${format}`);
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `analytics-export-${Date.now()}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast(`Exported as ${format.toUpperCase()}`, 'success');
    } catch (error) {
        console.error('Error exporting:', error);
        showToast('Export failed', 'error');
    }
}

// Toggle export menu
function toggleExportMenu() {
    const menu = document.getElementById('exportMenu');
    if (menu) {
        menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    }
}

// Close export menu when clicking outside
document.addEventListener('click', (e) => {
    const menu = document.getElementById('exportMenu');
    const btn = document.querySelector('.export-dropdown button');
    if (menu && btn && !menu.contains(e.target) && !btn.contains(e.target)) {
        menu.style.display = 'none';
    }
});

// Toggle alerts panel
function toggleAlerts() {
    const panel = document.getElementById('alertsPanel');
    if (panel) {
        panel.style.display = panel.style.display === 'none' ? 'flex' : 'none';
    }
}

// Check alerts
function checkAlerts(data) {
    if (!data) return;
    
    alerts = [];
    
    // Check system health
    if (data.basic?.system) {
        const system = data.basic.system;
        if (!system.neo4j?.connected) {
            alerts.push({
                type: 'error',
                title: 'Neo4j Disconnected',
                message: 'Neo4j database is not connected',
                time: new Date().toISOString()
            });
        }
        if (system.elasticsearch?.enabled && !system.elasticsearch?.connected) {
            alerts.push({
                type: 'warning',
                title: 'Elasticsearch Disconnected',
                message: 'Elasticsearch is enabled but not connected',
                time: new Date().toISOString()
            });
        }
    }
    
    // Check performance
    if (data.performance) {
        const perf = data.performance;
        if (perf.errorRate > 0.1) {
            alerts.push({
                type: 'error',
                title: 'High Error Rate',
                message: `Error rate is ${(perf.errorRate * 100).toFixed(1)}%`,
                time: new Date().toISOString()
            });
        }
        if (perf.latency?.p95 > 1000) {
            alerts.push({
                type: 'warning',
                title: 'High Latency',
                message: `P95 latency is ${perf.latency.p95.toFixed(0)}ms`,
                time: new Date().toISOString()
            });
        }
    }
    
    // Update alerts UI
    updateAlertsUI();
}

// Update alerts UI
function updateAlertsUI() {
    const badge = document.getElementById('alertBadge');
    const list = document.getElementById('alertsList');
    
    if (badge) {
        if (alerts.length > 0) {
            badge.textContent = alerts.length;
            badge.style.display = 'block';
        } else {
            badge.style.display = 'none';
        }
    }
    
    if (list) {
        if (alerts.length === 0) {
            list.innerHTML = '<div class="empty-state"><p>No active alerts</p></div>';
        } else {
            list.innerHTML = alerts.map(alert => `
                <div class="alert-item ${alert.type}">
                    <div class="alert-title">${escapeHtml(alert.title)}</div>
                    <div class="alert-message">${escapeHtml(alert.message)}</div>
                    <div class="alert-time">${formatDate(alert.time)}</div>
                </div>
            `).join('');
        }
    }
}

// Format date helper
function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    
    if (diffSecs < 60) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    
    return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        hour: '2-digit', 
        minute: '2-digit' 
    });
}
