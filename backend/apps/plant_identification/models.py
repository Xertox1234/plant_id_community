"""
Plant identification models for the Plant Community application.

This module contains models for plant data, identification requests, and results.
"""

from django.db import models
from django.conf import settings
from django.urls import reverse
from imagekit.models import ImageSpecField, ProcessedImageField
from imagekit.processors import ResizeToFill, ResizeToFit
from taggit.managers import TaggableManager
from apps.core.validators import validate_plant_identification_image, validate_image_file
import uuid

# Wagtail models will be appended at the end to avoid circular imports


class PlantSpecies(models.Model):
    """
    Model representing a plant species with botanical information.
    """
    
    # UUID for secure references (prevents IDOR attacks)
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    # Basic Information
    scientific_name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Scientific binomial name (e.g., Rosa damascena)"
    )
    
    common_names = models.TextField(
        blank=True,
        help_text="Common names separated by commas"
    )
    
    family = models.CharField(
        max_length=100,
        blank=True,
        help_text="Plant family name"
    )
    
    genus = models.CharField(
        max_length=100,
        blank=True,
        help_text="Plant genus"
    )
    
    species = models.CharField(
        max_length=100,
        blank=True,
        help_text="Species name"
    )
    
    # External API IDs
    trefle_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Trefle API plant ID"
    )
    
    plantnet_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="PlantNet API plant ID"
    )
    
    # Plant Characteristics
    plant_type = models.CharField(
        max_length=50,
        choices=[
            ('tree', 'Tree'),
            ('shrub', 'Shrub'),
            ('herb', 'Herb'),
            ('grass', 'Grass'),
            ('fern', 'Fern'),
            ('moss', 'Moss'),
            ('succulent', 'Succulent'),
            ('vine', 'Vine'),
            ('annual', 'Annual'),
            ('perennial', 'Perennial'),
            ('biennial', 'Biennial'),
        ],
        blank=True
    )
    
    growth_habit = models.CharField(
        max_length=100,
        blank=True,
        help_text="How the plant grows (e.g., climbing, spreading, upright)"
    )
    
    mature_height_min = models.FloatField(
        null=True,
        blank=True,
        help_text="Minimum mature height in meters"
    )
    
    mature_height_max = models.FloatField(
        null=True,
        blank=True,
        help_text="Maximum mature height in meters"
    )
    
    # Care Information
    light_requirements = models.CharField(
        max_length=20,
        choices=[
            ('full_sun', 'Full Sun'),
            ('partial_sun', 'Partial Sun'),
            ('partial_shade', 'Partial Shade'),
            ('full_shade', 'Full Shade'),
        ],
        blank=True
    )
    
    water_requirements = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('moderate', 'Moderate'),
            ('high', 'High'),
        ],
        blank=True
    )
    
    soil_ph_min = models.FloatField(
        null=True,
        blank=True,
        help_text="Minimum soil pH tolerance"
    )
    
    soil_ph_max = models.FloatField(
        null=True,
        blank=True,
        help_text="Maximum soil pH tolerance"
    )
    
    hardiness_zone_min = models.IntegerField(
        null=True,
        blank=True,
        help_text="Minimum USDA hardiness zone"
    )
    
    hardiness_zone_max = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum USDA hardiness zone"
    )
    
    # Additional Information
    description = models.TextField(
        blank=True,
        help_text="General description of the plant"
    )
    
    native_regions = models.TextField(
        blank=True,
        help_text="Native regions and countries"
    )
    
    bloom_time = models.CharField(
        max_length=100,
        blank=True,
        help_text="When the plant typically blooms"
    )
    
    flower_color = models.CharField(
        max_length=100,
        blank=True,
        help_text="Typical flower colors"
    )
    
    # Images
    primary_image = models.ImageField(
        upload_to='plants/species/',
        null=True,
        blank=True,
        help_text="Primary image of the plant"
    )
    
    primary_image_thumbnail = ImageSpecField(
        source='primary_image',
        processors=[ResizeToFill(300, 300)],
        format='JPEG',
        options={'quality': 85}
    )
    
    # Tags and Classification
    tags = TaggableManager(
        blank=True,
        help_text="Tags for categorizing plants (e.g., medicinal, edible, toxic)"
    )
    
    # Status and Metadata
    is_verified = models.BooleanField(
        default=False,
        help_text="Has this species been verified by an expert?"
    )
    
    verification_source = models.CharField(
        max_length=200,
        blank=True,
        help_text="Source of verification (e.g., botanist name, institution)"
    )
    
    # Auto-storage tracking (NEW: for ≥50% confidence plant IDs)
    auto_stored = models.BooleanField(
        default=False,
        help_text="Was this species auto-stored from a high-confidence identification (≥50%)?"
    )
    
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Highest confidence score from identifications that created this species"
    )
    
    identification_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this species has been identified"
    )
    
    api_source = models.CharField(
        max_length=50,
        choices=[
            ('manual', 'Manual Entry'),
            ('plantnet', 'PlantNet API'),
            ('trefle', 'Trefle API'),
            ('combined', 'Combined APIs'),
            ('community', 'Community Contributed'),
        ],
        default='manual',
        help_text="Primary source where this species data came from"
    )
    
    community_confirmed = models.BooleanField(
        default=False,
        help_text="Has this species been confirmed by community voting?"
    )
    
    expert_reviewed = models.BooleanField(
        default=False,
        help_text="Has this species been reviewed by a plant expert?"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['scientific_name']
        verbose_name = 'Plant Species'
        verbose_name_plural = 'Plant Species'
    
    def __str__(self):
        return self.scientific_name
    
    def get_absolute_url(self):
        return reverse('plant_identification:species_detail', kwargs={'pk': self.pk})
    
    @property
    def display_name(self):
        """Return the best display name for the species."""
        if self.common_names:
            first_common = self.common_names.split(',')[0].strip()
            return f"{first_common} ({self.scientific_name})"
        return self.scientific_name
    
    @property
    def common_names_list(self):
        """Return common names as a list."""
        if self.common_names:
            return [name.strip() for name in self.common_names.split(',')]
        return []
    
    def update_confidence_score(self, new_confidence: float):
        """Update the confidence score if this is higher than the current one."""
        if self.confidence_score is None or new_confidence > self.confidence_score:
            self.confidence_score = new_confidence
    
    def increment_identification_count(self):
        """Increment the count of identifications for this species."""
        self.identification_count += 1
        
    @staticmethod
    def should_auto_store(confidence: float) -> bool:
        """Static method to check if a confidence score qualifies for auto-storage."""
        return confidence >= 0.5


class PlantIdentificationRequest(models.Model):
    """
    Model representing a user's request to identify a plant.
    """
    
    # Request ID for tracking
    request_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique identifier for this identification request"
    )
    
    # User who made the request
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='plant_identification_requests'
    )
    
    # Plant Images
    image_1 = ProcessedImageField(
        upload_to='plants/identifications/',
        processors=[ResizeToFit(1200, 1200)],
        format='JPEG',
        options={'quality': 90},
        validators=[validate_plant_identification_image],
        help_text="Primary image of the plant"
    )
    
    image_1_thumbnail = ImageSpecField(
        source='image_1',
        processors=[ResizeToFill(300, 300)],
        format='JPEG',
        options={'quality': 85}
    )
    
    image_2 = ProcessedImageField(
        upload_to='plants/identifications/',
        processors=[ResizeToFit(1200, 1200)],
        format='JPEG',
        options={'quality': 90},
        validators=[validate_plant_identification_image],
        null=True,
        blank=True,
        help_text="Optional second image"
    )
    
    image_2_thumbnail = ImageSpecField(
        source='image_2',
        processors=[ResizeToFill(300, 300)],
        format='JPEG',
        options={'quality': 85}
    )
    
    image_3 = ProcessedImageField(
        upload_to='plants/identifications/',
        processors=[ResizeToFit(1200, 1200)],
        format='JPEG',
        options={'quality': 90},
        validators=[validate_plant_identification_image],
        null=True,
        blank=True,
        help_text="Optional third image"
    )
    
    image_3_thumbnail = ImageSpecField(
        source='image_3',
        processors=[ResizeToFill(300, 300)],
        format='JPEG',
        options={'quality': 85}
    )
    
    # Location and Context
    location = models.CharField(
        max_length=200,
        blank=True,
        help_text="Where was this plant found?"
    )
    
    latitude = models.FloatField(
        null=True,
        blank=True,
        help_text="GPS latitude"
    )
    
    longitude = models.FloatField(
        null=True,
        blank=True,
        help_text="GPS longitude"
    )
    
    # User Description
    description = models.TextField(
        blank=True,
        help_text="User's description of the plant"
    )
    
    plant_size = models.CharField(
        max_length=50,
        choices=[
            ('small', 'Small (< 30cm)'),
            ('medium', 'Medium (30cm - 1m)'),
            ('large', 'Large (1m - 3m)'),
            ('very_large', 'Very Large (> 3m)'),
        ],
        blank=True,
        help_text="Approximate size of the plant"
    )
    
    habitat = models.CharField(
        max_length=100,
        blank=True,
        help_text="Where was the plant growing? (e.g., garden, forest, field)"
    )
    
    # Request Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Identification'),
            ('processing', 'Processing with AI'),
            ('identified', 'Identified'),
            ('needs_help', 'Needs Community Help'),
            ('failed', 'Identification Failed'),
        ],
        default='pending'
    )
    
    # AI Processing
    processed_by_ai = models.BooleanField(
        default=False,
        help_text="Has this been processed by AI identification?"
    )
    
    ai_processing_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When was this processed by AI?"
    )
    
    # Community Collection Assignment
    assigned_to_collection = models.ForeignKey(
        'users.UserPlantCollection',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='identification_requests',
        help_text="User's collection this plant was added to"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Plant ID Request #{self.request_id.hex[:8]} by {self.user.username}"
    
    def get_absolute_url(self):
        return reverse('plant_identification:request_detail', kwargs={'request_id': self.request_id})
    
    @property
    def images(self):
        """Return a list of all uploaded images."""
        images = [self.image_1]
        if self.image_2:
            images.append(self.image_2)
        if self.image_3:
            images.append(self.image_3)
        return images
    
    @property
    def image_thumbnails(self):
        """Return a list of all image thumbnails."""
        thumbnails = [self.image_1_thumbnail]
        if self.image_2_thumbnail:
            thumbnails.append(self.image_2_thumbnail)
        if self.image_3_thumbnail:
            thumbnails.append(self.image_3_thumbnail)
        return thumbnails


class PlantIdentificationResult(models.Model):
    """
    Model representing an identification result for a plant request.
    """
    
    # UUID for secure references (prevents IDOR attacks)
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    # Link to the identification request
    request = models.ForeignKey(
        PlantIdentificationRequest,
        on_delete=models.CASCADE,
        related_name='identification_results'
    )
    
    # Identified species (if matched to database)
    identified_species = models.ForeignKey(
        PlantSpecies,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='identification_results'
    )
    
    # Alternative identification (if species not in database)
    suggested_scientific_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Suggested scientific name if not in our database"
    )
    
    suggested_common_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Suggested common name"
    )
    
    # Confidence and Source
    confidence_score = models.FloatField(
        help_text="Confidence score (0.0 to 1.0)"
    )
    
    identification_source = models.CharField(
        max_length=20,
        choices=[
            ('ai_trefle', 'AI - Trefle API'),
            ('ai_plantnet', 'AI - PlantNet API'),
            ('ai_combined', 'AI - Combined APIs'),
            ('community', 'Community Identification'),
            ('expert', 'Expert Identification'),
            ('user_manual', 'Manual User Entry'),
        ]
    )
    
    # User who provided this identification (for community/expert IDs)
    identified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='plant_identifications_given'
    )
    
    # Additional Information
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this identification"
    )
    
    # External API Response Data
    api_response_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Raw API response data for debugging"
    )
    
    # Voting System for Community IDs
    upvotes = models.PositiveIntegerField(
        default=0,
        help_text="Number of users who agree with this identification"
    )
    
    downvotes = models.PositiveIntegerField(
        default=0,
        help_text="Number of users who disagree with this identification"
    )
    
    # Status
    is_accepted = models.BooleanField(
        default=False,
        help_text="Has the requesting user accepted this identification?"
    )
    
    is_primary = models.BooleanField(
        default=False,
        help_text="Is this the primary/best identification for this request?"
    )
    
    # AI-Generated Care Instructions
    ai_care_instructions = models.JSONField(
        null=True,
        blank=True,
        help_text="AI-generated care instructions for this plant"
    )
    
    care_instructions_generated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When care instructions were generated"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-confidence_score', '-created_at']
        indexes = [
            models.Index(fields=['request', '-confidence_score']),
            models.Index(fields=['identified_species']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        if self.identified_species:
            name = self.identified_species.scientific_name
        else:
            name = self.suggested_scientific_name or self.suggested_common_name
        return f"ID: {name} (confidence: {self.confidence_score:.2%})"
    
    @property
    def display_name(self):
        """Return the best display name for this identification."""
        if self.identified_species:
            return self.identified_species.display_name
        elif self.suggested_scientific_name:
            if self.suggested_common_name:
                return f"{self.suggested_common_name} ({self.suggested_scientific_name})"
            return self.suggested_scientific_name
        return self.suggested_common_name or "Unknown Species"
    
    @property
    def vote_score(self):
        """Calculate the net vote score."""
        return self.upvotes - self.downvotes


class UserPlant(models.Model):
    """
    Model representing a plant in a user's collection.
    """
    
    # UUID for secure references (prevents IDOR attacks)
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    # Link to user and collection
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='plants'
    )
    
    collection = models.ForeignKey(
        'users.UserPlantCollection',
        on_delete=models.CASCADE,
        related_name='plants'
    )
    
    # Plant Information
    species = models.ForeignKey(
        PlantSpecies,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='user_plants'
    )
    
    # Custom name given by user
    nickname = models.CharField(
        max_length=100,
        blank=True,
        help_text="Personal name for this plant"
    )
    
    # Care tracking
    acquisition_date = models.DateField(
        null=True,
        blank=True,
        help_text="When did you get this plant?"
    )
    
    location_in_home = models.CharField(
        max_length=100,
        blank=True,
        help_text="Where is this plant located? (e.g., living room window)"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Personal notes about this plant"
    )
    
    # Status
    is_alive = models.BooleanField(
        default=True,
        help_text="Is this plant still alive?"
    )
    
    is_public = models.BooleanField(
        default=True,
        help_text="Show this plant in your public collection?"
    )
    
    # Link to original identification request
    from_identification_request = models.ForeignKey(
        PlantIdentificationRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collection_plants',
        help_text="Original identification request that led to this plant"
    )
    
    # Link to identification result (NEW)
    from_identification_result = models.ForeignKey(
        PlantIdentificationResult,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collection_plants',
        help_text="Specific identification result that was accepted"
    )
    
    # AI-generated care instructions (NEW)
    care_instructions_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="AI-generated or custom care instructions for this plant"
    )
    
    # Images
    image = models.ImageField(
        upload_to='plants/collections/',
        null=True,
        blank=True,
        help_text="Current photo of your plant"
    )
    
    image_thumbnail = ImageSpecField(
        source='image',
        processors=[ResizeToFill(300, 300)],
        format='JPEG',
        options={'quality': 85}
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'collection', 'species', 'nickname']
    
    def __str__(self):
        name = self.nickname or (self.species.display_name if self.species else "Unknown Plant")
        return f"{self.user.username}'s {name}"
    
    def get_absolute_url(self):
        return reverse('plant_identification:user_plant_detail', kwargs={'pk': self.pk})
    
    @property
    def display_name(self):
        """Return the best display name for this plant."""
        if self.nickname:
            return self.nickname
        elif self.species:
            return self.species.display_name
        return "Unknown Plant"


