from django.conf import settings
from django.db import IntegrityError, models
from django.utils import timezone
from wagtail.images import get_image_model_string


class TrustLevel(models.IntegerChoices):
    NEW = 0, "New"
    BASIC = 1, "Basic"
    MEMBER = 2, "Member"
    REGULAR = 3, "Regular"
    LEADER = 4, "Leader"


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
    # Known gap (todo 271): for_user() is called from several trigger points
    # beyond "this user opened a topic" — MeProfileView and the push-delivery
    # task (forum_host/tasks.py) both create a profile as a side effect of
    # unrelated actions. For a pre-ship "sleeper" account, whichever of these
    # fires first stamps read_watermark_at=now and silently collapses that
    # user's entire pre-existing unread backlog, not just the topic (if any)
    # they were actually looking at. Not fixed here — see the todo.
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
