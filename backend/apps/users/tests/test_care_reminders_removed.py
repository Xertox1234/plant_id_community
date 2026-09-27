"""The users care-reminder system is gone (todo 410 slice B).

``users.CareReminder``, ``CareReminderLog``, the six ``me/care-reminders/*``
routes, ``core.PlantCareReminder`` and its service were dead end to end: no
client called the routes and no scheduler sent a reminder. The owner chose one
reminder model (2026-09-26): garden_calendar ``CareTask`` due dates, pushed by
``apps.garden_calendar.tasks``. These tests pin the removal.
"""

import uuid

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import NoReverseMatch, Resolver404, resolve, reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

_ID = uuid.uuid4()
REMOVED_PATHS = [
    "/api/v1/auth/me/care-reminders/",
    f"/api/v1/auth/me/care-reminders/{_ID}/",
    f"/api/v1/auth/me/care-reminders/{_ID}/action/",
    "/api/v1/auth/me/care-reminders/stats/",
    "/api/v1/auth/me/care-reminders/export/calendar/",
    "/api/v1/auth/me/care-reminders/calendar/preview/",
]
REMOVED_NAMES = [
    "care_reminders",
    "care_reminder_detail",
    "care_reminder_action",
    "care_reminder_stats",
    "export_care_reminders_calendar",
    "care_reminder_calendar_preview",
]


def _is_real_route(path):
    """The root URLconf ends in a Wagtail catch-all, so a removed path still
    "resolves" to ``wagtail_serve`` (which 404s). See the legacy-mount test."""
    try:
        return resolve(path).url_name != "wagtail_serve"
    except Resolver404:
        return False


class RemovedRoutesTest(SimpleTestCase):
    def test_the_paths_are_not_routes(self):
        for path in REMOVED_PATHS:
            with self.subTest(path=path):
                self.assertFalse(_is_real_route(path))

    def test_the_route_names_do_not_reverse(self):
        for name in REMOVED_NAMES:
            for full in (name, f"users:{name}", f"v1:users:{name}"):
                with self.subTest(name=full), self.assertRaises(NoReverseMatch):
                    reverse(full)

    def test_the_models_are_gone(self):
        for app_label, model in (
            ("users", "CareReminder"),
            ("users", "CareReminderLog"),
            ("core", "PlantCareReminder"),
        ):
            with self.subTest(model=model), self.assertRaises(LookupError):
                apps.get_model(app_label, model)


class RemovedRoutesOverHttpTest(TestCase):
    def test_an_authenticated_request_gets_404(self):
        client = APIClient()
        client.force_authenticate(
            User.objects.create_user(username="u", email="u@example.com")
        )
        for path in REMOVED_PATHS:
            with self.subTest(path=path):
                self.assertEqual(
                    client.get(path).status_code, status.HTTP_404_NOT_FOUND
                )


class CarePreferenceTest(TestCase):
    def test_only_the_push_opt_out_survives(self):
        """The reminder sweep reads ``care_reminder_notifications``; there is
        no care-reminder email, so that preference is gone."""
        from apps.core.services.notification_service import NotificationService

        user = User.objects.create_user(username="p", email="p@example.com")
        self.assertTrue(user.care_reminder_notifications)
        self.assertFalse(hasattr(user, "care_reminder_email"))
        prefs = NotificationService().get_user_notification_preferences(user)
        self.assertNotIn("care_reminder_email", prefs)

    def test_the_push_opt_out_is_settable_by_the_user(self):
        """PR #854 review: with the email preference gone, the push opt-out
        must be reachable, or care pushes cannot be turned off."""
        user = User.objects.create_user(username="q", email="q@example.com")
        client = APIClient()
        client.force_authenticate(user)

        response = client.patch(
            "/api/v1/auth/user/update/",
            {"care_reminder_notifications": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        user.refresh_from_db()
        self.assertFalse(user.care_reminder_notifications)
        self.assertIs(
            client.get("/api/v1/auth/user/").data["care_reminder_notifications"], False
        )


class ExpandContractColumnsTest(TestCase):
    """The dropped fields leave Django state only; their columns stay, with a
    DB default, until todo 458 drops them. The old container still reads them
    during a rolling deploy (PR #854 review)."""

    def test_the_columns_remain_with_a_db_default(self):
        from django.db import connection

        with connection.cursor() as cursor:
            for table, column in (
                ("auth_user", "care_reminder_email"),
                ("users_onboardingprogress", "first_care_reminder_created"),
            ):
                cursor.execute(
                    "SELECT column_default FROM information_schema.columns "
                    "WHERE table_name = %s AND column_name = %s",
                    [table, column],
                )
                row = cursor.fetchone()
                with self.subTest(column=column):
                    self.assertIsNotNone(row, "column was dropped too early")
                    self.assertEqual(row[0], "false")
        # And a row inserted by the new code (which no longer knows the
        # column) still satisfies NOT NULL.
        User.objects.create_user(username="n", email="n@example.com")
