/**
 * Keyboard Shortcuts Manager
 * Handles keyboard shortcuts and displays help modal
 */

class KeyboardShortcuts {
    constructor() {
        this.shortcuts = new Map();
        this.modal = null;
        this.helpButton = null;
        this.init();
    }

    init() {
        // Register default shortcuts
        this.registerDefaultShortcuts();

        // Create help button
        this.createHelpButton();

        // Create modal
        this.createModal();

        // Start listening for keyboard events
        this.startListening();
    }

    registerDefaultShortcuts() {
        // Global shortcuts
        this.register('ctrl+k', 'Quick Search', () => {
            const searchInput = document.querySelector('input[type="search"], input[name="search"], input[placeholder*="search"]');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        });

        this.register('escape', 'Close Modal/Dialog', () => {
            const modals = document.querySelectorAll('.custom-modal.show, .modal.show');
            modals.forEach(modal => {
                modal.classList.remove('show');
            });
        });

        this.register('ctrl+/', 'Show Keyboard Shortcuts', () => {
            this.showModal();
        });

        this.register('f1', 'Show Keyboard Shortcuts', (e) => {
            e.preventDefault();
            this.showModal();
        });

        // Page-specific shortcuts
        this.registerPageShortcuts();
    }

    registerPageShortcuts() {
        const path = window.location.pathname;

        // Dashboard shortcuts
        if (path === '/' || path.includes('dashboard')) {
            this.register('ctrl+r', 'Refresh Dashboard', () => {
                window.location.reload();
            });
        }

        // Artists page shortcuts
        if (path.includes('artists')) {
            this.register('ctrl+n', 'Add New Artist', () => {
                const addBtn = document.querySelector('[data-action="add-artist"], .btn:has(.bi-plus)');
                if (addBtn) addBtn.click();
            });

            this.register('ctrl+f', 'Filter Artists', () => {
                const filterInput = document.querySelector('#filter-artist, input[placeholder*="filter"]');
                if (filterInput) filterInput.focus();
            });
        }

        // Songs page shortcuts
        if (path.includes('songs')) {
            this.register('ctrl+f', 'Filter Songs', () => {
                const filterInput = document.querySelector('#filter-song, input[placeholder*="filter"]');
                if (filterInput) filterInput.focus();
            });
        }

        // Monitor page shortcuts
        if (path.includes('monitor')) {
            this.register('ctrl+s', 'Start/Stop Monitor', () => {
                const toggleBtn = document.querySelector('[data-action="toggle-monitor"], .btn:has(.bi-play), .btn:has(.bi-pause)');
                if (toggleBtn) toggleBtn.click();
            });

            this.register('ctrl+shift+s', 'Scrape Once', () => {
                const scrapeBtn = document.querySelector('[data-action="scrape"], .btn:has(.bi-broadcast)');
                if (scrapeBtn) scrapeBtn.click();
            });
        }

        // Settings shortcuts
        if (path.includes('settings')) {
            this.register('ctrl+s', 'Save Settings', () => {
                const saveBtn = document.querySelector('#btn-save, [data-action="save"]');
                if (saveBtn) saveBtn.click();
            });
        }

        // Playlist builder shortcuts
        if (path.includes('playlist-builder')) {
            this.register('ctrl+a', 'Select All', () => {
                const selectAllBtn = document.querySelector('[data-action="select-all"], .btn:has(.bi-check-all)');
                if (selectAllBtn) selectAllBtn.click();
            });

            this.register('ctrl+d', 'Deselect All', () => {
                const deselectBtn = document.querySelector('[data-action="deselect-all"], .btn:has(.bi-x-square)');
                if (deselectBtn) deselectBtn.click();
            });

            this.register('ctrl+shift+c', 'Create Playlist', () => {
                const createBtn = document.querySelector('[data-action="create-playlist"], .btn:has(.bi-plus-square)');
                if (createBtn) createBtn.click();
            });
        }

        // AI Playlists shortcuts
        if (path.includes('ai-playlists')) {
            this.register('ctrl+enter', 'Generate Playlist', () => {
                const generateBtn = document.querySelector('#btn-generate, [data-action="generate"]');
                if (generateBtn && !generateBtn.disabled) generateBtn.click();
            });
        }
    }

