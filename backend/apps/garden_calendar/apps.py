"""
Garden Calendar Django App Configuration.

This app handles community events, seasonal templates, location-based features,
and weather integration for the Plant Community calendar system.
"""

from django.apps import AppConfig


class GardenCalendarConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.garden_calendar"
    verbose_name = "Garden Calendar"

    def ready(self):
        """Import signals and audit log registration when Django starts."""
        try:
            from . import signals  # noqa F401
        except ImportError:
            pass

        # Register the garden models for the audit trail, the way the users and
        # plant_identification apps do. Until todo 571 nothing imported this
        # module, so no garden model ever wrote a LogEntry.
        from django.conf import settings

        if "auditlog" in settings.INSTALLED_APPS:
            try:
                import apps.garden_calendar.auditlog  # noqa: F401
            except RuntimeError:
                # Auditlog models not yet migrated; registration happens after migrate
                pass
