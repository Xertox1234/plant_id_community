"""Optional forum email goes only to an address its account has verified
(audit 2026-11-24 F211). The proof is ``email_verification``'s: an allauth
``EmailAddress`` row, verified, for the account's CURRENT email.
"""

import pytest
from allauth.account.models import EmailAddress
from apps.core.services.email_service import (
    SUPPRESSED_UNVERIFIED,
    EmailOutcome,
    EmailService,
    EmailType,
)
from apps.forum_host.eligibility import REASON_UNVERIFIED, recheck
from apps.users.email_verification import (
    mark_email_verified,
    verified_email_q,
    verified_user_ids,
)
from django.contrib.auth import get_user_model
from django.core import mail
from wagtail_forum.digest import mailable_accounts

pytestmark = pytest.mark.django_db

User = get_user_model()

FORUM_TYPES = [
    EmailType.FORUM_REPLY,
    EmailType.FORUM_MENTION,
    EmailType.FORUM_QUOTE,
    EmailType.FORUM_SOLUTION,
    EmailType.FORUM_DIGEST,
]


def _user(username, *, email=None, verified=False):
    user = User.objects.create_user(
        username=username, email=email or f"{username}@x.test", password="x" * 16
    )
    if verified:
        assert mark_email_verified(user)
    return user


def _send(user, email_type):
    service = EmailService()
    sent = service.send_email(
        email_type=email_type,
        recipient=user,
        subject="s",
        template_name="generic_notification",
        context={"message": "m"},
    )
    return service, sent


@pytest.mark.parametrize("email_type", FORUM_TYPES)
def test_email_service_holds_forum_mail_to_an_unverified_address(email_type):
    service, sent = _send(_user("never"), email_type)

    assert sent is False
    assert service.last_outcome == EmailOutcome.SUPPRESSED
    assert service.last_suppression_reason == SUPPRESSED_UNVERIFIED
    assert mail.outbox == []


@pytest.mark.parametrize("email_type", FORUM_TYPES)
def test_email_service_sends_forum_mail_to_a_verified_address(email_type):
    _, sent = _send(_user("done", verified=True), email_type)

    assert sent is True
    assert len(mail.outbox) == 1


def test_an_address_string_is_held_the_same_way():
    user = _user("plain")
    _, sent = _send(user.email, EmailType.FORUM_REPLY)
    assert sent is False


@pytest.mark.parametrize(
    "email_type",
    [
        EmailType.ACCOUNT_VERIFICATION,
        EmailType.PASSWORD_RESET,
        EmailType.SECURITY_ALERT,
        EmailType.IDENTIFICATION_RESULT,
    ],
)
def test_other_mail_is_unaffected(email_type):
    _, sent = _send(_user("never"), email_type)
    assert sent is True


@pytest.mark.parametrize(
    "event", ["reply_added", "mention", "quote", "answer_accepted"]
)
def test_the_send_time_recheck_holds_email_but_not_push(event):
    never, done = _user("never"), _user("done", verified=True)
    # Every email cell on, so only the address decides.
    from wagtail_forum.preferences import EVENT_VERBS

    on = {never.pk: {}, done.pk: {}}
    for pk in on:
        on[pk] = {
            verb: {"email": True} for verb in {str(v) for v in EVENT_VERBS.values()}
        }
    ids = [never.pk, done.pk]

    email = recheck(event, ids, {}, "email", overrides_by_user=on)
    push = recheck(event, ids, {}, "push", overrides_by_user=on)

    assert [u.pk for u in email.eligible] == [done.pk]
    assert email.suppressed == {never.pk: REASON_UNVERIFIED}
    assert {u.pk for u in push.eligible} == set(ids)


def test_the_recheck_cost_does_not_grow_with_recipients(django_assert_num_queries):
    users = [_user(f"u{i}", verified=bool(i % 2)) for i in range(4)]
    for batch in (users[:1], users):
        with django_assert_num_queries(1):
            recheck(
                "reply_added",
                [u.pk for u in batch],
                {},
                "email",
                users=batch,
                overrides_by_user={},
            )


def test_the_digest_goes_only_to_verified_addresses():
    _user("never")
    done = _user("done", verified=True)
    assert list(mailable_accounts()) == [done]


def test_verification_is_of_the_current_address_whatever_its_case():
    mixed = _user("mixed", email="Mixed.Case@X.test", verified=True)
    moved = _user("moved", verified=True)
    moved.email = "elsewhere@x.test"
    moved.save(update_fields=["email"])
    unverified_row = _user("pending")
    EmailAddress.objects.create(
        user=unverified_row, email=unverified_row.email, verified=False
    )
    # Another account's proof of the same address is not this account's.
    twin = User.objects.create_user(username="twin", email=mixed.email)

    assert verified_user_ids([mixed, moved, unverified_row, twin]) == {mixed.pk}
    assert list(User.objects.filter(verified_email_q())) == [mixed]


@pytest.mark.parametrize("provider", ["google.com", "apple.com", "password"])
def test_a_firebase_account_with_a_verified_email_gets_forum_mail(provider):
    from apps.users.firebase_auth_views import get_or_create_user_from_firebase

    user, created = get_or_create_user_from_firebase(
        firebase_uid=f"uid-{provider}",
        firebase_email="Fire.Base@x.test",
        email_verified=True,
        provider=provider,
        accepted_terms=True,
    )

    assert created
    _, sent = _send(user, EmailType.FORUM_REPLY)
    assert sent is True
    assert user in mailable_accounts()


def test_a_web_google_account_gets_forum_mail(rf):
    from apps.users import oauth_views

    user = oauth_views._find_or_create_user(
        "google",
        {
            "id": "g-1",
            "email": "goo@x.test",
            "verified_email": True,
            "given_name": "G",
            "family_name": "O",
        },
        accepted_terms=True,
    )

    assert user is not None
    _, sent = _send(user, EmailType.FORUM_REPLY)
    assert sent is True
