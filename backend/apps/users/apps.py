from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
    
    def ready(self):
        """Import signals and audit log registration when the app is ready."""
        import apps.users.signals

        # Register audit log only if auditlog app is installed and migrated
        # This prevents RuntimeError during initial migrations
        from django.conf import settings
        if 'auditlog' in settings.INSTALLED_APPS:
            try:
                import apps.users.auditlog  # noqa: F401 - Register models for audit trail (GDPR compliance)
            except RuntimeError:
                # Auditlog models not yet migrated - registration will happen after migrate
                pass
