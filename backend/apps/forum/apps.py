from django.apps import AppConfig


class ForumConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.forum'
    verbose_name = 'Community Forum'

    def ready(self):
        """
        Register signal handlers when Django app is ready.

        Imports signals module to register signal receivers.
        Follows pattern from apps/blog/apps.py.
        """
        from . import signals  # noqa: F401
