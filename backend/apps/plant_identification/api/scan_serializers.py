"""Serializers for the Scan 2.0 job API (B4).

``ScanJobSerializer`` is the job JSON every scan endpoint returns. Photo URLs
point at the authenticated photo stream, never at storage: scan photos have
no public URL.
"""

from __future__ import annotations

from typing import Dict, Optional

from django.urls import reverse
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ..constants import SCAN_MODE_CHOICES
from ..scan_models import ScanJob, ScanJobImage

# The photo shown as the job's thumbnail: the first present, in this order.
COVER_PHOTO_ORDER = ("whole", "leaf", "problem", "flower")

SCAN_ROLES = tuple(role for role, _label in ScanJobImage.ROLE_CHOICES)


def _photo_url(request, job: ScanJob, role: str) -> str:
    # Resolve within the live request's namespace (docs/rules/api.md).
    ns = request.resolver_match.namespace if request.resolver_match else ""
    name = f"{ns}:scans-photos" if ns else "scans-photos"
    path = reverse(name, kwargs={"uuid": job.uuid, "role": role})
    url: str = request.build_absolute_uri(path)
    return url


class ScanJobSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uuid", read_only=True)
    charged_as = serializers.ChoiceField(
        choices=SCAN_MODE_CHOICES,
        allow_blank=True,
        read_only=True,
        help_text="What the scan was charged as; empty until it is done or "
        "degraded, and always empty for a failed or cancelled scan.",
    )
    result = serializers.JSONField(
        read_only=True,
        allow_null=True,
        help_text="The scan's summary once it is done or degraded; null otherwise.",
    )
    photos = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()

    class Meta:
        model = ScanJob
        fields = [
            "id",
            "mode",
            "status",
            "charged_as",
            "created_at",
            "finished_at",
            "result",
            "photos",
            "cover_photo",
        ]
        read_only_fields = fields

    def _roles(self, job: ScanJob) -> list[str]:
        # images is prefetched by the view; .all() reuses the prefetch.
        return [image.role for image in job.images.all()]

    @extend_schema_field(
        {
            "type": "object",
            "additionalProperties": {"type": "string", "format": "uri"},
            "description": "Absolute URL of each stored photo, keyed by role.",
        }
    )
    def get_photos(self, job: ScanJob) -> Dict[str, str]:
        request = self.context["request"]
        return {role: _photo_url(request, job, role) for role in self._roles(job)}

    @extend_schema_field({"type": "string", "format": "uri", "nullable": True})
    def get_cover_photo(self, job: ScanJob) -> Optional[str]:
        roles = set(self._roles(job))
        for role in COVER_PHOTO_ORDER:
            if role in roles:
                return _photo_url(self.context["request"], job, role)
        return None


class ScanJobCreateSerializer(serializers.Serializer):
    """The multipart create request: documents the form for the schema.

    The view validates the files itself (role rules depend on the mode).
    """

    mode = serializers.ChoiceField(choices=SCAN_MODE_CHOICES)
    utc_offset_minutes = serializers.IntegerField(
        required=False,
        help_text="Minutes east of UTC (-840..840); absent or invalid means UTC.",
    )
    problem = serializers.ImageField(
        required=False, help_text="Close-up of the problem. Required for diagnose."
    )
    leaf = serializers.ImageField(
        required=False, help_text="A leaf. Required for identify."
    )
    whole = serializers.ImageField(required=False, help_text="The whole plant.")
    flower = serializers.ImageField(required=False, help_text="A flower.")
