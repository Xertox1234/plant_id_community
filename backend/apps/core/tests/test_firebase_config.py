"""Tests for the lazy Firebase Admin SDK bootstrap (apps/core/firebase_config).

Only the initialization-arbitration logic is exercised — real Firebase I/O is
mocked. Added with todo 253 slice 6, when FIREBASE_CREDENTIALS_PATH became a
real (optional) Django setting and the forum push pipeline started depending
on this module outside tests.
"""

from unittest.mock import MagicMock, patch

import firebase_admin
from apps.core import constants, firebase_config
from django.test import override_settings


def setup_function():
    firebase_config.reset_firebase()


def teardown_function():
    firebase_config.reset_firebase()


@override_settings(FIREBASE_CREDENTIALS_PATH="/tmp/creds.json")
def test_initialize_firebase_reuses_existing_default_app():
    # apps/users' Firebase ID-token exchange initializes the default app via
    # ADC; a second initialize_app() raises ValueError ("already exists"),
    # which the broad except used to swallow into False — silently killing
    # the push pipeline whenever auth had initialized Firebase first.
    existing_app = MagicMock(name="existing-default-app")
    with patch("firebase_admin.get_app", return_value=existing_app), patch(
        "firebase_admin.initialize_app"
    ) as mock_init:
        assert firebase_config.initialize_firebase() is True

    mock_init.assert_not_called()


@override_settings(FIREBASE_CREDENTIALS_PATH="/tmp/creds.json")
def test_initialize_firebase_inits_from_credentials_path_when_no_app():
    with patch(
        "firebase_admin.get_app", side_effect=ValueError("no default app")
    ), patch("firebase_admin.credentials.Certificate") as mock_cert, patch(
        "firebase_admin.initialize_app"
    ) as mock_init:
        assert firebase_config.initialize_firebase() is True

    mock_cert.assert_called_once_with("/tmp/creds.json")
    # With the app options since todo 727 (the SDK's HTTP timeout).
    mock_init.assert_called_once_with(
        mock_cert.return_value, options=firebase_config.firebase_app_options()
    )


@override_settings(FIREBASE_CREDENTIALS_PATH=None)
def test_initialize_firebase_returns_false_when_path_unset():
    assert firebase_config.initialize_firebase() is False


@override_settings(FIREBASE_CREDENTIALS_PATH="/tmp/creds.json")
def test_initialize_firebase_adopts_winner_on_concurrent_init_race():
    # Threaded runserver: two first-touch requests can both miss get_app()
    # and both call initialize_app(); the loser's ValueError must adopt the
    # winner's app, not report Firebase unavailable (one dropped push /
    # 500'd login per process warm-up otherwise) — slice-6 review.
    winner_app = MagicMock(name="winner-app")
    with patch(
        "firebase_admin.get_app",
        side_effect=[ValueError("no default app"), winner_app],
    ), patch("firebase_admin.credentials.Certificate"), patch(
        "firebase_admin.initialize_app",
        side_effect=ValueError("The default Firebase app already exists."),
    ):
        assert firebase_config.initialize_firebase() is True

    assert firebase_config._firebase_app is winner_app


class _OfflineCredential(firebase_admin.credentials.Base):
    """A credential the SDK accepts at ``initialize_app`` and never uses:
    initialization makes no network call."""

    def get_credential(self):
        return None


@override_settings(FIREBASE_CREDENTIALS_PATH="/tmp/creds.json")
def test_the_firebase_app_is_initialized_with_an_http_timeout_below_the_soft_limit():
    """Todo 727: the SDK's HTTP client defaults to 120 s, longer than a
    task's soft time limit, so one hung FCM send could outlast it. The option
    is read from the REAL initialized app, the object ``messaging`` reads it
    from (``app.options.get("httpTimeout")``)."""
    from apps.forum_host import constants as forum_constants
    from django.conf import settings

    with patch(
        "firebase_admin.credentials.Certificate", return_value=_OfflineCredential()
    ):
        assert firebase_config.initialize_firebase() is True

    timeout = firebase_admin.get_app().options.get("httpTimeout")
    assert timeout == constants.FIREBASE_HTTP_TIMEOUT_SECONDS == 30
    # Below both soft limits a send can run under: the batch tasks' own and
    # the global one the single-recipient push task inherits.
    assert timeout < forum_constants.NOTIFICATION_BATCH_SOFT_TIME_LIMIT
    assert timeout < settings.CELERY_TASK_SOFT_TIME_LIMIT


def test_the_verify_only_fallback_app_carries_the_same_http_timeout():
    """apps/users' projectId-only init (the auth-emulator loop) is adopted by
    the FCM sender when it runs first, so it sets the timeout too."""
    options = firebase_config.firebase_app_options(projectId="demo-project")

    assert options == {
        "httpTimeout": constants.FIREBASE_HTTP_TIMEOUT_SECONDS,
        "projectId": "demo-project",
    }
    firebase_admin.initialize_app(_OfflineCredential(), options=options)
    assert firebase_admin.get_app().options.get("httpTimeout") == 30
    assert firebase_admin.get_app().project_id == "demo-project"
    # The FCM service builds its HTTP client from that option.
    from firebase_admin import messaging

    service = messaging._get_messaging_service(firebase_admin.get_app())
    assert service._client.timeout == 30
