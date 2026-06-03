"""
Tests for run_identification Celery task idempotency guard.

Verifies that calling the task on an already-non-pending request returns
early without re-running identification.
"""

from unittest.mock import MagicMock, patch

from apps.plant_identification.models import PlantIdentificationRequest
from apps.plant_identification.tasks import run_identification
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class RunIdentificationIdempotencyTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="idemptest",
            email="idemptest@example.com",
            password="pass123",  # pragma: allowlist secret
        )
        self.request_obj = PlantIdentificationRequest.objects.create(
            user=self.user,
            status="completed",
        )

    def _call_task(self):
        # Call the underlying function, bypassing Celery worker
        with patch(
            "apps.plant_identification.tasks.get_channel_layer",
            return_value=MagicMock(),
        ):
            return run_identification(str(self.request_obj.request_id))

    def test_skips_completed_request(self):
        self.request_obj.status = "completed"
        self.request_obj.save()

        with patch(
            "apps.plant_identification.tasks.PlantIdentificationService"
        ) as MockService:
            self._call_task()
            MockService.return_value.identify_plant_from_request.assert_not_called()

    def test_skips_failed_request(self):
        self.request_obj.status = "failed"
        self.request_obj.save()

        with patch(
            "apps.plant_identification.tasks.PlantIdentificationService"
        ) as MockService:
            self._call_task()
            MockService.return_value.identify_plant_from_request.assert_not_called()

    def test_processes_pending_request(self):
        self.request_obj.status = "pending"
        self.request_obj.save()

        with patch(
            "apps.plant_identification.tasks.PlantIdentificationService"
        ) as MockService:
            instance = MockService.return_value
            instance.identify_plant_from_request.return_value = []
            self._call_task()

        instance.identify_plant_from_request.assert_called_once()

    def test_guard_fires_on_second_call_after_status_changes(self):
        """Guard must prevent re-execution when status advances between calls."""
        self.request_obj.status = "pending"
        self.request_obj.save()

        # First call: task runs, service marks request completed
        def advance_status(req, **kwargs):
            req.status = "completed"
            req.save()
            return []

        with patch(
            "apps.plant_identification.tasks.PlantIdentificationService"
        ) as MockService:
            instance = MockService.return_value
            instance.identify_plant_from_request.side_effect = advance_status
            self._call_task()
            call_count_after_first = instance.identify_plant_from_request.call_count

            # Second call: guard should return early, service should not be called again
            self._call_task()
            self.assertEqual(
                instance.identify_plant_from_request.call_count, call_count_after_first
            )


class RunIdentificationDurabilityTest(TestCase):
    """M13: a worker killed mid-identification must not silently drop the message.

    `acks_late` defers the broker ack until the task returns, and
    `reject_on_worker_lost` requeues the message if the worker dies — together
    they survive a SIGKILL during the up-to-120s external I/O. Safe because the
    task is idempotent (the status guard above prevents duplicate processing).
    """

    def test_task_declares_late_ack_and_reject_on_worker_lost(self):
        self.assertTrue(
            run_identification.acks_late,
            "run_identification must ack late so a lost message is redelivered",
        )
        self.assertTrue(
            run_identification.reject_on_worker_lost,
            "run_identification must requeue when the worker is lost",
        )
