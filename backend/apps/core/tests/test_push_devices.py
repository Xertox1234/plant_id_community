"""Per-device push registrations and fan-out (todo 621).

Registration ownership (two devices, sign-out, cross-account reuse, token
rotation, concurrent registration), the legacy ``ForumProfile.fcm_token``
migration and deploy skew, and the forum and care senders reaching every
device with per-device failure handling. FCM is mocked throughout; every
token is an obviously fake string.
"""

import importlib
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

# Imported here, not first by a request inside a test that patches
# ``apps.core.push_devices.register_device``: the API module binds that name
# on import, so a first import under the patch would keep the mock for good.
from apps.core.api import push_devices as _push_devices_api  # noqa: F401
from apps.core.models import PushDevice
from apps.core.push_devices import (
    device_tokens_for_users,
    forget_device_token,
    register_device,
    unregister_device,
)
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail_forum.models import ForumProfile

User = get_user_model()

REGISTER = "/api/v1/push-devices/"
UNREGISTER = "/api/v1/push-devices/unregister/"
ME_PROFILE = "/api/v1/forum/me/profile/"


def _tokens(user):
    return list(
        PushDevice.objects.filter(user=user)
        .order_by("created_at", "pk")
        .values_list("token", flat=True)
    )


def _legacy(user):
    return ForumProfile.for_user(user).fcm_token


def _set_legacy(user, token):
    """Write the legacy column as an app build from before todo 621 did."""
    profile = ForumProfile.for_user(user)
    profile.fcm_token = token
    profile.save(update_fields=["fcm_token"])


class RegistrationOwnershipTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="a@x.com")
        self.bob = User.objects.create_user(username="bob", email="b@x.com")

    def test_two_devices_of_one_account_both_stay_registered(self):
        register_device(self.alice, "fake-token-phone", "install-phone", "ios")
        register_device(self.alice, "fake-token-tablet", "install-tablet", "android")

        self.assertEqual(_tokens(self.alice), ["fake-token-phone", "fake-token-tablet"])
        self.assertEqual(
            device_tokens_for_users([self.alice.pk]),
            {self.alice.pk: ["fake-token-phone", "fake-token-tablet"]},
        )

    def test_sign_out_on_either_device_removes_only_that_device(self):
        register_device(self.alice, "fake-token-phone", "install-phone")
        register_device(self.alice, "fake-token-tablet", "install-tablet")

        self.assertEqual(unregister_device(self.alice, "fake-token-tablet"), 1)
        self.assertEqual(_tokens(self.alice), ["fake-token-phone"])

        self.assertEqual(unregister_device(self.alice, "fake-token-phone"), 1)
        self.assertEqual(_tokens(self.alice), [])

    def test_a_token_reused_by_another_account_moves_to_it(self):
        register_device(self.alice, "fake-token-shared", "install-shared")
        _set_legacy(self.alice, "fake-token-shared")
        register_device(self.alice, "fake-token-other", "install-other")

        register_device(self.bob, "fake-token-shared", "install-shared")

        self.assertEqual(_tokens(self.bob), ["fake-token-shared"])
        # Alice keeps her other device and loses only the shared one, in both
        # stores.
        self.assertEqual(_tokens(self.alice), ["fake-token-other"])
        self.assertEqual(_legacy(self.alice), "")

    def test_alice_cannot_remove_bobs_device_by_its_token(self):
        register_device(self.bob, "fake-token-bob", "install-bob")

        self.assertEqual(unregister_device(self.alice, "fake-token-bob"), 0)
        self.assertEqual(_tokens(self.bob), ["fake-token-bob"])

    def test_a_rotated_token_replaces_the_same_installation_only(self):
        register_device(self.alice, "fake-token-old", "install-phone")
        register_device(self.alice, "fake-token-tablet", "install-tablet")

        register_device(self.alice, "fake-token-new", "install-phone")

        self.assertEqual(
            sorted(_tokens(self.alice)), ["fake-token-new", "fake-token-tablet"]
        )

    def test_a_late_sign_out_of_the_old_token_keeps_the_rotated_one(self):
        register_device(self.alice, "fake-token-old", "install-phone")
        register_device(self.alice, "fake-token-new", "install-phone")

        self.assertEqual(unregister_device(self.alice, "fake-token-old"), 0)
        self.assertEqual(_tokens(self.alice), ["fake-token-new"])

    def test_an_installation_that_switches_accounts_moves_with_its_token(self):
        register_device(self.alice, "fake-token-a", "install-shared")

        register_device(self.bob, "fake-token-b", "install-shared")

        self.assertEqual(_tokens(self.alice), [])
        self.assertEqual(_tokens(self.bob), ["fake-token-b"])

    def test_re_registering_is_idempotent(self):
        register_device(self.alice, "fake-token-phone", "install-phone")
        register_device(self.alice, "fake-token-phone", "install-phone")

        self.assertEqual(PushDevice.objects.count(), 1)

    def test_a_registration_that_loses_a_race_retries_and_converges(self):
        """Two concurrent registrations of one token: the loser's upsert hits
        the unique constraint, and its retry releases the winner's row."""
        real = PushDevice.objects.update_or_create
        calls = {"n": 0}

        def racing(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                # The concurrent winner commits Bob's row first.
                PushDevice.objects.create(
                    user=self.bob, token="fake-token-raced", installation_id=None
                )
                raise IntegrityError("duplicate key value")
            return real(**kwargs)

        with patch.object(PushDevice.objects, "update_or_create", side_effect=racing):
            register_device(self.alice, "fake-token-raced", "install-a")

        self.assertEqual(calls["n"], 2)
        self.assertEqual(_tokens(self.alice), ["fake-token-raced"])
        self.assertEqual(_tokens(self.bob), [])

    def test_a_registration_that_keeps_losing_raises(self):
        with patch.object(
            PushDevice.objects,
            "update_or_create",
            side_effect=IntegrityError("duplicate key value"),
        ):
            with self.assertRaises(IntegrityError):
                register_device(self.alice, "fake-token-raced", "install-a")

    def test_a_dead_token_is_forgotten_for_its_account_only(self):
        register_device(self.alice, "fake-token-dead", "install-1")
        register_device(self.alice, "fake-token-live", "install-2")
        _set_legacy(self.alice, "fake-token-dead")

        self.assertEqual(forget_device_token(self.bob.pk, "fake-token-dead"), 0)
        self.assertEqual(forget_device_token(self.alice.pk, "fake-token-dead"), 2)

        self.assertEqual(_tokens(self.alice), ["fake-token-live"])
        self.assertEqual(_legacy(self.alice), "")


class LegacyTokenSkewTest(TestCase):
    """Deploy skew: the legacy column is still read and still written."""

    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="a@x.com")

    def test_the_send_targets_the_legacy_token_and_devices_once_each(self):
        _set_legacy(self.alice, "fake-token-phone")
        register_device(self.alice, "fake-token-phone", "install-phone")
        register_device(self.alice, "fake-token-tablet", "install-tablet")

        self.assertEqual(
            device_tokens_for_users([self.alice.pk]),
            {self.alice.pk: ["fake-token-phone", "fake-token-tablet"]},
        )

    def test_a_legacy_only_registration_is_still_a_device(self):
        _set_legacy(self.alice, "fake-token-old-build")

        self.assertEqual(
            device_tokens_for_users([self.alice.pk]),
            {self.alice.pk: ["fake-token-old-build"]},
        )

    def test_the_migration_copies_every_legacy_token(self):
        bob = User.objects.create_user(username="bob", email="b@x.com")
        carol = User.objects.create_user(username="carol", email="c@x.com")
        ForumProfile.for_user(carol)
        _set_legacy(self.alice, "fake-token-a")
        _set_legacy(bob, "fake-token-b")
        # An already-copied row (the step re-run) is not duplicated.
        PushDevice.objects.create(user=bob, token="fake-token-b")

        migration = importlib.import_module("apps.core.migrations.0006_pushdevice")
        migration.copy_legacy_tokens(django_apps, None)

        self.assertEqual(_tokens(self.alice), ["fake-token-a"])
        self.assertEqual(_tokens(bob), ["fake-token-b"])
        self.assertEqual(_tokens(carol), [])
        # The legacy column is untouched: an older backend still reads it.
        self.assertEqual(_legacy(self.alice), "fake-token-a")


