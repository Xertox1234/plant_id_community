"""
Circuit Breaker Event Listeners for Monitoring and Logging

Implements event handlers for pybreaker circuit state changes to provide
visibility into circuit breaker behavior using our bracketed logging pattern.

Usage:
    from .circuit_monitoring import CircuitMonitor

    circuit_breaker = CircuitBreaker(
        fail_max=3,
        reset_timeout=60,
        listeners=[CircuitMonitor('plant_id_api')]
    )
"""

import logging
from datetime import datetime
from typing import Optional

import sentry_sdk
from apps.core.utils.pii_safe_logging import log_safe_api_error
from pybreaker import CircuitBreakerListener

from .provider_failures import classify_provider_failure

logger = logging.getLogger(__name__)


def _alert(message: str) -> None:
    """Raise a threshold alert to Sentry.

    Sentry is real now. Until todo 395 landed, `backend/sentry_sdk.py` was a
    five-line local stub -- "Minimal test stub for sentry_sdk to avoid hard
    dependency during local tests" -- committed in the first backend commit.
    `backend/` is the Django project root and therefore on `sys.path`, so
    `import sentry_sdk` resolved to that stub and NOT to the real
    `sentry-sdk==2.68.1` in requirements.txt. `sentry_sdk.init()` returned None
    for the project's entire history, so no error, trace or profile ever reached
    Sentry. The stub is gone; the import resolves to the installed package.

    **Delivery still depends on SENTRY_DSN being set**, and it is not set in
    production today. With no DSN, `init()` is never called and
    `capture_message` is a no-op -- which is what makes this safe in dev and in
    tests. Setting the DSN is what turns this into something a human sees.

    The try/except is NOT leftover scaffolding from the stub era. Alerting must
    never be able to break the failure path it reports on: this runs inside a
    circuit-breaker listener, so an exception here would turn "the provider is
    down" into "the provider is down and the listener crashed". Only the
    exception TYPE is logged -- a Sentry exception message can contain the DSN,
    which carries a key.
    """
    try:
        sentry_sdk.capture_message(message, level="error")
    except Exception as exc:  # noqa: BLE001 - see docstring; must never propagate
        alert_error = type(exc).__name__
        logger.warning(
            f"[CIRCUIT] Sentry alert not sent ({alert_error}); "
            "the circuit-open log line above is the surviving signal"
        )


