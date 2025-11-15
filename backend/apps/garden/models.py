"""
Garden Planner Models

Provides comprehensive garden planning functionality including:
- Garden layouts with drag-and-drop plant positioning
- Care reminders with weather integration
- Task management for seasonal gardening activities
- Pest and disease tracking
- Garden journal with photos
- Plant care reference library
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Garden(models.Model):
    """
    User's garden with layout and metadata.

    Supports visual layout designer with JSON storage for plant positions.
    Can be private or shared publicly with the community.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gardens'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Dimensions stored as JSON: {width: int, height: int, unit: 'ft'|'m'}
    dimensions = models.JSONField(
        help_text="Garden dimensions in format: {width: 20, height: 10, unit: 'ft'}"
    )

    # Layout data for canvas designer: {plants: [{plantId, x, y}], gridSize: 12}
    layout_data = models.JSONField(
        default=dict,
        help_text="Plant positions and canvas metadata"
    )

    # Optional location for weather integration
    location = models.JSONField(
        null=True,
        blank=True,
        help_text="Location data: {lat: float, lng: float, city: str}"
    )

    climate_zone = models.CharField(
        max_length=20,
        blank=True,
        help_text="USDA hardiness zone (e.g., '7a', '9b')"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Visibility settings
    VISIBILITY_CHOICES = [
        ('private', 'Private'),
        ('public', 'Public'),
    ]
    visibility = models.CharField(
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default='private'
    )

    # Staff can feature gardens in community showcase
    featured = models.BooleanField(
        default=False,
        help_text="Featured in community garden gallery"
    )

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['visibility', 'featured']),
        ]
        verbose_name = 'Garden'
        verbose_name_plural = 'Gardens'

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class GardenPlant(models.Model):
    """
    Plant instance in a specific garden.

    Links to PlantSpecies for care information, stores position on canvas,
    and tracks health status for visual indicators.
    """
    garden = models.ForeignKey(
        Garden,
        on_delete=models.CASCADE,
        related_name='plants'
    )

    # Optional link to plant identification database
    plant_species = models.ForeignKey(
        'plant_identification.PlantSpecies',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='garden_planner_instances'
    )

    # Core identification (required even without species link)
    common_name = models.CharField(max_length=200)
    scientific_name = models.CharField(max_length=200, blank=True)

    planted_date = models.DateField()

    # Position on canvas: {x: int, y: int}
    position = models.JSONField(
        help_text="Position on canvas in format: {x: 5, y: 10}"
    )

    # Optional photo of this specific plant
    image = models.ImageField(
        upload_to='garden_plants/',
        null=True,
        blank=True
    )

    notes = models.TextField(
        blank=True,
        help_text="Personal notes about this plant"
    )

    # Health status for visual indicators
    HEALTH_STATUS_CHOICES = [
        ('healthy', 'Healthy'),
        ('needs_attention', 'Needs Attention'),
        ('diseased', 'Diseased'),
        ('dead', 'Dead'),
    ]
    health_status = models.CharField(
        max_length=20,
        choices=HEALTH_STATUS_CHOICES,
        default='healthy'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['garden', '-planted_date']
        verbose_name = 'Garden Plant'
        verbose_name_plural = 'Garden Plants'

    def __str__(self):
        return f"{self.common_name} in {self.garden.name}"


class CareReminder(models.Model):
    """
    Care task reminder for a specific plant.

    Supports recurring reminders with weather-aware scheduling.
    Syncs to Firebase for push notifications.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='garden_care_reminders'
    )

    garden_plant = models.ForeignKey(
        GardenPlant,
        on_delete=models.CASCADE,
        related_name='reminders'
    )

    # Reminder type
    REMINDER_TYPE_CHOICES = [
        ('watering', 'Watering'),
        ('fertilizing', 'Fertilizing'),
        ('pruning', 'Pruning'),
        ('repotting', 'Repotting'),
        ('pest_check', 'Pest Check'),
        ('custom', 'Custom'),
    ]
    reminder_type = models.CharField(
        max_length=20,
        choices=REMINDER_TYPE_CHOICES
    )

    custom_type_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom reminder type name (if type is 'custom')"
    )

    # Scheduling
    scheduled_date = models.DateTimeField()
    recurring = models.BooleanField(default=False)
    interval_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Days between recurring reminders"
    )

    # Completion tracking
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Skip tracking (e.g., weather-based)
    skipped = models.BooleanField(default=False)
    skip_reason = models.TextField(blank=True)

    notes = models.TextField(blank=True)

    # Notification tracking
    notification_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_date']
        indexes = [
            models.Index(fields=['user', 'scheduled_date', 'completed']),
            models.Index(fields=['notification_sent', 'scheduled_date']),
        ]
        verbose_name = 'Care Reminder'
        verbose_name_plural = 'Care Reminders'

    def __str__(self):
        return f"{self.get_reminder_type_display()} - {self.garden_plant.common_name}"


class Task(models.Model):
    """
    Seasonal gardening task.

    Can be garden-specific or general user tasks.
    Pre-populated seasonal templates available via API.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='garden_tasks'
    )

    garden = models.ForeignKey(
        Garden,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tasks',
        help_text="Optional: Link to specific garden"
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)

    # Completion tracking
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Categorization
    CATEGORY_CHOICES = [
        ('planting', 'Planting'),
        ('maintenance', 'Maintenance'),
        ('harvesting', 'Harvesting'),
        ('preparation', 'Preparation'),
        ('other', 'Other'),
    ]
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES
    )

    SEASON_CHOICES = [
        ('spring', 'Spring'),
        ('summer', 'Summer'),
        ('fall', 'Fall'),
        ('winter', 'Winter'),
        ('year_round', 'Year Round'),
    ]
    season = models.CharField(
        max_length=10,
        choices=SEASON_CHOICES,
        blank=True
    )

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-priority', 'due_date']
        verbose_name = 'Gardening Task'
        verbose_name_plural = 'Gardening Tasks'

    def __str__(self):
        return self.title


