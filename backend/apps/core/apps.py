from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        from . import checks  # noqa: F401  (registers core.E364)
        from .django70_compat import install

        install()  # todo 452: taggit + Wagtail mail shims for Django 7.0
