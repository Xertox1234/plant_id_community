"""
Core models for the Plant Community application.

Includes email tracking, notifications, and other shared functionality.
"""

import uuid

from django.contrib.auth import get_user_model
from django.core.validators import EmailValidator
from django.db import models
from django.utils import timezone

User = get_user_model()


class EmailNotification(models.Model):
    """
    Track all email notifications sent by the system.
    Used for analytics, debugging, and compliance.
    """

    # Status choices
    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_BOUNCED = "bounced"
    STATUS_DELIVERED = "delivered"
    STATUS_COMPLAINED = "complained"

    # Delivered, bounced and complained are set only by the provider's own
    # feedback (apps/core/email_feedback.py), never assumed from a send.
    # There is no "opened" state: opens are not collected (owner decision
    # 2026-10-12, todo 625). Clicks are EmailClick rows, not a status.
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
        (STATUS_BOUNCED, "Bounced"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_COMPLAINED, "Complained"),
    ]

    # Priority choices
    PRIORITY_LOW = "low"
    PRIORITY_NORMAL = "normal"
    PRIORITY_HIGH = "high"
    PRIORITY_URGENT = "urgent"

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_NORMAL, "Normal"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_URGENT, "Urgent"),
    ]

    # UUID for tracking
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for tracking",
    )

    # Email details
    email_type = models.CharField(
        max_length=100, help_text="Type of email (from EmailType constants)"
    )

    recipient_email = models.EmailField(
        validators=[EmailValidator()], help_text="Email address of recipient"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_notification_logs",
        help_text="User who received the email (if registered)",
    )

    subject = models.CharField(max_length=200, help_text="Email subject line")

    template_name = models.CharField(
        max_length=100, help_text="Template used for email"
    )

    # Status and tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        help_text="Current status of email",
    )

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_NORMAL,
        help_text="Email priority level",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    bounced_at = models.DateTimeField(null=True, blank=True)
    complained_at = models.DateTimeField(null=True, blank=True)

    # Correlation with the provider's feedback (todo 625). ``message_id`` is
    # the RFC 5322 Message-ID this app set on the message; Resend echoes it as
    # ``data.message_id``. ``provider_email_id`` is Resend's own id, stored
    # from the first event that matched, so a later event that carries only
    # that id still finds the row.
    message_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    provider_email_id = models.CharField(
        max_length=64, blank=True, default="", db_index=True
    )

    # Error tracking
    error_message = models.TextField(
        blank=True, help_text="Error message if sending failed"
    )

    retry_count = models.PositiveIntegerField(
        default=0, help_text="Number of retry attempts"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email_type"]),
            models.Index(fields=["recipient_email"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.email_type} to {self.recipient_email} ({self.status})"

    def mark_sent(self):
        """Mark email as sent."""
        self.status = self.STATUS_SENT
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])

    def mark_failed(self, error_message: str = None):
        """Mark email as failed."""
        self.status = self.STATUS_FAILED
        if error_message:
            self.error_message = error_message
        self.save(update_fields=["status", "error_message"])


