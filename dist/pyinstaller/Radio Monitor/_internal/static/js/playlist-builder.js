/**
 * Playlist Builder - Frontend JavaScript
 * Radio Monitor 1.2.0
 *
 * Phase 5: View Modes & Filtering
 */

// ==================== GLOBAL STATE ====================

const PlaylistBuilderState = {
    currentView: 'by_artist',  // 'by_artist' or 'by_song'
    selections: new Set(),     // Set of song IDs
    filters: {
        stations: [],
        dateField: 'last_seen_at',
        dateStart: null,
        dateEnd: null,
        minPlays: null,
        maxPlays: null,
        search: ''
    },
    sort: { column: 'last_seen', direction: 'desc' },
    pagination: { page: 1, perPage: 50, total: 0 },
    editingPlaylistId: null,   // If editing existing playlist
    editingPlaylistName: null, // Name of playlist being edited
    showOnlySelected: false,
    expandedArtists: new Set()  // Artist IDs with expanded song lists
};

// ==================== URL STATE MANAGEMENT ====================

/**
 * Update URL with current state (filters, sort, view mode)
 * Does NOT include selections (stored in database)
 */
function updateURL() {
    const url = new URL(window.location);

    // Clear existing params
    url.searchParams.delete('view');
    url.searchParams.delete('page');
    url.searchParams.delete('per_page');
    url.searchParams.delete('sort');
    url.searchParams.delete('direction');
    url.searchParams.delete('stations');
    url.searchParams.delete('date_field');
    url.searchParams.delete('date_start');
    url.searchParams.delete('date_end');
    url.searchParams.delete('min_plays');
    url.searchParams.delete('max_plays');
    url.searchParams.delete('search');
    url.searchParams.delete('show');

    // Add view mode
    url.searchParams.set('view', PlaylistBuilderState.currentView);

    // Add pagination
    if (PlaylistBuilderState.pagination.page > 1) {
        url.searchParams.set('page', PlaylistBuilderState.pagination.page);
    }
    if (PlaylistBuilderState.pagination.perPage !== 50) {
        url.searchParams.set('per_page', PlaylistBuilderState.pagination.perPage);
    }

    // Add sort
    url.searchParams.set('sort', PlaylistBuilderState.sort.column);
    url.searchParams.set('direction', PlaylistBuilderState.sort.direction);

    // Add filters
    if (PlaylistBuilderState.filters.stations.length > 0) {
        url.searchParams.set('stations', PlaylistBuilderState.filters.stations.join(','));
    }
    if (PlaylistBuilderState.filters.dateStart) {
        url.searchParams.set('date_field', PlaylistBuilderState.filters.dateField);
        url.searchParams.set('date_start', PlaylistBuilderState.filters.dateStart);
        url.searchParams.set('date_end', PlaylistBuilderState.filters.dateEnd);
    }
    if (PlaylistBuilderState.filters.minPlays !== null) {
        url.searchParams.set('min_plays', PlaylistBuilderState.filters.minPlays);
    }
    if (PlaylistBuilderState.filters.maxPlays !== null) {
        url.searchParams.set('max_plays', PlaylistBuilderState.filters.maxPlays);
    }
    if (PlaylistBuilderState.filters.search) {
        url.searchParams.set('search', PlaylistBuilderState.filters.search);
    }
    if (PlaylistBuilderState.showOnlySelected) {
        url.searchParams.set('show', 'selected');
    }

    // Update URL without reloading
    window.history.replaceState({}, '', url);
}

/**
 * Load state from URL query parameters
 */
function loadStateFromURL() {
    const url = new URL(window.location);

    // View mode
    const view = url.searchParams.get('view');
    if (view === 'by_artist' || view === 'by_song') {
        PlaylistBuilderState.currentView = view;
    }

    // Pagination
    PlaylistBuilderState.pagination.page = parseInt(url.searchParams.get('page')) || 1;
    PlaylistBuilderState.pagination.perPage = parseInt(url.searchParams.get('per_page')) || 50;

    // Sort
    PlaylistBuilderState.sort.column = url.searchParams.get('sort') || 'last_seen';
    PlaylistBuilderState.sort.direction = url.searchParams.get('direction') || 'desc';

    // Filters
    const stations = url.searchParams.get('stations');
    if (stations) {
        PlaylistBuilderState.filters.stations = stations.split(',').map(s => s.trim());
    }

    PlaylistBuilderState.filters.dateField = url.searchParams.get('date_field') || 'last_seen_at';
    PlaylistBuilderState.filters.dateStart = url.searchParams.get('date_start');
    PlaylistBuilderState.filters.dateEnd = url.searchParams.get('date_end');

    PlaylistBuilderState.filters.minPlays = parseInt(url.searchParams.get('min_plays')) || null;
    PlaylistBuilderState.filters.maxPlays = parseInt(url.searchParams.get('max_plays')) || null;
    PlaylistBuilderState.filters.search = url.searchParams.get('search') || '';

    PlaylistBuilderState.showOnlySelected = url.searchParams.get('show') === 'selected';
}

// ==================== API CALLS ====================

/**
 * Fetch songs from API
 */
async function fetchSongs() {
    const params = new URLSearchParams({
        page: PlaylistBuilderState.pagination.page,
        per_page: PlaylistBuilderState.pagination.perPage,
        sort: PlaylistBuilderState.sort.column,
        direction: PlaylistBuilderState.sort.direction
    });

    // Add filters
    if (PlaylistBuilderState.filters.stations.length > 0) {
        params.set('stations', PlaylistBuilderState.filters.stations.join(','));
    }
    if (PlaylistBuilderState.filters.dateStart && PlaylistBuilderState.filters.dateEnd) {
        params.set('date_field', PlaylistBuilderState.filters.dateField);
        params.set('date_start', PlaylistBuilderState.filters.dateStart);
        params.set('date_end', PlaylistBuilderState.filters.dateEnd);
    }
    if (PlaylistBuilderState.filters.minPlays !== null) {
        params.set('min_plays', PlaylistBuilderState.filters.minPlays);
    }
    if (PlaylistBuilderState.filters.maxPlays !== null) {
        params.set('max_plays', PlaylistBuilderState.filters.maxPlays);
    }
    if (PlaylistBuilderState.filters.search) {
        params.set('search', PlaylistBuilderState.filters.search);
    }
    if (PlaylistBuilderState.showOnlySelected) {
        params.set('show', 'selected');
    }

    const response = await fetch(`/api/playlist-builder/songs?${params}`);
    if (!response.ok) {
        throw new Error('Failed to fetch songs');
    }
    return await response.json();
}

/**
 * Fetch artists from API
 */