class CircuitMonitor(CircuitBreakerListener):
    """
    Circuit breaker event listener for monitoring and logging state changes.

    Implements the bracketed logging pattern ([CIRCUIT] prefix) for easy
    filtering and monitoring of circuit breaker events.
    """

    def __init__(self, service_name: str):
        """
        Initialize circuit monitor for a specific service.

        Args:
            service_name: Name of the service being monitored (e.g., 'plant_id_api')
        """
        self.service_name = service_name
        self.last_state_change = None
        self.circuit_open_time = None
        self.consecutive_failures = 0
        self.last_failure_reason = None

    def state_change(self, cb, old_state, new_state):
        """
        Called when circuit breaker changes state.

        Args:
            cb: CircuitBreaker instance
            old_state: Previous state (CircuitBreakerState object or string)
            new_state: New state (CircuitBreakerState object or string)
        """
        self.last_state_change = datetime.now()

        # pybreaker passes state objects; extract name string for logging
        old_name = old_state.name if hasattr(old_state, "name") else str(old_state)
        new_name = new_state.name if hasattr(new_state, "name") else str(new_state)

        logger.warning(
            f"[CIRCUIT] {self.service_name} state transition: "
            f"{old_name.upper()} → {new_name.upper()} "
            f"(fail_count={cb.fail_counter})"
        )

        # Track when circuit opens for duration monitoring
        if new_name == "open":
            self.circuit_open_time = datetime.now()
            logger.error(
                f"[CIRCUIT] {self.service_name} circuit OPENED - "
                f"API calls blocked for {cb.reset_timeout}s "
                f"(consecutive failures: {cb.fail_counter}, "
                f"last reason: {self.last_failure_reason})"
            )
            # Todo 393 AC 4: a THRESHOLD alert, not a per-request one. The
            # circuit only opens after fail_max consecutive failures, which is
            # exactly the "sustained failure" condition -- so this fires when a
            # provider is genuinely down, not when one request times out.
            # capture_message is a no-op when SENTRY_DSN is unset, so this is
            # safe in dev and in tests; whether it reaches a person in
            # production depends on that DSN being configured.
            _alert(
                f"{self.service_name} circuit OPENED after "
                f"{cb.fail_counter} consecutive failures "
                f"(last reason: {self.last_failure_reason})"
            )

        # Log successful recovery
        elif old_name == "half_open" and new_name == "closed":
            if self.circuit_open_time:
                duration = (datetime.now() - self.circuit_open_time).total_seconds()
                logger.info(
                    f"[CIRCUIT] {self.service_name} circuit CLOSED - "
                    f"Service recovered after {duration:.1f}s downtime"
                )
                self.circuit_open_time = None

        # Log half-open testing
        elif new_name == "half_open":
            logger.info(
                f"[CIRCUIT] {self.service_name} entering HALF-OPEN state - "
                f"Testing service recovery"
            )

    def before_call(self, cb, func, *args, **kwargs):
        """
        Called before executing the protected function.

        Args:
            cb: CircuitBreaker instance
            func: Function about to be called
            args: Function positional arguments
            kwargs: Function keyword arguments
        """
        # Only log in half-open state to avoid spam
        if cb.current_state == "half_open":
            logger.info(
                f"[CIRCUIT] {self.service_name} testing recovery call "
                f"(half-open state)"
            )

    def success(self, cb):
        """
        Called after a successful function execution.

        Args:
            cb: CircuitBreaker instance
        """
        # Reset consecutive failure counter
        self.consecutive_failures = 0

        # Only log successes in half-open state (recovery progress)
        if cb.current_state == "half_open":
            logger.info(
                f"[CIRCUIT] {self.service_name} recovery test SUCCESS "
                f"({cb._state_storage.counter} / {cb.success_threshold} required)"
            )

    def failure(self, cb, exception):
        """
        Called after a failed function execution.

        Args:
            cb: CircuitBreaker instance
            exception: Exception that was raised
        """
        self.consecutive_failures += 1
        self.last_failure_reason = classify_provider_failure(exception)

        # NOT str(exception): `requests` builds its message from the PREPARED
        # URL, and PlantNet sends its credential as the `api-key` query
        # parameter (plantnet_service.py:251). Truncating to 100 characters is
        # not redaction -- measured against a 22-character key, a 403 on a short
        # path put 15 of those characters in the log, and a shorter host or
        # reason phrase puts in more. The call sites inside the services were
        # fixed for this; this listener sits behind BOTH of them and was missed.
        # See log_safe_api_error's docstring, which describes this exact hole.
        logger.error(
            f"[CIRCUIT] {self.service_name} call FAILED ({self.last_failure_reason}) - "
            f"{log_safe_api_error(exception)} "
            f"(fail_count={cb.fail_counter}/{cb.fail_max})"
        )

        # Warn when approaching circuit open threshold
        if cb.fail_counter == cb.fail_max - 1:
            logger.warning(
                f"[CIRCUIT] {self.service_name} WARNING - "
                f"One more failure will open circuit "
                f"({cb.fail_counter}/{cb.fail_max})"
            )

    def call_failed(self, cb, exception):
        """
        Called when the circuit is open and call is blocked without execution.

        Args:
            cb: CircuitBreaker instance
            exception: CircuitBreakerError that will be raised
        """
        logger.warning(
            f"[CIRCUIT] {self.service_name} call BLOCKED - "
            f"Circuit is OPEN, fast-failing without API call "
            f"(retry in {self._get_retry_time(cb)}s)"
        )

    def _get_retry_time(self, cb) -> int:
        """
        Calculate seconds until circuit can retry.

        Args:
            cb: CircuitBreaker instance

        Returns:
            Seconds until reset_timeout expires
        """
        if self.circuit_open_time:
            elapsed = (datetime.now() - self.circuit_open_time).total_seconds()
            remaining = max(0, cb.reset_timeout - elapsed)
            return int(remaining)
        return cb.reset_timeout


