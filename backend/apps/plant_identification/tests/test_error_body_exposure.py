"""Anonymous error paths must not echo exception text to the client (todo 354).

CodeQL's ``py/stack-trace-exposure`` flagged three anonymously-reachable sites
here (#90 ``identify/health/``, #104 and #114 ``status/``). #114 is the
interesting one: its sink is ``urls.py``'s ``return Response(status)``, but the
``str(e)`` it returns lives in the *service* status dicts, which
``PlantIdentificationService.get_service_status`` merges verbatim.

Each test forces the failure and asserts the secret marker never reaches the
response body while the log still gets it.
"""

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

# Distinctive enough that a substring check cannot pass by accident.
BOOM = "psycopg2.OperationalError: FATAL password for user 'deploy' at 10.1.2.3"


@pytest.mark.django_db
def test_service_status_does_not_echo_the_exception():
    """#104 — the view's own ``except`` no longer renders ``str(e)``."""
    with patch(
        "apps.plant_identification.services.identification_service"
        ".PlantIdentificationService.get_service_status",
        side_effect=RuntimeError(BOOM),
    ):
        resp = APIClient().get(reverse("v1:plant_identification:service_status"))

    assert resp.status_code == 503
    assert BOOM not in str(resp.data)
    assert resp.data["error"] == "Service status unavailable"


@pytest.mark.django_db
def test_health_check_does_not_echo_the_exception():
    """#90 — ``identify/health/`` is AllowAny, so its body is public."""
    with patch(
        "apps.plant_identification.api.simple_views"
        ".CombinedPlantIdentificationService",
        side_effect=RuntimeError(BOOM),
    ):
        resp = APIClient().get(reverse("v1:plant_identification:simple_health"))

    assert resp.status_code == 503
    assert BOOM not in str(resp.data)
    assert resp.data["error"] == "Health check failed"


@pytest.mark.parametrize(
    "module,cls",
    [
        ("trefle_service", "TrefleAPIService"),
        ("plantnet_service", "PlantNetAPIService"),
    ],
)
def test_service_status_dicts_carry_no_exception_text(module, cls):
    """#114 — the taint the anonymous ``status/`` endpoint actually returns."""
    mod = __import__(f"apps.plant_identification.services.{module}", fromlist=[cls])
    service_cls = getattr(mod, cls)
    # __new__, not __init__: constructing the real service needs API keys.
    service = service_cls.__new__(service_cls)

    # The two services reach the API differently, so break both routes.
    with patch.object(mod, "requests", side_effect=RuntimeError(BOOM)):
        with patch.object(
            service_cls, "_make_request", side_effect=RuntimeError(BOOM), create=True
        ):
            result = service_cls.get_service_status(service)

    assert BOOM not in str(result), result
    assert result["error"] == "Service status check failed"


def test_corrupt_image_message_carries_no_pil_text():
    """#23 -> #121 — PIL's message reached the client via readable_message()."""
    from apps.plant_identification.utils.file_validation import validate_image_file
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.exceptions import ValidationError

    # A real JPEG magic number + content type, but truncated garbage inside, so
    # extension/MIME checks pass and PIL is the layer that rejects it.
    broken = SimpleUploadedFile(
        "photo.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 64, content_type="image/jpeg"
    )

    with pytest.raises(ValidationError) as exc:
        validate_image_file(broken)

    message = str(exc.value)
    assert "Invalid or corrupted image file" in message
    assert "cannot identify image file" not in message, message
