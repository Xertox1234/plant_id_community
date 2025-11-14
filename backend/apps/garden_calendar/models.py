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

from .constants import (
    HEALTH_STATUS_CHOICES,
    HEALTH_STATUS_DEFAULT,
    CARE_TASK_TYPES,
    CARE_TASK_PRIORITY,
)

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


# =============================================================================
# Garden Planner Models (Phase 1 - Nov 2025)
# =============================================================================


class GrowingZone(models.Model):
    """
    Reference model for USDA Hardiness Zones with detailed climate data.
    Used for plant recommendations and care scheduling.
    """

    zone_code = models.CharField(
        max_length=5,
        unique=True,
        help_text="USDA zone code (e.g., '7a', '7b')"
    )

    temp_min = models.SmallIntegerField(
        help_text="Minimum average temperature (Fahrenheit)"
    )

    temp_max = models.SmallIntegerField(
        help_text="Maximum average temperature (Fahrenheit)"
    )

    description = models.TextField(
        blank=True,
        help_text="Description of climate characteristics"
    )

    first_frost_date = models.CharField(
        max_length=10,
        blank=True,
        help_text="Average first frost date (MM-DD format)"
    )

    last_frost_date = models.CharField(
        max_length=10,
        blank=True,
        help_text="Average last frost date (MM-DD format)"
    )

    growing_season_days = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Average growing season length in days"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['zone_code']
        verbose_name = 'Growing Zone'
        verbose_name_plural = 'Growing Zones'

    def __str__(self):
        return f"Zone {self.zone_code} ({self.temp_min}°F to {self.temp_max}°F)"


