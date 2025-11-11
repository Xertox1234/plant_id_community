/**
 * Wagtail AI Content Generation Widget (Phase 4: Issue #157)
 *
 * Provides "Generate with AI" buttons for BlogPostPage fields:
 * - Title generation
 * - Introduction generation
 * - Meta description generation
 *
 * Features:
 * - Context-aware prompts (plant species, difficulty level)
 * - Loading states and quota display
 * - Error handling with retry
 * - Caching indicator
 */

(function() {
    'use strict';

    /**
     * AI Widget Configuration
     */
    const CONFIG = {
        apiEndpoint: '/blog-admin/api/generate-field-content/',
        csrfToken: document.querySelector('[name=csrfmiddlewaretoken]')?.value,
        fields: {
            title: {
                selector: '#id_title',
                label: 'Generate Title with AI',
                icon: '✨',
                fieldName: 'title'
            },
            introduction: {
                selector: 'div[data-contentpath="introduction"] iframe',
                label: 'Generate Introduction with AI',
                icon: '✨',
                fieldName: 'introduction'
            },
            meta_description: {
                selector: '#id_search_description',
                label: 'Generate Meta Description with AI',
                icon: '✨',
                fieldName: 'meta_description'
            }
        }
    };

    /**
     * AI Widget Class
     */
    class AIContentWidget {
        constructor(fieldConfig) {
            this.config = fieldConfig;
            this.field = document.querySelector(fieldConfig.selector);
            this.container = null;
            this.button = null;
            this.quotaDisplay = null;
            this.isGenerating = false;
        }

        /**
         * Initialize the widget by creating button and UI elements
         */
        init() {
            if (!this.field) {
                console.warn(`[AI Widget] Field not found: ${this.config.selector}`);
                return;
            }

            this.createButton();
            this.createQuotaDisplay();
            this.attachEventListeners();
            this.loadQuotaInfo();
        }

        /**
         * Create the "Generate with AI" button
         */
        createButton() {
            // Find the field's parent container
            const fieldWrapper = this.field.closest('.field') || this.field.closest('.w-field');
            if (!fieldWrapper) {
                console.warn(`[AI Widget] Field wrapper not found for ${this.config.selector}`);
                return;
            }

            // Create button container
            this.container = document.createElement('div');
            this.container.className = 'ai-widget-container';
            this.container.style.cssText = 'margin-top: 8px; display: flex; align-items: center; gap: 12px;';

            // Create button
            this.button = document.createElement('button');
            this.button.type = 'button';
            this.button.className = 'button button-secondary ai-generate-button';
            this.button.innerHTML = `<span class="icon">${this.config.icon}</span> ${this.config.label}`;
            this.button.style.cssText = 'display: inline-flex; align-items: center; gap: 6px;';

            // Create quota display
            this.quotaDisplay = document.createElement('span');
            this.quotaDisplay.className = 'ai-quota-display';
            this.quotaDisplay.style.cssText = 'font-size: 12px; color: #666;';

            // Append elements
            this.container.appendChild(this.button);
            this.container.appendChild(this.quotaDisplay);

            // Insert after field wrapper
            fieldWrapper.parentNode.insertBefore(this.container, fieldWrapper.nextSibling);
        }

        /**
         * Create quota display element
         */
        createQuotaDisplay() {
            // Already created in createButton()
        }

        /**
         * Attach event listeners
         */
        attachEventListeners() {
            if (!this.button) return;

            this.button.addEventListener('click', () => {
                this.generateContent();
            });
        }

        /**
         * Load quota information from backend
         */
        async loadQuotaInfo() {
            // For now, just show placeholder
            // In full implementation, make API call to get current quota
            this.updateQuotaDisplay(null);
        }

        /**
         * Update quota display with remaining calls
         */
        updateQuotaDisplay(remainingCalls, limit = null) {
            if (!this.quotaDisplay) return;

            if (remainingCalls !== null) {
                const percentage = limit ? (remainingCalls / limit * 100).toFixed(0) : 100;
                const color = percentage > 50 ? '#0ea5e9' : percentage > 20 ? '#f59e0b' : '#ef4444';

                this.quotaDisplay.innerHTML = `
                    <span style="color: ${color};">
                        ${remainingCalls}/${limit || '?'} AI calls remaining
                    </span>
                `;
            } else {
                this.quotaDisplay.textContent = '';
            }
        }

        /**
         * Get context for AI generation from page form
         */
        getContext() {
            const context = {};

            // Get title
            const titleField = document.querySelector('#id_title');
            if (titleField && titleField.value) {
                context.title = titleField.value;
            }

            // Get introduction (from rich text field)
            const introFrame = document.querySelector('div[data-contentpath="introduction"] iframe');
            if (introFrame) {
                try {
                    const introContent = introFrame.contentDocument?.body?.textContent || '';
                    if (introContent) {
                        context.introduction = introContent;
                    }
                } catch (e) {
                    console.warn('[AI Widget] Could not access introduction content:', e);
                }
            }

            // Get difficulty level
            const difficultyField = document.querySelector('#id_difficulty_level');
            if (difficultyField && difficultyField.value) {
                context.difficulty_level = difficultyField.value;
            }

            // Get related plants (if available)
            // This is more complex in Wagtail - would need to parse the chooser widget
            // For now, skip this field

            return context;
        }

        /**
         * Generate AI content
         */
        async generateContent() {
            if (this.isGenerating) {
                console.log('[AI Widget] Generation already in progress');
                return;
            }

            this.isGenerating = true;
            this.setLoadingState(true);

            try {
                // Prepare request data
                const requestData = {
                    field_name: this.config.fieldName,
                    context: this.getContext()
                };

                console.log('[AI Widget] Generating content for:', this.config.fieldName, requestData);

                // Make API request
                const response = await fetch(CONFIG.apiEndpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': CONFIG.csrfToken
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify(requestData)
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || `Server returned ${response.status}`);
                }

                if (data.success) {
                    this.setFieldValue(data.content);
                    this.showSuccess(data.cached);
                    this.updateQuotaDisplay(data.remaining_calls, data.limit);
                } else {
                    throw new Error(data.error || 'Content generation failed');
                }

            } catch (error) {
                console.error('[AI Widget] Generation error:', error);
                this.showError(error.message);
            } finally {
                this.isGenerating = false;
                this.setLoadingState(false);
            }
        }

        /**
         * Set field value with generated content
         */
        setFieldValue(content) {
            if (!this.field) return;

            // Handle different field types
            if (this.field.tagName === 'INPUT' || this.field.tagName === 'TEXTAREA') {
                // Regular input/textarea
                this.field.value = content;
                this.field.dispatchEvent(new Event('input', { bubbles: true }));
                this.field.dispatchEvent(new Event('change', { bubbles: true }));
            } else if (this.field.tagName === 'IFRAME') {
                // Rich text field (Draftail/TinyMCE)
                try {
                    const doc = this.field.contentDocument;
                    if (doc && doc.body) {
                        doc.body.innerHTML = `<p>${content}</p>`;
                        this.field.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                } catch (e) {
                    console.error('[AI Widget] Could not set rich text value:', e);
                    this.showError('Could not update rich text field. Please copy the generated content manually.');
                }
            }
        }

        /**
         * Set loading state
         */
        setLoadingState(isLoading) {
            if (!this.button) return;

            if (isLoading) {
                this.button.disabled = true;
                this.button.innerHTML = `
                    <span class="icon">⏳</span>
                    Generating...
                `;
                this.button.classList.add('button-loading');
            } else {
                this.button.disabled = false;
                this.button.innerHTML = `
                    <span class="icon">${this.config.icon}</span>
                    ${this.config.label}
                `;
                this.button.classList.remove('button-loading');
            }
        }

        /**
         * Show success message
         */
        showSuccess(wasCached) {
            const message = wasCached
                ? '✓ Content generated (from cache)'
                : '✓ Content generated';

            this.showToast(message, 'success');

            // Add highlight animation to field
            if (this.field) {
                this.field.style.transition = 'background-color 0.3s';
                this.field.style.backgroundColor = '#d4edda';
                setTimeout(() => {
                    this.field.style.backgroundColor = '';
                }, 2000);
            }
        }

        /**
         * Show error message
         */
        showError(errorMessage) {
            this.showToast(`✗ ${errorMessage}`, 'error');
        }

        /**
         * Show toast notification
         */
        showToast(message, type = 'info') {
            // Use Wagtail's built-in messages if available
            if (window.wagtail && window.wagtail.messages) {
                window.wagtail.messages.show({
                    text: message,
                    type: type
                });
                return;
            }

            // Fallback: Create custom toast
            const toast = document.createElement('div');
            toast.className = `ai-toast ai-toast-${type}`;
            toast.textContent = message;
            toast.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 12px 16px;
                background: ${type === 'error' ? '#f44336' : type === 'success' ? '#4caf50' : '#2196f3'};
                color: white;
                border-radius: 4px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                z-index: 10000;
                animation: slideIn 0.3s ease-out;
            `;

            document.body.appendChild(toast);

            setTimeout(() => {
                toast.style.animation = 'slideOut 0.3s ease-in';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
    }

    /**
     * Initialize all AI widgets when page loads
     */
    function initializeAIWidgets() {
        console.log('[AI Widget] Initializing AI content generation widgets...');

        // Wait for Wagtail admin to fully load
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initializeAIWidgets);
            return;
        }

        // Create widget for each configured field
        Object.values(CONFIG.fields).forEach(fieldConfig => {
            const widget = new AIContentWidget(fieldConfig);
            widget.init();
        });

        console.log('[AI Widget] Initialization complete');
    }

    // Initialize widgets
    initializeAIWidgets();

    // Re-initialize on Wagtail admin events (for StreamField blocks, etc.)
    document.addEventListener('wagtail:panel-init', initializeAIWidgets);

})();
