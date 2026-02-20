/**
 * Confirmation Dialog System
 * Provides confirmation dialogs for destructive actions
 */

class ConfirmManager {
    constructor() {
        this.container = null;
        this.currentCallback = null;
        this.init();
    }

    init() {
        // Create modal if it doesn't exist
        this.container = document.getElementById('confirm-modal');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'confirm-modal';
            this.container.className = 'modal';
            this.container.innerHTML = `
                <div class="modal-dialog modal-sm">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Confirm Action</h5>
                            <button type="button" class="close" data-dismiss="modal">&times;</button>
                        </div>
                        <div class="modal-body">
                            <div class="confirm-message"></div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-danger confirm-btn">Confirm</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(this.container);

            // Add button handlers
            const cancelBtn = this.container.querySelector('[data-dismiss="modal"]');
            const confirmBtn = this.container.querySelector('.confirm-btn');

            cancelBtn.addEventListener('click', () => this.hide(false));
            confirmBtn.addEventListener('click', () => this.hide(true));
        }
    }

    /**
     * Show confirmation dialog
     * @param {string} message - Confirmation message
     * @param {string} title - Dialog title (optional)
     * @param {string} confirmText - Confirm button text (optional, default: "Confirm")
     * @param {string} confirmClass - Confirm button class (optional, default: "btn-danger")
     * @returns {Promise<boolean>} - User's choice
     */
    confirm(message, title = 'Confirm Action', confirmText = 'Confirm', confirmClass = 'btn-danger') {
        return new Promise((resolve) => {
            // Store callback
            this.currentCallback = resolve;

            // Update dialog content
            const titleElement = this.container.querySelector('.modal-title');
            const messageElement = this.container.querySelector('.confirm-message');
            const confirmBtn = this.container.querySelector('.confirm-btn');

            titleElement.textContent = title;
            messageElement.textContent = message;
            confirmBtn.textContent = confirmText;

            // Update confirm button class
            confirmBtn.className = `btn ${confirmClass} confirm-btn`;

            // Show modal
            this.container.classList.add('show');
        });
    }

    /**
     * Hide confirmation dialog
     * @param {boolean} confirmed - User's choice
     */
    hide(confirmed) {
        this.container.classList.remove('show');

        if (this.currentCallback) {
            this.currentCallback(confirmed);
            this.currentCallback = null;
        }
    }

    /**
     * Confirm delete action
     */
    confirmDelete(itemName, itemType = 'item') {
        return this.confirm(
            `Are you sure you want to delete ${itemType} "${itemName}"? This action cannot be undone.`,
            'Confirm Delete',
            'Delete',
            'btn-danger'
        );
    }

    /**
     * Confirm remove action
     */
    confirmRemove(itemName, itemType = 'item') {
        return this.confirm(
            `Are you sure you want to remove ${itemType} "${itemName}"?`,
            'Confirm Remove',
            'Remove',
            'btn-warning'
        );
    }

    /**
     * Confirm reset action
     */
    confirmReset(itemName, itemType = 'item') {
        return this.confirm(
            `Are you sure you want to reset ${itemType} "${itemName}"?`,
            'Confirm Reset',
            'Reset',
            'btn-warning'
        );
    }

    /**
     * Custom confirmation
     */
    custom(options) {
        const {
            message,
            title = 'Confirm',
            confirmText = 'Confirm',
            cancelText = 'Cancel',
            confirmClass = 'btn-primary'
        } = options;

        return this.confirm(message, title, confirmText, confirmClass);
    }
}

// Global instance
const Confirm = new ConfirmManager();

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {});
}
