from django.apps import AppConfig


class BlogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.blog'

    def ready(self):
        """
        Import signal handlers when app is ready.

        This ensures signals are registered after all apps are loaded,
        preventing import order issues and circular dependencies.

        Registered signals:
        - page_published: Invalidate cache on blog post publish
        - page_unpublished: Invalidate cache on blog post unpublish
        - post_delete: Invalidate cache on blog post deletion
        """
        # Import signals module to register handlers
        # This must be done in ready() to avoid AppRegistryNotReady errors
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
