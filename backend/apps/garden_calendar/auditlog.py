"""
Audit log registration for garden_calendar app models.

Registers user garden data models for audit trail tracking to comply with:
- GDPR Article 30 (records of processing activities)
- SOC 2 audit trail requirements
- Security monitoring and unauthorized access detection
"""

from auditlog.registry import auditlog
from .models import (
    GardenBed,
    Plant,
    CareTask,
    CareLog,
    Harvest,
)


# Register GardenBed for garden ownership and modification tracking
# Tracks: User garden bed creation, layout changes, soil condition updates
# Critical for: Answering "Who modified garden bed X?" for GDPR requests
auditlog.register(
    GardenBed,
    include_fields=[
        'name', 'bed_type', 'length_inches', 'width_inches', 'depth_inches',
        'sun_exposure', 'soil_type', 'soil_ph', 'notes', 'is_active',
        'last_fertilized', 'last_watered'
    ],
    exclude_fields=['layout_data'],  # Exclude large JSON blobs for performance
)

# Register Plant for plant lifecycle and health tracking
# Tracks: Plant additions, health status changes, growth stage transitions
auditlog.register(
    Plant,
    include_fields=[
        'common_name', 'variety', 'health_status', 'growth_stage',
        'planted_date', 'expected_harvest_date', 'position_x', 'position_y',
        'notes', 'is_active'
    ],
)

# Register CareTask for task management and completion tracking
# Tracks: Task creation, scheduling changes, completion/skip status
auditlog.register(
    CareTask,
    include_fields=[
        'task_type', 'priority', 'scheduled_date', 'completed', 'skipped',
        'completed_at', 'notes', 'is_recurring', 'recurrence_interval_days'
    ],
)

# Register CareLog for user activity and observation tracking
# Tracks: User observations, care activities, plant health notes
auditlog.register(
    CareLog,
    include_fields=[
        'activity_type', 'notes', 'plant_health_before', 'plant_health_after',
        'hours_spent', 'materials_used', 'cost', 'weather_conditions'
    ],
)

# Register Harvest for harvest record tracking
# Tracks: Harvest amounts, quality assessments, timing
auditlog.register(
    Harvest,
    include_fields=[
        'harvest_date', 'quantity', 'unit', 'quality_rating',
        'taste_rating', 'notes', 'shared_with_community'
    ],
)