async function fetchArtists() {
    const params = new URLSearchParams({
        page: PlaylistBuilderState.pagination.page,
        per_page: PlaylistBuilderState.pagination.perPage,
        sort: PlaylistBuilderState.sort.column === 'last_seen' ? 'name' : PlaylistBuilderState.sort.column,
        direction: PlaylistBuilderState.sort.direction
    });

    // Add filters (same as songs)
    if (PlaylistBuilderState.filters.stations.length > 0) {
        params.set('stations', PlaylistBuilderState.filters.stations.join(','));
    }
    if (PlaylistBuilderState.filters.dateStart && PlaylistBuilderState.filters.dateEnd) {
        params.set('date_field', PlaylistBuilderState.filters.dateField);
        params.set('date_start', PlaylistBuilderState.filters.dateStart);
        params.set('date_end', PlaylistBuilderState.filters.dateEnd);
    }
    if (PlaylistBuilderState.filters.minPlays !== null) {
        params.set('min_plays', PlaylistBuilderState.filters.minPlays);
    }
    if (PlaylistBuilderState.filters.maxPlays !== null) {
        params.set('max_plays', PlaylistBuilderState.filters.maxPlays);
    }
    if (PlaylistBuilderState.filters.search) {
        params.set('search', PlaylistBuilderState.filters.search);
    }
    if (PlaylistBuilderState.showOnlySelected) {
        params.set('show', 'selected');
    }

    const response = await fetch(`/api/playlist-builder/artists?${params}`);
    if (!response.ok) {
        throw new Error('Failed to fetch artists');
    }
    return await response.json();
}

/**
 * Fetch songs for a specific artist (for expanding artist row)
 */
async function fetchArtistSongs(artistId) {
    const response = await fetch(`/api/artists/${artistId}/songs?limit=500`);
    if (!response.ok) {
        throw new Error('Failed to fetch artist songs');
    }
    const data = await response.json();
    return data.items || [];
}

/**
 * Toggle song selection
 */
async function toggleSongSelection(songId, selected) {
    const response = await fetch('/api/playlist-builder/selections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ song_id: songId, selected: selected })
    });

    if (!response.ok) {
        throw new Error('Failed to update selection');
    }

    const data = await response.json();
    if (selected) {
        PlaylistBuilderState.selections.add(songId);
    } else {
        PlaylistBuilderState.selections.delete(songId);
    }

    updateSelectionCount(data.count);
    return data;
}

/**
 * Batch update song selections (for artist checkbox or select all)
 */
async function batchUpdateSelections(songIds, selected) {
    const response = await fetch('/api/playlist-builder/selections/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ song_ids: songIds, selected: selected })
    });

    if (!response.ok) {
        throw new Error('Failed to batch update selections');
    }

    const data = await response.json();
    songIds.forEach(id => {
        if (selected) {
            PlaylistBuilderState.selections.add(id);
        } else {
            PlaylistBuilderState.selections.delete(id);
        }
    });

    updateSelectionCount(data.count);
    return data;
}

/**
 * Clear all selections
 */
async function clearAllSelections() {
    const response = await fetch('/api/playlist-builder/selections', {
        method: 'DELETE'
    });

    if (!response.ok) {
        throw new Error('Failed to clear selections');
    }

    PlaylistBuilderState.selections.clear();
    updateSelectionCount(0);
}

// ==================== RENDERING ====================

/**
 * Update selection count badge
 */
function updateSelectionCount(count) {
    const badge = document.getElementById('selectionCount');
    if (badge) {
        badge.textContent = `${count} song${count !== 1 ? 's' : ''} selected`;
    }

    // Enable/disable buttons
    const btnClear = document.getElementById('btnClearSelection');
    const btnShowOnly = document.getElementById('btnShowOnlySelected');
    const btnCreate = document.getElementById('btnCreatePlaylist');

    if (btnClear) btnClear.disabled = count === 0;
    if (btnShowOnly) btnShowOnly.disabled = count === 0;
    if (btnCreate) btnCreate.disabled = count === 0;
}

/**
 * Show loading state
 */
function showLoading(message = 'Loading...') {
    // Show overlay for blocking operations (Phase 6)
    const overlay = document.getElementById('loadingOverlay');
    const msgEl = document.getElementById('loadingMessage');
    if (overlay && msgEl) {
        msgEl.textContent = message;
        overlay.classList.remove('d-none');
    }

    // Also show inline loading state
    document.getElementById('loadingState').classList.remove('d-none');
    document.getElementById('emptyState').classList.add('d-none');
    document.getElementById('byArtistView').classList.add('d-none');
    document.getElementById('bySongView').classList.add('d-none');
    document.getElementById('paginationNav').classList.add('d-none');
}

/**
 * Hide loading state
 */
function hideLoading() {
    // Hide overlay
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.classList.add('d-none');
    }

    // Hide inline loading state
    document.getElementById('loadingState').classList.add('d-none');
}

/**
 * Show empty state
 */
function showEmptyState() {
    document.getElementById('emptyState').classList.remove('d-none');
    document.getElementById('byArtistView').classList.add('d-none');
    document.getElementById('bySongView').classList.add('d-none');
    document.getElementById('paginationNav').classList.add('d-none');
}

/**
 * Render "By Artist" view
 */
