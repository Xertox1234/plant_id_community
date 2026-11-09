"""Erasing a deleted account's Firestore data and Firebase login (Plan B, task 4)."""

from unittest.mock import MagicMock, patch

import pytest
from apps.users.constants import (
    DELETED_ACCOUNT_REASON_SELF,
    ERASE_STEP_FIREBASE_AUTH,
    ERASE_STEP_FIRESTORE,
)
from apps.users.deletion import email_hash, erase_firebase_data
from apps.users.models import DeletedAccount
from firebase_admin import auth

pytestmark = pytest.mark.django_db

UID = "firebase-uid-123"


@pytest.fixture
def record():
    return DeletedAccount.objects.create(
        user_id=None,
        email="gone@example.test",
        email_hash=email_hash("gone@example.test"),
        reason=DELETED_ACCOUNT_REASON_SELF,
        firebase_uid=UID,
    )


@pytest.fixture
def calls():
    """Mocked Firestore client and ``auth.delete_user`` sharing one call log."""
    manager = MagicMock()
    client = manager.client
    with (
        patch("apps.users.deletion.initialize_firebase", return_value=True),
        patch("apps.users.deletion.get_firestore_client", return_value=client),
        patch("firebase_admin.auth.delete_user", manager.delete_user),
    ):
        yield manager


def test_deletes_firestore_tree_then_login(record, calls):
    erase_firebase_data(record)

    user_doc = calls.client.collection.return_value.document.return_value
    calls.client.collection.assert_called_once_with("users")
    calls.client.collection.return_value.document.assert_called_once_with(UID)
    names = [
        c[0]
        for c in calls.mock_calls
        if c[0] in ("client.recursive_delete", "delete_user")
    ]
    assert names == ["client.recursive_delete", "delete_user"]
    calls.client.recursive_delete.assert_called_once_with(user_doc)
    calls.delete_user.assert_called_once_with(UID)
    record.refresh_from_db()
    assert record.steps_done == [ERASE_STEP_FIRESTORE, ERASE_STEP_FIREBASE_AUTH]


def test_user_not_found_counts_as_done(record, calls):
    calls.delete_user.side_effect = auth.UserNotFoundError("gone")

    erase_firebase_data(record)

    record.refresh_from_db()
    assert record.steps_done == [ERASE_STEP_FIRESTORE, ERASE_STEP_FIREBASE_AUTH]


def test_no_uid_marks_both_done_without_calls(record, calls):
    record.firebase_uid = ""
    record.save(update_fields=["firebase_uid"])

    erase_firebase_data(record)

    calls.client.recursive_delete.assert_not_called()
    calls.delete_user.assert_not_called()
    record.refresh_from_db()
    assert record.steps_done == [ERASE_STEP_FIRESTORE, ERASE_STEP_FIREBASE_AUTH]


def test_no_uid_needs_no_firebase_config(record):
    record.firebase_uid = ""
    record.save(update_fields=["firebase_uid"])
    with patch("apps.users.deletion.initialize_firebase", return_value=False):
        erase_firebase_data(record)
    record.refresh_from_db()
    assert record.steps_done == [ERASE_STEP_FIRESTORE, ERASE_STEP_FIREBASE_AUTH]


def test_a_finished_firestore_step_is_not_repeated(record, calls):
    record.steps_done = [ERASE_STEP_FIRESTORE]
    record.save(update_fields=["steps_done"])

    erase_firebase_data(record)

    calls.client.recursive_delete.assert_not_called()
    calls.delete_user.assert_called_once_with(UID)
    record.refresh_from_db()
    assert record.steps_done == [ERASE_STEP_FIRESTORE, ERASE_STEP_FIREBASE_AUTH]


def test_unconfigured_firebase_raises(record):
    with (
        patch("apps.users.deletion.initialize_firebase", return_value=False),
        patch("apps.users.deletion.get_firestore_client", return_value=None),
        patch("firebase_admin.auth.delete_user") as delete_user,
    ):
        with pytest.raises(RuntimeError, match="Firebase"):
            erase_firebase_data(record)
    delete_user.assert_not_called()
    record.refresh_from_db()
    assert record.steps_done == []


def test_unconfigured_firebase_raises_for_the_auth_step_too(record):
    record.steps_done = [ERASE_STEP_FIRESTORE]
    record.save(update_fields=["steps_done"])
    with (
        patch("apps.users.deletion.initialize_firebase", return_value=False),
        patch("firebase_admin.auth.delete_user") as delete_user,
    ):
        with pytest.raises(RuntimeError, match="Firebase"):
            erase_firebase_data(record)
    delete_user.assert_not_called()


def test_a_failed_firestore_delete_is_not_recorded_and_retries(record, calls):
    calls.client.recursive_delete.side_effect = [RuntimeError("boom"), None]

    with pytest.raises(RuntimeError, match="boom"):
        erase_firebase_data(record)
    record.refresh_from_db()
    assert record.steps_done == []
    calls.delete_user.assert_not_called()

    erase_firebase_data(record)
    record.refresh_from_db()
    assert record.steps_done == [ERASE_STEP_FIRESTORE, ERASE_STEP_FIREBASE_AUTH]
    assert calls.client.recursive_delete.call_count == 2
