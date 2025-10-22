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
from pybreaker import CircuitBreakerListener

logger = logging.getLogger(__name__)


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

    def state_change(self, cb, old_state, new_state):
        """
        Called when circuit breaker changes state.

        Args:
            cb: CircuitBreaker instance
            old_state: Previous state string ('closed', 'open', 'half_open')
            new_state: New state string ('closed', 'open', 'half_open')
        """
        self.last_state_change = datetime.now()

        logger.warning(
            f"[CIRCUIT] {self.service_name} state transition: "
            f"{old_state.upper()} → {new_state.upper()} "
            f"(fail_count={cb.fail_counter})"
        )

        # Track when circuit opens for duration monitoring
        if new_state == 'open':
            self.circuit_open_time = datetime.now()
            logger.error(
                f"[CIRCUIT] {self.service_name} circuit OPENED - "
                f"API calls blocked for {cb.reset_timeout}s "
                f"(consecutive failures: {cb.fail_counter})"
            )

        # Log successful recovery
        elif old_state == 'half_open' and new_state == 'closed':
            if self.circuit_open_time:
                duration = (datetime.now() - self.circuit_open_time).total_seconds()
                logger.info(
                    f"[CIRCUIT] {self.service_name} circuit CLOSED - "
                    f"Service recovered after {duration:.1f}s downtime"
                )
                self.circuit_open_time = None

        # Log half-open testing
        elif new_state == 'half_open':
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
        if cb.current_state == 'half_open':
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
        if cb.current_state == 'half_open':
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

        # Log all failures with details
        logger.error(
            f"[CIRCUIT] {self.service_name} call FAILED - "
            f"{exception.__class__.__name__}: {str(exception)[:100]} "
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
            'state': state,
            'service_name': self.monitor.service_name,
            'fail_count': self.circuit.fail_counter,
            'fail_max': self.circuit.fail_max,
            'reset_timeout': self.circuit.reset_timeout,
            'success_threshold': self.circuit.success_threshold,
        }

        # Add time-based metrics
        if self.monitor.last_state_change:
            status['last_state_change'] = self.monitor.last_state_change.isoformat()

        if state == 'open' and self.monitor.circuit_open_time:
            duration = (datetime.now() - self.monitor.circuit_open_time).total_seconds()
            status['open_duration_seconds'] = int(duration)
            status['retry_in_seconds'] = self.monitor._get_retry_time(self.circuit)

        return status

    def is_healthy(self) -> bool:
        """
        Check if circuit is in healthy state (closed).

        Returns:
            True if circuit is closed, False otherwise
        """
        return self.circuit.current_state == 'closed'

    def is_degraded(self) -> bool:
        """
        Check if circuit is in degraded state (half-open).

        Returns:
            True if circuit is testing recovery, False otherwise
        """
        return self.circuit.current_state == 'half_open'

    def is_unavailable(self) -> bool:
        """
        Check if circuit is unavailable (open).

        Returns:
            True if circuit is open, False otherwise
        """
        return self.circuit.current_state == 'open'


# Convenience function for creating monitored circuit breakers
def create_monitored_circuit(
    service_name: str,
    fail_max: int,
    reset_timeout: int,
    success_threshold: int = 1,
    timeout: Optional[int] = None,  # Note: timeout not supported by pybreaker - included for documentation
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
        'fail_max': fail_max,
        'reset_timeout': reset_timeout,
        'exclude': [KeyboardInterrupt],  # Never break on Ctrl+C
        'listeners': [monitor],
    }

    # Add optional parameters
    if success_threshold > 1:
        circuit_kwargs['success_threshold'] = success_threshold

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
