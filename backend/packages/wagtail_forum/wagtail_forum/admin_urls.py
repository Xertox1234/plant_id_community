"""Admin URL patterns the package mounts via the ``register_admin_urls`` hook
(see ``wagtail_hooks.py``). Namespaced like Wagtail's own
``wagtailadmin_reports`` so the report view's ``index_url_name`` and the
Reports menu item resolve with ``reverse()`` under any admin mount.
"""

from django.urls import path

from .admin_views import ModerationQueueView

app_name = "wagtail_forum_reports"
urlpatterns = [
    path("moderation-queue/", ModerationQueueView.as_view(), name="moderation_queue"),
    path(
        "moderation-queue/results/",
        ModerationQueueView.as_view(results_only=True),
        name="moderation_queue_results",
    ),
]