class GardenBed(models.Model):
    """
    Model representing a physical garden bed or growing area.
    """

    BED_TYPES = [
        ('raised', 'Raised Bed'),
        ('in_ground', 'In-Ground Bed'),
        ('container', 'Container Garden'),
        ('greenhouse', 'Greenhouse'),
        ('indoor', 'Indoor Growing'),
        ('hydroponic', 'Hydroponic System'),
        ('other', 'Other'),
    ]

    SUN_EXPOSURE = [
        ('full_sun', 'Full Sun (6+ hours)'),
        ('partial_sun', 'Partial Sun (4-6 hours)'),
        ('partial_shade', 'Partial Shade (2-4 hours)'),
        ('full_shade', 'Full Shade (<2 hours)'),
    ]

    # Primary Key
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        primary_key=True,
        help_text="Unique identifier for secure references"
    )

    # Ownership
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='garden_beds',
        help_text="User who owns this garden bed"
    )

    # Basic Information
    name = models.CharField(
        max_length=200,
        help_text="Name of this garden bed"
    )

    description = models.TextField(
        blank=True,
        help_text="Detailed description of this bed"
    )

    bed_type = models.CharField(
        max_length=20,
        choices=BED_TYPES,
        default='raised',
        help_text="Type of garden bed"
    )

    # Dimensions (in inches for precision)
    length_inches = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Length in inches"
    )

    width_inches = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Width in inches"
    )

    depth_inches = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Depth/height in inches"
    )

    # Layout Data (for visual canvas designer)
    layout_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON data for plant positions on canvas (x, y coordinates)"
    )

    # Location and Climate
    location_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Location description (e.g., 'Backyard', 'Front Porch')"
    )

    sun_exposure = models.CharField(
        max_length=20,
        choices=SUN_EXPOSURE,
        blank=True,
        help_text="Daily sun exposure"
    )

    hardiness_zone = models.CharField(
        max_length=5,
        blank=True,
        help_text="USDA Hardiness Zone"
    )

    # Soil Information
    soil_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Soil type (e.g., 'Clay', 'Sandy', 'Loam')"
    )

    soil_ph = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(14)],
        help_text="Soil pH level (0-14)"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Is this bed currently in use?"
    )

    notes = models.TextField(
        blank=True,
        help_text="General notes about this bed"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Garden Bed'
        verbose_name_plural = 'Garden Beds'
        indexes = [
            models.Index(fields=['owner', '-updated_at']),
            models.Index(fields=['owner', 'is_active']),
            models.Index(fields=['hardiness_zone']),
        ]

    def __str__(self):
        return f"{self.name} ({self.owner.username})"

    @property
    def area_square_inches(self):
        """Calculate bed area in square inches."""
        if self.length_inches and self.width_inches:
            return self.length_inches * self.width_inches
        return None

    @property
    def area_square_feet(self):
        """Calculate bed area in square feet."""
        area_inches = self.area_square_inches
        if area_inches:
            return round(area_inches / 144, 2)  # 144 sq inches = 1 sq foot
        return None

    @property
    def volume_cubic_inches(self):
        """Calculate bed volume in cubic inches."""
        if self.length_inches and self.width_inches and self.depth_inches:
            return self.length_inches * self.width_inches * self.depth_inches
        return None

    @property
    def plant_count(self):
        """Get number of plants in this bed."""
        return self.plants.filter(is_active=True).count()

    @property
    def utilization_rate(self):
        """
        Calculate bed utilization (0.0 to 1.0).
        Based on number of plants relative to area.
        Assumes 1 plant per square foot for standard spacing.
        """
        area = self.area_square_feet
        if not area or area == 0:
            return None

        plant_count = self.plant_count
        # 1 plant per square foot = 100% utilization
        utilization = plant_count / area
        return min(utilization, 1.0)  # Cap at 100%


class Plant(models.Model):
    """
    Model representing an individual plant instance in a garden bed.
    """

    GROWTH_STAGES = [
        ('seed', 'Seed'),
        ('germination', 'Germination'),
        ('seedling', 'Seedling'),
        ('vegetative', 'Vegetative Growth'),
        ('budding', 'Budding'),
        ('flowering', 'Flowering'),
        ('fruiting', 'Fruiting/Producing'),
        ('harvest', 'Harvest Ready'),
        ('dormant', 'Dormant'),
        ('declining', 'Declining'),
    ]

    # Primary Key
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        primary_key=True,
        help_text="Unique identifier for secure references"
    )

    # Relationships
    garden_bed = models.ForeignKey(
        GardenBed,
        on_delete=models.CASCADE,
        related_name='plants',
        help_text="Garden bed this plant is in"
    )

    plant_species = models.ForeignKey(
        'plant_identification.PlantSpecies',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='garden_instances',
        help_text="Link to identified plant species (optional)"
    )

    # Plant Identification
    common_name = models.CharField(
        max_length=200,
        help_text="Common name of plant"
    )

    scientific_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Scientific name (if known)"
    )

    variety = models.CharField(
        max_length=200,
        blank=True,
        help_text="Specific variety or cultivar"
    )

    # Planting Information
    planted_date = models.DateField(
        help_text="Date this plant was planted/sown"
    )

    source = models.CharField(
        max_length=200,
        blank=True,
        help_text="Where plant came from (nursery, seed packet, gift, etc.)"
    )

    # Position in Bed
    position_x = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="X coordinate on canvas (for visual layout)"
    )

    position_y = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Y coordinate on canvas (for visual layout)"
    )

    # Health and Growth
    health_status = models.CharField(
        max_length=20,
        choices=HEALTH_STATUS_CHOICES,
        default=HEALTH_STATUS_DEFAULT,
        help_text="Current health status"
    )

    growth_stage = models.CharField(
        max_length=20,
        choices=GROWTH_STAGES,
        blank=True,
        help_text="Current growth stage"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Is this plant still growing/alive?"
    )

    removed_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date plant was removed/died"
    )

    removal_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text="Why plant was removed (harvested, died, etc.)"
    )

    # Notes
    notes = models.TextField(
        blank=True,
        help_text="General notes about this plant"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['garden_bed', '-planted_date']
        verbose_name = 'Plant'
        verbose_name_plural = 'Plants'
        indexes = [
            models.Index(fields=['garden_bed', '-planted_date']),
            models.Index(fields=['garden_bed', 'is_active']),
            models.Index(fields=['health_status']),
            models.Index(fields=['common_name']),
        ]

    def __str__(self):
        return f"{self.common_name} in {self.garden_bed.name}"

    @property
    def days_since_planted(self):
        """Calculate days since planting."""
        from django.utils import timezone
        today = timezone.now().date()
        return (today - self.planted_date).days

    @property
    def age_display(self):
        """Human-readable age display."""
        days = self.days_since_planted
        if days < 30:
            return f"{days} days"
        elif days < 365:
            weeks = days // 7
            return f"{weeks} weeks"
        else:
            years = days // 365
            months = (days % 365) // 30
            if months > 0:
                return f"{years}y {months}m"
            return f"{years} year{'s' if years > 1 else ''}"

    @property
    def pending_care_tasks_count(self):
        """Count of pending care tasks."""
        return self.care_tasks.filter(
            completed=False,
            skipped=False
        ).count()


class PlantImage(models.Model):
    """
    Model for storing multiple images per plant to track growth progress.
    """

    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        related_name='images',
        help_text="Plant this image belongs to"
    )

    image = models.ImageField(
        upload_to='garden_plants/%Y/%m/',
        help_text="Plant photograph"
    )

    caption = models.CharField(
        max_length=200,
        blank=True,
        help_text="Image caption/description"
    )

    taken_date = models.DateField(
        auto_now_add=True,
        help_text="Date photo was taken"
    )

    is_primary = models.BooleanField(
        default=False,
        help_text="Is this the primary/featured image?"
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-taken_date']
        verbose_name = 'Plant Image'
        verbose_name_plural = 'Plant Images'

    def __str__(self):
        return f"Image of {self.plant.common_name} - {self.taken_date}"


class CareTask(models.Model):
    """
    Model for care reminders and tasks for individual plants.
    """

    # Primary Key
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        primary_key=True,
        help_text="Unique identifier for secure references"
    )

    # Relationships
    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        related_name='care_tasks',
        help_text="Plant this task is for"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_care_tasks',
        help_text="User who created this task"
    )

    # Task Details
    task_type = models.CharField(
        max_length=20,
        choices=CARE_TASK_TYPES,
        help_text="Type of care task"
    )

    custom_task_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Custom task name (if task_type='custom')"
    )

    title = models.CharField(
        max_length=200,
        help_text="Task title/description"
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional notes or instructions"
    )

    priority = models.CharField(
        max_length=10,
        choices=CARE_TASK_PRIORITY,
        default='medium',
        help_text="Task priority level"
    )

    # Scheduling
    scheduled_date = models.DateTimeField(
        help_text="When this task should be done"
    )

    is_recurring = models.BooleanField(
        default=False,
        help_text="Does this task repeat?"
    )

    recurrence_interval_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="How often to repeat (in days)"
    )

    recurrence_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="When to stop recurring (optional)"
    )

    # Completion Status
    completed = models.BooleanField(
        default=False,
        help_text="Has this task been completed?"
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When task was completed"
    )

    completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_care_tasks',
        help_text="User who completed this task"
    )

    # Skip Status
    skipped = models.BooleanField(
        default=False,
        help_text="Was this task skipped?"
    )

    skip_reason = models.TextField(
        blank=True,
        help_text="Why task was skipped"
    )

    skipped_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When task was skipped"
    )

    # Notification
    notification_sent = models.BooleanField(
        default=False,
        help_text="Has notification been sent?"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scheduled_date']
        verbose_name = 'Care Task'
        verbose_name_plural = 'Care Tasks'
        indexes = [
            models.Index(fields=['plant', 'scheduled_date']),
            models.Index(fields=['created_by', 'completed', 'skipped']),
            models.Index(fields=['task_type', 'scheduled_date']),
            models.Index(fields=['scheduled_date', 'completed']),
        ]

    def __str__(self):
        return f"{self.get_task_type_display()} - {self.plant.common_name} ({self.scheduled_date.strftime('%Y-%m-%d')})"

    @property
    def is_overdue(self):
        """Check if task is past due."""
        from django.utils import timezone
        return (
            not self.completed and
            not self.skipped and
            self.scheduled_date < timezone.now()
        )

    @property
    def is_pending(self):
        """Check if task is still pending."""
        return not self.completed and not self.skipped

    def mark_complete(self, user):
        """Mark task as completed."""
        from django.utils import timezone
        self.completed = True
        self.completed_at = timezone.now()
        self.completed_by = user
        self.save()

        # Create next occurrence if recurring
        if self.is_recurring and self.recurrence_interval_days:
            self._create_next_occurrence()

    def mark_skip(self, user, reason=''):
        """Mark task as skipped."""
        from django.utils import timezone
        self.skipped = True
        self.skip_reason = reason
        self.skipped_at = timezone.now()
        self.save()

    def _create_next_occurrence(self):
        """Create next recurring task instance."""
        from datetime import timedelta
        from django.utils import timezone

        # Check if we've reached end date
        if self.recurrence_end_date:
            next_date = self.scheduled_date + timedelta(days=self.recurrence_interval_days)
            if next_date.date() > self.recurrence_end_date:
                return  # Stop recurring

        # Create new task instance
        CareTask.objects.create(
            plant=self.plant,
            created_by=self.created_by,
            task_type=self.task_type,
            custom_task_name=self.custom_task_name,
            title=self.title,
            notes=self.notes,
            priority=self.priority,
            scheduled_date=self.scheduled_date + timedelta(days=self.recurrence_interval_days),
            is_recurring=True,
            recurrence_interval_days=self.recurrence_interval_days,
            recurrence_end_date=self.recurrence_end_date,
        )


class CareLog(models.Model):
    """
    Model for logging care activities and observations for plants.
    """

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        primary_key=True,
        help_text="Unique identifier for secure references"
    )

    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        related_name='care_logs',
        help_text="Plant this log entry is for"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='plant_care_logs',
        help_text="User who created this log"
    )

    log_date = models.DateTimeField(
        auto_now_add=True,
        help_text="When this log entry was created"
    )

    activity_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of activity (watering, fertilizing, etc.)"
    )

    notes = models.TextField(
        blank=True,
        help_text="Log entry content/observations"
    )

    # Plant health tracking
    plant_health_before = models.CharField(
        max_length=20,
        blank=True,
        choices=HEALTH_STATUS_CHOICES,
        help_text="Plant health status before this care activity"
    )

    plant_health_after = models.CharField(
        max_length=20,
        blank=True,
        choices=HEALTH_STATUS_CHOICES,
        help_text="Plant health status after this care activity"
    )

    # Activity metrics
    hours_spent = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Hours spent on this activity"
    )

    materials_used = models.TextField(
        blank=True,
        help_text="Materials or products used"
    )

    cost = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost of materials/service"
    )

    # Weather conditions
    weather_conditions = models.TextField(
        blank=True,
        help_text="Weather conditions during activity"
    )

    # Optional metrics (legacy fields - kept for backward compatibility)
    temperature = models.SmallIntegerField(
        null=True,
        blank=True,
        help_text="Temperature at time of log (Fahrenheit)"
    )

    humidity = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Humidity percentage"
    )

    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags for categorizing logs"
    )

    class Meta:
        ordering = ['-log_date']
        verbose_name = 'Care Log Entry'
        verbose_name_plural = 'Care Log Entries'
        indexes = [
            models.Index(fields=['plant', '-log_date']),
            models.Index(fields=['user', '-log_date']),
        ]

    def __str__(self):
        return f"Log for {self.plant.common_name} - {self.log_date.strftime('%Y-%m-%d')}"


