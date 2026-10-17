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
the bed's name. Those are labels, not prose. Deleting a user purges a garden
LogEntry when either (see ``purge_garden_audit_entries`` below):

- it describes a garden object the user still has when the account goes,
  the DELETE rows the cascade itself writes included (owner decision
  2026-10-11, todo 586); or
- the user is its ``actor``, which also covers objects the user deleted
  before the account (owner decision 2026-10-11, todo 606).

What neither matches survives the account: a row written with no actor (by a
Celery task, the CMS admin, or a garden view before todo 606 wired the actor)
for an object the user had already deleted. The actor match covers rows
written from todo 606 on, not older ones.

``actor`` is set by the garden API views (``api/audit_actor.py``), which set
it once DRF has authenticated the request, through a receiver connected below
rather than auditlog's ``set_actor`` (todo 631, see that module).
``AuditlogMiddleware`` could not do it: it runs before DRF authenticates the
JWT. Rows written outside those views (Celery tasks, the CMS admin) have a NULL
actor. auditlog also stores the actor's email in ``actor_email``; the actor
match purges those rows with the account.

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

from .api.audit_actor import connect_actor_receiver
from .models import CareLog, CareTask, GardenBed, Harvest, Plant

connect_actor_receiver()

# Register GardenBed for garden ownership and modification tracking
# Tracks: User garden bed creation, layout changes, soil condition updates
# (what changed, when, and by whom from the garden API; see the module docstring)
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

# The purge deletes at most this many LogEntry rows per statement (todo 631):
# a heavy user's rows are never one huge IN clause, and their pks are never
# all held in memory at once.
PURGE_CHUNK_SIZE = 500


def _delete_in_chunks(queryset):
    """Delete ``queryset``'s LogEntry rows, ``PURGE_CHUNK_SIZE`` at a time."""
    model = get_logentry_model()
    # Unordered (todo 643 #4): LogEntry's default ``-timestamp`` ordering
    # would re-sort every remaining matching row for each chunk. Any chunk
    # will do, since every row of the queryset goes.
    queryset = queryset.order_by()
    while True:
        pks = list(queryset.values_list("pk", flat=True)[:PURGE_CHUNK_SIZE])
        if not pks:
            return
        model.objects.filter(pk__in=pks).delete()


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
    describe, and purge the garden LogEntry rows that name them as actor.
    After the delete the garden rows are gone and the actor is NULL
    (``on_delete=SET_NULL``), so neither can be looked up then.

    The actor rows go now, in chunks (todo 631), rather than as one pk list
    carried to ``post_delete``. Django sends ``pre_delete`` inside the
    delete's transaction, so a rolled-back delete keeps them."""
    targets = []
    content_type_ids = []
    for model, queryset in _garden_objects_of(instance).items():
        content_type_id = ContentType.objects.get_for_model(model).pk
        content_type_ids.append(content_type_id)
        pks = [str(pk) for pk in queryset.values_list("pk", flat=True)]
        if pks:
            targets.append((content_type_id, pks))
    _delete_in_chunks(
        get_logentry_model().objects.filter(
            actor=instance, content_type_id__in=content_type_ids
        )
    )
    setattr(instance, _TARGETS_ATTR, targets)


def purge_garden_audit_entries(sender, instance, **kwargs):
    """Delete every LogEntry of the deleted user's garden objects (the rows
    they are the actor of went in ``collect_garden_audit_targets``, todo 606).

    Runs on the user's ``post_delete``, which Django sends after the cascade
    has deleted (and so audited) every garden row: the DELETE entries the
    cascade wrote are purged with the older CREATE and UPDATE ones. It runs
    inside the delete's transaction, so a rolled-back delete keeps its trail.
    Each statement names at most ``PURGE_CHUNK_SIZE`` objects (todo 631).
    """
    targets = instance.__dict__.pop(_TARGETS_ATTR, ())
    entries = get_logentry_model().objects
    for content_type_id, pks in targets:
        for start in range(0, len(pks), PURGE_CHUNK_SIZE):
            _delete_in_chunks(
                entries.filter(
                    content_type_id=content_type_id,
                    object_pk__in=pks[start : start + PURGE_CHUNK_SIZE],
                )
            )


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
