"""Regression test: project loggers must not double-emit through root.

`settings.LOGGING` attaches the same handlers (`console`/`console_prod`) to the
`django`, `apps`, and `plant_community_backend` loggers AND to `root`. If one of
those loggers also propagates to `root`, every record it handles is emitted
twice. The `django` logger was missing `propagate=False` (fixed 2026-06-06),
so all `django.*` records (request/server/security/db) double-logged in prod.

This lives in `apps.blog.tests` (not forum) because the logging config is global
and blog is always installed + run by CI's pytest (forum tests are ignored).
"""

import logging

from django.test import SimpleTestCase


class LoggerPropagationTests(SimpleTestCase):
    def test_project_loggers_do_not_propagate_to_root(self):
        # Each carries its own handlers; propagating to root (same handlers)
        # would double every record.
        for name in ("django", "apps", "plant_community_backend"):
            with self.subTest(logger=name):
                self.assertFalse(
                    logging.getLogger(name).propagate,
                    f"{name} logger must set propagate=False, or its records "
                    f"double-emit via root (which carries the same handlers).",
                )
