"""
Smart Reminder Service

Weather-aware care reminder management.

Provides:
- Automatic reminder skipping based on weather
- Reminder adjustment recommendations
- Integration with WeatherService
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from ..models import CareReminder, Garden
from .weather_service import WeatherService

logger = logging.getLogger(__name__)


class SmartReminderService:
    """
    Intelligent reminder management with weather awareness.

    Automatically adjusts care reminders based on:
    - Current weather conditions
    - Weather forecast
    - Plant-specific needs
    """

    @classmethod
    def check_reminder_with_weather(
        cls,
        reminder: CareReminder
    ) -> Dict[str, Any]:
        """
        Check if reminder should be adjusted based on weather.

        Args:
            reminder: CareReminder instance

        Returns:
            Dict with:
            - should_skip: bool
            - skip_reason: str or None
            - recommendations: list of strings
            - weather_data: dict or None
        """
        # Get garden location
        garden = reminder.garden_plant.garden
        if not garden.location or 'lat' not in garden.location or 'lng' not in garden.location:
            logger.info(f"[REMINDER] No location for garden {garden.id}, skipping weather check")
            return {
                'should_skip': False,
                'skip_reason': None,
                'recommendations': [],
                'weather_data': None
            }

        lat = garden.location['lat']
        lng = garden.location['lng']

        # Get weather recommendations
        weather_recs = WeatherService.get_care_recommendations(lat, lng)

        # Check if watering reminder should be skipped
        should_skip = False
        skip_reason = None

        if reminder.reminder_type == 'watering' and weather_recs['skip_watering']:
            should_skip = True
            skip_reason = "Heavy rain forecasted or recently occurred"
            logger.info(f"[REMINDER] Skipping watering reminder {reminder.id} due to rain")

        # Check for frost warnings (affects all outdoor plants)
        recommendations = weather_recs['recommendations'].copy()
        if weather_recs['frost_warning'] and weather_recs['frost_warning']['has_frost']:
            if reminder.reminder_type in ['watering', 'fertilizing']:
                recommendations.insert(0, "Delay this task until after frost passes")

        # Check for heatwave warnings
        if weather_recs['heat_warning'] and weather_recs['heat_warning']['has_heatwave']:
            if reminder.reminder_type == 'watering':
                recommendations.insert(0, "Consider watering in early morning or evening to avoid water stress")

        return {
            'should_skip': should_skip,
            'skip_reason': skip_reason,
            'recommendations': recommendations,
            'weather_data': {
                'frost_warning': weather_recs['frost_warning'],
                'heat_warning': weather_recs['heat_warning']
            }
        }

    @classmethod
    def auto_skip_reminders(cls) -> Dict[str, int]:
        """
        Automatically skip reminders that should be delayed due to weather.

        Runs as background task (cron job or celery beat).

        Returns:
            Dict with:
            - skipped_count: int (number of reminders skipped)
            - affected_users: set of user IDs
        """
        from datetime import date

        # Get today's incomplete watering reminders
        today = datetime.now().date()
        reminders = CareReminder.objects.filter(
            scheduled_date__date=today,
            completed=False,
            skipped=False,
            reminder_type='watering'
        ).select_related('garden_plant__garden')

        skipped_count = 0
        affected_users = set()

        for reminder in reminders:
            check_result = cls.check_reminder_with_weather(reminder)

            if check_result['should_skip']:
                # Skip the reminder
                reminder.skipped = True
                reminder.skip_reason = check_result['skip_reason']
                reminder.save()

                skipped_count += 1
                affected_users.add(reminder.user_id)

                logger.info(
                    f"[REMINDER] Auto-skipped reminder {reminder.id} "
                    f"for user {reminder.user_id}: {check_result['skip_reason']}"
                )

                # If recurring, create next instance
                if reminder.recurring and reminder.interval_days:
                    next_date = reminder.scheduled_date + timedelta(days=reminder.interval_days)
                    CareReminder.objects.create(
                        user=reminder.user,
                        garden_plant=reminder.garden_plant,
                        reminder_type=reminder.reminder_type,
                        custom_type_name=reminder.custom_type_name,
                        scheduled_date=next_date,
                        recurring=True,
                        interval_days=reminder.interval_days,
                        notes=reminder.notes
                    )
                    logger.info(f"[REMINDER] Created next instance for {next_date}")

        logger.info(
            f"[REMINDER] Auto-skipped {skipped_count} reminders "
            f"for {len(affected_users)} users"
        )

        return {
            'skipped_count': skipped_count,
            'affected_users': affected_users
        }

    @classmethod
    def get_upcoming_reminders_with_weather(
        cls,
        user,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming reminders with weather-based recommendations.

        Args:
            user: User instance
            days: Number of days ahead to check

        Returns:
            List of dicts with:
            - reminder: CareReminder instance
            - should_skip: bool
            - skip_reason: str or None
            - recommendations: list of strings
            - weather_data: dict or None
        """
        end_date = datetime.now() + timedelta(days=days)

        reminders = CareReminder.objects.filter(
            user=user,
            completed=False,
            scheduled_date__lte=end_date
        ).select_related(
            'garden_plant__garden'
        ).order_by('scheduled_date')

        results = []
        for reminder in reminders:
            check_result = cls.check_reminder_with_weather(reminder)
            results.append({
                'reminder': reminder,
                **check_result
            })

        return results

    @classmethod
    def adjust_watering_frequency(
        cls,
        garden: Garden,
        plant_water_needs: str = 'medium'
    ) -> int:
        """
        Suggest watering frequency based on local weather patterns.

        Args:
            garden: Garden instance with location
            plant_water_needs: 'low', 'medium', or 'high'

        Returns:
            Suggested watering interval in days
        """
        if not garden.location or 'lat' not in garden.location:
            # No location - use defaults
            from ..constants import WATER_NEED_FREQUENCY
            return WATER_NEED_FREQUENCY.get(plant_water_needs, 3)

        lat = garden.location['lat']
        lng = garden.location['lng']

        # Get forecast for next 5 days
        forecast = WeatherService.get_forecast(lat, lng, days=5)
        if not forecast:
            # Weather unavailable - use defaults
            from ..constants import WATER_NEED_FREQUENCY
            return WATER_NEED_FREQUENCY.get(plant_water_needs, 3)

        # Calculate average daily precipitation
        total_precip = sum(day['precipitation_amount'] for day in forecast)
        avg_precip = total_precip / len(forecast)

        # Calculate average temperature
        avg_temp = sum((day['temp_max'] + day['temp_min']) / 2 for day in forecast) / len(forecast)

        # Base intervals by plant needs
        base_intervals = {
            'low': 7,     # Drought-tolerant
            'medium': 3,  # Average
            'high': 1     # Water-loving
        }

        base_interval = base_intervals.get(plant_water_needs, 3)

        # Adjust based on precipitation
        if avg_precip > 0.3:  # Heavy rain expected
            adjustment = 1.5  # Water less frequently
        elif avg_precip > 0.1:  # Moderate rain
            adjustment = 1.2
        else:  # Dry weather
            adjustment = 1.0

        # Adjust based on temperature
        if avg_temp > 90:  # Hot weather
            adjustment *= 0.8  # Water more frequently
        elif avg_temp > 75:  # Warm weather
            adjustment *= 0.9
        elif avg_temp < 50:  # Cool weather
            adjustment *= 1.2  # Water less frequently

        # Calculate suggested interval
        suggested_interval = int(base_interval * adjustment)

        # Bounds checking
        suggested_interval = max(1, min(14, suggested_interval))

        logger.info(
            f"[REMINDER] Suggested watering interval: {suggested_interval} days "
            f"(base: {base_interval}, avg_precip: {avg_precip:.2f}, avg_temp: {avg_temp:.1f})"
        )

        return suggested_interval
