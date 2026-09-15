"""A failed identification provider must SAY SO (todo 393).

The defect these pin down was not an outage, it was silence. With Plant.id
credit-blocked and PlantNet healthy, `identify_plant` still returned populated
`combined_suggestions` and `care_instructions`; `source`, `confidence_score` and
`disease_detection` were simply never set, the error branch never fired because
it required BOTH providers to fail, and the only log line said
`Unexpected Plant.id error: HTTPError` -- which distinguishes nothing. Disease
diagnosis, a headline feature, was off in production with nobody told. It was
caught by hand, during an unrelated key rotation.

So the cases worth testing are the ways it could go quiet again:

  - a PARTIAL failure must be visible. One provider down and the other up is the
    exact shape that produced no signal at all.
  - "the plant is healthy" and "the health endpoint failed" must not render
    identically. `disease_detection: null` meant both, which is why nothing
    downstream could tell them apart -- including a human reading the response.
  - identification succeeding must NOT imply disease detection ran. They are
    separate Plant.id endpoints and the second one's failure was swallowed, so
    `source == "plant_id"` can coexist with disease detection being off.
  - an UNCONFIGURED provider must not count as failed, or a single-provider
    deployment is permanently "degraded" and the signal gets ignored.
  - the circuit listener must not log the credential. PlantNet sends its key in
    the query string and `str(exception)` carries the prepared URL.
"""

from unittest.mock import Mock, patch

import pytest
import requests
from apps.plant_identification.provider_failures import classify_provider_failure
from apps.plant_identification.services.combined_identification_service import (
    CombinedPlantIdentificationService,
    ProviderOutcome,
)
from requests.models import PreparedRequest, Response

PLANT_ID_OK = {
    "suggestions": [{"plant_name": "Monstera deliciosa", "probability": 0.9}],
    "top_suggestion": {"plant_name": "Monstera deliciosa"},
    "confidence": 0.9,
    "health_assessment": None,
    "health_assessment_error": None,
}
PLANTNET_OK = {
    "results": [
        {"score": 0.8, "species": {"scientificNameWithoutAuthor": "Monstera deliciosa"}}
    ]
}


def http_error(status: int) -> requests.exceptions.HTTPError:
    """A real requests HTTPError whose message carries a key-bearing URL."""
    url = f"https://my-api.plantnet.org/v2/identify/all?api-key={CREDENTIAL}"
    resp = Response()
    resp.status_code = status
    resp.url = url
    resp.reason = "Forbidden"
    req = PreparedRequest()
    req.prepare_method("GET")
    req.prepare_url(url, None)
    resp.request = req
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        return exc


CREDENTIAL = "2b10SUPERSECRETPLANTNETKEY"


def build(plant_id=None, plantnet=None):
    """A service with both providers stubbed; None means 'not configured'."""
    with patch.object(
        CombinedPlantIdentificationService, "__init__", lambda self: None
    ):
        svc = CombinedPlantIdentificationService()
    svc.plant_id = plant_id
    svc.plantnet = plantnet
    from apps.plant_identification.services.combined_identification_service import (
        get_executor,
    )

    svc.executor = get_executor()
    return svc


def provider(returns=None, raises=None):
    stub = Mock()
    stub.identify_plant = Mock(return_value=returns, side_effect=raises)
    return stub


# --------------------------------------------------------------------------
# the production shape: one provider down, the other fine
# --------------------------------------------------------------------------


def test_a_failed_plant_id_is_reported_even_though_plantnet_answered():
    svc = build(
        plant_id=provider(raises=http_error(403)),
        plantnet=provider(returns=PLANTNET_OK),
    )

    out = svc.identify_plant(b"image-bytes")

    # The old behaviour is preserved: the user still gets an answer.
    assert out["combined_suggestions"], "PlantNet's answer must still come through"
    assert "error" not in out, "a partial failure is not a failed request"
    # ... but it is no longer silent.
    assert out["degraded"] is True
    assert out["providers"]["plant_id"]["status"] == "failed"
    assert out["providers"]["plant_id"]["reason"] == "auth-rejected"
    assert out["providers"]["plantnet"]["status"] == "ok"
    # Disease detection is a Plant.id-only feature, so it is off -- and says why.
    assert out["disease_detection"] is None
    assert out["disease_detection_status"] == "unavailable"
    assert out["disease_detection_reason"] == "auth-rejected"


