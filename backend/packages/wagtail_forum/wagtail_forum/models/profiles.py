from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from wagtail.images import get_image_model_string


class TrustLevel(models.IntegerChoices):
    NEW = 0, _("New")
    BASIC = 1, _("Basic")
    MEMBER = 2, _("Member")
    REGULAR = 3, _("Regular")
    LEADER = 4, _("Leader")


class ForumProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wagtail_forum_profile",
    )
    # Member-editable (via API in Plan 1C).
    display_name = models.CharField(max_length=80, blank=True)
    avatar = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    bio = models.TextField(blank=True)
    signature = models.CharField(max_length=255, blank=True)
    # FCM device token — registered by the mobile app on login. Used by
    # forum_host/tasks.py to deliver push notifications. Nullable: a user
    # who has never registered a token (web-only) simply receives no pushes.
    fcm_token = models.CharField(max_length=255, blank=True, default="")
    # Forum "user title" (cf. Discourse): a role label shown beside the name
    # ("Head moderator", "Master gardener"). Admin-set only — deliberately NOT
    # member-editable via MeProfileSerializer; it reads as an endorsement.
    title = models.CharField(max_length=80, blank=True, default="")
    # System-computed (read-only to members).
    trust_level = models.PositiveSmallIntegerField(
        choices=TrustLevel.choices, default=TrustLevel.NEW
    )
    post_count = models.PositiveIntegerField(default=0)
    flags_received = models.PositiveIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    # Per-user fallback baseline for "unread" (todo 253 slice 5, H10): a
    # topic is unread if its last_post_at is newer than this, UNLESS a more
    # specific TopicRead row exists for that exact topic. Plain default (not
    # auto_now_add) so a future "mark all read" action can advance it.
    #
    # This wall-clock default is now only the LAST resort: both creation paths
    # pass an explicit seed from initial_read_watermark() (see that method), so
    # this default only fires for a row created by something that bypasses both
    # — e.g. a raw ForumProfile.objects.create() in a test. A host whose user
    # model has no `date_joined` lands on the same now() value, but via
    # initial_read_watermark()'s own fallback rather than this default.
    #
    # Todo 285 (2026-07-31) closed the tradeoff todo 271 #1 had accepted here.
    # The gap was: profile creation is reached from seven non-test call sites
    # across five modules, only ONE of which means "this user read something":
    #   * api/views.py TopicDetailView.retrieve   — a genuine read
    #   * api/views.py MeProfileView.get_object   — fetching one's own profile
    #   * workflow.py (x2)                        — trust check when the user
    #                                               submits a post
    #   * api/direct_messages.py _screen_dm_body  — trust check when the user
    #                                               sends a DM (todo 280)
    #   * forum_host/tasks.py                     — push delivery, i.e. a
    #                                               THIRD PARTY's action
    #   * signals.py _refresh_profile             — post-count/trust recount,
    #                                               which bypasses for_user()
    #                                               entirely (get_or_create on
    #                                               user_id)
    # (api/presence.py touch_last_seen deliberately does NOT appear here: it
    # uses .filter(user=user), so a presence ping creates no row.)
    # Whichever fired first stamped read_watermark_at=now, so for a pre-ship
    # "sleeper" account (no profile row yet) an unrelated trigger could
    # collapse that user's whole pre-existing unread backlog forest-wide, not
    # just the topic they were looking at (a push delivery involves no looking
    # at all). Seeding from a stable per-user fact makes *which* trigger fires
    # first stop mattering, which is why BOTH creation paths were fixed rather
    # than only the lazy classmethod.
    #
    # Existing rows are deliberately left alone: migration 0016 already
    # backfilled them to migration-apply time, and re-deriving them from
    # date_joined would resurface an established member's entire pre-0016
    # backlog — exactly what 0016 was written to avoid.
    #
    # The sleeper cohort (an old account with no profile row yet) DOES get its
    # real backlog surfaced on first touch, and that is the intended outcome,
    # not an inconsistency with the paragraph above: the two cases differ in
    # whether the user was ever shown that content. An 0016 row's owner had a
    # profile through launch; a sleeper never did, so collapsing their backlog
    # would be hiding posts they have not seen. In practice the flood is
    # bounded because no forum content predates UNREAD_LAUNCH_AT — NOT
    # because the annotation falls through to that constant. _annotate_topic_unread
    # Coalesces TopicRead, then the watermark, then UNREAD_LAUNCH_AT, so once
    # any profile row exists the constant is never reached. If UNREAD_LAUNCH_AT
    # is ever moved forward past a sleeper's date_joined, that bound is gone.
    read_watermark_at = models.DateTimeField(default=timezone.now)

    @staticmethod
    def initial_read_watermark(user):
        """Seed value for a NEW profile's ``read_watermark_at``.

        Derived from a stable per-user fact rather than wall-clock-at-first-
        touch, so an unrelated trigger creating the row does not silently mark
        that user's whole backlog read (todo 285).

        ``getattr`` keeps this host-agnostic: ``date_joined`` is
        ``AbstractUser``-only, not part of the ``AbstractBaseUser`` contract
        this package assumes, so a host without it falls back to the field's
        wall-clock default, i.e. to the pre-285 behaviour.
        """
        return getattr(user, "date_joined", None) or timezone.now()

    @classmethod
    def initial_read_watermark_for_user_id(cls, user_id):
        """``initial_read_watermark`` for a caller that holds only a user id.

        Pass this as a *callable* in ``get_or_create(defaults=...)``: Django
        resolves callable defaults only on the create branch (``resolve_callables``
        in ``django/db/models/query.py``), so this extra SELECT never runs on the
        common already-exists path.
        """
        # _base_manager, not _default_manager: a host whose User model
        # filters its default manager (soft-delete / active-only) would
        # otherwise get None back for those users and silently fall through
        # to now(), reinstating the very bug this closes. _base_manager is
        # unfiltered by contract — it is what Django itself uses to resolve
        # related objects.
        user = get_user_model()._base_manager.filter(pk=user_id).first()
        return cls.initial_read_watermark(user)

    @classmethod
    def for_user(cls, user):
        # get_or_create is not atomic: under concurrent first-touch requests
        # (e.g. fan-out mobile API calls in Plan 1C) two callers can both miss
        # the SELECT and race to INSERT, with the loser hitting the OneToOne
        # unique constraint. Fall back to a plain get() in that case.
        try:
            profile, _ = cls.objects.get_or_create(
                user=user,
                defaults={
                    "read_watermark_at": lambda: cls.initial_read_watermark(user)
                },
            )
        except IntegrityError:
            profile = cls.objects.get(user=user)
        return profile

    def __str__(self):
        return self.display_name or self.user.get_username()
