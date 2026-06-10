/**
 * Blocklist page JavaScript
 * Manages blocklist UI interactions and API calls
 */

// State
let currentTab = 'artist'; // 'artist' or 'song' (singular for API)
let currentPage = 1;
let totalPages = 1;
let selectedItems = []; // Array of {type, id, name}
let searchTimeout = null;
let searchResultsData = []; // Store search results to avoid HTML attribute escaping issues
let debugLog = []; // Store debug messages

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Don't update debug state on initial load - wait for debug panel to be opened
    loadStats();
    loadBlocklist();

    // Setup search input with debouncing
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const query = this.value.trim();

            if (query.length >= 2) {
                searchTimeout = setTimeout(() => searchItems(query), 300);
            } else {
                document.getElementById('searchResults').innerHTML = '';
            }
        });
    }
});

/**
 * Load blocklist statistics
 */
async function loadStats() {
    try {
        const response = await fetch('/api/blocklist/stats');

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const stats = await response.json();

        const statArtists = document.getElementById('stat-artists');
        const statSongs = document.getElementById('stat-songs');
        const statTotal = document.getElementById('stat-total');
        const tabArtistsCount = document.getElementById('tab-artists-count');
        const tabSongsCount = document.getElementById('tab-songs-count');

        if (statArtists) statArtists.textContent = stats.total_artists || 0;
        if (statSongs) statSongs.textContent = stats.total_song_entries || 0;
        if (statTotal) statTotal.textContent = stats.total_songs_affected || 0;
        if (tabArtistsCount) tabArtistsCount.textContent = stats.total_artists || 0;
        if (tabSongsCount) tabSongsCount.textContent = stats.total_song_entries || 0;

    } catch (error) {
        console.error('[Blocklist] Error loading stats:', error);
        // Set default values on error
        const statArtists = document.getElementById('stat-artists');
        const statSongs = document.getElementById('stat-songs');
        const statTotal = document.getElementById('stat-total');
        const tabArtistsCount = document.getElementById('tab-artists-count');
        const tabSongsCount = document.getElementById('tab-songs-count');

        if (statArtists) statArtists.textContent = '0';
        if (statSongs) statSongs.textContent = '0';
        if (statTotal) statTotal.textContent = '0';
        if (tabArtistsCount) tabArtistsCount.textContent = '0';
        if (tabSongsCount) tabSongsCount.textContent = '0';
    }
}

/**
 * Load blocklist items for current tab and page
 */
async function loadBlocklist(page = 1) {
    currentPage = page;
    const container = document.getElementById('blocklist-container');

    if (!container) {
        console.error('[Blocklist] ERROR: blocklist-container element not found!');
        return;
    }

    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;

    // Hide pagination while loading
    const paginationContainer = document.getElementById('pagination-container');
    if (paginationContainer) {
        paginationContainer.classList.add('d-none');
    }

    try {
        const url = new URL('/api/blocklist', window.location);
        url.searchParams.set('entity_type', currentTab);
        url.searchParams.set('page', page);
        url.searchParams.set('limit', 50);

        const response = await fetch(url);

        // Check for HTTP errors
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }

        const result = await response.json();

        // Validate response structure
        if (!result || typeof result.pages === 'undefined') {
            throw new Error('Invalid response format from API');
        }

        totalPages = result.pages || 0;
        renderBlocklistItems(result.items || []);
        renderPagination();
    } catch (error) {
        console.error('[Blocklist] Error loading blocklist:', error);
        container.innerHTML = `
            <div class="alert alert-danger">
                <strong>Error loading blocklist:</strong> ${error.message}
                <br><small class="text-muted">Check browser console for details</small>
            </div>
        `;
        // Ensure pagination is hidden on error
        if (paginationContainer) {
            paginationContainer.classList.add('d-none');
        }
    }
}

/**
 * Render blocklist items
 */
