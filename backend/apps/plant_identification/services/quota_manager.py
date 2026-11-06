"""
API Quota Management Service

Tracks API usage for Plant.id and PlantNet to prevent quota exhaustion.
Uses Redis for distributed quota tracking across multiple Django workers.

Features:
- Daily/monthly quota tracking for Plant.id
- Daily/hourly quota tracking for PlantNet
- Warning logs at 80% threshold
- Graceful degradation when quotas exceeded
- Automatic expiration of quota counters
"""

import logging
from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone
from typing import Any, Dict, Optional, cast

from django.conf import settings
from django_redis import get_redis_connection
from redis import Redis

from ..constants import (
    PLANT_ID_QUOTA_WARNING_THRESHOLD,
    PLANTNET_DAILY_QUOTA,
    PLANTNET_HOURLY_QUOTA,
    PLANTNET_QUOTA_WARNING_THRESHOLD,
    QUOTA_KEY_PREFIX_PLANT_ID_DAILY,
    QUOTA_KEY_PREFIX_PLANT_ID_MONTHLY,
    QUOTA_KEY_PREFIX_PLANTNET_DAILY,
    QUOTA_KEY_PREFIX_PLANTNET_HOURLY,
)

logger = logging.getLogger(__name__)


class QuotaExceeded(Exception):
    """Raised when API quota has been exhausted."""

    pass


