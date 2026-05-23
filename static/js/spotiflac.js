/**
 * SpotiFLAC Integration for Radio Monitor
 *
 * Handles the SpotiFLAC download functionality including:
 * - Spotify search
 * - Download configuration
 * - Progress tracking
 * - Automatic file movement to Lidarr
 */

class SpotiFLACIntegration {
    constructor() {
        console.log('SpotiFLACIntegration constructor called');

        this.modal = null;
        this.currentFailureId = null;
        this.currentSongTitle = null;
        this.currentArtistName = null;
        this.selectedTrackUrl = null;

        this.initElements();
        this.bindEvents();

        console.log('SpotiFLACIntegration initialized successfully');
    }

    initElements() {
        // Modal
        this.modalElement = document.getElementById('spotiflacDownloadModal');
        this.modal = new bootstrap.Modal(this.modalElement);

        // Step 1: URL Selection
        this.urlInput = document.getElementById('spotify-url-input');
        this.searchBtn = document.getElementById('search-spotify-btn');
        this.searchResultsDiv = document.getElementById('spotify-search-results');
        this.searchResultsList = document.getElementById('search-results-list');

        // Step 2: Download Configuration
        this.trackInfoSpan = document.getElementById('selected-track-info');
        this.lidarrPathInput = document.getElementById('lidarr-path-input');
        this.formatCode = document.getElementById('detected-format-code');
        this.customFormatInput = document.getElementById('custom-format-input');
        this.qualitySelect = document.getElementById('quality-preference-select');
        this.startDownloadBtn = document.getElementById('start-download-btn');

        // Step 3: Progress
        this.progressBar = document.getElementById('download-progress-bar');
        this.downloadStatus = document.getElementById('download-status');
        this.downloadService = document.getElementById('download-service');
        this.downloadSize = document.getElementById('download-size');
        this.downloadSpeed = document.getElementById('download-speed');

        // Step 4: Auto-move
        this.tempFilePath = document.getElementById('temp-file-path');
        this.finalDestPath = document.getElementById('final-destination-path');
        this.moveProgress = document.getElementById('move-progress');
        this.moveResult = document.getElementById('move-result');

        // Service selection - Load saved preferences
        this.loadServicePreferences();
    }

    loadServicePreferences() {
        // Load from localStorage or use defaults
        const savedPrefs = localStorage.getItem('spotiflac_service_preferences');
        let preferences = {
            services: ['tidal', 'youtube'],
            checked: ['tidal']
        };

        if (savedPrefs) {
            try {
                preferences = JSON.parse(savedPrefs);
            } catch (e) {
                console.error('Failed to parse saved preferences:', e);
            }
        }

        // Apply preferences to checkboxes
        const serviceSelection = document.getElementById('service-selection');
        if (serviceSelection) {
            const checkboxes = serviceSelection.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(checkbox => {
                const serviceId = checkbox.value;
                // Check if service should be checked
                checkbox.checked = preferences.checked.includes(serviceId);
                // Save current state on change
                checkbox.addEventListener('change', () => this.saveServicePreferences());
            });
        }

        return preferences;
    }

    saveServicePreferences() {
        const serviceSelection = document.getElementById('service-selection');
        if (!serviceSelection) return;

        const checkboxes = serviceSelection.querySelectorAll('input[type="checkbox"]');
        const checkedServices = [];
        const allServices = [];

        checkboxes.forEach(checkbox => {
            allServices.push(checkbox.value);
            if (checkbox.checked) {
                checkedServices.push(checkbox.value);
            }
        });

        const preferences = {
            services: allServices,
            checked: checkedServices
        };

        localStorage.setItem('spotiflac_service_preferences', JSON.stringify(preferences));
        console.log('Saved service preferences:', preferences);
    }

    bindEvents() {
        this.searchBtn.addEventListener('click', () => this.searchSpotify());
        this.startDownloadBtn.addEventListener('click', () => this.startDownload());

        // Add event listener for manual URL input
        this.urlInput.addEventListener('input', () => {
            const url = this.urlInput.value.trim();
            if (url && url.startsWith('https://open.spotify.com/')) {
                this.selectedTrackUrl = url;
                // Update track info with generic text
                this.trackInfoSpan.textContent = 'Custom URL: ' + url.substring(0, 40) + '...';
            }
        });
    }

