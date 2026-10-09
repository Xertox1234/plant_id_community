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
        user = User.objects.create_user(username="p", email="p@example.com")
        self.assertTrue(user.care_reminder_notifications)
        self.assertFalse(hasattr(user, "care_reminder_email"))

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


class DroppedColumnsTest(TestCase):
    """0015 left both columns behind for the old container to read during the
    rolling deploy (PR #854 review); 0017 drops them (todo 458)."""

    def test_the_columns_are_gone(self):
        from django.db import connection

        with connection.cursor() as cursor:
            for table, column in (
                ("auth_user", "care_reminder_email"),
                ("users_onboardingprogress", "first_care_reminder_created"),
            ):
                # Pin the schema: a same-named table elsewhere must not answer.
                cursor.execute(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = %s AND column_name = %s",
                    [table, column],
                )
                with self.subTest(column=column):
                    self.assertIsNone(cursor.fetchone())


class RetiredOnboardingStepTest(TestCase):
    """0016 only altered the choices; 0017 moves rows off the retired step."""

    def test_rows_on_the_retired_step_move_on(self):
        from importlib import import_module

        from apps.users.models import OnboardingProgress

        migration = import_module(
            "apps.users.migrations.0017_drop_care_reminder_columns"
        )
        stuck = User.objects.create_user(username="s", email="s@example.com")
        OnboardingProgress.objects.create(
            user=stuck,
            current_step="care_reminder_set",
            completed_steps=["account_created", "care_reminder_set"],
        )
        other = User.objects.create_user(username="o", email="o@example.com")
        OnboardingProgress.objects.create(
            user=other, completed_steps=["account_created"]
        )

        migration.remap_retired_onboarding_step(apps, None)

        stuck_progress = OnboardingProgress.objects.get(user=stuck)
        self.assertEqual(stuck_progress.current_step, "onboarding_completed")
        self.assertEqual(stuck_progress.completed_steps, ["account_created"])
        other_progress = OnboardingProgress.objects.get(user=other)
        self.assertEqual(other_progress.current_step, "account_created")
        self.assertEqual(other_progress.completed_steps, ["account_created"])