class InAppNotification(models.Model):
    """
    In-app notifications for users.
    """

    # Category choices
    CATEGORY_PLANT_CARE = "plant_care"
    CATEGORY_FORUM = "forum"
    CATEGORY_IDENTIFICATION = "identification"
    CATEGORY_SYSTEM = "system"
    CATEGORY_COMMUNITY = "community"

    CATEGORY_CHOICES = [
        (CATEGORY_PLANT_CARE, "Plant Care"),
        (CATEGORY_FORUM, "Forum"),
        (CATEGORY_IDENTIFICATION, "Plant Identification"),
        (CATEGORY_SYSTEM, "System"),
        (CATEGORY_COMMUNITY, "Community"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="in_app_notifications"
    )

    title = models.CharField(max_length=200, help_text="Notification title")

    message = models.TextField(help_text="Notification message")

    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_SYSTEM
    )

    # Optional action URL
    action_url = models.URLField(
        blank=True, help_text="URL to navigate to when clicked"
    )

    # Status
    is_read = models.BooleanField(
        default=False, help_text="Whether user has read this notification"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["category"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        status = "Read" if self.is_read else "Unread"
        return f"{self.title} - {self.user.username} ({status})"

    def mark_read(self):
        """Mark notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class PushDevice(models.Model):
    """One mobile installation's FCM registration (todo 621).

    An account may hold any number of these, one per device, so a second
    phone no longer replaces the first. Shared by every push feature (forum
    and care reminders), which is why it lives here and not in the forum
    package. ``apps.core.push_devices`` is the only writer.

    ``token`` is globally unique: an FCM token identifies one installation,
    so registering it for an account releases it from any other. A token is
    a credential: never log it or echo it from the API.

    ``installation_id`` is a random id the app keeps for its install. When a
    token rotates, registering the new one replaces the row of the same
    installation instead of leaving the old token behind. Null for a row
    migrated from the legacy ``ForumProfile.fcm_token`` or written by an
    older app build, which sends no id.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="push_devices"
    )
    token = models.CharField(max_length=255, unique=True)
    installation_id = models.CharField(
        max_length=64, null=True, blank=True, unique=True
    )
    platform = models.CharField(max_length=16, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"PushDevice({self.platform or 'unknown'}) for user {self.user_id}"


class DeliveryIntent(models.Model):
    """One external delivery that must not be lost: the outbox (todo 619).

    Written in the same transaction as the event that causes it (a forum
    reply, a verification request), so it exists exactly when the event
    does, whatever happens to the broker afterwards. A worker claims the row
    before sending and records the outcome after; reconciliation
    (``apps.core.tasks.reconcile_deliveries``) re-drives a row whose enqueue
    was lost, whose transient failure is due for another attempt, or whose
    worker died mid-send. See ``apps/core/delivery.py`` for the contract.

    ``payload`` holds ids and display fields only. Never a message body, a
    token, a signed link or an email address: the row outlives the send.
    """

    class Kind(models.TextChoices):
        FORUM_EMAIL = "forum_email", "Forum email"
        FORUM_WEB_PUSH = "forum_web_push", "Forum browser push"
        # Mobile push (FCM), recorded since todo 624 so a quiet-hours or
        # coalescing hold survives a worker restart.
        FORUM_PUSH = "forum_push", "Forum mobile push"
        VERIFICATION_EMAIL = "verification_email", "Verification email"
        NEWSLETTER_CONFIRMATION = (
            "newsletter_confirmation",
            "Newsletter confirmation",
        )
        LOCKOUT_EMAIL = "lockout_email", "Account lockout email"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CLAIMED = "claimed", "Claimed"
        SENT = "sent", "Sent"
        SUPPRESSED = "suppressed", "Suppressed"
        FAILED = "failed", "Failed"

    kind = models.CharField(max_length=32, choices=Kind.choices)
    event = models.CharField(max_length=64, blank=True, default="")
    recipient = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    # What the delivery is about: a forum post pk, a newsletter subscriber pk.
    subject_key = models.CharField(max_length=64, blank=True, default="")
    batch_id = models.UUIDField(null=True, blank=True, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    claimed_at = models.DateTimeField(null=True, blank=True)
    claim_token = models.UUIDField(null=True, blank=True, db_index=True)
    # An exception class name or a suppression reason, never its message.
    last_error = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at"], name="core_delivery_due_idx"
            ),
            models.Index(
                fields=["kind", "recipient", "status"],
                name="core_delivery_recipient_idx",
            ),
        ]
        constraints = [
            # One forum delivery per channel, event, post and recipient: a
            # duplicate dispatch inserts nothing (ON CONFLICT DO NOTHING).
            models.UniqueConstraint(
                fields=["kind", "event", "subject_key", "recipient"],
                condition=models.Q(
                    kind__in=["forum_email", "forum_web_push", "forum_push"]
                ),
                name="uniq_core_forum_delivery",
            ),
        ]

    def __str__(self):
        return f"DeliveryIntent({self.kind}, {self.status}) #{self.pk}"


class EmailSuppression(models.Model):
    """An address the provider said not to mail again (todo 625).

    Keyed by a SHA-256 of the normalized address, never the address itself:
    the row has to outlive the account (an address that hard-bounced still
    bounces after its account is deleted), and a hash is enough to answer
    "is this address suppressed?". The policy is in
    ``apps/core/email_feedback.py`` and docs/operations/notification-baseline.md:
    a hard bounce stops all mail to the address, a complaint stops optional
    mail only. A reason is only ever strengthened, never weakened, by a later
    event; staff lift a suppression by deleting the row.
    """

    class Reason(models.TextChoices):
        COMPLAINT = "complaint", "Spam complaint"
        HARD_BOUNCE = "hard_bounce", "Hard bounce"

    address_hash = models.CharField(max_length=64, unique=True)
    reason = models.CharField(max_length=16, choices=Reason.choices)
    # The provider event (svix id) that last set the reason.
    source_event = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"EmailSuppression({self.reason}) #{self.pk}"


class EmailProviderEvent(models.Model):
    """One webhook event from the email provider, kept for replay safety.

    ``svix_id`` is unique: the same event delivered twice (Svix retries until
    it gets a 2xx) is recorded once and applied once. No address, subject or
    bounce message text is stored; the bounce ``message`` can quote the
    address. Deleted after ``EMAIL_FEEDBACK_RETENTION_DAYS``.
    """

    svix_id = models.CharField(max_length=64, unique=True)
    event_type = models.CharField(max_length=40)
    # The event's own time (top-level ``created_at``), not its arrival time.
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    notification = models.ForeignKey(
        EmailNotification,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="provider_events",
    )
    provider_email_id = models.CharField(max_length=64, blank=True, default="")
    bounce_type = models.CharField(max_length=32, blank=True, default="")
    bounce_subtype = models.CharField(max_length=32, blank=True, default="")

    def __str__(self):
        return f"EmailProviderEvent({self.event_type}) #{self.pk}"


class EmailClick(models.Model):
    """A click on a tracked link in one email: first-party click attribution
    (todo 625, owner decision 2026-10-12).

    Written by the signed click redirect (``apps/core/api/email_feedback.py``)
    only. One row per email and link, so a repeated click is never counted
    twice; only a click within ``EMAIL_CLICK_ATTRIBUTION_DAYS`` of the send is
    recorded. Deleted after ``EMAIL_FEEDBACK_RETENTION_DAYS`` and with the
    account. No IP address or user agent is stored.
    """

    notification = models.ForeignKey(
        EmailNotification, on_delete=models.CASCADE, related_name="clicks"
    )
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="email_clicks",
    )
    # Which link: a key of EMAIL_TRACKED_LINK_KEYS, never the URL itself.
    link = models.CharField(max_length=32)
    clicked_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "link"], name="uniq_core_email_click"
            )
        ]

    def __str__(self):
        return f"EmailClick({self.link}) #{self.pk}"