def test_a_healthy_plant_does_not_look_like_a_failure():
    """The discriminator the old response could not express."""
    svc = build(
        plant_id=provider(returns=PLANT_ID_OK),  # health ran, found nothing
        plantnet=provider(returns=PLANTNET_OK),
    )

    out = svc.identify_plant(b"image-bytes")

    assert out["degraded"] is False
    assert out["source"] == "plant_id"
    assert out["disease_detection"] is None  # same value as the failure case...
    assert out["disease_detection_status"] == "ok"  # ...different meaning
    assert out["disease_detection_reason"] is None


def test_identification_can_succeed_while_disease_detection_is_off():
    """Two Plant.id endpoints; the second one's failure used to vanish."""
    svc = build(
        plant_id=provider(
            returns={**PLANT_ID_OK, "health_assessment_error": "http-402"}
        ),
        plantnet=provider(returns=PLANTNET_OK),
    )

    out = svc.identify_plant(b"image-bytes")

    assert out["source"] == "plant_id", "identification itself worked"
    assert out["providers"]["plant_id"]["status"] == "ok"
    assert out["disease_detection_status"] == "unavailable"
    assert out["disease_detection_reason"] == "http-402"


def test_an_unconfigured_provider_is_not_a_failure():
    svc = build(plant_id=None, plantnet=provider(returns=PLANTNET_OK))

    out = svc.identify_plant(b"image-bytes")

    assert out["providers"]["plant_id"]["status"] == "not_configured"
    assert out["providers"]["plant_id"]["reason"] is None
    assert out["degraded"] is False, (
        "a deployment that never enabled Plant.id is not degraded; "
        "calling it degraded trains people to ignore the flag"
    )


def test_both_providers_failing_still_produces_the_error_and_names_both():
    svc = build(
        plant_id=provider(raises=requests.exceptions.Timeout()),
        plantnet=provider(raises=http_error(429)),
    )

    out = svc.identify_plant(b"image-bytes")

    assert "error" in out
    assert out["degraded"] is True
    assert out["providers"]["plant_id"]["reason"] == "timeout"
    assert out["providers"]["plantnet"]["reason"] == "rate-limited"


def test_the_degraded_log_line_names_the_provider_and_the_reason():
    """Asserted on the module logger: the project's JSON logging sets
    propagate=False, so caplog never sees `apps.*` records."""
    svc = build(
        plant_id=provider(raises=http_error(403)),
        plantnet=provider(returns=PLANTNET_OK),
    )

    with patch(
        "apps.plant_identification.services.combined_identification_service.logger"
    ) as log:
        svc.identify_plant(b"image-bytes")

    degraded = [
        c.args[0] for c in log.error.call_args_list if "[DEGRADED]" in str(c.args[0])
    ]
    assert degraded, "a partial failure must leave a greppable line"
    assert "plant_id=auth-rejected" in degraded[0]
    assert "disease_detection=unavailable" in degraded[0]


# --------------------------------------------------------------------------
# the circuit listener sits behind BOTH services
# --------------------------------------------------------------------------


def test_the_circuit_failure_log_does_not_carry_the_api_key():
    """PlantNet sends its key as the `api-key` query parameter, and
    `str(exception)` is built from the prepared URL.

    This listener used to log `str(exception)[:100]`. Truncation is not
    redaction: measured against a 22-character key, a 403 on a short path put 15
    of those characters into the log, and a shorter host or reason phrase puts
    in more. The call sites inside the services were hardened for this; the
    listener behind both of them was missed.
    """
    from apps.plant_identification.circuit_monitoring import CircuitMonitor

    monitor = CircuitMonitor("plantnet_api")
    breaker = Mock(fail_counter=1, fail_max=3)

    with patch("apps.plant_identification.circuit_monitoring.logger") as log:
        monitor.failure(breaker, http_error(403))

    logged = " ".join(str(c.args[0]) for c in log.error.call_args_list)
    assert CREDENTIAL not in logged, f"credential leaked into the log: {logged}"
    assert CREDENTIAL[:8] not in logged, "not even a prefix of the key"
    assert "auth-rejected" in logged, "but the reason must still be there"
    assert "HTTPError(status=403)" in logged


