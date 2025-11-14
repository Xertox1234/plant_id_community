"""
Care Schedule Service

Automatically generates care tasks based on plant species, seasonal templates,
and growing zone data.

This service handles:
- Auto-generating care tasks for new plants
- Creating seasonal care schedules
- Scheduling recurring tasks (watering, fertilizing, etc.)
- Zone-specific task timing based on frost dates
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from django.db.models import QuerySet
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..models import Plant, CareTask, SeasonalTemplate, GrowingZone
from ..constants import CARE_TASK_TYPES, CARE_TASK_PRIORITY

User = get_user_model()
logger = logging.getLogger(__name__)


class CareScheduleService:
    """
    Service for auto-generating care task schedules.

    All methods are static to avoid state management.
    Handles intelligent task creation based on plant characteristics.
    """

    # Default care intervals in days
    DEFAULT_INTERVALS = {
        'watering': {
            'seedling': 1,      # Daily for seedlings
            'vegetative': 2,    # Every 2 days for vegetative growth
            'flowering': 2,     # Every 2 days during flowering
            'fruiting': 1,      # Daily during fruiting
            'dormant': 7,       # Weekly when dormant
        },
        'fertilizing': {
            'seedling': 14,     # Bi-weekly for seedlings
            'vegetative': 14,   # Bi-weekly during growth
            'flowering': 7,     # Weekly during flowering
            'fruiting': 7,      # Weekly during fruiting
            'dormant': 0,       # No fertilizing when dormant
        },
        'pruning': {
            'seedling': 0,      # No pruning for seedlings
            'vegetative': 30,   # Monthly during growth
            'flowering': 0,     # No pruning during flowering
            'fruiting': 21,     # Every 3 weeks during fruiting
            'dormant': 60,      # Bi-monthly when dormant
        },
        'pest_check': {
            'default': 7,       # Weekly pest checks for all stages
        },
        'harvesting': {
            'fruiting': 3,      # Check every 3 days when fruiting
        }
    }

    @staticmethod
    def generate_initial_tasks_for_plant(plant: Plant) -> List[CareTask]:
        """
        Generate initial set of care tasks when a plant is created.

        Creates tasks for:
        - Watering (recurring based on growth stage)
        - Fertilizing (recurring based on growth stage)
        - Pest checking (weekly recurring)
        - Pruning (if applicable based on growth stage)

        Args:
            plant: Plant instance

        Returns:
            List of created CareTask objects
        """
        logger.info(f"[CARE_SCHEDULE] Generating initial tasks for plant {plant.uuid}")

        created_tasks = []
        growth_stage = plant.growth_stage
        now = timezone.now()

        # 1. Watering task (highest priority, recurring)
        watering_interval = CareScheduleService.DEFAULT_INTERVALS['watering'].get(
            growth_stage, 2
        )
        if watering_interval > 0:
            task = CareTask.objects.create(
                plant=plant,
                task_type='watering',
                priority='high',
                scheduled_date=now + timedelta(days=1),  # Start tomorrow
                is_recurring=True,
                recurrence_interval_days=watering_interval,
                notes=f"Auto-generated watering schedule for {growth_stage} stage"
            )
            created_tasks.append(task)
            logger.info(f"[CARE_SCHEDULE] Created watering task (every {watering_interval} days)")

        # 2. Fertilizing task (recurring based on growth stage)
        fertilizing_interval = CareScheduleService.DEFAULT_INTERVALS['fertilizing'].get(
            growth_stage, 14
        )
        if fertilizing_interval > 0:
            task = CareTask.objects.create(
                plant=plant,
                task_type='fertilizing',
                priority='medium',
                scheduled_date=now + timedelta(days=7),  # Start in a week
                is_recurring=True,
                recurrence_interval_days=fertilizing_interval,
                notes=f"Auto-generated fertilizing schedule for {growth_stage} stage"
            )
            created_tasks.append(task)
            logger.info(f"[CARE_SCHEDULE] Created fertilizing task (every {fertilizing_interval} days)")

        # 3. Pest check task (weekly recurring)
        pest_check_interval = CareScheduleService.DEFAULT_INTERVALS['pest_check']['default']
        task = CareTask.objects.create(
            plant=plant,
            task_type='pest_check',
            priority='medium',
            scheduled_date=now + timedelta(days=3),  # Start in 3 days
            is_recurring=True,
            recurrence_interval_days=pest_check_interval,
            notes="Auto-generated weekly pest inspection"
        )
        created_tasks.append(task)
        logger.info(f"[CARE_SCHEDULE] Created pest check task (weekly)")

        # 4. Pruning task (if applicable)
        pruning_interval = CareScheduleService.DEFAULT_INTERVALS['pruning'].get(
            growth_stage, 0
        )
        if pruning_interval > 0:
            task = CareTask.objects.create(
                plant=plant,
                task_type='pruning',
                priority='low',
                scheduled_date=now + timedelta(days=14),  # Start in 2 weeks
                is_recurring=True,
                recurrence_interval_days=pruning_interval,
                notes=f"Auto-generated pruning schedule for {growth_stage} stage"
            )
            created_tasks.append(task)
            logger.info(f"[CARE_SCHEDULE] Created pruning task (every {pruning_interval} days)")

        # 5. Harvesting reminder (if in fruiting stage)
        if growth_stage == 'fruiting':
            harvesting_interval = CareScheduleService.DEFAULT_INTERVALS['harvesting']['fruiting']
            task = CareTask.objects.create(
                plant=plant,
                task_type='harvesting',
                priority='high',
                scheduled_date=now + timedelta(days=7),  # Start in a week
                is_recurring=True,
                recurrence_interval_days=harvesting_interval,
                notes="Auto-generated harvest check reminder"
            )
            created_tasks.append(task)
            logger.info(f"[CARE_SCHEDULE] Created harvesting task (every {harvesting_interval} days)")

        logger.info(f"[CARE_SCHEDULE] Created {len(created_tasks)} initial tasks for plant {plant.uuid}")
        return created_tasks

    @staticmethod
    def update_tasks_for_growth_stage_change(plant: Plant, old_stage: str, new_stage: str) -> Dict[str, Any]:
        """
        Update care task schedules when a plant's growth stage changes.

        Adjusts recurrence intervals for existing tasks based on new stage.
        Creates new tasks if needed (e.g., harvesting when entering fruiting).

        Args:
            plant: Plant instance
            old_stage: Previous growth stage
            new_stage: New growth stage

        Returns:
            Dictionary with update statistics
        """
        logger.info(f"[CARE_SCHEDULE] Updating tasks for plant {plant.uuid}: {old_stage} → {new_stage}")

        updates = {
            'watering_updated': False,
            'fertilizing_updated': False,
            'pruning_updated': False,
            'harvesting_created': False,
            'tasks_adjusted': []
        }

        # Get active recurring tasks
        recurring_tasks = CareTask.objects.filter(
            plant=plant,
            is_recurring=True,
            completed=False,
            skipped=False
        )

        # Update watering interval
        watering_task = recurring_tasks.filter(task_type='watering').first()
        if watering_task:
            new_interval = CareScheduleService.DEFAULT_INTERVALS['watering'].get(new_stage, 2)
            if watering_task.recurrence_interval_days != new_interval:
                watering_task.recurrence_interval_days = new_interval
                watering_task.notes = f"Adjusted for {new_stage} stage (was {old_stage})"
                watering_task.save()
                updates['watering_updated'] = True
                updates['tasks_adjusted'].append('watering')
                logger.info(f"[CARE_SCHEDULE] Updated watering interval to {new_interval} days")

        # Update fertilizing interval
        fertilizing_task = recurring_tasks.filter(task_type='fertilizing').first()
        if fertilizing_task:
            new_interval = CareScheduleService.DEFAULT_INTERVALS['fertilizing'].get(new_stage, 14)
            if new_interval == 0:
                # Dormant stage - pause fertilizing
                fertilizing_task.is_recurring = False
                fertilizing_task.notes = "Paused during dormant stage"
                fertilizing_task.save()
                updates['fertilizing_updated'] = True
                updates['tasks_adjusted'].append('fertilizing')
                logger.info(f"[CARE_SCHEDULE] Paused fertilizing for dormant stage")
            elif fertilizing_task.recurrence_interval_days != new_interval:
                fertilizing_task.recurrence_interval_days = new_interval
                fertilizing_task.notes = f"Adjusted for {new_stage} stage (was {old_stage})"
                fertilizing_task.save()
                updates['fertilizing_updated'] = True
                updates['tasks_adjusted'].append('fertilizing')
                logger.info(f"[CARE_SCHEDULE] Updated fertilizing interval to {new_interval} days")

        # Update pruning interval
        pruning_task = recurring_tasks.filter(task_type='pruning').first()
        if pruning_task:
            new_interval = CareScheduleService.DEFAULT_INTERVALS['pruning'].get(new_stage, 0)
            if new_interval == 0:
                # No pruning needed - pause task
                pruning_task.is_recurring = False
                pruning_task.notes = f"Not needed during {new_stage} stage"
                pruning_task.save()
                updates['pruning_updated'] = True
                updates['tasks_adjusted'].append('pruning')
                logger.info(f"[CARE_SCHEDULE] Paused pruning for {new_stage} stage")
            elif pruning_task.recurrence_interval_days != new_interval:
                pruning_task.recurrence_interval_days = new_interval
                pruning_task.notes = f"Adjusted for {new_stage} stage (was {old_stage})"
                pruning_task.save()
                updates['pruning_updated'] = True
                updates['tasks_adjusted'].append('pruning')
                logger.info(f"[CARE_SCHEDULE] Updated pruning interval to {new_interval} days")

        # Create harvesting task if entering fruiting stage
        if new_stage == 'fruiting' and old_stage != 'fruiting':
            harvesting_task = recurring_tasks.filter(task_type='harvesting').first()
            if not harvesting_task:
                harvesting_interval = CareScheduleService.DEFAULT_INTERVALS['harvesting']['fruiting']
                CareTask.objects.create(
                    plant=plant,
                    task_type='harvesting',
                    priority='high',
                    scheduled_date=timezone.now() + timedelta(days=3),
                    is_recurring=True,
                    recurrence_interval_days=harvesting_interval,
                    notes="Auto-generated harvest check (plant entered fruiting stage)"
                )
                updates['harvesting_created'] = True
                updates['tasks_adjusted'].append('harvesting')
                logger.info(f"[CARE_SCHEDULE] Created harvesting task for fruiting stage")

        logger.info(f"[CARE_SCHEDULE] Updated {len(updates['tasks_adjusted'])} task types")
        return updates

    @staticmethod
    def generate_seasonal_tasks(user: User, season: str) -> List[CareTask]:
        """
        Generate seasonal care tasks based on templates and user's growing zone.

        Args:
            user: User object
            season: Season name ('spring', 'summer', 'fall', 'winter')

        Returns:
            List of created CareTask objects
        """
        logger.info(f"[CARE_SCHEDULE] Generating seasonal tasks for user {user.id}, season: {season}")

        created_tasks = []

        # Get user's hardiness zone
        user_zone = getattr(user, 'hardiness_zone', None)
        if not user_zone:
            logger.warning(f"[CARE_SCHEDULE] User {user.id} has no hardiness zone set")
            return created_tasks

        # Get seasonal templates for user's zone
        templates = SeasonalTemplate.objects.filter(
            season=season,
            is_active=True
        ).filter(
            hardiness_zones__contains=[user_zone]
        )

        if not templates.exists():
            logger.info(f"[CARE_SCHEDULE] No seasonal templates found for {season} in zone {user_zone}")
            return created_tasks

        # Get user's plants
        from ..models import Plant
        plants = Plant.objects.filter(
            garden_bed__owner=user,
            is_active=True
        )

        # Create tasks from templates
        for template in templates:
            # Match plants by type if specified
            if template.plant_types:
                matching_plants = plants.filter(
                    plant_species__scientific_name__in=template.plant_types
                )
            else:
                # Universal template - apply to all plants
                matching_plants = plants

            for plant in matching_plants:
                # Calculate scheduled date based on template
                scheduled_date = CareScheduleService._calculate_seasonal_task_date(
                    template, user_zone
                )

                if scheduled_date:
                    task = CareTask.objects.create(
                        plant=plant,
                        task_type=template.task_type,
                        priority=template.priority,
                        scheduled_date=scheduled_date,
                        is_recurring=template.frequency_days is not None,
                        recurrence_interval_days=template.frequency_days,
                        notes=f"Seasonal task from template: {template.name}\n{template.instructions}"
                    )
                    created_tasks.append(task)

        logger.info(f"[CARE_SCHEDULE] Created {len(created_tasks)} seasonal tasks")
        return created_tasks

    @staticmethod
    def _calculate_seasonal_task_date(template: SeasonalTemplate, zone: str) -> Optional[datetime]:
        """
        Calculate the scheduled date for a seasonal task.

        Uses template's month/day and adjusts based on zone's frost dates.

        Args:
            template: SeasonalTemplate instance
            zone: Hardiness zone code

        Returns:
            Datetime for task scheduling, or None if cannot be calculated
        """
        now = timezone.now()
        current_year = now.year

        # Start with template's start month
        if not template.start_month:
            return None

        # Create datetime for template date
        target_month = template.start_month
        target_day = template.day_of_month or 1

        try:
            target_date = datetime(current_year, target_month, target_day, 12, 0)
            target_date = timezone.make_aware(target_date)

            # If date has passed this year, schedule for next year
            if target_date < now:
                target_date = target_date.replace(year=current_year + 1)

            # Adjust based on frost dates if template requires no frost
            if template.requires_no_frost:
                zone_data = GrowingZone.objects.filter(zone_code=zone).first()
                if zone_data and zone_data.last_frost_date:
                    # Parse frost date (format: "MM-DD")
                    try:
                        frost_month, frost_day = map(int, zone_data.last_frost_date.split('-'))
                        frost_date = datetime(current_year, frost_month, frost_day, 12, 0)
                        frost_date = timezone.make_aware(frost_date)

                        # If target is before last frost, push to 2 weeks after frost
                        if target_date < frost_date:
                            target_date = frost_date + timedelta(days=14)
                    except (ValueError, AttributeError):
                        logger.warning(f"[CARE_SCHEDULE] Could not parse frost date: {zone_data.last_frost_date}")

            return target_date

        except ValueError as e:
            logger.error(f"[CARE_SCHEDULE] Invalid date in template: {e}")
            return None

    @staticmethod
    def reschedule_overdue_tasks(user: User, days_overdue: int = 7) -> int:
        """
        Reschedule overdue tasks to today or tomorrow.

        Helps users catch up when tasks have been neglected.

        Args:
            user: User object
            days_overdue: Only reschedule tasks this many days overdue (default: 7)

        Returns:
            Count of tasks rescheduled
        """
        logger.info(f"[CARE_SCHEDULE] Rescheduling overdue tasks for user {user.id}")

        cutoff_date = timezone.now() - timedelta(days=days_overdue)

        overdue_tasks = CareTask.objects.filter(
            plant__garden_bed__owner=user,
            completed=False,
            skipped=False,
            scheduled_date__lt=cutoff_date
        )

        count = overdue_tasks.count()
        if count == 0:
            return 0

        # Reschedule to tomorrow
        tomorrow = timezone.now() + timedelta(days=1)
        overdue_tasks.update(
            scheduled_date=tomorrow,
            notes=f"Rescheduled from overdue status"
        )

        logger.info(f"[CARE_SCHEDULE] Rescheduled {count} overdue tasks")
        return count