class Harvest(models.Model):
    """
    Model for tracking harvests from plants.
    """

    HARVEST_UNITS = [
        ('count', 'Count (individual items)'),
        ('lb', 'Pounds'),
        ('oz', 'Ounces'),
        ('kg', 'Kilograms'),
        ('g', 'Grams'),
        ('bunch', 'Bunches'),
        ('basket', 'Baskets'),
    ]

    plant = models.ForeignKey(
        Plant,
        on_delete=models.CASCADE,
        related_name='harvests',
        help_text="Plant that was harvested"
    )

    harvest_date = models.DateField(
        help_text="Date of harvest"
    )

    quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Quantity harvested"
    )

    unit = models.CharField(
        max_length=10,
        choices=HARVEST_UNITS,
        default='count',
        help_text="Unit of measurement"
    )

    quality_rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Quality rating (1-5 stars)"
    )

    notes = models.TextField(
        blank=True,
        help_text="Notes about this harvest"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-harvest_date']
        verbose_name = 'Harvest'
        verbose_name_plural = 'Harvests'
        indexes = [
            models.Index(fields=['plant', '-harvest_date']),
        ]

    def __str__(self):
        return f"{self.quantity} {self.unit} from {self.plant.common_name} ({self.harvest_date})"

    @property
    def days_from_planting(self):
        """Calculate days from planting to harvest."""
        return (self.harvest_date - self.plant.planted_date).days