class PlantDiseaseRequest(models.Model):
    """
    Model representing a user's request to diagnose plant diseases.
    """
    
    # Request ID for tracking
    request_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique identifier for this disease diagnosis request"
    )
    
    # User who made the request
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='plant_disease_requests'
    )
    
    # Link to original plant identification (optional)
    plant_identification_request = models.ForeignKey(
        PlantIdentificationRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='disease_diagnosis_requests',
        help_text="Original plant ID request this disease diagnosis is based on"
    )
    
    # Plant species (if known)
    plant_species = models.ForeignKey(
        PlantSpecies,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='disease_requests',
        help_text="Known plant species with disease symptoms"
    )
    
    # Disease Symptom Images
    image_1 = ProcessedImageField(
        upload_to='plants/diseases/',
        processors=[ResizeToFit(1200, 1200)],
        format='JPEG',
        options={'quality': 90},
        validators=[validate_plant_identification_image],
        help_text="Primary image showing disease symptoms"
    )
    
    image_1_thumbnail = ImageSpecField(
        source='image_1',
        processors=[ResizeToFill(300, 300)],
        format='JPEG',
        options={'quality': 85}
    )
    
    image_2 = ProcessedImageField(
        upload_to='plants/diseases/',
        processors=[ResizeToFit(1200, 1200)],
        format='JPEG',
        options={'quality': 90},
        validators=[validate_plant_identification_image],
        null=True,
        blank=True,
        help_text="Optional second symptom image"
    )
    
    image_2_thumbnail = ImageSpecField(
        source='image_2',
        processors=[ResizeToFill(300, 300)],
        format='JPEG',
        options={'quality': 85}
    )
    
    image_3 = ProcessedImageField(
        upload_to='plants/diseases/',
        processors=[ResizeToFit(1200, 1200)],
        format='JPEG',
        options={'quality': 90},
        validators=[validate_plant_identification_image],
        null=True,
        blank=True,
        help_text="Optional third symptom image"
    )
    
    image_3_thumbnail = ImageSpecField(
        source='image_3',
        processors=[ResizeToFill(300, 300)],
        format='JPEG',
        options={'quality': 85}
    )
    
    # Symptom Description
    symptoms_description = models.TextField(
        blank=True,
        help_text="User's description of symptoms observed"
    )
    
    # Plant condition details
    plant_condition = models.CharField(
        max_length=20,
        choices=[
            ('excellent', 'Excellent - minor symptoms'),
            ('good', 'Good - some concerning symptoms'),
            ('fair', 'Fair - moderate damage visible'),
            ('poor', 'Poor - significant damage'),
            ('critical', 'Critical - plant may die'),
        ],
        blank=True,
        help_text="Overall condition of the plant"
    )
    
    # Location and Environmental Context
    location = models.CharField(
        max_length=200,
        blank=True,
        help_text="Where is this plant located?"
    )
    
    # Environmental factors
    recent_weather = models.CharField(
        max_length=200,
        blank=True,
        help_text="Recent weather conditions (rain, drought, temperature changes)"
    )
    
    recent_care_changes = models.TextField(
        blank=True,
        help_text="Any recent changes in watering, fertilizing, location, etc."
    )
    
    # Request Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Diagnosis'),
            ('processing', 'Processing with AI'),
            ('diagnosed', 'Disease Diagnosed'),
            ('needs_help', 'Needs Community Help'),
            ('failed', 'Diagnosis Failed'),
        ],
        default='pending'
    )
    
    # AI Processing
    processed_by_ai = models.BooleanField(
        default=False,
        help_text="Has this been processed by AI diagnosis?"
    )
    
    ai_processing_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When was this processed by AI?"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Disease Diagnosis #{self.request_id.hex[:8]} by {self.user.username}"
    
    def get_absolute_url(self):
        return reverse('plant_identification:disease_request_detail', kwargs={'request_id': self.request_id})
    
    @property
    def images(self):
        """Return a list of all uploaded symptom images."""
        images = [self.image_1]
        if self.image_2:
            images.append(self.image_2)
        if self.image_3:
            images.append(self.image_3)
        return images
    
    @property
    def image_thumbnails(self):
        """Return a list of all image thumbnails."""
        thumbnails = [self.image_1_thumbnail]
        if self.image_2_thumbnail:
            thumbnails.append(self.image_2_thumbnail)
        if self.image_3_thumbnail:
            thumbnails.append(self.image_3_thumbnail)
        return thumbnails


