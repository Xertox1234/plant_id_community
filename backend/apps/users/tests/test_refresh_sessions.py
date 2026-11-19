"""Refresh-session rules (todo 705 M5 and M6, audit 2026-11-10).

* An inactive account gets 401 at refresh.
* A refresh session lives at most 30 days from its sign-in (owner decision
  2026-11-17), however often it rotates.
* Reusing a rotated refresh token ends every session of the account; a reuse
  inside the race grace (two tabs, one cookie) is refused without revoking.
"""

import time
from datetime import timedelta

from apps.users.authentication import issue_refresh_token
from apps.users.constants import (
    ACCOUNT_DISABLED_CODE,
    REFRESH_REUSE_GRACE_SECONDS,
    REFRESH_SESSION_MAX_AGE_SECONDS,
    REFRESH_SESSION_START_CLAIM,
    REFRESH_TOKEN_REUSED_CODE,
    SESSION_EXPIRED_CODE,
)
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from freezegun import freeze_time
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

REFRESH_URL = "/api/v1/auth/token/refresh/"
DAY = 24 * 60 * 60


class RefreshSessionTestBase(TestCase):
    client: APIClient

    def setUp(self):
        cache.clear()  # the refresh endpoint is IP rate limited
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="sessions",
            email="sessions@example.com",
            password="Sessions-Pa55word!",  # pragma: allowlist secret
        )

    def _refresh_with(self, token) -> object:
        self.client.cookies["refresh_token"] = str(token)
        return self.client.post(REFRESH_URL)

    def _live_tokens(self) -> int:
        return OutstandingToken.objects.filter(
            user=self.user, blacklistedtoken__isnull=True
        ).count()


