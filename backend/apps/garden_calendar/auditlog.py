"""
Audit log registration for garden_calendar app models.

Registers user garden data models for audit trail tracking to comply with:
- GDPR Article 30 (records of processing activities)
- SOC 2 audit trail requirements
- Security monitoring and unauthorized access detection

Imported from ``GardenCalendarConfig.ready()`` (todo 571).

Scope (owner decision, 2026-10-11): all five models are audited, but no
free-text field is. ``notes``, ``materials_used``, ``weather_conditions``,
``description`` and ``skip_reason`` are user prose, and plant/care notes are
health-adjacent data; a LogEntry keeps old and new values indefinitely, so
prose must never land in one. Only structured fields (choices, dates, numbers,
flags, foreign keys and short labels) are listed in ``include_fields``. Keep it
that way when adding a field. Purging LogEntry rows on account deletion is a
separate follow-up.
"""

from auditlog.registry import auditlog

from .models import CareLog, CareTask, GardenBed, Harvest, Plant

# Register GardenBed for garden ownership and modification tracking
# Tracks: User garden bed creation, layout changes, soil condition updates
# Critical for: Answering "Who modified garden bed X?" for GDPR requests
auditlog.register(
    GardenBed,
    include_fields=[
        "name",
        "bed_type",
        "length_inches",
        "width_inches",
        "depth_inches",
        "sun_exposure",
        "soil_type",
        "soil_ph",
        "is_active",
    ],
    exclude_fields=["layout_data"],  # Exclude large JSON blobs for performance
)

# Register Plant for plant lifecycle and health tracking
# Tracks: Plant additions, health status changes, growth stage transitions
auditlog.register(
    Plant,
    include_fields=[
        "owner",  # the access-control field since todo 410
        "garden_bed",
        "common_name",
        "variety",
        "health_status",
        "growth_stage",
        "planted_date",
        "position_x",
        "position_y",
        "is_active",
    ],
)

# Register CareTask for task management and completion tracking
# Tracks: Task creation, scheduling changes, completion/skip status
auditlog.register(
    CareTask,
    include_fields=[
        "task_type",
        "priority",
        "scheduled_date",
        "completed",
        "skipped",
        "completed_at",
        "skipped_at",
        "is_recurring",
        "recurrence_interval_days",
    ],
)

# Register CareLog for user activity and observation tracking
# Tracks: Care activities and plant health transitions (not the prose notes)
auditlog.register(
    CareLog,
    include_fields=[
        "activity_type",
        "plant_health_before",
        "plant_health_after",
        "hours_spent",
        "cost",
    ],
)

# Register Harvest for harvest record tracking
# Tracks: Harvest amounts, quality assessments, timing
auditlog.register(
    Harvest,
    include_fields=[
        "harvest_date",
        "quantity",
        "unit",
        "quality_rating",
    ],
)
