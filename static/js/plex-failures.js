/**
 * Plex Failures View - Radio Monitor
 *
 * Handles the Plex failures table with filtering, pagination, and actions.
 * This file is loaded by templates/plex_failures.html
 */

class PlexFailuresView {
    constructor() {
        console.log('PlexFailuresView constructor starting...');

        try {
            this.failures = [];
            this.currentOffset = 0;
            this.pageSize = 50;
            this.total = 0;
            this.sortColumn = 'failure_date';
            this.sortDirection = 'desc';

            this.initElements();
            this.bindEvents();
            this.updateSortIndicators(); // Apply initial sort indicators
            this.loadFailures();
            this.loadStats();

            console.log('PlexFailuresView constructor completed');
        } catch (error) {
            console.error('Error in PlexFailuresView constructor:', error);
            throw error;
        }
    }

    initElements() {
        this.tableBody = document.getElementById('failuresTableBody');
        this.resolvedFilter = document.getElementById('resolvedFilter');
        this.pageSizeSelect = document.getElementById('pageSize');
        this.refreshBtn = document.getElementById('refreshBtn');
        this.clearAllBtn = document.getElementById('clearAllBtn');
        this.exportBtn = document.getElementById('exportBtn');
        this.exportModal = new bootstrap.Modal(document.getElementById('exportDialog'));
        this.clearModal = new bootstrap.Modal(document.getElementById('clearConfirmDialog'));
        this.pageInfo = document.getElementById('pageInfo');
        this.prevPageBtn = document.getElementById('prevPageBtn');
        this.nextPageBtn = document.getElementById('nextPageBtn');
    }

    bindEvents() {
        this.resolvedFilter.addEventListener('change', () => this.onFilterChange());
        this.pageSizeSelect.addEventListener('change', () => this.onPageSizeChange());
        this.refreshBtn.addEventListener('click', () => this.loadFailures());
        this.clearAllBtn.addEventListener('click', () => this.clearAll());
        this.exportBtn.addEventListener('click', () => this.showExportDialog());
        this.prevPageBtn.addEventListener('click', () => this.previousPage());
        this.nextPageBtn.addEventListener('click', () => this.nextPage());

        // Export modal
        document.getElementById('confirmExportBtn').addEventListener('click', () => this.exportFailures());
    }

    async loadFailures() {
        try {
            const params = new URLSearchParams({
                resolved: this.resolvedFilter.value,
                limit: this.pageSize,
                offset: this.currentOffset,
                sort: this.sortColumn,
                direction: this.sortDirection
            });

            const response = await fetch(`/plex-failures/api/failures?${params}`);
            const data = await response.json();

            this.failures = data.failures;
            this.total = data.total;
            this.renderTable();
            this.updatePagination();
            this.updateSortIndicators();
        } catch (error) {
            console.error('Failed to load failures:', error);
            Toast.error('Error loading failures');
            this.tableBody.innerHTML = '<tr><td colspan="8" class="loading">Error loading failures</td></tr>';
        }
    }