def test_opening_the_circuit_raises_an_alert_a_human_can_see():
    """AC 4: a THRESHOLD signal. The circuit opens only after fail_max
    consecutive failures, so this cannot fire on a single slow request."""
    from apps.plant_identification import circuit_monitoring

    monitor = circuit_monitoring.CircuitMonitor("plant_id_api")
    monitor.last_failure_reason = "payment-required"
    breaker = Mock(fail_counter=3, fail_max=3, reset_timeout=60)

    with patch.object(circuit_monitoring.sentry_sdk, "capture_message") as alert:
        monitor.state_change(breaker, "closed", "open")

    alert.assert_called_once()
    message = alert.call_args.args[0]
    assert "plant_id_api" in message
    assert "payment-required" in message, "the alert must name the reason"
    assert alert.call_args.kwargs["level"] == "error"


def test_a_recovering_circuit_does_not_alert():
    """Only OPEN is the alert condition; half-open and closed are recovery."""
    from apps.plant_identification import circuit_monitoring

    monitor = circuit_monitoring.CircuitMonitor("plant_id_api")
    breaker = Mock(fail_counter=0, fail_max=3, reset_timeout=60)

    with patch.object(circuit_monitoring.sentry_sdk, "capture_message") as alert:
        monitor.state_change(breaker, "open", "half_open")
        monitor.state_change(breaker, "half_open", "closed")

    alert.assert_not_called()


def test_a_real_circuit_reaching_its_threshold_actually_raises_the_alert():
    """Drive a REAL pybreaker circuit to OPEN and assert the alert comes out.

    The two tests above call `state_change(breaker, "closed", "open")` by hand
    on a `Mock` breaker whose `fail_counter` is pre-set, and hand-assign
    `last_failure_reason`. That pins what the listener does GIVEN the
    transition -- but every step that PRODUCES the transition is supplied by
    the test, so three links in the chain go unchecked, and all three have to
    hold for a real outage to reach a person:

      * that pybreaker calls `state_change` at all, with `"open"` as the name
        this listener matches on (it compares against a lowercase string);
      * that it fires on the fail_max-th failure and NOT before -- which is the
        entire difference between the threshold alert this AC asks for and a
        per-request alert that would page on one slow call;
      * that `last_failure_reason` is filled in by the real `failure()`
        callback from the real exception, rather than by the test. A `None`
        there would still produce an alert, just one that names nothing.

    A fresh breaker, not the module-level `_plant_id_circuit`, so this leaves no
    state behind for another test to trip over.
    """
    from apps.plant_identification import circuit_monitoring
    from pybreaker import CircuitBreakerError

    circuit, _monitor, _stats = circuit_monitoring.create_monitored_circuit(
        "plant_id_api", fail_max=3, reset_timeout=60, success_threshold=2
    )

    def payment_required():
        raise http_error(402)

    with patch.object(circuit_monitoring.sentry_sdk, "capture_message") as alert:
        for _ in range(2):
            with pytest.raises(requests.exceptions.HTTPError):
                circuit.call(payment_required)

        assert circuit.current_state == "closed"
        assert alert.call_count == 0, (
            "Alerted below the threshold. The circuit is what makes this a "
            "SUSTAINED-failure signal; firing on failure 1 of 3 would page a "
            "human for a single timeout and the alerts would be ignored."
        )

        # The call that TRIPS the threshold raises CircuitBreakerError, not the
        # provider's own exception -- pybreaker substitutes it in `on_failure`.
        # That substitution is why `classify_provider_failure` maps
        # CircuitBreakerError to `circuit-open`. The listener is unaffected: it
        # still receives the original HTTPError, which is how the alert below
        # can name `payment-required` rather than `circuit-open`.
        with pytest.raises(CircuitBreakerError):
            circuit.call(payment_required)

    assert circuit.current_state == "open"
    alert.assert_called_once()

    message = alert.call_args.args[0]
    assert "plant_id_api" in message, "the alert must name which provider died"
    assert "payment-required" in message, (
        "the reason must survive from the real exception, through the real "
        "failure() callback, into the alert -- unlike the Mock-breaker tests "
        "above, nothing here hand-sets it"
    )
    assert alert.call_args.kwargs["level"] == "error"


# --------------------------------------------------------------------------
# the reason vocabulary
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, "auth-rejected"),
        (403, "auth-rejected"),
        (402, "payment-required"),
        (429, "rate-limited"),
        (500, "http-500"),  # unmapped -> names the status, never guesses
        (418, "http-418"),
    ],
)
def test_http_status_reasons(status, expected):
    assert classify_provider_failure(http_error(status)) == expected