    register(shortcut, description, callback, category = 'General') {
        this.shortcuts.set(shortcut.toLowerCase(), {
            keys: shortcut.toLowerCase(),
            description,
            callback,
            category
        });
    }

    startListening() {
        document.addEventListener('keydown', (e) => {
            const shortcut = this.getKeyCombination(e);

            if (this.shortcuts.has(shortcut)) {
                e.preventDefault();
                const { callback } = this.shortcuts.get(shortcut);

                try {
                    callback(e);
                } catch (error) {
                    console.error(`Error executing keyboard shortcut "${shortcut}":`, error);
                }
            }
        });
    }

    getKeyCombination(event) {
        const keys = [];

        if (event.ctrlKey) keys.push('ctrl');
        if (event.altKey) keys.push('alt');
        if (event.shiftKey) keys.push('shift');
        if (event.metaKey) keys.push('meta');

        // Don't include modifier keys alone
        if (['Control', 'Alt', 'Shift', 'Meta'].includes(event.key)) {
            return keys.join('+') + '+' + event.key.toLowerCase();
        }

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
            'F1': 'f1',
            'F2': 'f2',
            'F3': 'f3',
            'F4': 'f4',
            'F5': 'f5',
            'F6': 'f6',
            'F7': 'f7',
            'F8': 'f8',
            'F9': 'f9',
            'F10': 'f10',
            'F11': 'f11',
            'F12': 'f12'
        };

        const key = specialKeys[event.key] || event.key.toLowerCase();
        keys.push(key);

        return keys.join('+');
    }

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
            this.showModal();
        });
    }

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

        // Populate shortcuts
        this.populateShortcuts();
    }

    populateShortcuts() {
        const listContainer = this.modal.querySelector('#shortcuts-list');
        listContainer.innerHTML = '';

        // Group shortcuts by category
        const categories = new Map();
        this.shortcuts.forEach((shortcut) => {
            if (!categories.has(shortcut.category)) {
                categories.set(shortcut.category, []);
            }
            categories.get(shortcut.category).push(shortcut);
        });

        // Render categories
        categories.forEach((shortcuts, category) => {
            const categoryDiv = document.createElement('div');
            categoryDiv.innerHTML = `
                <div class="keyboard-shortcut-category">${category}</div>
            `;

            shortcuts.forEach(shortcut => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'keyboard-shortcut-item';
                itemDiv.innerHTML = `
                    <kbd class="keyboard-badge">${this.formatShortcutKeys(shortcut.keys)}</kbd>
                    <span>${shortcut.description}</span>
                `;
                categoryDiv.appendChild(itemDiv);
            });

            listContainer.appendChild(categoryDiv);
        });
    }

    formatShortcutKeys(keys) {
        const parts = keys.split('+');
        return parts.map(key => `<kbd>${key.toUpperCase()}</kbd>`).join(' + ');
    }

    showModal() {
        this.modal.classList.add('show');
        document.body.style.overflow = 'hidden';

        // Focus on close button for accessibility
        setTimeout(() => {
            this.modal.querySelector('.custom-modal-close').focus();
        }, 100);
    }

    hideModal() {
        this.modal.classList.remove('show');
        document.body.style.overflow = '';
    }

    // Public method for adding custom shortcuts
    addShortcut(shortcut, description, callback, category = 'Custom') {
        this.register(shortcut, description, callback, category);
        this.populateShortcuts(); // Refresh modal
    }

    // Public method for removing shortcuts
    removeShortcut(shortcut) {
        this.shortcuts.delete(shortcut.toLowerCase());
        this.populateShortcuts(); // Refresh modal
    }

    // Export all shortcuts for documentation
    exportShortcuts() {
        const exported = {};
        this.shortcuts.forEach((value, key) => {
            exported[key] = {
                description: value.description,
                category: value.category
            };
        });
        return exported;
    }
}

// Initialize on DOM ready
let keyboardShortcuts;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        keyboardShortcuts = new KeyboardShortcuts();
    });
} else {
    keyboardShortcuts = new KeyboardShortcuts();
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = KeyboardShortcuts;
}
