"""expire_unverified_accounts (todo 447 slice C).

Every rule has a test that breaks exactly that rule on an otherwise
deletable account. Rules checked in SQL show up as "not a candidate";
the per-row checks (password, extra data, the locked re-check) show up as
"kept". The summary line tells the two apart, which is what makes each rule
individually testable although the extra-data backstop overlaps several.
"""

import io
import logging
from datetime import timedelta
from unittest.mock import patch

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from apps.users.constants import (
    UNVERIFIED_ACCOUNT_EXPIRY_DAYS,
    UNVERIFIED_ACCOUNT_SIGNUP_MARGIN_SECONDS,
)
from apps.users.management.commands import expire_unverified_accounts as command
from apps.users.models import UserPlantCollection
from apps.users.signup import (
    DEFAULT_COLLECTION_NAME,
    create_default_plant_collection,
    join_forum_members_group,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()

PASSWORD = "TestPassword123!"  # pragma: allowlist secret
OLD = timedelta(days=UNVERIFIED_ACCOUNT_EXPIRY_DAYS + 1)
MARGIN = timedelta(seconds=UNVERIFIED_ACCOUNT_SIGNUP_MARGIN_SECONDS)


@pytest.fixture
def expiry_log():
    """The ``apps`` logger does not propagate to root, where caplog listens."""
    records = []

    class _Handler(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = _Handler(level=logging.INFO)
    command_logger = logging.getLogger(command.__name__)
    previous = command_logger.level
    command_logger.addHandler(handler)
    command_logger.setLevel(logging.INFO)
    yield records
    command_logger.removeHandler(handler)
    command_logger.setLevel(previous)


def expire(*args):
    out = io.StringIO()
    call_command("expire_unverified_accounts", *args, stdout=out)
    return out.getvalue()


def age(user, by=OLD):
    """Move the account and its registration token back in time together."""
    joined = timezone.now() - by
    User.objects.filter(pk=user.pk).update(date_joined=joined)
    OutstandingToken.objects.filter(user=user).update(
        created_at=joined + timedelta(seconds=1)
    )
    user.refresh_from_db()
    return user


def stale_account(username="squat", email="victim@example.com", **fields):
    """An account shaped like a registration: unverified address, default
    collection, forum group, one refresh token, then left for 8 days."""
    user = User.objects.create_user(
        username=username, email=email, password=PASSWORD, **fields
    )
    EmailAddress.objects.create(user=user, email=email, verified=False, primary=True)
    create_default_plant_collection(user)
    join_forum_members_group(user)
    RefreshToken.for_user(user)
    return age(user)


def token_within_margin(user):
    """A second refresh token issued inside the signup margin."""
    token = RefreshToken.for_user(user)
    OutstandingToken.objects.filter(jti=token["jti"]).update(
        created_at=user.date_joined + timedelta(seconds=2)
    )


def exists(user):
    return User.objects.filter(pk=user.pk).exists()


def summary(out, candidates, kept, deleted, verb="deleted"):
    expected = (
        f"[PRUNE] unverified accounts: {candidates} candidate(s) older than "
        f"{UNVERIFIED_ACCOUNT_EXPIRY_DAYS}d, {kept} kept, {verb} {deleted}, 0 failed."
    )
    assert expected in out, out


@pytest.fixture
def board(db):
    index = Page.objects.get(id=1).add_child(
        instance=ForumIndex(title="Forum", slug="forum")
    )
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


# --- the real thing ----------------------------------------------------------


@pytest.mark.django_db
def test_a_real_registration_left_alone_for_eight_days_is_deleted(expiry_log):
    cache.clear()  # registration is rate limited per IP
    client = APIClient(enforce_csrf_checks=True)
    csrf = client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
    client.cookies["csrftoken"] = csrf
    response = client.post(
        "/api/v1/auth/register/",
        {
            "username": "newbie",
            "email": "newbie@example.com",
            "password": PASSWORD,
            "confirmPassword": PASSWORD,
        },
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == 201, response.content
    user = age(User.objects.get(username="newbie"))

    out = expire()

    summary(out, candidates=1, kept=0, deleted=1)
    assert not exists(user)
    assert not OutstandingToken.objects.filter(user_id=user.pk).exists()
    assert not OutstandingToken.objects.filter(user__isnull=True).exists()
    assert not EmailAddress.objects.filter(email="newbie@example.com").exists()
    # The id is logged; the address and the username never are.
    assert f"[PRUNE] deleted unverified account {user.pk}" in expiry_log
    assert not any("newbie" in line for line in expiry_log + [out])


@pytest.mark.django_db
def test_dry_run_deletes_nothing_and_reports_what_would_go(expiry_log):
    user = stale_account()

    out = expire("--dry-run")

    summary(out, candidates=1, kept=0, deleted=1, verb="would delete")
    assert exists(user)
    assert OutstandingToken.objects.filter(user=user).exists()
    assert f"[PRUNE] would delete unverified account {user.pk}" in expiry_log


# --- rules checked in SQL: the account is never a candidate ------------------


@pytest.mark.django_db
def test_an_account_younger_than_the_expiry_is_not_a_candidate():
    user = stale_account()
    age(user, by=timedelta(days=UNVERIFIED_ACCOUNT_EXPIRY_DAYS - 1))

    summary(expire(), candidates=0, kept=0, deleted=0)
    assert exists(user)


@pytest.mark.django_db
def test_a_verified_address_is_not_a_candidate():
    user = stale_account()
    EmailAddress.objects.filter(user=user).update(verified=True)

    summary(expire(), candidates=0, kept=0, deleted=0)
    assert exists(user)


@pytest.mark.django_db
def test_any_verified_address_counts_not_just_the_current_one():
    user = stale_account()
    EmailAddress.objects.create(user=user, email="old@example.com", verified=True)

    summary(expire(), candidates=0, kept=0, deleted=0)
    assert exists(user)


@pytest.mark.django_db
def test_a_firebase_account_is_not_a_candidate():
    user = stale_account(firebase_uid="fb-uid")

    summary(expire(), candidates=0, kept=0, deleted=0)
    assert exists(user)


@pytest.mark.django_db
def test_a_blank_firebase_uid_does_not_protect_an_account():
    user = stale_account(firebase_uid="")

    summary(expire(), candidates=1, kept=0, deleted=1)
    assert not exists(user)


@pytest.mark.django_db
def test_a_social_account_is_not_a_candidate():
    user = stale_account()
    SocialAccount.objects.create(user=user, provider="google", uid="g-1")

    summary(expire(), candidates=0, kept=0, deleted=0)
    assert exists(user)


@pytest.mark.django_db
@pytest.mark.parametrize("flag", ["is_staff", "is_superuser"])
def test_staff_and_superusers_are_not_candidates(flag):
    user = stale_account(**{flag: True})

    summary(expire(), candidates=0, kept=0, deleted=0)
    assert exists(user)


@pytest.mark.django_db
def test_an_empty_password_hash_is_not_a_candidate():
    user = stale_account()
    User.objects.filter(pk=user.pk).update(password="")

    summary(expire(), candidates=0, kept=0, deleted=0)
    assert exists(user)


@pytest.mark.django_db
def test_a_sign_in_after_registering_is_not_a_candidate():
    user = stale_account()
    User.objects.filter(pk=user.pk).update(
        last_login=user.date_joined + MARGIN + timedelta(seconds=1)
    )

    summary(expire(), candidates=0, kept=0, deleted=0)
    assert exists(user)


@pytest.mark.django_db
def test_a_last_login_stamped_at_registration_is_not_a_sign_in():
    user = stale_account()
    User.objects.filter(pk=user.pk).update(last_login=user.date_joined + MARGIN)

    summary(expire(), candidates=1, kept=0, deleted=1)
    assert not exists(user)


@pytest.mark.django_db
def test_a_refresh_after_registering_is_not_a_candidate():
    """Token rotation keeps a session alive without moving last_login."""
    user = stale_account()
    rotated = RefreshToken.for_user(user)
    OutstandingToken.objects.filter(jti=rotated["jti"]).update(
        created_at=user.date_joined + MARGIN + timedelta(seconds=1)
    )

    summary(expire(), candidates=0, kept=0, deleted=0)
    assert exists(user)


@pytest.mark.django_db
def test_a_forum_post_is_not_a_candidate(board):
    user = stale_account()
    topic = Topic.objects.create(board=board, title="T", slug="t")
    Post.objects.create(topic=topic, author=user, body=[])

    summary(expire(), candidates=0, kept=0, deleted=0)
    assert exists(user)


@pytest.mark.django_db
def test_a_forum_topic_is_not_a_candidate(board):
    user = stale_account()
    Topic.objects.create(board=board, title="T", slug="t", author=user)

    summary(expire(), candidates=0, kept=0, deleted=0)
    assert exists(user)


@pytest.mark.django_db
def test_a_revision_by_the_account_is_not_a_candidate(board):
    user = stale_account()
    topic = Topic.objects.create(board=board, title="T", slug="t")
    topic.save_revision(user=user)

    summary(expire(), candidates=0, kept=0, deleted=0)
    assert exists(user)


# --- per-row checks: the account is a candidate but kept ---------------------


@pytest.mark.django_db
def test_an_unusable_password_is_kept(expiry_log):
    user = stale_account()
    user.set_unusable_password()
    user.save(update_fields=["password"])

    summary(expire(), candidates=1, kept=1, deleted=0)
    assert exists(user)
    assert f"[PRUNE] account {user.pk} has no password; kept" in expiry_log


@pytest.mark.django_db
@pytest.mark.parametrize(
    "extra, label",
    [
        (
            lambda u: UserPlantCollection.objects.create(user=u, name="Cacti"),
            "users.UserPlantCollection",
        ),
        (
            lambda u: UserPlantCollection.objects.filter(user=u).update(name="Renamed"),
            "users.UserPlantCollection",
        ),
        (
            lambda u: EmailAddress.objects.create(user=u, email="second@example.com"),
            "account.EmailAddress",
        ),
        (lambda u: token_within_margin(u), "token_blacklist.OutstandingToken"),
        (
            lambda u: u.groups.add(Group.objects.create(name="Beta testers")),
            "users.User.groups",
        ),
        (
            lambda u: u.following.add(User.objects.create_user(username="other")),
            "users.User.following",
        ),
        (
            lambda u: User.objects.create_user(username="fan").following.add(u),
            "users.User",
        ),
    ],
    ids=[
        "second-collection",
        "renamed-collection",
        "second-address",
        "second-token-in-margin",
        "other-group",
        "following",
        "followed",
    ],
)
def test_data_beyond_what_registration_creates_keeps_the_account(
    extra, label, expiry_log
):
    user = stale_account()
    extra(user)

    summary(expire(), candidates=1, kept=1, deleted=0)
    assert exists(user)
    assert f"[PRUNE] account {user.pk} has {label} rows; kept" in expiry_log


@pytest.mark.django_db
def test_a_hidden_relation_keeps_the_account(board, expiry_log):
    """Relations declared with related_name='+' still count."""
    user = stale_account()
    Topic.objects.create(board=board, title="T", slug="t", last_post_author=user)

    summary(expire(), candidates=1, kept=1, deleted=0)
    assert exists(user)
    assert f"[PRUNE] account {user.pk} has wagtail_forum.Topic rows; kept" in (
        expiry_log
    )


@pytest.mark.django_db
def test_an_account_that_signs_in_during_the_run_is_kept(expiry_log):
    """Candidates are listed first; each is re-checked under a row lock."""
    user = stale_account()
    real = command._candidates
    calls = []

    def sign_in_after_listing(now):
        calls.append(now)
        if len(calls) == 2:
            User.objects.filter(pk=user.pk).update(last_login=timezone.now())
        return real(now)

    with patch.object(command, "_candidates", side_effect=sign_in_after_listing):
        out = expire()

    summary(out, candidates=1, kept=1, deleted=0)
    assert exists(user)
    assert f"[PRUNE] account {user.pk} changed; kept" in expiry_log


@pytest.mark.django_db
def test_a_failed_delete_is_reported_and_the_rest_still_go(expiry_log):
    first = stale_account("first", "first@example.com")
    second = stale_account("second", "second@example.com")
    real_delete = User.delete

    def delete(self, *args, **kwargs):
        if self.pk == first.pk:
            raise RuntimeError("boom")
        return real_delete(self, *args, **kwargs)

    out = io.StringIO()
    with patch.object(User, "delete", delete), pytest.raises(CommandError):
        call_command("expire_unverified_accounts", stdout=out)

    assert "deleted 1, 1 failed." in out.getvalue()
    assert exists(first)
    # The failure rolled back its own transaction, tokens included.
    assert OutstandingToken.objects.filter(user=first).exists()
    assert not exists(second)
    assert f"[PRUNE] could not delete account {first.pk}" in expiry_log


@pytest.mark.django_db
def test_the_default_collection_name_is_the_signup_one():
    """The backstop allows exactly the collection registration creates."""
    user = stale_account()
    assert list(
        UserPlantCollection.objects.filter(user=user).values_list("name", flat=True)
    ) == [DEFAULT_COLLECTION_NAME]
