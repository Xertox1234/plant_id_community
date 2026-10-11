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
that way when adding a field: no ``TextField`` may be listed
(``test_no_free_text_field_is_audited``).

``include_fields`` limits ``changes`` only. Every LogEntry also stores
``object_repr = str(instance)``, which auditlog does not filter: GardenBed's
carries the owner's username, and the others carry the plant's common name or
the bed's name. Those are labels, not prose, and they live only as long as the
account: deleting a user purges every LogEntry of their garden objects, the
DELETE rows the cascade itself writes included (owner decision 2026-10-11,
todo 586; see ``purge_garden_audit_entries`` below).

``actor`` is NULL on every garden LogEntry: no ``AuditlogMiddleware`` or
``set_actor`` is wired, and middleware could not see a JWT user anyway (DRF
authenticates in the view, after middleware runs). The trail records what
changed and when, not who changed it (todo 586).

Registering a model gives it a ``post_delete`` receiver, so Django can no
longer fast-delete it: deleting a plant, bed or user loads each garden row and
writes one DELETE LogEntry per row. Accepted (todo 586): account and plant
deletes are rare, and the alternative is an audit trail that misses deletes.
"""

from auditlog import get_logentry_model
from auditlog.registry import auditlog
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.db.models.signals import post_delete, pre_delete

from .models import CareLog, CareTask, GardenBed, Harvest, Plant

# Register GardenBed for garden ownership and modification tracking
# Tracks: User garden bed creation, layout changes, soil condition updates
# (what changed and when; actor is not recorded, see the module docstring)
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


# --- Account deletion purges the user's garden LogEntry rows (todo 586) -----

_TARGETS_ATTR = "_garden_audit_targets"


def _garden_objects_of(user):
    """Every garden row deleting ``user`` cascades to, per audited model."""
    return {
        GardenBed: GardenBed.objects.filter(owner=user),
        Plant: Plant.objects.filter(owner=user),
        CareTask: CareTask.objects.filter(Q(plant__owner=user) | Q(created_by=user)),
        CareLog: CareLog.objects.filter(Q(plant__owner=user) | Q(user=user)),
        Harvest: Harvest.objects.filter(plant__owner=user),
    }


def collect_garden_audit_targets(sender, instance, **kwargs):
    """Before a user is deleted, note which garden objects their LogEntry rows
    describe. After the delete the rows are gone and cannot be looked up."""
    targets = []
    for model, queryset in _garden_objects_of(instance).items():
        pks = [str(pk) for pk in queryset.values_list("pk", flat=True)]
        if pks:
            targets.append((ContentType.objects.get_for_model(model).pk, pks))
    setattr(instance, _TARGETS_ATTR, targets)


def purge_garden_audit_entries(sender, instance, **kwargs):
    """Delete every LogEntry of the deleted user's garden objects.

    Runs on the user's ``post_delete``, which Django sends after the cascade
    has deleted (and so audited) every garden row: the DELETE entries the
    cascade wrote are purged with the older CREATE and UPDATE ones. It runs
    inside the delete's transaction, so a rolled-back delete keeps its trail.
    """
    targets = instance.__dict__.pop(_TARGETS_ATTR, None)
    if not targets:
        return
    match = Q()
    for content_type_id, pks in targets:
        match |= Q(content_type_id=content_type_id, object_pk__in=pks)
    get_logentry_model().objects.filter(match).delete()


_User = get_user_model()
pre_delete.connect(
    collect_garden_audit_targets,
    sender=_User,
    dispatch_uid="garden_calendar.collect_garden_audit_targets",
)
post_delete.connect(
    purge_garden_audit_entries,
    sender=_User,
    dispatch_uid="garden_calendar.purge_garden_audit_entries",
)
