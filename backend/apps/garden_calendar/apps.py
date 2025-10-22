"""
Garden Calendar Django App Configuration.

This app handles community events, seasonal templates, location-based features,
and weather integration for the Plant Community calendar system.
"""

from django.apps import AppConfig


class GardenCalendarConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.garden_calendar'
    verbose_name = 'Garden Calendar'
    
    def ready(self):
        """
        Import signals when Django starts.
        """
        try:
            from . import signals  # noqa F401
        except ImportError:
            pass