class PlantDiseaseDatabase(models.Model):
    """
    Model for storing disease information from high-confidence diagnoses (≥50%).
    This builds our local knowledge base from API results.
    """
    
    # UUID for secure references
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    # Disease Information
    disease_name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Common name of the disease"
    )
    
    scientific_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Scientific name of the pathogen if available"
    )
    
    disease_type = models.CharField(
        max_length=20,
        choices=[
            ('fungal', 'Fungal Disease'),
            ('bacterial', 'Bacterial Disease'),
            ('viral', 'Viral Disease'),
            ('pest', 'Pest/Insect Damage'),
            ('abiotic', 'Abiotic/Environmental'),
            ('deficiency', 'Nutrient Deficiency'),
            ('toxicity', 'Toxicity/Poisoning'),
        ],
        help_text="Type of disease or problem"
    )
    
    severity_levels = models.JSONField(
        default=list,
        help_text="Array of severity levels (mild, moderate, severe)"
    )
    
    # Symptoms
    symptoms = models.JSONField(
        default=dict,
        help_text="Structured symptom data from API responses"
    )
    
    # Affected Plants
    affected_plant_families = models.JSONField(
        default=list,
        help_text="Plant families commonly affected by this disease"
    )
    
    affected_plants = models.ManyToManyField(
        PlantSpecies,
        blank=True,
        related_name='known_diseases',
        help_text="Specific plant species affected"
    )
    
    # Environmental factors
    seasonal_patterns = models.JSONField(
        default=dict,
        help_text="When this disease typically occurs (seasons, weather conditions)"
    )
    
    environmental_triggers = models.JSONField(
        default=list,
        help_text="Environmental conditions that trigger this disease"
    )
    
    # Storage metadata
    confidence_score = models.FloatField(
        help_text="Minimum confidence score from diagnoses (≥0.5 required)"
    )
    
    api_source = models.CharField(
        max_length=50,
        choices=[
            ('plant_health', 'plant.health API'),
            ('plantnet', 'PlantNet API'),
            ('manual', 'Manual Entry'),
            ('community', 'Community Contributed'),
        ],
        default='plant_health',
        help_text="Source of this disease information"
    )
    
    diagnosis_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of times this disease has been diagnosed"
    )
    
    # Community data
    community_confirmed = models.BooleanField(
        default=False,
        help_text="Has this been confirmed by community voting?"
    )
    
    expert_reviewed = models.BooleanField(
        default=False,
        help_text="Has this been reviewed by a plant health expert?"
    )
    
    # Additional Information
    description = models.TextField(
        blank=True,
        help_text="General description of the disease"
    )
    
    prevention_tips = models.TextField(
        blank=True,
        help_text="How to prevent this disease"
    )
    
    # Images
    reference_image = models.ImageField(
        upload_to='diseases/reference/',
        null=True,
        blank=True,
        help_text="Reference image showing typical symptoms"
    )
    
    reference_image_thumbnail = ImageSpecField(
        source='reference_image',
        processors=[ResizeToFill(300, 300)],
        format='JPEG',
        options={'quality': 85}
    )
    
    # Timestamps
    first_diagnosed = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-diagnosis_count', 'disease_name']
        verbose_name = 'Disease Database Entry'
        verbose_name_plural = 'Disease Database Entries'
    
    def __str__(self):
        return f"{self.disease_name} ({self.disease_type})"
    
    @property
    def display_name(self):
        """Return the best display name for the disease."""
        if self.scientific_name:
            return f"{self.disease_name} ({self.scientific_name})"
        return self.disease_name