class PestIssue(models.Model):
    """
    Pest or disease tracking for a specific plant.

    Supports multiple images and AI-powered treatment recommendations.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pest_issues'
    )

    garden_plant = models.ForeignKey(
        GardenPlant,
        on_delete=models.CASCADE,
        related_name='pest_issues'
    )

    pest_type = models.CharField(
        max_length=200,
        help_text="Type of pest or disease"
    )
    description = models.TextField()
    identified_date = models.DateField(auto_now_add=True)

    # Severity tracking
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES
    )

    # Treatment tracking
    treatment = models.TextField(blank=True)
    treatment_date = models.DateField(null=True, blank=True)

    # Resolution tracking
    resolved = models.BooleanField(default=False)
    resolved_date = models.DateField(null=True, blank=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-identified_date']
        verbose_name = 'Pest Issue'
        verbose_name_plural = 'Pest Issues'

    def __str__(self):
        return f"{self.pest_type} on {self.garden_plant.common_name}"


class PestImage(models.Model):
    """Images for pest/disease documentation."""
    pest_issue = models.ForeignKey(
        PestIssue,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='pest_issues/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']
        verbose_name = 'Pest Image'
        verbose_name_plural = 'Pest Images'

    def __str__(self):
        return f"Image for {self.pest_issue.pest_type}"


class JournalEntry(models.Model):
    """
    Garden observation journal with photos and weather data.

    Can be garden-wide or plant-specific.
    Automatically captures weather snapshot for historical reference.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='journal_entries'
    )

    garden = models.ForeignKey(
        Garden,
        on_delete=models.CASCADE,
        related_name='journal_entries'
    )

    garden_plant = models.ForeignKey(
        GardenPlant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_entries',
        help_text="Optional: Link to specific plant"
    )

    title = models.CharField(max_length=200)
    content = models.TextField()
    date = models.DateField()

    # Weather data snapshot from OpenWeatherMap
    weather_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Weather snapshot: {temp, conditions, humidity, etc.}"
    )

    # Tags for organization
    tags = models.JSONField(
        default=list,
        help_text="List of tags for filtering entries"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Journal Entry'
        verbose_name_plural = 'Journal Entries'
        indexes = [
            models.Index(fields=['user', '-date']),
        ]

    def __str__(self):
        return f"{self.title} - {self.date}"


class JournalImage(models.Model):
    """Images for journal entries."""
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='journal_entries/')
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']
        verbose_name = 'Journal Image'
        verbose_name_plural = 'Journal Images'

    def __str__(self):
        return f"Image for {self.journal_entry.title}"


class PlantCareLibrary(models.Model):
    """
    Shared plant care reference data.

    Provides care instructions, compatibility, and frequency defaults.
    Used to populate care plans and reminders automatically.
    """
    scientific_name = models.CharField(max_length=200, unique=True)
    common_names = models.JSONField(
        default=list,
        help_text="List of common names"
    )
    family = models.CharField(max_length=100, blank=True)

    # Light requirements
    SUNLIGHT_CHOICES = [
        ('full_sun', 'Full Sun'),
        ('partial_shade', 'Partial Shade'),
        ('full_shade', 'Full Shade'),
    ]
    sunlight = models.CharField(
        max_length=20,
        choices=SUNLIGHT_CHOICES
    )

    # Water requirements
    WATER_NEEDS_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    water_needs = models.CharField(
        max_length=20,
        choices=WATER_NEEDS_CHOICES
    )

    soil_type = models.CharField(max_length=200, blank=True)

    # Hardiness zones as JSON list: ["5a", "9b"]
    hardiness_zones = models.JSONField(
        default=list,
        help_text="USDA hardiness zones (e.g., ['5a', '9b'])"
    )

    # Care instructions
    care_instructions = models.TextField(blank=True)

    # Frequency defaults (in days)
    watering_frequency_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )
    fertilizing_frequency_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )
    pruning_frequency_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )

    # Companion planting
    companion_plants = models.JSONField(
        default=list,
        help_text="List of compatible plant species"
    )
    enemy_plants = models.JSONField(
        default=list,
        help_text="List of incompatible plant species"
    )

    # Common issues
    common_pests = models.JSONField(
        default=list,
        help_text="List of common pests for this plant"
    )
    common_diseases = models.JSONField(
        default=list,
        help_text="List of common diseases"
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scientific_name']
        verbose_name = 'Plant Care Library Entry'
        verbose_name_plural = 'Plant Care Library Entries'

    def __str__(self):
        return self.scientific_name