    async openDownloadModal(failureId, songTitle, artistName) {
        // Reset modal state
        this.resetModal();

        // Store failure info
        this.currentFailureId = failureId;
        this.currentSongTitle = songTitle;
        this.currentArtistName = artistName;

        // Show Step 1
        this.showStep('spotify-url');

        // Load saved service preferences
        this.loadServicePreferences();

        // Pre-fill Lidarr path and fetch naming convention
        await this.fetchLidarrPath(artistName);

        // Show modal
        this.modal.show();
    }

    resetModal() {
        // Clear inputs
        this.urlInput.value = '';
        this.searchResultsDiv.style.display = 'none';
        this.searchResultsList.innerHTML = '';
        this.trackInfoSpan.textContent = '';
        this.selectedTrackUrl = null;

        // Reset progress
        this.progressBar.style.width = '0%';
        this.progressBar.textContent = '0%';
        this.downloadStatus.textContent = 'Initializing...';
        this.downloadService.textContent = '-';
        this.downloadSize.textContent = '0 MB';
        this.downloadSpeed.textContent = '0 MB/s';

        // Hide move step
        this.moveProgress.style.display = 'none';
        this.moveResult.innerHTML = '';

        // Reset steps
        this.showStep('spotify-url');
    }

    async fetchLidarrPath(artistName) {
        try {
            const response = await fetch(`/plex-failures/api/lidarr/artist-path?artist_name=${encodeURIComponent(artistName)}`);
            const data = await response.json();

            this.lidarrPathInput.value = data.path;

            if (data.naming_convention) {
                this.formatCode.textContent = data.naming_convention;
            } else {
                this.formatCode.textContent = '{title} - {artist} (default)';
            }
        } catch (error) {
            console.error('Failed to fetch Lidarr path:', error);
            this.lidarrPathInput.value = 'Unknown - configure Lidarr';
            this.formatCode.textContent = '{title} - {artist} (default)';
        }
    }

    async searchSpotify() {
        const songTitle = this.currentSongTitle;
        const artistName = this.currentArtistName;

        try {
            const response = await fetch(`/plex-failures/api/spotiflac/search-spotify?song_title=${encodeURIComponent(songTitle)}&artist_name=${encodeURIComponent(artistName)}`);
            const data = await response.json();

            this.displaySearchResults(data.results);
        } catch (error) {
            console.error('Failed to search Spotify:', error);
            Toast.error('Failed to search Spotify');
        }
    }

    displaySearchResults(results) {
        if (results.length === 0) {
            this.searchResultsList.innerHTML = `
                <div class="alert alert-warning mb-0">
                    <i class="bi bi-exclamation-triangle"></i>
                    No results found on Spotify
                </div>
            `;
        } else {
            this.searchResultsList.innerHTML = results.map(track => `
                <div class="list-group-item list-group-item-action"
                     onclick="spotiFLAC.selectTrack('${track.url}', '${this.escapeHtml(track.title)}', '${this.escapeHtml(track.artist)}')">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${this.escapeHtml(track.title)}</h6>
                        <small>${track.duration}</small>
                    </div>
                    <p class="mb-1">${this.escapeHtml(track.artist)} - ${this.escapeHtml(track.album)}</p>
                </div>
            `).join('');
        }

        this.searchResultsDiv.style.display = 'block';
    }

    selectTrack(url, title, artist) {
        this.selectedTrackUrl = url;
        this.urlInput.value = url;
        this.trackInfoSpan.textContent = `${title} - ${artist}`;

        // Move to Step 2
        this.showStep('download-config');
    }