class DiseaseCareInstructions(models.Model):
    """
    Model for storing treatment and care instructions for diseases.
    """
    
    # UUID for secure references
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    # Link to disease
    disease = models.ForeignKey(
        PlantDiseaseDatabase,
        on_delete=models.CASCADE,
        related_name='care_instructions'
    )
    
    # Treatment Information
    treatment_name = models.CharField(
        max_length=200,
        help_text="Name of the treatment method"
    )
    
    treatment_type = models.CharField(
        max_length=20,
        choices=[
            ('organic', 'Organic Treatment'),
            ('chemical', 'Chemical Treatment'),
            ('cultural', 'Cultural/Management'),
            ('biological', 'Biological Control'),
            ('preventive', 'Preventive Measure'),
        ],
        help_text="Type of treatment approach"
    )
    
    # Instructions
    instructions = models.TextField(
        help_text="Detailed treatment instructions"
    )
    
    application_timing = models.TextField(
        blank=True,
        help_text="When and how often to apply this treatment"
    )
    
    materials_needed = models.JSONField(
        default=list,
        help_text="List of materials/products needed"
    )
    
    # Effectiveness
    effectiveness_score = models.FloatField(
        default=0.0,
        help_text="Community-rated effectiveness (0.0 to 1.0)"
    )
    
    success_rate = models.FloatField(
        null=True,
        blank=True,
        help_text="Percentage success rate if known"
    )
    
    # Community feedback
    community_votes = models.PositiveIntegerField(
        default=0,
        help_text="Total community votes received"
    )
    
    positive_votes = models.PositiveIntegerField(
        default=0,
        help_text="Positive 'this worked for me' votes"
    )
    
    negative_votes = models.PositiveIntegerField(
        default=0,
        help_text="Negative 'this didn't work' votes"
    )
    
    # Additional Information
    cost_estimate = models.CharField(
        max_length=20,
        choices=[
            ('free', 'Free'),
            ('low', 'Low Cost ($1-10)'),
            ('medium', 'Medium Cost ($10-50)'),
            ('high', 'High Cost ($50+)'),
        ],
        blank=True,
        help_text="Estimated cost of treatment"
    )
    
    difficulty_level = models.CharField(
        max_length=20,
        choices=[
            ('easy', 'Easy - Anyone can do'),
            ('moderate', 'Moderate - Some experience needed'),
            ('difficult', 'Difficult - Expert knowledge required'),
        ],
        default='easy',
        help_text="Difficulty level of applying treatment"
    )
    
    safety_notes = models.TextField(
        blank=True,
        help_text="Safety precautions and warnings"
    )
    
    # Source and validation
    source = models.CharField(
        max_length=20,
        choices=[
            ('api', 'API Response'),
            ('community', 'Community Contributed'),
            ('expert', 'Expert Recommendation'),
            ('research', 'Research/Scientific'),
        ],
        default='api',
        help_text="Source of this treatment information"
    )
    
    verified_by_expert = models.BooleanField(
        default=False,
        help_text="Has this been verified by a plant health expert?"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-effectiveness_score', '-positive_votes', 'treatment_name']
        unique_together = ['disease', 'treatment_name']
    
    def __str__(self):
        return f"{self.treatment_name} for {self.disease.disease_name}"
    
    @property
    def success_percentage(self):
        """Calculate success percentage from community votes."""
        if self.community_votes == 0:
            return None
        return (self.positive_votes / self.community_votes) * 100
    
    @property
    def vote_ratio(self):
        """Calculate positive vote ratio."""
        total_votes = self.positive_votes + self.negative_votes
        if total_votes == 0:
            return 0.5  # Neutral if no votes
        return self.positive_votes / total_votes


class PlantDiseaseResult(models.Model):
    """
    Model representing a disease diagnosis result.
    """
    
    # UUID for secure references
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    # Link to the diagnosis request
    request = models.ForeignKey(
        PlantDiseaseRequest,
        on_delete=models.CASCADE,
        related_name='diagnosis_results'
    )
    
    # Disease identification
    identified_disease = models.ForeignKey(
        PlantDiseaseDatabase,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='diagnosis_results',
        help_text="Disease identified from our local database"
    )
    
    # Alternative identification (if not in local database yet)
    suggested_disease_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Disease name from API if not in our database"
    )
    
    suggested_disease_type = models.CharField(
        max_length=20,
        choices=[
            ('fungal', 'Fungal Disease'),
            ('bacterial', 'Bacterial Disease'),
            ('viral', 'Viral Disease'),
            ('pest', 'Pest/Insect Damage'),
            ('abiotic', 'Abiotic/Environmental'),
            ('deficiency', 'Nutrient Deficiency'),
            ('toxicity', 'Toxicity/Poisoning'),
        ],
        blank=True,
        help_text="Type of disease suggested by API"
    )
    
    # Confidence and Source
    confidence_score = models.FloatField(
        help_text="Confidence score (0.0 to 1.0)"
    )
    
    diagnosis_source = models.CharField(
        max_length=20,
        choices=[
            ('local_db', 'Local Database'),
            ('api_plant_health', 'plant.health API'),
            ('api_combined', 'Combined APIs'),
            ('community', 'Community Diagnosis'),
            ('expert', 'Expert Diagnosis'),
        ]
    )
    
    # User who provided this diagnosis (for community diagnoses)
    diagnosed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='disease_diagnoses_given'
    )
    
    # Diagnosis details
    symptoms_identified = models.JSONField(
        default=list,
        help_text="List of symptoms identified in the images"
    )
    
    severity_assessment = models.CharField(
        max_length=20,
        choices=[
            ('mild', 'Mild - Early symptoms'),
            ('moderate', 'Moderate - Noticeable damage'),
            ('severe', 'Severe - Significant damage'),
            ('critical', 'Critical - Plant in danger'),
        ],
        blank=True,
        help_text="Assessed severity of the disease"
    )
    
    # Treatment recommendations
    recommended_treatments = models.JSONField(
        default=list,
        help_text="List of recommended treatment IDs or names"
    )
    
    immediate_actions = models.TextField(
        blank=True,
        help_text="Immediate actions the user should take"
    )
    
    # Additional Information
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this diagnosis"
    )
    
    # External API Response Data
    api_response_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Raw API response data for debugging"
    )
    
    # Community validation
    community_confirmed = models.BooleanField(
        default=False,
        help_text="Has this diagnosis been confirmed by community votes?"
    )
    
    upvotes = models.PositiveIntegerField(
        default=0,
        help_text="Number of users who agree with this diagnosis"
    )
    
    downvotes = models.PositiveIntegerField(
        default=0,
        help_text="Number of users who disagree with this diagnosis"
    )
    
    # Status
    is_accepted = models.BooleanField(
        default=False,
        help_text="Has the requesting user accepted this diagnosis?"
    )
    
    is_primary = models.BooleanField(
        default=False,
        help_text="Is this the primary/best diagnosis for this request?"
    )
    
    # Auto-storage flag
    stored_to_database = models.BooleanField(
        default=False,
        help_text="Has this high-confidence result been stored to local database?"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-confidence_score', '-created_at']
        indexes = [
            models.Index(fields=['request', '-confidence_score']),
            models.Index(fields=['identified_disease']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['confidence_score']),  # For filtering high-confidence results
        ]
    
    def __str__(self):
        disease_name = self.identified_disease.disease_name if self.identified_disease else self.suggested_disease_name
        return f"Disease: {disease_name} (confidence: {self.confidence_score:.2%})"
    
    @property
    def display_name(self):
        """Return the best display name for this diagnosis."""
        if self.identified_disease:
            return self.identified_disease.display_name
        elif self.suggested_disease_name:
            return self.suggested_disease_name
        return "Unknown Disease"
    
    @property
    def vote_score(self):
        """Calculate the net vote score."""
        return self.upvotes - self.downvotes
    
    def should_store_to_database(self):
        """Check if this result should be stored to local database (≥50% confidence)."""
        return self.confidence_score >= 0.5 and not self.stored_to_database


class SavedDiagnosis(models.Model):
    """
    Model for user's saved disease diagnoses and treatments.
    """
    
    # UUID for secure references
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    # User who saved this diagnosis
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_diagnoses'
    )
    
    # Link to the diagnosis result
    diagnosis_result = models.ForeignKey(
        PlantDiseaseResult,
        on_delete=models.CASCADE,
        related_name='saved_by_users'
    )
    
    # User's notes and tracking
    personal_notes = models.TextField(
        blank=True,
        help_text="User's personal notes about this diagnosis and treatment"
    )
    
    treatments_tried = models.ManyToManyField(
        DiseaseCareInstructions,
        through='TreatmentAttempt',
        related_name='tried_by_users',
        help_text="Treatments the user has tried for this diagnosis"
    )
    
    # Status tracking
    treatment_status = models.CharField(
        max_length=20,
        choices=[
            ('not_started', 'Not Started'),
            ('in_progress', 'Treatment in Progress'),
            ('successful', 'Successfully Treated'),
            ('failed', 'Treatment Failed'),
            ('monitoring', 'Monitoring Progress'),
        ],
        default='not_started',
        help_text="Current treatment status"
    )
    
    # Plant outcome
    plant_recovered = models.BooleanField(
        null=True,
        blank=True,
        help_text="Did the plant recover? (null = unknown/in progress)"
    )
    
    # Sharing preferences
    share_with_community = models.BooleanField(
        default=False,
        help_text="Share this diagnosis experience with the community"
    )
    
    # Timestamps
    saved_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-saved_at']
        unique_together = ['user', 'diagnosis_result']
    
    def __str__(self):
        return f"{self.user.username} saved: {self.diagnosis_result.display_name}"