class QuotaManager:
    """
    Manages API quota tracking for Plant.id and PlantNet services.

    Uses Redis for distributed quota counters that persist across
    multiple Django worker processes.
    """

    def __init__(self):
        """Initialize QuotaManager with Redis connection."""
        self.redis_client = self._get_redis_connection()

    def _get_redis_connection(self) -> Optional[Redis]:
        """
        Get Redis connection for quota tracking.

        Returns:
            Redis client or None if Redis unavailable
        """
        try:
            redis_client: Redis = get_redis_connection("default")
            # Verify connection
            redis_client.ping()
            return redis_client
        except Exception as e:
            logger.warning(f"[QUOTA] Redis unavailable for quota tracking: {e}")
            return None

    def _seconds_until_midnight(self) -> int:
        """
        Calculate seconds until midnight UTC for daily quota expiration.

        Returns:
            Seconds until next midnight UTC
        """
        now = datetime.now(dt_timezone.utc)
        tomorrow = datetime.combine(
            now.date() + timedelta(days=1), time.min, tzinfo=dt_timezone.utc
        )
        return int((tomorrow - now).total_seconds())

    def _seconds_until_month_end(self) -> int:
        """
        Calculate seconds until end of month UTC for monthly quota expiration.

        Returns:
            Seconds until end of current month UTC
        """
        now = datetime.now(dt_timezone.utc)
        # Get first day of next month
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1, tzinfo=dt_timezone.utc)
        else:
            next_month = datetime(now.year, now.month + 1, 1, tzinfo=dt_timezone.utc)
        return int((next_month - now).total_seconds())

    def _ensure_ttl(self, key: str, seconds: int) -> None:
        """Give ``key`` an expiry if it has none.

        Checked after every increment, not only the first: an increment whose
        EXPIRE never ran (a crash between the two commands, or a Redis error)
        would otherwise leave a counter that never resets, and the API would
        stay "over quota" until someone deleted the key by hand. TTL -1 means
        no expiry. Works on every Redis version (EXPIRE NX needs 7.0).
        """
        client = self.redis_client
        if client is not None and cast(int, client.ttl(key)) < 0:
            client.expire(key, seconds)
            logger.info(f"[QUOTA] {key} expiry set ({seconds}s)")

    # =========================================================================
    # Plant.id Quota Management
    # =========================================================================

    def can_call_plant_id(self, calls: int = 1, reserve: int = 0) -> bool:
        """
        Check whether `calls` more Plant.id calls fit under both caps.

        Args:
            calls: API calls about to be made (a diagnosis makes 2).
            reserve: Daily calls to leave untouched for a later diagnosis.

        Returns:
            True iff daily + calls + reserve <= the daily cap and
            monthly + calls <= the monthly cap. Fails open when Redis is down.
        """
        if not self.redis_client:
            # Redis unavailable - allow call (fail open)
            logger.warning(
                "[QUOTA] Redis unavailable, allowing Plant.id call (no quota tracking)"
            )
            return True

        try:
            daily_ok = (
                self.get_plant_id_daily_usage() + calls + reserve
                <= settings.PLANT_ID_DAILY_QUOTA
            )
            monthly_ok = (
                self.get_plant_id_monthly_usage() + calls
                <= settings.PLANT_ID_MONTHLY_QUOTA
            )
            return bool(daily_ok and monthly_ok)
        except Exception as e:
            logger.error(f"[QUOTA] Error checking Plant.id quota: {e}")
            return True  # Fail open

    def get_plant_id_daily_usage(self) -> int:
        """
        Get current Plant.id daily usage count.

        Returns:
            Number of API calls made today
        """
        if not self.redis_client:
            return 0

        try:
            count = cast(
                Optional[bytes], self.redis_client.get(QUOTA_KEY_PREFIX_PLANT_ID_DAILY)
            )
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"[QUOTA] Error getting Plant.id daily usage: {e}")
            return 0

    def get_plant_id_monthly_usage(self) -> int:
        """
        Get current Plant.id monthly usage count.

        Returns:
            Number of API calls made this month
        """
        if not self.redis_client:
            return 0

        try:
            count = cast(
                Optional[bytes],
                self.redis_client.get(QUOTA_KEY_PREFIX_PLANT_ID_MONTHLY),
            )
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"[QUOTA] Error getting Plant.id monthly usage: {e}")
            return 0

    def reserve_plant_id(self, calls: int = 1, reserve: int = 0) -> bool:
        """Atomically claim ``calls`` Plant.id calls under both caps.

        ``can_call_plant_id`` then ``increment_plant_id`` after the HTTP calls
        let two concurrent jobs both pass at 1/3 and land at 5/3. Here each
        INCRBY is the claim: a counter that went over its cap is rolled back
        with DECRBY and the claim refused. A claim that was not spent (a cache
        hit after it, an open circuit, a failed first call) is handed back
        with ``release_plant_id``. Fails open when Redis is down, like
        ``can_call_plant_id``.

        Args:
            calls: API calls about to be made (a diagnosis makes 2).
            reserve: Daily calls to leave untouched for a later diagnosis.
        """
        client = self.redis_client
        if client is None:
            logger.warning(
                "[QUOTA] Redis unavailable, allowing Plant.id call (no quota tracking)"
            )
            return True
        daily_key = QUOTA_KEY_PREFIX_PLANT_ID_DAILY
        monthly_key = QUOTA_KEY_PREFIX_PLANT_ID_MONTHLY
        try:
            daily = cast(int, client.incrby(daily_key, calls))
            self._ensure_ttl(daily_key, self._seconds_until_midnight())
            if daily + reserve > settings.PLANT_ID_DAILY_QUOTA:
                client.decrby(daily_key, calls)
                return False
            monthly = cast(int, client.incrby(monthly_key, calls))
            self._ensure_ttl(monthly_key, self._seconds_until_month_end())
            if monthly > settings.PLANT_ID_MONTHLY_QUOTA:
                client.decrby(monthly_key, calls)
                client.decrby(daily_key, calls)
                return False
        except Exception as e:
            logger.error(f"[QUOTA] Error reserving Plant.id quota: {e}")
            return True  # Fail open
        logger.info(
            f"[QUOTA] Plant.id usage: {daily}/{settings.PLANT_ID_DAILY_QUOTA} daily, "
            f"{monthly}/{settings.PLANT_ID_MONTHLY_QUOTA} monthly"
        )
        return True

    def release_plant_id(self, calls: int) -> None:
        """Hand back ``calls`` reserved Plant.id calls that were never made."""
        client = self.redis_client
        if client is None or calls <= 0:
            return
        try:
            client.decrby(QUOTA_KEY_PREFIX_PLANT_ID_DAILY, calls)
            client.decrby(QUOTA_KEY_PREFIX_PLANT_ID_MONTHLY, calls)
        except Exception as e:
            logger.error(f"[QUOTA] Error releasing Plant.id quota: {e}")

    def increment_plant_id(self, calls: int = 1) -> None:
        """
        Add `calls` real API calls to the Plant.id counters (daily and monthly).

        Sets expiration times automatically on first increment.
        Logs warnings when approaching quota limits (80% threshold).
        """
        if not self.redis_client:
            return

        daily_quota = settings.PLANT_ID_DAILY_QUOTA
        monthly_quota = settings.PLANT_ID_MONTHLY_QUOTA
        try:
            # Increment daily counter
            daily_count = cast(
                int, self.redis_client.incrby(QUOTA_KEY_PREFIX_PLANT_ID_DAILY, calls)
            )
            self._ensure_ttl(
                QUOTA_KEY_PREFIX_PLANT_ID_DAILY, self._seconds_until_midnight()
            )

            # Increment monthly counter
            monthly_count = cast(
                int, self.redis_client.incrby(QUOTA_KEY_PREFIX_PLANT_ID_MONTHLY, calls)
            )
            self._ensure_ttl(
                QUOTA_KEY_PREFIX_PLANT_ID_MONTHLY, self._seconds_until_month_end()
            )

            # Log current usage
            logger.info(
                f"[QUOTA] Plant.id usage: {daily_count}/{daily_quota} daily, "
                f"{monthly_count}/{monthly_quota} monthly"
            )

            # Warn if approaching daily quota
            daily_threshold = daily_quota * PLANT_ID_QUOTA_WARNING_THRESHOLD
            if daily_count >= daily_threshold and daily_count < daily_quota:
                remaining = daily_quota - daily_count
                logger.warning(
                    f"[QUOTA] WARNING: Plant.id approaching daily quota! "
                    f"{daily_count}/{daily_quota} used ({remaining} remaining)"
                )

            # Warn if approaching monthly quota
            monthly_threshold = monthly_quota * PLANT_ID_QUOTA_WARNING_THRESHOLD
            if monthly_count >= monthly_threshold and monthly_count < monthly_quota:
                remaining = monthly_quota - monthly_count
                logger.warning(
                    f"[QUOTA] WARNING: Plant.id approaching monthly quota! "
                    f"{monthly_count}/{monthly_quota} used ({remaining} remaining)"
                )

            # Error if quota exceeded
            if daily_count > daily_quota:
                logger.error(
                    f"[QUOTA] ERROR: Plant.id daily quota EXCEEDED! "
                    f"{daily_count}/{daily_quota}"
                )

        except Exception as e:
            logger.error(f"[QUOTA] Error incrementing Plant.id quota: {e}")

    # =========================================================================
    # PlantNet Quota Management
    # =========================================================================

    def can_call_plantnet(self) -> bool:
        """
        Check if PlantNet hourly quota is available.

        Returns:
            True if quota available, False if exhausted
        """
        if not self.redis_client:
            # Redis unavailable - allow call (fail open)
            logger.warning(
                "[QUOTA] Redis unavailable, allowing PlantNet call (no quota tracking)"
            )
            return True

        try:
            hourly_count = self.get_plantnet_hourly_usage()
            return hourly_count < PLANTNET_HOURLY_QUOTA
        except Exception as e:
            logger.error(f"[QUOTA] Error checking PlantNet quota: {e}")
            return True  # Fail open

    def get_plantnet_hourly_usage(self) -> int:
        """
        Get current PlantNet hourly usage count.

        Returns:
            Number of API calls made this hour
        """
        if not self.redis_client:
            return 0

        try:
            count = cast(
                Optional[bytes], self.redis_client.get(QUOTA_KEY_PREFIX_PLANTNET_HOURLY)
            )
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"[QUOTA] Error getting PlantNet hourly usage: {e}")
            return 0

    def get_plantnet_daily_usage(self) -> int:
        """
        Get current PlantNet daily usage count.

        Returns:
            Number of API calls made today
        """
        if not self.redis_client:
            return 0

        try:
            count = cast(
                Optional[bytes], self.redis_client.get(QUOTA_KEY_PREFIX_PLANTNET_DAILY)
            )
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"[QUOTA] Error getting PlantNet daily usage: {e}")
            return 0

    def increment_plantnet(self) -> None:
        """
        Increment PlantNet usage counters (hourly and daily).

        Sets expiration times automatically on first increment.
        Logs warnings when approaching quota limits (80% threshold).
        """
        if not self.redis_client:
            return

        try:
            # Increment hourly counter
            hourly_count = cast(
                int, self.redis_client.incr(QUOTA_KEY_PREFIX_PLANTNET_HOURLY)
            )
            self._ensure_ttl(QUOTA_KEY_PREFIX_PLANTNET_HOURLY, 3600)

            # Increment daily counter
            daily_count = cast(
                int, self.redis_client.incr(QUOTA_KEY_PREFIX_PLANTNET_DAILY)
            )
            self._ensure_ttl(
                QUOTA_KEY_PREFIX_PLANTNET_DAILY, self._seconds_until_midnight()
            )

            # Log current usage
            logger.info(
                f"[QUOTA] PlantNet usage: {hourly_count}/{PLANTNET_HOURLY_QUOTA} hourly, "
                f"{daily_count}/{PLANTNET_DAILY_QUOTA} daily"
            )

            # Warn if approaching hourly quota
            hourly_threshold = PLANTNET_HOURLY_QUOTA * PLANTNET_QUOTA_WARNING_THRESHOLD
            if (
                hourly_count >= hourly_threshold
                and hourly_count < PLANTNET_HOURLY_QUOTA
            ):
                remaining = PLANTNET_HOURLY_QUOTA - hourly_count
                logger.warning(
                    f"[QUOTA] WARNING: PlantNet approaching hourly quota! "
                    f"{hourly_count}/{PLANTNET_HOURLY_QUOTA} used ({remaining} remaining)"
                )

            # Warn if approaching daily quota
            daily_threshold = PLANTNET_DAILY_QUOTA * PLANTNET_QUOTA_WARNING_THRESHOLD
            if daily_count >= daily_threshold and daily_count < PLANTNET_DAILY_QUOTA:
                remaining = PLANTNET_DAILY_QUOTA - daily_count
                logger.warning(
                    f"[QUOTA] WARNING: PlantNet approaching daily quota! "
                    f"{daily_count}/{PLANTNET_DAILY_QUOTA} used ({remaining} remaining)"
                )

            # Error if quota exceeded
            if hourly_count > PLANTNET_HOURLY_QUOTA:
                logger.error(
                    f"[QUOTA] ERROR: PlantNet hourly quota EXCEEDED! "
                    f"{hourly_count}/{PLANTNET_HOURLY_QUOTA}"
                )

        except Exception as e:
            logger.error(f"[QUOTA] Error incrementing PlantNet quota: {e}")

    # =========================================================================
    # Quota Status Reporting
    # =========================================================================

    def get_quota_status(self) -> Dict[str, Any]:
        """
        Get current quota status for all APIs.

        Returns:
            Dictionary with quota usage statistics
        """
        return {
            "plant_id": {
                "daily": {
                    "used": self.get_plant_id_daily_usage(),
                    "limit": settings.PLANT_ID_DAILY_QUOTA,
                    "remaining": max(
                        0,
                        settings.PLANT_ID_DAILY_QUOTA - self.get_plant_id_daily_usage(),
                    ),
                    "available": self.can_call_plant_id(),
                },
                "monthly": {
                    "used": self.get_plant_id_monthly_usage(),
                    "limit": settings.PLANT_ID_MONTHLY_QUOTA,
                    "remaining": max(
                        0,
                        settings.PLANT_ID_MONTHLY_QUOTA
                        - self.get_plant_id_monthly_usage(),
                    ),
                },
            },
            "plantnet": {
                "hourly": {
                    "used": self.get_plantnet_hourly_usage(),
                    "limit": PLANTNET_HOURLY_QUOTA,
                    "remaining": max(
                        0, PLANTNET_HOURLY_QUOTA - self.get_plantnet_hourly_usage()
                    ),
                    "available": self.can_call_plantnet(),
                },
                "daily": {
                    "used": self.get_plantnet_daily_usage(),
                    "limit": PLANTNET_DAILY_QUOTA,
                    "remaining": max(
                        0, PLANTNET_DAILY_QUOTA - self.get_plantnet_daily_usage()
                    ),
                },
            },
        }
