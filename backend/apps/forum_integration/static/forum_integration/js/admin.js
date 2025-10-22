/*
Forum Integration Admin JavaScript
Custom JavaScript for Wagtail admin forum integration
*/

document.addEventListener('DOMContentLoaded', function() {
    // Initialize forum admin functionality
    initForumAdmin();
});

function initForumAdmin() {
    // Add forum-specific CSS classes
    document.body.classList.add('forum-integration');
    
    // Initialize quick actions
    initQuickActions();
    
    // Initialize forum statistics updates
    initForumStats();
    
    // Initialize forum mapping management
    initForumMappings();
    
    // Initialize moderation tools
    initModerationTools();
}

// Quick Actions Panel
function initQuickActions() {
    const quickActionsHTML = `
        <div class="forum-quick-actions" id="forum-quick-actions">
            <h4>🌱 Forum Quick Actions</h4>
            <a href="/forum/" class="quick-action" target="_blank">
                View Live Forum
            </a>
            <a href="/forum/moderation/" class="quick-action" target="_blank">
                Moderation Queue
            </a>
            <a href="/cms/pages/" class="quick-action">
                Manage Forum Pages
            </a>
            <button class="quick-action" onclick="refreshForumStats()">
                Refresh Statistics
            </button>
            <button class="quick-action" onclick="toggleQuickActions()">
                Hide Quick Actions
            </button>
        </div>
    `;
    
    // Only add quick actions on forum-related pages
    if (isForumPage()) {
        document.body.insertAdjacentHTML('beforeend', quickActionsHTML);
    }
}

function isForumPage() {
    const path = window.location.pathname;
    return path.includes('forum') || 
           document.querySelector('[data-forum-page]') !== null ||
           document.title.toLowerCase().includes('forum');
}

function toggleQuickActions() {
    const panel = document.getElementById('forum-quick-actions');
    if (panel) {
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    }
}

// Forum Statistics
function initForumStats() {
    // Auto-refresh forum stats every 5 minutes
    setInterval(refreshForumStats, 5 * 60 * 1000);
    
    // Add click handlers for stat cards
    document.querySelectorAll('.forum-stat-card').forEach(card => {
        card.addEventListener('click', function() {
            const url = this.dataset.url;
            if (url) {
                window.location.href = url;
            }
        });
        
        card.style.cursor = 'pointer';
    });
}

function refreshForumStats() {
    const statsElements = document.querySelectorAll('[data-forum-stat]');
    
    if (statsElements.length === 0) return;
    
    // Show loading indicators
    statsElements.forEach(el => {
        el.classList.add('loading');
        el.innerHTML = '<span class="forum-loading"></span>';
    });
    
    // Fetch updated stats
    fetch('/admin/forum-stats-api/', {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        updateForumStats(data);
    })
    .catch(error => {
        console.error('Error refreshing forum stats:', error);
        // Remove loading indicators
        statsElements.forEach(el => {
            el.classList.remove('loading');
        });
    });
}

function updateForumStats(data) {
    // Update individual stat elements
    Object.keys(data).forEach(key => {
        const element = document.querySelector(`[data-forum-stat="${key}"]`);
        if (element) {
            element.textContent = data[key];
            element.classList.remove('loading');
            element.classList.add('fade-in');
        }
    });
    
    // Update timestamp
    const timestamp = document.getElementById('stats-timestamp');
    if (timestamp) {
        timestamp.textContent = new Date().toLocaleTimeString();
    }
}

// Forum Page Mappings
function initForumMappings() {
    const mappingItems = document.querySelectorAll('.mapping-item');
    
    mappingItems.forEach(item => {
        // Add toggle functionality for inactive mappings
        const toggleBtn = item.querySelector('.toggle-mapping');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', function(e) {
                e.preventDefault();
                toggleForumMapping(this.dataset.mappingId);
            });
        }
        
        // Add edit functionality
        const editBtn = item.querySelector('.edit-mapping');
        if (editBtn) {
            editBtn.addEventListener('click', function(e) {
                e.preventDefault();
                editForumMapping(this.dataset.mappingId);
            });
        }
    });
}

function toggleForumMapping(mappingId) {
    fetch(`/admin/forum-mapping/${mappingId}/toggle/`, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update UI
            const item = document.querySelector(`[data-mapping="${mappingId}"]`);
            if (item) {
                if (data.is_active) {
                    item.classList.remove('inactive');
                } else {
                    item.classList.add('inactive');
                }
            }
            
            showNotification(data.message, 'success');
        } else {
            showNotification(data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error toggling mapping:', error);
        showNotification('Error updating forum mapping', 'error');
    });
}