class InactiveUserRefreshTest(RefreshSessionTestBase):
    def test_an_inactive_user_gets_401_at_refresh(self):
        token = issue_refresh_token(self.user)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self._refresh_with(token)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], ACCOUNT_DISABLED_CODE)
        self.assertEqual(response.cookies["refresh_token"].value, "")
        # The presented token is burned too.
        self.assertTrue(
            BlacklistedToken.objects.filter(token__jti=token["jti"]).exists()
        )

    def test_an_active_user_refreshes(self):
        response = self._refresh_with(issue_refresh_token(self.user))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AbsoluteSessionCapTest(RefreshSessionTestBase):
    def test_the_cap_is_thirty_days(self):
        self.assertEqual(REFRESH_SESSION_MAX_AGE_SECONDS, 30 * DAY)

    def test_a_rotation_keeps_the_session_start(self):
        start = int(time.time()) - 3 * DAY
        response = self._refresh_with(issue_refresh_token(self.user, start))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rotated = RefreshToken(response.cookies["refresh_token"].value)
        self.assertEqual(rotated[REFRESH_SESSION_START_CLAIM], start)

    def test_a_sign_in_starts_a_new_session(self):
        before = int(time.time())
        token = issue_refresh_token(self.user)
        self.assertGreaterEqual(token[REFRESH_SESSION_START_CLAIM], before)

    def test_a_refresh_past_the_cap_is_refused(self):
        token = issue_refresh_token(self.user)
        # A token whose own exp is still in the future, from a session that
        # began 31 days ago: only the cap can refuse it.
        token[REFRESH_SESSION_START_CLAIM] = int(time.time()) - 31 * DAY
        token.set_exp(lifetime=timedelta(days=1))

        response = self._refresh_with(token)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], SESSION_EXPIRED_CODE)
        self.assertNotIn(
            "access_token", {k for k, v in response.cookies.items() if v.value}
        )

    def test_a_refresh_just_inside_the_cap_succeeds(self):
        start = int(time.time()) - 29 * DAY
        response = self._refresh_with(issue_refresh_token(self.user, start))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_token_never_outlives_its_session(self):
        start = int(time.time()) - 29 * DAY
        token = issue_refresh_token(self.user, start)
        self.assertEqual(token["exp"], start + REFRESH_SESSION_MAX_AGE_SECONDS)

    def test_the_rotated_cookie_dies_with_the_session(self):
        start = int(time.time()) - 29 * DAY
        response = self._refresh_with(issue_refresh_token(self.user, start))
        self.assertLessEqual(int(response.cookies["refresh_token"]["max-age"]), DAY)

    def test_a_token_from_before_the_claim_uses_its_iat(self):
        token = issue_refresh_token(self.user)
        del token[REFRESH_SESSION_START_CLAIM]
        response = self._refresh_with(token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rotated = RefreshToken(response.cookies["refresh_token"].value)
        self.assertEqual(rotated[REFRESH_SESSION_START_CLAIM], token["iat"])


class RotatedTokenReuseTest(RefreshSessionTestBase):
    def test_reusing_a_rotated_token_ends_the_session(self):
        with freeze_time() as frozen:
            first = issue_refresh_token(self.user)
            other_device = issue_refresh_token(self.user)  # a second session
            rotated = self._refresh_with(first)
            self.assertEqual(rotated.status_code, status.HTTP_200_OK)
            new_token = rotated.cookies["refresh_token"].value
            self.assertEqual(self._live_tokens(), 2)

            frozen.tick(REFRESH_REUSE_GRACE_SECONDS + 5)
            reuse = self._refresh_with(first)

            self.assertEqual(reuse.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(reuse.data["code"], REFRESH_TOKEN_REUSED_CODE)
            self.assertEqual(self._live_tokens(), 0)
            # The token the rotation issued, and the other session, are dead.
            for token in (new_token, other_device):
                self.assertEqual(
                    self._refresh_with(token).status_code,
                    status.HTTP_401_UNAUTHORIZED,
                )

    def test_a_reuse_inside_the_race_grace_revokes_nothing(self):
        with freeze_time():
            first = issue_refresh_token(self.user)
            rotated = self._refresh_with(first)
            self.assertEqual(rotated.status_code, status.HTTP_200_OK)
            new_token = rotated.cookies["refresh_token"].value

            reuse = self._refresh_with(first)

            self.assertEqual(reuse.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertNotEqual(reuse.data.get("code"), REFRESH_TOKEN_REUSED_CODE)
            self.assertEqual(self._live_tokens(), 1)
            self.assertEqual(
                self._refresh_with(new_token).status_code, status.HTTP_200_OK
            )

    def test_a_forged_token_naming_the_user_revokes_nothing(self):
        with freeze_time() as frozen:
            first = issue_refresh_token(self.user)
            self._refresh_with(first)
            frozen.tick(REFRESH_REUSE_GRACE_SECONDS + 5)
            live_before = self._live_tokens()
            forged = str(first)[:-4] + (
                "AAAA" if not str(first).endswith("AAAA") else "BBBB"
            )

            response = self._refresh_with(forged)

            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(self._live_tokens(), live_before)


class NonRotationBlacklistIsNotReuseTest(RefreshSessionTestBase):
    """Only a token a refresh ROTATED counts as reused (todo 705 review).

    A token blacklisted by a revocation, a logout or a refused refresh is a
    plain 401 when it comes back, however late, and ends no other session.
    """

    def _assert_plain_401_and_other_session_lives(self, stale, survivor):
        response = self._refresh_with(stale)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(response.data.get("code"), REFRESH_TOKEN_REUSED_CODE)
        self.assertEqual(self._refresh_with(survivor).status_code, status.HTTP_200_OK)

    def test_a_token_revoked_by_a_first_provider_link_is_not_reuse(self):
        # The probe: browser A's token is revoked when a password user first
        # links Google in browser B, which then signs in afresh.
        from apps.users.account_links import revoke_refresh_tokens

        with freeze_time() as frozen:
            browser_a = issue_refresh_token(self.user)
            revoke_refresh_tokens(self.user)
            browser_b = issue_refresh_token(self.user)
            frozen.tick(REFRESH_REUSE_GRACE_SECONDS + 5)

            self._assert_plain_401_and_other_session_lives(browser_a, browser_b)

    def test_a_logged_out_token_is_not_reuse(self):
        with freeze_time() as frozen:
            logged_out = issue_refresh_token(self.user)
            other = issue_refresh_token(self.user)
            self.client.force_authenticate(self.user)
            self.client.cookies["refresh_token"] = str(logged_out)
            self.assertEqual(
                self.client.post("/api/v1/auth/logout/").status_code,
                status.HTTP_200_OK,
            )
            self.client.force_authenticate(None)
            self.assertTrue(
                BlacklistedToken.objects.filter(token__jti=logged_out["jti"]).exists()
            )
            frozen.tick(REFRESH_REUSE_GRACE_SECONDS + 5)

            self._assert_plain_401_and_other_session_lives(logged_out, other)

    def test_a_token_burned_by_a_refused_refresh_is_not_reuse(self):
        with freeze_time() as frozen:
            expired = issue_refresh_token(self.user)
            expired[REFRESH_SESSION_START_CLAIM] = int(time.time()) - 31 * DAY
            expired.set_exp(lifetime=timedelta(days=1))
            other = issue_refresh_token(self.user)
            refused = self._refresh_with(expired)
            self.assertEqual(refused.data["code"], SESSION_EXPIRED_CODE)
            frozen.tick(REFRESH_REUSE_GRACE_SECONDS + 5)

            self._assert_plain_401_and_other_session_lives(expired, other)

    def test_only_the_rotation_marks_a_token(self):
        from apps.users.models import RotatedRefreshToken

        token = issue_refresh_token(self.user)
        self.assertEqual(self._refresh_with(token).status_code, status.HTTP_200_OK)
        self.assertEqual(
            list(RotatedRefreshToken.objects.values_list("token__jti", flat=True)),
            [token["jti"]],
        )
