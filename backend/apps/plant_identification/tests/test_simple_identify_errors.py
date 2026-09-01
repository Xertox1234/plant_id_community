"""A rejected upload on the Identify endpoint returns a readable 400 (todo 320
sibling finding).

``apps.plant_identification.utils.validate_image_file`` raises DRF's
``ValidationError``; the view used to catch Django's, so the real reason fell
through to the generic 500 handler — and even the intended branch would have
rendered ``str(e)``, a Python list repr. The web client shows ``error``
verbatim (``plantIdService.extractErrorMessage``).
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
def test_rejected_upload_returns_a_readable_400():
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="identify-320"))
    not_an_image = SimpleUploadedFile(
        "notes.txt", b"just text", content_type="text/plain"
    )

    resp = client.post(
        reverse("v1:plant_identification:simple_identify"),
        {"image": not_an_image},
        format="multipart",
    )

    assert resp.status_code == 400
    assert resp.data["success"] is False
    error = resp.data["error"]
    assert error.startswith("Invalid Content-Type: text/plain"), error
    assert "ErrorDetail" not in error and not error.startswith("["), error
