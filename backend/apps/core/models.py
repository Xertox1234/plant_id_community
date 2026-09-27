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
    STATUS_OPENED = "opened"
    STATUS_CLICKED = "clicked"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
        (STATUS_BOUNCED, "Bounced"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_OPENED, "Opened"),
        (STATUS_CLICKED, "Clicked"),
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
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    error_message = models.TextField(
        blank=True, help_text="Error message if sending failed"
    )

    retry_count = models.PositiveIntegerField(
        default=0, help_text="Number of retry attempts"
    )

    # Analytics
    open_count = models.PositiveIntegerField(
        default=0, help_text="Number of times email was opened"
    )

    click_count = models.PositiveIntegerField(
        default=0, help_text="Number of times links were clicked"
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

    def mark_opened(self):
        """Mark email as opened."""
        if self.status == self.STATUS_SENT:
            self.status = self.STATUS_OPENED
            self.opened_at = timezone.now()
        self.open_count += 1
        self.save(update_fields=["status", "opened_at", "open_count"])

    def mark_clicked(self):
        """Mark email as clicked."""
        if self.status in [self.STATUS_SENT, self.STATUS_OPENED]:
            self.status = self.STATUS_CLICKED
            self.clicked_at = timezone.now()
        self.click_count += 1
        self.save(update_fields=["status", "clicked_at", "click_count"])


class ForumNotificationSubscription(models.Model):
    """
    User subscriptions to forum notifications.
    """

    # Notification type choices
    TYPE_TOPIC_REPLY = "topic_reply"
    TYPE_MENTION = "mention"
    TYPE_NEW_TOPIC = "new_topic"
    TYPE_DIGEST = "digest"

    TYPE_CHOICES = [
        (TYPE_TOPIC_REPLY, "Topic Replies"),
        (TYPE_MENTION, "Mentions"),
        (TYPE_NEW_TOPIC, "New Topics"),
        (TYPE_DIGEST, "Daily/Weekly Digest"),
    ]

    # Frequency choices
    FREQUENCY_INSTANT = "instant"
    FREQUENCY_DAILY = "daily"
    FREQUENCY_WEEKLY = "weekly"
    FREQUENCY_NEVER = "never"

    FREQUENCY_CHOICES = [
        (FREQUENCY_INSTANT, "Instant"),
        (FREQUENCY_DAILY, "Daily Digest"),
        (FREQUENCY_WEEKLY, "Weekly Digest"),
        (FREQUENCY_NEVER, "Never"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="forum_subscriptions"
    )

    notification_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, help_text="Type of forum notification"
    )

    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default=FREQUENCY_INSTANT,
        help_text="How often to send notifications",
    )

    # Optional: specific topic/forum subscriptions
    topic_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Specific topic ID (for topic reply notifications)",
    )

    forum_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Specific forum ID (for forum-specific notifications)",
    )

    is_active = models.BooleanField(
        default=True, help_text="Whether this subscription is active"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["user", "notification_type", "topic_id", "forum_id"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["notification_type", "frequency"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.notification_type} ({self.frequency})"


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
