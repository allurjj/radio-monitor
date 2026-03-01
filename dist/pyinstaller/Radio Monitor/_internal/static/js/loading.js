/**
 * Loading Spinner System
 * Provides loading indicators for async operations
 */

class LoadingManager {
    constructor() {
        this.container = null;
        this.loadingCount = 0;
        this.init();
    }

    init() {
        // Create loading container if it doesn't exist
        this.container = document.getElementById('loading-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'loading-container';
            this.container.className = 'loading-overlay';
            this.container.style.display = 'none';
            this.container.innerHTML = `
                <div class="loading-spinner">
                    <div class="spinner"></div>
                    <div class="loading-text">Loading...</div>
                </div>
            `;
            document.body.appendChild(this.container);
        }
    }

    /**
     * Show loading spinner with optional message
     * @param {string} message - Loading message (optional)
     */
    show(message = 'Loading...') {
        this.loadingCount++;
        const textElement = this.container.querySelector('.loading-text');
        if (textElement) {
            textElement.textContent = message;
        }
        this.container.style.display = 'flex';
        document.body.classList.add('loading-active');
    }

    /**
     * Hide loading spinner
     */
    hide() {
        this.loadingCount--;
        if (this.loadingCount <= 0) {
            this.loadingCount = 0;
            this.container.style.display = 'none';
            document.body.classList.remove('loading-active');
        }
    }

    /**
     * Toggle loading state
     */
    toggle(message) {
        if (this.loadingCount > 0) {
            this.hide();
        } else {
            this.show(message);
        }
    }

    /**
     * Wrap an async function with loading indicator
     * @param {Function} fn - Async function to wrap
     * @param {string} message - Loading message
     */
    async wrap(fn, message = 'Loading...') {
        this.show(message);
        try {
            const result = await fn();
            return result;
        } finally {
            this.hide();
        }
    }

    /**
     * Create a small inline spinner for buttons
     * @param {HTMLElement} element - Element to add spinner to
     */
    addInlineSpinner(element) {
        const spinner = document.createElement('span');
        spinner.className = 'inline-spinner';
        element.appendChild(spinner);
        element.classList.add('loading');
        return spinner;
    }

    /**
     * Remove inline spinner from element
     */
    removeInlineSpinner(element) {
        const spinner = element.querySelector('.inline-spinner');
        if (spinner) {
            spinner.remove();
        }
        element.classList.remove('loading');
    }
}

// Global instance
const Loading = new LoadingManager();

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {});
}
