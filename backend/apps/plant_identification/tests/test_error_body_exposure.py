"""Anonymous error paths must not echo exception text to the client (todo 354).

CodeQL's ``py/stack-trace-exposure`` flagged three anonymously-reachable sites
here (#90 ``identify/health/``, #104 and #114 ``status/``). #114 is the
interesting one: its sink is ``urls.py``'s ``return Response(status)``, but the
``str(e)`` it returns lives in the *service* status dicts, which
``PlantIdentificationService.get_service_status`` merges verbatim.

Each test forces the failure and asserts the secret marker never reaches the
response body while the log still gets it.
"""

import io
import logging
import pathlib
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
import requests
from django.urls import reverse
from rest_framework.test import APIClient

# Distinctive enough that a substring check cannot pass by accident.
BOOM = "psycopg2.OperationalError: FATAL password for user 'deploy' at 10.1.2.3"
# Stands in for TREFLE_API_KEY / PLANTNET_API_KEY in the prepared-URL message.
FAKE_KEY = "s3cret-provider-key-must-never-be-logged"


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


@contextmanager
def capture(logger):
    """Collect a module logger's output.

    Not ``caplog``: the ``apps.*`` loggers are configured ``propagate=False``,
    so pytest's root-attached handler never sees them and every assertion on
    ``caplog.text`` would pass vacuously.
    """
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.DEBUG)
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield buf
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


@pytest.mark.parametrize(
    "module,cls,key_param",
    [
        ("trefle_service", "TrefleAPIService", "token"),
        ("plantnet_service", "PlantNetAPIService", "api-key"),
    ],
)
def test_service_status_leaks_the_key_to_neither_body_nor_log(module, cls, key_param):
    """#114, and the credential leak review round 1 found underneath it.

    Both services send their API key as a QUERY PARAMETER, and ``requests``
    builds its exception message from the *prepared* URL — so ``str(e)``, and
    ``logger.exception``'s traceback, used to write the key into the log even
    after the response body was cleaned up.

    The failure is forced with a real ``HTTPError`` carrying a realistic URL,
    so both sinks are actually driven. An earlier version of this test passed
    ``__new__`` with no ``session`` and patched the module's ``requests``
    attribute, which meant the exception actually raised was ``AttributeError``
    and neither assertion touched the mechanism.
    """
    mod = __import__(f"apps.plant_identification.services.{module}", fromlist=[cls])
    service_cls = getattr(mod, cls)
    # __new__, not __init__: constructing the real service needs API keys.
    service = service_cls.__new__(service_cls)
    service.api_key = FAKE_KEY

    boom = requests.exceptions.HTTPError(
        "401 Client Error: Unauthorized for url: "
        f"https://provider.test/v1/plants?{key_param}={FAKE_KEY}&limit=1"
    )
    # PlantNet's status call goes through self.session.get; Trefle's goes
    # through _make_request. Break both so one parametrisation covers each.
    session = Mock()
    session.get.side_effect = boom
    service.session = session

    with patch.object(service_cls, "_make_request", side_effect=boom, create=True):
        with capture(mod.logger) as log:
            result = service_cls.get_service_status(service)

    # The exception really did reach the handler under test.
    assert result["status"] == "error", result
    assert result["error"] == "Service status check failed"

    assert FAKE_KEY not in str(result), f"key reached the response body: {result}"
    assert FAKE_KEY not in log.getvalue(), "key reached the log"
    # ...and the diagnostic that replaced it is actually useful.
    assert "HTTPError" in log.getvalue(), log.getvalue()


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


def _requests_handlers_interpolating_the_exception(path):
    """Yield (lineno, source) for every logger call that interpolates a
    ``requests`` exception.

    Scoping is deliberate. The exception name is checked only INSIDE its own
    ``except requests...`` block — a later ``except Exception as e`` rebinds the
    same name and can never receive a ``RequestException``, so flagging it
    would be a false positive. Aliases assigned inside the handler
    (``last_exception = e``) are followed across the whole function, because
    the retry decorator logs one after the loop has ended.

    ``e.response.status_code`` and ``log_safe_api_error(e)`` are the approved
    shapes and are not reported.
    """
    import ast

    def logger_calls(scope):
        for call in (n for n in ast.walk(scope) if isinstance(n, ast.Call)):
            if ast.unparse(call.func).startswith("logger."):
                yield call

    def interpolates(call, names):
        for arg in call.args:
            safe = set()
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Attribute):
                    safe |= {n for n in ast.walk(sub.value) if isinstance(n, ast.Name)}
                if isinstance(sub, ast.Call) and ast.unparse(sub.func).endswith(
                    "log_safe_api_error"
                ):
                    safe |= {n for n in ast.walk(sub) if isinstance(n, ast.Name)}
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Name) and sub.id in names and sub not in safe:
                    return True
        return False

    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for handler in (n for n in ast.walk(func) if isinstance(n, ast.ExceptHandler)):
            if not handler.name:
                continue
            if "requests" not in ast.unparse(handler.type or ast.Constant(None)):
                continue
            # The bound name, inside its own handler only.
            for call in logger_calls(handler):
                if interpolates(call, {handler.name}):
                    yield call.lineno, ast.unparse(call)
            # Aliases assigned in the handler outlive it — check the function.
            aliases = {
                t.id
                for n in ast.walk(handler)
                if isinstance(n, ast.Assign)
                and isinstance(n.value, ast.Name)
                and n.value.id == handler.name
                for t in n.targets
                if isinstance(t, ast.Name)
            }
            if aliases:
                for call in logger_calls(func):
                    if interpolates(call, aliases):
                        yield call.lineno, ast.unparse(call)


# Only the services that authenticate with a QUERY PARAMETER, where the
# prepared URL in the exception message carries the key. Header-authenticated
# clients (plant_id, plant_health, unsplash, pexels) are safe by construction;
# the weather services are fixed on the slice-1 branch. Widening this sweep to
# the whole service layer is todo 358.
KEYED_IN_QUERY_STRING = [
    "apps/plant_identification/services/plantnet_service.py",
    "apps/plant_identification/services/trefle_service.py",
]


@pytest.mark.parametrize("service", KEYED_IN_QUERY_STRING)
def test_no_requests_handler_interpolates_its_exception(service):
    """Drift guard (todo 354).

    ``requests`` puts the prepared URL in its exception message, so a service
    that authenticates with a query parameter leaks its key the moment a
    handler interpolates the exception. Trefle (``token``) and PlantNet
    (``api-key``) both did. The surviving ``{str(e)}`` calls in these files sit
    in ``except Exception`` blocks that a ``RequestException`` clause already
    shadows — this fails if anyone reorders those, or writes a new handler the
    same way. Use ``log_safe_api_error(exc)``.
    """
    offenders = list(_requests_handlers_interpolating_the_exception(service))
    assert not offenders, "\n".join(f"  line {n}: {src}" for n, src in offenders)
