"""Todo 447 slice B: the email-verification follow-ups.

- item 1: the first provider link to a password account revokes its refresh
  tokens and mails a notice (web OAuth, allauth, Firebase);
- item 4: allauth ``EmailAddress`` rows are stored lowercase (and backfilled);
- item 5: ``mark_email_verified`` goes through allauth and never takes
  ``primary`` from another address;
- item 9: verification mails are capped per account;
- item 11: account mail goes out from Celery, and send failures are logged.
"""

import importlib
from unittest.mock import MagicMock, patch

from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount
from apps.users import oauth_views, tasks
from apps.users.constants import (
    ACCOUNT_MAIL_MAX_RETRIES,
    ACCOUNT_MAIL_RETRY_DELAY,
    VERIFICATION_EMAIL_CAP,
)
from apps.users.email_verification import (
    is_email_verified,
    mark_email_verified,
    send_verification_email,
)
from apps.users.firebase_auth_views import get_or_create_user_from_firebase
from apps.users.oauth_adapters import CustomAccountAdapter, CustomSocialAccountAdapter
from celery.exceptions import Retry
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

REGISTER_URL = "/api/v1/auth/register/"
RESEND_URL = "/api/v1/auth/verify-email/resend/"
PASSWORD = "TestPassword123!"  # pragma: allowlist secret


def _is_revoked(refresh) -> bool:
    return BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()


def _verified_password_account(username="owner", email="owner@example.com"):
    user = User.objects.create_user(username=username, email=email, password=PASSWORD)
    mark_email_verified(user)
    return user


def _notices():
    return [m for m in mail.outbox if "sign-in was connected" in m.subject]


# --- item 1: first provider link ------------------------------------------------


@override_settings(API_PUBLIC_URL="https://api.example.test")
class WebOAuthFirstLinkTest(TestCase):
    def _sign_in(self, email="owner@example.com", uid="g-owner"):
        with self.captureOnCommitCallbacks(execute=True):
            return oauth_views._find_or_create_user(
                "google", {"email": email, "id": uid}
            )

    def test_first_link_to_a_password_account_revokes_and_notifies(self):
        user = _verified_password_account()
        session = RefreshToken.for_user(user)

        self.assertEqual(self._sign_in(), user)

        self.assertTrue(_is_revoked(session))
        [notice] = _notices()
        self.assertEqual(notice.to, ["owner@example.com"])
        self.assertIn("Google", notice.subject)
        self.assertIn("https://api.example.test/accounts/password/reset/", notice.body)
        self.assertTrue(
            SocialAccount.objects.filter(
                user=user, provider="google", uid="g-owner"
            ).exists()
        )

    def test_later_sign_ins_are_not_a_first_link(self):
        user = _verified_password_account()
        self._sign_in()
        session = RefreshToken.for_user(user)
        mail.outbox.clear()

        self.assertEqual(self._sign_in(), user)

        self.assertFalse(_is_revoked(session))
        self.assertEqual(_notices(), [])

    def test_account_without_a_password_is_left_alone(self):
        user = User.objects.create_user(username="social", email="owner@example.com")
        mark_email_verified(user)
        session = RefreshToken.for_user(user)

        self.assertEqual(self._sign_in(), user)

        self.assertFalse(_is_revoked(session))
        self.assertEqual(_notices(), [])

    def test_identity_linked_to_another_account_is_refused(self):
        _verified_password_account()
        other = User.objects.create_user(username="other", email="other@example.com")
        SocialAccount.objects.create(user=other, provider="google", uid="g-owner")

        self.assertIsNone(self._sign_in())
        self.assertEqual(_notices(), [])

    def test_missing_provider_id_is_refused(self):
        _verified_password_account()

        with self.captureOnCommitCallbacks(execute=True):
            result = oauth_views._find_or_create_user(
                "google", {"email": "owner@example.com"}
            )

        self.assertIsNone(result)

    def test_refused_identity_on_signup_leaves_no_account(self):
        other = User.objects.create_user(username="other", email="other@example.com")
        SocialAccount.objects.create(user=other, provider="google", uid="g-new")

        self.assertIsNone(self._sign_in(email="new@example.com", uid="g-new"))
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_created_account_records_its_identity(self):
        user = self._sign_in(email="new@example.com", uid="g-new")

        self.assertTrue(
            SocialAccount.objects.filter(
                user=user, provider="google", uid="g-new"
            ).exists()
        )
        self.assertEqual(_notices(), [])  # no password, nothing to warn about


