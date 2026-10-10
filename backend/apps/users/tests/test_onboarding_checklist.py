"""The onboarding checklist (todo 412): steps derived from what the user
did, a dismiss flag the client may set, and no demo-data endpoints."""

from unittest.mock import patch

from apps.users.models import OnboardingProgress
from apps.users.onboarding import CHECKLIST_STEPS, record_first_identification
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic, TopicBookmark

User = get_user_model()

PROGRESS_URL = "/api/v1/auth/me/onboarding/progress/"


def _steps(resp):
    return {step["key"]: step["done"] for step in resp.data["checklist"]["steps"]}


class OnboardingChecklistTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="ada", password="TestPass123!")
        self.client.force_authenticate(user=self.user)
        root = Page.objects.get(id=1)
        index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
        self.board = index.add_child(
            instance=ForumBoard(title="General", slug="general")
        )

    def _topic(self, slug="hi"):
        return Topic.objects.create(
            board=self.board, title=slug.title(), slug=slug, author=self.user, live=True
        )

    def test_a_new_user_has_every_step_open(self):
        resp = self.client.get(PROGRESS_URL)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            [s["key"] for s in resp.data["checklist"]["steps"]], list(CHECKLIST_STEPS)
        )
        self.assertEqual(_steps(resp), {key: False for key in CHECKLIST_STEPS})
        self.assertFalse(resp.data["checklist"]["complete"])
        self.assertFalse(resp.data["checklist"]["dismissed"])

    def test_a_live_forum_post_ticks_its_step(self):
        Post.objects.create(
            topic=self._topic(), author=self.user, is_opening_post=True, live=True
        )

        self.assertTrue(_steps(self.client.get(PROGRESS_URL))["forum_post"])

    def test_a_post_held_for_moderation_does_not_count(self):
        Post.objects.create(
            topic=self._topic(), author=self.user, is_opening_post=True, live=False
        )

        self.assertFalse(_steps(self.client.get(PROGRESS_URL))["forum_post"])

    def test_saving_a_topic_ticks_its_step(self):
        TopicBookmark.objects.create(user=self.user, topic=self._topic())

        self.assertTrue(_steps(self.client.get(PROGRESS_URL))["save_topic"])

    def test_every_step_done_is_complete(self):
        topic = self._topic()
        Post.objects.create(
            topic=topic, author=self.user, is_opening_post=True, live=True
        )
        TopicBookmark.objects.create(user=self.user, topic=topic)
        record_first_identification(self.user)

        resp = self.client.get(PROGRESS_URL)

        self.assertEqual(_steps(resp), {key: True for key in CHECKLIST_STEPS})
        self.assertTrue(resp.data["checklist"]["complete"])

    def test_a_finished_checklist_stays_finished_after_a_step_is_undone(self):
        topic = self._topic()
        Post.objects.create(
            topic=topic, author=self.user, is_opening_post=True, live=True
        )
        bookmark = TopicBookmark.objects.create(user=self.user, topic=topic)
        record_first_identification(self.user)
        self.assertTrue(self.client.get(PROGRESS_URL).data["checklist"]["complete"])

        bookmark.delete()  # a normal thing to do once the topic is read

        resp = self.client.get(PROGRESS_URL)
        self.assertFalse(_steps(resp)["save_topic"])
        self.assertTrue(resp.data["checklist"]["complete"])

    def test_dismissing_the_card(self):
        resp = self.client.patch(
            PROGRESS_URL, {"completed_checklist": True}, format="json"
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["checklist"]["dismissed"])
        self.assertTrue(self.client.get(PROGRESS_URL).data["checklist"]["dismissed"])

    def test_a_non_boolean_flag_is_refused_not_stored_truthy(self):
        # A string "false" is truthy; it used to be stored as True.
        resp = self.client.patch(
            PROGRESS_URL, {"completed_checklist": "false"}, format="json"
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["fields"], ["completed_checklist"])
        progress = OnboardingProgress.objects.get(user=self.user)
        self.assertFalse(progress.completed_checklist)

    def test_a_client_cannot_tick_a_derived_step(self):
        resp = self.client.patch(
            PROGRESS_URL,
            {"first_identification_completed": True, "first_forum_post_created": True},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(_steps(resp)["identify_plant"])
        self.assertFalse(_steps(resp)["forum_post"])

    def test_a_bad_completed_at_is_a_400_and_keeps_the_stored_value(self):
        ok = self.client.patch(
            PROGRESS_URL,
            {"onboarding_completed_at": "2026-09-26T10:00:00Z"},
            format="json",
        )
        self.assertEqual(ok.status_code, 200)

        # Impossible date (parse_datetime RAISES), garbage (returns None), a
        # number: each a 400, none clearing the stored timestamp.
        for bad in ("2026-13-01T00:00:00", "garbage", 5):
            with self.subTest(value=bad):
                resp = self.client.patch(
                    PROGRESS_URL, {"onboarding_completed_at": bad}, format="json"
                )
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.data["fields"], ["onboarding_completed_at"])
        progress = OnboardingProgress.objects.get(user=self.user)
        self.assertIsNotNone(progress.onboarding_completed_at)

    def test_the_demo_data_endpoints_are_gone(self):
        for method, path in (
            ("post", "/api/v1/auth/me/onboarding/create-demo-data/"),
            ("delete", "/api/v1/auth/me/onboarding/demo-data/"),
        ):
            with self.subTest(path=path):
                resp = getattr(self.client, method)(path)
                self.assertEqual(resp.status_code, 404)

    def test_the_demo_data_model_and_table_are_gone(self):
        """users 0018 drops the unused demo-data model and its table (todo 532)."""
        from django.apps import apps
        from django.db import connection

        with self.assertRaises(LookupError):
            apps.get_model("users", "demodata")
        self.assertNotIn("users_demodata", connection.introspection.table_names())


