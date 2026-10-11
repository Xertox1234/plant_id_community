"""A diagnosis photo's EXIF (GPS included) is never kept (todo 461).

The mobile app uploads the photo as image_picker hands it back, EXIF and all
(image_picker_android even copies the EXIF onto the resized file). The server
is what drops it: ``PlantDiseaseRequest.image_1`` is a ``ProcessedImageField``
that re-encodes the upload to JPEG before it is stored, and imagekit writes no
EXIF. plant.health is then sent that stored copy (``perform_create`` saves
first and diagnoses ``request_obj``), re-encoded once more by
``PlantHealthAPIService._prepare_image``.

These pin that, so a processor change that started carrying EXIF across
(``options={"exif": ...}``, or a raw-bytes passthrough) fails here.
"""

import io
import shutil
import tempfile
from unittest import mock

from apps.plant_identification.models import PlantDiseaseRequest
from apps.plant_identification.services.plant_health_service import (
    PlantHealthAPIService,
)
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

GPS_IFD = 0x8825
MAKE = 0x010F


def _jpeg_with_gps() -> bytes:
    """A real JPEG whose EXIF carries a camera make and a GPS position."""
    img = Image.new("RGB", (1600, 1200), (40, 120, 40))
    exif = Image.Exif()
    exif[MAKE] = "PhoneMaker"
    gps = exif.get_ifd(GPS_IFD)
    gps[1] = "N"  # GPSLatitudeRef
    gps[2] = (37.0, 46.0, 30.0)  # GPSLatitude
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    return buf.getvalue()


def _exif_of(fileobj) -> dict:
    with Image.open(fileobj) as im:
        exif = im.getexif()
        return {**dict(exif), **{GPS_IFD: dict(exif.get_ifd(GPS_IFD))}}


class DiagnosisPhotoExifTestCase(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        media = override_settings(MEDIA_ROOT=self.media_root)
        media.enable()
        self.addCleanup(media.disable)
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="exif", email="exif@example.com", password="x" * 16
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_fixture_really_carries_gps(self):
        """Guards the test itself: the upload does have EXIF to lose."""
        exif = _exif_of(io.BytesIO(_jpeg_with_gps()))
        self.assertEqual(exif[MAKE], "PhoneMaker")
        self.assertEqual(exif[GPS_IFD][1], "N")

    def test_the_stored_photo_and_what_plant_health_reads_have_no_exif(self):
        seen = {}

        def capture(request_obj):
            seen["name"] = request_obj.image_1.name
            request_obj.image_1.open("rb")
            seen["exif"] = _exif_of(request_obj.image_1)
            return []

        with mock.patch(
            "apps.plant_identification.views.PlantDiseaseService"
        ) as service:
            service.return_value.diagnose_disease_from_request.side_effect = capture
            response = self.client.post(
                "/api/v1/plant-identification/disease-requests/",
                {
                    "image_1": SimpleUploadedFile(
                        "IMG_0042.jpg", _jpeg_with_gps(), content_type="image/jpeg"
                    ),
                    "symptoms_description": "Brown spots spreading upward",
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, 201, response.data)
        # plant.health is handed the stored request, not the raw upload.
        self.assertEqual(seen["exif"], {GPS_IFD: {}})

        stored = PlantDiseaseRequest.objects.get(user=self.user)
        self.assertEqual(stored.image_1.name, seen["name"])
        with stored.image_1.open("rb") as fh:
            self.assertEqual(_exif_of(fh), {GPS_IFD: {}})

    def test_the_plant_health_payload_is_re_encoded_without_exif(self):
        import base64

        payload = PlantHealthAPIService.__new__(PlantHealthAPIService)._prepare_image(
            io.BytesIO(_jpeg_with_gps())
        )
        self.assertEqual(_exif_of(io.BytesIO(base64.b64decode(payload))), {GPS_IFD: {}})