class TreatmentAttempt(models.Model):
    """
    Through model for tracking user's treatment attempts.
    """
    
    saved_diagnosis = models.ForeignKey(SavedDiagnosis, on_delete=models.CASCADE)
    treatment = models.ForeignKey(DiseaseCareInstructions, on_delete=models.CASCADE)
    
    # Attempt details
    started_date = models.DateField(
        help_text="Date when treatment was started"
    )
    
    completed_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when treatment was completed (if applicable)"
    )
    
    # Results
    effectiveness_rating = models.IntegerField(
        choices=[
            (1, '1 - Not effective'),
            (2, '2 - Slightly effective'),
            (3, '3 - Moderately effective'),
            (4, '4 - Very effective'),
            (5, '5 - Completely effective'),
        ],
        null=True,
        blank=True,
        help_text="User's rating of treatment effectiveness"
    )
    
    success = models.BooleanField(
        null=True,
        blank=True,
        help_text="Was this treatment successful? (null = in progress)"
    )
    
    # User feedback
    user_notes = models.TextField(
        blank=True,
        help_text="User's notes about this treatment attempt"
    )
    
    side_effects = models.TextField(
        blank=True,
        help_text="Any negative effects or problems encountered"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['saved_diagnosis', 'treatment']
        ordering = ['-started_date']
    
    def __str__(self):
        return f"{self.treatment.treatment_name} attempted by {self.saved_diagnosis.user.username}"


class SavedCareInstructions(models.Model):
    """
    Model for user's saved plant care instruction cards.
    """
    
    # UUID for secure references
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    # User who saved this care card
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_care_instructions'
    )
    
    # Plant information
    plant_species = models.ForeignKey(
        PlantSpecies,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Plant species this care card is for"
    )
    
    # Plant identification info (if saved from an identification result)
    plant_scientific_name = models.CharField(
        max_length=200,
        help_text="Scientific name of the plant"
    )
    
    plant_common_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Common name of the plant"
    )
    
    plant_family = models.CharField(
        max_length=100,
        blank=True,
        help_text="Plant family"
    )
    
    # Care instructions data (JSON)
    care_instructions_data = models.JSONField(
        help_text="Full care instructions data from the API"
    )
    
    # User's notes and experience
    personal_notes = models.TextField(
        blank=True,
        help_text="User's personal notes and experiences with this plant"
    )
    
    custom_nickname = models.CharField(
        max_length=100,
        blank=True,
        help_text="User's custom nickname for this plant"
    )
    
    # Care tracking
    care_difficulty_experienced = models.CharField(
        max_length=20,
        choices=[
            ('very_easy', 'Very Easy'),
            ('easy', 'Easy'), 
            ('moderate', 'Moderate'),
            ('challenging', 'Challenging'),
            ('difficult', 'Difficult'),
        ],
        null=True,
        blank=True,
        help_text="User's experienced difficulty level"
    )
    
    current_status = models.CharField(
        max_length=20,
        choices=[
            ('planning', 'Planning to Get'),
            ('newly_acquired', 'Recently Acquired'),
            ('thriving', 'Thriving'),
            ('struggling', 'Having Issues'),
            ('recovered', 'Recovered from Problems'),
            ('lost', 'Plant Lost'),
        ],
        default='planning',
        help_text="Current status of user's plant"
    )
    
    # Sharing preferences
    share_with_community = models.BooleanField(
        default=False,
        help_text="Share this care experience with the community"
    )
    
    is_favorite = models.BooleanField(
        default=False,
        help_text="Mark as favorite care card"
    )
    
    # Timestamps
    saved_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_viewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time user viewed this care card"
    )
    
    class Meta:
        ordering = ['-saved_at']
        unique_together = ['user', 'plant_scientific_name']
    
    def __str__(self):
        display_name = self.custom_nickname or self.plant_common_name or self.plant_scientific_name
        return f"{self.user.username} saved care for: {display_name}"
    
    @property
    def display_name(self):
        """Get the best display name for this plant."""
        if self.custom_nickname:
            return self.custom_nickname
        elif self.plant_common_name:
            return self.plant_common_name
        return self.plant_scientific_name
    
    def update_last_viewed(self):
        """Update the last viewed timestamp."""
        from django.utils import timezone
        self.last_viewed_at = timezone.now()
        self.save(update_fields=['last_viewed_at'])


class PlantIdentificationVote(models.Model):
    """
    Model to track user votes on identification results for persistence across sessions.
    """
    VOTE_CHOICES = [
        ('upvote', 'Upvote'),
        ('downvote', 'Downvote'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='identification_votes'
    )
    
    result = models.ForeignKey(
        PlantIdentificationResult,
        on_delete=models.CASCADE,
        related_name='user_votes'
    )
    
    vote_type = models.CharField(
        max_length=10,
        choices=VOTE_CHOICES,
        help_text="Type of vote cast by the user"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'result']  # One vote per user per result
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} voted {self.vote_type} on result {self.result.id}"


