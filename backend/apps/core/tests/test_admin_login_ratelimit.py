"""Admin sign-in hardening (todo 705 M22, audit 2026-11-10).

* The Wagtail (/cms/login/) and Django (/admin/login/) login forms answer 429
  after five failed passwords from one IP in 15 minutes.
* Every signed-in request under /cms/ and /admin/ needs a verified django-otp
  second factor: enrol a TOTP app once, then a code each sign-in. A session
  that never saw a login form (the web OAuth callback's ``django_login``) is
  gated the same way.
"""

from apps.core.constants import (
    ADMIN_LOGIN_FAILURE_RATE,
    ADMIN_OTP_SETUP_PATH,
    ADMIN_OTP_VERIFY_PATH,
)
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django_otp.oath import TOTP
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

User = get_user_model()

PASSWORD = "Admin-Pa55word-for-tests!"  # pragma: allowlist secret
WRONG = "wrong-guess"  # pragma: allowlist secret


def _code(device: TOTPDevice) -> str:
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    return f"{totp.token():0{device.digits}d}"


class AdminLoginThrottleTest(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser(
            username="boss", email="boss@example.com", password=PASSWORD
        )

    def _wrong(self, path):
        return self.client.post(path, {"username": "boss", "password": WRONG})

    def test_the_rate_is_five_failures_per_fifteen_minutes(self):
        self.assertEqual(ADMIN_LOGIN_FAILURE_RATE, "5/15m")

    def test_six_wrong_passwords_at_cms_login_are_throttled(self):
        for _ in range(5):
            self.assertEqual(self._wrong("/cms/login/").status_code, 200)
        sixth = self._wrong("/cms/login/")
        self.assertEqual(sixth.status_code, 429)
        self.assertGreater(int(sixth["Retry-After"]), 0)
        # Throttled before the password is checked: the right one is refused too.
        right = self.client.post(
            "/cms/login/", {"username": "boss", "password": PASSWORD}
        )
        self.assertEqual(right.status_code, 429)

    def test_six_wrong_passwords_at_admin_login_are_throttled(self):
        for _ in range(5):
            self.assertEqual(self._wrong("/admin/login/").status_code, 200)
        self.assertEqual(self._wrong("/admin/login/").status_code, 429)

    def test_the_count_is_per_ip(self):
        for _ in range(5):
            self._wrong("/cms/login/")
        other_ip = self.client.post(
            "/cms/login/",
            {"username": "boss", "password": WRONG},
            REMOTE_ADDR="203.0.113.9",
        )
        self.assertEqual(other_ip.status_code, 200)

    def test_successful_sign_ins_do_not_count(self):
        for _ in range(6):
            ok = self.client.post(
                "/cms/login/", {"username": "boss", "password": PASSWORD}
            )
            self.assertEqual(ok.status_code, 302)
            self.client.logout()

    def test_a_get_of_the_form_is_never_throttled(self):
        for _ in range(5):
            self._wrong("/cms/login/")
        self.assertEqual(self.client.get("/cms/login/").status_code, 200)


@override_settings(STAFF_OTP_REQUIRED=True)
class StaffSecondFactorTest(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser(
            username="boss", email="boss@example.com", password=PASSWORD
        )

    def _sign_in(self):
        response = self.client.post(
            "/cms/login/", {"username": "boss", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 302)
        return response

    def test_staff_sign_in_without_a_device_is_sent_to_enrol(self):
        self._sign_in()
        response = self.client.get("/cms/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(ADMIN_OTP_SETUP_PATH))

    def test_django_admin_is_gated_too(self):
        self._sign_in()
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(ADMIN_OTP_SETUP_PATH))

    def test_a_session_from_outside_the_login_form_is_gated(self):
        # What the web OAuth callback does: django_login, no admin form.
        self.client.force_login(self.admin)
        response = self.client.get("/cms/pages/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(ADMIN_OTP_SETUP_PATH))

    def test_blog_admin_is_gated_too(self):
        self._sign_in()
        response = self.client.get("/blog-admin/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(ADMIN_OTP_SETUP_PATH))

    def test_a_non_staff_session_is_not_sent_to_enrol(self):
        member = User.objects.create_user(
            username="member", email="member@example.com", password=PASSWORD
        )
        self.client.force_login(member)
        response = self.client.get("/cms/")
        self.assertFalse(response.get("Location", "").startswith(ADMIN_OTP_SETUP_PATH))

    def test_a_non_staff_user_cannot_open_the_setup_page(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice

        member = User.objects.create_user(
            username="member2", email="member2@example.com", password=PASSWORD
        )
        self.client.force_login(member)
        response = self.client.get(ADMIN_OTP_SETUP_PATH)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TOTPDevice.objects.filter(user=member).exists())

    def test_a_forum_moderator_without_staff_is_gated(self):
        # Wagtail admin access comes from wagtailadmin.access_admin, which the
        # Forum Moderators group has without is_staff (forum_host/bootstrap.py).
        # Owner decision 2026-11-18: anyone who can open the admin needs TOTP.
        from django.contrib.auth.models import Group, Permission

        moderators = Group.objects.create(name="Moderators for test")
        moderators.permissions.add(
            Permission.objects.get(
                content_type__app_label="wagtailadmin", codename="access_admin"
            )
        )
        moderator = User.objects.create_user(
            username="mod", email="mod@example.com", password=PASSWORD
        )
        moderator.groups.add(moderators)
        self.assertFalse(moderator.is_staff)
        self.client.force_login(moderator)

        gated = self.client.get("/cms/")
        self.assertEqual(gated.status_code, 302)
        self.assertTrue(gated["Location"].startswith(ADMIN_OTP_SETUP_PATH))
        self.assertEqual(self.client.get(ADMIN_OTP_SETUP_PATH).status_code, 200)

    def test_recovery_then_removing_the_lost_device_reaches_enrolment(self):
        # The documented recovery: addstatictoken, verify with it, delete the
        # lost TOTP device. The used static device stays (confirmed), and must
        # not keep the user at verify with no code left that works.
        lost = TOTPDevice.objects.create(
            user=self.admin, name="lost phone", confirmed=True
        )
        call_command("addstatictoken", "boss", "-t", "recover123")
        self._sign_in()
        ok = self.client.post(ADMIN_OTP_VERIFY_PATH, {"token": "recover123"})
        self.assertEqual(ok.status_code, 302)
        lost.delete()
        self.client.logout()

        self._sign_in()
        gated = self.client.get("/cms/")
        self.assertTrue(gated["Location"].startswith(ADMIN_OTP_SETUP_PATH))
        self.assertEqual(self.client.get(ADMIN_OTP_SETUP_PATH).status_code, 200)

    def test_the_two_factor_pages_are_never_cached(self):
        self._sign_in()
        response = self.client.get(ADMIN_OTP_SETUP_PATH)
        self.assertIn("no-store", response["Cache-Control"])

    def test_enrolling_a_totp_app_opens_the_admin(self):
        self._sign_in()
        page = self.client.get(ADMIN_OTP_SETUP_PATH)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, page.context["secret"])
        device = TOTPDevice.objects.get(user=self.admin, confirmed=False)

        wrong = self.client.post(ADMIN_OTP_SETUP_PATH, {"token": "000000"})
        self.assertEqual(wrong.status_code, 200)
        self.assertEqual(self.client.get("/cms/").status_code, 302)

        # A wrong code makes TOTPDevice refuse every code for a growing delay
        # (django-otp's throttle); a person retyping waits that out.
        device.refresh_from_db()
        self.assertEqual(device.throttling_failure_count, 1)
        device.throttle_reset()

        done = self.client.post(
            ADMIN_OTP_SETUP_PATH, {"token": _code(device), "next": "/cms/"}
        )
        self.assertEqual(done.status_code, 302)
        self.assertEqual(done["Location"], "/cms/")
        device.refresh_from_db()
        self.assertTrue(device.confirmed)
        self.assertEqual(self.client.get("/cms/").status_code, 200)

    def test_a_later_sign_in_asks_for_a_code(self):
        device = TOTPDevice.objects.create(user=self.admin, name="app", confirmed=True)
        self._sign_in()
        gated = self.client.get("/cms/")
        self.assertEqual(gated.status_code, 302)
        self.assertTrue(gated["Location"].startswith(ADMIN_OTP_VERIFY_PATH))
        # Enrolment is closed once a device exists: no second device.
        to_verify = self.client.get(ADMIN_OTP_SETUP_PATH)
        self.assertTrue(to_verify["Location"].startswith(ADMIN_OTP_VERIFY_PATH))

        self.assertEqual(
            self.client.post(ADMIN_OTP_VERIFY_PATH, {"token": "123456"}).status_code,
            200,
        )
        self.assertEqual(self.client.get("/cms/").status_code, 302)

        device.refresh_from_db()
        self.assertEqual(device.throttling_failure_count, 1)
        device.throttle_reset()  # the wrong code's delay, waited out

        ok = self.client.post(ADMIN_OTP_VERIFY_PATH, {"token": _code(device)})
        self.assertEqual(ok.status_code, 302)
        self.assertEqual(self.client.get("/cms/").status_code, 200)
        self.assertEqual(TOTPDevice.objects.filter(user=self.admin).count(), 1)

    def test_a_recovery_code_from_addstatictoken_opens_the_admin(self):
        TOTPDevice.objects.create(user=self.admin, name="lost phone", confirmed=True)
        call_command("addstatictoken", "boss", "-t", "recover123")
        self.assertTrue(StaticDevice.objects.filter(user=self.admin).exists())
        self._sign_in()

        ok = self.client.post(ADMIN_OTP_VERIFY_PATH, {"token": "recover123"})

        self.assertEqual(ok.status_code, 302)
        self.assertEqual(self.client.get("/cms/").status_code, 200)

    def test_an_offsite_next_is_ignored(self):
        device = TOTPDevice.objects.create(user=self.admin, name="app", confirmed=True)
        self._sign_in()
        ok = self.client.post(
            ADMIN_OTP_VERIFY_PATH,
            {"token": _code(device), "next": "https://evil.example/"},
        )
        self.assertEqual(ok["Location"], "/cms/")

    def test_anonymous_requests_are_left_to_the_admin_login(self):
        response = self.client.get("/cms/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/cms/login/"))

    def test_the_setup_page_needs_a_signed_in_user(self):
        response = self.client.get(ADMIN_OTP_SETUP_PATH)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/cms/login/"))


class SecondFactorSettingTest(TestCase):
    def test_on_by_default_outside_test_runs(self):
        from pathlib import Path

        settings_py = (
            Path(__file__).resolve().parents[3]
            / "plant_community_backend"
            / "settings.py"
        ).read_text()
        self.assertIn(
            'STAFF_OTP_REQUIRED = config("STAFF_OTP_REQUIRED", '
            "default=not _IS_TEST_RUN, cast=bool)",
            settings_py,
        )
