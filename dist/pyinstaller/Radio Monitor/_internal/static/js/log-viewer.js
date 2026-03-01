/**
 * Log Viewer Component for Radio Monitor 1.0
 *
 * Features:
 * - Real-time log tailing with auto-refresh
 * - Log level filtering (DEBUG, INFO, WARNING, ERROR, CRITICAL)
 * - Search functionality
 * - Auto-scroll to bottom (toggleable)
 * - Efficient rendering with syntax highlighting
 */

class LogViewer {
    constructor(options = {}) {
        this.options = {
            container: options.container || '#log-viewer',
            statsContainer: options.statsContainer || '#log-stats-container',
            autoRefreshInterval: options.autoRefreshInterval || 5000,
            initialTail: options.initialTail || 1000,
            onLogLoad: options.onLogLoad || null,
            onError: options.onError || null
        };

        this.autoRefreshTimer = null;
        this.isLoading = false;
        this.currentFilters = {
            level: '',
            search: '',
            tail: this.options.initialTail
        };
    }

    init() {
        // Load initial data
        this.loadLogStats();
        this.loadLogs();

        // Setup filter handlers
        this.setupEventHandlers();
    }

    setupEventHandlers() {
        // Filter level
        const levelSelect = document.getElementById('filter-level');
        if (levelSelect) {
            levelSelect.addEventListener('change', (e) => {
                this.currentFilters.level = e.target.value;
                this.loadLogs();
            });
        }

        // Search input (debounced)
        const searchInput = document.getElementById('filter-search');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce((e) => {
                this.currentFilters.search = e.target.value;
                this.loadLogs();
            }, 500));
        }

        // Tail lines
        const tailSelect = document.getElementById('filter-tail');
        if (tailSelect) {
            tailSelect.addEventListener('change', (e) => {
                this.currentFilters.tail = e.target.value;
                this.loadLogs();
            });
        }

        // Auto-refresh toggle
        const autoRefreshToggle = document.getElementById('toggle-auto-refresh');
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.startAutoRefresh();
                } else {
                    this.stopAutoRefresh();
                }
            });
        }

        // Download button
        const downloadBtn = document.getElementById('btn-download');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => {
                this.downloadLogs();
            });
        }

        // Clear button
        const clearBtn = document.getElementById('btn-clear');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                this.clearLogs();
            });
        }

        // Export CSV button
        const exportBtn = document.getElementById('export-csv');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                this.exportLogsToCSV();
            });
        }
    }

    loadLogStats() {
        fetch('/logs/api/logs/stats')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.exists) {
                    this.displayLogStats(data.stats);
                } else {
                    this.displayNoStats();
                }
            })
            .catch(error => {
                console.error('Error loading log stats:', error);
                this.displayNoStats();
            });
    }

    displayLogStats(stats) {
        const filePath = document.getElementById('log-file-path');
        const fileSize = document.getElementById('log-file-size');
        const totalLines = document.getElementById('log-total-lines');

        if (filePath) filePath.textContent = stats.file_path;
        if (fileSize) fileSize.textContent = stats.file_size_human;
        if (totalLines) totalLines.textContent = stats.total_lines.toLocaleString();
    }

    displayNoStats() {
        const filePath = document.getElementById('log-file-path');
        const fileSize = document.getElementById('log-file-size');
        const totalLines = document.getElementById('log-total-lines');

        if (filePath) filePath.textContent = 'Not found';
        if (fileSize) fileSize.textContent = '0 KB';
        if (totalLines) totalLines.textContent = '0';
    }

    loadLogs() {
        if (this.isLoading) return;
        this.isLoading = true;

        const container = document.querySelector(this.options.container);
        if (!container) return;

        // Show loading indicator
        if (!container.querySelector('.spinner-border')) {
            container.innerHTML = `
                <div class="text-center text-muted py-2">
                    <div class="spinner-border spinner-border-sm" role="status"></div>
                    <span class="ms-2">Loading logs...</span>
                </div>
            `;
        }

        // Build query parameters
        const params = new URLSearchParams({
            tail: this.currentFilters.tail
        });

        if (this.currentFilters.level) {
            params.append('level', this.currentFilters.level);
        }

        if (this.currentFilters.search) {
            params.append('search', this.currentFilters.search);
        }

        fetch(`/logs/api/logs?${params}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.displayLogs(data.logs);

                    // Update line count
                    const countBadge = document.getElementById('log-count');
                    if (countBadge) {
                        countBadge.textContent = `${data.logs.length} lines`;
                    }

                    // Call callback if provided
                    if (this.options.onLogLoad) {
                        this.options.onLogLoad(data.logs);
                    }
                } else {
                    this.displayError(data.error || 'Unknown error');
                }
            })
            .catch(error => {
                console.error('Error loading logs:', error);
                this.displayError(error.message);
                if (this.options.onError) {
                    this.options.onError(error);
                }
            })
            .finally(() => {
                this.isLoading = false;
            });
    }

    displayLogs(logs) {
        const container = document.querySelector(this.options.container);
        if (!container) return;

        if (!logs || logs.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-5">
                    <i class="bi bi-inbox" style="font-size: 3rem;"></i>
                    <p class="mt-3">No logs found</p>
                </div>
            `;
            return;
        }

        let html = '<div class="log-lines">';
        logs.forEach(log => {
            html += this.renderLogLine(log);
        });
        html += '</div>';

        container.innerHTML = html;

        // Auto-scroll to bottom if enabled
        const autoScrollToggle = document.getElementById('toggle-auto-scroll');
        if (autoScrollToggle && autoScrollToggle.checked) {
            container.scrollTop = container.scrollHeight;
        }
    }

    renderLogLine(log) {
        const levelClass = {
            'DEBUG': 'log-debug',
            'INFO': 'log-info',
            'WARNING': 'log-warning',
            'ERROR': 'log-error',
            'CRITICAL': 'log-critical'
        }[log.level] || 'log-info';

        const levelBadge = {
            'DEBUG': 'bg-secondary',
            'INFO': 'bg-primary',
            'WARNING': 'bg-warning text-dark',
            'ERROR': 'bg-danger',
            'CRITICAL': 'bg-dark'
        }[log.level] || 'bg-secondary';

        return `
            <div class="log-line ${levelClass}" data-level="${log.level}">
                <span class="log-line-number">${log.line_number}</span>
                <span class="log-timestamp">${log.timestamp || ''}</span>
                <span class="badge ${levelBadge} log-level-badge">${log.level}</span>
                <span class="log-message">${this.escapeHtml(log.message)}</span>
            </div>
        `;
    }

    displayError(message) {
        const container = document.querySelector(this.options.container);
        if (!container) return;

        container.innerHTML = `
            <div class="alert alert-danger m-3">
                <i class="bi bi-exclamation-triangle"></i> Error loading logs: ${message}
            </div>
        `;
    }

    downloadLogs() {
        window.location.href = '/logs/api/logs/download';
    }

    clearLogs() {
        let confirmation = prompt(
            'This action cannot be undone. Type CLEAR_LOGS to confirm:'
        );

        if (confirmation !== 'CLEAR_LOGS') {
            return;
        }

        fetch('/logs/api/logs', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                confirm: 'CLEAR_LOGS'
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Log file cleared successfully!');
                this.loadLogStats();
                this.loadLogs();
            } else {
                alert('Error clearing logs: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error clearing logs:', error);
            alert('Error clearing logs: ' + error.message);
        });
    }

    exportLogsToCSV() {
        // Get current displayed logs
        const container = document.querySelector(this.options.container);
        const logLines = container?.querySelectorAll('.log-line');

        if (!logLines || logLines.length === 0) {
            Toast.warning('No logs to export');
            return;
        }

        // CSV headers
        const headers = ['Line Number', 'Timestamp', 'Level', 'Message'].join(',');

        // Convert log lines to CSV rows
        const data = Array.from(logLines).map(line => {
            const lineNum = line.querySelector('.log-line-number')?.textContent || '';
            const timestamp = line.querySelector('.log-timestamp')?.textContent || '';
            const level = line.getAttribute('data-level') || '';
            const message = line.querySelector('.log-message')?.textContent.trim() || '';
            return [
                `"${lineNum}"`,
                `"${timestamp}"`,
                `"${level}"`,
                `"${message.replace(/"/g, '""')}"`
            ].join(',');
        });

        const csv = [headers, ...data].join('\n');

        // Create download
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const date = new Date().toISOString().slice(0, 10);
        a.download = `radio-monitor-logs-${date}.csv`;
        a.click();
        URL.revokeObjectURL(url);

        Toast.success(`Exported ${logLines.length} log lines to CSV`);
    }

    startAutoRefresh() {
        if (this.autoRefreshTimer) return;

        this.autoRefreshTimer = setInterval(() => {
            this.loadLogs();
        }, this.options.autoRefreshInterval);
    }

    stopAutoRefresh() {
        if (this.autoRefreshTimer) {
            clearInterval(this.autoRefreshTimer);
            this.autoRefreshTimer = null;
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// Auto-initialize if on logs page
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('log-viewer')) {
        const logViewer = new LogViewer();
        logViewer.init();
    }
});