class IdentifyTicksTheChecklistTests(TestCase):
    """The identify endpoint records the step itself: results are not
    persisted (todo 411), so there is no row to derive it from."""

    URL = "/api/v1/plant-identification/identify/"

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="bo", password="TestPass123!")
        self.client.force_authenticate(user=self.user)

    def _identify(self, suggestions):
        result = {"combined_suggestions": suggestions, "confidence_score": 0.9}
        image = SimpleUploadedFile(
            "leaf.jpg", b"\xff\xd8\xff\xe0fake", content_type="image/jpeg"
        )
        with patch("apps.plant_identification.utils.validate_image_file"), patch(
            "apps.plant_identification.api.simple_views.CombinedPlantIdentificationService"
        ) as service:
            service.return_value.identify_plant.return_value = result
            service.return_value.get_identification_summary.return_value = "summary"
            return self.client.post(self.URL, {"image": image}, format="multipart")

    def test_a_successful_identification_ticks_identify_plant(self):
        resp = self._identify(
            [{"plant_name": "Monstera", "scientific_name": "Monstera deliciosa"}]
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(
            OnboardingProgress.objects.get(
                user=self.user
            ).first_identification_completed
        )

    def test_an_answer_with_no_suggestion_does_not_count(self):
        resp = self._identify([])

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["plant_name"], "Unknown")
        self.assertFalse(
            OnboardingProgress.objects.filter(
                user=self.user, first_identification_completed=True
            ).exists()
        )

    def test_recording_creates_a_missing_progress_row(self):
        OnboardingProgress.objects.filter(user=self.user).delete()

        record_first_identification(self.user)

        self.assertTrue(
            OnboardingProgress.objects.get(
                user=self.user
            ).first_identification_completed
        )

    def test_recording_never_raises(self):
        with patch(
            "apps.users.models.OnboardingProgress.objects.filter",
            side_effect=RuntimeError("db down"),
        ):
            record_first_identification(self.user)  # no exception
