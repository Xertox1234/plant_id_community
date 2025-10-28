from django.apps import AppConfig


class PlantIdentificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.plant_identification'

    def ready(self):
        """Import audit log registration when the app is ready."""
        # Register audit log only if auditlog app is installed and migrated
        # This prevents RuntimeError during initial migrations
        from django.conf import settings
        if 'auditlog' in settings.INSTALLED_APPS:
            try:
                import apps.plant_identification.auditlog  # Register models for audit trail (GDPR compliance)  # noqa: F401
            except RuntimeError:
                # Auditlog models not yet migrated - registration will happen after migrate
                pass
