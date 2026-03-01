/**
 * Keyboard Shortcuts System - Enhanced
 * Provides global keyboard shortcuts for common actions
 * CSS Improvements #7, #8, #9: Hover effects, transitions, and keyboard shortcuts
 */

class KeyboardManager {
    constructor() {
        this.shortcuts = new Map();
        this.modal = null;
        this.helpButton = null;
        this.init();
    }

    init() {
        // Register default shortcuts
        this.registerDefaults();

        // Create help button
        this.createHelpButton();

        // Create modal
        this.createModal();

        // Listen for keyboard events
        document.addEventListener('keydown', (e) => this.handleKeyDown(e));

        // Add button hover effects to action buttons
        this.addHoverEffects();
    }

    /**
     * Handle keyboard events
     */
    handleKeyDown(e) {
        const keyCombination = this.getKeyCombination(e);

        // Check if this combination is registered
        if (this.shortcuts.has(keyCombination)) {
            // Ignore if user is typing in an input field (except for specific shortcuts)
            if (this.isTyping(e) && !this.allowWhileTyping(keyCombination)) {
                return;
            }

            e.preventDefault();
            const shortcut = this.shortcuts.get(keyCombination);

            try {
                shortcut.action(e);
            } catch (error) {
                console.error(`Error executing keyboard shortcut "${keyCombination}":`, error);
            }

            return;
        }

        // Legacy single key support (backwards compatibility)
        if (!e.ctrlKey && !e.altKey && !e.metaKey && !e.shiftKey) {
            const key = e.key.toLowerCase();

            if (this.shortcuts.has(key)) {
                if (this.isTyping(e)) {
                    return;
                }

                e.preventDefault();
                const shortcut = this.shortcuts.get(key);
                shortcut.action(e);
            }
        }
    }

    /**
     * Get key combination string
     */
    getKeyCombination(event) {
        const parts = [];

        if (event.ctrlKey) parts.push('ctrl');
        if (event.altKey) parts.push('alt');
        if (event.shiftKey) parts.push('shift');
        if (event.metaKey) parts.push('meta');

        // Handle special keys
        const specialKeys = {
            'Escape': 'escape',
            ' ': 'space',
            'ArrowUp': 'up',
            'ArrowDown': 'down',
            'ArrowLeft': 'left',
            'ArrowRight': 'right',
            'Enter': 'enter',
            'Tab': 'tab',
            'Delete': 'delete',
            'Backspace': 'backspace',
            'F1': 'f1', 'F2': 'f2', 'F3': 'f3', 'F4': 'f4',
            'F5': 'f5', 'F6': 'f6', 'F7': 'f7', 'F8': 'f8',
            'F9': 'f9', 'F10': 'f10', 'F11': 'f11', 'F12': 'f12'
        };

        const key = specialKeys[event.key] || event.key.toLowerCase();
        parts.push(key);

        return parts.join('+');
    }

    /**
     * Check if shortcut should work while typing
     */
    allowWhileTyping(shortcut) {
        const allowedWhileTyping = ['escape', 'ctrl+enter', 'ctrl+s'];
        return allowedWhileTyping.includes(shortcut);
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
        // === GLOBAL SHORTCUTS ===

        // 'Ctrl+/' - Show keyboard shortcuts help
        this.register('ctrl+/', 'Show keyboard shortcuts', () => {
            this.showHelp();
        });

        // 'F1' - Show keyboard shortcuts help
        this.register('f1', 'Show keyboard shortcuts', (e) => {
            e.preventDefault();
            this.showHelp();
        });

        // 'Escape' - Close modals
        this.register('escape', 'Close modals/dialogs', () => {
            const modals = document.querySelectorAll('.modal.show, .custom-modal.show');
            modals.forEach(modal => {
                modal.classList.remove('show');
            });
        });

        // 'Ctrl+K' - Quick search
        this.register('ctrl+k', 'Quick search', () => {
            const searchInput = document.querySelector('input[type="search"], input[name="search"], input[placeholder*="search"], [data-shortcut="search"]');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        });

        // 't' - Focus search (legacy, backwards compat)
        this.register('t', 'Focus search', () => {
            const searchInput = document.querySelector('[data-shortcut="search"]');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        });

        // 's' - Focus sidebar
        this.register('s', 'Toggle sidebar', () => {
            const sidebar = document.querySelector('#sidebar-wrapper');
            if (sidebar) {
                sidebar.classList.toggle('toggled');
            }
        });

        // === PAGE-SPECIFIC SHORTCUTS ===
        this.registerPageShortcuts();
    }

