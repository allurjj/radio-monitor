// ==========================================
// MULTI-THEME SYSTEM
// ==========================================

(function() {
    'use strict';

    // Available themes (10 total)
    const THEMES = ['light', 'dark', 'ocean', 'forest', 'sunset', 'midnight', 'rose', 'arctic', 'grape', 'caramel'];

    // Load saved theme on page load
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);

    // Expose theme functions globally
    window.getCurrentTheme = function() {
        return document.documentElement.getAttribute('data-theme') || 'light';
    };

    window.setTheme = function(theme) {
        if (!THEMES.includes(theme)) {
            console.warn(`Invalid theme: ${theme}. Using 'light' instead.`);
            theme = 'light';
        }

        // Apply new theme
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);

        // Update theme selector UI
        updateThemeSelectorUI(theme);

        // Update Chart.js instances if they exist
        if (typeof updateChartsTheme === 'function') {
            updateChartsTheme(theme);
        }

        // Dispatch event for other components
        document.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
    };

    // Update theme selector UI (active state)
    function updateThemeSelectorUI(activeTheme) {
        document.querySelectorAll('.theme-option').forEach(option => {
            option.classList.remove('active');
            if (option.dataset.theme === activeTheme) {
                option.classList.add('active');
            }
        });
    }

    // Initialize theme selector on page load
    function initializeThemeSelector() {
        const currentTheme = getCurrentTheme();
        updateThemeSelectorUI(currentTheme);

        // Add click handlers to theme options
        document.querySelectorAll('.theme-option').forEach(option => {
            option.addEventListener('click', function() {
                const theme = this.dataset.theme;
                if (theme) {
                    setTheme(theme);
                }
            });
        });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeThemeSelector);
    } else {
        initializeThemeSelector();
    }

    // Export for use in other scripts
    window.THEMES = THEMES;
})();