// Moderation Tools
function initModerationTools() {
    // Add moderation shortcuts
    document.addEventListener('keydown', function(e) {
        // Alt + M: Quick moderation
        if (e.altKey && e.key === 'm') {
            e.preventDefault();
            window.open('/forum/moderation/', '_blank');
        }
        
        // Alt + F: Quick forum view
        if (e.altKey && e.key === 'f') {
            e.preventDefault();
            window.open('/forum/', '_blank');
        }
    });
    
    // Initialize bulk moderation actions
    const bulkActions = document.getElementById('bulk-moderation-actions');
    if (bulkActions) {
        initBulkModeration();
    }
}

function initBulkModeration() {
    const selectAllBtn = document.getElementById('select-all-posts');
    const moderationForm = document.getElementById('bulk-moderation-form');
    
    if (selectAllBtn) {
        selectAllBtn.addEventListener('change', function() {
            const checkboxes = document.querySelectorAll('input[name="selected_posts"]');
            checkboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
        });
    }
    
    if (moderationForm) {
        moderationForm.addEventListener('submit', function(e) {
            const selectedPosts = document.querySelectorAll('input[name="selected_posts"]:checked');
            
            if (selectedPosts.length === 0) {
                e.preventDefault();
                showNotification('Please select at least one post', 'warning');
                return false;
            }
            
            const action = document.querySelector('select[name="action"]').value;
            if (!action) {
                e.preventDefault();
                showNotification('Please select an action', 'warning');
                return false;
            }
            
            if (!confirm(`Are you sure you want to ${action} ${selectedPosts.length} post(s)?`)) {
                e.preventDefault();
                return false;
            }
        });
    }
}

// Utility Functions
function getCSRFToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrftoken') {
            return value;
        }
    }
    
    // Fallback: try to get from meta tag
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    return csrfMeta ? csrfMeta.getAttribute('content') : '';
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `forum-notification notification-${type}`;
    notification.innerHTML = `
        <span class="notification-message">${message}</span>
        <button class="notification-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
    
    // Add animation
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);
}

// Forum Page Enhancement
function enhanceForumPages() {
    // Add plant-themed icons to forum categories
    const categoryIcons = {
        'plant-identification': '🔍',
        'plant-care-growing': '🌱',
        'indoor-plants': '🏠',
        'outdoor-gardening': '🌻',
        'plant-diseases-pests': '🐛',
        'seeds-propagation': '🌱',
        'garden-design': '🎨',
        'plant-photography': '📸',
        'community-trading': '💰',
        'general-discussion': '💬'
    };
    
    Object.keys(categoryIcons).forEach(category => {
        const elements = document.querySelectorAll(`[data-category="${category}"]`);
        elements.forEach(element => {
            const icon = document.createElement('span');
            icon.className = 'category-icon';
            icon.textContent = categoryIcons[category];
            element.prepend(icon);
        });
    });
}

// Auto-save functionality for forum settings
function initAutoSave() {
    const forms = document.querySelectorAll('.forum-settings-form');
    
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input, textarea, select');
        
        inputs.forEach(input => {
            input.addEventListener('change', function() {
                autoSaveFormData(form);
            });
        });
    });
}

function autoSaveFormData(form) {
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    
    // Save to localStorage as backup
    localStorage.setItem('forum_settings_backup', JSON.stringify(data));
    
    // Optional: Send to server for auto-save
    fetch(form.action, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCSRFToken()
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Settings auto-saved', 'success');
        }
    })
    .catch(error => {
        console.error('Auto-save error:', error);
    });
}

// Initialize additional features when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    enhanceForumPages();
    initAutoSave();
    
    // Add custom CSS for forum theme
    const style = document.createElement('style');
    style.textContent = `
        .forum-notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            border: 1px solid #e0e6ed;
            border-radius: 6px;
            padding: 15px 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 10000;
            transform: translateX(400px);
            transition: transform 0.3s ease;
            min-width: 300px;
        }
        
        .forum-notification.show {
            transform: translateX(0);
        }
        
        .forum-notification.notification-success {
            border-left: 4px solid #28a745;
        }
        
        .forum-notification.notification-error {
            border-left: 4px solid #dc3545;
        }
        
        .forum-notification.notification-warning {
            border-left: 4px solid #ffc107;
        }
        
        .notification-close {
            position: absolute;
            top: 10px;
            right: 10px;
            background: none;
            border: none;
            font-size: 18px;
            cursor: pointer;
            color: #999;
        }
        
        .notification-close:hover {
            color: #333;
        }
        
        .category-icon {
            margin-right: 8px;
            font-size: 1.2em;
        }
    `;
    document.head.appendChild(style);
});

// Export functions for external use
window.forumAdmin = {
    refreshForumStats,
    toggleQuickActions,
    showNotification,
    toggleForumMapping
};