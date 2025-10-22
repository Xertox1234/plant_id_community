"""
User models for the Plant Community application.

Extends Django's default User model with plant-specific fields and social features.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.urls import reverse
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill
from taggit.managers import TaggableManager
from apps.core.validators import validate_avatar_image
import uuid


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser with plant community features.
    """
    
    # UUID for secure references (prevents IDOR attacks)
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    # Profile Information
    bio = models.TextField(
        max_length=500,
        blank=True,
        help_text="Tell us about yourself and your plant interests"
    )
    
    location = models.CharField(
        max_length=100,
        blank=True,
        help_text="City, Country or general location"
    )
    
    # Enhanced Location Fields for Garden Calendar
    hardiness_zone = models.CharField(
        max_length=5,
        blank=True,
        help_text="USDA Hardiness Zone (e.g., '7a', '9b') for climate-specific recommendations"
    )
    
    zip_code = models.CharField(
        max_length=10,
        blank=True,
        help_text="ZIP/Postal code for weather and local event integration"
    )
    
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude coordinate for precise location-based features"
    )
    
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude coordinate for precise location-based features"
    )
    
    location_privacy = models.CharField(
        max_length=20,
        choices=[
            ('private', 'Private - Don\'t share my location'),
            ('zone_only', 'Zone Only - Share my hardiness zone'),
            ('city', 'City Level - Share my city/region'),
            ('precise', 'Precise - Share exact coordinates (for close friends)')
        ],
        default='zone_only',
        help_text="Control how much location information is shared with other users"
    )
    
    microclimate_offset = models.SmallIntegerField(
        default=0,
        help_text="Temperature offset in Fahrenheit for microclimate adjustments (-10 to +10)"
    )
    
    website = models.URLField(
        blank=True,
        help_text="Your personal website or blog"
    )
    
    # Profile Image
    avatar = models.ImageField(
        upload_to='avatars/',
        validators=[validate_avatar_image],
        null=True,
        blank=True,
        help_text="Upload a profile picture"
    )
    
    avatar_thumbnail = ImageSpecField(
        source='avatar',
        processors=[ResizeToFill(150, 150)],
        format='JPEG',
        options={'quality': 85}
    )
    
    # Plant-related fields
    gardening_experience = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner (< 1 year)'),
            ('intermediate', 'Intermediate (1-5 years)'),
            ('advanced', 'Advanced (5+ years)'),
            ('expert', 'Expert (Professional/Botanist)'),
        ],
        blank=True,
        help_text="Your gardening/plant care experience level"
    )
    
    favorite_plant_types = TaggableManager(
        blank=True,
        help_text="Tag your favorite types of plants (e.g., succulents, ferns, flowers)"
    )
    
    # Social Features
    following = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='followers',
        blank=True,
        help_text="Users you are following"
    )
    
    # Privacy Settings
    profile_visibility = models.CharField(
        max_length=10,
        choices=[
            ('public', 'Public - Anyone can see my profile'),
            ('friends', 'Friends Only - Only people I follow can see my profile'),
            ('private', 'Private - Only I can see my profile'),
        ],
        default='public',
        help_text="Control who can see your profile"
    )
    
    show_email = models.BooleanField(
        default=False,
        help_text="Show email address on your public profile"
    )
    
    show_location = models.BooleanField(
        default=True,
        help_text="Show location on your public profile"
    )
    
    # Notification Settings
    email_notifications = models.BooleanField(
        default=True,
        help_text="Receive email notifications for activity"
    )
    
    plant_id_notifications = models.BooleanField(
        default=True,
        help_text="Get notified when someone identifies your plant photos"
    )
    
    forum_notifications = models.BooleanField(
        default=True,
        help_text="Get notified about forum replies and mentions"
    )
    
    # Care reminder preferences
    care_reminder_notifications = models.BooleanField(
        default=True,
        help_text="Receive push notifications for plant care reminders"
    )
    
    care_reminder_email = models.BooleanField(
        default=False,
        help_text="Receive email notifications for plant care reminders"
    )
    
    # Account Statistics
    plants_identified = models.PositiveIntegerField(
        default=0,
        help_text="Number of plants identified by this user"
    )
    
    identifications_helped = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this user helped identify plants for others"
    )
    
    forum_posts_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of forum posts made by this user"
    )
    
    # Trust Level System for Forum Permissions
    TRUST_LEVELS = [
        ('new', 'New Member'),
        ('basic', 'Basic Member'),
        ('trusted', 'Trusted Member'),
        ('veteran', 'Veteran Member'),
    ]
    
    trust_level = models.CharField(
        max_length=10,
        choices=TRUST_LEVELS,
        default='new',
        help_text="Trust level for forum permissions (affects image uploads, etc.)"
    )
    
    posts_count_verified = models.PositiveIntegerField(
        default=0,
        help_text="Number of approved/verified forum posts (cached for performance)"
    )
    
    trust_level_updated = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True,
        help_text="Last time trust level was recalculated"
    )
    
    # Generic created/updated timestamps for API parity
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'auth_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.username
    
    def get_absolute_url(self):
        return reverse('users:profile', kwargs={'username': self.username})
    
    @property
    def display_name(self):
        """Return the best display name for the user."""
        if self.get_full_name():
            return self.get_full_name()
        return self.username
    
    @property
    def follower_count(self):
        """Return the number of followers."""
        return self.followers.count()
    
    @property
    def following_count(self):
        """Return the number of users being followed."""
        return self.following.count()
    
    def is_following(self, user):
        """Check if this user is following another user."""
        return self.following.filter(id=user.id).exists()
    
    def follow(self, user):
        """Follow another user."""
        if not self.is_following(user) and user != self:
            self.following.add(user)
    
    def unfollow(self, user):
        """Unfollow another user."""
        if self.is_following(user):
            self.following.remove(user)
    
    @property
    def account_age_days(self):
        """Return the number of days since account creation."""
        from django.utils import timezone
        return (timezone.now() - self.date_joined).days
    
    def can_upload_images(self):
        """Check if user can upload images based on trust level."""
        # Staff and superusers can always upload
        if self.is_staff or self.is_superuser:
            return True
        
        # Basic trust level and above can upload images
        return self.trust_level in ['basic', 'trusted', 'veteran']
    
    def update_trust_level(self):
        """Update user's trust level based on activity and account age."""
        from django.utils import timezone
        
        # Don't downgrade trust levels automatically (only upgrades)
        current_level_index = [level[0] for level in self.TRUST_LEVELS].index(self.trust_level)
        
        # Calculate new trust level based on criteria
        new_level = 'new'
        
        # Progression criteria
        if (self.posts_count_verified >= 100 and self.account_age_days >= 90 and 
            current_level_index < 3):
            new_level = 'veteran'
        elif (self.posts_count_verified >= 25 and self.account_age_days >= 30 and 
              current_level_index < 2):
            new_level = 'trusted'
        elif (self.posts_count_verified >= 5 and self.account_age_days >= 7 and 
              current_level_index < 1):
            new_level = 'basic'
        
        # Only update if it's an upgrade
        new_level_index = [level[0] for level in self.TRUST_LEVELS].index(new_level)
        if new_level_index > current_level_index:
            old_level = self.trust_level
            self.trust_level = new_level
            self.trust_level_updated = timezone.now()
            self.save(update_fields=['trust_level', 'trust_level_updated'])
            
            # Log the trust level upgrade for potential notifications
            self.log_trust_level_upgrade(old_level, new_level)
            
        return self.trust_level
    
    def log_trust_level_upgrade(self, old_level, new_level):
        """Log trust level upgrades for potential notifications."""
        try:
            ActivityLog.objects.create(
                user=self,
                activity_type='trust_level_upgrade',
                description=f"Trust level upgraded from {old_level} to {new_level}",
                is_public=False
            )
        except Exception:
            # Don't fail if activity logging fails
            pass
    
    def get_trust_level_display_info(self):
        """Get detailed information about current trust level and next requirements."""
        trust_info = {
            'current_level': self.trust_level,
            'current_display': self.get_trust_level_display(),
            'can_upload_images': self.can_upload_images(),
            'posts_count': self.posts_count_verified,
            'account_age_days': self.account_age_days,
        }
        
        # Add next level requirements
        if self.trust_level == 'new':
            trust_info.update({
                'next_level': 'basic',
                'posts_needed': max(0, 5 - self.posts_count_verified),
                'days_needed': max(0, 7 - self.account_age_days),
            })
        elif self.trust_level == 'basic':
            trust_info.update({
                'next_level': 'trusted',
                'posts_needed': max(0, 25 - self.posts_count_verified),
                'days_needed': max(0, 30 - self.account_age_days),
            })
        elif self.trust_level == 'trusted':
            trust_info.update({
                'next_level': 'veteran',
                'posts_needed': max(0, 100 - self.posts_count_verified),
                'days_needed': max(0, 90 - self.account_age_days),
            })
        else:  # veteran
            trust_info.update({
                'next_level': None,
                'posts_needed': 0,
                'days_needed': 0,
            })
        
        return trust_info


