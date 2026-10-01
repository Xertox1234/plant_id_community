"""Shared fixtures for the ``wagtail_forum`` package tests.

The package tests run inside the host project's settings, so whatever
override providers the host registered at ``AppConfig.ready()`` are live
during them. This host's provider (``apps.forum_host.forum_settings.provide``)
answers from a process-level memo and, when that memo is cold, loads it with a
SELECT. A test without database access that reaches ``get_setting`` for a
mapped name — the heuristic spam check reads two — then fails with "Database
access not allowed" when its file runs alone, and passes in the full suite
only because an earlier DB test warmed the memo (todo 501). The memo can also
carry values from a host test whose ``ForumSettings`` row was rolled back.

The package cannot know about a host's storage, and none of its tests create
host override rows, so its tests resolve settings without host providers:
``get_setting`` goes straight to the ``WAGTAILFORUM_<NAME>`` Django setting,
then the package default. ``test_conf`` still registers its own providers on
top of the emptied list. The list is restored in place after every test, so
host tests that run later in the same process see their provider again.
"""

import pytest
from wagtail_forum import conf


@pytest.fixture(autouse=True)
def _without_host_override_providers():
    saved = list(conf._override_providers)
    conf._override_providers.clear()
    try:
        yield
    finally:
        conf._override_providers[:] = saved