# =============================================================================
# WAGTAIL MODELS FOR HEADLESS CMS API
# =============================================================================
# These models integrate with Wagtail for headless CMS functionality

from wagtail.models import Page
from wagtail.fields import StreamField, RichTextField
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, InlinePanel
from wagtail.search import index
from wagtail.snippets.models import register_snippet
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from modelcluster.contrib.taggit import ClusterTaggableManager
from taggit.models import TaggedItemBase
from django.db.models import Q


# StreamField blocks for plant care instructions
class PlantCareBlocks(blocks.StreamBlock):
    """Flat StreamField blocks for plant care content."""
    
    heading = blocks.CharBlock(
        icon="title",
        template="plant_identification/blocks/heading.html"
    )
    
    paragraph = blocks.RichTextBlock(
        icon="pilcrow", 
        template="plant_identification/blocks/paragraph.html"
    )
    
    care_tip = blocks.StructBlock([
        ('tip_title', blocks.CharBlock()),
        ('tip_content', blocks.RichTextBlock()),
        ('difficulty_level', blocks.ChoiceBlock(choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
        ]))
    ], icon="help", template="plant_identification/blocks/care_tip.html")
    
    seasonal_care = blocks.StructBlock([
        ('season', blocks.ChoiceBlock(choices=[
            ('spring', 'Spring'),
            ('summer', 'Summer'),
            ('autumn', 'Autumn/Fall'),
            ('winter', 'Winter'),
        ])),
        ('care_instructions', blocks.RichTextBlock()),
        ('special_notes', blocks.RichTextBlock(required=False))
    ], icon="date", template="plant_identification/blocks/seasonal_care.html")
    
    problem_solution = blocks.StructBlock([
        ('problem', blocks.CharBlock()),
        ('symptoms', blocks.RichTextBlock()),
        ('solution', blocks.RichTextBlock()),
        ('prevention', blocks.RichTextBlock(required=False))
    ], icon="warning", template="plant_identification/blocks/problem_solution.html")
    
    image = ImageChooserBlock(
        icon="image",
        template="plant_identification/blocks/image.html"
    )
    
    gallery = blocks.StructBlock([
        ('gallery_title', blocks.CharBlock(required=False)),
        ('images', blocks.ListBlock(ImageChooserBlock(), min_num=2, max_num=8))
    ], icon="image", template="plant_identification/blocks/gallery.html")


@register_snippet
class PlantCareGuide(models.Model):
    """
    Wagtail snippet for plant care instructions.
    
    This model provides structured plant care data through the Wagtail API
    while linking to the existing PlantSpecies model.
    """
    
    plant_species = models.OneToOneField(
        PlantSpecies,
        on_delete=models.CASCADE,
        related_name='care_guide',
        help_text="Plant species this care guide is for"
    )
    
    # Basic care information
    care_difficulty = models.CharField(
        max_length=20,
        choices=[
            ('very_easy', 'Very Easy'),
            ('easy', 'Easy'),
            ('moderate', 'Moderate'),
            ('challenging', 'Challenging'),
            ('difficult', 'Difficult'),
        ],
        default='moderate'
    )
    
    # Quick care summary
    quick_care_summary = RichTextField(
        help_text="Brief summary of care requirements"
    )
    
    # Detailed care content using StreamField
    care_content = StreamField(
        PlantCareBlocks(),
        help_text="Detailed care instructions using content blocks",
        use_json_field=True
    )
    
    # Key care metrics (derived from PlantSpecies)
    light_description = models.TextField(
        blank=True,
        help_text="Detailed light requirements description"
    )
    
    watering_description = models.TextField(
        blank=True,
        help_text="Detailed watering instructions"
    )
    
    soil_description = models.TextField(
        blank=True,
        help_text="Soil requirements and recommendations"
    )
    
    temperature_description = models.TextField(
        blank=True,
        help_text="Temperature preferences and tolerance"
    )
    
    humidity_description = models.TextField(
        blank=True,
        help_text="Humidity requirements"
    )
    
    fertilizing_description = models.TextField(
        blank=True,
        help_text="Fertilizing schedule and recommendations"
    )
    
    # Propagation information
    propagation_methods = models.TextField(
        blank=True,
        help_text="How to propagate this plant"
    )
    
    # Common problems
    common_problems = models.TextField(
        blank=True,
        help_text="Common issues and solutions"
    )
    
    # Seasonal care notes
    seasonal_notes = models.TextField(
        blank=True,
        help_text="Special seasonal care considerations"
    )
    
    # Tags for categorization
    tags = ClusterTaggableManager(
        blank=True,
        help_text="Tags for categorizing care guides"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Featured guide
    is_featured = models.BooleanField(
        default=False,
        help_text="Feature this care guide"
    )
    
    panels = [
        FieldPanel('plant_species'),
        FieldPanel('care_difficulty'),
        FieldPanel('quick_care_summary'),
        FieldPanel('care_content'),
        MultiFieldPanel([
            FieldPanel('light_description'),
            FieldPanel('watering_description'),
            FieldPanel('soil_description'),
            FieldPanel('temperature_description'),
            FieldPanel('humidity_description'),
            FieldPanel('fertilizing_description'),
        ], heading="Care Details"),
        MultiFieldPanel([
            FieldPanel('propagation_methods'),
            FieldPanel('common_problems'),
            FieldPanel('seasonal_notes'),
        ], heading="Additional Information"),
        FieldPanel('tags'),
        FieldPanel('is_featured'),
    ]
    
    search_fields = [
        index.SearchField('plant_species__scientific_name'),
        index.SearchField('plant_species__common_names'),
        index.SearchField('quick_care_summary'),
        index.SearchField('care_content'),
        index.FilterField('care_difficulty'),
        index.FilterField('is_featured'),
    ]
    
    class Meta:
        verbose_name = "Plant Care Guide"
        verbose_name_plural = "Plant Care Guides"
        ordering = ['plant_species__scientific_name']
    
    def __str__(self):
        return f"Care Guide: {self.plant_species.scientific_name}"
    
    @property
    def display_name(self):
        """Get display name from plant species."""
        if self.plant_species.common_names:
            return self.plant_species.common_names.split(',')[0].strip()
        return self.plant_species.scientific_name
    
    @property
    def care_level_description(self):
        """Get human-readable care difficulty."""
        return dict(self._meta.get_field('care_difficulty').choices)[self.care_difficulty]




@register_snippet  
class PlantCategory(models.Model):
    """
    Categories for organizing plants (different from blog categories).
    """
    
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Category name (e.g., 'Houseplants', 'Succulents', 'Herbs')"
    )
    
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-friendly name"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Category description"
    )
    
    # Visual elements
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="CSS icon class (e.g., 'fas fa-leaf')"
    )
    
    color = models.CharField(
        max_length=7,
        default="#28a745",
        help_text="Category color (hex code)"
    )
    
    cover_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Cover image for the category"
    )
    
    # Settings
    is_featured = models.BooleanField(
        default=False,
        help_text="Show this category prominently"
    )
    
    # Plant species in this category
    plant_species = ParentalManyToManyField(
        PlantSpecies,
        blank=True,
        help_text="Plant species in this category"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    panels = [
        FieldPanel('name'),
        FieldPanel('slug'),
        FieldPanel('description'),
        MultiFieldPanel([
            FieldPanel('icon'),
            FieldPanel('color'), 
            FieldPanel('cover_image'),
            FieldPanel('is_featured'),
        ], heading="Display Settings"),
        FieldPanel('plant_species'),
    ]
    
    search_fields = [
        index.SearchField('name'),
        index.SearchField('description'),
        index.FilterField('is_featured'),
    ]
    
    class Meta:
        verbose_name = "Plant Category"
        verbose_name_plural = "Plant Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# Wagtail Page models for plant identification content

class PlantIdentificationBasePage(Page):
    """Base page for plant identification content."""
    
    meta_description = models.TextField(
        max_length=160,
        blank=True,
        help_text="Meta description for search engines"
    )
    
    social_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Image for social media sharing"
    )
    
    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('meta_description'),
            FieldPanel('social_image'),
        ], heading="SEO Settings")
    ]
    
    search_fields = Page.search_fields + [
        index.SearchField('meta_description'),
    ]
    
    class Meta:
        abstract = True


