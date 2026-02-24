/**
 * Table Transitions Utility
 * CSS Improvement #7.2: Add smooth transitions to filter changes
 */

class TableTransitions {
    /**
     * Add fade-in animation to table rows
     * @param {string|HTMLElement} tableSelector - Table selector or element
     * @param {number} delay - Stagger delay in ms (default: 50ms)
     */
    static addFadeIn(tableSelector, delay = 50) {
        const table = typeof tableSelector === 'string'
            ? document.querySelector(tableSelector)
            : tableSelector;

        if (!table) return;

        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const rows = Array.from(tbody.querySelectorAll('tr'));

        // Remove existing fade-in classes
        rows.forEach(row => row.classList.remove('fade-in-row'));

        // Trigger reflow to restart animation
        void tbody.offsetWidth;

        // Add fade-in classes with staggered delay
        rows.forEach((row, index) => {
            row.classList.add('fade-in-row');
            row.style.animationDelay = `${index * delay}ms`;
        });
    }

    /**
     * Add fade-in animation to new rows
     * @param {HTMLElement[]} rows - Array of row elements
     * @param {number} delay - Stagger delay in ms (default: 50ms)
     */
    static addNewRows(rows, delay = 50) {
        rows.forEach((row, index) => {
            row.classList.add('fade-in-row');
            row.style.animationDelay = `${index * delay}ms`;
        });
    }

    /**
     * Add transition class to filter container
     * @param {string|HTMLElement} selector - Filter container selector or element
     */
    static addFilterTransition(selector) {
        const element = typeof selector === 'string'
            ? document.querySelector(selector)
            : selector;

        if (!element) return;

        element.classList.add('filter-transition');
    }

    /**
     * Apply entering animation
     * @param {string|HTMLElement} selector - Element selector or element
     */
    static entering(selector) {
        const element = typeof selector === 'string'
            ? document.querySelector(selector)
            : selector;

        if (!element) return;

        element.classList.remove('exiting', 'entered');
        element.classList.add('entering');

        setTimeout(() => {
            element.classList.remove('entering');
            element.classList.add('entered');
        }, 300);
    }

    /**
     * Apply exiting animation
     * @param {string|HTMLElement} selector - Element selector or element
     * @param {Function} callback - Callback after animation completes
     */
    static exiting(selector, callback) {
        const element = typeof selector === 'string'
            ? document.querySelector(selector)
            : selector;

        if (!element) return;

        element.classList.remove('entering', 'entered');
        element.classList.add('exiting');

        setTimeout(() => {
            if (callback) callback();
            element.classList.remove('exiting');
        }, 300);
    }

    /**
     * Initialize table transitions for a table
     * @param {string|HTMLElement} tableSelector - Table selector or element
     * @param {Object} options - Configuration options
     */
    static init(tableSelector, options = {}) {
        const {
            fadeIn = true,
            hoverHighlight = true,
            staggerDelay = 50,
            onRowClick = null
        } = options;

        const table = typeof tableSelector === 'string'
            ? document.querySelector(tableSelector)
            : tableSelector;

        if (!table) return;

        // Add fade-in animation
        if (fadeIn) {
            this.addFadeIn(table, staggerDelay);
        }

        // Add hover highlight
        if (hoverHighlight) {
            const rows = table.querySelectorAll('tbody tr');
            rows.forEach(row => {
                row.style.cursor = onRowClick ? 'pointer' : '';
                if (onRowClick) {
                    row.addEventListener('click', () => onRowClick(row));
                }
            });
        }
    }

    /**
     * Update table content with transition
     * @param {string|HTMLElement} tableSelector - Table selector or element
     * @param {string|HTMLElement} tbodySelector - Tbody selector or element
     * @param {string} newContent - New HTML content
     */
    static updateWithTransition(tableSelector, tbodySelector, newContent) {
        const table = typeof tableSelector === 'string'
            ? document.querySelector(tableSelector)
            : tableSelector;

        const tbody = typeof tbodySelector === 'string'
            ? document.querySelector(tbodySelector)
            : tbodySelector;

        if (!table || !tbody) return;

        // Add exiting animation
        this.exiting(tbody, () => {
            // Update content
            tbody.innerHTML = newContent;

            // Add entering animation
            this.entering(tbody);

            // Add fade-in to new rows
            this.addFadeIn(table);
        });
    }

    /**
     * Add loading state to table
     * @param {string|HTMLElement} tableSelector - Table selector or element
     */
    static showLoading(tableSelector) {
        const table = typeof tableSelector === 'string'
            ? document.querySelector(tableSelector)
            : tableSelector;

        if (!table) return;

        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        // Store original content
        tbody.dataset.originalContent = tbody.innerHTML;

        // Add loading row
        tbody.innerHTML = `
            <tr>
                <td colspan="${table.rows[0]?.cells?.length || 1}" class="text-center py-5">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-2 text-muted">Loading data...</p>
                </td>
            </tr>
        `;
    }

    /**
     * Hide loading state and restore content
     * @param {string|HTMLElement} tableSelector - Table selector or element
     * @param {string} newContent - New content to display (optional)
     */
    static hideLoading(tableSelector, newContent = null) {
        const table = typeof tableSelector === 'string'
            ? document.querySelector(tableSelector)
            : tableSelector;

        if (!table) return;

        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        // Restore or update content
        if (newContent) {
            tbody.innerHTML = newContent;
        } else if (tbody.dataset.originalContent) {
            tbody.innerHTML = tbody.dataset.originalContent;
            delete tbody.dataset.originalContent;
        }

        // Add fade-in animation
        this.addFadeIn(table);
    }

    /**
     * Add empty state to table
     * @param {string|HTMLElement} tableSelector - Table selector or element
     * @param {Object} config - Empty state configuration
     */
    static showEmptyState(tableSelector, config = {}) {
        const {
            icon = 'bi-inbox',
            title = 'No Data Available',
            message = 'Check back later or adjust your filters.',
            action = null
        } = config;

        const table = typeof tableSelector === 'string'
            ? document.querySelector(tableSelector)
            : tableSelector;

        if (!table) return;

        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const colspan = table.rows[0]?.cells?.length || 1;

        let actionHTML = '';
        if (action) {
            actionHTML = `<div class="empty-state-action">${action}</div>`;
        }

        tbody.innerHTML = `
            <tr>
                <td colspan="${colspan}">
                    <div class="empty-state">
                        <div class="empty-state-icon">
                            <i class="bi ${icon}"></i>
                        </div>
                        <div class="empty-state-title">${title}</div>
                        <div class="empty-state-message">${message}</div>
                        ${actionHTML}
                    </div>
                </td>
            </tr>
        `;
    }
}

// Auto-initialize tables with data-transition attribute
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        const tables = document.querySelectorAll('table[data-transition]');
        tables.forEach(table => {
            TableTransitions.init(table, {
                fadeIn: true,
                hoverHighlight: true,
                staggerDelay: 50
            });
        });
    });
} else {
    const tables = document.querySelectorAll('table[data-transition]');
    tables.forEach(table => {
        TableTransitions.init(table, {
            fadeIn: true,
            hoverHighlight: true,
            staggerDelay: 50
        });
    });
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TableTransitions;
}
