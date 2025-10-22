"""
Search app configuration.
"""

from django.apps import AppConfig


class SearchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.search'
    verbose_name = 'Advanced Search'
    
    def ready(self):
        """Initialize search functionality when app is ready."""
        from . import signals