    async loadStats() {
        try {
            const response = await fetch('/plex-failures/api/failures/stats?days=30');
            const stats = await response.json();

            document.getElementById('totalFailures').textContent = stats.total_failures;
            document.getElementById('unresolvedFailures').textContent = stats.unresolved_failures;
            document.getElementById('resolvedFailures').textContent = stats.resolved_failures;
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }

    renderTable() {
        if (this.failures.length === 0) {
            this.tableBody.innerHTML = `
                <tr>
                    <td colspan="6">
                        <div class="empty-state">
                            <i class="bi bi-check-circle empty-state-icon"></i>
                            <h5 class="empty-state-title">No Plex failures found</h5>
                            <p class="empty-state-description text-muted">Try adjusting your filters to see more results.</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        this.tableBody.innerHTML = this.failures.map(failure => {
            const song = failure.song || { song_title: 'Unknown', artist_name: 'Unknown' };

            // Format retry status badge
            let retryStatusBadge = '<span class="text-muted"><i class="bi bi-dash"></i></span>';
            if (failure.retry_match_succeeded === true) {
                retryStatusBadge = '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Matched</span>';
            } else if (failure.retry_match_succeeded === false) {
                retryStatusBadge = '<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Failed</span>';
            }

            return `
                <tr>
                    <td>${failure.song && failure.song.id
                        ? `<a href="/songs/${failure.song.id}" class="text-decoration-none">${this.escapeHtml(song.song_title)}</a>`
                        : this.escapeHtml(song.song_title)}</td>
                    <td>${failure.song && failure.song.artist_mbid
                        ? `<a href="/artists/${failure.song.artist_mbid}" class="text-decoration-none">${this.escapeHtml(song.artist_name)}</a>`
                        : this.escapeHtml(song.artist_name)}</td>
                    <td>${this.formatDate(failure.failure_date)}</td>
                    <td>${retryStatusBadge}</td>
                    <td><span class="resolved-badge ${failure.resolved}">${failure.resolved ? 'Yes' : 'No'}</span></td>
                    <td>
                        ${!failure.resolved ? `
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-outline-primary" onclick="plexFailures.retryOne(${failure.id})" title="Retry Match">
                                    <i class="bi bi-arrow-clockwise"></i>
                                </button>
                                <button class="btn btn-outline-secondary" onclick="plexFailures.dismissOne(${failure.id})" title="Dismiss">
                                    <i class="bi bi-x"></i>
                                </button>
                            </div>
                        ` : '<span class="text-muted">-</span>'}
                    </td>
                </tr>
            `;
        }).join('');
    }

    updatePagination() {
        const start = this.currentOffset + 1;
        const end = Math.min(this.currentOffset + this.pageSize, this.total);
        this.pageInfo.textContent = `Showing ${start}-${end} of ${this.total}`;

        this.prevPageBtn.disabled = this.currentOffset === 0;
        this.nextPageBtn.disabled = end >= this.total;
    }

    onFilterChange() {
        this.currentOffset = 0;
        this.loadFailures();
    }

    onPageSizeChange() {
        this.pageSize = parseInt(this.pageSizeSelect.value);
        this.currentOffset = 0;
        this.loadFailures();
    }

    sortFailures(column) {
        // Toggle direction if same column
        if (this.sortColumn === column) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortColumn = column;
            this.sortDirection = 'asc';
        }

        // Update UI indicators
        this.updateSortIndicators();

        // Reload data
        this.loadFailures();
    }

    updateSortIndicators() {
        // Remove all sort classes
        document.querySelectorAll('th.sortable').forEach(th => {
            th.classList.remove('sorted-asc', 'sorted-desc');
        });

        // Add sort class to current column
        const currentHeader = document.querySelector(`th[onclick="plexFailures.sortFailures('${this.sortColumn}')"]`);
        if (currentHeader) {
            currentHeader.classList.add(`sorted-${this.sortDirection}`);
        }
    }

    async dismissOne(failureId) {
        console.log('dismissOne called for failure:', failureId);

        // Check if Confirm is available
        let confirmed = false;
        if (typeof Confirm === 'undefined' || !Confirm || !Confirm.confirm) {
            console.error('Confirm not available, using browser confirm');
            confirmed = confirm('Dismiss this failure? It will be removed from the list.');
        } else {
            confirmed = await Confirm.confirm(
                'Dismiss this failure? It will be removed from the list.',
                'Dismiss Failure',
                'Dismiss',
                'btn-warning'
            );
        }

        if (!confirmed) {
            return;
        }

        try {
            const response = await fetch(`/plex-failures/api/failures/${failureId}/dismiss`, {
                method: 'POST'
            });
            const data = await response.json();

            if (data.success) {
                if (typeof Toast !== 'undefined' && Toast && Toast.success) {
                    Toast.success('Failure dismissed');
                } else {
                    console.log('Toast not available, using alert');
                    alert('Failure dismissed');
                }
                this.loadFailures();
                this.loadStats();
            } else {
                const errorMsg = 'Failed to dismiss: ' + (data.error || 'Unknown error');
                if (typeof Toast !== 'undefined' && Toast && Toast.error) {
                    Toast.error(errorMsg);
                } else {
                    alert(errorMsg);
                }
            }
        } catch (error) {
            console.error('Failed to dismiss:', error);
            if (typeof Toast !== 'undefined' && Toast && Toast.error) {
                Toast.error('Failed to dismiss failure');
            } else {
                alert('Failed to dismiss failure: ' + error.message);
            }
        }
    }

    async retryOne(failureId) {
        // Safety check - log entry
        console.log('retryOne called for failure:', failureId);

        try {
            const response = await fetch(`/plex-failures/api/failures/${failureId}/retry`, {
                method: 'POST'
            });

            console.log('Response status:', response.status);

            if (!response.ok) {
                const errorData = await response.json();
                const errorMsg = 'Failed to retry: ' + (errorData.error || 'Unknown error');
                console.error(errorMsg);

                if (typeof Toast !== 'undefined' && Toast && Toast.error) {
                    Toast.error(errorMsg);
                } else {
                    console.error('Toast not available, using alert');
                    alert(errorMsg);
                }
                return;
            }

            const data = await response.json();
            console.log('Response data:', data);

            if (data.success) {
                if (data.found) {
                    if (typeof Toast !== 'undefined' && Toast && Toast.success) {
                        Toast.success(data.message, 15000);
                    } else {
                        console.log('Toast not available, using alert');
                        alert('Success: ' + data.message);
                    }
                    this.loadFailures();
                    this.loadStats();
                } else {
                    if (typeof Toast !== 'undefined' && Toast && Toast.info) {
                        Toast.info(data.message, 15000);
                    } else {
                        console.log('Toast not available, using alert');
                        alert('Info: ' + data.message);
                    }
                    this.loadFailures(); // Update attempts counter
                }
            } else {
                const errorMsg = 'Failed to retry: ' + (data.error || 'Unknown error');
                console.error(errorMsg);

                if (typeof Toast !== 'undefined' && Toast && Toast.error) {
                    Toast.error(errorMsg);
                } else {
                    alert(errorMsg);
                }
            }
        } catch (error) {
            console.error('Failed to retry:', error);
            if (typeof Toast !== 'undefined' && Toast && Toast.error) {
                Toast.error('Failed to retry failure');
            } else {
                alert('Failed to retry failure: ' + error.message);
            }
        }
    }

    openMatchModal(songId, songTitle, artistName) {
        // Store song info for the override
        document.getElementById('matchSongTitle').textContent = songTitle;
        document.getElementById('matchArtistName').textContent = artistName;

        // Store song ID for saving
        this.currentOverrideSongId = songId;

        // Clear previous results
        this.clearMatchResults();

        // Show modal
        const matchModal = new bootstrap.Modal(document.getElementById('matchModal'));
        matchModal.show();

        // Auto-search Plex for matches
        this.searchPlexMatches(songTitle, artistName);
    }

    async searchPlexMatches(songTitle, artistName) {
        try {
            const response = await fetch('/plex-failures/api/plex/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    song_title: songTitle,
                    artist_name: artistName
                })
            });

            const data = await response.json();

            if (data.success && data.matches && data.matches.length > 0) {
                this.displayMatchResults(data.matches);
            } else {
                this.showNoMatches();
            }
        } catch (error) {
            console.error('Failed to search Plex:', error);
            Toast.error('Failed to search Plex library');
        }
    }

    displayMatchResults(matches) {
        const resultsContainer = document.getElementById('plexSearchResults');

        resultsContainer.innerHTML = matches.map(match => `
            <div class="list-group-item list-group-item-action plex-match-item"
                 data-rating-key="${match.rating_key}"
                 data-title="${this.escapeHtml(match.title)}"
                 data-artist-name="${this.escapeHtml(match.artist_name)}"
                 data-album-title="${this.escapeHtml(match.album_title)}"
                 onclick="plexFailures.selectMatch(this)">
                <div class="d-flex w-100 justify-content-between align-items-center">
                    <div>
                        <h6 class="mb-1">${this.escapeHtml(match.title)}</h6>
                        <p class="mb-1 text-muted">${this.escapeHtml(match.artist_name)} - ${this.escapeHtml(match.album_title)}</p>
                        <small class="text-muted">
                            <i class="bi bi-music-note"></i> ${match.track_number || '?'} |
                            <i class="bi bi-clock"></i> ${match.duration || '?'} |
                            <i class="bi bi-calendar"></i> ${match.year || '?'}
                        </small>
                    </div>
                    <div class="text-end">
                        <div class="confidence-score">${Math.round(match.confidence)}%</div>
                        <small class="text-muted">${match.strategy}</small>
                    </div>
                </div>
            </div>
        `).join('');

        resultsContainer.style.display = 'block';
    }

    selectMatch(element) {
        // Remove previous selection
        document.querySelectorAll('.plex-match-item').forEach(item => {
            item.classList.remove('active', 'selected');
        });

        // Add selection to clicked item
        element.classList.add('active', 'selected');

        // Enable save button
        document.getElementById('saveOverrideBtn').disabled = false;

        // Store selected match data
        this.selectedMatch = {
            rating_key: element.dataset.ratingKey,
            title: element.dataset.title,
            artist_name: element.dataset.artistName,
            album_title: element.dataset.albumTitle
        };
    }

    clearMatchResults() {
        document.getElementById('plexSearchResults').innerHTML = '';
        document.getElementById('plexSearchResults').style.display = 'none';
        document.getElementById('saveOverrideBtn').disabled = true;
        this.selectedMatch = null;
    }

    showNoMatches() {
        const resultsContainer = document.getElementById('plexSearchResults');
        resultsContainer.innerHTML = `
            <div class="alert alert-warning mb-0">
                <i class="bi bi-exclamation-triangle"></i>
                No matches found in Plex library
            </div>
        `;
        resultsContainer.style.display = 'block';
    }

    async saveOverride() {
        if (!this.selectedMatch) {
            Toast.error('Please select a track first');
            return;
        }

        const notes = document.getElementById('overrideNotes').value;

        try {
            const response = await fetch('/plex-failures/api/plex/override', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    song_id: this.currentOverrideSongId,
            plex_rating_key: this.selectedMatch.rating_key,
            plex_title: this.selectedMatch.title,
            plex_artist_name: this.selectedMatch.artist_name,
            plex_album_title: this.selectedMatch.album_title,
            notes: notes
                })
            });

            const data = await response.json();

            if (data.success) {
                Toast.success('Plex override saved');
                bootstrap.Modal.getInstance(document.getElementById('matchModal')).hide();
                this.loadFailures();
            } else {
                Toast.error('Failed to save override: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Failed to save override:', error);
            Toast.error('Failed to save Plex override');
        }
    }

    async clearAll() {
        try {
            const response = await fetch('/plex-failures/api/failures/stats?days=30');
            const stats = await response.json();

            document.getElementById('clearCount').textContent = stats.total_failures;

            this.clearModal.show();
        } catch (error) {
            console.error('Failed to get stats:', error);
            Toast.error('Failed to get failure count');
        }
    }

    async confirmClearAll() {
        try {
            const response = await fetch('/plex-failures/api/failures/clear-all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    confirmed: true
                })
            });

            const data = await response.json();

            if (data.success) {
                Toast.success(`Cleared ${data.deleted} failure records`);
                this.clearModal.hide();
                this.loadFailures();
                this.loadStats();
            } else {
                Toast.error('Failed to clear: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Failed to clear all:', error);
            Toast.error('Failed to clear failures');
        }
    }

    showExportDialog() {
        this.exportModal.show();
    }

    async exportFailures() {
        const resolved = document.getElementById('exportResolved').value;
        const days = document.getElementById('exportDays').value;

        try {
            const response = await fetch('/plex-failures/api/failures/export', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    resolved: resolved,
                    days: days
                })
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = response.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] || 'plex_failures.csv';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                Toast.success('Export successful');
                this.exportModal.hide();
            } else {
                Toast.error('Export failed');
            }
        } catch (error) {
            console.error('Failed to export:', error);
            Toast.error('Failed to export failures');
        }
    }

    previousPage() {
        if (this.currentOffset > 0) {
            this.currentOffset -= this.pageSize;
            this.loadFailures();
        }
    }

    nextPage() {
        const end = this.currentOffset + this.pageSize;
        if (end < this.total) {
            this.currentOffset += this.pageSize;
            this.loadFailures();
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatDate(dateStr) {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        return date.toLocaleString();
    }

    formatReason(reason) {
        const reasons = {
            'song_not_found': 'Song Not Found',
            'artist_not_found': 'Artist Not Found',
            'multiple_matches': 'Multiple Matches'
        };
        return reasons[reason] || reason;
    }
}

// Initialize with error boundary
try {
    console.log('Initializing PlexFailuresView...');
    const plexFailures = new PlexFailuresView();
    console.log('PlexFailuresView initialized successfully:', !!plexFailures);

    // Expose globally for debugging
    window.plexFailures = plexFailures;
} catch (error) {
    console.error('Failed to initialize PlexFailuresView:', error);
    alert('Error loading Plex Failures page: ' + error.message);
}
