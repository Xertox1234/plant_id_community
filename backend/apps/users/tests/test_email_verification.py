"""Email verification closes the registration pre-hijack (todo 446).

An attacker could register a victim's address with a password, then inherit
the victim's first Google (web or Firebase) sign-in, because those paths matched
the existing account by email. Now a sign-in may only match an account whose
email is verified, and password registration proves ownership through an
emailed link confirmed by a POST (never a GET: mail scanners prefetch links).
"""

import importlib
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount
from apps.users import oauth_views
from apps.users.email_verification import (
    is_email_verified,
    mark_email_verified,
    verification_url,
)
from apps.users.firebase_auth_views import get_or_create_user_from_firebase
from apps.users.oauth_adapters import CustomAccountAdapter, CustomSocialAccountAdapter
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

User = get_user_model()

REGISTER_URL = "/api/v1/auth/register/"
VERIFY_URL = "/api/v1/auth/verify-email/"
RESEND_URL = "/api/v1/auth/verify-email/resend/"
PASSWORD = "TestPassword123!"  # pragma: allowlist secret


def _key_from(url):
    return parse_qs(urlparse(url).query)["key"][0]


class RegistrationSendsVerificationTest(TestCase):
    def setUp(self):
        cache.clear()  # ratelimit counters persist in the test cache

    def _register(self, email="new@example.com"):
        csrf = self.client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                REGISTER_URL,
                data={
                    "username": "newbie",
                    "email": email,
                    "password": PASSWORD,
                    "confirmPassword": PASSWORD,
                },
                HTTP_X_CSRFTOKEN=csrf,
            )

    def test_registration_is_unverified_and_emails_a_web_link(self):
        response = self._register()

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="newbie")
        self.assertFalse(is_email_verified(user))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])
        self.assertIn("/verify-email?key=", mail.outbox[0].body)

    def test_a_case_variant_of_a_taken_email_is_refused(self):
        User.objects.create_user(username="alice", email="alice@example.com")

        response = self._register(email="Alice@example.com")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="newbie").exists())


