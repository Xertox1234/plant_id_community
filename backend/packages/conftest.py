"""Host-side fixtures for the vendored packages' tests (``packages/*``).

This file belongs to the host, not to a package: ``wagtail_forum`` must not
import ``apps.*`` (``test_reusability.py``), and it cannot know the host's
sign-in rules.

The host's API session authenticator ignores a session whose account has not
accepted the current policy version (todo 701), and a package test's user is
created bare, with no version. The package tests sign in with real sessions
(a forum unlock lives in one), so for them the authenticator is the plain DRF
one. The policy gate itself is tested by the host, in
``apps/users/tests/test_policy_session_paths.py``.
"""

import pytest
from rest_framework.authentication import SessionAuthentication


@pytest.fixture(autouse=True)
def _plain_session_authentication(monkeypatch):
    from apps.users.authentication import PolicyCheckedSessionAuthentication

    monkeypatch.setattr(
        PolicyCheckedSessionAuthentication,
        "authenticate",
        SessionAuthentication.authenticate,
    )