class AllauthFirstLinkTest(TestCase):
    def _sociallogin(self, email):
        sociallogin = MagicMock()
        sociallogin.account.provider = "google"
        sociallogin.account.extra_data = {"email": email}
        sociallogin.is_existing = False
        sociallogin.email_addresses = [EmailAddress(email=email, verified=True)]
        return sociallogin

    def _pre_social_login(self, sociallogin):
        request = RequestFactory().get("/accounts/google/login/callback/")
        with self.captureOnCommitCallbacks(execute=True):
            CustomSocialAccountAdapter().pre_social_login(request, sociallogin)

    def test_connect_revokes_and_notifies(self):
        user = _verified_password_account()
        session = RefreshToken.for_user(user)
        sociallogin = self._sociallogin("owner@example.com")

        self._pre_social_login(sociallogin)

        sociallogin.connect.assert_called_once()
        self.assertTrue(_is_revoked(session))
        self.assertEqual(len(_notices()), 1)

    def test_case_variant_of_a_verified_account_is_matched(self):
        # Item 4's carry-over: this lookup was case-exact.
        user = _verified_password_account(email="Owner@Example.com")
        sociallogin = self._sociallogin("owner@example.com")

        self._pre_social_login(sociallogin)

        self.assertEqual(sociallogin.connect.call_args.args[1], user)

    def test_ambiguous_case_variants_are_refused(self):
        User.objects.create_user(username="a", email="Dup@example.com")
        User.objects.create_user(username="b", email="dup@example.com")
        sociallogin = self._sociallogin("dup@example.com")

        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self._pre_social_login(sociallogin)

        self.assertIn("error=user_creation_failed", ctx.exception.response.url)
        sociallogin.connect.assert_not_called()