class UserPlantCollection(models.Model):
    """
    Model to represent a user's plant collection.
    """
    
    # UUID for secure references (prevents IDOR attacks)
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='plant_collections'
    )
    
    name = models.CharField(
        max_length=100,
        help_text="Name of your plant collection (e.g., 'Indoor Plants', 'Garden')"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of this plant collection"
    )
    
    is_public = models.BooleanField(
        default=True,
        help_text="Make this collection visible to other users"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'name']
    
    def __str__(self):
        return f"{self.user.username}'s {self.name}"
    
    @property
    def plant_count(self):
        """Return the number of plants in this collection."""
        return self.plants.count()


class UserMessage(models.Model):
    """
    Model for private messages between users.
    """
    
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_messages'
    )
    
    subject = models.CharField(
        max_length=200,
        help_text="Message subject"
    )
    
    message = models.TextField(
        help_text="Message content"
    )
    
    is_read = models.BooleanField(
        default=False,
        help_text="Has the recipient read this message?"
    )
    
    parent_message = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        help_text="Parent message if this is a reply"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Message from {self.sender.username} to {self.recipient.username}: {self.subject}"
    
    def mark_as_read(self):
        """Mark this message as read."""
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class ActivityLog(models.Model):
    """
    Model to track user activities for the activity feed.
    """
    
    ACTIVITY_TYPES = [
        ('plant_identified', 'Plant Identified'),
        ('plant_added', 'Plant Added to Collection'),
        ('user_followed', 'User Followed'),
        ('forum_post', 'Forum Post Created'),
        ('forum_reply', 'Forum Reply Created'),
        ('profile_updated', 'Profile Updated'),
        ('trust_level_upgrade', 'Trust Level Upgraded'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    
    activity_type = models.CharField(
        max_length=20,
        choices=ACTIVITY_TYPES
    )
    
    description = models.CharField(
        max_length=255,
        help_text="Human-readable description of the activity"
    )
    
    # Generic foreign key fields for linking to any model
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    
    is_public = models.BooleanField(
        default=True,
        help_text="Should this activity be visible to other users?"
    )
    
    created_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username}: {self.description}"


class PushSubscription(models.Model):
    """
    Model to store Web Push API subscription data for users.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
        help_text="User who owns this push subscription"
    )
    
    # Web Push subscription data
    endpoint = models.URLField(
        max_length=500,
        help_text="Push service endpoint URL"
    )
    
    p256dh_key = models.CharField(
        max_length=255,
        help_text="P256DH public key for encryption"
    )
    
    auth_key = models.CharField(
        max_length=255,
        help_text="Auth secret for encryption"
    )
    
    # Device/browser identification
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string for device identification"
    )
    
    device_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Human-readable device name (e.g., 'Chrome on Android')"
    )
    
    # Subscription metadata
    is_active = models.BooleanField(
        default=True,
        help_text="Is this subscription currently active?"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this subscription was used to send a notification"
    )
    
    class Meta:
        unique_together = ['user', 'endpoint']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['endpoint']),
        ]
    
    def __str__(self):
        return f"Push subscription for {self.user.username} ({self.device_name or 'Unknown device'})"
    
    def mark_as_used(self):
        """Update the last_used timestamp."""
        from django.utils import timezone
        self.last_used = timezone.now()
        self.save(update_fields=['last_used'])
    
    def deactivate(self):
        """Deactivate this subscription (usually due to failed delivery)."""
        self.is_active = False
        self.save(update_fields=['is_active'])


class CareReminder(models.Model):
    """
    Model for managing plant care reminders.
    """
    
    REMINDER_TYPES = [
        ('watering', 'Watering'),
        ('fertilizing', 'Fertilizing'),
        ('repotting', 'Repotting'),
        ('pruning', 'Pruning'),
        ('inspection', 'General Inspection'),
        ('custom', 'Custom Care Task'),
    ]
    
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Every 2 weeks'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Every 3 months'),
        ('biannual', 'Every 6 months'),
        ('annual', 'Yearly'),
        ('custom', 'Custom interval'),
    ]
    
    # UUID for secure references
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='care_reminders',
        help_text="User who owns this reminder"
    )
    
    # Link to saved care instructions
    saved_care_instructions = models.ForeignKey(
        'plant_identification.SavedCareInstructions',
        on_delete=models.CASCADE,
        related_name='reminders',
        help_text="Care instructions this reminder is based on"
    )
    
    # Reminder details
    reminder_type = models.CharField(
        max_length=20,
        choices=REMINDER_TYPES,
        help_text="Type of care reminder"
    )
    
    title = models.CharField(
        max_length=200,
        help_text="Reminder title (e.g., 'Water your Fiddle Leaf Fig')"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Optional detailed description or instructions"
    )
    
    # Scheduling
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='weekly',
        help_text="How often this reminder should trigger"
    )
    
    custom_interval_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Custom interval in days (for custom frequency)"
    )
    
    next_reminder_date = models.DateTimeField(
        help_text="When this reminder should next trigger"
    )
    
    last_reminder_sent = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last reminder was sent"
    )
    
    # User interaction tracking
    total_sent = models.PositiveIntegerField(
        default=0,
        help_text="Total number of reminders sent"
    )
    
    total_completed = models.PositiveIntegerField(
        default=0,
        help_text="Number of times user marked as completed"
    )
    
    total_snoozed = models.PositiveIntegerField(
        default=0,
        help_text="Number of times user snoozed this reminder"
    )
    
    current_streak = models.PositiveIntegerField(
        default=0,
        help_text="Current streak of completed reminders"
    )
    
    longest_streak = models.PositiveIntegerField(
        default=0,
        help_text="Longest streak of completed reminders"
    )
    
    # Settings
    is_active = models.BooleanField(
        default=True,
        help_text="Is this reminder currently active?"
    )
    
    send_push_notification = models.BooleanField(
        default=True,
        help_text="Send push notifications for this reminder"
    )
    
    send_email_notification = models.BooleanField(
        default=False,
        help_text="Send email notifications for this reminder"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['next_reminder_date']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['next_reminder_date', 'is_active']),
            models.Index(fields=['reminder_type']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.get_frequency_display()}"
    
    def calculate_next_reminder_date(self):
        """Calculate the next reminder date based on frequency."""
        from django.utils import timezone
        from datetime import timedelta
        
        if self.frequency == 'custom' and self.custom_interval_days:
            delta = timedelta(days=self.custom_interval_days)
        else:
            frequency_map = {
                'daily': timedelta(days=1),
                'weekly': timedelta(weeks=1),
                'biweekly': timedelta(weeks=2),
                'monthly': timedelta(days=30),
                'quarterly': timedelta(days=90),
                'biannual': timedelta(days=180),
                'annual': timedelta(days=365),
            }
            delta = frequency_map.get(self.frequency, timedelta(weeks=1))
        
        base_date = self.last_reminder_sent or timezone.now()
        return base_date + delta
    
    def mark_completed(self):
        """Mark this reminder as completed and update streaks."""
        from django.utils import timezone
        
        self.total_completed += 1
        self.current_streak += 1
        
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        
        # Calculate next reminder date
        self.last_reminder_sent = timezone.now()
        self.next_reminder_date = self.calculate_next_reminder_date()
        
        self.save(update_fields=[
            'total_completed', 'current_streak', 'longest_streak',
            'last_reminder_sent', 'next_reminder_date'
        ])
    
    def mark_snoozed(self, snooze_hours=24):
        """Snooze this reminder for a specified number of hours."""
        from django.utils import timezone
        from datetime import timedelta
        
        self.total_snoozed += 1
        self.next_reminder_date = timezone.now() + timedelta(hours=snooze_hours)
        
        self.save(update_fields=['total_snoozed', 'next_reminder_date'])
    
    def mark_skipped(self):
        """Skip this reminder and reset streak."""
        self.current_streak = 0
        self.last_reminder_sent = timezone.now()
        self.next_reminder_date = self.calculate_next_reminder_date()
        
        self.save(update_fields=[
            'current_streak', 'last_reminder_sent', 'next_reminder_date'
        ])
    
    def send_reminder(self):
        """Send the reminder notification and update counters."""
        from django.utils import timezone
        
        self.total_sent += 1
        self.last_reminder_sent = timezone.now()
        
        self.save(update_fields=['total_sent', 'last_reminder_sent'])
        
        # Import here to avoid circular imports
        from .services import NotificationService
        
        # Send push notification if enabled
        if self.send_push_notification:
            NotificationService.send_care_reminder_push(self)
        
        # Send email notification if enabled
        if self.send_email_notification:
            NotificationService.send_care_reminder_email(self)


class CareReminderLog(models.Model):
    """
    Model to log care reminder actions for analytics and user history.
    """
    
    ACTION_CHOICES = [
        ('sent', 'Reminder Sent'),
        ('completed', 'Marked as Completed'),
        ('snoozed', 'Snoozed'),
        ('skipped', 'Skipped'),
        ('dismissed', 'Dismissed'),
    ]
    
    reminder = models.ForeignKey(
        CareReminder,
        on_delete=models.CASCADE,
        related_name='action_logs'
    )
    
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        help_text="Action taken on the reminder"
    )
    
    action_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional data about the action (e.g., snooze duration)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reminder', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.reminder.title} - {self.get_action_display()}"


class OnboardingProgress(models.Model):
    """
    Model to track user's onboarding progress through the getting started checklist.
    """
    
    ONBOARDING_STEPS = [
        ('account_created', 'Account Created'),
        ('profile_completed', 'Profile Completed'),
        ('first_plant_identified', 'First Plant Identified'),
        ('care_card_saved', 'Care Card Saved'),
        ('forum_category_followed', 'Forum Category Followed'),
        ('first_forum_post', 'First Forum Post Created'),
        ('push_notifications_enabled', 'Push Notifications Enabled'),
        ('care_reminder_set', 'Care Reminder Set'),
        ('onboarding_completed', 'Onboarding Completed'),
    ]
    
    # UUID for secure references
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='onboarding_progress',
        help_text="User whose onboarding progress this tracks"
    )
    
    # Onboarding steps tracking
    current_step = models.CharField(
        max_length=30,
        choices=ONBOARDING_STEPS,
        default='account_created',
        help_text="Current step in the onboarding process"
    )
    
    completed_steps = models.JSONField(
        default=list,
        help_text="List of completed onboarding steps"
    )
    
    # Progress metadata
    is_onboarding_active = models.BooleanField(
        default=True,
        help_text="Is the user currently in the onboarding flow?"
    )
    
    is_onboarding_completed = models.BooleanField(
        default=False,
        help_text="Has the user completed the full onboarding?"
    )
    
    onboarding_version = models.CharField(
        max_length=10,
        default='1.0',
        help_text="Version of the onboarding flow the user went through"
    )
    
    # Demo mode settings
    demo_mode_enabled = models.BooleanField(
        default=False,
        help_text="Is demo mode currently enabled for this user?"
    )
    
    demo_data_shown = models.JSONField(
        default=dict,
        help_text="Track which demo data has been shown to the user"
    )
    
    # User preferences during onboarding
    skip_demo_mode = models.BooleanField(
        default=False,
        help_text="User chose to skip demo mode"
    )
    
    preferred_plant_types = models.JSONField(
        default=list,
        help_text="Plant types the user showed interest in during onboarding"
    )
    
    interested_features = models.JSONField(
        default=list,
        help_text="Features the user expressed interest in"
    )
    
    # Simple flags used by frontend onboarding UI
    completed_welcome = models.BooleanField(
        default=False,
        help_text="User completed welcome step"
    )
    completed_first_tour = models.BooleanField(
        default=False,
        help_text="User completed their first guided tour"
    )
    completed_tours = models.JSONField(
        default=list,
        help_text="List of completed tour identifiers (e.g., 'dashboard')"
    )
    completed_checklist = models.BooleanField(
        default=False,
        help_text="User completed the getting started checklist"
    )
    demo_data_created = models.BooleanField(
        default=False,
        help_text="Demo data has been generated for this user"
    )
    demo_data_skipped = models.BooleanField(
        default=False,
        help_text="User chose to skip creating demo data"
    )
    first_identification_completed = models.BooleanField(
        default=False,
        help_text="User completed their first plant identification"
    )
    first_care_reminder_created = models.BooleanField(
        default=False,
        help_text="User created their first care reminder"
    )
    first_forum_post_created = models.BooleanField(
        default=False,
        help_text="User created their first forum post"
    )
    push_notifications_enabled = models.BooleanField(
        default=False,
        help_text="User enabled push notifications during onboarding"
    )
    batch_identification_tried = models.BooleanField(
        default=False,
        help_text="User tried batch identification feature"
    )
    
    # Analytics data
    onboarding_entry_point = models.CharField(
        max_length=50,
        blank=True,
        help_text="How the user discovered the platform (organic, referral, etc.)"
    )
    
    total_onboarding_time_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total time spent in onboarding flow"
    )
    
    steps_completion_times = models.JSONField(
        default=dict,
        help_text="Time taken to complete each onboarding step"
    )
    
    # Timestamps
    onboarding_started_at = models.DateTimeField(auto_now_add=True)
    last_step_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the user last completed an onboarding step"
    )
    onboarding_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the user completed the full onboarding"
    )
    
    # Generic created/updated timestamps for API parity
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['is_onboarding_active']),
            models.Index(fields=['current_step']),
            models.Index(fields=['onboarding_completed_at']),
        ]
    
    def __str__(self):
        return f"Onboarding for {self.user.username} - {self.get_current_step_display()}"
    
    def complete_step(self, step_name, time_taken_seconds=None):
        """Mark a specific onboarding step as completed."""
        from django.utils import timezone
        
        if step_name not in [choice[0] for choice in self.ONBOARDING_STEPS]:
            raise ValueError(f"Invalid onboarding step: {step_name}")
        
        # Add to completed steps if not already there
        if step_name not in self.completed_steps:
            self.completed_steps.append(step_name)
        
        # Update timing data
        if time_taken_seconds:
            self.steps_completion_times[step_name] = time_taken_seconds
        
        # Update timestamps
        self.last_step_completed_at = timezone.now()
        
        # Move to next step if this was the current step
        if step_name == self.current_step:
            next_step = self._get_next_step(step_name)
            if next_step:
                self.current_step = next_step
            else:
                # All steps completed
                self.is_onboarding_completed = True
                self.is_onboarding_active = False
                self.onboarding_completed_at = timezone.now()
                
                # Calculate total onboarding time
                if self.onboarding_started_at:
                    delta = timezone.now() - self.onboarding_started_at
                    self.total_onboarding_time_seconds = int(delta.total_seconds())
        
        self.save(update_fields=[
            'completed_steps', 'steps_completion_times', 'last_step_completed_at',
            'current_step', 'is_onboarding_completed', 'is_onboarding_active',
            'onboarding_completed_at', 'total_onboarding_time_seconds'
        ])
    
    def _get_next_step(self, current_step):
        """Get the next step in the onboarding sequence."""
        steps = [choice[0] for choice in self.ONBOARDING_STEPS]
        try:
            current_index = steps.index(current_step)
            if current_index + 1 < len(steps):
                return steps[current_index + 1]
        except ValueError:
            pass
        return None
    
    @property
    def completion_percentage(self):
        """Calculate the completion percentage of onboarding."""
        total_steps = len(self.ONBOARDING_STEPS)
        completed = len(self.completed_steps)
        return (completed / total_steps) * 100
    
    @property
    def remaining_steps(self):
        """Get list of remaining onboarding steps."""
        all_steps = [choice[0] for choice in self.ONBOARDING_STEPS]
        return [step for step in all_steps if step not in self.completed_steps]
    
    def enable_demo_mode(self):
        """Enable demo mode for this user."""
        self.demo_mode_enabled = True
        self.save(update_fields=['demo_mode_enabled'])
    
    def disable_demo_mode(self):
        """Disable demo mode for this user."""
        self.demo_mode_enabled = False
        self.save(update_fields=['demo_mode_enabled'])
    
    def mark_demo_data_shown(self, demo_type, data_id=None):
        """Mark that specific demo data has been shown to the user."""
        if demo_type not in self.demo_data_shown:
            self.demo_data_shown[demo_type] = []
        
        if data_id and data_id not in self.demo_data_shown[demo_type]:
            self.demo_data_shown[demo_type].append(data_id)
        
        self.save(update_fields=['demo_data_shown'])


class DemoData(models.Model):
    """
    Model for storing demo/sample data to show new users during onboarding.
    """
    
    DEMO_TYPES = [
        ('plant_species', 'Sample Plant Species'),
        ('identification_request', 'Sample Identification Request'),
        ('care_instructions', 'Sample Care Instructions'),
        ('forum_topic', 'Sample Forum Topic'),
        ('forum_post', 'Sample Forum Post'),
        ('user_plant', 'Sample User Plant Collection'),
        ('care_reminder', 'Sample Care Reminder'),
    ]
    
    # UUID for secure references
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    # Demo data identification
    demo_type = models.CharField(
        max_length=30,
        choices=DEMO_TYPES,
        help_text="Type of demo data this represents"
    )
    
    title = models.CharField(
        max_length=200,
        help_text="Title/name for this demo data item"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of this demo data"
    )
    
    # Demo data content
    data_content = models.JSONField(
        help_text="The actual demo data content as JSON"
    )
    
    # Display settings
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Order in which to display this demo data"
    )
    
    is_featured = models.BooleanField(
        default=False,
        help_text="Is this featured demo data?"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Is this demo data currently active?"
    )
    
    # Targeting
    target_onboarding_step = models.CharField(
        max_length=30,
        choices=OnboardingProgress.ONBOARDING_STEPS,
        blank=True,
        help_text="Which onboarding step this demo data is relevant for"
    )
    
    target_user_types = models.JSONField(
        default=list,
        help_text="Types of users this demo data is most relevant for"
    )
    
    # Visual elements
    image_url = models.URLField(
        blank=True,
        help_text="Optional image URL for this demo data"
    )
    
    icon_class = models.CharField(
        max_length=50,
        blank=True,
        help_text="CSS icon class for this demo data"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_demo_data',
        help_text="User who created this demo data"
    )
    
    # Analytics
    view_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this demo data has been viewed"
    )
    
    interaction_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times users have interacted with this demo data"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['demo_type', 'display_order', 'title']
        indexes = [
            models.Index(fields=['demo_type', 'is_active']),
            models.Index(fields=['target_onboarding_step']),
            models.Index(fields=['is_featured', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.get_demo_type_display()}: {self.title}"
    
    def increment_view_count(self):
        """Increment the view count for this demo data."""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def increment_interaction_count(self):
        """Increment the interaction count for this demo data."""
        self.interaction_count += 1
        self.save(update_fields=['interaction_count'])
    
    @classmethod
    def get_for_onboarding_step(cls, step_name, limit=None):
        """Get demo data relevant for a specific onboarding step."""
        queryset = cls.objects.filter(
            target_onboarding_step=step_name,
            is_active=True
        ).order_by('display_order', 'title')
        
        if limit:
            queryset = queryset[:limit]
        
        return queryset
    
    @classmethod
    def get_featured(cls, demo_type=None, limit=None):
        """Get featured demo data, optionally filtered by type."""
        queryset = cls.objects.filter(
            is_featured=True,
            is_active=True
        ).order_by('display_order', 'title')
        
        if demo_type:
            queryset = queryset.filter(demo_type=demo_type)
        
        if limit:
            queryset = queryset[:limit]
        
        return queryset


class OnboardingAnalytics(models.Model):
    """
    Model for tracking onboarding analytics and user behavior.
    """
    
    ACTION_TYPES = [
        ('step_started', 'Onboarding Step Started'),
        ('step_completed', 'Onboarding Step Completed'),
        ('step_skipped', 'Onboarding Step Skipped'),
        ('demo_viewed', 'Demo Data Viewed'),
        ('demo_interacted', 'Demo Data Interacted With'),
        ('help_requested', 'Help Requested'),
        ('onboarding_abandoned', 'Onboarding Abandoned'),
        ('onboarding_completed', 'Onboarding Completed'),
    ]
    
    # Link to user and onboarding progress
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='onboarding_analytics'
    )
    
    onboarding_progress = models.ForeignKey(
        OnboardingProgress,
        on_delete=models.CASCADE,
        related_name='analytics_events'
    )
    
    # Event details
    action_type = models.CharField(
        max_length=30,
        choices=ACTION_TYPES,
        help_text="Type of action that occurred"
    )
    
    step_name = models.CharField(
        max_length=30,
        blank=True,
        help_text="Onboarding step related to this action"
    )
    
    # Event data
    event_data = models.JSONField(
        default=dict,
        help_text="Additional data about the event"
    )
    
    # Context
    page_url = models.URLField(
        blank=True,
        help_text="URL where the action occurred"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string"
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the user"
    )
    
    # Timing
    time_spent_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Time spent on this action/step"
    )
    
    session_duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total session duration when this action occurred"
    )
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action_type', '-created_at']),
            models.Index(fields=['onboarding_progress', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_action_type_display()}"
    
    @classmethod
    def log_event(cls, user, action_type, step_name=None, event_data=None, **kwargs):
        """Log an onboarding analytics event."""
        try:
            onboarding_progress = user.onboarding_progress
        except OnboardingProgress.DoesNotExist:
            # Create onboarding progress if it doesn't exist
            onboarding_progress = OnboardingProgress.objects.create(user=user)
        
        return cls.objects.create(
            user=user,
            onboarding_progress=onboarding_progress,
            action_type=action_type,
            step_name=step_name or '',
            event_data=event_data or {},
            **kwargs
        )