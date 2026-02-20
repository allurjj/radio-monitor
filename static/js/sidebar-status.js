// ==========================================
// SIDEBAR STATUS UPDATES
// ==========================================

(function() {
    'use strict';

    let statusInterval = null;

    // Update all status indicators
    function updateAllStatus() {
        updateMonitorStatus();
        updateLidarrStatus();
        updatePlexStatus();
        updateScraperStatus();
    }

    // Update Monitor status
    function updateMonitorStatus() {
        fetch('/api/monitor/status')
            .then(response => response.json())
            .then(data => {
                const status = data.running ? 'online' : 'offline';
                updateStatusIcon('monitor', status);
            })
            .catch(error => {
                console.error('Failed to fetch monitor status:', error);
                updateStatusIcon('monitor', 'offline');
            });
    }

    // Update Lidarr status
    function updateLidarrStatus() {
        fetch('/api/status/lidarr')
            .then(response => response.json())
            .then(data => {
                const status = data.success ? 'online' : 'offline';
                updateStatusIcon('lidarr', status);
            })
            .catch(error => {
                console.error('Failed to fetch Lidarr status:', error);
                updateStatusIcon('lidarr', 'offline');
            });
    }

    // Update Plex status
    function updatePlexStatus() {
        fetch('/api/status/plex')
            .then(response => response.json())
            .then(data => {
                const status = data.success ? 'online' : 'offline';
                updateStatusIcon('plex', status);
            })
            .catch(error => {
                console.error('Failed to fetch Plex status:', error);
                updateStatusIcon('plex', 'offline');
            });
    }

    // Update Scraper status
    function updateScraperStatus() {
        fetch('/api/system/status')
            .then(response => response.json())
            .then(data => {
                // Scraper can be running or idle
                let status;
                if (data.scrapers && data.scrapers.status === 'running') {
                    status = 'online';
                } else {
                    status = 'warning'; // Idle
                }
                updateStatusIcon('scraper', status);
            })
            .catch(error => {
                console.error('Failed to fetch scraper status:', error);
                updateStatusIcon('scraper', 'warning');
            });
    }

    // Update individual status icon
    function updateStatusIcon(service, status) {
        const dot = document.querySelector(`#status-${service} .status-dot`);
        if (dot) {
            // Remove all status classes
            dot.classList.remove('online', 'offline', 'warning');
            // Add new status class
            dot.classList.add(status);
        }
    }

    // Start status updates when DOM is ready
    if (document.getElementById('status-monitor')) {
        // Update immediately on page load
        updateAllStatus();

        // Update every 30 seconds
        statusInterval = setInterval(updateAllStatus, 30000);
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        if (statusInterval) {
            clearInterval(statusInterval);
        }
    });
})();
