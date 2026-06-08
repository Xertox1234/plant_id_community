# wagtail-forum

A reusable, Wagtail-native community forum. Boards are Wagtail Pages; topics and
posts are feature-rich snippets (moderation workflow, revisions, locking, search).
Headless DRF API is optional (`pip install wagtail-forum[api]`).

The core imports nothing host-specific and uses `settings.AUTH_USER_MODEL`.
