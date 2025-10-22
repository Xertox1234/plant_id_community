"""
Admin configuration for search models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import SearchQuery, UserSearchPreferences, SavedSearch, SearchResultClick


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    """Admin interface for search queries."""
    
    list_display = [
        'query_text_short', 'content_type', 'user_link', 'results_count', 
        'response_time_ms', 'created_at'
    ]
    list_filter = [
        'content_type', 'created_at', 'results_count'
    ]
    search_fields = [
        'query_text', 'user__username', 'user__email'
    ]
    readonly_fields = [
        'uuid', 'query_text', 'content_type', 'user', 'session_key',
        'results_count', 'response_time_ms', 'filters_applied', 'created_at'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    def query_text_short(self, obj):
        """Return shortened query text."""
        if len(obj.query_text) > 50:
            return obj.query_text[:50] + '...'
        return obj.query_text
    query_text_short.short_description = 'Query'
    
    def user_link(self, obj):
        """Return link to user admin page."""
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return 'Anonymous'
    user_link.short_description = 'User'
    
    def has_add_permission(self, request):
        """Disable adding search queries through admin."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable changing search queries through admin."""
        return False


@admin.register(UserSearchPreferences)
class UserSearchPreferencesAdmin(admin.ModelAdmin):
    """Admin interface for user search preferences."""
    
    list_display = [
        'user_link', 'default_content_type', 'results_per_page', 
        'save_search_history', 'enable_personalized_results', 'created_at'
    ]
    list_filter = [
        'default_content_type', 'save_search_history', 'enable_personalized_results',
        'boost_expert_content', 'enable_search_alerts'
    ]
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    def user_link(self, obj):
        """Return link to user admin page."""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'


@admin.register(SavedSearch)
class SavedSearchAdmin(admin.ModelAdmin):
    """Admin interface for saved searches."""
    
    list_display = [
        'name', 'user_link', 'content_type', 'enable_alerts', 
        'times_used', 'last_used', 'is_active', 'created_at'
    ]
    list_filter = [
        'content_type', 'enable_alerts', 'alert_frequency', 'is_active', 'created_at'
    ]
    search_fields = [
        'name', 'query_text', 'user__username', 'user__email'
    ]
    readonly_fields = [
        'times_used', 'last_used', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    
    def user_link(self, obj):
        """Return link to user admin page."""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'


@admin.register(SearchResultClick)
class SearchResultClickAdmin(admin.ModelAdmin):
    """Admin interface for search result clicks."""
    
    list_display = [
        'search_query_short', 'result_type', 'result_id', 'result_position',
        'user_link', 'clicked_at'
    ]
    list_filter = [
        'result_type', 'result_position', 'result_page', 'clicked_at'
    ]
    search_fields = [
        'search_query__query_text', 'result_id', 'user__username'
    ]
    readonly_fields = [
        'search_query', 'result_type', 'result_id', 'result_position',
        'result_page', 'user', 'session_key', 'clicked_at'
    ]
    ordering = ['-clicked_at']
    date_hierarchy = 'clicked_at'
    
    def search_query_short(self, obj):
        """Return shortened search query text."""
        query_text = obj.search_query.query_text
        if len(query_text) > 30:
            return query_text[:30] + '...'
        return query_text
    search_query_short.short_description = 'Search Query'
    
    def user_link(self, obj):
        """Return link to user admin page."""
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return 'Anonymous'
    user_link.short_description = 'User'
    
    def has_add_permission(self, request):
        """Disable adding clicks through admin."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable changing clicks through admin."""
        return False


# Note: SearchQuery is already registered above with SearchQueryAdmin