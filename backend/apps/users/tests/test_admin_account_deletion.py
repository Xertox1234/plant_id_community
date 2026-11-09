"""Staff account deletion in the admin (Plan B, task 7).

Staff delete accounts through actions that run ``request_account_deletion``
(so the erase job runs), never through the plain delete views. Every
``delay`` here is patched: conftest does not run the task inline.
"""

from unittest.mock import patch

import pytest
from apps.users.constants import (
    DELETED_ACCOUNT_REASON_ABUSE,
    DELETED_ACCOUNT_REASON_SELF,
    DELETED_ACCOUNT_REASON_STAFF,
    DELETED_ACCOUNT_REASON_UNDER_13,
    DELETED_ACCOUNT_STATUS_DONE,
    DELETED_ACCOUNT_STATUS_PENDING,
)
from apps.users.deletion import is_signup_blocked, request_account_deletion
from apps.users.models import DeletedAccount
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

User = get_user_model()

pytestmark = pytest.mark.django_db

PW = "pw-not-used-1234"  # pragma: allowlist secret


@pytest.fixture
def delay():
    with patch("apps.users.tasks.delete_account_task.delay") as m:
        yield m


@pytest.fixture
def admin_client(client):
    root = User.objects.create_superuser("root7", "root7@example.test", PW)
    client.force_login(root)
    return client


@pytest.fixture
def target():
    return User.objects.create_user("target7", "target7@example.test", PW)


def _run_action(client, action, pks):
    return client.post(
        reverse("admin:users_user_changelist"),
        {"action": action, "_selected_action": [str(p) for p in pks]},
        follow=True,
    )


def _messages(response):
    return [str(m) for m in response.context["messages"]]


