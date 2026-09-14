"""Name WHY an identification provider returned nothing.

Todo 393. Before this, a total failure of the primary provider was silent: with
Plant.id credit-blocked and PlantNet healthy,
`combined_identification_service.identify_plant` still returned populated
`combined_suggestions` and `care_instructions`, while `source`,
`confidence_score` and `disease_detection` were simply never set. No error, no
metric, and a log line that said `Unexpected Plant.id error: HTTPError` -- which
distinguishes nothing. Disease diagnosis is a headline feature and it was off in
production with nobody told.

The point of this module is that a reason is a STABLE TOKEN, greppable and
comparable across requests, rather than a formatted exception. Tokens go into
bracketed log lines (`docs/rules/api.md`) and into the API response, so both a
human reading logs and a client rendering a degraded state see the same word.

HONESTY RULE, and it is the whole design constraint here
  A token must claim only what the evidence supports. `402` means the HTTP
  status was 402 Payment Required -- it does NOT mean "Plant.id ran out of
  credits", because **which status Plant.id returns on credit exhaustion has
  never been observed**. The account was funded before any identification ran
  against an empty one, and there is no way to force the condition from a funded
  key. So the mapping covers only statuses whose meaning is fixed by HTTP
  itself, and anything else becomes `http-<status>` -- always specific, never a
  guess wearing a confident label. A wrong reason stated with authority is worse
  than the silence this replaces, because it sends the next person somewhere
  else entirely.

  When a real credit block is eventually observed, add the mapping and record
  the observed status in todo 393's Work Log. Do not add it from documentation.
"""

import requests
from apps.core.exceptions import ExternalAPIError
from pybreaker import CircuitBreakerError

from .services.quota_manager import QuotaExceeded

# Statuses whose meaning is fixed by HTTP itself, not by any vendor's usage.
_STATUS_REASONS = {
    401: "auth-rejected",
    403: "auth-rejected",
    402: "payment-required",
    429: "rate-limited",
}

UNKNOWN = "unknown"


def classify_provider_failure(exc: BaseException) -> str:
    """Return a stable token naming why a provider call failed.

    Ordering matters: the specific exception types are checked before
    `RequestException`, because `HTTPError`, `Timeout` and `ConnectionError` are
    all subclasses of it and a single `RequestException` branch would collapse
    them into one useless token.
    """
    if isinstance(exc, CircuitBreakerError):
        return "circuit-open"
    if isinstance(exc, QuotaExceeded):
        return "local-quota-exceeded"
    if isinstance(exc, ExternalAPIError):
        # Raised by the services themselves; 503 is the circuit's fast-fail.
        status = getattr(exc, "status_code", None)
        if status == 503:
            return "circuit-open"
        return _STATUS_REASONS.get(
            status, f"http-{status}" if status else "unavailable"
        )
    if isinstance(exc, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "connection-error"
    if isinstance(exc, requests.exceptions.HTTPError):
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        if status is None:
            return "http-error"
        return _STATUS_REASONS.get(status, f"http-{status}")
    if isinstance(exc, requests.exceptions.RequestException):
        return "request-failed"
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return "response-malformed"
    # Never return the exception's message -- it can carry a URL or payload.
    # The type name is safe, and `log_safe_api_error` handles the detail.
    return type(exc).__name__
