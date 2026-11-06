"""Background scan jobs and their private, role-tagged photos (Scan 2.0 B2)."""

from __future__ import annotations

import logging
import uuid

from django.conf import settings
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .constants import SCAN_MODE_CHOICES
from .scan_storage import scan_photo_storage

logger = logging.getLogger(__name__)


class ScanJob(models.Model):
    ACTIVE_STATUSES = ("pending", "processing")

    MODE_CHOICES = SCAN_MODE_CHOICES
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("done", "Done"),
        ("degraded", "Degraded"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]
    CHARGED_AS_CHOICES = SCAN_MODE_CHOICES
    DECISION_CHOICES = [
        ("undecided", "Undecided"),
        ("kept", "Kept"),
        ("dismissed", "Dismissed"),
        ("expired", "Expired"),
        ("removed", "Removed"),
    ]
    # Decisions after which the scan's photos and result are erased.
    ERASED_DECISIONS = ("dismissed", "expired", "removed")

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scan_jobs"
    )
    mode = models.CharField(max_length=16, choices=MODE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    charged_as = models.CharField(max_length=16, choices=CHARGED_AS_CHOICES, blank=True)
    local_date = models.DateField()
    utc_offset_minutes = models.SmallIntegerField(default=0)
    result = models.JSONField(null=True, blank=True)
    failure_reason = models.CharField(max_length=64, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    # Default "kept": rows written by an old build (which auto-saves every
    # scan) and by any non-decision writer stay kept; new-flow jobs are
    # created "undecided" explicitly.
    decision = models.CharField(max_length=16, choices=DECISION_CHOICES, default="kept")
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "local_date"], name="scanjob_user_date_idx"),
            models.Index(fields=["user", "status"], name="scanjob_user_status_idx"),
            models.Index(fields=["user", "decision"], name="scanjob_user_decision_idx"),
        ]
        constraints = [
            # The create view's row lock is what serializes creates; this
            # makes "one running scan per user" hold for every other writer
            # too (admin, shell, a future endpoint) (scan-2 audit L5).
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status__in=("pending", "processing")),
                name="scanjob_one_active_per_user",
            ),
        ]

    def __str__(self) -> str:
        return f"ScanJob {self.uuid} ({self.mode}, {self.status})"


def scan_photo_path(instance: "ScanJobImage", filename: str) -> str:
    """Stable per-role key; ``filename`` is ignored (the client never names it)."""
    job = instance.job
    return f"scans/{job.user_id}/{job.uuid}/{instance.role}.jpg"


class ScanJobImage(models.Model):
    ROLE_CHOICES = [
        ("problem", "Problem"),
        ("leaf", "Leaf"),
        ("whole", "Whole plant"),
        ("flower", "Flower"),
    ]

    job = models.ForeignKey(ScanJob, on_delete=models.CASCADE, related_name="images")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    # A callable storage: never the default storage. Pass normalize_scan_photo()
    # output so the stored file is a re-encoded, EXIF-free JPEG.
    image = models.ImageField(storage=scan_photo_storage, upload_to=scan_photo_path)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job", "role"], name="scanjobimage_job_role_uniq"
            )
        ]

    def __str__(self) -> str:
        return f"{self.job_id}:{self.role}"


@receiver(post_delete, sender=ScanJobImage)
def delete_scan_photo_on_commit(sender, instance: ScanJobImage, **kwargs) -> None:
    """Remove the stored file once the delete commits. Never raises.

    Covers account deletion through the CASCADE. Pattern: apps/users/avatars.py.
    """
    name = instance.image.name if instance.image else ""
    if not name:
        return
    storage = instance.image.storage

    def delete() -> None:
        try:
            storage.delete(name)
        except Exception:
            logger.exception("[SCAN] Could not delete a scan photo file")

    transaction.on_commit(delete)