function renderBlocklistItems(items) {
    const container = document.getElementById('blocklist-container');

    if (!container) {
        console.error('[Blocklist] ERROR: blocklist-container not found in renderBlocklistItems!');
        return;
    }

    if (items.length === 0) {
        container.innerHTML = `
            <div class="text-center py-5">
                <i class="bi bi-ban display-4 text-muted"></i>
                <p class="text-muted mt-3">No ${currentTab === 'artist' ? 'artists' : 'songs'} on blocklist</p>
            </div>
        `;
        return;
    }

    let html = '';
    for (const item of items) {
        if (item.entity_type === 'artist') {
            html += `
                <div class="blocklist-item">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h5 class="mb-1">
                                <i class="bi bi-person"></i> ${escapeHtml(item.artist_name || 'Unknown Artist')}
                            </h5>
                            <p class="text-muted mb-1">
                                Blocks ${item.songs_blocked === '*' ? 'all' : item.songs_blocked} songs
                            </p>
                            ${item.reason ? `<small class="text-muted">Reason: ${escapeHtml(item.reason)}</small>` : ''}
                            <br>
                            <small class="text-muted">Added ${formatDate(item.created_at)}</small>
                        </div>
                        <button class="btn btn-sm btn-outline-danger" onclick="unblockItem(${item.id})">
                            <i class="bi bi-trash"></i> Unblock
                        </button>
                    </div>
                </div>
            `;
        } else {
            html += `
                <div class="blocklist-item">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h5 class="mb-1">
                                <i class="bi bi-music-note"></i> ${escapeHtml(item.song_title)}
                            </h5>
                            <p class="text-muted mb-1">
                                by ${escapeHtml(item.artist_name || item.song_artist_name || 'Unknown Artist')}
                            </p>
                            ${item.reason ? `<small class="text-muted">Reason: ${escapeHtml(item.reason)}</small>` : ''}
                            <br>
                            <small class="text-muted">Added ${formatDate(item.created_at)}</small>
                        </div>
                        <button class="btn btn-sm btn-outline-danger" onclick="unblockItem(${item.id})">
                            <i class="bi bi-trash"></i> Unblock
                        </button>
                    </div>
                </div>
            `;
        }
    }

    container.innerHTML = html;
}

/**
 * Render pagination controls
 */
function renderPagination() {
    const container = document.getElementById('pagination-container');
    const pagination = document.getElementById('pagination');

    // Handle edge cases
    if (!container || !pagination) {
        console.error('Pagination elements not found');
        return;
    }

    // Validate totalPages
    if (typeof totalPages !== 'number' || totalPages <= 1 || !isFinite(totalPages)) {
        container.classList.add('d-none');
        return;
    }

    container.classList.remove('d-none');

    let html = '';

    // Previous button
    html += `
        <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="loadBlocklist(${currentPage - 1}); return false;">Previous</a>
        </li>
    `;

    // Page numbers
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
            html += `
                <li class="page-item ${i === currentPage ? 'active' : ''}">
                    <a class="page-link" href="#" onclick="loadBlocklist(${i}); return false;">${i}</a>
                </li>
            `;
        } else if (i === currentPage - 3 || i === currentPage + 3) {
            html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
        }
    }

    // Next button
    html += `
        <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="loadBlocklist(${currentPage + 1}); return false;">Next</a>
        </li>
    `;

    pagination.innerHTML = html;
}

/**
 * Switch between tabs
 */
function switchTab(tab) {
    // Convert plural to singular for API
    currentTab = tab === 'artists' ? 'artist' : 'song';
    currentPage = 1;

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    // Reload blocklist
    loadBlocklist();
}

/**
 * Search for artists and songs
 */
async function searchItems(query) {
    const container = document.getElementById('searchResults');
    container.innerHTML = '<div class="text-center"><div class="spinner-border spinner-border-sm"></div></div>';

    try {
        const url = new URL('/api/blocklist/search', window.location);
        url.searchParams.set('q', query);
        url.searchParams.set('limit', 10);

        const response = await fetch(url);
        const results = await response.json();

        renderSearchResults(results);
    } catch (error) {
        console.error('Error searching:', error);
        container.innerHTML = `<div class="alert alert-danger">Error searching: ${error.message}</div>`;
    }
}

