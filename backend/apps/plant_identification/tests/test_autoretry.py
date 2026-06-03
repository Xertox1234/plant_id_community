"""
Tests for run_identification autoretry behavior (audit H1 / M12).

Two coupled defects had to be fixed together:

  H1 — the service swallowed every exception (returning fallback results and/or
       marking the request "failed"), so retryable errors never reached the task
       and `autoretry_for` was inert; and the task wrote a terminal "failed"
       mid-flight, which clobbered a retried run via the idempotency guard.
  M12 — the RateLimitExceeded exhaustion path left the request stuck "pending".

These tests deliberately mock ONLY the external API client
(`PlantNetAPIService.identify_with_location`) — never the whole
`PlantIdentificationService` — and exercise `on_failure` directly so they don't
depend on Celery eager-mode retry semantics.
"""

import io
from unittest.mock import MagicMock, patch

import requests
from apps.core.exceptions import ExternalAPIError
from apps.plant_identification.exceptions import APIUnavailable
from apps.plant_identification.models import (
    PlantIdentificationRequest,
    PlantIdentificationResult,
)
from apps.plant_identification.services.identification_service import (
    PlantIdentificationService,
)
from apps.plant_identification.tasks import run_identification
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

User = get_user_model()


def _test_image():
    image = Image.new("RGB", (64, 64), color="green")
    buf = io.BytesIO()
    image.save(buf, format="JPEG")
    buf.seek(0)
    return SimpleUploadedFile(
        name="plant.jpg", content=buf.read(), content_type="image/jpeg"
    )


class ServiceReRaisesTransientErrorsTest(TestCase):
    """The service must propagate retryable external-API errors (not swallow
    them into fallback results / a terminal "failed" status), so the task's
    autoretry_for can fire."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="reraise",
            email="reraise@example.com",
            password="pass123",  # pragma: allowlist secret
        )
        self.service = PlantIdentificationService()
        # Mock ONLY the external API client — not the service under test.
        self.service.plantnet = MagicMock()

    def _make_request(self):
        return PlantIdentificationRequest.objects.create(
            user=self.user, image_1=_test_image(), location="Test"
        )

    def _assert_propagates_and_not_finalized(self, exc):
        self.service.plantnet.identify_with_location.side_effect = exc
        req = self._make_request()

        with self.assertRaises(type(exc)):
            # reraise_transient=True is the Celery-task path.
            self.service.identify_plant_from_request(req, reraise_transient=True)

        req.refresh_from_db()
        # Not marked terminal-"failed" — that's on_failure's job after retries
        # are exhausted, not an immediate permanent failure (audit H1).
        self.assertEqual(req.status, "processing")
        # No fallback ("Rosa damascena" etc.) rows leaked from the failed attempt.
        self.assertEqual(
            PlantIdentificationResult.objects.filter(request=req).count(), 0
        )

    def test_external_api_error_propagates(self):
        self._assert_propagates_and_not_finalized(ExternalAPIError("PlantNet down"))

    def test_api_unavailable_propagates(self):
        self._assert_propagates_and_not_finalized(APIUnavailable("temporarily down"))

    def test_request_exception_propagates(self):
        self._assert_propagates_and_not_finalized(
            requests.exceptions.ConnectionError("conn reset")
        )

    def test_empty_results_still_falls_back(self):
        """A non-error empty response (None) must keep the graceful fallback —
        only *exceptions* propagate now."""
        self.service.plantnet.identify_with_location.return_value = None
        req = self._make_request()

        results = self.service.identify_plant_from_request(req)

        req.refresh_from_db()
        self.assertIn(req.status, ["identified", "needs_help"])
        self.assertGreater(len(results), 0)

    def test_sync_mode_swallows_transient_and_falls_back(self):
        """Zero-regression guard for the LIVE synchronous view path
        (reraise_transient=False, the default): a transient external-API error
        must NOT propagate -- it degrades to fallback results so the create
        endpoint still returns 201, exactly as before this todo."""
        self.service.plantnet.identify_with_location.side_effect = ExternalAPIError(
            "PlantNet down"
        )
        req = self._make_request()

        # No flag -> sync path. Must not raise.
        results = self.service.identify_plant_from_request(req)

        req.refresh_from_db()
        self.assertIn(req.status, ["identified", "needs_help"])
        self.assertGreater(len(results), 0)


class OnFailureFinalizesStatusTest(TestCase):
    """IdentificationTask.on_failure owns the terminal "failed" write."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="onfail",
            email="onfail@example.com",
            password="pass123",  # pragma: allowlist secret
        )

    def _request(self, status):
        return PlantIdentificationRequest.objects.create(user=self.user, status=status)

    def _call_on_failure(self, req):
        run_identification.on_failure(
            ExternalAPIError("exhausted"),
            "task-id",
            (str(req.request_id),),
            {},
            None,
        )

    def test_processing_marked_failed_on_exhaustion(self):
        """After retries exhaust, a mid-flight "processing" request ends "failed"
        (not stuck pending/processing — audit M12)."""
        req = self._request("processing")
        self._call_on_failure(req)
        req.refresh_from_db()
        self.assertEqual(req.status, "failed")

    def test_pending_marked_failed_on_exhaustion(self):
        req = self._request("pending")
        self._call_on_failure(req)
        req.refresh_from_db()
        self.assertEqual(req.status, "failed")

    def test_does_not_clobber_identified(self):
        """on_failure must never overwrite a terminal-success status."""
        req = self._request("identified")
        self._call_on_failure(req)
        req.refresh_from_db()
        self.assertEqual(req.status, "identified")

    def test_does_not_clobber_needs_help(self):
        req = self._request("needs_help")
        self._call_on_failure(req)
        req.refresh_from_db()
        self.assertEqual(req.status, "needs_help")


class TaskAutoretryWiringTest(TestCase):
    """Config + task-body assertions that together prove autoretry will fire for
    a transient error — without depending on Celery eager-mode semantics."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="wiring",
            email="wiring@example.com",
            password="pass123",  # pragma: allowlist secret
        )

    def test_retryable_exceptions_in_autoretry_for(self):
        self.assertIn(ExternalAPIError, run_identification.autoretry_for)
        self.assertIn(APIUnavailable, run_identification.autoretry_for)
        self.assertIn(
            requests.exceptions.RequestException, run_identification.autoretry_for
        )

    def test_task_body_reraises_transient_error(self):
        """When the service raises a retryable error, the task body must re-raise
        it (so Celery's autoretry_for catches it) and must NOT write "failed"."""
        req = PlantIdentificationRequest.objects.create(
            user=self.user, status="pending"
        )
        with patch(
            "apps.plant_identification.tasks.PlantIdentificationService"
        ) as MockService, patch(
            "apps.plant_identification.tasks.get_channel_layer",
            return_value=MagicMock(),
        ):
            service_call = MockService.return_value.identify_plant_from_request
            service_call.side_effect = ExternalAPIError("PlantNet down")
            with self.assertRaises(ExternalAPIError):
                run_identification(str(req.request_id))

        # The task must opt into re-raise so autoretry_for fires (sync callers don't).
        service_call.assert_called_once()
        self.assertTrue(service_call.call_args.kwargs.get("reraise_transient"))

        req.refresh_from_db()
        # Body must not finalize — on_failure owns the terminal write.
        self.assertNotEqual(req.status, "failed")