    /**
     * Register page-specific shortcuts
     */
    registerPageShortcuts() {
        const path = window.location.pathname;

        // Dashboard shortcuts
        if (path === '/' || path.includes('dashboard')) {
            this.register('ctrl+r', 'Refresh dashboard', () => {
                location.reload();
            });
        }

        // Monitor page shortcuts
        if (path.includes('monitor')) {
            this.register('ctrl+s', 'Start/Stop monitor', () => {
                const toggleBtn = document.querySelector('[data-action="toggle-monitor"], .btn:has(.bi-play), .btn:has(.bi-pause)');
                if (toggleBtn) toggleBtn.click();
            });

            this.register('ctrl+shift+s', 'Scrape once', () => {
                const scrapeBtn = document.querySelector('[data-action="scrape"], .btn:has(.bi-broadcast)');
                if (scrapeBtn) scrapeBtn.click();
            });
        }

        // Artists page shortcuts
        if (path.includes('artists')) {
            this.register('ctrl+n', 'Add new artist', () => {
                const addBtn = document.querySelector('[data-action="add"], .btn:has(.bi-plus)');
                if (addBtn) addBtn.click();
            });

            this.register('ctrl+f', 'Filter artists', () => {
                const filterInput = document.querySelector('#filter-artist, input[placeholder*="filter"]');
                if (filterInput) filterInput.focus();
            });
        }

        // Songs page shortcuts
        if (path.includes('songs')) {
            this.register('ctrl+f', 'Filter songs', () => {
                const filterInput = document.querySelector('#filter-song, input[placeholder*="filter"]');
                if (filterInput) filterInput.focus();
            });
        }

        // Settings page shortcuts
        if (path.includes('settings')) {
            this.register('ctrl+s', 'Save settings', () => {
                const saveBtn = document.querySelector('#btn-save, [data-action="save"]');
                if (saveBtn) saveBtn.click();
            });
        }

        // Playlist builder shortcuts
        if (path.includes('playlist-builder')) {
            this.register('ctrl+a', 'Select all', () => {
                const selectAllBtn = document.querySelector('[data-action="select-all"]');
                if (selectAllBtn) selectAllBtn.click();
            });

            this.register('ctrl+d', 'Deselect all', () => {
                const deselectBtn = document.querySelector('[data-action="deselect-all"]');
                if (deselectBtn) deselectBtn.click();
            });

            this.register('ctrl+shift+c', 'Create playlist', () => {
                const createBtn = document.querySelector('[data-action="create-playlist"]');
                if (createBtn) createBtn.click();
            });
        }

        // AI Playlists shortcuts
        if (path.includes('ai-playlists')) {
            this.register('ctrl+enter', 'Generate playlist', () => {
                const generateBtn = document.querySelector('#btn-generate');
                if (generateBtn && !generateBtn.disabled) generateBtn.click();
            });
        }
    }

    /**
     * Add hover effects to action buttons
     * CSS Improvement #7.1
     */
    addHoverEffects() {
        // Add hover effect class to primary action buttons
        const actionButtons = document.querySelectorAll(`
            .btn-primary,
            .btn-success,
            .btn-danger,
            .btn-warning,
            .btn-info
        `);

        actionButtons.forEach(btn => {
            // Don't add if already has the class
            if (!btn.classList.contains('btn-hover-effect')) {
                btn.classList.add('btn-hover-effect');
            }
        });

        // Add icon hover effect to buttons with icons
        const iconButtons = document.querySelectorAll('.btn .bi');
        iconButtons.forEach(icon => {
            icon.parentElement.classList.add('btn-icon-hover');
        });
    }

    /**
     * Create help button
     * CSS Improvement #7.3
     */
    createHelpButton() {
        // Check if button already exists
        if (document.querySelector('.keyboard-shortcuts-help')) {
            this.helpButton = document.querySelector('.keyboard-shortcuts-help');
            return;
        }

        const container = document.createElement('div');
        container.className = 'keyboard-shortcuts-help';
        container.innerHTML = `
            <button class="btn btn-primary" data-tooltip="Keyboard Shortcuts (Ctrl+/)" aria-label="Show keyboard shortcuts">
                <i class="bi bi-keyboard"></i>
            </button>
        `;

        document.body.appendChild(container);
        this.helpButton = container;

        // Add click handler
        container.querySelector('button').addEventListener('click', () => {
            this.showHelp();
        });
    }