/**
 * Render search results
 */
function renderSearchResults(results) {
    const container = document.getElementById('searchResults');

    if (!results.artists?.length && !results.songs?.length) {
        container.innerHTML = '<p class="text-muted text-center">No results found</p>';
        searchResultsData = [];
        return;
    }

    // Store results in array for event handlers
    searchResultsData = [];

    let html = '';
    let itemIndex = 0;

    // Artists
    if (results.artists?.length) {
        html += '<h6 class="mt-2">Artists</h6>';
        for (const artist of results.artists) {
            const isSelected = selectedItems.some(i => i.type === 'artist' && i.id === artist.mbid);
            const itemData = {
                type: 'artist',
                id: artist.mbid,
                name: artist.name,
                songCount: artist.song_count,
                artistName: ''
            };
            searchResultsData.push(itemData);

            html += `
                <div class="search-result-item ${isSelected ? 'selected-item' : ''}" data-search-index="${itemIndex}">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${escapeHtml(artist.name)}</strong>
                            <small class="text-muted d-block">${artist.song_count} songs</small>
                        </div>
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-primary btn-block-all" type="button" data-search-index="${itemIndex}">
                                Block All
                            </button>
                        </div>
                    </div>
                </div>
            `;
            itemIndex++;
        }
    }

    // Songs
    if (results.songs?.length) {
        html += '<h6 class="mt-3">Songs</h6>';
        for (const song of results.songs) {
            const isSelected = selectedItems.some(i => i.type === 'song' && i.id === song.id);
            const itemData = {
                type: 'song',
                id: song.id,
                name: song.title,
                songCount: null,
                artistName: song.artist_name
            };
            searchResultsData.push(itemData);

            html += `
                <div class="search-result-item ${isSelected ? 'selected-item' : ''}" data-search-index="${itemIndex}">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${escapeHtml(song.title)}</strong>
                            <small class="text-muted d-block">by ${escapeHtml(song.artist_name)}</small>
                        </div>
                        <i class="bi bi-plus-circle text-primary"></i>
                    </div>
                </div>
            `;
            itemIndex++;
        }
    }

    container.innerHTML = html;

    // Add event listeners using event delegation with index-based lookup
    container.querySelectorAll('.search-result-item').forEach(item => {
        const clickHandler = function(e) {
            const index = parseInt(this.dataset.searchIndex);
            const data = searchResultsData[index];

            if (!data) return;

            // Don't trigger if clicking the "Block All" button
            if (e.target.closest('.btn-block-all')) {
                e.stopPropagation();
                selectItem(data.type, data.id, data.name, data.songCount, data.artistName, true);
                return;
            }

            selectItem(data.type, data.id, data.name, data.songCount, data.artistName);
        };

        // Remove old listener and add new one
        item.removeEventListener('click', clickHandler);
        item.addEventListener('click', clickHandler);
    });
}

/**
 * Select an item to block
 */
function selectItem(type, id, name, songCount, artistName = '', forceBlockAll = null) {
    // Check if already selected
    const existingIndex = selectedItems.findIndex(i => i.type === type && String(i.id) === String(id));

    if (existingIndex !== -1) {
        // Remove if already selected
        selectedItems.splice(existingIndex, 1);
    } else {
        // Add new selection
        selectedItems.push({
            type: type,
            id: id,
            name: name,
            artistName: artistName,
            blockAll: forceBlockAll !== null ? forceBlockAll : (type === 'artist' && songCount !== null)
        });
    }

    updateSelectedItems();
}

/**
 * Update selected items display
 */
