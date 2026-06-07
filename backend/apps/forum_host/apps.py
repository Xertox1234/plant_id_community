from django.apps import AppConfig


class ForumHostAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.forum_host"
    label = "forum_host"
    verbose_name = "Forum Host Integration"

    def ready(self):
        from .bootstrap import connect

        connect()
        from . import signals  # noqa: F401  (registers signal receivers)
