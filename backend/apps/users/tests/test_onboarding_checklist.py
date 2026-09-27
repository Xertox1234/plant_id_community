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
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()

PROGRESS_URL = "/api/v1/auth/me/onboarding/progress/"


def _steps(resp):
    return {step["key"]: step["done"] for step in resp.data["checklist"]["steps"]}


class OnboardingChecklistTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="ada", password="TestPass123!")
        self.client.force_authenticate(user=self.user)

    def test_a_new_user_has_every_step_open(self):
        resp = self.client.get(PROGRESS_URL)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            [s["key"] for s in resp.data["checklist"]["steps"]], list(CHECKLIST_STEPS)
        )
        self.assertEqual(_steps(resp), {key: False for key in CHECKLIST_STEPS})
        self.assertFalse(resp.data["checklist"]["complete"])
        self.assertFalse(resp.data["checklist"]["dismissed"])

    def test_a_forum_post_ticks_its_step(self):
        root = Page.objects.get(id=1)
        index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
        board = index.add_child(instance=ForumBoard(title="General", slug="general"))
        topic = Topic.objects.create(
            board=board, title="Hi", slug="hi", author=self.user, live=True
        )
        Post.objects.create(
            topic=topic, author=self.user, is_opening_post=True, live=True
        )

        self.assertTrue(_steps(self.client.get(PROGRESS_URL))["forum_post"])

    def test_a_bio_ticks_the_profile_step_and_whitespace_does_not(self):
        self.user.bio = "   "
        self.user.save(update_fields=["bio"])
        self.assertFalse(_steps(self.client.get(PROGRESS_URL))["profile"])

        self.user.bio = "Fern person."
        self.user.save(update_fields=["bio"])
        self.assertTrue(_steps(self.client.get(PROGRESS_URL))["profile"])

    def test_every_step_done_is_complete(self):
        self.user.bio = "Fern person."
        self.user.save(update_fields=["bio"])
        record_first_identification(self.user)
        with patch("wagtail_forum.models.Post.objects") as posts:
            posts.filter.return_value.exists.return_value = True
            resp = self.client.get(PROGRESS_URL)

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

    def test_the_demo_data_endpoints_are_gone(self):
        for method, path in (
            ("post", "/api/v1/auth/me/onboarding/create-demo-data/"),
            ("delete", "/api/v1/auth/me/onboarding/demo-data/"),
        ):
            with self.subTest(path=path):
                resp = getattr(self.client, method)(path)
                self.assertEqual(resp.status_code, 404)


class IdentifyTicksTheChecklistTests(TestCase):
    """The identify endpoint records the step itself: results are not
    persisted (todo 411), so there is no row to derive it from."""

    URL = "/api/v1/plant-identification/identify/"

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="bo", password="TestPass123!")

    def _identify(self):
        image = SimpleUploadedFile(
            "leaf.jpg", b"\\xff\\xd8\\xff\\xe0fake", content_type="image/jpeg"
        )
        return self.client.post(self.URL, {"image": image}, format="multipart")

    def test_a_successful_identification_ticks_identify_plant(self):
        self.client.force_authenticate(user=self.user)
        result = {
            "combined_suggestions": [
                {
                    "plant_name": "Monstera",
                    "scientific_name": "Monstera deliciosa",
                    "probability": 0.9,
                }
            ],
            "confidence_score": 0.9,
        }
        with patch("apps.plant_identification.utils.validate_image_file"), patch(
            "apps.plant_identification.api.simple_views.CombinedPlantIdentificationService"
        ) as service:
            service.return_value.identify_plant.return_value = result
            service.return_value.get_identification_summary.return_value = "Monstera"
            resp = self._identify()

        self.assertEqual(resp.status_code, 200, resp.data)
        progress = OnboardingProgress.objects.get(user=self.user)
        self.assertTrue(progress.first_identification_completed)

    def test_recording_never_raises(self):
        with patch(
            "apps.users.models.OnboardingProgress.objects.get_or_create",
            side_effect=RuntimeError("db down"),
        ):
            record_first_identification(self.user)  # no exception