class PlantSpeciesPage(PlantIdentificationBasePage):
    """
    Wagtail page for individual plant species.
    
    This creates a dedicated page for each plant species that can be
    managed through Wagtail and exposed via the headless API.
    """
    
    plant_species = models.OneToOneField(
        PlantSpecies,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='species_page',
        help_text="Plant species this page represents"
    )
    
    # Page content
    introduction = RichTextField(
        help_text="Introduction to this plant species"
    )
    
    # Detailed content using StreamField
    content_blocks = StreamField(
        PlantCareBlocks(),
        help_text="Detailed plant information and care instructions",
        use_json_field=True
    )
    
    # Featured images
    hero_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Main hero image for this plant"
    )
    
    gallery_images = models.ManyToManyField(
        'wagtailimages.Image',
        blank=True,
        help_text="Gallery of plant images"
    )
    
    # Categorization
    categories = ParentalManyToManyField(
        PlantCategory,
        blank=True,
        help_text="Categories for this plant"
    )
    
    # Settings
    is_featured = models.BooleanField(
        default=False,
        help_text="Feature this plant species"
    )
    
    content_panels = PlantIdentificationBasePage.content_panels + [
        FieldPanel('plant_species'),
        FieldPanel('introduction'),
        FieldPanel('content_blocks'),
        MultiFieldPanel([
            FieldPanel('hero_image'),
            FieldPanel('gallery_images'),
        ], heading="Images"),
        MultiFieldPanel([
            FieldPanel('categories'),
            FieldPanel('is_featured'),
        ], heading="Categorization")
    ]
    
    search_fields = PlantIdentificationBasePage.search_fields + [
        index.SearchField('introduction'),
        index.SearchField('content_blocks'),
        index.FilterField('categories'),
        index.FilterField('is_featured'),
    ]
    
    class Meta:
        verbose_name = "Plant Species Page"
    
    def get_context(self, request):
        context = super().get_context(request)
        
        # Add related plants (same family or categories)
        related_plants = PlantSpeciesPage.objects.live().public().exclude(
            id=self.id
        ).filter(
            Q(plant_species__family=self.plant_species.family) |
            Q(categories__in=self.categories.all())
        ).distinct()[:6]
        
        context.update({
            'related_plants': related_plants,
            'care_guide': getattr(self.plant_species, 'care_guide', None),
        })
        
        return context


class PlantCategoryIndexPage(PlantIdentificationBasePage):
    """
    Index page for browsing plant categories.
    """
    
    introduction = RichTextField(
        blank=True,
        help_text="Introduction to plant categories"
    )
    
    categories_per_page = models.IntegerField(
        default=12,
        help_text="Number of categories to display per page"
    )
    
    show_featured_plants = models.BooleanField(
        default=True,
        help_text="Show featured plants section"
    )
    
    content_panels = PlantIdentificationBasePage.content_panels + [
        FieldPanel('introduction'),
        FieldPanel('categories_per_page'),
        FieldPanel('show_featured_plants'),
    ]
    
    def get_context(self, request):
        context = super().get_context(request)
        
        # Get plant categories
        categories = PlantCategory.objects.filter(is_featured=True)
        
        # Featured plants
        featured_plants = []
        if self.show_featured_plants:
            featured_plants = PlantSpeciesPage.objects.live().public().filter(
                is_featured=True
            )[:6]
        
        context.update({
            'categories': categories,
            'featured_plants': featured_plants,
        })
        
        return context
    
    class Meta:
        verbose_name = "Plant Category Index Page"


# =============================================================================
# BATCH IDENTIFICATION MODELS
# =============================================================================

class BatchIdentificationRequest(models.Model):
    """
    Model representing a batch plant identification request with multiple images.
    Supports side-by-side comparison and quick actions workflow.
    """
    
    # Batch ID for tracking
    batch_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique identifier for this batch identification request"
    )
    
    # User who made the request
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='batch_identification_requests'
    )
    
    # Batch metadata
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional title for this batch (e.g., 'Garden Walk', 'Field Trip')"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Optional description of the batch identification session"
    )
    
    location = models.CharField(
        max_length=200,
        blank=True,
        help_text="Location where these plants were photographed"
    )
    
    # Batch Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('uploading', 'Uploading Images'),
            ('processing', 'Processing with AI'),
            ('completed', 'Batch Completed'),
            ('partial', 'Partially Completed'),
            ('failed', 'Processing Failed'),
        ],
        default='uploading'
    )
    
    # Processing metadata
    total_images = models.PositiveIntegerField(
        default=0,
        help_text="Total number of images in this batch"
    )
    
    processed_images = models.PositiveIntegerField(
        default=0,
        help_text="Number of images successfully processed"
    )
    
    failed_images = models.PositiveIntegerField(
        default=0,
        help_text="Number of images that failed processing"
    )
    
    # AI Processing
    processing_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When AI processing started"
    )
    
    processing_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When AI processing completed"
    )
    
    # Background processing job ID for tracking
    job_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Background job ID for tracking processing status"
    )
    
    # Settings
    auto_accept_high_confidence = models.BooleanField(
        default=False,
        help_text="Automatically accept results with >90% confidence"
    )
    
    share_with_community = models.BooleanField(
        default=False,
        help_text="Share this batch with the community"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        title = self.title or f"Batch #{self.batch_id.hex[:8]}"
        return f"{title} by {self.user.username}"
    
    @property
    def processing_progress(self):
        """Calculate processing progress percentage."""
        if self.total_images == 0:
            return 0
        return (self.processed_images / self.total_images) * 100
    
    @property
    def is_complete(self):
        """Check if all images have been processed."""
        return self.processed_images + self.failed_images >= self.total_images
    
    def update_progress(self):
        """Update batch status based on individual request statuses."""
        from django.db.models import Count
        
        status_counts = self.individual_requests.aggregate(
            total=Count('id'),
            completed=Count('id', filter=models.Q(status__in=['identified', 'failed'])),
            failed=Count('id', filter=models.Q(status='failed'))
        )
        
        self.total_images = status_counts['total']
        self.processed_images = status_counts['completed'] - status_counts['failed']
        self.failed_images = status_counts['failed']
        
        # Update batch status
        if self.is_complete:
            if self.failed_images == 0:
                self.status = 'completed'
            elif self.processed_images > 0:
                self.status = 'partial'
            else:
                self.status = 'failed'
            
            if not self.processing_completed_at:
                from django.utils import timezone
                self.processing_completed_at = timezone.now()
        
        self.save(update_fields=[
            'total_images', 'processed_images', 'failed_images', 
            'status', 'processing_completed_at'
        ])


class BatchIdentificationComparison(models.Model):
    """
    Model for storing side-by-side comparison data for batch identification results.
    """
    
    # UUID for secure references
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    # Link to batch request
    batch_request = models.ForeignKey(
        BatchIdentificationRequest,
        on_delete=models.CASCADE,
        related_name='comparisons'
    )
    
    # Individual requests being compared
    primary_request = models.ForeignKey(
        PlantIdentificationRequest,
        on_delete=models.CASCADE,
        related_name='primary_comparisons',
        help_text="Primary plant identification request"
    )
    
    secondary_requests = models.ManyToManyField(
        PlantIdentificationRequest,
        related_name='secondary_comparisons',
        help_text="Additional requests to compare side-by-side"
    )
    
    # Comparison metadata
    comparison_title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Title for this comparison group"
    )
    
    comparison_notes = models.TextField(
        blank=True,
        help_text="User notes about the comparison"
    )
    
    # User selections and decisions
    selected_result = models.ForeignKey(
        PlantIdentificationResult,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='comparison_selections',
        help_text="Result selected by user after comparison"
    )
    
    decision_reasoning = models.TextField(
        blank=True,
        help_text="User's reasoning for their selection"
    )
    
    # Quick actions taken
    action_taken = models.CharField(
        max_length=20,
        choices=[
            ('none', 'No Action'),
            ('accept_save', 'Accept & Save to My Plants'),
            ('ask_community', 'Ask Community for Help'),
            ('regenerate_care', 'Regenerate Care Instructions'),
            ('mark_uncertain', 'Mark as Uncertain'),
        ],
        default='none',
        help_text="Quick action taken by user"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When user completed this comparison"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['batch_request', '-created_at']),
            models.Index(fields=['action_taken']),
        ]
    
    def __str__(self):
        return f"Comparison for {self.primary_request} in batch {self.batch_request.batch_id.hex[:8]}"
    
    @property
    def is_completed(self):
        """Check if user has completed this comparison."""
        return self.completed_at is not None
    
    def mark_completed(self, action=None, selected_result=None, reasoning=""):
        """Mark this comparison as completed with optional action."""
        from django.utils import timezone
        
        if action:
            self.action_taken = action
        if selected_result:
            self.selected_result = selected_result
        if reasoning:
            self.decision_reasoning = reasoning
        
        self.completed_at = timezone.now()
        self.save(update_fields=['action_taken', 'selected_result', 'decision_reasoning', 'completed_at'])


