"""
Garden Calendar Models

This module contains models for community events, seasonal templates, 
weather alerts, and location-based calendar features.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

User = get_user_model()


class CommunityEvent(models.Model):
    """
    Model for community-shared calendar events like plant swaps, workshops, etc.
    """
    
    EVENT_TYPES = [
        ('plant_swap', 'Plant Swap'),
        ('workshop', 'Workshop/Class'),
        ('garden_tour', 'Garden Tour'),
        ('vendor_sale', 'Plant Sale/Vendor'),
        ('bulk_order', 'Group/Bulk Order'),
        ('meetup', 'General Meetup'),
        ('maintenance', 'Community Garden Maintenance'),
        ('harvest', 'Community Harvest'),
        ('other', 'Other Event'),
    ]
    
    PRIVACY_LEVELS = [
        ('public', 'Public - Anyone can see'),
        ('local', 'Local - People in same city/region'),
        ('zone', 'Zone - People in same hardiness zone'),
        ('friends', 'Friends - Only people I follow'),
        ('private', 'Private - Invitation only'),
    ]
    
    # Basic Event Information
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    organizer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='organized_events',
        help_text="User who created this event"
    )
    
    title = models.CharField(
        max_length=200,
        help_text="Event title/name"
    )
    
    description = models.TextField(
        help_text="Detailed event description"
    )
    
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPES,
        help_text="Type of community event"
    )
    
    # Date and Time
    start_datetime = models.DateTimeField(
        help_text="Event start date and time"
    )
    
    end_datetime = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Event end date and time (optional for short events)"
    )
    
    is_all_day = models.BooleanField(
        default=False,
        help_text="Is this an all-day event?"
    )
    
    # Location
    location_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Venue name or general location description"
    )
    
    address = models.TextField(
        blank=True,
        help_text="Full address (will be masked based on privacy settings)"
    )
    
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City for regional filtering"
    )
    
    hardiness_zone = models.CharField(
        max_length=5,
        blank=True,
        help_text="USDA Hardiness Zone for climate-relevant events"
    )
    
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude for precise location (optional)"
    )
    
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude for precise location (optional)"
    )
    
    # Privacy and Visibility
    privacy_level = models.CharField(
        max_length=10,
        choices=PRIVACY_LEVELS,
        default='local',
        help_text="Who can see this event"
    )
    
    max_attendees = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Maximum number of attendees (leave blank for unlimited)"
    )
    
    # Event Features
    requires_rsvp = models.BooleanField(
        default=False,
        help_text="Does this event require RSVP?"
    )
    
    is_recurring = models.BooleanField(
        default=False,
        help_text="Is this a recurring event?"
    )
    
    recurrence_rule = models.JSONField(
        blank=True,
        null=True,
        help_text="JSON data for recurring event rules (RRULE format)"
    )
    
    # Contact Information
    contact_email = models.EmailField(
        blank=True,
        help_text="Contact email for event questions"
    )
    
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Contact phone number (will be masked based on privacy)"
    )
    
    external_url = models.URLField(
        blank=True,
        help_text="External link for more information or registration"
    )
    
    # Weather Dependency
    weather_dependent = models.BooleanField(
        default=False,
        help_text="Should this event be canceled/postponed due to bad weather?"
    )
    
    weather_backup_plan = models.TextField(
        blank=True,
        help_text="What happens if weather is bad? (indoor venue, reschedule, etc.)"
    )
    
    # Forum Integration - using string reference for optional dependency
    forum_topic_id = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="ID of associated forum discussion topic (if forum enabled)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['start_datetime']
        verbose_name = 'Community Event'
        verbose_name_plural = 'Community Events'
        indexes = [
            models.Index(fields=['start_datetime', 'privacy_level']),
            models.Index(fields=['city', 'hardiness_zone']),
            models.Index(fields=['event_type', 'start_datetime']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.start_datetime.strftime('%Y-%m-%d')}"
    
    @property
    def duration_hours(self):
        """Calculate event duration in hours."""
        if self.end_datetime:
            delta = self.end_datetime - self.start_datetime
            return delta.total_seconds() / 3600
        return 1  # Default to 1 hour for events without end time
    
    @property
    def is_past(self):
        """Check if event has already occurred."""
        return self.start_datetime < timezone.now()
    
    @property
    def attendee_count(self):
        """Get current number of attendees."""
        return self.attendees.count()
    
    @property
    def spots_remaining(self):
        """Get number of spots remaining (if max_attendees is set)."""
        if self.max_attendees:
            return max(0, self.max_attendees - self.attendee_count)
        return None


class EventAttendee(models.Model):
    """
    Model to track event attendees/RSVPs.
    """
    
    RSVP_STATUS = [
        ('going', 'Going'),
        ('maybe', 'Maybe'),
        ('not_going', 'Not Going'),
        ('invited', 'Invited (No Response)'),
    ]
    
    event = models.ForeignKey(
        CommunityEvent,
        on_delete=models.CASCADE,
        related_name='attendees'
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='event_attendances'
    )
    
    status = models.CharField(
        max_length=10,
        choices=RSVP_STATUS,
        default='going'
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Optional notes from the attendee"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['event', 'user']
        verbose_name = 'Event Attendee'
        verbose_name_plural = 'Event Attendees'
    
    def __str__(self):
        return f"{self.user.username} - {self.event.title} ({self.status})"


class SeasonalTemplate(models.Model):
    """
    Model for zone-based seasonal task templates that automatically generate
    care reminders based on location and climate.
    """
    
    TASK_TYPES = [
        ('watering', 'Watering'),
        ('fertilizing', 'Fertilizing'),
        ('pruning', 'Pruning'),
        ('planting', 'Planting'),
        ('harvesting', 'Harvesting'),
        ('pest_control', 'Pest Control'),
        ('disease_prevention', 'Disease Prevention'),
        ('soil_preparation', 'Soil Preparation'),
        ('mulching', 'Mulching'),
        ('winterization', 'Winter Preparation'),
        ('spring_cleanup', 'Spring Cleanup'),
        ('inspection', 'Plant Inspection'),
        ('other', 'Other Task'),
    ]
    
    SEASONS = [
        ('spring', 'Spring'),
        ('summer', 'Summer'),
        ('fall', 'Fall/Autumn'),
        ('winter', 'Winter'),
    ]
    
    # Template Identification
    name = models.CharField(
        max_length=200,
        help_text="Template name (e.g., 'Spring Tomato Care - Zone 7')"
    )
    
    description = models.TextField(
        help_text="Detailed description of this seasonal template"
    )
    
    # Location and Climate
    hardiness_zones = models.JSONField(
        help_text="List of USDA zones this template applies to (e.g., ['7a', '7b', '8a'])"
    )
    
    season = models.CharField(
        max_length=10,
        choices=SEASONS,
        help_text="Primary season for this template"
    )
    
    # Task Details
    task_type = models.CharField(
        max_length=20,
        choices=TASK_TYPES,
        help_text="Type of gardening task"
    )
    
    plant_types = models.JSONField(
        blank=True,
        null=True,
        help_text="List of plant types this applies to (e.g., ['tomatoes', 'roses', 'succulents'])"
    )
    
    # Timing
    start_month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Month to start this task (1-12)"
    )
    
    end_month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        blank=True,
        null=True,
        help_text="Month to end this task (optional, for multi-month tasks)"
    )
    
    day_of_month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        blank=True,
        null=True,
        help_text="Specific day of month (optional, defaults to 1st)"
    )
    
    frequency_days = models.PositiveIntegerField(
        default=7,
        help_text="How often to repeat this task (in days)"
    )
    
    # Weather Conditions
    temperature_min = models.SmallIntegerField(
        blank=True,
        null=True,
        help_text="Minimum temperature (Fahrenheit) for this task"
    )
    
    temperature_max = models.SmallIntegerField(
        blank=True,
        null=True,
        help_text="Maximum temperature (Fahrenheit) for this task"
    )
    
    requires_no_frost = models.BooleanField(
        default=False,
        help_text="Should this task wait until frost danger has passed?"
    )
    
    requires_no_rain = models.BooleanField(
        default=False,
        help_text="Should this task be skipped during rainy weather?"
    )
    
    # Content
    instructions = models.TextField(
        help_text="Detailed instructions for this seasonal task"
    )
    
    tips = models.TextField(
        blank=True,
        help_text="Additional tips and advice"
    )
    
    # Priority and Visibility
    priority = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low Priority'),
            ('medium', 'Medium Priority'),
            ('high', 'High Priority'),
            ('critical', 'Critical/Time Sensitive'),
        ],
        default='medium'
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Is this template active and should generate tasks?"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_templates',
        help_text="User who created this template (optional for system templates)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['season', 'start_month', 'day_of_month', 'task_type']
        verbose_name = 'Seasonal Template'
        verbose_name_plural = 'Seasonal Templates'
        indexes = [
            models.Index(fields=['season', 'start_month']),
            models.Index(fields=['task_type', 'is_active']),
        ]
    
    def __str__(self):
        zones_str = ', '.join(self.hardiness_zones) if self.hardiness_zones else 'All Zones'
        return f"{self.name} ({zones_str}) - {self.get_season_display()}"
    
    @property
    def applicable_zones_display(self):
        """Get human-readable list of applicable zones."""
        if self.hardiness_zones:
            return ', '.join(sorted(self.hardiness_zones))
        return 'All Zones'


class WeatherAlert(models.Model):
    """
    Model for weather-based alerts and notifications that affect garden tasks.
    """
    
    ALERT_TYPES = [
        ('frost', 'Frost Warning'),
        ('freeze', 'Freeze Warning'),
        ('high_wind', 'High Wind Alert'),
        ('heavy_rain', 'Heavy Rain Alert'),
        ('drought', 'Drought Conditions'),
        ('heat_wave', 'Excessive Heat'),
        ('severe_weather', 'Severe Weather Warning'),
        ('good_conditions', 'Favorable Conditions'),
    ]
    
    SEVERITY_LEVELS = [
        ('info', 'Informational'),
        ('low', 'Low Impact'),
        ('medium', 'Medium Impact'),
        ('high', 'High Impact'),
        ('critical', 'Critical/Emergency'),
    ]
    
    # Alert Identification
    alert_type = models.CharField(
        max_length=20,
        choices=ALERT_TYPES,
        help_text="Type of weather alert"
    )
    
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_LEVELS,
        default='medium',
        help_text="Severity level of this alert"
    )
    
    # Location
    zip_code = models.CharField(
        max_length=10,
        help_text="ZIP code this alert applies to"
    )
    
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City name for display"
    )
    
    hardiness_zone = models.CharField(
        max_length=5,
        blank=True,
        help_text="USDA zone this alert applies to"
    )
    
    # Alert Details
    title = models.CharField(
        max_length=200,
        help_text="Alert title/headline"
    )
    
    message = models.TextField(
        help_text="Detailed alert message"
    )
    
    recommendations = models.TextField(
        blank=True,
        help_text="Recommended actions for gardeners"
    )
    
    # Timing
    start_datetime = models.DateTimeField(
        help_text="When the weather condition starts"
    )
    
    end_datetime = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the weather condition ends (if known)"
    )
    
    expires_at = models.DateTimeField(
        help_text="When this alert expires and should be removed"
    )
    
    # Weather Data
    temperature_low = models.SmallIntegerField(
        blank=True,
        null=True,
        help_text="Predicted low temperature (Fahrenheit)"
    )
    
    temperature_high = models.SmallIntegerField(
        blank=True,
        null=True,
        help_text="Predicted high temperature (Fahrenheit)"
    )
    
    wind_speed = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        help_text="Wind speed in MPH"
    )
    
    precipitation_chance = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        blank=True,
        null=True,
        help_text="Chance of precipitation (0-100%)"
    )
    
    precipitation_amount = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Expected precipitation in inches"
    )
    
    # System Fields
    is_active = models.BooleanField(
        default=True,
        help_text="Is this alert currently active?"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-severity', '-start_datetime']
        verbose_name = 'Weather Alert'
        verbose_name_plural = 'Weather Alerts'
        indexes = [
            models.Index(fields=['zip_code', 'is_active']),
            models.Index(fields=['start_datetime', 'end_datetime']),
            models.Index(fields=['alert_type', 'severity']),
        ]
    
    def __str__(self):
        location = self.city if self.city else self.zip_code
        return f"{self.get_alert_type_display()} - {location} ({self.start_datetime.strftime('%m/%d')})"
    
    @property
    def is_current(self):
        """Check if alert is currently in effect."""
        now = timezone.now()
        return (
            self.is_active and
            self.start_datetime <= now and
            (self.end_datetime is None or self.end_datetime >= now) and
            self.expires_at >= now
        )
    
    @property
    def color_code(self):
        """Get color code for UI display based on severity."""
        colors = {
            'info': '#3B82F6',      # Blue
            'low': '#10B981',       # Green  
            'medium': '#F59E0B',    # Amber
            'high': '#EF4444',      # Red
            'critical': '#7C2D12',  # Dark Red
        }
        return colors.get(self.severity, '#6B7280')  # Default Gray