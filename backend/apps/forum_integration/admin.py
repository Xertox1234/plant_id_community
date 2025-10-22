"""
Admin configuration for Forum Integration models.
"""

from django.contrib import admin
from .models import ForumPageMapping


@admin.register(ForumPageMapping)
class ForumPageMappingAdmin(admin.ModelAdmin):
    """Admin for Forum Page Mappings."""
    
    list_display = (
        'wagtail_page_title', 'machina_forum_name', 'is_active', 
        'created_at', 'updated_at'
    )
    
    list_filter = ('is_active', 'created_at', 'updated_at')
    
    search_fields = (
        'wagtail_page__title', 'machina_forum__name'
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Mapping Configuration', {
            'fields': ('wagtail_page', 'machina_forum', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def wagtail_page_title(self, obj):
        """Display Wagtail page title."""
        return obj.wagtail_page.title
    wagtail_page_title.short_description = "Wagtail Page"
    
    def machina_forum_name(self, obj):
        """Display Machina forum name."""
        return obj.machina_forum.name
    machina_forum_name.short_description = "Machina Forum"