def test_an_unmapped_status_names_itself_rather_than_guessing():
    """The honesty rule: a wrong reason stated with authority is worse than none.

    Which status Plant.id returns on credit exhaustion has never been observed,
    so nothing may be labelled 'credit-blocked' on speculation.
    """
    assert classify_provider_failure(http_error(507)) == "http-507"


def test_non_http_failures_are_named_too():
    assert classify_provider_failure(requests.exceptions.Timeout()) == "timeout"
    assert (
        classify_provider_failure(requests.exceptions.ConnectionError())
        == "connection-error"
    )
    assert classify_provider_failure(ValueError()) == "response-malformed"


def test_a_reason_never_carries_the_exception_message():
    """Messages can hold a URL with a query-string credential."""
    reason = classify_provider_failure(RuntimeError(f"boom ?api-key={CREDENTIAL}"))
    assert CREDENTIAL not in reason
    assert reason == "RuntimeError"


# --------------------------------------------------------------------------
# ProviderOutcome
# --------------------------------------------------------------------------


def test_provider_outcome_distinguishes_absent_from_failed():
    assert ProviderOutcome({"x": 1}).failed is False
    assert ProviderOutcome(None, "timeout").failed is True
    assert ProviderOutcome(None, None, configured=False).failed is False
    # A failure with no reason must still render as failed, not as ok.
    assert ProviderOutcome(None, None).as_status() == {
        "status": "failed",
        "reason": "unknown",
    }


def test_the_alert_cannot_crash_the_failure_path_it_reports_on():
    """Alerting is never allowed to break the thing it is watching.

    This runs inside a circuit-breaker listener. If `capture_message` raises --
    a broken DSN, a transport error, a serialization failure -- an unguarded
    call would turn "the provider is down" into "the provider is down and the
    listener crashed", losing the circuit-open log line as well as the alert.

    Before todo 395 the failure mode was AttributeError, because
    `backend/sentry_sdk.py` was a local stub with no `capture_message` at all.
    The stub is gone, so this asserts the durable invariant -- any exception is
    contained -- rather than that one vanished symptom.
    """
    from apps.plant_identification import circuit_monitoring

    monitor = circuit_monitoring.CircuitMonitor("plant_id_api")
    monitor.last_failure_reason = "rate-limited"
    breaker = Mock(fail_counter=3, fail_max=3, reset_timeout=60)

    with patch.object(
        circuit_monitoring.sentry_sdk,
        "capture_message",
        side_effect=RuntimeError("transport is down"),
    ):
        with patch.object(circuit_monitoring, "logger") as log:
            monitor.state_change(breaker, "closed", "open")  # must not raise

    # Asserted on the module logger, not caplog: `apps.*` sets propagate=False.
    written = " ".join(str(c) for c in log.mock_calls)
    assert "circuit OPENED" in written, (
        "the circuit-open log line is the signal that survives a dead alert "
        "channel; losing it leaves the outage completely invisible"
    )
    assert "RuntimeError" in written, "say why the alert did not go out"


def test_the_alert_failure_notice_never_logs_the_sentry_message():
    """A Sentry exception message can quote the DSN, which carries a key."""
    from apps.plant_identification import circuit_monitoring

    monitor = circuit_monitoring.CircuitMonitor("plant_id_api")
    breaker = Mock(fail_counter=3, fail_max=3, reset_timeout=60)
    # Fabricated, not a real DSN. The whole point of the test is that this
    # value must NOT reach the log, so it has to look like the real thing.
    secret_dsn = (
        "https://deadbeefcafe@o123.ingest.sentry.io/456"  # pragma: allowlist secret
    )

    with patch.object(
        circuit_monitoring.sentry_sdk,
        "capture_message",
        side_effect=RuntimeError(f"bad dsn: {secret_dsn}"),
    ):
        with patch.object(circuit_monitoring, "logger") as log:
            monitor.state_change(breaker, "closed", "open")

    written = " ".join(str(c) for c in log.mock_calls)
    assert "deadbeefcafe" not in written, "the DSN key reached the log"
    assert secret_dsn not in written