class CircuitStats:
    """
    Helper class to track and retrieve circuit breaker statistics.

    Usage:
        stats = CircuitStats(circuit_breaker, monitor)
        status = stats.get_status()
    """

    def __init__(self, circuit_breaker, monitor: CircuitMonitor):
        """
        Initialize circuit stats tracker.

        Args:
            circuit_breaker: pybreaker.CircuitBreaker instance
            monitor: CircuitMonitor instance
        """
        self.circuit = circuit_breaker
        self.monitor = monitor

    def get_status(self) -> dict:
        """
        Get current circuit breaker status for health checks.

        Returns:
            Dictionary with circuit state and metrics
        """
        state = self.circuit.current_state

        status = {
            "state": state,
            "service_name": self.monitor.service_name,
            "fail_count": self.circuit.fail_counter,
            "fail_max": self.circuit.fail_max,
            "reset_timeout": self.circuit.reset_timeout,
            "success_threshold": self.circuit.success_threshold,
        }

        # Add time-based metrics
        if self.monitor.last_state_change:
            status["last_state_change"] = self.monitor.last_state_change.isoformat()

        if state == "open" and self.monitor.circuit_open_time:
            duration = (datetime.now() - self.monitor.circuit_open_time).total_seconds()
            status["open_duration_seconds"] = int(duration)
            status["retry_in_seconds"] = self.monitor._get_retry_time(self.circuit)

        return status

    def is_healthy(self) -> bool:
        """
        Check if circuit is in healthy state (closed).

        Returns:
            True if circuit is closed, False otherwise
        """
        return self.circuit.current_state == "closed"

    def is_degraded(self) -> bool:
        """
        Check if circuit is in degraded state (half-open).

        Returns:
            True if circuit is testing recovery, False otherwise
        """
        return self.circuit.current_state == "half_open"

    def is_unavailable(self) -> bool:
        """
        Check if circuit is unavailable (open).

        Returns:
            True if circuit is open, False otherwise
        """
        return self.circuit.current_state == "open"


# Convenience function for creating monitored circuit breakers
def create_monitored_circuit(
    service_name: str,
    fail_max: int,
    reset_timeout: int,
    success_threshold: int = 1,
    timeout: Optional[
        int
    ] = None,  # Note: timeout not supported by pybreaker - included for documentation
) -> tuple:
    """
    Factory function to create a circuit breaker with monitoring.

    Args:
        service_name: Name of the service (e.g., 'plant_id_api')
        fail_max: Number of failures before opening circuit
        reset_timeout: Seconds to wait before testing recovery
        success_threshold: Consecutive successes needed to close circuit
        timeout: Optional timeout (not used by circuit breaker - handle in service layer)

    Returns:
        Tuple of (CircuitBreaker, CircuitMonitor, CircuitStats)

    Example:
        circuit, monitor, stats = create_monitored_circuit(
            'plant_id_api',
            fail_max=3,
            reset_timeout=60,
            success_threshold=2
        )

    Note:
        The timeout parameter is not passed to pybreaker CircuitBreaker.
        Timeouts should be handled in the service layer (e.g., requests timeout).
        This parameter is included for API consistency and documentation.
    """
    from pybreaker import CircuitBreaker

    monitor = CircuitMonitor(service_name)

    circuit_kwargs = {
        "fail_max": fail_max,
        "reset_timeout": reset_timeout,
        "exclude": [KeyboardInterrupt],  # Never break on Ctrl+C
        "listeners": [monitor],
    }

    # Add optional parameters
    if success_threshold > 1:
        circuit_kwargs["success_threshold"] = success_threshold

    # Note: timeout is NOT passed to CircuitBreaker
    # It should be handled in the service layer (e.g., requests.post(timeout=X))

    circuit = CircuitBreaker(**circuit_kwargs)
    stats = CircuitStats(circuit, monitor)

    logger.info(
        f"[CIRCUIT] Initialized circuit breaker for {service_name} "
        f"(fail_max={fail_max}, reset_timeout={reset_timeout}s, "
        f"success_threshold={success_threshold})"
    )

    return circuit, monitor, stats