def test_abuse_action_blocks_resignup(
    admin_client, target, delay, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        resp = _run_action(admin_client, "delete_account_abuse", [target.pk])
    record = DeletedAccount.objects.get(user_id=target.pk)
    assert record.reason == DELETED_ACCOUNT_REASON_ABUSE
    assert is_signup_blocked("target7@example.test")
    delay.assert_called_once_with(record.pk)
    assert "1 account(s) scheduled for deletion (Abuse)." in _messages(resp)


def test_under_13_and_staff_actions_use_their_reason(
    admin_client, delay, django_capture_on_commit_callbacks
):
    a = User.objects.create_user("kid7", "kid7@example.test", PW)
    b = User.objects.create_user("plain7", "plain7@example.test", PW)
    with django_capture_on_commit_callbacks(execute=True):
        _run_action(admin_client, "delete_account_under_13", [a.pk])
        _run_action(admin_client, "delete_account_staff", [b.pk])
    assert (
        DeletedAccount.objects.get(user_id=a.pk).reason
        == DELETED_ACCOUNT_REASON_UNDER_13
    )
    assert (
        DeletedAccount.objects.get(user_id=b.pk).reason == DELETED_ACCOUNT_REASON_STAFF
    )
    assert is_signup_blocked("kid7@example.test")
    assert not is_signup_blocked("plain7@example.test")


def test_action_reports_refused_without_aborting_batch(
    admin_client, target, delay, django_capture_on_commit_callbacks
):
    colleague = User.objects.create_user("colleague7", "c7@example.test", PW)
    colleague.is_staff = True
    colleague.save()
    with django_capture_on_commit_callbacks(execute=True):
        resp = _run_action(
            admin_client, "delete_account_staff", [colleague.pk, target.pk]
        )
    assert DeletedAccount.objects.filter(user_id=target.pk).exists()
    assert not DeletedAccount.objects.filter(user_id=colleague.pk).exists()
    msgs = " ".join(_messages(resp))
    assert "1 account" in msgs and "scheduled" in msgs
    assert "1 refused" in msgs and "colleague7" in msgs
    assert delay.call_count == 1


def test_django_admin_user_delete_is_denied(admin_client, target):
    resp = admin_client.post(
        reverse("admin:users_user_delete", args=[target.pk]), {"post": "yes"}
    )
    assert resp.status_code == 403
    assert User.objects.filter(pk=target.pk).exists()


def test_django_admin_bulk_delete_not_offered(admin_client, target):
    resp = admin_client.get(reverse("admin:users_user_changelist"))
    names = [a[0] for a in resp.context["action_form"].fields["action"].choices]
    assert "delete_selected" not in names
    assert "delete_account_abuse" in names


def test_wagtail_user_delete_view_is_blocked(admin_client, target):
    url = reverse("wagtailusers_users:delete", args=[target.pk])
    assert admin_client.get(url).status_code == 302
    resp = admin_client.post(url, follow=True)
    assert User.objects.filter(pk=target.pk).exists()
    assert any("Delete account" in m for m in _messages(resp))


def test_wagtail_bulk_delete_is_not_available(admin_client, target):
    from wagtail.admin.views.bulk_action.registry import bulk_action_registry

    cls = bulk_action_registry.get_bulk_action_class("users", "user", "delete")
    assert cls.__module__ == "apps.users.wagtail_hooks"
    resp = admin_client.post(
        reverse("wagtail_bulk_action", args=("users", "user", "delete"))
        + f"?id={target.pk}"
    )
    assert User.objects.filter(pk=target.pk).exists()
    assert resp.status_code in (200, 302, 403)
    # Even a direct execute deletes nothing.
    assert cls.execute_action([target], model=User) == (0, 0)
    assert User.objects.filter(pk=target.pk).exists()


# --- request_account_deletion (R14) ---------------------------------------


def test_invalid_reason_raises_before_any_lock(target, django_assert_num_queries):
    with django_assert_num_queries(0):
        with pytest.raises(ValueError):
            request_account_deletion(target, "bogus")
    assert not DeletedAccount.objects.exists()


def test_pending_self_upgrades_to_abuse(target, delay):
    first = request_account_deletion(target, DELETED_ACCOUNT_REASON_SELF)
    assert not is_signup_blocked("target7@example.test")
    again = request_account_deletion(target, DELETED_ACCOUNT_REASON_ABUSE)
    assert again.pk == first.pk
    first.refresh_from_db()
    assert first.reason == DELETED_ACCOUNT_REASON_ABUSE
    assert is_signup_blocked("target7@example.test")


def test_pending_abuse_is_not_downgraded(target, delay):
    first = request_account_deletion(target, DELETED_ACCOUNT_REASON_ABUSE)
    request_account_deletion(target, DELETED_ACCOUNT_REASON_STAFF)
    first.refresh_from_db()
    assert first.reason == DELETED_ACCOUNT_REASON_ABUSE


# --- DeletedAccount admin --------------------------------------------------


def _record(user_id, status):
    return DeletedAccount.objects.create(
        user_id=user_id,
        firebase_uid="uid-secret-7",
        email="gone@example.test",
        email_hash="h" * 64,
        reason=DELETED_ACCOUNT_REASON_SELF,
        status=status,
    )


def test_deleted_account_admin_is_read_only(admin_client):
    rec = _record(1, DELETED_ACCOUNT_STATUS_PENDING)
    url = reverse("admin:users_deletedaccount_changelist")
    resp = admin_client.get(url)
    assert resp.status_code == 200
    assert b"gone@example.test" not in resp.content
    assert (
        admin_client.get(reverse("admin:users_deletedaccount_add")).status_code == 403
    )
    assert (
        admin_client.post(
            reverse("admin:users_deletedaccount_delete", args=[rec.pk]),
            {"post": "yes"},
        ).status_code
        == 403
    )
    assert DeletedAccount.objects.filter(pk=rec.pk).exists()
    names = [a[0] for a in resp.context["action_form"].fields["action"].choices]
    assert "delete_selected" not in names


def test_retry_erase_queues_only_pending(admin_client, delay):
    p1 = _record(1, DELETED_ACCOUNT_STATUS_PENDING)
    p2 = _record(2, DELETED_ACCOUNT_STATUS_PENDING)
    done = _record(3, DELETED_ACCOUNT_STATUS_DONE)
    resp = admin_client.post(
        reverse("admin:users_deletedaccount_changelist"),
        {
            "action": "retry_erase",
            "_selected_action": [str(p1.pk), str(p2.pk), str(done.pk)],
        },
        follow=True,
    )
    assert delay.call_count == 2
    queued = sorted(c.args[0] for c in delay.call_args_list)
    assert queued == sorted([p1.pk, p2.pk])
    assert "2 re-queued, 0 failed (pending rows only)." in _messages(resp)


def test_retry_erase_on_done_row_queues_nothing(admin_client, delay):
    done = _record(3, DELETED_ACCOUNT_STATUS_DONE)
    admin_client.post(
        reverse("admin:users_deletedaccount_changelist"),
        {"action": "retry_erase", "_selected_action": [str(done.pk)]},
        follow=True,
    )
    delay.assert_not_called()


def test_deleted_account_detail_hides_email_and_uid(admin_client):
    rec = _record(1, DELETED_ACCOUNT_STATUS_PENDING)
    resp = admin_client.get(reverse("admin:users_deletedaccount_change", args=[rec.pk]))
    assert resp.status_code == 200
    assert b"gone@example.test" not in resp.content
    assert b"uid-secret-7" not in resp.content


def test_action_counts_user_deleted_meanwhile(admin_client, target, delay):
    with patch(
        "apps.users.admin.request_account_deletion", side_effect=User.DoesNotExist
    ):
        resp = _run_action(admin_client, "delete_account_staff", [target.pk])
    assert resp.status_code == 200
    assert "1 account(s) already deleted." in _messages(resp)


# --- permission gate on the deletion actions ------------------------------

ACCOUNT_ACTIONS = (
    "delete_account_staff",
    "delete_account_abuse",
    "delete_account_under_13",
)


def _staff_with(client, *codenames):
    """A staff member holding exactly ``codenames`` (users app) and logged in."""
    staff = User.objects.create_user("helper7", "helper7@example.test", PW)
    staff.is_staff = True
    staff.save()
    staff.user_permissions.set(
        Permission.objects.filter(
            content_type__app_label="users", codename__in=codenames
        )
    )
    client.force_login(staff)
    return staff


def _action_names(response):
    # The changelist renders no action form at all when no action is allowed.
    form = response.context["action_form"]
    return [] if form is None else [a[0] for a in form.fields["action"].choices]


def test_staff_with_only_view_and_change_cannot_delete_accounts(
    client, target, delay, django_capture_on_commit_callbacks
):
    _staff_with(client, "view_user", "change_user")
    listing = client.get(reverse("admin:users_user_changelist"))
    assert listing.status_code == 200
    for name in ACCOUNT_ACTIONS:
        assert name not in _action_names(listing)

    for name in ACCOUNT_ACTIONS:
        with django_capture_on_commit_callbacks(execute=True):
            resp = _run_action(client, name, [target.pk])
        assert resp.status_code == 200
    assert not DeletedAccount.objects.exists()
    target.refresh_from_db()
    assert target.is_active is True
    delay.assert_not_called()


def test_staff_with_delete_user_permission_can_delete_accounts(
    client, target, delay, django_capture_on_commit_callbacks
):
    _staff_with(client, "view_user", "change_user", "delete_user")
    listing = client.get(reverse("admin:users_user_changelist"))
    for name in ACCOUNT_ACTIONS:
        assert name in _action_names(listing)
    with django_capture_on_commit_callbacks(execute=True):
        _run_action(client, "delete_account_staff", [target.pk])
    assert DeletedAccount.objects.filter(user_id=target.pk).exists()


def test_superuser_sees_every_deletion_action(admin_client):
    listing = admin_client.get(reverse("admin:users_user_changelist"))
    for name in ACCOUNT_ACTIONS:
        assert name in _action_names(listing)
    records = admin_client.get(reverse("admin:users_deletedaccount_changelist"))
    assert "retry_erase" in _action_names(records)


def test_staff_without_delete_user_cannot_retry_erase(client, delay):
    _staff_with(client, "view_deletedaccount", "view_user", "change_user")
    rec = _record(1, DELETED_ACCOUNT_STATUS_PENDING)
    url = reverse("admin:users_deletedaccount_changelist")
    listing = client.get(url)
    assert listing.status_code == 200
    assert "retry_erase" not in _action_names(listing)
    client.post(
        url, {"action": "retry_erase", "_selected_action": [str(rec.pk)]}, follow=True
    )
    delay.assert_not_called()


def test_retry_erase_keeps_going_past_a_broker_failure(admin_client, delay):
    p1 = _record(1, DELETED_ACCOUNT_STATUS_PENDING)
    p2 = _record(2, DELETED_ACCOUNT_STATUS_PENDING)
    p3 = _record(3, DELETED_ACCOUNT_STATUS_PENDING)
    delay.side_effect = [None, ConnectionError("broker down"), None]
    resp = admin_client.post(
        reverse("admin:users_deletedaccount_changelist"),
        {
            "action": "retry_erase",
            "_selected_action": [str(p1.pk), str(p2.pk), str(p3.pk)],
        },
        follow=True,
    )
    assert resp.status_code == 200
    assert delay.call_count == 3
    assert "2 re-queued, 1 failed (pending rows only)." in _messages(resp)


def test_action_logs_the_acting_staff_member(
    admin_client, target, delay, django_capture_on_commit_callbacks
):
    root = User.objects.get(username="root7")
    with patch("apps.users.admin.logger") as logger:
        with django_capture_on_commit_callbacks(execute=True):
            _run_action(admin_client, "delete_account_staff", [target.pk])
    lines = [c.args[0] % c.args[1:] for c in logger.info.call_args_list]
    assert (
        f"[ACCOUNT DELETE] staff {root.pk} requested deletion of account "
        f"{target.pk} (staff)"
    ) in lines