async function renderByArtistView() {
    showLoading();

    try {
        const data = await fetchArtists();
        PlaylistBuilderState.pagination.total = data.total;

        hideLoading();

        if (data.artists.length === 0) {
            showEmptyState();
            updateResultsCount(0, data.total);
            return;
        }

        document.getElementById('emptyState').classList.add('d-none');
        document.getElementById('byArtistView').classList.remove('d-none');
        document.getElementById('bySongView').classList.add('d-none');

        const tbody = document.getElementById('artistListBody');
        tbody.innerHTML = '';

        for (const artist of data.artists) {
            // Fetch artist's songs to calculate selection count
            const songs = await fetchArtistSongs(artist.mbid);
            const selectedSongs = songs.filter(s => PlaylistBuilderState.selections.has(s.id));
            const selectedCount = selectedSongs.length;
            const totalCount = artist.song_count || 0;

            // Determine checkbox state
            let checkboxState = '';
            if (selectedCount === 0) {
                checkboxState = ''; // Empty
            } else if (selectedCount === totalCount) {
                checkboxState = 'checked'; // Full
            } else {
                checkboxState = 'partial'; // Partial
            }

            // Create artist row
            const row = document.createElement('tr');
            row.className = 'artist-row';
            row.dataset.artistId = artist.mbid;

            row.innerHTML = `
                <td>
                    <input type="checkbox" class="form-check-input artist-checkbox"
                           data-artist-id="${artist.mbid}"
                           data-artist-name="${artist.name}"
                           ${checkboxState === 'checked' ? 'checked' : ''}>
                </td>
                <td>
                    <span class="artist-name expandable artist-expand"
                          data-artist-id="${artist.mbid}">
                        <i class="bi bi-chevron-right me-2"></i>${artist.name}
                    </span>
                    ${selectedCount > 0 ? `<span class="badge bg-secondary ms-2">${selectedCount}/${totalCount} selected</span>` : ''}
                </td>
                <td>${totalCount}</td>
                <td>
                    <span class="badge bg-${selectedCount > 0 ? 'primary' : 'secondary'}">${selectedCount}</span>
                </td>
            `;

            tbody.appendChild(row);

            // Create songs row (hidden by default)
            const songsRow = document.createElement('tr');
            songsRow.className = 'artist-songs';
            songsRow.dataset.artistId = artist.mbid;

            const songsTable = `
                <td colspan="4">
                    <table class="table table-sm mb-0">
                        <tbody>
                            ${songs.map(song => `
                                <tr class="song-row ${PlaylistBuilderState.selections.has(song.id) ? 'selected' : ''}">
                                    <td width="40">
                                        <input type="checkbox" class="form-check-input song-checkbox"
                                               data-song-id="${song.id}"
                                               ${PlaylistBuilderState.selections.has(song.id) ? 'checked' : ''}>
                                    </td>
                                    <td>${song.song_title || song.title || ''}</td>
                                    <td width="80">${song.play_count || song.plays || 0}</td>
                                    <td width="120">${formatDate(song.last_seen_at)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </td>
            `;

            songsRow.innerHTML = songsTable;
            tbody.appendChild(songsRow);
        }

        // Add event listeners
        attachArtistViewEventListeners();

        // Update sort indicators
        updateSortIndicators();

        // Render pagination
        renderPagination();

        // Update results count
        updateResultsCount(data.artists.length, data.total);

    } catch (error) {
        console.error('Error rendering artist view:', error);
        showError('Failed to load artists: ' + error.message);
        hideLoading();
    }
}

/**
 * Render "By Song" view
 */
async function renderBySongView() {
    showLoading();

    try {
        const data = await fetchSongs();
        PlaylistBuilderState.pagination.total = data.total;

        hideLoading();

        if (data.songs.length === 0) {
            showEmptyState();
            updateResultsCount(0, data.total);
            return;
        }

        document.getElementById('emptyState').classList.add('d-none');
        document.getElementById('bySongView').classList.remove('d-none');
        document.getElementById('byArtistView').classList.add('d-none');

        const tbody = document.getElementById('songListBody');
        tbody.innerHTML = '';

        for (const song of data.songs) {
            const row = document.createElement('tr');
            row.className = 'song-row ' + (song.selected ? 'selected' : '');
            row.dataset.songId = song.id;

            row.innerHTML = `
                <td>
                    <input type="checkbox" class="form-check-input song-checkbox"
                           data-song-id="${song.id}"
                           ${song.selected ? 'checked' : ''}>
                </td>
                <td>${song.artist_name || ''}</td>
                <td>${song.song_title || song.title || ''}</td>
                <td>${song.play_count || song.plays || 0}</td>
                <td>${formatDate(song.last_seen_at)}</td>
            `;

            tbody.appendChild(row);
        }

        // Add event listeners
        attachSongViewEventListeners();

        // Update sort indicators
        updateSortIndicators();

        // Render pagination
        renderPagination();

        // Update results count
        updateResultsCount(data.songs.length, data.total);

    } catch (error) {
        console.error('Error rendering song view:', error);
        showError('Failed to load songs: ' + error.message);
        hideLoading();
    }
}

/**
 * Render pagination
 */
function renderPagination() {
    const totalPages = Math.ceil(PlaylistBuilderState.pagination.total / PlaylistBuilderState.pagination.perPage);
    const currentPage = PlaylistBuilderState.pagination.page;

    const pagination = document.getElementById('pagination');
    pagination.innerHTML = '';

    if (totalPages <= 1) {
        document.getElementById('paginationNav').classList.add('d-none');
        return;
    }

    document.getElementById('paginationNav').classList.remove('d-none');

    // Previous button
    const prevLi = document.createElement('li');
    prevLi.className = `page-item ${currentPage === 1 ? 'disabled' : ''}`;
    prevLi.innerHTML = `<a class="page-link" href="#" data-page="${currentPage - 1}">Previous</a>`;
    pagination.appendChild(prevLi);

    // Page numbers
    const maxVisible = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);

    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
        const li = document.createElement('li');
        li.className = `page-item ${i === currentPage ? 'active' : ''}`;
        li.innerHTML = `<a class="page-link" href="#" data-page="${i}">${i}</a>`;
        pagination.appendChild(li);
    }

    // Next button
    const nextLi = document.createElement('li');
    nextLi.className = `page-item ${currentPage === totalPages ? 'disabled' : ''}`;
    nextLi.innerHTML = `<a class="page-link" href="#" data-page="${currentPage + 1}">Next</a>`;
    pagination.appendChild(nextLi);

    // Add click handlers
    pagination.querySelectorAll('a[data-page]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const page = parseInt(e.target.dataset.page);
            if (page >= 1 && page <= totalPages) {
                loadPage(page);
            }
        });
    });
}

/**
 * Update results count display
 */
function updateResultsCount(shown, total) {
    const el = document.getElementById('resultsCount');
    if (el) {
        el.textContent = `Showing ${shown} of ${total} songs`;
    }
}

/**
 * Format date for display
 */
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
}

// ==================== EVENT LISTENERS ====================

/**
 * Attach event listeners for "By Artist" view
 */
function attachArtistViewEventListeners() {
    // Artist expand/collapse
    document.querySelectorAll('.artist-expand').forEach(span => {
        span.addEventListener('click', (e) => {
            const artistId = e.currentTarget.dataset.artistId;
            toggleArtistExpansion(artistId);
        });
    });

    // Artist checkbox (tri-state)
    document.querySelectorAll('.artist-checkbox').forEach(checkbox => {
        checkbox.addEventListener('click', async (e) => {
            e.stopPropagation();
            const artistId = e.target.dataset.artistId;
            await handleArtistCheckboxClick(artistId);
        });
    });

    // Song checkbox
    document.querySelectorAll('.song-checkbox').forEach(checkbox => {
        checkbox.addEventListener('click', async (e) => {
            e.stopPropagation();
            const songId = parseInt(e.target.dataset.songId);
            const selected = e.target.checked;

            // Update selection without full re-render
            const data = await toggleSongSelection(songId, selected);

            // Update row styling immediately
            const row = e.target.closest('.song-row');
            if (row) {
                if (selected) {
                    row.classList.add('selected');
                } else {
                    row.classList.remove('selected');
                }
            }

            // Update parent artist checkbox state
            const artistRow = e.target.closest('tr').previousElementSibling;
            if (artistRow) {
                const artistId = artistRow.dataset.artistId;
                await updateArtistCheckboxState(artistId);
            }
        });
    });
}

/**
 * Attach event listeners for "By Song" view
 */
function attachSongViewEventListeners() {
    // Song checkbox
    document.querySelectorAll('.song-checkbox').forEach(checkbox => {
        checkbox.addEventListener('click', async (e) => {
            const songId = parseInt(e.target.dataset.songId);
            const selected = e.target.checked;

            // Update selection without full re-render
            await toggleSongSelection(songId, selected);

            // Update row styling immediately
            const row = e.target.closest('.song-row');
            if (row) {
                if (selected) {
                    row.classList.add('selected');
                } else {
                    row.classList.remove('selected');
                }
            }
        });
    });

    // Select all checkbox
    const selectAll = document.getElementById('selectAllSongs');
    if (selectAll) {
        selectAll.addEventListener('click', async (e) => {
            const checkboxes = document.querySelectorAll('.song-checkbox');
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);

            // Get all song IDs on current page
            const songIds = Array.from(checkboxes).map(cb => parseInt(cb.dataset.songId));

            await batchUpdateSelections(songIds, !allChecked);

            // Update checkboxes and row styling without full re-render
            const shouldBeChecked = !allChecked;
            checkboxes.forEach(cb => {
                cb.checked = shouldBeChecked;
                const row = cb.closest('.song-row');
                if (row) {
                    if (shouldBeChecked) {
                        row.classList.add('selected');
                    } else {
                        row.classList.remove('selected');
                    }
                }
            });
        });
    }
}

/**
 * Toggle artist expansion
 */
function toggleArtistExpansion(artistId) {
    const songsRow = document.querySelector(`.artist-songs[data-artist-id="${artistId}"]`);
    const expandIcon = document.querySelector(`.artist-expand[data-artist-id="${artistId}"] i`);

    if (songsRow.classList.contains('show')) {
        songsRow.classList.remove('show');
        expandIcon.className = 'bi bi-chevron-right me-2';
        PlaylistBuilderState.expandedArtists.delete(artistId);
    } else {
        songsRow.classList.add('show');
        expandIcon.className = 'bi bi-chevron-down me-2';
        PlaylistBuilderState.expandedArtists.add(artistId);
    }
}

/**
 * Update artist checkbox state without full re-render
 */
async function updateArtistCheckboxState(artistId) {
    const artistRow = document.querySelector(`.artist-row[data-artist-id="${artistId}"]`);
    const songsRow = document.querySelector(`.artist-songs[data-artist-id="${artistId}"]`);

    if (!artistRow || !songsRow) return;

    const songCheckboxes = songsRow.querySelectorAll('.song-checkbox');
    const selectedCount = Array.from(songCheckboxes).filter(cb => cb.checked).length;
    const totalCount = songCheckboxes.length;

    const checkbox = artistRow.querySelector('.artist-checkbox');
    const selectedBadge = artistRow.querySelector('.badge');

    // Update checkbox state
    if (selectedCount === 0) {
        checkbox.checked = false;
        checkbox.indeterminate = false;
        checkbox.classList.remove('checkbox-partial');
    } else if (selectedCount === totalCount) {
        checkbox.checked = true;
        checkbox.indeterminate = false;
        checkbox.classList.remove('checkbox-partial');
    } else {
        checkbox.checked = false;
        checkbox.indeterminate = true;
        checkbox.classList.add('checkbox-partial');
    }

    // Update selected badge
    if (selectedBadge) {
        selectedBadge.textContent = `${selectedCount}/${totalCount} selected`;
        if (selectedCount > 0) {
            selectedBadge.classList.remove('bg-secondary');
            selectedBadge.classList.add('bg-primary');
        } else {
            selectedBadge.classList.remove('bg-primary');
            selectedBadge.classList.add('bg-secondary');
        }
    }

    // Update selected count column
    const selectedCountCol = artistRow.querySelector('td:last-child .badge');
    if (selectedCountCol) {
        selectedCountCol.textContent = selectedCount;
        if (selectedCount > 0) {
            selectedCountCol.classList.remove('bg-secondary');
            selectedCountCol.classList.add('bg-primary');
        } else {
            selectedCountCol.classList.remove('bg-primary');
            selectedCountCol.classList.add('bg-secondary');
        }
    }
}

/**
 * Handle artist checkbox click (tri-state logic)
 */
async function handleArtistCheckboxClick(artistId) {
    const checkbox = document.querySelector(`.artist-checkbox[data-artist-id="${artistId}"]`);
    const songsRow = document.querySelector(`.artist-songs[data-artist-id="${artistId}"]`);
    const songCheckboxes = songsRow.querySelectorAll('.song-checkbox');

    // Get all song IDs for this artist
    const songIds = Array.from(songCheckboxes).map(cb => parseInt(cb.dataset.songId));

    // Count currently selected
    const selectedCount = Array.from(songCheckboxes).filter(cb => cb.checked).length;
    const totalCount = songIds.length;

    let shouldSelect;
    if (selectedCount === 0) {
        // Empty -> Select all
        shouldSelect = true;
    } else if (selectedCount === totalCount) {
        // Full -> Deselect all
        shouldSelect = false;
    } else {
        // Partial -> Select all
        shouldSelect = true;
    }

    await batchUpdateSelections(songIds, shouldSelect);

    // Re-render
    await renderByArtistView();
}

// ==================== FILTER HANDLERS ====================

/**
 * Handle filter changes
 */
function handleFilterChange() {
    // Update station filter from UI
    const stationSelect = document.getElementById('filterStation');
    const selectedStations = Array.from(stationSelect.selectedOptions).map(opt => opt.value);
    PlaylistBuilderState.filters.stations = selectedStations;

    // Update other filters from UI
    const minPlays = document.getElementById('filterMinPlays').value;
    const maxPlays = document.getElementById('filterMaxPlays').value;
    const search = document.getElementById('filterSearch').value;
    const dateFrom = document.getElementById('filterDateFrom').value;
    const dateTo = document.getElementById('filterDateTo').value;

    PlaylistBuilderState.filters.minPlays = minPlays ? parseInt(minPlays) : null;
    PlaylistBuilderState.filters.maxPlays = maxPlays ? parseInt(maxPlays) : null;
    PlaylistBuilderState.filters.search = search;

    if (document.getElementById('dateRangeToggle').checked && dateFrom && dateTo) {
        PlaylistBuilderState.filters.dateStart = dateFrom;
        PlaylistBuilderState.filters.dateEnd = dateTo;
    } else {
        PlaylistBuilderState.filters.dateStart = null;
        PlaylistBuilderState.filters.dateEnd = null;
    }

    // Reset to page 1
    PlaylistBuilderState.pagination.page = 1;

    // Update URL and reload
    updateURL();
    loadData();
}

/**
 * Load data based on current view
 */
function loadData() {
    if (PlaylistBuilderState.currentView === 'by_artist') {
        renderByArtistView();
    } else {
        renderBySongView();
    }
}

/**
 * Load specific page
 */
function loadPage(pageNumber) {
    PlaylistBuilderState.pagination.page = pageNumber;
    updateURL();
    loadData();
}

/**
 * Switch view mode
 */
function switchViewMode(viewMode) {
    PlaylistBuilderState.currentView = viewMode;
    PlaylistBuilderState.pagination.page = 1; // Reset to page 1
    updateURL();

    // Update radio buttons
    document.getElementById('viewByArtist').checked = (viewMode === 'by_artist');
    document.getElementById('viewBySong').checked = (viewMode === 'by_song');

    loadData();
}

/**
 * Handle column header click for sorting
 */
function handleColumnSort(column) {
    // Map column names to sort column names
    const columnMapping = {
        'name': 'name',
        'song_count': 'song_count',
        'selected_count': 'selected_count',
        'artist_name': 'artist_name',
        'title': 'title',
        'plays': 'play_count',
        'last_seen': 'last_seen'
    };

    const sortColumn = columnMapping[column] || column;

    // Toggle direction if clicking same column, otherwise set to asc
    if (PlaylistBuilderState.sort.column === sortColumn) {
        PlaylistBuilderState.sort.direction = PlaylistBuilderState.sort.direction === 'asc' ? 'desc' : 'asc';
    } else {
        PlaylistBuilderState.sort.column = sortColumn;
        PlaylistBuilderState.sort.direction = 'asc';
    }

    handleFilterChange();
}

/**
 * Update sort indicators in table headers
 */
function updateSortIndicators() {
    // Map sort column back to header data-sort attribute
    const reverseMapping = {
        'name': 'name',
        'song_count': 'song_count',
        'selected_count': 'selected_count',
        'artist_name': 'artist_name',
        'title': 'title',
        'play_count': 'plays',
        'last_seen': 'last_seen'
    };

    const currentSortColumn = reverseMapping[PlaylistBuilderState.sort.column] || PlaylistBuilderState.sort.column;

    // Remove all sort classes
    document.querySelectorAll('.sortable').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
    });

    // Add sort class to current column
    const currentHeader = document.querySelector(`.sortable[data-sort="${currentSortColumn}"]`);
    if (currentHeader) {
        currentHeader.classList.add(PlaylistBuilderState.sort.direction === 'asc' ? 'sorted-asc' : 'sorted-desc');
    }
}

/**
 * Toggle "Show Only Selected"
 */
function toggleShowOnlySelected() {
    PlaylistBuilderState.showOnlySelected = !PlaylistBuilderState.showOnlySelected;
    PlaylistBuilderState.pagination.page = 1; // Reset to page 1

    const btn = document.getElementById('btnShowOnlySelected');
    if (PlaylistBuilderState.showOnlySelected) {
        btn.classList.add('btn-success');
        btn.classList.remove('btn-info');
        btn.innerHTML = '<i class="bi bi-check2-square"></i> Show All Songs';
    } else {
        btn.classList.add('btn-info');
        btn.classList.remove('btn-success');
        btn.innerHTML = '<i class="bi bi-check2-square"></i> Show Only Selected';
    }

    updateURL();

    // Only reload data (don't need to switch views)
    loadData();
}

/**
 * Reset all filters
 */
function resetFilters() {
    PlaylistBuilderState.filters = {
        stations: [],
        dateField: 'last_seen_at',
        dateStart: null,
        dateEnd: null,
        minPlays: null,
        maxPlays: null,
        search: ''
    };
    PlaylistBuilderState.sort = { column: 'last_seen', direction: 'desc' };
    PlaylistBuilderState.pagination.page = 1;
    PlaylistBuilderState.showOnlySelected = false;

    // Reset form inputs
    const stationSelect = document.getElementById('filterStation');
    Array.from(stationSelect.options).forEach(option => {
        option.selected = false;
    });

    document.getElementById('dateRangeToggle').checked = false;
    document.getElementById('dateRangeInputs').style.display = 'none';
    document.getElementById('filterDateFrom').value = '';
    document.getElementById('filterDateTo').value = '';
    document.getElementById('filterMinPlays').value = '';
    document.getElementById('filterMaxPlays').value = '';
    document.getElementById('filterSearch').value = '';
    document.getElementById('filterPageSize').value = '50';

    const btn = document.getElementById('btnShowOnlySelected');
    btn.classList.add('btn-info');
    btn.classList.remove('btn-success');
    btn.innerHTML = '<i class="bi bi-check2-square"></i> Show Only Selected';

    updateURL();
    loadData();
}

// ==================== TOAST NOTIFICATIONS ====================

/**
 * Show success toast
 */
function showSuccess(message) {
    const toastEl = document.getElementById('successToast');
    const toastBody = document.getElementById('successToastMessage');
    toastBody.textContent = message;
    const toast = new bootstrap.Toast(toastEl);
    toast.show();
}

/**
 * Show error toast
 */
function showError(message) {
    const toastEl = document.getElementById('errorToast');
    const toastBody = document.getElementById('errorToastMessage');
    toastBody.textContent = message;
    const toast = new bootstrap.Toast(toastEl);
    toast.show();
}

/**
 * Show warning toast
 */
function showWarning(message) {
    const toastEl = document.getElementById('errorToast');
    const toastBody = document.getElementById('errorToastMessage');
    toastBody.textContent = message;
    // Change to warning color
    toastEl.classList.remove('bg-danger');
    toastEl.classList.add('bg-warning');
    const toast = new bootstrap.Toast(toastEl);
    toast.show();
    // Reset to error color
    setTimeout(() => {
        toastEl.classList.remove('bg-warning');
        toastEl.classList.add('bg-danger');
    }, 5000);
}

// ==================== INITIALIZATION ====================

/**
 * Initialize playlist builder
 */
async function initPlaylistBuilder() {
    console.log('Initializing Playlist Builder...');

    // Load state from URL
    loadStateFromURL();

    // Update view mode radio buttons
    document.getElementById('viewByArtist').checked = (PlaylistBuilderState.currentView === 'by_artist');
    document.getElementById('viewBySong').checked = (PlaylistBuilderState.currentView === 'by_song');

    // Set filter values from state
    if (PlaylistBuilderState.filters.stations.length > 0) {
        const stationSelect = document.getElementById('filterStation');
        Array.from(stationSelect.options).forEach(option => {
            option.selected = PlaylistBuilderState.filters.stations.includes(option.value);
        });
    }

    if (PlaylistBuilderState.filters.dateStart && PlaylistBuilderState.filters.dateEnd) {
        document.getElementById('dateRangeToggle').checked = true;
        document.getElementById('dateRangeInputs').style.display = 'block';
        document.getElementById('filterDateFrom').value = PlaylistBuilderState.filters.dateStart;
        document.getElementById('filterDateTo').value = PlaylistBuilderState.filters.dateEnd;
    }

    if (PlaylistBuilderState.filters.minPlays !== null) {
        document.getElementById('filterMinPlays').value = PlaylistBuilderState.filters.minPlays;
    }
    if (PlaylistBuilderState.filters.maxPlays !== null) {
        document.getElementById('filterMaxPlays').value = PlaylistBuilderState.filters.maxPlays;
    }

    if (PlaylistBuilderState.filters.search) {
        document.getElementById('filterSearch').value = PlaylistBuilderState.filters.search;
    }

    document.getElementById('filterPageSize').value = PlaylistBuilderState.pagination.perPage;

    if (PlaylistBuilderState.showOnlySelected) {
        const btn = document.getElementById('btnShowOnlySelected');
        btn.classList.add('btn-success');
        btn.classList.remove('btn-info');
        btn.innerHTML = '<i class="bi bi-check2-square"></i> Show All Songs';
    }

    // Load current selections
    try {
        const response = await fetch('/api/playlist-builder/selections');
        if (response.ok) {
            const data = await response.json();
            data.song_ids.forEach(id => PlaylistBuilderState.selections.add(id));
            updateSelectionCount(data.count);
        }
    } catch (error) {
        console.error('Error loading selections:', error);
    }

    // Load playlist dropdown (Phase 6)
    await loadPlaylistDropdown();

    // Attach event listeners
    attachEventListeners();

    // Attach station filter change handler
    const stationSelect = document.getElementById('filterStation');
    stationSelect.addEventListener('change', () => {
        const selectedStations = Array.from(stationSelect.selectedOptions).map(opt => opt.value);
        PlaylistBuilderState.filters.stations = selectedStations;
        // Don't auto-apply, wait for user to click "Apply Filters"
    });

    // Load initial data
    loadData();
}

// ==================== PLAYLIST MANAGEMENT (PHASE 6) ====================

/**
 * Load playlists into dropdown
 */
async function loadPlaylistDropdown() {
    try {
        const response = await fetch('/api/playlists/manual');
        if (!response.ok) throw new Error('Failed to load playlists');

        const data = await response.json();
        const dropdown = document.getElementById('playlistDropdown');

        // Clear existing options (keep first option)
        dropdown.innerHTML = '<option value="">-- Create New Playlist --</option>';

        // Add playlists sorted alphabetically
        data.playlists
            .sort((a, b) => a.name.localeCompare(b.name))
            .forEach(playlist => {
                const option = document.createElement('option');
                option.value = playlist.id;
                option.textContent = `${playlist.name} (${playlist.song_count} songs)`;
                dropdown.appendChild(option);
            });
    } catch (error) {
        console.error('Error loading playlist dropdown:', error);
        showError('Failed to load playlists');
    }
}

/**
 * Handle playlist dropdown selection
 */
function handlePlaylistSelection() {
    const dropdown = document.getElementById('playlistDropdown');
    const playlistId = dropdown.value;
    const btnLoad = document.getElementById('btnLoadPlaylist');
    const btnDelete = document.getElementById('btnDeletePlaylist');

    // Enable/disable buttons
    if (playlistId) {
        btnLoad.disabled = false;
        btnDelete.disabled = false;

        // If we have current selections, show confirmation
        if (PlaylistBuilderState.selections.size > 0) {
            const playlistName = dropdown.options[dropdown.selectedIndex].text;
            showLoadPlaylistConfirmation(playlistId, playlistName);
        } else {
            // No selections, load immediately
            loadPlaylistForEditing(playlistId);
        }
    } else {
        // No playlist selected - exit edit mode
        btnLoad.disabled = true;
        btnDelete.disabled = true;

        // If we were in edit mode, reset to create mode
        if (PlaylistBuilderState.editingPlaylistId) {
            resetUIToCreateMode();
        }
    }
}

/**
 * Show load playlist confirmation modal
 */
function showLoadPlaylistConfirmation(playlistId, playlistName) {
    const currentCount = PlaylistBuilderState.selections.size;
    document.getElementById('loadPlaylistMessage').textContent =
        `This will replace your ${currentCount} selected song(s) with "${playlistName}".`;

    const modal = new bootstrap.Modal(document.getElementById('loadPlaylistModal'));
    modal.show();

    // Store playlistId for confirmation
    document.getElementById('btnConfirmLoad').dataset.playlistId = playlistId;
}

/**
 * Load playlist for editing
 */
async function loadPlaylistForEditing(playlistId) {
    try {
        showLoading('Loading playlist...');

        const response = await fetch(`/api/playlists/manual/${playlistId}/load`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Failed to load playlist');

        const data = await response.json();

        // Update state
        PlaylistBuilderState.editingPlaylistId = playlistId;
        PlaylistBuilderState.editingPlaylistName = data.name;

        // Reload selections from database
        const selResponse = await fetch('/api/playlist-builder/selections');
        if (selResponse.ok) {
            const selData = await selResponse.json();
            PlaylistBuilderState.selections = new Set(selData.song_ids);
            updateSelectionCount(selData.count);
        }

        // Update UI
        updateUIForEditingMode(data.name);

        // Clear URL filters and reload
        const url = new URL(window.location);
        url.searchParams.delete('stations');
        url.searchParams.delete('date_field');
        url.searchParams.delete('date_start');
        url.searchParams.delete('date_end');
        url.searchParams.delete('min_plays');
        url.searchParams.delete('max_plays');
        url.searchParams.delete('search');
        window.history.replaceState({}, '', url);

        // Reset filters
        PlaylistBuilderState.filters = {
            stations: [],
            dateField: 'last_seen_at',
            dateStart: null,
            dateEnd: null,
            minPlays: null,
            maxPlays: null,
            search: ''
        };

        // Reload data
        await loadData();

        hideLoading();
        showSuccess(`Loaded "${data.name}" with ${data.song_count} songs`);

    } catch (error) {
        hideLoading();
        console.error('Error loading playlist:', error);
        showError('Failed to load playlist');
    }
}

/**
 * Update UI for editing mode
 */
function updateUIForEditingMode(playlistName) {
    // Update page title
    document.querySelector('h4').innerHTML =
        `<i class="bi bi-music-note-list"></i> Edit: ${playlistName} ` +
        `<span class="badge bg-secondary" id="selectionCount">${PlaylistBuilderState.selections.size} songs selected</span>`;

    // Update create button text
    const btnCreate = document.getElementById('btnCreatePlaylist');
    btnCreate.innerHTML = '<i class="bi bi-save"></i> Update Playlist';

    // Update modal title
    document.getElementById('playlistModalTitle').textContent = 'Update Playlist';
}

/**
 * Reset UI to create mode
 */
function resetUIToCreateMode() {
    // Reset page title
    document.querySelector('h4').innerHTML =
        `<i class="bi bi-music-note-list"></i> Playlist Builder ` +
        `<span class="badge bg-secondary" id="selectionCount">0 songs selected</span>`;

    // Reset create button
    const btnCreate = document.getElementById('btnCreatePlaylist');
    btnCreate.innerHTML = '<i class="bi bi-check-lg"></i> Create Playlist';

    // Reset modal title
    document.getElementById('playlistModalTitle').textContent = 'Create Playlist';

    // Reset playlist dropdown
    document.getElementById('playlistDropdown').value = '';
    document.getElementById('btnLoadPlaylist').disabled = true;
    document.getElementById('btnDeletePlaylist').disabled = true;

    // Clear editing state
    PlaylistBuilderState.editingPlaylistId = null;
    PlaylistBuilderState.editingPlaylistName = null;
}

/**
 * Handle "Create Playlist" button click
 */
function handleCreatePlaylist() {
    const selectionCount = PlaylistBuilderState.selections.size;

    if (selectionCount === 0) {
        showError('Please select at least one song');
        return;
    }

    // Clear form or populate if editing
    if (PlaylistBuilderState.editingPlaylistId && PlaylistBuilderState.editingPlaylistName) {
        // Populate with existing playlist data
        document.getElementById('playlistName').value = PlaylistBuilderState.editingPlaylistName;
        document.getElementById('plexPlaylistName').value = ''; // Keep empty unless user wants to override
        document.getElementById('playlistNotes').value = '';
    } else {
        // Clear form for new playlist
        document.getElementById('playlistName').value = '';
        document.getElementById('plexPlaylistName').value = '';
        document.getElementById('playlistNotes').value = '';
    }

    // Update summary
    updatePlaylistSummary(selectionCount);

    // Update modal title and button
    if (PlaylistBuilderState.editingPlaylistId) {
        document.getElementById('playlistModalTitle').textContent = 'Update Playlist';
        document.getElementById('btnSavePlaylist').innerHTML = '<i class="bi bi-save"></i> Update Playlist';
    } else {
        document.getElementById('playlistModalTitle').textContent = 'Create Playlist';
        document.getElementById('btnSavePlaylist').innerHTML = '<i class="bi bi-save"></i> Save Playlist';
    }

    // Show save button, hide Plex create button
    document.getElementById('btnSavePlaylist').style.display = 'inline-block';
    document.getElementById('btnConfirmCreate').style.display = 'none';

    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('playlistModal'));
    modal.show();
}

/**
 * Update playlist summary in modal
 */
function updatePlaylistSummary(selectionCount) {
    const summaryList = document.getElementById('playlistSummaryList');
    summaryList.innerHTML = `
        <li><strong>${selectionCount}</strong> songs selected</li>
        <li>Playlist will be saved to Radio Monitor database</li>
        <li>You can create Plex playlist after saving</li>
    `;
}

/**
 * Handle save playlist button click
 */
async function handleSavePlaylist() {
    const name = document.getElementById('playlistName').value.trim();
    const plexName = document.getElementById('plexPlaylistName').value.trim();
    const notes = document.getElementById('playlistNotes').value.trim();

    // Validate
    if (!name) {
        showError('Please enter a playlist name');
        return;
    }

    if (PlaylistBuilderState.selections.size === 0) {
        showError('Please select at least one song');
        return;
    }

    try {
        showLoading('Saving playlist...');

        const payload = {
            name: name,
            plex_playlist_name: plexName || name,
            notes: notes
        };

        let response;
        if (PlaylistBuilderState.editingPlaylistId) {
            // Update existing
            response = await fetch(`/api/playlists/manual/${PlaylistBuilderState.editingPlaylistId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } else {
            // Create new
            response = await fetch('/api/playlists/manual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        }

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to save playlist');
        }

        const data = await response.json();

        hideLoading();

        // Store playlist ID for Plex creation
        const playlistId = data.playlist_id || PlaylistBuilderState.editingPlaylistId;
        const finalPlexName = plexName || name;

        // Update editing state if name changed
        if (PlaylistBuilderState.editingPlaylistId) {
            PlaylistBuilderState.editingPlaylistName = name;
            updateUIForEditingMode(name);
        }

        // Update summary to show Plex option
        updatePlaylistSummaryForPlex(playlistId, finalPlexName, name);

        // Show Plex create button
        document.getElementById('btnSavePlaylist').style.display = 'none';
        document.getElementById('btnConfirmCreate').style.display = 'inline-block';
        document.getElementById('btnConfirmCreate').dataset.playlistId = playlistId;
        document.getElementById('btnConfirmCreate').dataset.plexName = finalPlexName;

        showSuccess(`Playlist "${name}" saved successfully. You can now create it in Plex.`);

    } catch (error) {
        hideLoading();
        console.error('Error saving playlist:', error);
        showError(error.message || 'Failed to save playlist');
    }
}

/**
 * Update playlist summary to show Plex option
 */
function updatePlaylistSummaryForPlex(playlistId, plexName, displayName) {
    const summaryList = document.getElementById('playlistSummaryList');
    const selectionCount = PlaylistBuilderState.selections.size;

    summaryList.innerHTML = `
        <li><strong>${displayName}</strong> saved with ${selectionCount} songs</li>
        <li>Ready to create in Plex as <strong>"${plexName}"</strong></li>
        <li>Click "Create in Plex" below to finish</li>
    `;
}

/**
 * Handle "Create in Plex" button click
 */
async function handleCreateInPlex() {
    const btn = document.getElementById('btnConfirmCreate');
    const playlistId = btn.dataset.playlistId;
    const plexName = btn.dataset.plexName;

    if (!playlistId) {
        showError('Playlist ID not found. Please save the playlist first.');
        return;
    }

    try {
        showLoading('Creating playlist in Plex...');

        const response = await fetch(`/api/playlists/manual/${playlistId}/create-in-plex`, {
            method: 'POST'
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to create playlist in Plex');
        }

        const result = await response.json();

        hideLoading();

        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('playlistModal'));
        modal.hide();

        // Clear selections
        await clearAllSelections();

        // Reset to create mode
        PlaylistBuilderState.editingPlaylistId = null;
        resetUIToCreateMode();

        // Reload dropdown
        await loadPlaylistDropdown();

        // Reload data
        await loadData();

        // Show success with details
        if (result.not_found > 0) {
            showWarning(
                `Playlist "${plexName}" created in Plex with ${result.added} songs. ` +
                `${result.not_found} songs not found in Plex.`
            );
        } else {
            showSuccess(`Playlist "${plexName}" created in Plex with ${result.added} songs.`);
        }

    } catch (error) {
        hideLoading();
        console.error('Error creating Plex playlist:', error);
        showError(error.message || 'Failed to create playlist in Plex');

        // Re-show save button so they can try again or close
        document.getElementById('btnSavePlaylist').style.display = 'inline-block';
        document.getElementById('btnConfirmCreate').style.display = 'none';
    }
}

/**
 * Handle delete playlist button click
 */
function handleDeletePlaylist() {
    const dropdown = document.getElementById('playlistDropdown');
    const playlistId = dropdown.value;

    if (!playlistId) {
        showError('Please select a playlist to delete');
        return;
    }

    const playlistName = dropdown.options[dropdown.selectedIndex].text;

    // Show confirmation
    document.getElementById('deletePlaylistMessage').textContent =
        `Delete "${playlistName}"? This action cannot be undone.`;

    const modal = new bootstrap.Modal(document.getElementById('deletePlaylistModal'));
    modal.show();

    // Store playlistId for confirmation
    document.getElementById('btnConfirmDelete').dataset.playlistId = playlistId;
}

/**
 * Confirm delete playlist
 */
async function confirmDeletePlaylist() {
    const btn = document.getElementById('btnConfirmDelete');
    const playlistId = btn.dataset.playlistId;

    if (!playlistId) return;

    try {
        showLoading('Deleting playlist...');

        const response = await fetch(`/api/playlists/manual/${playlistId}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Failed to delete playlist');

        hideLoading();

        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('deletePlaylistModal'));
        modal.hide();

        // If we were editing this playlist, reset to create mode
        if (PlaylistBuilderState.editingPlaylistId === parseInt(playlistId)) {
            PlaylistBuilderState.editingPlaylistId = null;
            await clearAllSelections();
            resetUIToCreateMode();
        }

        // Reload dropdown
        await loadPlaylistDropdown();

        // Reload data
        await loadData();

        showSuccess('Playlist deleted successfully');

    } catch (error) {
        hideLoading();
        console.error('Error deleting playlist:', error);
        showError('Failed to delete playlist');
    }
}

/**
 * Handle clear selection button click
 */
function handleClearSelection() {
    const selectionCount = PlaylistBuilderState.selections.size;

    if (selectionCount === 0) {
        showError('No selections to clear');
        return;
    }

    if (PlaylistBuilderState.editingPlaylistId) {
        // Editing mode - ask if they want to discard changes
        const playlistName = document.querySelector('h4').textContent.replace('Edit: ', '').replace(' Playlist Builder', '');
        document.getElementById('clearSelectionMessage').textContent =
            `Discard changes to "${playlistName}" and clear ${selectionCount} selections?`;
    } else {
        // Create mode - simple confirmation
        document.getElementById('clearSelectionMessage').textContent =
            `Clear all ${selectionCount} selections?`;
    }

    const modal = new bootstrap.Modal(document.getElementById('clearSelectionModal'));
    modal.show();
}

/**
 * Confirm clear selections
 */
async function confirmClearSelections() {
    try {
        showLoading('Clearing selections...');

        await clearAllSelections();

        // If editing, reset to create mode
        if (PlaylistBuilderState.editingPlaylistId) {
            PlaylistBuilderState.editingPlaylistId = null;
            resetUIToCreateMode();
        }

        // Reload data
        await loadData();

        hideLoading();

        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('clearSelectionModal'));
        modal.hide();

        showSuccess('All selections cleared');

    } catch (error) {
        hideLoading();
        console.error('Error clearing selections:', error);
        showError('Failed to clear selections');
    }
}

/**
 * Validate playlist form inputs
 */
function validatePlaylistForm() {
    const name = document.getElementById('playlistName').value.trim();
    const selectionCount = PlaylistBuilderState.selections.size;
    const btnSave = document.getElementById('btnSavePlaylist');

    // Enable if name is not empty and has selections
    if (name && selectionCount > 0) {
        btnSave.disabled = false;
    } else {
        btnSave.disabled = true;
    }
}

/**
 * Attach all event listeners
 */
function attachEventListeners() {
    // View mode toggle
    document.getElementById('viewByArtist').addEventListener('change', () => switchViewMode('by_artist'));
    document.getElementById('viewBySong').addEventListener('change', () => switchViewMode('by_song'));

    // Apply filters button
    document.getElementById('btnApplyFilters').addEventListener('click', handleFilterChange);

    // Reset filters button
    document.getElementById('btnResetFilters').addEventListener('click', resetFilters);

    // Show only selected toggle
    document.getElementById('btnShowOnlySelected').addEventListener('click', toggleShowOnlySelected);

    // Date range toggle
    document.getElementById('dateRangeToggle').addEventListener('change', (e) => {
        document.getElementById('dateRangeInputs').style.display = e.target.checked ? 'block' : 'none';
    });

    // Sortable column headers
    document.addEventListener('click', (e) => {
        const sortableHeader = e.target.closest('.sortable');
        if (sortableHeader) {
            const column = sortableHeader.dataset.sort;
            if (column) {
                handleColumnSort(column);
            }
        }
    });

    // Page size dropdown
    document.getElementById('filterPageSize').addEventListener('change', (e) => {
        PlaylistBuilderState.pagination.perPage = parseInt(e.target.value);
        PlaylistBuilderState.pagination.page = 1;
        handleFilterChange();
    });

    // Search with debounce
    let searchTimeout;
    document.getElementById('filterSearch').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            PlaylistBuilderState.filters.search = e.target.value;
            handleFilterChange();
        }, 300);
    });

    // Clear selection button
    document.getElementById('btnClearSelection').addEventListener('click', handleClearSelection);

    // Playlist dropdown
    document.getElementById('playlistDropdown').addEventListener('change', handlePlaylistSelection);

    // Create new playlist button
    document.getElementById('btnCreateNew').addEventListener('click', async () => {
        // Reset to create mode
        if (PlaylistBuilderState.editingPlaylistId) {
            if (PlaylistBuilderState.selections.size > 0) {
                // Show confirmation if we have selections
                handleClearSelection();
            } else {
                PlaylistBuilderState.editingPlaylistId = null;
                resetUIToCreateMode();
            }
        }
    });

    // Load playlist button
    document.getElementById('btnLoadPlaylist').addEventListener('click', () => {
        const playlistId = document.getElementById('playlistDropdown').value;
        if (playlistId) {
            if (PlaylistBuilderState.selections.size > 0) {
                const playlistName = document.getElementById('playlistDropdown').options[
                    document.getElementById('playlistDropdown').selectedIndex
                ].text;
                showLoadPlaylistConfirmation(playlistId, playlistName);
            } else {
                loadPlaylistForEditing(playlistId);
            }
        }
    });

    // Delete playlist button
    document.getElementById('btnDeletePlaylist').addEventListener('click', handleDeletePlaylist);

    // Create playlist button (in filter bar)
    document.getElementById('btnCreatePlaylist').addEventListener('click', handleCreatePlaylist);

    // Save playlist button (in modal)
    document.getElementById('btnSavePlaylist').addEventListener('click', handleSavePlaylist);

    // Create in Plex button (in modal)
    document.getElementById('btnConfirmCreate').addEventListener('click', handleCreateInPlex);

    // Confirm load playlist
    document.getElementById('btnConfirmLoad').addEventListener('click', () => {
        const playlistId = document.getElementById('btnConfirmLoad').dataset.playlistId;
        if (playlistId) {
            const modal = bootstrap.Modal.getInstance(document.getElementById('loadPlaylistModal'));
            modal.hide();
            loadPlaylistForEditing(playlistId);
        }
    });

    // Confirm delete playlist
    document.getElementById('btnConfirmDelete').addEventListener('click', confirmDeletePlaylist);

    // Confirm clear selections
    document.getElementById('btnConfirmClear').addEventListener('click', confirmClearSelections);

    // Playlist name input validation
    document.getElementById('playlistName').addEventListener('input', validatePlaylistForm);
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPlaylistBuilder);
} else {
    initPlaylistBuilder();
}

console.log('Playlist Builder Phase 5 loaded successfully');