function updateSelectedItems() {
    const container = document.getElementById('selectedItems');
    const countEl = document.getElementById('selectedCount');
    const previewEl = document.getElementById('previewCount');
    const addBtn = document.getElementById('addBtn');
    const selectedContainer = document.getElementById('selectedContainer');

    countEl.textContent = selectedItems.length;

    if (selectedItems.length === 0) {
        container.innerHTML = '';
        previewEl.textContent = '0';
        addBtn.disabled = true;
        selectedContainer.classList.add('d-none');
        return;
    }

    selectedContainer.classList.remove('d-none');

    let html = '';
    let totalSongs = 0;

    for (const item of selectedItems) {
        if (item.type === 'artist') {
            totalSongs += item.blockAll ? 999 : 0; // Approximation
            html += `
                <div class="search-result-item selected-item">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <i class="bi bi-person"></i> ${escapeHtml(item.name)}
                            ${item.blockAll ? '<span class="badge bg-primary ms-2">All Songs</span>' : ''}
                        </div>
                        <button class="btn btn-sm btn-outline-danger" data-remove-type="${item.type}" data-remove-id="${item.id}">
                            <i class="bi bi-x"></i>
                        </button>
                    </div>
                </div>
            `;
        } else {
            totalSongs += 1;
            html += `
                <div class="search-result-item selected-item">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <i class="bi bi-music-note"></i> ${escapeHtml(item.name)}
                            <small class="text-muted d-block">by ${escapeHtml(item.artistName)}</small>
                        </div>
                        <button class="btn btn-sm btn-outline-danger" data-remove-type="${item.type}" data-remove-id="${item.id}">
                            <i class="bi bi-x"></i>
                        </button>
                    </div>
                </div>
            `;
        }
    }

    container.innerHTML = html;

    // Add event listeners to remove buttons
    container.querySelectorAll('[data-remove-type]').forEach(btn => {
        btn.addEventListener('click', function() {
            const type = this.dataset.removeType;
            const id = this.dataset.removeId;
            removeSelectedItem(type, id);
        });
    });

    previewEl.textContent = totalSongs;
    addBtn.disabled = false;
}

/**
 * Remove selected item
 */
function removeSelectedItem(type, id) {
    selectedItems = selectedItems.filter(i => !(i.type === type && String(i.id) === String(id)));
    updateSelectedItems();
}

/**
 * Clear search
 */
function clearSearch() {
    document.getElementById('searchInput').value = '';
    document.getElementById('searchResults').innerHTML = '';
}

/**
 * Add selected items to blocklist
 */
async function addToBlocklist() {
    if (selectedItems.length === 0) return;

    const reason = document.getElementById('reasonInput').value.trim();
    const addBtn = document.getElementById('addBtn');

    addBtn.disabled = true;
    addBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Adding...';

    try {
        const response = await fetch('/api/blocklist/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items: selectedItems.map(item => ({
                    type: item.type,
                    id: item.id,
                    block_all: item.blockAll || false,
                    reason: reason || null
                }))
            })
        });

        const result = await response.json();

        if (response.ok) {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('addModal'));
            modal.hide();

            // Reset form
            selectedItems = [];
            document.getElementById('searchInput').value = '';
            document.getElementById('searchResults').innerHTML = '';
            document.getElementById('reasonInput').value = '';
            updateSelectedItems();

            // Reload blocklist and stats
            loadStats();
            loadBlocklist();

            // Show appropriate message based on results
            if (result.added > 0 && result.skipped > 0) {
                showToast('success', `${result.message} (${result.skipped} were already blocked)`);
            } else if (result.skipped > 0 && result.added === 0) {
                showToast('warning', 'All selected items are already on the blocklist');
            } else {
                showToast('success', result.message);
            }
        } else {
            showToast('error', result.error || 'Failed to add to blocklist');
        }
    } catch (error) {
        console.error('Error adding to blocklist:', error);
        showToast('error', 'Error adding to blocklist: ' + error.message);
    } finally {
        addBtn.disabled = false;
        addBtn.innerHTML = 'Add to Blocklist';
    }
}

/**
 * Unblock item
 */
