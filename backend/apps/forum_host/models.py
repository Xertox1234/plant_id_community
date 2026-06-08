# forum_host has no models of its own. This module exists so Django's
# emit_post_migrate_signal() sends post_migrate for this app (it skips app
# configs whose models_module is None), which is how bootstrap.py's receiver
# fires — after wagtail_forum is migrated and its permissions exist.
