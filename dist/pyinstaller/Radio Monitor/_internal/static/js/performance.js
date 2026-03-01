/**
 * Performance Optimization Utilities
 * Provides debouncing, throttling, lazy loading, and other performance helpers
 */

class PerformanceUtils {
    /**
     * Debounce function execution
     * Delays execution until after wait milliseconds have elapsed
     * since the last time the debounced function was invoked
     *
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @param {boolean} immediate - Execute on leading edge instead of trailing
     * @returns {Function} Debounced function
     */
    static debounce(func, wait = 300, immediate = false) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func.apply(this, args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(this, args);
        };
    }

    /**
     * Throttle function execution
     * Ensures function is called at most once per wait milliseconds
     *
     * @param {Function} func - Function to throttle
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Throttled function
     */
    static throttle(func, wait = 300) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, wait);
            }
        };
    }

    /**
     * Request animation frame throttle
     * Throttles function to execute once per animation frame
     *
     * @param {Function} func - Function to throttle
     * @returns {Function} Throttled function
     */
    static rafThrottle(func) {
        let rafId = null;
        return function executedFunction(...args) {
            if (rafId === null) {
                rafId = requestAnimationFrame(() => {
                    func.apply(this, args);
                    rafId = null;
                });
            }
        };
    }

    /**
     * Lazy load images when they come into viewport
     *
     * @param {string} selector - Image selector (default: 'img[data-src]')
     * @param {Object} options - IntersectionObserver options
     */
    static lazyLoadImages(selector = 'img[data-src]', options = {}) {
        // Default options
        const defaultOptions = {
            rootMargin: '50px 0px',
            threshold: 0.01
        };

        const observerOptions = { ...defaultOptions, ...options };

        // Check if IntersectionObserver is supported
        if (!('IntersectionObserver' in window)) {
            // Fallback: load all images immediately
            document.querySelectorAll(selector).forEach(img => {
                const src = img.getAttribute('data-src');
                if (src) {
                    img.src = src;
                    img.removeAttribute('data-src');
                }
            });
            return;
        }

        // Create observer
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    const src = img.getAttribute('data-src');

                    if (src) {
                        img.src = src;
                        img.removeAttribute('data-src');
                        img.classList.add('loaded');
                    }

                    observer.unobserve(img);
                }
            });
        }, observerOptions);

        // Observe all images
        document.querySelectorAll(selector).forEach(img => {
            imageObserver.observe(img);
        });

        return imageObserver;
    }

    /**
     * Lazy load content when element comes into viewport
     *
     * @param {string} selector - Element selector
     * @param {Function} callback - Function to call when element is visible
     * @param {Object} options - IntersectionObserver options
     */
    static lazyLoadContent(selector, callback, options = {}) {
        if (!('IntersectionObserver' in window)) {
            // Fallback: execute immediately
            const elements = document.querySelectorAll(selector);
            elements.forEach(callback);
            return;
        }

        const defaultOptions = {
            rootMargin: '50px 0px',
            threshold: 0.01
        };

        const observerOptions = { ...defaultOptions, ...options };
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    callback(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, observerOptions);

        document.querySelectorAll(selector).forEach(el => {
            observer.observe(el);
        });

        return observer;
    }

    /**
     * Batch DOM updates to reduce reflows
     *
     * @param {Function} updates - Function containing DOM updates
     */
    static batchUpdates(updates) {
        // Use requestAnimationFrame to batch updates
        requestAnimationFrame(() => {
            updates();
        });
    }

    /**
     * Measure function execution time
     *
     * @param {Function} func - Function to measure
     * @param {string} label - Performance label
     * @returns {Function} Wrapped function
     */
    static measure(func, label = 'Function execution') {
        return function executedFunction(...args) {
            const start = performance.now();
            const result = func.apply(this, args);
            const end = performance.now();
            console.log(`${label}: ${(end - start).toFixed(2)}ms`);
            return result;
        };
    }

    /**
     * Create a simple in-memory cache
     *
     * @param {number} maxSize - Maximum cache size (default: 100)
     * @param {number} ttl - Time-to-live in milliseconds (default: 300000 = 5 minutes)
     */
    static createCache(maxSize = 100, ttl = 300000) {
        const cache = new Map();
        const timestamps = new Map();

        return {
            get(key) {
                const timestamp = timestamps.get(key);
                if (timestamp && Date.now() - timestamp > ttl) {
                    cache.delete(key);
                    timestamps.delete(key);
                    return null;
                }
                return cache.get(key) || null;
            },
            set(key, value) {
                if (cache.size >= maxSize) {
                    // Remove oldest entry
                    const firstKey = cache.keys().next().value;
                    cache.delete(firstKey);
                    timestamps.delete(firstKey);
                }
                cache.set(key, value);
                timestamps.set(key, Date.now());
            },
            clear() {
                cache.clear();
                timestamps.clear();
            },
            get size() {
                return cache.size;
            }
        };
    }

    /**
     * Limit the rate of API calls
     *
     * @param {Function} func - Function to rate limit
     * @param {number} calls - Maximum number of calls
     * @param {number} period - Time period in milliseconds
     * @returns {Function} Rate-limited function
     */
    static rateLimit(func, calls = 10, period = 1000) {
        const callsQueue = [];

        return function executedFunction(...args) {
            const now = Date.now();

            // Remove old calls outside the period
            while (callsQueue.length > 0 && callsQueue[0] <= now - period) {
                callsQueue.shift();
            }

            // Check if we've exceeded the rate limit
            if (callsQueue.length >= calls) {
                console.warn('Rate limit exceeded');
                return;
            }

            // Add this call to the queue
            callsQueue.push(now);

            // Execute the function
            return func.apply(this, args);
        };
    }

    /**
     * Preload resources for faster navigation
     *
     * @param {Array<string>} urls - URLs to preload
     */
    static preloadResources(urls) {
        urls.forEach(url => {
            const link = document.createElement('link');
            link.rel = 'preload';
            link.href = url;
            link.as = url.endsWith('.js') ? 'script' : 'style';
            document.head.appendChild(link);
        });
    }

    /**
     * Detect if element is in viewport
     *
     * @param {HTMLElement} element - Element to check
     * @param {number} threshold - Threshold percentage (0-1)
     * @returns {boolean} True if element is in viewport
     */
    static isInViewport(element, threshold = 0) {
        const rect = element.getBoundingClientRect();
        const windowHeight = window.innerHeight || document.documentElement.clientHeight;
        const windowWidth = window.innerWidth || document.documentElement.clientWidth;

        const visibleHeight = Math.max(0, Math.min(rect.bottom, windowHeight) - Math.max(rect.top, 0));
        const visibleWidth = Math.max(0, Math.min(rect.right, windowWidth) - Math.max(rect.left, 0));

        const visibleArea = visibleHeight * visibleWidth;
        const totalArea = rect.height * rect.width;

        return (visibleArea / totalArea) >= threshold;
    }
}

// Auto-initialize lazy loading when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Lazy load images
        PerformanceUtils.lazyLoadImages();
    });
}

// Export to global scope
window.PerformanceUtils = PerformanceUtils;
window.debounce = PerformanceUtils.debounce;
window.throttle = PerformanceUtils.throttle;
