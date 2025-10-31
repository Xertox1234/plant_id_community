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
from datetime import datetime, timedelta, time
from typing import Optional, Dict, Any
from django.core.cache import cache
from redis import Redis
from django_redis import get_redis_connection

from ..constants import (
    PLANT_ID_DAILY_QUOTA,
    PLANT_ID_MONTHLY_QUOTA,
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
            redis_client = get_redis_connection('default')
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
        now = datetime.utcnow()
        tomorrow = datetime.combine(now.date() + timedelta(days=1), time.min)
        return int((tomorrow - now).total_seconds())

    def _seconds_until_month_end(self) -> int:
        """
        Calculate seconds until end of month UTC for monthly quota expiration.

        Returns:
            Seconds until end of current month UTC
        """
        now = datetime.utcnow()
        # Get first day of next month
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime(now.year, now.month + 1, 1)
        return int((next_month - now).total_seconds())

    # =========================================================================
    # Plant.id Quota Management
    # =========================================================================

    def can_call_plant_id(self) -> bool:
        """
        Check if Plant.id daily quota is available.

        Returns:
            True if quota available, False if exhausted
        """
        if not self.redis_client:
            # Redis unavailable - allow call (fail open)
            logger.warning("[QUOTA] Redis unavailable, allowing Plant.id call (no quota tracking)")
            return True

        try:
            daily_count = self.get_plant_id_daily_usage()
            return daily_count < PLANT_ID_DAILY_QUOTA
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
            count = self.redis_client.get(QUOTA_KEY_PREFIX_PLANT_ID_DAILY)
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
            count = self.redis_client.get(QUOTA_KEY_PREFIX_PLANT_ID_MONTHLY)
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"[QUOTA] Error getting Plant.id monthly usage: {e}")
            return 0

    def increment_plant_id(self) -> None:
        """
        Increment Plant.id usage counters (daily and monthly).

        Sets expiration times automatically on first increment.
        Logs warnings when approaching quota limits (80% threshold).
        """
        if not self.redis_client:
            return

        try:
            # Increment daily counter
            daily_count = self.redis_client.incr(QUOTA_KEY_PREFIX_PLANT_ID_DAILY)
            if daily_count == 1:
                # First call today - set expiration to midnight
                ttl = self._seconds_until_midnight()
                self.redis_client.expire(QUOTA_KEY_PREFIX_PLANT_ID_DAILY, ttl)
                logger.info(f"[QUOTA] Plant.id daily counter started (expires in {ttl}s)")

            # Increment monthly counter
            monthly_count = self.redis_client.incr(QUOTA_KEY_PREFIX_PLANT_ID_MONTHLY)
            if monthly_count == 1:
                # First call this month - set expiration to end of month
                ttl = self._seconds_until_month_end()
                self.redis_client.expire(QUOTA_KEY_PREFIX_PLANT_ID_MONTHLY, ttl)
                logger.info(f"[QUOTA] Plant.id monthly counter started (expires in {ttl}s)")

            # Log current usage
            logger.info(f"[QUOTA] Plant.id usage: {daily_count}/{PLANT_ID_DAILY_QUOTA} daily, "
                       f"{monthly_count}/{PLANT_ID_MONTHLY_QUOTA} monthly")

            # Warn if approaching daily quota
            daily_threshold = PLANT_ID_DAILY_QUOTA * PLANT_ID_QUOTA_WARNING_THRESHOLD
            if daily_count >= daily_threshold and daily_count < PLANT_ID_DAILY_QUOTA:
                remaining = PLANT_ID_DAILY_QUOTA - daily_count
                logger.warning(f"[QUOTA] WARNING: Plant.id approaching daily quota! "
                             f"{daily_count}/{PLANT_ID_DAILY_QUOTA} used ({remaining} remaining)")

            # Warn if approaching monthly quota
            monthly_threshold = PLANT_ID_MONTHLY_QUOTA * PLANT_ID_QUOTA_WARNING_THRESHOLD
            if monthly_count >= monthly_threshold and monthly_count < PLANT_ID_MONTHLY_QUOTA:
                remaining = PLANT_ID_MONTHLY_QUOTA - monthly_count
                logger.warning(f"[QUOTA] WARNING: Plant.id approaching monthly quota! "
                             f"{monthly_count}/{PLANT_ID_MONTHLY_QUOTA} used ({remaining} remaining)")

            # Error if quota exceeded
            if daily_count > PLANT_ID_DAILY_QUOTA:
                logger.error(f"[QUOTA] ERROR: Plant.id daily quota EXCEEDED! "
                           f"{daily_count}/{PLANT_ID_DAILY_QUOTA}")

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
            logger.warning("[QUOTA] Redis unavailable, allowing PlantNet call (no quota tracking)")
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
            count = self.redis_client.get(QUOTA_KEY_PREFIX_PLANTNET_HOURLY)
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
            count = self.redis_client.get(QUOTA_KEY_PREFIX_PLANTNET_DAILY)
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
            hourly_count = self.redis_client.incr(QUOTA_KEY_PREFIX_PLANTNET_HOURLY)
            if hourly_count == 1:
                # First call this hour - set expiration to 1 hour
                self.redis_client.expire(QUOTA_KEY_PREFIX_PLANTNET_HOURLY, 3600)
                logger.info("[QUOTA] PlantNet hourly counter started (expires in 3600s)")

            # Increment daily counter
            daily_count = self.redis_client.incr(QUOTA_KEY_PREFIX_PLANTNET_DAILY)
            if daily_count == 1:
                # First call today - set expiration to midnight
                ttl = self._seconds_until_midnight()
                self.redis_client.expire(QUOTA_KEY_PREFIX_PLANTNET_DAILY, ttl)
                logger.info(f"[QUOTA] PlantNet daily counter started (expires in {ttl}s)")

            # Log current usage
            logger.info(f"[QUOTA] PlantNet usage: {hourly_count}/{PLANTNET_HOURLY_QUOTA} hourly, "
                       f"{daily_count}/{PLANTNET_DAILY_QUOTA} daily")

            # Warn if approaching hourly quota
            hourly_threshold = PLANTNET_HOURLY_QUOTA * PLANTNET_QUOTA_WARNING_THRESHOLD
            if hourly_count >= hourly_threshold and hourly_count < PLANTNET_HOURLY_QUOTA:
                remaining = PLANTNET_HOURLY_QUOTA - hourly_count
                logger.warning(f"[QUOTA] WARNING: PlantNet approaching hourly quota! "
                             f"{hourly_count}/{PLANTNET_HOURLY_QUOTA} used ({remaining} remaining)")

            # Warn if approaching daily quota
            daily_threshold = PLANTNET_DAILY_QUOTA * PLANTNET_QUOTA_WARNING_THRESHOLD
            if daily_count >= daily_threshold and daily_count < PLANTNET_DAILY_QUOTA:
                remaining = PLANTNET_DAILY_QUOTA - daily_count
                logger.warning(f"[QUOTA] WARNING: PlantNet approaching daily quota! "
                             f"{daily_count}/{PLANTNET_DAILY_QUOTA} used ({remaining} remaining)")

            # Error if quota exceeded
            if hourly_count > PLANTNET_HOURLY_QUOTA:
                logger.error(f"[QUOTA] ERROR: PlantNet hourly quota EXCEEDED! "
                           f"{hourly_count}/{PLANTNET_HOURLY_QUOTA}")

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
            'plant_id': {
                'daily': {
                    'used': self.get_plant_id_daily_usage(),
                    'limit': PLANT_ID_DAILY_QUOTA,
                    'remaining': max(0, PLANT_ID_DAILY_QUOTA - self.get_plant_id_daily_usage()),
                    'available': self.can_call_plant_id(),
                },
                'monthly': {
                    'used': self.get_plant_id_monthly_usage(),
                    'limit': PLANT_ID_MONTHLY_QUOTA,
                    'remaining': max(0, PLANT_ID_MONTHLY_QUOTA - self.get_plant_id_monthly_usage()),
                },
            },
            'plantnet': {
                'hourly': {
                    'used': self.get_plantnet_hourly_usage(),
                    'limit': PLANTNET_HOURLY_QUOTA,
                    'remaining': max(0, PLANTNET_HOURLY_QUOTA - self.get_plantnet_hourly_usage()),
                    'available': self.can_call_plantnet(),
                },
                'daily': {
                    'used': self.get_plantnet_daily_usage(),
                    'limit': PLANTNET_DAILY_QUOTA,
                    'remaining': max(0, PLANTNET_DAILY_QUOTA - self.get_plantnet_daily_usage()),
                },
            },
        }
