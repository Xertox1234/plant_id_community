"""
Garden Analytics Service

Provides analytics and statistics for garden beds, plants, and care activities.

This service handles:
- Bed utilization calculations
- Plant health statistics
- Care task completion rates
- Harvest yield tracking
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from django.db.models import Count, Q, Avg, Sum, F
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

from ..models import GardenBed, Plant, CareTask, CareLog, Harvest
from ..constants import (
    CACHE_KEY_GARDEN_ANALYTICS,
    CACHE_TIMEOUT_ANALYTICS,
    HEALTH_STATUS_CHOICES,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class GardenAnalyticsService:
    """
    Service for calculating garden analytics and statistics.

    All methods are static to avoid state management.
    Uses caching for expensive calculations.
    """

    @staticmethod
    def get_bed_utilization_stats(user: User) -> Dict[str, Any]:
        """
        Calculate bed utilization statistics for a user's garden beds.

        Args:
            user: User object

        Returns:
            Dictionary with utilization statistics:
            - total_beds: Total number of garden beds
            - average_utilization: Average utilization across all beds
            - underutilized_beds: Beds with <50% utilization
            - well_utilized_beds: Beds with 50-85% utilization
            - overutilized_beds: Beds with >85% utilization
        """
        cache_key = CACHE_KEY_GARDEN_ANALYTICS.format(
            metric='bed_utilization',
            user_id=user.id
        )

        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"[CACHE] HIT for bed utilization stats user {user.id}")
            return cached_data

        logger.info(f"[ANALYTICS] Calculating bed utilization for user {user.id}")

        # Get all active garden beds
        beds = GardenBed.objects.filter(
            owner=user,
            is_active=True
        ).annotate(
            plant_count=Count('plants', filter=Q(plants__is_active=True))
        )

        if not beds.exists():
            return {
                'total_beds': 0,
                'average_utilization': 0.0,
                'underutilized_beds': [],
                'well_utilized_beds': [],
                'overutilized_beds': []
            }

        # Calculate utilization for each bed
        utilization_data = {
            'underutilized': [],  # < 50%
            'well_utilized': [],  # 50-85%
            'overutilized': []    # > 85%
        }
        total_utilization = 0.0
        bed_count = 0

        for bed in beds:
            util_rate = bed.utilization_rate
            if util_rate is not None:
                total_utilization += util_rate
                bed_count += 1

                bed_info = {
                    'uuid': str(bed.uuid),
                    'name': bed.name,
                    'utilization': round(util_rate * 100, 1),
                    'plant_count': bed.plant_count,
                    'area_sq_ft': bed.area_square_feet
                }

                if util_rate < 0.5:
                    utilization_data['underutilized'].append(bed_info)
                elif util_rate < 0.85:
                    utilization_data['well_utilized'].append(bed_info)
                else:
                    utilization_data['overutilized'].append(bed_info)

        result = {
            'total_beds': beds.count(),
            'average_utilization': round((total_utilization / bed_count * 100), 1) if bed_count > 0 else 0.0,
            'underutilized_beds': utilization_data['underutilized'],
            'well_utilized_beds': utilization_data['well_utilized'],
            'overutilized_beds': utilization_data['overutilized']
        }

        # Cache for 1 hour
        cache.set(cache_key, result, CACHE_TIMEOUT_ANALYTICS)
        logger.info(f"[CACHE] SET bed utilization stats for user {user.id}")

        return result

    @staticmethod
    def get_plant_health_stats(user: User) -> Dict[str, Any]:
        """
        Calculate plant health statistics for a user.

        Args:
            user: User object

        Returns:
            Dictionary with health statistics:
            - total_plants: Total number of plants
            - health_breakdown: Count by health status
            - health_percentage: Percentage by health status
            - needs_attention: Plants in poor health
        """
        cache_key = CACHE_KEY_GARDEN_ANALYTICS.format(
            metric='plant_health',
            user_id=user.id
        )

        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"[CACHE] HIT for plant health stats user {user.id}")
            return cached_data

        logger.info(f"[ANALYTICS] Calculating plant health for user {user.id}")

        # Get all active plants
        plants = Plant.objects.filter(
            garden_bed__owner=user,
            is_active=True
        )

        total_plants = plants.count()

        if total_plants == 0:
            return {
                'total_plants': 0,
                'health_breakdown': {},
                'health_percentage': {},
                'needs_attention': []
            }

        # Count by health status
        health_counts = plants.values('health_status').annotate(
            count=Count('uuid')
        )

        health_breakdown = {
            item['health_status']: item['count']
            for item in health_counts
        }

        health_percentage = {
            status: round((count / total_plants * 100), 1)
            for status, count in health_breakdown.items()
        }

        # Get plants that need attention (struggling, diseased, dying, dead)
        needs_attention_statuses = ['struggling', 'diseased', 'dying', 'dead']
        needs_attention = plants.filter(
            health_status__in=needs_attention_statuses
        ).select_related('garden_bed').values(
            'uuid', 'common_name', 'health_status', 'garden_bed__name'
        )

        result = {
            'total_plants': total_plants,
            'health_breakdown': health_breakdown,
            'health_percentage': health_percentage,
            'needs_attention': list(needs_attention)
        }

        # Cache for 1 hour
        cache.set(cache_key, result, CACHE_TIMEOUT_ANALYTICS)
        logger.info(f"[CACHE] SET plant health stats for user {user.id}")

        return result

    @staticmethod
    def get_care_task_stats(user: User, days: int = 30) -> Dict[str, Any]:
        """
        Calculate care task statistics for a user.

        Args:
            user: User object
            days: Number of days to look back (default: 30)

        Returns:
            Dictionary with task statistics:
            - total_tasks: Total tasks in period
            - completed_tasks: Completed tasks count
            - skipped_tasks: Skipped tasks count
            - overdue_tasks: Overdue tasks count
            - completion_rate: Percentage completed
            - upcoming_week: Tasks due in next 7 days
        """
        logger.info(f"[ANALYTICS] Calculating care task stats for user {user.id}")

        start_date = timezone.now() - timedelta(days=days)

        # Get tasks in the time period
        tasks = CareTask.objects.filter(
            plant__garden_bed__owner=user,
            scheduled_date__gte=start_date
        )

        total_tasks = tasks.count()
        completed_tasks = tasks.filter(completed=True).count()
        skipped_tasks = tasks.filter(skipped=True).count()

        # Overdue tasks (not completed, not skipped, past due date)
        overdue_tasks = tasks.filter(
            completed=False,
            skipped=False,
            scheduled_date__lt=timezone.now()
        ).count()

        # Upcoming tasks (next 7 days)
        next_week = timezone.now() + timedelta(days=7)
        upcoming_tasks = tasks.filter(
            completed=False,
            skipped=False,
            scheduled_date__gte=timezone.now(),
            scheduled_date__lte=next_week
        ).select_related('plant').values(
            'uuid', 'task_type', 'scheduled_date', 'priority', 'plant__common_name'
        ).order_by('scheduled_date')

        completion_rate = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0.0

        return {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'skipped_tasks': skipped_tasks,
            'overdue_tasks': overdue_tasks,
            'completion_rate': completion_rate,
            'upcoming_week': list(upcoming_tasks)
        }

    @staticmethod
    def get_harvest_summary(user: User, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Calculate harvest summary for a user.

        Args:
            user: User object
            year: Optional year to filter (default: current year)

        Returns:
            Dictionary with harvest summary:
            - total_harvests: Total harvest count
            - total_weight_lbs: Total weight in pounds
            - average_quality: Average quality rating
            - average_taste: Average taste rating
            - by_plant: Breakdown by plant
            - by_month: Breakdown by month
        """
        logger.info(f"[ANALYTICS] Calculating harvest summary for user {user.id}")

        if year is None:
            year = timezone.now().year

        # Get harvests for the year
        harvests = Harvest.objects.filter(
            plant__garden_bed__owner=user,
            harvest_date__year=year
        )

        total_harvests = harvests.count()

        if total_harvests == 0:
            return {
                'total_harvests': 0,
                'total_weight_lbs': 0.0,
                'average_quality': None,
                'average_taste': None,
                'by_plant': [],
                'by_month': []
            }

        # Total weight in lbs (convert oz to lbs)
        total_lbs = harvests.filter(unit='lbs').aggregate(total=Sum('quantity'))['total'] or 0
        total_oz = harvests.filter(unit='oz').aggregate(total=Sum('quantity'))['total'] or 0
        total_weight_lbs = total_lbs + (total_oz / 16)

        # Average ratings
        avg_quality = harvests.aggregate(avg=Avg('quality_rating'))['avg']
        avg_taste = harvests.aggregate(avg=Avg('taste_rating'))['avg']

        # By plant
        by_plant = harvests.values(
            'plant__uuid', 'plant__common_name'
        ).annotate(
            harvest_count=Count('uuid'),
            total_quantity=Sum('quantity')
        ).order_by('-harvest_count')[:10]

        # By month
        by_month = harvests.extra(
            select={'month': 'EXTRACT(month FROM harvest_date)'}
        ).values('month').annotate(
            harvest_count=Count('uuid')
        ).order_by('month')

        return {
            'total_harvests': total_harvests,
            'total_weight_lbs': round(total_weight_lbs, 2),
            'average_quality': round(avg_quality, 1) if avg_quality else None,
            'average_taste': round(avg_taste, 1) if avg_taste else None,
            'by_plant': list(by_plant),
            'by_month': list(by_month)
        }

    @staticmethod
    def get_comprehensive_dashboard(user: User) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data for a user.

        Combines multiple analytics into a single response.

        Args:
            user: User object

        Returns:
            Dictionary with all analytics sections
        """
        logger.info(f"[ANALYTICS] Building comprehensive dashboard for user {user.id}")

        return {
            'bed_utilization': GardenAnalyticsService.get_bed_utilization_stats(user),
            'plant_health': GardenAnalyticsService.get_plant_health_stats(user),
            'care_tasks': GardenAnalyticsService.get_care_task_stats(user),
            'harvest_summary': GardenAnalyticsService.get_harvest_summary(user)
        }

    @staticmethod
    def invalidate_user_cache(user: User) -> None:
        """
        Invalidate all analytics cache for a user.

        Call this when user makes changes to their garden data.

        Args:
            user: User object
        """
        cache_keys = [
            CACHE_KEY_GARDEN_ANALYTICS.format(metric='bed_utilization', user_id=user.id),
            CACHE_KEY_GARDEN_ANALYTICS.format(metric='plant_health', user_id=user.id),
        ]

        for key in cache_keys:
            cache.delete(key)

        logger.info(f"[CACHE] INVALIDATED analytics cache for user {user.id}")
