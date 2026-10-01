"""The PlantNet circuit breaker opens and then fails fast (todo 464, from 001).

`plantnet_service.py` routes every identify call through the module-level
`_plantnet_circuit` (`create_monitored_circuit("plantnet_api")`), but until
now only Plant.id's breaker had a test (`test_circuit_breaker_locks.py`).
Nothing showed that PLANTNET_CIRCUIT_FAIL_MAX consecutive failures open the
PlantNet breaker, or that an open breaker answers WITHOUT an HTTP request --
which is the whole point: during an outage we stop paying latency (and quota)
for calls we already know will fail.

The HTTP layer is `requests.Session.post`; the call count on that mock is the
proof that the fast-fail never reached it.
"""

import io
from unittest.mock import Mock, patch

import requests
from apps.core.exceptions import ExternalAPIError
from apps.plant_identification.constants import PLANTNET_CIRCUIT_FAIL_MAX
from apps.plant_identification.services import plantnet_service
from apps.plant_identification.services.plantnet_service import PlantNetAPIService
from django.core.cache import cache
from django.test import SimpleTestCase
from PIL import Image


def _reset_plantnet_circuit():
    """Close the module-level breaker so no test leaks an open circuit."""
    circuit = plantnet_service._plantnet_circuit
    circuit._state_storage.reset_counter()
    circuit._state_storage.reset_success_counter()
    circuit.close()


def _jpeg(color="red"):
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color).save(buf, format="JPEG")
    buf.seek(0)
    return buf


class PlantNetCircuitBreakerFailMaxTests(SimpleTestCase):
    def test_fail_max_is_the_documented_five(self):
        """Pin the threshold literally: the breaker tests below derive their
        failure counts from the constant, so on their own they would still
        pass if it shrank to 1 (``docs/rules/testing.md``: tracking a
        constant does not pin it)."""
        self.assertEqual(PLANTNET_CIRCUIT_FAIL_MAX, 5)
        self.assertEqual(plantnet_service._plantnet_circuit.fail_max, 5)


class PlantNetCircuitBreakerTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        _reset_plantnet_circuit()
        # Quota is Redis-backed; pin it open so the only thing that can stop a
        # call reaching the HTTP layer is the breaker under test.
        quota = patch.object(plantnet_service, "QuotaManager")
        self.quota = quota.start().return_value
        self.quota.can_call_plantnet.return_value = True
        self.addCleanup(quota.stop)

    def tearDown(self):
        _reset_plantnet_circuit()
        cache.clear()

    @patch("apps.plant_identification.services.plantnet_service.requests.Session")
    def test_breaker_opens_after_fail_max_and_then_fails_fast_without_http(
        self, mock_session
    ):
        post = mock_session.return_value.post
        failing = Mock()
        failing.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "503 Server Error"
        )
        post.return_value = failing

        service = PlantNetAPIService(api_key="test-key")
        self.assertIs(service.circuit, plantnet_service._plantnet_circuit)
        self.assertEqual(service.circuit.current_state, "closed")

        # N real failures, each one an actual HTTP attempt. The colours do NOT
        # keep the cache keys distinct: after the service's JPEG q85 re-encode,
        # (0,0,0) and (1,0,0) come out byte-identical. They do not need to --
        # failures are never cached, so every call still reaches the HTTP layer.
        for i in range(PLANTNET_CIRCUIT_FAIL_MAX):
            with self.assertRaises(ExternalAPIError):
                service.identify_plant([_jpeg((i, 0, 0))])
        self.assertEqual(post.call_count, PLANTNET_CIRCUIT_FAIL_MAX)

        # The breaker is now open...
        self.assertEqual(service.circuit.current_state, "open")

        # ...so the next call raises the service-degraded error WITHOUT
        # touching the HTTP layer.
        with self.assertRaises(ExternalAPIError) as ctx:
            service.identify_plant([_jpeg("blue")])
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("temporarily unavailable", str(ctx.exception))
        self.assertEqual(post.call_count, PLANTNET_CIRCUIT_FAIL_MAX)

    @patch("apps.plant_identification.services.plantnet_service.requests.Session")
    def test_breaker_stays_closed_below_fail_max(self, mock_session):
        """One failure short of the threshold still makes the HTTP call --
        the fast-fail above is the breaker's doing, not an artefact of the
        mocks refusing every request."""
        post = mock_session.return_value.post
        failing = Mock()
        failing.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "503 Server Error"
        )
        post.return_value = failing

        service = PlantNetAPIService(api_key="test-key")
        for i in range(PLANTNET_CIRCUIT_FAIL_MAX - 1):
            with self.assertRaises(ExternalAPIError):
                service.identify_plant([_jpeg((0, i, 0))])

        self.assertEqual(service.circuit.current_state, "closed")
        with self.assertRaises(ExternalAPIError):
            service.identify_plant([_jpeg("green")])
        self.assertEqual(post.call_count, PLANTNET_CIRCUIT_FAIL_MAX)
