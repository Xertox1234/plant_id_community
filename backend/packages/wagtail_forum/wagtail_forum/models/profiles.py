from django.conf import settings
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
    # Existing rows are backfilled to migration-apply time (see migration
    # 0016) so an established member's whole history doesn't show unread on
    # ship day; a profile created after that (lazily, via for_user()) gets
    # its own creation-time stamp — a host-agnostic proxy for "when they
    # showed up," since `user.date_joined` is off-limits here (AbstractUser-
    # only, not part of the AbstractBaseUser contract this package assumes).
    #
    # Accepted tradeoff, decided 2026-07-29 (todo 271 #1) — read this as the
    # standing disposition, not a stale TODO. for_user() is the package's lazy
    # profile-creation entry point and is reached from five non-test calls
    # across four modules, only ONE of which means "this user read something":
    #   * api/views.py TopicDetailView.retrieve   — a genuine read
    #   * api/views.py MeProfileView.get_object   — fetching one's own profile
    #   * workflow.py (x2)                        — trust check when the user
    #                                               submits a post
    #   * forum_host/tasks.py                     — push delivery, i.e. a
    #                                               THIRD PARTY's action
    # And for_user() is not even the only creation path: signals.py's
    # _refresh_profile calls ForumProfile.objects.get_or_create(user_id=...)
    # directly on every post-count/trust recount, bypassing this classmethod.
    # Whichever fires first stamps read_watermark_at=now, so for a pre-ship
    # "sleeper" account (no profile row yet) an unrelated trigger can collapse
    # that user's whole pre-existing unread backlog forest-wide, not just the
    # topic they were looking at (a push delivery involves no looking at all).
    # Accepted because: no live complaint; the blast radius is one cohort
    # (accounts predating the profile row) times one cosmetic signal (badge
    # state); and the genuine read path (TopicDetailView.retrieve's _mark_read
    # on_commit callback) already collapses the backlog forest-wide by design,
    # per its own comment there — so the non-read triggers differ in
    # propriety, not in effect. Re-scope trigger: an actual "why did my unread
    # badges disappear" report. The concrete candidate fix — seed the initial
    # watermark from `getattr(user, "date_joined", None)` so it derives from a
    # stable per-user fact instead of wall-clock-at-first-touch — is tracked
    # as todo 285, deliberately NOT bundled here (it changes unread semantics
    # for every existing account).
    read_watermark_at = models.DateTimeField(default=timezone.now)

    @classmethod
    def for_user(cls, user):
        # get_or_create is not atomic: under concurrent first-touch requests
        # (e.g. fan-out mobile API calls in Plan 1C) two callers can both miss
        # the SELECT and race to INSERT, with the loser hitting the OneToOne
        # unique constraint. Fall back to a plain get() in that case.
        try:
            profile, _ = cls.objects.get_or_create(user=user)
        except IntegrityError:
            profile = cls.objects.get(user=user)
        return profile

    def __str__(self):
        return self.display_name or self.user.get_username()
