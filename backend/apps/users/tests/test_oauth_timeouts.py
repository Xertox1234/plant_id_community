"""Every outbound call in the web OAuth callback carries a timeout.

The web process runs under uvicorn, which has no per-request hard kill the way
gunicorn's ``--timeout 120`` had (live forum replies, slice 1). A provider that
stalls a token exchange or profile fetch would otherwise hold a sync thread
for as long as the socket stays open.
"""

from unittest.mock import MagicMock, patch

from apps.users import oauth_views
from apps.users.constants import OAUTH_PROVIDER_TIMEOUT_SECONDS
from django.test import RequestFactory, SimpleTestCase


def _response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


class OAuthProviderTimeoutTest(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/api/auth/oauth/x/callback/")

    def _assert_all_bounded(self, mock):
        self.assertTrue(mock.call_args_list, "expected at least one outbound call")
        for call in mock.call_args_list:
            self.assertEqual(call.kwargs.get("timeout"), OAUTH_PROVIDER_TIMEOUT_SECONDS)

    @patch("requests.get")
    @patch("requests.post")
    def test_google_token_and_profile_calls_carry_a_timeout(self, mock_post, mock_get):
        mock_post.return_value = _response(200, {"access_token": "tok"})
        mock_get.return_value = _response(
            200, {"email": "a@example.com", "verified_email": True}
        )

        oauth_views._handle_google_callback(self.request, code="abc")

        self._assert_all_bounded(mock_post)
        self._assert_all_bounded(mock_get)

    @patch("requests.get")
    @patch("requests.post")
    def test_github_token_profile_and_email_calls_carry_a_timeout(
        self, mock_post, mock_get
    ):
        mock_post.return_value = _response(200, {"access_token": "tok"})
        # No public email, so the /user/emails call runs too.
        mock_get.side_effect = [
            _response(200, {"login": "octo", "email": None}),
            _response(
                200, [{"email": "a@example.com", "primary": True, "verified": True}]
            ),
        ]

        oauth_views._handle_github_callback(self.request, code="abc")

        self._assert_all_bounded(mock_post)
        self.assertEqual(mock_get.call_count, 2)
        self._assert_all_bounded(mock_get)

    def test_timeout_is_well_under_the_old_gunicorn_backstop(self):
        self.assertLessEqual(OAUTH_PROVIDER_TIMEOUT_SECONDS, 60)