class BatchIdentificationImage(models.Model):
    """
    Model for individual images within a batch identification request.
    Links to PlantIdentificationRequest for compatibility with existing workflow.
    """
    
    # UUID for secure references
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references"
    )
    
    # Link to batch request
    batch_request = models.ForeignKey(
        BatchIdentificationRequest,
        on_delete=models.CASCADE,
        related_name='batch_images'
    )
    
    # Link to individual identification request
    identification_request = models.OneToOneField(
        PlantIdentificationRequest,
        on_delete=models.CASCADE,
        related_name='batch_image',
        help_text="Individual plant identification request for this image"
    )
    
    # Image metadata
    original_filename = models.CharField(
        max_length=255,
        help_text="Original filename when uploaded"
    )
    
    upload_order = models.PositiveIntegerField(
        help_text="Order in which this image was uploaded in the batch"
    )
    
    # GPS data if available
    latitude = models.FloatField(
        null=True,
        blank=True,
        help_text="GPS latitude if available in EXIF data"
    )
    
    longitude = models.FloatField(
        null=True,
        blank=True,
        help_text="GPS longitude if available in EXIF data"
    )
    
    # Image quality assessment
    image_quality_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Automated image quality assessment (0.0 to 1.0)"
    )
    
    quality_issues = models.JSONField(
        default=list,
        help_text="List of detected quality issues (blur, lighting, etc.)"
    )
    
    # Processing status
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Processing'),
            ('processing', 'Processing'),
            ('completed', 'Processing Completed'),
            ('failed', 'Processing Failed'),
            ('skipped', 'Skipped'),
        ],
        default='pending'
    )
    
    processing_error = models.TextField(
        blank=True,
        help_text="Error message if processing failed"
    )
    
    # User feedback
    user_confidence_rating = models.IntegerField(
        choices=[
            (1, '1 - Very uncertain'),
            (2, '2 - Somewhat uncertain'),
            (3, '3 - Neutral'),
            (4, '4 - Somewhat confident'),
            (5, '5 - Very confident'),
        ],
        null=True,
        blank=True,
        help_text="User's confidence in the identification results"
    )
    
    user_notes = models.TextField(
        blank=True,
        help_text="User's notes about this specific plant/image"
    )
    
    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When processing completed for this image"
    )
    
    class Meta:
        ordering = ['upload_order']
        indexes = [
            models.Index(fields=['batch_request', 'upload_order']),
            models.Index(fields=['processing_status']),
        ]
    
    def __str__(self):
        return f"Image {self.upload_order} in batch {self.batch_request.batch_id.hex[:8]}"
    
    @property
    def has_location_data(self):
        """Check if this image has GPS location data."""
        return self.latitude is not None and self.longitude is not None
    
    def mark_processing_complete(self, success=True, error_message=""):
        """Mark this image as completed processing."""
        from django.utils import timezone
        
        if success:
            self.processing_status = 'completed'
        else:
            self.processing_status = 'failed'
            self.processing_error = error_message
        
        self.processed_at = timezone.now()
        self.save(update_fields=['processing_status', 'processing_error', 'processed_at'])
        
        # Update batch progress
        self.batch_request.update_progress()


class BatchProcessingQueue(models.Model):
    """
    Model for managing background processing queue for batch identifications.
    """
    
    # Link to batch request
    batch_request = models.ForeignKey(
        BatchIdentificationRequest,
        on_delete=models.CASCADE,
        related_name='processing_queue_items'
    )
    
    # Processing details
    queue_position = models.PositiveIntegerField(
        help_text="Position in the processing queue"
    )
    
    priority = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low Priority'),
            ('normal', 'Normal Priority'),
            ('high', 'High Priority'),
            ('urgent', 'Urgent'),
        ],
        default='normal'
    )
    
    # Processing resources allocated
    max_concurrent_requests = models.PositiveIntegerField(
        default=3,
        help_text="Maximum number of concurrent API requests for this batch"
    )
    
    estimated_completion_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Estimated completion time based on queue position"
    )
    
    # Worker assignment
    worker_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID of the background worker processing this batch"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('queued', 'Queued'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        default='queued'
    )
    
    # Timestamps
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When processing started"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When processing completed"
    )
    
    # Retry logic
    retry_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of retry attempts"
    )
    
    max_retries = models.PositiveIntegerField(
        default=3,
        help_text="Maximum number of retry attempts"
    )
    
    last_error = models.TextField(
        blank=True,
        help_text="Last error message if processing failed"
    )
    
    class Meta:
        ordering = ['priority', 'queue_position', 'queued_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['queue_position']),
        ]
    
    def __str__(self):
        return f"Queue item for batch {self.batch_request.batch_id.hex[:8]} (position: {self.queue_position})"
    
    def start_processing(self, worker_id):
        """Mark this queue item as started processing."""
        from django.utils import timezone
        
        self.status = 'processing'
        self.worker_id = worker_id
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'worker_id', 'started_at'])
    
    def complete_processing(self, success=True, error_message=""):
        """Mark this queue item as completed."""
        from django.utils import timezone
        
        if success:
            self.status = 'completed'
        else:
            self.status = 'failed'
            self.last_error = error_message
            
            # Schedule retry if under limit
            if self.retry_count < self.max_retries:
                self.retry_count += 1
                self.status = 'queued'
                self.worker_id = ''
                self.started_at = None
                # Re-queue with lower priority
                self.queue_position = BatchProcessingQueue.objects.filter(
                    status='queued'
                ).count() + 1
        
        self.completed_at = timezone.now()
        self.save(update_fields=[
            'status', 'last_error', 'retry_count', 'queue_position', 
            'worker_id', 'started_at', 'completed_at'
        ])