// ==========================================
// DASHBOARD FUNCTIONALITY
// ==========================================

(function() {
    'use strict';

    // Load stations dropdown
    function loadStations() {
        fetch('/api/stations/dropdown')
            .then(response => response.json())
            .then(data => {
                const select = document.getElementById('recent-plays-station');
                if (!select) return;

                // Clear existing options (except "All Stations")
                select.innerHTML = '<option value="">All Stations</option>';

                // Add station options
                if (data.stations && Array.isArray(data.stations)) {
                    data.stations.forEach(station => {
                        const option = document.createElement('option');
                        option.value = station.id;
                        option.textContent = station.name;
                        select.appendChild(option);
                    });
                }

                // Load saved preference
                const savedStation = localStorage.getItem('dashboard-recent-plays-station') || '';
                select.value = savedStation;
            })
            .catch(error => {
                console.error('Failed to load stations:', error);
            });
    }

    // Load recent plays
    function loadRecentPlays() {
        const stationSelect = document.getElementById('recent-plays-station');
        const limitSelect = document.getElementById('recent-plays-limit');

        const stationId = stationSelect ? stationSelect.value : '';
        const limit = limitSelect ? limitSelect.value : '25';

        console.log(`[Dashboard] Loading recent plays: stationId="${stationId}" (type: ${typeof stationId}), limit=${limit}`);
        const url = `/api/plays/recent?station_id=${stationId}&limit=${limit}`;
        console.log(`[Dashboard] Fetching URL: ${url}`);
        fetch(url)
            .then(response => response.json())
            .then(plays => {
                console.log(`[Dashboard] Received ${plays.length} plays`);
                // Log the station_ids in the returned data
                if (plays && plays.length > 0) {
                    const stationIds = plays.map(p => p.station_id);
                    console.log(`[Dashboard] Station IDs in results:`, stationIds);
                }
                displayRecentPlays(plays);
            })
            .catch(error => {
                console.error('Error loading recent plays:', error);
                const tbody = document.getElementById('recent-plays-body');
                if (tbody) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="4" class="text-center text-danger">
                                Error loading plays: ${error.message}
                            </td>
                        </tr>
                    `;
                }
            });
    }

    // Display recent plays in table
    function displayRecentPlays(plays) {
        const tbody = document.getElementById('recent-plays-body');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (!plays || plays.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center text-muted">
                        No recent plays to display. Start monitoring to see data here.
                    </td>
                </tr>
            `;
            return;
        }

        plays.forEach(play => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><small>${play.timestamp}</small></td>
                <td><span class="badge bg-secondary">${play.station_id || play.station_name || 'Unknown'}</span></td>
                <td><strong>${play.artist_name}</strong></td>
                <td>${play.song_title}</td>
            `;
            tbody.appendChild(tr);
        });

        // Store plays for export
        window.currentRecentPlays = plays;
    }

    // Initialize filters
    function initializeFilters() {
        const stationSelect = document.getElementById('recent-plays-station');
        const limitSelect = document.getElementById('recent-plays-limit');

        if (!stationSelect || !limitSelect) return;

        // Load saved limit preference
        const savedLimit = localStorage.getItem('dashboard-recent-plays-limit') || '25';
        limitSelect.value = savedLimit;

        // Station filter change handler
        stationSelect.addEventListener('change', (e) => {
            const stationId = e.target.value;
            console.log(`[Dashboard] Station changed to: "${stationId}" (type: ${typeof stationId})`);
            localStorage.setItem('dashboard-recent-plays-station', stationId);
            loadRecentPlays();
        });

        // Limit filter change handler
        limitSelect.addEventListener('change', (e) => {
            const limit = e.target.value;
            console.log(`[Dashboard] Limit changed to: ${limit}`);
            localStorage.setItem('dashboard-recent-plays-limit', limit);
            loadRecentPlays();
        });
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', () => {
        loadStations();
        initializeFilters();
        loadRecentPlays();

        // Auto-refresh every 30 seconds
        setInterval(() => {
            checkMonitorStatus();
            checkLidarrStatus();
            checkPlexStatus();
            loadRecentPlays();
        }, 30000);
    });
})();

// ==========================================
// STATUS CHECKING FUNCTIONS
// ==========================================

function checkMonitorStatus() {
    console.log('[checkMonitorStatus] Starting status check...');
    fetch('/api/monitor/status')
        .then(response => {
            console.log('[checkMonitorStatus] Response status:', response.status, 'ok:', response.ok);
            if (!response.ok) {
                throw new Error('Server error: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            console.log('[checkMonitorStatus] Received data:', data);

            // Update both navbar and dashboard status
            const navbarStatus = document.getElementById('navbar-monitor-status-text');
            const dashboardStatus = document.getElementById('monitor-status-text');

            let statusHTML = '';
            if (data.error) {
                statusHTML = data.error;
            } else if (data.running) {
                statusHTML = 'Running (' + data.interval + ' min)';
            } else {
                statusHTML = 'Stopped';
            }

            // Update navbar (compact version)
            if (navbarStatus) {
                navbarStatus.textContent = statusHTML;
                // Update indicator color
                const indicator = document.querySelector('#navbar-monitor-status .status-indicator');
                if (indicator) {
                    indicator.className = 'status-indicator';
                    if (data.error) {
                        indicator.classList.add('offline');
                    } else if (data.running) {
                        indicator.classList.add('online');
                    } else {
                        indicator.classList.add('unknown');
                    }
                }
            }

            // Update dashboard System Status card (full version with icons)
            if (dashboardStatus) {
                if (data.error) {
                    dashboardStatus.innerHTML = '<span class="text-danger"><i class="bi bi-exclamation-triangle"></i> ' + data.error + '</span>';
                } else if (data.running) {
                    dashboardStatus.innerHTML = '<span class="text-success"><i class="bi bi-play-circle"></i> Running (' + data.interval + ' min interval)</span>';
                } else {
                    dashboardStatus.innerHTML = '<span class="text-warning"><i class="bi bi-pause-circle"></i> Stopped</span>';
                }
            }

            console.log('[checkMonitorStatus] Status updated successfully');
        })
        .catch(error => {
            console.error('[checkMonitorStatus] Error:', error);
            // Update both locations on error
            const navbarStatus = document.getElementById('navbar-monitor-status-text');
            const dashboardStatus = document.getElementById('monitor-status-text');

            if (navbarStatus) {
                navbarStatus.textContent = 'Error';
                const indicator = document.querySelector('#navbar-monitor-status .status-indicator');
                if (indicator) {
                    indicator.className = 'status-indicator offline';
                }
            }
            if (dashboardStatus) {
                dashboardStatus.innerHTML = '<span class="text-danger"><i class="bi bi-exclamation-triangle"></i> Error</span>';
            }
        });
}

function checkLidarrStatus() {
    fetch('/api/status/lidarr')
        .then(response => {
            if (!response.ok) {
                throw new Error('Server error');
            }
            return response.json();
        })
        .then(data => {
            const statusText = document.getElementById('lidarr-status-text');
            if (statusText) {
                if (data.success) {
                    statusText.innerHTML = '<span class="text-success"><i class="bi bi-check-circle"></i> ' + data.message + '</span>';
                } else {
                    statusText.innerHTML = '<span class="text-warning"><i class="bi bi-exclamation-circle"></i> ' + data.message + '</span>';
                }
            }
        })
        .catch(error => {
            console.error('Error checking Lidarr status:', error);
            const statusText = document.getElementById('lidarr-status-text');
            if (statusText) {
                statusText.innerHTML = '<span class="text-danger"><i class="bi bi-x-circle"></i> Error checking status</span>';
            }
        });
}

function checkPlexStatus() {
    fetch('/api/status/plex')
        .then(response => {
            if (!response.ok) {
                throw new Error('Server error');
            }
            return response.json();
        })
        .then(data => {
            const statusText = document.getElementById('plex-status-text');
            if (statusText) {
                if (data.success) {
                    statusText.innerHTML = '<span class="text-success"><i class="bi bi-check-circle"></i> ' + data.message + '</span>';
                } else {
                    statusText.innerHTML = '<span class="text-warning"><i class="bi bi-exclamation-circle"></i> ' + data.message + '</span>';
                }
            }
        })
        .catch(error => {
            console.error('Error checking Plex status:', error);
            const statusText = document.getElementById('plex-status-text');
            if (statusText) {
                statusText.innerHTML = '<span class="text-danger"><i class="bi bi-x-circle"></i> Error checking status</span>';
            }
        });
}

// ==========================================
// MONITOR CONTROL BUTTONS
// ==========================================

document.addEventListener('DOMContentLoaded', function() {
    // Export CSV button
    const exportBtn = document.getElementById('export-csv');
    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            exportRecentPlaysToCSV();
        });
    }

    // Start monitoring button
    const startBtn = document.getElementById('btn-monitor-start');
    if (startBtn) {
        startBtn.addEventListener('click', function() {
            fetch('/api/monitor/start', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'started') {
                        showToast('Monitoring started successfully', 'success');
                        checkMonitorStatus();
                    } else {
                        showToast(data.message || 'Monitoring already running', 'warning');
                    }
                })
                .catch(error => {
                    showToast('Error starting monitor: ' + error, 'danger');
                });
        });
    }

    // Start monitoring button (empty state)
    const startEmptyBtn = document.getElementById('btn-monitor-start-empty');
    if (startEmptyBtn) {
        startEmptyBtn.addEventListener('click', function() {
            const btn = this;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Starting...';

            fetch('/api/monitor/start', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'started') {
                        showToast('Monitoring started successfully! Redirecting...', 'success');
                        // Refresh page after 2 seconds to show updated dashboard
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);
                    } else {
                        showToast(data.message || 'Monitoring already running', 'warning');
                        btn.disabled = false;
                        btn.innerHTML = '<i class="bi bi-play-circle"></i> Start Monitoring';
                    }
                })
                .catch(error => {
                    showToast('Error starting monitor: ' + error, 'danger');
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-play-circle"></i> Start Monitoring';
                });
        });
    }

    // Stop monitoring button
    const stopBtn = document.getElementById('btn-monitor-stop');
    if (stopBtn) {
        stopBtn.addEventListener('click', function() {
            fetch('/api/monitor/stop', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'stopped') {
                        showToast('Monitoring stopped successfully', 'success');
                        checkMonitorStatus();
                    } else {
                        showToast(data.message || 'Monitoring already stopped', 'warning');
                    }
                })
                .catch(error => {
                    showToast('Error stopping monitor: ' + error, 'danger');
                });
        });
    }
});

// Export recent plays to CSV
function exportRecentPlaysToCSV() {
    const plays = window.currentRecentPlays;

    if (!plays || plays.length === 0) {
        Toast.warning('No data to export');
        return;
    }

    // CSV headers
    const headers = ['Time', 'Station', 'Artist', 'Song'].join(',');

    // Convert plays to CSV rows
    const data = plays.map(play => {
        return [
            `"${play.timestamp || ''}"`,
            `"${(play.station_id || play.station_name || 'Unknown').replace(/"/g, '""')}"`,
            `"${(play.artist_name || '').replace(/"/g, '""')}"`,
            `"${(play.song_title || '').replace(/"/g, '""')}"`
        ].join(',');
    });

    const csv = [headers, ...data].join('\n');

    // Create download
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const date = new Date().toISOString().slice(0, 10);
    a.download = `radio-monitor-recent-plays-${date}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    Toast.success(`Exported ${plays.length} plays to CSV`);
}