    /**
     * Create modal
     * CSS Improvement #7.3
     */
    createModal() {
        // Check if modal already exists
        if (document.querySelector('#keyboard-shortcuts-modal')) {
            this.modal = document.querySelector('#keyboard-shortcuts-modal');
            return;
        }

        const modal = document.createElement('div');
        modal.id = 'keyboard-shortcuts-modal';
        modal.className = 'custom-modal keyboard-shortcuts-modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-labelledby', 'keyboard-shortcuts-title');
        modal.innerHTML = `
            <div class="custom-modal-dialog">
                <div class="custom-modal-content">
                    <div class="custom-modal-header">
                        <h2 id="keyboard-shortcuts-title" class="custom-modal-title">
                            <i class="bi bi-keyboard"></i> Keyboard Shortcuts
                        </h2>
                        <button type="button" class="custom-modal-close" aria-label="Close">
                            <i class="bi bi-x-lg"></i>
                        </button>
                    </div>
                    <div class="custom-modal-body">
                        <div class="keyboard-shortcuts-list" id="shortcuts-list">
                            <!-- Shortcuts will be populated here -->
                        </div>
                    </div>
                    <div class="custom-modal-footer">
                        <button type="button" class="btn btn-secondary btn-close-modal">Close</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        this.modal = modal;

        // Add close handlers
        const closeBtn = modal.querySelector('.custom-modal-close');
        const footerCloseBtn = modal.querySelector('.btn-close-modal');

        closeBtn.addEventListener('click', () => this.hideModal());
        footerCloseBtn.addEventListener('click', () => this.hideModal());

        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hideModal();
            }
        });

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('show')) {
                this.hideModal();
            }
        });
    }

    /**
     * Show keyboard shortcuts help
     * CSS Improvement #7.3
     */
    showHelp() {
        if (!this.modal) {
            this.createModal();
        }

        // Populate shortcuts list
        this.populateShortcuts();

        // Show modal
        this.modal.classList.add('show');
        document.body.style.overflow = 'hidden';

        // Focus on close button for accessibility
        setTimeout(() => {
            this.modal.querySelector('.custom-modal-close').focus();
        }, 100);
    }

    /**
     * Hide keyboard shortcuts help
     */
    hideModal() {
        if (this.modal) {
            this.modal.classList.remove('show');
            document.body.style.overflow = '';
        }
    }

    /**
     * Populate shortcuts in modal
     */
    populateShortcuts() {
        const listContainer = this.modal.querySelector('#shortcuts-list');
        if (!listContainer) return;

        listContainer.innerHTML = '';

        // Group shortcuts by category
        const categories = new Map();
        categories.set('General', []);
        categories.set('Page-Specific', []);

        for (const [key, shortcut] of this.shortcuts) {
            // Determine category
            let category = 'General';
            if (key.includes('ctrl+') && !['ctrl+k', 'ctrl+/'].includes(key)) {
                category = 'Page-Specific';
            }

            if (!categories.has(category)) {
                categories.set(category, []);
            }

            categories.get(category).push({
                key,
                description: shortcut.description
            });
        }

        // Render categories
        categories.forEach((shortcuts, category) => {
            if (shortcuts.length === 0) return;

            const categoryDiv = document.createElement('div');
            categoryDiv.innerHTML = `
                <div class="keyboard-shortcut-category">${category}</div>
            `;

            shortcuts.forEach(shortcut => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'keyboard-shortcut-item';
                itemDiv.innerHTML = `
                    <kbd class="keyboard-badge">${this.formatShortcutKeys(shortcut.key)}</kbd>
                    <span>${shortcut.description}</span>
                `;
                categoryDiv.appendChild(itemDiv);
            });

            listContainer.appendChild(categoryDiv);
        });
    }

    /**
     * Format shortcut keys for display
     */
    formatShortcutKeys(keys) {
        const parts = keys.split('+');
        return parts.map(key => `<kbd>${key.toUpperCase()}</kbd>`).join(' + ');
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
