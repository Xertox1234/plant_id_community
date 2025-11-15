from django.apps import AppConfig


class GardenConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.garden'
    verbose_name = 'Garden Planner'

    def ready(self):
        """Import signal handlers when app is ready."""
        import apps.garden.signals  # noqa: F401