async function unblockItem(blocklistId) {
    if (!confirm('Are you sure you want to unblock this item?')) return;

    try {
        const response = await fetch(`/api/blocklist/${blocklistId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (response.ok) {
            loadStats();
            loadBlocklist();
            showToast('success', 'Item unblocked successfully');
        } else {
            showToast('error', result.error || 'Failed to unblock item');
        }
    } catch (error) {
        console.error('Error unblocking:', error);
        showToast('error', 'Error unblocking item: ' + error.message);
    }
}

/**
 * Export blocklist
 */
async function exportBlocklist() {
    try {
        const response = await fetch('/api/blocklist/export', {
            method: 'POST'
        });

        const data = await response.json();

        // Create blob and download
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `blocklist-export-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);

        showToast('success', 'Blocklist exported successfully');
    } catch (error) {
        console.error('Error exporting blocklist:', error);
        showToast('error', 'Error exporting blocklist: ' + error.message);
    }
}

/**
 * Import blocklist
 */
function importBlocklist() {
    const modal = new bootstrap.Modal(document.getElementById('importModal'));
    modal.show();
}

/**
 * Execute import
 */
async function executeImport() {
    const fileInput = document.getElementById('importFile');
    const file = fileInput.files[0];

    if (!file) {
        showToast('error', 'Please select a file to import');
        return;
    }

    try {
        const text = await file.text();
        const data = JSON.parse(text);

        const response = await fetch('/api/blocklist/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (response.ok) {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('importModal'));
            modal.hide();

            // Reset form
            fileInput.value = '';

            // Reload
            loadStats();
            loadBlocklist();

            showToast('success', `Imported ${result.imported} items${result.skipped ? `, skipped ${result.skipped}` : ''}`);
        } else {
            showToast('error', result.error || 'Failed to import blocklist');
        }
    } catch (error) {
        console.error('Error importing:', error);
        showToast('error', 'Error importing blocklist: ' + error.message);
    }
}

/**
 * Show toast notification
 */
function showToast(type, message) {
    // Create toast container if doesn't exist
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : 'success'} border-0`;
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${escapeHtml(message)}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;

    container.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();

    // Remove from DOM after hiding
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

/**
 * Format date
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== DEBUG FUNCTIONS ====================

/**
 * Update debug state display
 */
function updateDebugState(message) {
    const stateEl = document.getElementById('debug-state');
    if (stateEl) {
        const state = {
            currentTab: currentTab,
            currentPage: currentPage,
            totalPages: totalPages,
            selectedCount: selectedItems.length,
            timestamp: new Date().toISOString()
        };
        stateEl.textContent = JSON.stringify(state, null, 2);
        debugLog.push(`[${new Date().toISOString()}] ${message}`);
    }
}

/**
 * Test blocklist API endpoint
 */
async function testBlocklistAPI() {
    const debugEl = document.getElementById('debug-api');
    if (!debugEl) return;

    debugEl.innerHTML = '<div class="text-info">Testing API...</div>';

    try {
        // Test stats endpoint
        const statsResponse = await fetch('/api/blocklist/stats');
        const statsData = await statsResponse.json();

        // Test items endpoint
        const itemsResponse = await fetch('/api/blocklist?entity_type=song&page=1&limit=5');
        const itemsData = await itemsResponse.json();

        // Test debug endpoint
        const debugResponse = await fetch('/api/blocklist/debug');
        const debugData = await debugResponse.json();

        debugEl.innerHTML = `
            <h6>Stats API (HTTP ${statsResponse.status})</h6>
            <pre>${JSON.stringify(statsData, null, 2)}</pre>

            <h6>Items API (HTTP ${itemsResponse.status})</h6>
            <pre>${JSON.stringify(itemsData, null, 2)}</pre>

            <h6>Debug API (HTTP ${debugResponse.status})</h6>
            <pre>${JSON.stringify(debugData, null, 2)}</pre>
        `;

        updateDebugState('API test completed');
    } catch (error) {
        debugEl.innerHTML = `<div class="text-danger">Error: ${error.message}</div>`;
        updateDebugState(`API test failed: ${error.message}`);
    }
}

/**
 * Clear debug log
 */
function clearDebug() {
    debugLog = [];
    const debugApi = document.getElementById('debug-api');
    if (debugApi) {
        debugApi.innerHTML = '';
    }
    updateDebugState('Debug cleared');
}