class VerifyEmailEndpointTest(TestCase):
    """Confirming needs the key AND a session for the key's account. The key
    alone would let a victim who clicks the link in their inbox verify an
    attacker's pre-registered account."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="ada", email="ada@example.com", password=PASSWORD
        )
        self.key = _key_from(verification_url(self.user))
        self.client.force_authenticate(user=self.user)

    def test_owner_signed_in_verifies_and_gets_the_welcome_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(VERIFY_URL, {"key": self.key}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(is_email_verified(self.user))
        self.assertEqual(len(mail.outbox), 1)  # welcome, via email_confirmed

    def test_key_alone_is_not_enough(self):
        # The victim clicking the link from their inbox, not signed in.
        response = APIClient().post(VERIFY_URL, {"key": self.key}, format="json")

        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(is_email_verified(self.user))

    def test_signed_in_as_another_account_is_refused(self):
        # The victim signed in to their own account, clicking the attacker's link.
        # Same address in another case: registration's duplicate check is
        # exact-case, so only the owner check can tell these accounts apart.
        other = User.objects.create_user(username="victim", email="ADA@example.com")
        client = APIClient()
        client.force_authenticate(user=other)

        response = client.post(VERIFY_URL, {"key": self.key}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(is_email_verified(self.user))

    def test_allauth_confirm_view_rejects_our_key(self):
        # /accounts/confirm-email/<key>/ needs no session; our salt keeps it out.
        self.client.post(f"/accounts/confirm-email/{self.key}/")

        self.assertFalse(is_email_verified(self.user))

    def test_get_changes_nothing(self):
        response = self.client.get(VERIFY_URL, {"key": self.key})

        self.assertEqual(response.status_code, 405)
        self.assertFalse(is_email_verified(self.user))

    def test_bad_or_non_string_key_is_refused(self):
        for key in ("forged", 1, ["x"], None):
            response = self.client.post(VERIFY_URL, {"key": key}, format="json")
            self.assertEqual(response.status_code, 400, key)
        self.assertFalse(is_email_verified(self.user))

    def test_key_for_a_previous_email_is_refused(self):
        self.user.email = "new-address@example.com"
        self.user.save(update_fields=["email"])

        response = self.client.post(VERIFY_URL, {"key": self.key}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(is_email_verified(self.user))

    def test_address_verified_on_another_account_is_refused(self):
        other = User.objects.create_user(username="owner", email="ada@example.com")
        mark_email_verified(other)

        response = self.client.post(VERIFY_URL, {"key": self.key}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(is_email_verified(self.user))

    def test_key_cannot_be_reused(self):
        self.client.post(VERIFY_URL, {"key": self.key}, format="json")

        response = self.client.post(VERIFY_URL, {"key": self.key}, format="json")

        self.assertEqual(response.status_code, 400)


class AllauthMailIsRoutedTest(TestCase):
    """allauth's own verification mails (its /accounts/ signup and login) carry
    our link, so they obey the same session rule."""

    def test_adapter_sends_our_link(self):
        user = User.objects.create_user(
            username="ada", email="ada@example.com", password=PASSWORD
        )
        address = EmailAddress.objects.create(
            user=user, email=user.email, verified=False, primary=True
        )
        confirmation = MagicMock()
        confirmation.email_address = address

        with self.captureOnCommitCallbacks(execute=True):
            CustomAccountAdapter().send_confirmation_mail(None, confirmation, True)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/verify-email?key=", mail.outbox[0].body)
        self.assertNotIn("/accounts/confirm-email/", mail.outbox[0].body)


class ResendVerificationTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="ada", email="ada@example.com", password=PASSWORD
        )
        self.client.force_authenticate(user=self.user)

    def test_unverified_user_gets_a_new_link(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(RESEND_URL)

        self.assertEqual(
            response.data, {"verified": False, "sent": True, "limit_reached": False}
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_verified_user_gets_nothing(self):
        mark_email_verified(self.user)

        response = self.client.post(RESEND_URL)

        self.assertEqual(response.data, {"verified": True, "sent": False})
        self.assertEqual(len(mail.outbox), 0)

    def test_requires_sign_in(self):
        response = APIClient().post(RESEND_URL)

        self.assertIn(response.status_code, (401, 403))


class WebOAuthGuardTest(TestCase):
    """``oauth_views._find_or_create_user`` (the web Google button)."""

    def test_unverified_local_account_is_refused(self):
        User.objects.create_user(
            username="squatter", email="victim@example.com", password=PASSWORD
        )

        with self.assertRaises(oauth_views.UnverifiedLocalAccount):
            oauth_views._find_or_create_user(
                "google", {"email": "victim@example.com", "id": "g-victim"}
            )

    def test_verified_local_account_is_matched(self):
        user = User.objects.create_user(username="real", email="real@example.com")
        mark_email_verified(user)

        result = oauth_views._find_or_create_user(
            "google", {"email": "real@example.com", "id": "g-real"}
        )

        self.assertEqual(result, user)

    def test_created_account_is_verified_so_the_next_login_matches(self):
        first = oauth_views._find_or_create_user(
            "google", {"email": "fresh@example.com", "id": "g-fresh", "given_name": "F"}
        )
        self.assertTrue(is_email_verified(first))

        again = oauth_views._find_or_create_user(
            "google", {"email": "fresh@example.com", "id": "g-fresh", "given_name": "F"}
        )

        self.assertEqual(again, first)

    def test_address_verified_on_another_account_creates_nobody(self):
        # todo 447: the new account could never verify it (one verified holder)
        # and would be refused on its next sign-in. Refuse before creating it.
        # The holder's row differs in case: the check must ignore case.
        _holder_who_moved_on("Taken@example.com")

        result = oauth_views._find_or_create_user(
            "google", {"email": "taken@example.com", "id": "g-taken", "given_name": "T"}
        )

        self.assertIsNone(result)
        self.assertFalse(User.objects.filter(email="taken@example.com").exists())

    def test_verified_account_is_matched_whatever_the_case(self):
        # Review round 1: a case-exact lookup missed this account, and the
        # case-insensitive creation check then refused its own owner.
        user = User.objects.create_user(username="john", email="John@Example.com")
        mark_email_verified(user)

        result = oauth_views._find_or_create_user(
            "google", {"email": "john@example.com", "id": "g-john"}
        )

        self.assertEqual(result, user)
        self.assertEqual(User.objects.count(), 1)

    def test_verified_owner_wins_over_a_parked_case_variant(self):
        # Review round 2: registration compared case-exactly, so a stranger
        # could park "Alice@" beside the real "alice@". Refusing on the
        # ambiguity would lock the owner out; the verified account wins.
        owner = User.objects.create_user(username="alice", email="alice@example.com")
        mark_email_verified(owner)
        User.objects.create_user(username="parked", email="Alice@example.com")

        result = oauth_views._find_or_create_user(
            "google", {"email": "alice@example.com", "id": "g-alice"}
        )

        self.assertEqual(result, owner)

    def test_case_variants_with_no_verified_holder_are_refused(self):
        User.objects.create_user(username="a", email="Dup@example.com")
        User.objects.create_user(username="b", email="dup@example.com")

        result = oauth_views._find_or_create_user(
            "google", {"email": "dup@example.com", "id": "g-dup"}
        )

        self.assertIsNone(result)
        self.assertEqual(User.objects.count(), 2)


def _holder_who_moved_on(email):
    """An account holding ``email`` verified whose User.email has changed."""
    holder = User.objects.create_user(username="holder", email=email)
    mark_email_verified(holder)
    holder.email = "moved@example.com"
    holder.save(update_fields=["email"])
    return holder


class AllauthAdapterGuardTest(TestCase):
    """``oauth_adapters.pre_social_login`` (allauth under /accounts/)."""

    def setUp(self):
        self.adapter = CustomSocialAccountAdapter()
        self.request = RequestFactory().get("/accounts/google/login/callback/")

    def _sociallogin(self, email):
        sociallogin = MagicMock()
        sociallogin.account.provider = "google"
        sociallogin.account.extra_data = {"email": email}
        sociallogin.is_existing = False
        sociallogin.email_addresses = [EmailAddress(email=email, verified=True)]
        sociallogin.connect = MagicMock()
        return sociallogin

    def test_unverified_local_account_is_refused(self):
        User.objects.create_user(
            username="squatter", email="victim@example.com", password=PASSWORD
        )
        sociallogin = self._sociallogin("victim@example.com")

        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(self.request, sociallogin)

        self.assertIn("error=account_unverified", ctx.exception.response.url)
        sociallogin.connect.assert_not_called()


class FirebaseGuardTest(TestCase):
    """``get_or_create_user_from_firebase``'s legacy email fallback."""

    def test_unverified_local_account_is_refused(self):
        squatter = User.objects.create_user(
            username="squatter", email="victim@example.com", password=PASSWORD
        )

        with self.assertRaises(ValueError):
            get_or_create_user_from_firebase(
                firebase_uid="victim-uid",
                firebase_email="victim@example.com",
                email_verified=True,
            )

        squatter.refresh_from_db()
        self.assertFalse(squatter.firebase_uid)

    def test_created_account_is_verified(self):
        user, created = get_or_create_user_from_firebase(
            firebase_uid="new-uid",
            firebase_email="new@example.com",
            email_verified=True,
        )

        self.assertTrue(created)
        self.assertTrue(is_email_verified(user))

    def test_address_verified_on_another_account_creates_nobody(self):
        _holder_who_moved_on("taken@example.com")

        with self.assertRaises(ValueError):
            get_or_create_user_from_firebase(
                firebase_uid="taken-uid",
                firebase_email="taken@example.com",
                email_verified=True,
            )

        self.assertFalse(User.objects.filter(firebase_uid="taken-uid").exists())

    def test_verified_account_is_matched_whatever_the_case(self):
        user = User.objects.create_user(username="john", email="John@Example.com")
        mark_email_verified(user)

        matched, created = get_or_create_user_from_firebase(
            firebase_uid="john-uid",
            firebase_email="john@example.com",
            email_verified=True,
        )

        self.assertFalse(created)
        self.assertEqual(matched, user)

    def test_verified_owner_wins_over_a_parked_case_variant(self):
        owner = User.objects.create_user(username="alice", email="alice@example.com")
        mark_email_verified(owner)
        User.objects.create_user(username="parked", email="Alice@example.com")

        matched, created = get_or_create_user_from_firebase(
            firebase_uid="alice-uid",
            firebase_email="alice@example.com",
            email_verified=True,
        )

        self.assertFalse(created)
        self.assertEqual(matched, owner)


