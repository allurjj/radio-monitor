/**
 * Keyboard Shortcuts System
 * Provides global keyboard shortcuts for common actions
 */

class KeyboardManager {
    constructor() {
        this.shortcuts = new Map();
        this.init();
    }

    init() {
        // Register default shortcuts
        this.registerDefaults();

        // Listen for keyboard events
        document.addEventListener('keydown', (e) => this.handleKeyDown(e));
    }

    /**
     * Handle keyboard events
     */
    handleKeyDown(e) {
        // Ignore if user is typing in an input field
        if (this.isTyping(e)) {
            return;
        }

        // Ignore if modifier keys are pressed (unless registered)
        if (e.ctrlKey || e.altKey || e.metaKey) {
            return;
        }

        const key = e.key.toLowerCase();

        // Find and execute matching shortcut
        for (const [shortcutKey, shortcut] of this.shortcuts) {
            if (shortcutKey === key) {
                e.preventDefault();
                shortcut.action(e);
                return;
            }
        }
    }

    /**
     * Check if user is typing in an input field
     */
    isTyping(e) {
        const tag = e.target.tagName.toLowerCase();
        const type = e.target.type || '';

        const inputTags = ['input', 'textarea', 'select'];
        const inputTypes = ['text', 'password', 'email', 'search', 'url', 'tel'];

        if (inputTags.includes(tag)) {
            return true;
        }

        if (tag === 'input' && inputTypes.includes(type)) {
            return true;
        }

        if (e.target.isContentEditable) {
            return true;
        }

        return false;
    }

    /**
     * Register a keyboard shortcut
     * @param {string} key - Keyboard key
     * @param {string} description - Description for help
     * @param {Function} action - Action to execute
     */
    register(key, description, action) {
        this.shortcuts.set(key.toLowerCase(), {
            key: key.toLowerCase(),
            description,
            action
        });
    }

    /**
     * Unregister a keyboard shortcut
     */
    unregister(key) {
        this.shortcuts.delete(key.toLowerCase());
    }

    /**
     * Register default shortcuts
     */
    registerDefaults() {
        // 't' - Focus search
        this.register('t', 'Focus search', () => {
            const searchInput = document.querySelector('[data-shortcut="search"]');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        });

        // 's' - Focus sidebar
        this.register('s', 'Focus sidebar', () => {
            const sidebar = document.querySelector('.sidebar');
            if (sidebar) {
                // Toggle sidebar on mobile
                if (window.innerWidth <= 768) {
                    sidebar.classList.toggle('collapsed');
                }
            }
        });

        // 'esc' - Close modals
        this.register('escape', 'Close modals', () => {
            const activeModal = document.querySelector('.modal.show');
            if (activeModal) {
                const closeBtn = activeModal.querySelector('[data-dismiss="modal"]');
                if (closeBtn) {
                    closeBtn.click();
                }
            }
        });

        // '/' - Open help
        this.register('/', 'Show keyboard shortcuts', () => {
            this.showHelp();
        });

        // 'r' - Refresh current page
        this.register('r', 'Refresh', () => {
            location.reload();
        });
    }

    /**
     * Show keyboard shortcuts help
     */
    showHelp() {
        // Create modal if it doesn't exist
        let modal = document.getElementById('keyboard-shortcuts-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'keyboard-shortcuts-modal';
            modal.className = 'modal';
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Keyboard Shortcuts</h5>
                            <button type="button" class="close" data-dismiss="modal">&times;</button>
                        </div>
                        <div class="modal-body">
                            <div class="keyboard-shortcuts-list"></div>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);

            // Add close button handler
            const closeBtn = modal.querySelector('[data-dismiss="modal"]');
            closeBtn.addEventListener('click', () => {
                modal.classList.remove('show');
            });
        }

        // Populate shortcuts list
        const listContainer = modal.querySelector('.keyboard-shortcuts-list');
        listContainer.innerHTML = '';

        for (const [key, shortcut] of this.shortcuts) {
            const shortcutItem = document.createElement('div');
            shortcutItem.className = 'keyboard-shortcut-item';
            shortcutItem.innerHTML = `
                <kbd>${key === 'escape' ? 'Esc' : key.toUpperCase()}</kbd>
                <span>${shortcut.description}</span>
            `;
            listContainer.appendChild(shortcutItem);
        }

        // Show modal
        modal.classList.add('show');
    }

    /**
     * Get all registered shortcuts
     */
    getShortcuts() {
        return Array.from(this.shortcuts.values());
    }
}

// Global instance
const Keyboard = new KeyboardManager();

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {});
}