class PushDeviceApiTest(TestCase):
    def setUp(self):
        cache.clear()  # the per-user rate limit lives in the cache
        self.alice = User.objects.create_user(username="alice", email="a@x.com")
        self.bob = User.objects.create_user(username="bob", email="b@x.com")
        self.client = APIClient()

    def test_registration_needs_a_signed_in_user(self):
        response = self.client.post(REGISTER, {"token": "fake-token"}, format="json")

        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(PushDevice.objects.exists())

    def test_register_two_devices_then_sign_out_of_one(self):
        self.client.force_authenticate(self.alice)

        for token, install in (
            ("fake-token-1", "install-1"),
            ("fake-token-2", "install-2"),
        ):
            response = self.client.post(
                REGISTER,
                {"token": token, "installation_id": install, "platform": "ios"},
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.data)
            # The token is a credential: never echoed back.
            self.assertNotIn(token, response.content.decode())

        response = self.client.post(
            UNREGISTER, {"token": "fake-token-1"}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"removed": 1})
        self.assertEqual(_tokens(self.alice), ["fake-token-2"])

    def test_signing_out_of_a_device_another_account_now_holds_removes_nothing(self):
        register_device(self.bob, "fake-token-bob", "install-bob")
        self.client.force_authenticate(self.alice)

        response = self.client.post(
            UNREGISTER, {"token": "fake-token-bob"}, format="json"
        )

        self.assertEqual(response.data, {"removed": 0})
        self.assertEqual(_tokens(self.bob), ["fake-token-bob"])

    def test_a_missing_or_bad_token_is_a_400(self):
        self.client.force_authenticate(self.alice)

        for body in (
            {},
            {"token": ""},
            {"token": "x" * 256},
            {"token": "t", "platform": "pc"},
        ):
            with self.subTest(body=body):
                response = self.client.post(REGISTER, body, format="json")
                self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.client.post(UNREGISTER, {}, format="json").status_code, 400
        )

    def test_a_lost_race_is_a_409_the_client_can_retry(self):
        self.client.force_authenticate(self.alice)
        with patch(
            "apps.core.api.push_devices.register_device",
            side_effect=IntegrityError("duplicate key value"),
        ):
            response = self.client.post(
                REGISTER, {"token": "fake-token"}, format="json"
            )

        self.assertEqual(response.status_code, 409)

    def test_the_legacy_profile_patch_is_mirrored_per_device(self):
        """An app build from before todo 621 still PATCHes ``fcm_token``."""
        register_device(self.alice, "fake-token-new-build", "install-new")
        self.client.force_authenticate(self.alice)

        response = self.client.patch(
            ME_PROFILE, {"fcm_token": "fake-token-old-build"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            sorted(_tokens(self.alice)),
            ["fake-token-new-build", "fake-token-old-build"],
        )

        # The old build signs out: only its own device goes.
        response = self.client.patch(ME_PROFILE, {"fcm_token": ""}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(_tokens(self.alice), ["fake-token-new-build"])
        self.assertEqual(_legacy(self.alice), "")

    def test_two_legacy_builds_then_the_first_signs_out(self):
        """Two pre-621 builds share the one-token column, as they always did.

        A's write is replaced by B's, so A's row goes with it; A's later
        sign-out clears the column (B's token, the only one it can name).
        The signed-out build must not be left receiving pushes.
        """
        register_device(self.alice, "fake-token-new-build", "install-new")
        self.client.force_authenticate(self.alice)

        for token in ("fake-token-legacy-a", "fake-token-legacy-b"):
            response = self.client.patch(
                ME_PROFILE, {"fcm_token": token}, format="json"
            )
            self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            sorted(_tokens(self.alice)),
            ["fake-token-legacy-b", "fake-token-new-build"],
        )
        self.assertEqual(_legacy(self.alice), "fake-token-legacy-b")

        # Re-sending the same token keeps its row.
        response = self.client.patch(
            ME_PROFILE, {"fcm_token": "fake-token-legacy-b"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("fake-token-legacy-b", _tokens(self.alice))

        # A signs out: no token of A remains, and the 621 device is untouched.
        response = self.client.patch(ME_PROFILE, {"fcm_token": ""}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(_tokens(self.alice), ["fake-token-new-build"])
        self.assertEqual(_legacy(self.alice), "")

    def test_an_old_build_never_removes_a_phone_that_upgraded(self):
        """Phone B wrote the column as a pre-621 build, then upgraded.

        Its registration with an installation id takes the token out of the
        column, so old-build phone A replacing or clearing the column leaves
        B's row alone.
        """
        _set_legacy(self.alice, "fake-token-phone-b")
        register_device(self.alice, "fake-token-phone-b", "install-b")
        self.assertEqual(_legacy(self.alice), "")
        self.client.force_authenticate(self.alice)

        response = self.client.patch(
            ME_PROFILE, {"fcm_token": "fake-token-legacy-a"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            sorted(_tokens(self.alice)),
            ["fake-token-legacy-a", "fake-token-phone-b"],
        )

        # A signs out: only A's own legacy row goes.
        response = self.client.patch(ME_PROFILE, {"fcm_token": ""}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(_tokens(self.alice), ["fake-token-phone-b"])

    def test_an_upgraded_phone_signing_out_through_the_legacy_path_is_removed(
        self,
    ):
        """An upgraded build falls back to the profile PATCH on a 404 (skew).

        Its later legacy sign-out must remove its row, and the legacy write
        must not erase the installation id it registered with.
        """
        register_device(self.alice, "fake-token-phone-b", "install-b", platform="ios")
        self.client.force_authenticate(self.alice)

        response = self.client.patch(
            ME_PROFILE, {"fcm_token": "fake-token-phone-b"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        device = PushDevice.objects.get(token="fake-token-phone-b")
        self.assertEqual(device.installation_id, "install-b")
        self.assertEqual(device.platform, "ios")

        response = self.client.patch(ME_PROFILE, {"fcm_token": ""}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(_tokens(self.alice), [])

    def test_a_rotation_takes_the_old_token_out_of_the_column(self):
        """The column holds B1 (a skew fallback wrote it); B rotates to B2."""
        register_device(self.alice, "fake-token-b1", "install-b")
        _set_legacy(self.alice, "fake-token-b1")

        register_device(self.alice, "fake-token-b2", "install-b")

        self.assertEqual(_tokens(self.alice), ["fake-token-b2"])
        self.assertEqual(_legacy(self.alice), "")

    def test_a_shared_phone_rotation_clears_the_previous_account_column(self):
        """Bob's phone (T1, install X) moves to Alice on a rotated T2.

        Bob's row goes, and T1 leaves Bob's column too, or Bob's pushes keep
        reaching the phone Alice now uses.
        """
        bob = User.objects.create_user(username="bob-rot", password="x")
        register_device(bob, "fake-token-t1", "install-x")
        _set_legacy(bob, "fake-token-t1")

        register_device(self.alice, "fake-token-t2", "install-x")

        self.assertEqual(_tokens(bob), [])
        self.assertEqual(_legacy(bob), "")
        self.assertEqual(_tokens(self.alice), ["fake-token-t2"])

    def test_an_upgraded_registration_without_an_installation_id(self):
        """Secure storage failed: no id, but it came through /push-devices/.

        It still takes the token out of its own column, so an old build's
        later write cannot release it.
        """
        _set_legacy(self.alice, "fake-token-a")
        register_device(self.alice, "fake-token-a", platform="ios")
        self.assertEqual(_legacy(self.alice), "")
        self.client.force_authenticate(self.alice)

        response = self.client.patch(
            ME_PROFILE, {"fcm_token": "fake-token-old-b"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            sorted(_tokens(self.alice)), ["fake-token-a", "fake-token-old-b"]
        )
        self.assertEqual(
            PushDevice.objects.get(token="fake-token-old-b").platform, "legacy"
        )

    def test_a_profile_patch_without_a_token_leaves_devices_alone(self):
        register_device(self.alice, "fake-token-1", "install-1")
        self.client.force_authenticate(self.alice)

        response = self.client.patch(ME_PROFILE, {"bio": "Hello"}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(_tokens(self.alice), ["fake-token-1"])

    def test_a_failed_mirror_rolls_back_the_column_write(self):
        """Todo 650 #4: the column and its mirror commit together."""
        from django.db import OperationalError

        self.client.force_authenticate(self.alice)
        self.client.raise_request_exception = False
        with patch(
            "apps.core.push_devices.register_device",
            side_effect=OperationalError("connection lost"),
        ):
            response = self.client.patch(
                ME_PROFILE, {"fcm_token": "fake-token-old-build"}, format="json"
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(_legacy(self.alice), "")
        self.assertEqual(_tokens(self.alice), [])

    def test_a_failed_release_rolls_back_the_replacing_write(self):
        from django.db import OperationalError

        _set_legacy(self.alice, "fake-token-first")
        register_device(self.alice, "fake-token-first", platform="legacy", legacy=True)
        self.client.force_authenticate(self.alice)
        self.client.raise_request_exception = False
        with patch(
            "apps.core.push_devices.unregister_device",
            side_effect=OperationalError("connection lost"),
        ):
            self.client.patch(
                ME_PROFILE, {"fcm_token": "fake-token-second"}, format="json"
            )

        self.assertEqual(_legacy(self.alice), "fake-token-first")
        self.assertEqual(_tokens(self.alice), ["fake-token-first"])

    def test_registration_is_rate_limited_per_account(self):
        """Todo 650 #3: 30 an hour per account, then 429."""
        self.client.force_authenticate(self.alice)
        statuses = [
            self.client.post(
                REGISTER, {"token": "fake-token-1"}, format="json"
            ).status_code
            for _ in range(31)
        ]
        self.assertEqual(statuses, [200] * 30 + [429])

        # Per account: another account is not limited.
        self.client.force_authenticate(self.bob)
        response = self.client.post(REGISTER, {"token": "fake-token-2"}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_sign_out_is_rate_limited_per_account(self):
        self.client.force_authenticate(self.alice)
        statuses = [
            self.client.post(
                UNREGISTER, {"token": "fake-token-1"}, format="json"
            ).status_code
            for _ in range(31)
        ]
        self.assertEqual(statuses, [200] * 30 + [429])

        self.client.force_authenticate(self.bob)
        response = self.client.post(
            UNREGISTER, {"token": "fake-token-1"}, format="json"
        )
        self.assertEqual(response.status_code, 200)


class DeviceCapTest(TestCase):
    """Owner decision 2026-10-16 (todo 650 #5, #6): an account keeps at most
    ``PUSH_DEVICE_MAX_PER_ACCOUNT`` devices; a registration past it evicts the
    oldest, silently, and the send path never targets more."""

    def setUp(self):
        from apps.core.constants import PUSH_DEVICE_MAX_PER_ACCOUNT

        self.cap = PUSH_DEVICE_MAX_PER_ACCOUNT
        self.alice = User.objects.create_user(username="alice", email="a@x.com")
        self.bob = User.objects.create_user(username="bob", email="b@x.com")
        for i in range(self.cap):
            register_device(self.alice, f"fake-token-{i}", f"install-{i}")

    def test_the_cap_is_ten(self):
        self.assertEqual(self.cap, 10)

    def test_a_registration_past_the_cap_evicts_the_oldest(self):
        register_device(self.alice, "fake-token-new", "install-new")

        self.assertEqual(
            _tokens(self.alice),
            [f"fake-token-{i}" for i in range(1, self.cap)] + ["fake-token-new"],
        )

    def test_re_registering_an_old_device_evicts_nothing(self):
        register_device(self.alice, "fake-token-0", "install-0")

        self.assertEqual(
            _tokens(self.alice), [f"fake-token-{i}" for i in range(self.cap)]
        )

    def test_the_device_being_registered_is_never_the_one_evicted(self):
        # Over the cap from before it (a pre-cap row), the account's OLDEST
        # device re-registers: it stays, and the next oldest go.
        PushDevice.objects.create(user=self.alice, token="fake-token-pre-cap")

        register_device(self.alice, "fake-token-0", "install-0")

        self.assertEqual(
            _tokens(self.alice),
            ["fake-token-0"]
            + [f"fake-token-{i}" for i in range(2, self.cap)]
            + ["fake-token-pre-cap"],
        )

    def test_an_evicted_token_leaves_the_legacy_column(self):
        _set_legacy(self.alice, "fake-token-0")

        register_device(self.alice, "fake-token-new", "install-new")

        self.assertEqual(_legacy(self.alice), "")
        self.assertNotIn(
            "fake-token-0", device_tokens_for_users([self.alice.pk])[self.alice.pk]
        )

    def test_another_account_is_untouched(self):
        register_device(self.bob, "fake-token-bob", "install-bob")

        register_device(self.alice, "fake-token-new", "install-new")

        self.assertEqual(_tokens(self.bob), ["fake-token-bob"])

    def test_the_api_evicts_silently(self):
        cache.clear()
        client = APIClient()
        client.force_authenticate(self.alice)

        response = client.post(
            REGISTER,
            {"token": "fake-token-new", "installation_id": "install-new"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"registered": True})
        self.assertEqual(len(_tokens(self.alice)), self.cap)

    def test_the_send_path_targets_at_most_the_newest_devices(self):
        # Rows from before the cap, kept until the account next registers.
        now = timezone.now()
        for i in range(25):
            junk = PushDevice.objects.create(
                user=self.alice, token=f"fake-token-junk-{i}"
            )
            # created_at is auto_now_add: set it after the insert.
            PushDevice.objects.filter(pk=junk.pk).update(
                created_at=now + timedelta(seconds=i + 1)
            )
        _set_legacy(self.alice, "fake-token-legacy")

        tokens = device_tokens_for_users([self.alice.pk])[self.alice.pk]

        self.assertEqual(
            tokens,
            ["fake-token-legacy"]
            + [f"fake-token-junk-{i}" for i in range(25 - self.cap, 25)],
        )


def _fcm(send=None):
    fcm = MagicMock()
    if send is not None:
        fcm.send.side_effect = send
    return fcm


def _sent_tokens(fcm):
    return [c.kwargs["token"] for c in fcm.Message.call_args_list]


def _failing_on(failures):
    """A mock FCM client whose send raises ``failures[token]`` for the listed
    device tokens and succeeds for every other one."""
    fcm = MagicMock()
    fcm.Message.side_effect = lambda **kwargs: MagicMock(token=kwargs["token"])

    def send(message):
        if message.token in failures:
            raise failures[message.token]
        return "projects/x/messages/1"

    fcm.send.side_effect = send
    return fcm


class ForumFanOutTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="a@x.com")
        ForumProfile.for_user(self.alice)
        register_device(self.alice, "fake-token-phone", "install-phone")
        register_device(self.alice, "fake-token-tablet", "install-tablet")

    def _patches(self, fcm):
        return (
            patch("apps.core.firebase_config.is_firebase_available", return_value=True),
            patch("apps.core.firebase_config.get_fcm_client", return_value=fcm),
        )

    def _send_single(self, fcm, **kwargs):
        from apps.forum_host.tasks import send_forum_push

        a, b = self._patches(fcm)
        with a, b, patch("apps.forum_host.tasks.send_forum_push.delay") as handoff:
            send_forum_push("reply_added", self.alice.pk, {"topic_id": "1"}, **kwargs)
        return handoff

    def _send_batch(self, fcm):
        from apps.forum_host.tasks import send_forum_push_batch

        a, b = self._patches(fcm)
        with a, b, patch("apps.forum_host.tasks.send_forum_push.delay") as handoff:
            send_forum_push_batch("reply_added", [self.alice.pk], {"topic_id": "1"})
        return handoff

    def test_both_devices_receive_a_forum_push(self):
        for send in (self._send_single, self._send_batch):
            with self.subTest(path=send.__name__):
                fcm = _fcm()
                send(fcm)
                self.assertEqual(
                    _sent_tokens(fcm), ["fake-token-phone", "fake-token-tablet"]
                )

    def test_a_dead_token_clears_only_that_device(self):
        from firebase_admin import messaging

        for send in (self._send_single, self._send_batch):
            with self.subTest(path=send.__name__):
                fcm = _failing_on(
                    {"fake-token-phone": messaging.UnregisteredError("gone")}
                )

                handoff = send(fcm)

                self.assertEqual(_tokens(self.alice), ["fake-token-tablet"])
                handoff.assert_not_called()
                # Restore the phone for the next path.
                register_device(self.alice, "fake-token-phone", "install-phone")

    def test_a_transient_failure_retries_that_device_only(self):
        from firebase_admin import exceptions as fb_exceptions

        for send in (self._send_single, self._send_batch):
            with self.subTest(path=send.__name__):
                fcm = _failing_on(
                    {"fake-token-tablet": fb_exceptions.UnavailableError("down")}
                )

                handoff = send(fcm)

                # The phone got it; only the tablet is retried, alone.
                handoff.assert_called_once_with(
                    "reply_added",
                    self.alice.pk,
                    {"topic_id": "1"},
                    token="fake-token-tablet",
                )
                self.assertEqual(
                    sorted(_tokens(self.alice)),
                    ["fake-token-phone", "fake-token-tablet"],
                )

    def test_a_refused_device_retry_enqueue_still_hands_off_the_rest(self):
        """Todo 650 #2: the single path guards each hand-off, as the batch
        path already did (todo 643 #1)."""
        from apps.forum_host.tasks import send_forum_push
        from firebase_admin import exceptions as fb_exceptions
        from kombu.exceptions import OperationalError as BrokerError

        register_device(self.alice, "fake-token-watch", "install-watch")
        fcm = _failing_on(
            {
                "fake-token-tablet": fb_exceptions.UnavailableError("down"),
                "fake-token-watch": fb_exceptions.UnavailableError("down"),
            }
        )
        a, b = self._patches(fcm)
        with a, b, patch(
            "apps.forum_host.tasks.send_forum_push.delay",
            side_effect=[BrokerError("broker down"), None],
        ) as handoff, self.assertLogs("forum_host.tasks", "ERROR") as logs:
            send_forum_push("reply_added", self.alice.pk, {"topic_id": "1"})

        self.assertEqual(
            [c.kwargs["token"] for c in handoff.call_args_list],
            ["fake-token-tablet", "fake-token-watch"],
        )
        self.assertIn("OperationalError", "\n".join(logs.output))
        self.assertNotIn("broker down", "\n".join(logs.output))

    def test_a_single_device_retry_sends_to_that_device_only(self):
        fcm = _fcm()

        self._send_single(fcm, token="fake-token-tablet")

        self.assertEqual(_sent_tokens(fcm), ["fake-token-tablet"])

    def test_a_single_device_retry_for_a_token_since_removed_sends_nothing(self):
        unregister_device(self.alice, "fake-token-tablet")
        fcm = _fcm()

        self._send_single(fcm, token="fake-token-tablet")

        fcm.send.assert_not_called()

    def test_every_device_failing_transiently_retries_the_task(self):
        from apps.forum_host.tasks import send_forum_push
        from firebase_admin import exceptions as fb_exceptions

        fcm = _fcm(send=fb_exceptions.UnavailableError("down"))
        a, b = self._patches(fcm)
        with a, b:
            result = send_forum_push.apply(
                args=("reply_added", self.alice.pk, {"topic_id": "1"})
            )

        # Initial attempt + 3 retries, each to both devices.
        self.assertEqual(fcm.send.call_count, 8)
        self.assertEqual(result.status, "FAILURE")


class CareFanOutTest(TestCase):
    def setUp(self):
        from apps.garden_calendar.models import CareTask, Plant

        self.alice = User.objects.create_user(username="alice", email="a@x.com")
        register_device(self.alice, "fake-token-phone", "install-phone")
        register_device(self.alice, "fake-token-tablet", "install-tablet")
        plant = Plant.objects.create(
            owner=self.alice, common_name="Monstera", planted_date=date(2026, 1, 1)
        )
        self.task = CareTask.objects.create(
            plant=plant,
            created_by=self.alice,
            task_type="watering",
            title="Water the Monstera",
            scheduled_date=timezone.now() - timedelta(minutes=5),
        )

    def _run(self, fcm):
        from apps.garden_calendar.tasks import send_due_care_task_reminders

        with patch(
            "apps.core.firebase_config.is_firebase_available", return_value=True
        ), patch("apps.core.firebase_config.get_fcm_client", return_value=fcm), patch(
            "apps.garden_calendar.tasks.send_care_reminder_to_device.delay"
        ) as handoff:
            send_due_care_task_reminders.run()
        self.task.refresh_from_db()
        return handoff

    def test_both_devices_receive_the_reminder(self):
        fcm = _fcm()

        handoff = self._run(fcm)

        self.assertEqual(_sent_tokens(fcm), ["fake-token-phone", "fake-token-tablet"])
        self.assertTrue(self.task.notification_sent)
        handoff.assert_not_called()

    def test_a_dead_token_clears_only_that_device_and_the_claim_stands(self):
        from firebase_admin import messaging

        fcm = _failing_on({"fake-token-phone": messaging.UnregisteredError("gone")})

        handoff = self._run(fcm)

        self.assertEqual(_tokens(self.alice), ["fake-token-tablet"])
        self.assertTrue(self.task.notification_sent)
        handoff.assert_not_called()

    def test_a_transient_failure_on_one_device_retries_it_alone(self):
        """The tablet's failure must not release the claim: the next sweep
        would re-send to the phone, which already has it."""
        from firebase_admin import exceptions as fb_exceptions

        fcm = _failing_on({"fake-token-tablet": fb_exceptions.UnavailableError("down")})

        handoff = self._run(fcm)

        self.assertTrue(self.task.notification_sent)
        handoff.assert_called_once()
        owner_id, token, data, content = handoff.call_args.args
        self.assertEqual((owner_id, token), (self.alice.pk, "fake-token-tablet"))
        self.assertEqual(data["care_task_uuid"], str(self.task.uuid))
        self.assertEqual(content, ["Water the Monstera", "Monstera is due for care."])

    def test_every_device_failing_transiently_releases_the_claim(self):
        from firebase_admin import exceptions as fb_exceptions

        fcm = _fcm(send=fb_exceptions.UnavailableError("down"))

        handoff = self._run(fcm)

        self.assertFalse(self.task.notification_sent)
        handoff.assert_not_called()

    def _retry(self, fcm, token="fake-token-tablet"):
        from apps.garden_calendar.tasks import send_care_reminder_to_device

        with patch(
            "apps.core.firebase_config.is_firebase_available", return_value=True
        ), patch("apps.core.firebase_config.get_fcm_client", return_value=fcm):
            return send_care_reminder_to_device.apply(
                args=(
                    self.alice.pk,
                    token,
                    {"event": "care_task_due"},
                    ["Water the Monstera", "Monstera is due for care."],
                )
            )

    def test_the_device_retry_sends_to_that_device_only(self):
        fcm = _fcm()

        self._retry(fcm)

        self.assertEqual(_sent_tokens(fcm), ["fake-token-tablet"])

    def test_the_device_retry_skips_a_removed_device_or_an_opted_out_owner(self):
        unregister_device(self.alice, "fake-token-tablet")
        fcm = _fcm()
        self._retry(fcm)
        fcm.send.assert_not_called()

        User.objects.filter(pk=self.alice.pk).update(care_reminder_notifications=False)
        self._retry(fcm, token="fake-token-phone")
        fcm.send.assert_not_called()

    def test_the_device_retry_retries_transient_and_drops_dead(self):
        from firebase_admin import exceptions as fb_exceptions
        from firebase_admin import messaging

        fcm = _fcm(send=fb_exceptions.UnavailableError("down"))
        result = self._retry(fcm)
        self.assertEqual(fcm.send.call_count, 4)  # initial + max_retries=3
        self.assertEqual(result.status, "FAILURE")

        fcm = _fcm(send=messaging.UnregisteredError("gone"))
        self._retry(fcm)
        self.assertEqual(fcm.send.call_count, 1)
        self.assertEqual(_tokens(self.alice), ["fake-token-phone"])
