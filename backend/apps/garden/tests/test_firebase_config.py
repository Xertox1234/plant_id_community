"""Tests for the lazy Firebase Admin SDK bootstrap (apps/garden/firebase_config).

Only the initialization-arbitration logic is exercised — real Firebase I/O is
mocked. Added with todo 253 slice 6, when FIREBASE_CREDENTIALS_PATH became a
real (optional) Django setting and the forum push pipeline started depending
on this module outside tests.
"""

from unittest.mock import MagicMock, patch

from apps.garden import firebase_config
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
    mock_init.assert_called_once_with(mock_cert.return_value)


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
