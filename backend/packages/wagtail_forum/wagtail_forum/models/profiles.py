from django.conf import settings
from django.db import IntegrityError, models
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