class BackfillMigrationTest(TestCase):
    """Migration 0012. Data only (no schema change), so the function runs
    against the current models rather than a rewound schema."""

    def _run(self):
        migration = importlib.import_module(
            "apps.users.migrations.0012_backfill_verified_email_addresses"
        )
        migration.backfill(django_apps, None)

    def test_provider_created_accounts_are_verified_password_ones_are_not(self):
        firebase = User.objects.create_user(
            username="fb", email="fb@example.com", firebase_uid="uid-1"
        )
        oauth = User.objects.create_user(username="oauth", email="oauth@example.com")
        social = User.objects.create_user(
            username="social", email="social@example.com", password=PASSWORD
        )
        SocialAccount.objects.create(user=social, provider="google", uid="g-1")
        password = User.objects.create_user(
            username="pw", email="pw@example.com", password=PASSWORD
        )

        self._run()

        self.assertTrue(is_email_verified(firebase))
        self.assertTrue(is_email_verified(oauth))  # unusable password: OAuth-made
        self.assertTrue(is_email_verified(social))
        self.assertFalse(is_email_verified(password))
        self.assertTrue(EmailAddress.objects.filter(user=password).exists())

    def test_never_verifies_an_address_already_verified_elsewhere(self):
        holder = User.objects.create_user(username="holder", email="dup@example.com")
        mark_email_verified(holder)
        User.objects.create_user(
            username="dup", email="DUP@example.com", firebase_uid="uid-2"
        )

        self._run()

        self.assertEqual(
            EmailAddress.objects.filter(email__iexact="dup@example.com", verified=True)
            .values_list("user__username", flat=True)
            .get(),
            "holder",
        )