def test_no_local_stub_shadows_the_real_sentry_package():
    """The todo 395 fix, pinned in the place that depends on it.

    This test previously asserted the OPPOSITE -- that `backend/sentry_sdk.py`
    shadowed the installed package -- and was written to fail loudly when the
    stub was removed, so the fix could not go unnoticed. It has now been
    inverted rather than deleted: the same line is what proves the bug is gone
    and what will catch a convenience stub being re-added.

    `backend/` is the Django project root and so is on `sys.path`. Any module
    named `sentry_sdk.py` placed there wins over the installed package and
    silently disables all error reporting. See
    `apps/core/tests/test_sentry_options_drift.py` for the settings half.
    """
    from pathlib import Path

    import sentry_sdk

    project_root = Path(__file__).resolve().parents[3]

    # The direct check, and the one that cannot be argued with: the shadowing
    # file is a module named sentry_sdk sitting in the project root itself.
    # This holds whatever else happens to be on sys.path, and does not depend
    # on which copy won the import.
    for shadow in (project_root / "sentry_sdk.py", project_root / "sentry_sdk"):
        assert not shadow.exists(), (
            f"{shadow} exists. backend/ is the Django project root and so is on "
            "sys.path, so a module named sentry_sdk there wins over the "
            "installed package and silently disables all error reporting "
            "(todo 395)."
        )

    resolved = Path(sentry_sdk.__file__).resolve()

    # `not under project_root` was the original phrasing and it is WRONG here:
    # this project's documented venv is backend/venv, so the real installed SDK
    # is under project_root too and the guard failed for every local developer
    # while passing in CI, where site-packages sits outside the repo. A check
    # that fires on the correct state teaches people to ignore it. Exempt the
    # package directories rather than dropping the repo check, which still
    # catches a stub dropped anywhere else in the tree.
    in_site_packages = any(
        part in ("site-packages", "dist-packages") for part in resolved.parts
    )
    assert in_site_packages or not resolved.is_relative_to(project_root), (
        f"sentry_sdk resolves to {resolved}, inside {project_root} and outside "
        "any site-packages -- a local module is shadowing the real SDK and "
        "init() is a no-op (todo 395)"
    )
    assert hasattr(sentry_sdk, "capture_message")


def test_the_summary_says_when_the_health_check_did_not_run():
    """`summary` is the one field a client may render alone, so an omission
    there is the 'quietly thinner payload' this todo is about."""
    svc = build(
        plant_id=provider(raises=http_error(403)),
        plantnet=provider(returns=PLANTNET_OK),
    )
    out = svc.identify_plant(b"image-bytes")

    summary = svc.get_identification_summary(out)
    assert "Health check unavailable" in summary
    assert "auth-rejected" not in summary, "reason tokens are for logs, not people"


def test_a_healthy_plant_summary_says_nothing_about_availability():
    svc = build(
        plant_id=provider(returns=PLANT_ID_OK),
        plantnet=provider(returns=PLANTNET_OK),
    )
    out = svc.identify_plant(b"image-bytes")

    summary = svc.get_identification_summary(out)
    assert "Health check unavailable" not in summary
    assert "Identified as:" in summary


def test_an_executor_timeout_is_named_like_any_other_failure():
    """The one reason token produced by `gather` rather than `call`."""
    from concurrent.futures import TimeoutError as FuturesTimeoutError

    svc = build(
        plant_id=provider(returns=PLANT_ID_OK),
        plantnet=provider(returns=PLANTNET_OK),
    )
    real_submit = svc.executor.submit

    class SlowFuture:
        def result(self, timeout=None):
            raise FuturesTimeoutError()

    def submit(fn, *a, **k):
        # Only the Plant.id call stalls; PlantNet still answers.
        return SlowFuture() if "plant_id" in fn.__name__ else real_submit(fn, *a, **k)

    with patch.object(svc.executor, "submit", side_effect=submit):
        out = svc.identify_plant(b"image-bytes")

    assert out["providers"]["plant_id"]["status"] == "failed"
    assert out["providers"]["plant_id"]["reason"] == "executor-timeout"
    assert out["degraded"] is True
    assert out["disease_detection_reason"] == "executor-timeout"


def test_a_detected_disease_still_warns_and_is_not_swallowed_by_the_new_branch():
    """The `elif` added for the unavailable case must not disturb the existing
    warning -- it sits on the same if/elif chain."""
    diseased = {
        **PLANT_ID_OK,
        "health_assessment": {"is_healthy": False, "disease_name": "Powdery mildew"},
    }
    svc = build(
        plant_id=provider(returns=diseased), plantnet=provider(returns=PLANTNET_OK)
    )
    out = svc.identify_plant(b"image-bytes")

    assert out["disease_detection_status"] == "ok"
    summary = svc.get_identification_summary(out)
    assert "Health Issue Detected: Powdery mildew" in summary
    assert "Health check unavailable" not in summary
