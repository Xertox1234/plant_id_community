from django.apps import AppConfig


class ForumHostAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.forum_host"
    label = "forum_host"
    verbose_name = "Forum Host Integration"

    def ready(self):
        from .bootstrap import connect

        connect()
        # Register the H15 similar-topics vector index so `rebuild_indexes` and
        # the endpoint can find it. django-ai-core has no autodiscovery — an
        # index exists only once its module is imported. Import-safe: the module
        # builds no embedding transformer / hits no DB at import (see its
        # docstring), so this is inert until the feature is enabled + rebuilt.
        from . import signals  # noqa: F401  (registers signal receivers)
        from . import vector_indexes  # noqa: F401