    async startDownload() {
        console.log('startDownload called');
        console.log('selectedTrackUrl:', this.selectedTrackUrl);
        console.log('currentFailureId:', this.currentFailureId);

        if (!this.selectedTrackUrl) {
            console.error('No track URL selected');
            Toast.error('Please select a track first');
            return;
        }

        // Get selected services in priority order
        // Need to sort by the saved service order, not DOM order
        const serviceSelection = document.getElementById('service-selection');
        const allCheckboxes = Array.from(serviceSelection.querySelectorAll('input[type="checkbox"]'));

        // Get checked services
        const checkedServices = allCheckboxes
            .filter(cb => cb.checked)
            .map(cb => cb.value);

        console.log('Selected services (DOM order):', checkedServices);

        if (checkedServices.length === 0) {
            console.error('No services selected');
            Toast.error('Please select at least one download source');
            return;
        }

        // Load saved preferences to get correct order
        const savedPrefs = localStorage.getItem('spotiflac_service_preferences');
        let serviceOrder = ['tidal', 'qobuz', 'amazon', 'deezer', 'youtube', 'spoti'];

        if (savedPrefs) {
            try {
                const prefs = JSON.parse(savedPrefs);
                serviceOrder = prefs.services || serviceOrder;
            } catch (e) {
                console.error('Failed to parse saved preferences:', e);
            }
        }

        // Sort checked services by the saved order
        const services = checkedServices.sort((a, b) => {
            return serviceOrder.indexOf(a) - serviceOrder.indexOf(b);
        });

        console.log('Services to try (priority order):', services);

        // Save current preferences
        this.saveServicePreferences();

        // Move to Step 3
        this.showStep('download-progress');

        try {
            console.log('Sending download request to API...');
            const response = await fetch('/plex-failures/api/spotiflac/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    plex_failure_id: this.currentFailureId,
                    spotify_url: this.selectedTrackUrl,
                    services: services
                })
            });

            console.log('API response status:', response.status);
            const data = await response.json();
            console.log('API response data:', data);

            if (data.success) {
                this.showDownloadSuccess(data);
            } else {
                this.showDownloadError(data.error || 'Download failed');
            }
        } catch (error) {
            console.error('Failed to start download:', error);
            this.showDownloadError('Download failed: ' + error.message);
        }
    }

    showDownloadSuccess(data) {
        // Update progress to 100%
        this.progressBar.style.width = '100%';
        this.progressBar.textContent = '100%';
        this.downloadStatus.textContent = 'Complete!';
        this.downloadService.textContent = data.service_used || 'Unknown';
        this.downloadSize.textContent = '5.0 MB'; // Mock size

        // Show auto-move step
        this.tempFilePath.value = data.file_path || 'Unknown';
        this.finalDestPath.value = this.lidarrPathInput.value;

        document.getElementById('step-move-file').style.display = 'block';

        // Auto-move file
        this.autoMoveFile(data.file_path);
    }

    async autoMoveFile(sourceFile) {
        this.moveProgress.style.display = 'block';

        try {
            const response = await fetch('/plex-failures/api/spotiflac/auto-move', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    source_file: sourceFile,
                    artist_name: this.currentArtistName,
                    lidarr_path: this.lidarrPathInput.value,
                    url_type: 'track'
                })
            });

            const data = await response.json();

            if (data.success) {
                this.moveProgress.style.display = 'none';
                this.moveResult.innerHTML = `
                    <div class="alert alert-success">
                        <i class="bi bi-check-circle"></i>
                        <strong>Success!</strong> File moved to: ${data.destination_path}
                    </div>
                    <p class="text-muted">
                        The song is now in your Lidarr library. Wait for Plex to scan, then click "Retry Match" to test if Plex can find it.
                    </p>
                `;
            } else {
                this.showMoveError(data.error || 'Move failed');
            }
        } catch (error) {
            console.error('Failed to auto-move:', error);
            this.showMoveError('Auto-move failed: ' + error.message);
        }
    }

    showDownloadError(error) {
        this.downloadStatus.textContent = 'Failed';
        this.progressBar.classList.add('bg-danger');
        Toast.error('Download failed: ' + error);
    }

    showMoveError(error) {
        this.moveProgress.style.display = 'none';
        this.moveResult.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i>
                <strong>Auto-move failed:</strong> ${error}
            </div>
            <p class="text-muted">
                The file was downloaded to: <code>${this.tempFilePath.value}</code><br>
                You can manually move it to your Lidarr library.
            </p>
        `;
    }

    showStep(stepId) {
        // Hide all steps
        document.getElementById('step-spotify-url').style.display = 'none';
        document.getElementById('step-download-config').style.display = 'none';
        document.getElementById('step-download-progress').style.display = 'none';

        // Show requested step
        const stepPrefix = stepId.split('-')[0];
        document.getElementById(`step-${stepId}`).style.display = 'block';

        // Reset progress step visibility
        if (stepPrefix !== 'download') {
            document.getElementById('step-move-file').style.display = 'none';
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize SpotiFLAC integration
const spotiFLAC = new SpotiFLACIntegration();