class FirebaseFirstLinkTest(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("v1:users:firebase_token_exchange")

    @patch("apps.users.firebase_auth_views.firebase_auth.verify_id_token")
    def test_first_bind_revokes_old_sessions_but_not_the_new_one(self, mock_verify):
        user = _verified_password_account()
        old = RefreshToken.for_user(user)
        mock_verify.return_value = {
            "uid": "fb-owner",
            "email": "owner@example.com",
            "email_verified": True,
            "firebase": {"sign_in_provider": "google.com"},
        }

        with self.captureOnCommitCallbacks(execute=True):
            response = APIClient().post(
                self.url, {"firebase_token": "a.b.c"}, format="json"
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(_is_revoked(old))
        new = RefreshToken(response.data["refresh_token"])
        self.assertFalse(_is_revoked(new))
        [notice] = _notices()
        self.assertIn("Google", notice.subject)

    def test_bound_account_is_not_a_first_link(self):
        user = _verified_password_account()
        user.firebase_uid = "fb-owner"
        user.save(update_fields=["firebase_uid"])
        session = RefreshToken.for_user(user)

        with self.captureOnCommitCallbacks(execute=True):
            get_or_create_user_from_firebase(
                firebase_uid="fb-owner",
                firebase_email="owner@example.com",
                email_verified=True,
                provider="google.com",
            )

        self.assertFalse(_is_revoked(session))
        self.assertEqual(_notices(), [])


# --- item 4: lowercase rows ------------------------------------------------------


class LowercaseAddressTest(TestCase):
    def test_new_rows_are_lowercase(self):
        user = User.objects.create_user(username="m", email="Mixed@Example.com")

        mark_email_verified(user)

        self.assertEqual(
            list(
                EmailAddress.objects.filter(user=user).values_list("email", flat=True)
            ),
            ["mixed@example.com"],
        )
        self.assertTrue(is_email_verified(user))


class LowercaseMigrationTest(TestCase):
    """Migration 0014. Data only, so it runs against the current models."""

    def _run(self):
        migration = importlib.import_module(
            "apps.users.migrations.0014_lowercase_email_addresses"
        )
        migration.lowercase(django_apps, None)

    def test_mixed_case_row_is_lowercased(self):
        user = User.objects.create_user(username="a", email="Ann@Example.com")
        address = EmailAddress.objects.create(
            user=user, email="Ann@Example.com", verified=True, primary=True
        )

        self._run()

        address.refresh_from_db()
        self.assertEqual(address.email, "ann@example.com")
        self.assertTrue(address.verified)

    def test_two_verified_variants_are_left_alone(self):
        # Lowercasing would violate unique_verified_email. Neither account is
        # picked; get_account_by_email keeps refusing the ambiguity.
        a = User.objects.create_user(username="a", email="Bob@example.com")
        b = User.objects.create_user(username="b", email="bob@example.com")
        upper = EmailAddress.objects.create(
            user=a, email="Bob@example.com", verified=True, primary=True
        )
        EmailAddress.objects.create(
            user=b, email="bob@example.com", verified=True, primary=True
        )

        self._run()

        upper.refresh_from_db()
        self.assertEqual(upper.email, "Bob@example.com")

    def test_unverified_variant_beside_a_verified_one_is_lowercased(self):
        a = User.objects.create_user(username="a", email="Cat@example.com")
        b = User.objects.create_user(username="b", email="cat@example.com")
        parked = EmailAddress.objects.create(
            user=a, email="Cat@example.com", verified=False, primary=True
        )
        EmailAddress.objects.create(
            user=b, email="cat@example.com", verified=True, primary=True
        )

        self._run()

        parked.refresh_from_db()
        self.assertEqual(parked.email, "cat@example.com")
        self.assertFalse(parked.verified)

    def test_same_account_duplicate_is_left_alone(self):
        user = User.objects.create_user(username="d", email="Dee@example.com")
        upper = EmailAddress.objects.create(
            user=user, email="Dee@example.com", verified=False, primary=False
        )
        EmailAddress.objects.create(
            user=user, email="dee@example.com", verified=True, primary=True
        )

        self._run()

        upper.refresh_from_db()
        self.assertEqual(upper.email, "Dee@example.com")


# --- item 5: mark_email_verified through allauth -------------------------------


class MarkEmailVerifiedTest(TestCase):
    def test_keeps_another_primary_address(self):
        user = User.objects.create_user(username="p", email="new@example.com")
        old = EmailAddress.objects.create(
            user=user, email="old@example.com", verified=True, primary=True
        )

        self.assertTrue(mark_email_verified(user))

        old.refresh_from_db()
        self.assertTrue(old.primary)
        new = EmailAddress.objects.get(user=user, email="new@example.com")
        self.assertTrue(new.verified)
        self.assertFalse(new.primary)

    def test_case_variant_verified_elsewhere_is_refused(self):
        # allauth's own conflict check is case-exact; a pre-0014 row differs
        # from ours only in case.
        holder = User.objects.create_user(username="h", email="elsewhere@example.com")
        EmailAddress.objects.create(
            user=holder, email="Taken@Example.com", verified=True, primary=True
        )
        user = User.objects.create_user(username="u", email="taken@example.com")

        self.assertFalse(mark_email_verified(user))
        self.assertFalse(is_email_verified(user))


# --- item 9: the cap ---------------------------------------------------------------


class VerificationCapTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="ada", email="ada@example.com", password=PASSWORD
        )
        self.client.force_authenticate(user=self.user)

    def _resend(self):
        cache.clear()  # the hourly rate limit is not what is under test
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(RESEND_URL)

    def test_registration_mail_counts_toward_the_cap(self):
        csrf = self.client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
        client = APIClient(enforce_csrf_checks=True)
        client.cookies["csrftoken"] = csrf
        with self.captureOnCommitCallbacks(execute=True):
            response = client.post(
                REGISTER_URL,
                {
                    "username": "newbie",
                    "email": "newbie@example.com",
                    "password": PASSWORD,
                    "confirmPassword": PASSWORD,
                },
                HTTP_X_CSRFTOKEN=csrf,
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            User.objects.get(username="newbie").verification_emails_sent, 1
        )

    def test_resend_stops_at_the_cap(self):
        for _ in range(VERIFICATION_EMAIL_CAP):
            self.assertTrue(self._resend().data["sent"])
        mail.outbox.clear()

        response = self._resend()

        self.assertEqual(
            response.data, {"verified": False, "sent": False, "limit_reached": True}
        )
        self.assertEqual(mail.outbox, [])
        self.user.refresh_from_db()
        self.assertEqual(self.user.verification_emails_sent, VERIFICATION_EMAIL_CAP)

    def test_allauth_mails_are_capped_too(self):
        self.user.verification_emails_sent = VERIFICATION_EMAIL_CAP
        self.user.save(update_fields=["verification_emails_sent"])
        confirmation = MagicMock()
        confirmation.email_address.user = self.user

        with self.captureOnCommitCallbacks(execute=True):
            CustomAccountAdapter().send_confirmation_mail(None, confirmation, False)

        self.assertEqual(mail.outbox, [])


# --- item 11: Celery ----------------------------------------------------------------


class MailIsQueuedTest(TestCase):
    def test_nothing_is_queued_before_commit(self):
        user = User.objects.create_user(username="q", email="q@example.com")

        with patch.object(tasks.send_verification_email_task, "delay") as delay:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                send_verification_email(user)
            delay.assert_not_called()
            for callback in callbacks:
                callback()

        delay.assert_called_once_with(user.pk)

    def test_broker_failure_is_logged_not_raised(self):
        user = User.objects.create_user(username="q", email="q@example.com")

        with (
            patch.object(
                tasks.send_verification_email_task,
                "delay",
                side_effect=ConnectionError("broker down"),
            ),
            self.assertLogs("apps.users.email_verification", "ERROR") as logs,
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.assertTrue(send_verification_email(user))

        self.assertIn("Could not queue send_verification_email_task", logs.output[0])

    def test_task_drops_a_mail_for_an_address_verified_meanwhile(self):
        user = User.objects.create_user(username="q", email="q@example.com")
        mark_email_verified(user)

        with patch.object(tasks.send_verification_email_task, "retry") as retry:
            tasks.send_verification_email_task.apply(args=(user.pk,))

        self.assertEqual(mail.outbox, [])
        retry.assert_not_called()  # nothing to send is not a failed send


class MailTaskRetryTest(TestCase):
    """A send that reports failure retries with backoff, then gives up with
    an error log. ``.apply()`` ignores countdown, so the countdown is pinned
    with ``push_request`` + a mocked ``retry`` (docs/rules/celery.md)."""

    def setUp(self):
        self.user = User.objects.create_user(username="r", email="r@example.com")
        self.task = tasks.send_welcome_email_task

    def _run(self, retries):
        self.task.push_request(retries=retries)
        try:
            return self.task.run(self.user.pk)
        finally:
            self.task.pop_request()

    def test_failed_send_retries_with_backoff(self):
        for attempt in range(ACCOUNT_MAIL_MAX_RETRIES):
            with (
                self.subTest(attempt=attempt),
                patch(
                    "apps.core.services.email_service.EmailService.send_welcome_email",
                    return_value=False,
                ),
                patch.object(self.task, "retry", side_effect=Retry()) as retry,
            ):
                with self.assertRaises(Retry):
                    self._run(attempt)
                self.assertEqual(
                    retry.call_args.kwargs["countdown"],
                    ACCOUNT_MAIL_RETRY_DELAY * 2**attempt,
                )

    def test_last_failure_is_logged_and_dropped(self):
        with (
            patch(
                "apps.core.services.email_service.EmailService.send_welcome_email",
                return_value=False,
            ),
            patch.object(self.task, "retry") as retry,
            self.assertLogs("apps.users.tasks", "ERROR") as logs,
        ):
            self._run(ACCOUNT_MAIL_MAX_RETRIES)

        retry.assert_not_called()
        self.assertIn("giving up", logs.output[0])

    def test_successful_send_does_not_retry(self):
        with (
            patch(
                "apps.core.services.email_service.EmailService.send_welcome_email",
                return_value=True,
            ),
            patch.object(self.task, "retry") as retry,
        ):
            self._run(0)

        retry.assert_not_called()
