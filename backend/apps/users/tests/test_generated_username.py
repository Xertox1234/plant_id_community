"""Accounts the user did not name get a random username, never one built from
their email.

The forum serves ``username`` to anonymous readers (author blocks, community
stats), so an email-derived username published most of the member's address.
The Firebase path is covered in ``test_firebase_auth.py``; this file covers the
generator, the custom OAuth flow and the allauth social-signup adapters.
"""

from unittest.mock import MagicMock, patch

from apps.users import oauth_views
from apps.users.oauth_adapters import CustomAccountAdapter, CustomSocialAccountAdapter
from apps.users.signup import generate_username
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

User = get_user_model()

HANDLE = r"^member_[a-z2-9]{8}$"


class GenerateUsernameTest(TestCase):
    def test_format(self):
        self.assertRegex(generate_username(), HANDLE)

    def test_draws_again_on_a_taken_handle(self):
        User.objects.create_user(username="member_aaaaaaaa")
        # First draw spells the taken handle, the second a free one.
        draws = iter("a" * 8 + "b" * 8)
        with patch("apps.users.signup.secrets.choice", lambda _: next(draws)):
            self.assertEqual(generate_username(), "member_bbbbbbbb")

    def test_gives_up_rather_than_looping_forever(self):
        User.objects.create_user(username="member_aaaaaaaa")
        with patch("apps.users.signup.secrets.choice", lambda _: "a"):
            with self.assertRaises(RuntimeError):
                generate_username()


class OAuthFindOrCreateUsernameTest(TestCase):
    """The custom ``/api/auth/oauth/<provider>/callback/`` flow."""

    def test_google_signup_username_is_not_the_email_local_part(self):
        user = oauth_views._find_or_create_user(
            "google",
            {"email": "jane.doe@example.com", "id": "g-1", "given_name": "Jane"},
        )

        self.assertIsNotNone(user)
        self.assertRegex(user.username, HANDLE)
        self.assertNotIn("jane", user.username)
        self.assertEqual(user.first_name, "Jane")

    def test_github_signup_username_is_not_the_login(self):
        user = oauth_views._find_or_create_user(
            "github",
            {"email": "jane@example.com", "id": 7, "login": "janedoe", "name": "J D"},
        )

        self.assertIsNotNone(user)
        self.assertRegex(user.username, HANDLE)
        self.assertEqual((user.first_name, user.last_name), ("J", "D"))


class AllauthSocialSignupUsernameTest(TestCase):
    """allauth's default builds the username from the name or email local part;
    the adapters replace that with a generated handle."""

    def setUp(self):
        self.request = RequestFactory().get("/accounts/github/login/callback/")

    def test_social_populate_user_drops_the_provider_username(self):
        sociallogin = MagicMock()
        sociallogin.user = User()

        user = CustomSocialAccountAdapter().populate_user(
            self.request,
            sociallogin,
            {"username": "janedoe", "email": "jane@example.com", "name": "Jane"},
        )

        self.assertEqual(user.username, "")
        self.assertEqual(user.email, "jane@example.com")

    def test_account_populate_username_generates_a_handle(self):
        user = User(email="jane.doe@example.com", first_name="Jane")

        CustomAccountAdapter().populate_username(self.request, user)

        self.assertRegex(user.username, HANDLE)

    def test_account_populate_username_keeps_a_chosen_username(self):
        user = User(username="chosen", email="jane@example.com")

        CustomAccountAdapter().populate_username(self.request, user)

        self.assertEqual(user.username, "chosen")
