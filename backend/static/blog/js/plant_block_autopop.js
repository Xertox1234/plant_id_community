/**
 * Plant Block Auto-Population JavaScript
 * 
 * This script provides auto-population functionality for Wagtail StreamField blocks
 * related to plants. It integrates with the backend API to fetch plant data and
 * populate block fields automatically.
 */

(function() {
    'use strict';
    
    // Configuration
    const CONFIG = {
        apiUrls: {
            plantLookup: '/api/blog-api/plant-lookup/',
            plantSuggestions: '/api/blog-api/plant-suggestions/',
            aiContent: '/api/blog-api/ai-content/'
        },
        debounceDelay: 300,
        suggestionLimit: 10,
        cacheTimeout: 300000 // 5 minutes
    };
    
    // Cache for API responses
    const cache = new Map();
    
    /**
     * Utility function to debounce API calls
     */
    function debounce(func, wait) {
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
    
    /**
     * Make API requests with error handling
     */
    async function apiRequest(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken(),
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`API request failed: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API request error:', error);
            throw error;
        }
    }
    
    /**
     * Get CSRF token from cookie
     */
    function getCSRFToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    /**
     * Create auto-complete dropdown
     */
    function createAutocompleteDropdown(input, suggestions) {
        // Remove existing dropdown
        const existingDropdown = document.querySelector('.plant-autocomplete-dropdown');
        if (existingDropdown) {
            existingDropdown.remove();
        }
        
        if (suggestions.length === 0) return;
        
        const dropdown = document.createElement('div');
        dropdown.className = 'plant-autocomplete-dropdown';
        dropdown.style.cssText = `
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: white;
            border: 1px solid #ddd;
            border-top: none;
            max-height: 200px;
            overflow-y: auto;
            z-index: 1000;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        `;
        
        suggestions.forEach(suggestion => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            item.style.cssText = `
                padding: 8px 12px;
                cursor: pointer;
                border-bottom: 1px solid #f0f0f0;
            `;
            item.innerHTML = `
                <span style="font-weight: ${suggestion.type === 'scientific' ? 'bold' : 'normal'};">
                    ${suggestion.label}
                </span>
                <small style="color: #666; margin-left: 8px;">${suggestion.type}</small>
            `;
            
            item.addEventListener('click', () => {
                input.value = suggestion.value;
                input.dispatchEvent(new Event('change', { bubbles: true }));
                dropdown.remove();
            });
            
            item.addEventListener('mouseenter', () => {
                item.style.backgroundColor = '#f5f5f5';
            });
            
            item.addEventListener('mouseleave', () => {
                item.style.backgroundColor = 'white';
            });
            
            dropdown.appendChild(item);
        });
        
        // Position dropdown relative to input
        const inputRect = input.getBoundingClientRect();
        input.parentNode.style.position = 'relative';
        input.parentNode.appendChild(dropdown);
        
        // Close dropdown when clicking outside
        setTimeout(() => {
            document.addEventListener('click', function closeDropdown(e) {
                if (!dropdown.contains(e.target) && e.target !== input) {
                    dropdown.remove();
                    document.removeEventListener('click', closeDropdown);
                }
            });
        }, 100);
    }
    
    /**
     * Show loading indicator
     */
    function showLoadingIndicator(element) {
        const indicator = document.createElement('div');
        indicator.className = 'plant-loading-indicator';
        indicator.innerHTML = '🌱 Loading plant data...';
        indicator.style.cssText = `
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: #f9f9f9;
            border: 1px solid #ddd;
            padding: 8px 12px;
            font-size: 12px;
            color: #666;
            z-index: 999;
        `;
        
        element.parentNode.style.position = 'relative';
        element.parentNode.appendChild(indicator);
        
        return indicator;
    }
    
    /**
     * Remove loading indicator
     */
    function removeLoadingIndicator() {
        const indicators = document.querySelectorAll('.plant-loading-indicator');
        indicators.forEach(indicator => indicator.remove());
    }
    
    /**
     * Get plant suggestions for autocomplete
     */
    const getSuggestions = debounce(async function(query, input) {
        if (query.length < 2) return;
        
        const cacheKey = `suggestions_${query}`;
        
        // Check cache first
        if (cache.has(cacheKey)) {
            const cachedData = cache.get(cacheKey);
            if (Date.now() - cachedData.timestamp < CONFIG.cacheTimeout) {
                createAutocompleteDropdown(input, cachedData.data);
                return;
            }
            cache.delete(cacheKey);
        }
        
        try {
            const response = await apiRequest(
                `${CONFIG.apiUrls.plantSuggestions}?q=${encodeURIComponent(query)}&limit=${CONFIG.suggestionLimit}`
            );
            
            if (response.success) {
                cache.set(cacheKey, {
                    data: response.suggestions,
                    timestamp: Date.now()
                });
                createAutocompleteDropdown(input, response.suggestions);
            }
        } catch (error) {
            console.error('Failed to get plant suggestions:', error);
        }
    }, CONFIG.debounceDelay);
    
    /**
     * Auto-populate block fields
     */
    async function autoPopulateFields(plantName, blockType, blockContainer) {
        if (!plantName.trim()) return;
        
        const loadingIndicator = showLoadingIndicator(
            blockContainer.querySelector(`[name*="${blockType === 'plant_spotlight' ? 'plant_name' : 'care_title'}"]`)
        );
        
        try {
            const response = await apiRequest(CONFIG.apiUrls.plantLookup, {
                method: 'POST',
                body: JSON.stringify({
                    query: plantName,
                    block_type: blockType
                })
            });
            
            removeLoadingIndicator();
            
            if (response.success) {
                populateBlockFields(response.fields, response.source, blockContainer);
                showPopulationSuccess(blockContainer, response.source, response.confidence);
            } else {
                showPopulationError(blockContainer, response.error || 'Plant not found');
            }
        } catch (error) {
            removeLoadingIndicator();
            showPopulationError(blockContainer, 'Failed to fetch plant data');
            console.error('Auto-population error:', error);
        }
    }
    
    /**
     * Populate block fields with data
     */
    function populateBlockFields(fields, source, blockContainer) {
        Object.entries(fields).forEach(([fieldName, value]) => {
            if (!value) return;
            
            const input = blockContainer.querySelector(`[name*="${fieldName}"]`);
            if (input) {
                if (input.tagName === 'SELECT') {
                    // Handle select fields
                    const option = input.querySelector(`option[value="${value}"]`);
                    if (option) {
                        input.value = value;
                    }
                } else if (input.tagName === 'TEXTAREA' || input.type === 'text') {
                    // Only populate if field is empty
                    if (!input.value.trim()) {
                        input.value = value;
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
                
                // Add visual indicator that field was auto-populated
                input.style.backgroundColor = '#f0f8f0';
                setTimeout(() => {
                    input.style.backgroundColor = '';
                }, 2000);
            }
        });
    }
    
    /**
     * Show success message
     */
    function showPopulationSuccess(container, source, confidence) {
        const message = document.createElement('div');
        message.className = 'plant-population-success';
        message.innerHTML = `
            ✅ Auto-populated from ${source} 
            ${confidence ? `(${Math.round(confidence * 100)}% confidence)` : ''}
        `;
        message.style.cssText = `
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
            padding: 8px 12px;
            margin: 8px 0;
            border-radius: 4px;
            font-size: 12px;
        `;
        
        container.insertBefore(message, container.firstChild);
        
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 300);
        }, 5000);
    }
    
    /**
     * Show error message
     */
    function showPopulationError(container, error) {
        const message = document.createElement('div');
        message.className = 'plant-population-error';
        message.innerHTML = `❌ ${error}`;
        message.style.cssText = `
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
            padding: 8px 12px;
            margin: 8px 0;
            border-radius: 4px;
            font-size: 12px;
        `;
        
        container.insertBefore(message, container.firstChild);
        
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 300);
        }, 5000);
    }
    
    /**
     * Initialize auto-population for a specific block
     */
    function initializeBlock(blockContainer, blockType) {
        let triggerField;
        
        if (blockType === 'plant_spotlight') {
            triggerField = blockContainer.querySelector('[name*="scientific_name"]') || 
                          blockContainer.querySelector('[name*="plant_name"]');
        } else if (blockType === 'care_instructions') {
            triggerField = blockContainer.querySelector('[name*="care_title"]');
        }
        
        if (!triggerField) return;
        
        // Add autocomplete functionality
        triggerField.addEventListener('input', (e) => {
            getSuggestions(e.target.value, e.target);
        });
        
        // Add auto-population on blur
        triggerField.addEventListener('blur', (e) => {
            const plantName = e.target.value.trim();
            if (plantName) {
                setTimeout(() => {
                    autoPopulateFields(plantName, blockType, blockContainer);
                }, 100);
            }
        });
        
        // Add visual indicator for auto-population capability
        triggerField.style.borderLeft = '3px solid #28a745';
        triggerField.title = 'This field supports auto-population. Type a plant name and press tab/click elsewhere.';
    }
    
    /**
     * Main initialization function
     */
    function initPlantBlockAutopopulation() {
        // Wait for Wagtail admin to be ready
        if (typeof $ === 'undefined' || typeof window.wagtail === 'undefined') {
            setTimeout(initPlantBlockAutopopulation, 500);
            return;
        }
        
        // Initialize existing blocks
        document.querySelectorAll('[data-streamfield-stream-container]').forEach(container => {
            const plantSpotlights = container.querySelectorAll('[data-contentpath*="plant_spotlight"]');
            const careInstructions = container.querySelectorAll('[data-contentpath*="care_instructions"]');
            
            plantSpotlights.forEach(block => initializeBlock(block, 'plant_spotlight'));
            careInstructions.forEach(block => initializeBlock(block, 'care_instructions'));
        });
        
        // Watch for new blocks being added
        if (window.MutationObserver) {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    mutation.addedNodes.forEach((node) => {
                        if (node.nodeType === 1) { // Element node
                            // Check if it's a plant spotlight block
                            const plantSpotlights = node.querySelectorAll ? 
                                node.querySelectorAll('[data-contentpath*="plant_spotlight"]') : [];
                            const careInstructions = node.querySelectorAll ? 
                                node.querySelectorAll('[data-contentpath*="care_instructions"]') : [];
                            
                            plantSpotlights.forEach(block => initializeBlock(block, 'plant_spotlight'));
                            careInstructions.forEach(block => initializeBlock(block, 'care_instructions'));
                            
                            // Also check the node itself
                            if (node.getAttribute && node.getAttribute('data-contentpath')) {
                                if (node.getAttribute('data-contentpath').includes('plant_spotlight')) {
                                    initializeBlock(node, 'plant_spotlight');
                                } else if (node.getAttribute('data-contentpath').includes('care_instructions')) {
                                    initializeBlock(node, 'care_instructions');
                                }
                            }
                        }
                    });
                });
            });
            
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        }
        
        console.log('Plant Block Auto-population initialized');
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPlantBlockAutopopulation);
    } else {
        initPlantBlockAutopopulation();
    }
    
})();