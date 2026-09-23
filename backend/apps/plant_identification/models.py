"""
Plant identification models for the Plant Community application.

This module contains models for plant data, identification requests, and results.
"""

import uuid

from apps.core.validators import validate_plant_identification_image
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F
from django.urls import reverse
from imagekit.models import ImageSpecField, ProcessedImageField
from imagekit.processors import ResizeToFill, ResizeToFit
from taggit.managers import TaggableManager

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
        help_text="Unique identifier for secure references",
    )

    # Basic Information
    scientific_name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Scientific binomial name (e.g., Rosa damascena)",
    )

    common_names = models.TextField(
        blank=True, help_text="Common names separated by commas"
    )

    family = models.CharField(max_length=100, blank=True, help_text="Plant family name")

    genus = models.CharField(max_length=100, blank=True, help_text="Plant genus")

    species = models.CharField(max_length=100, blank=True, help_text="Species name")

    # External API IDs
    trefle_id = models.CharField(
        max_length=50, blank=True, null=True, help_text="Trefle API plant ID"
    )

    plantnet_id = models.CharField(
        max_length=50, blank=True, null=True, help_text="PlantNet API plant ID"
    )

    # Plant Characteristics
    plant_type = models.CharField(
        max_length=50,
        choices=[
            ("tree", "Tree"),
            ("shrub", "Shrub"),
            ("herb", "Herb"),
            ("grass", "Grass"),
            ("fern", "Fern"),
            ("moss", "Moss"),
            ("succulent", "Succulent"),
            ("vine", "Vine"),
            ("annual", "Annual"),
            ("perennial", "Perennial"),
            ("biennial", "Biennial"),
        ],
        blank=True,
    )

    growth_habit = models.CharField(
        max_length=100,
        blank=True,
        help_text="How the plant grows (e.g., climbing, spreading, upright)",
    )

    mature_height_min = models.FloatField(
        null=True, blank=True, help_text="Minimum mature height in meters"
    )

    mature_height_max = models.FloatField(
        null=True, blank=True, help_text="Maximum mature height in meters"
    )

    # Care Information
    light_requirements = models.CharField(
        max_length=20,
        choices=[
            ("full_sun", "Full Sun"),
            ("partial_sun", "Partial Sun"),
            ("partial_shade", "Partial Shade"),
            ("full_shade", "Full Shade"),
        ],
        blank=True,
    )

    water_requirements = models.CharField(
        max_length=20,
        choices=[
            ("low", "Low"),
            ("moderate", "Moderate"),
            ("high", "High"),
        ],
        blank=True,
    )

    soil_ph_min = models.FloatField(
        null=True, blank=True, help_text="Minimum soil pH tolerance"
    )

    soil_ph_max = models.FloatField(
        null=True, blank=True, help_text="Maximum soil pH tolerance"
    )

    hardiness_zone_min = models.IntegerField(
        null=True, blank=True, help_text="Minimum USDA hardiness zone"
    )

    hardiness_zone_max = models.IntegerField(
        null=True, blank=True, help_text="Maximum USDA hardiness zone"
    )

    # Additional Information
    description = models.TextField(
        blank=True, help_text="General description of the plant"
    )

    native_regions = models.TextField(
        blank=True, help_text="Native regions and countries"
    )

    bloom_time = models.CharField(
        max_length=100, blank=True, help_text="When the plant typically blooms"
    )

    flower_color = models.CharField(
        max_length=100, blank=True, help_text="Typical flower colors"
    )

    # Images
    primary_image = models.ImageField(
        upload_to="plants/species/",
        null=True,
        blank=True,
        help_text="Primary image of the plant",
    )

    primary_image_thumbnail = ImageSpecField(
        source="primary_image",
        processors=[ResizeToFill(300, 300)],
        format="JPEG",
        options={"quality": 85},
    )

    # Tags and Classification
    tags = TaggableManager(
        blank=True,
        help_text="Tags for categorizing plants (e.g., medicinal, edible, toxic)",
    )

    # Status and Metadata
    is_verified = models.BooleanField(
        default=False, help_text="Has this species been verified by an expert?"
    )

    verification_source = models.CharField(
        max_length=200,
        blank=True,
        help_text="Source of verification (e.g., botanist name, institution)",
    )

    # Auto-storage tracking (NEW: for ≥50% confidence plant IDs)
    auto_stored = models.BooleanField(
        default=False,
        help_text="Was this species auto-stored from a high-confidence identification (≥50%)?",
    )

    confidence_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Highest confidence score from identifications that created this species",
    )

    identification_count = models.PositiveIntegerField(
        default=0, help_text="Number of times this species has been identified"
    )

    api_source = models.CharField(
        max_length=50,
        choices=[
            ("manual", "Manual Entry"),
            ("plantnet", "PlantNet API"),
            ("trefle", "Trefle API"),
            ("combined", "Combined APIs"),
            ("community", "Community Contributed"),
        ],
        default="manual",
        help_text="Primary source where this species data came from",
    )

    community_confirmed = models.BooleanField(
        default=False, help_text="Has this species been confirmed by community voting?"
    )

    expert_reviewed = models.BooleanField(
        default=False, help_text="Has this species been reviewed by a plant expert?"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scientific_name"]
        verbose_name = "Plant Species"
        verbose_name_plural = "Plant Species"

    def __str__(self):
        return self.scientific_name

    def get_absolute_url(self):
        return reverse("plant_identification:species_detail", kwargs={"pk": self.pk})

    @property
    def display_name(self):
        """Return the best display name for the species."""
        if self.common_names:
            first_common = self.common_names.split(",")[0].strip()
            return f"{first_common} ({self.scientific_name})"
        return self.scientific_name

    @property
    def common_names_list(self):
        """Return common names as a list."""
        if self.common_names:
            return [name.strip() for name in self.common_names.split(",")]
        return []

    def update_confidence_score(self, new_confidence: float):
        """Update the confidence score if this is higher than the current one."""
        if self.confidence_score is None or new_confidence > self.confidence_score:
            self.confidence_score = new_confidence

    def increment_identification_count(self):
        """Increment the count of identifications for this species atomically."""
        PlantSpecies.objects.filter(id=self.id).update(
            identification_count=F("identification_count") + 1
        )
        self.refresh_from_db()

    @staticmethod
    def should_auto_store(confidence: float) -> bool:
        """Static method to check if a confidence score qualifies for auto-storage."""
        return confidence >= 0.5


class RequestImagesMixin:
    """Shared ``images`` / ``image_thumbnails`` aggregation for request models.

    ``PlantIdentificationRequest`` and ``PlantDiseaseRequest`` both expose up to
    three image slots (``image_1..3``) with matching thumbnails; these properties
    collect the populated ones into a list. Single-sourced here (todo 223 / L3) —
    they were byte-identical copies, the model-layer twin of the serializer dedup
    in todo 221 / M4. Properties only, so this adds no DB fields or migrations.
    """

    @property
    def images(self):
        """Return a list of all uploaded images (image_1 plus any populated extras)."""
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


class PlantIdentificationRequest(RequestImagesMixin, models.Model):
    """
    Model representing a user's request to identify a plant.

    CASCADE POLICY:
    - user: CASCADE (user's identification requests deleted with user per GDPR)
    - assigned_to_collection: SET_NULL (preserves request if collection deleted)
    """

    # Request ID for tracking
    request_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique identifier for this identification request",
    )

    # User who made the request
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="plant_identification_requests",
    )

    # Plant Images
    image_1 = ProcessedImageField(
        upload_to="plants/identifications/",
        processors=[ResizeToFit(1200, 1200)],
        format="JPEG",
        options={"quality": 90},
        validators=[validate_plant_identification_image],
        help_text="Primary image of the plant",
    )

    image_1_thumbnail = ImageSpecField(
        source="image_1",
        processors=[ResizeToFill(300, 300)],
        format="JPEG",
        options={"quality": 85},
    )

    image_2 = ProcessedImageField(
        upload_to="plants/identifications/",
        processors=[ResizeToFit(1200, 1200)],
        format="JPEG",
        options={"quality": 90},
        validators=[validate_plant_identification_image],
        null=True,
        blank=True,
        help_text="Optional second image",
    )

    image_2_thumbnail = ImageSpecField(
        source="image_2",
        processors=[ResizeToFill(300, 300)],
        format="JPEG",
        options={"quality": 85},
    )

    image_3 = ProcessedImageField(
        upload_to="plants/identifications/",
        processors=[ResizeToFit(1200, 1200)],
        format="JPEG",
        options={"quality": 90},
        validators=[validate_plant_identification_image],
        null=True,
        blank=True,
        help_text="Optional third image",
    )

    image_3_thumbnail = ImageSpecField(
        source="image_3",
        processors=[ResizeToFill(300, 300)],
        format="JPEG",
        options={"quality": 85},
    )

    # Location and Context
    location = models.CharField(
        max_length=200, blank=True, help_text="Where was this plant found?"
    )

    latitude = models.FloatField(null=True, blank=True, help_text="GPS latitude")

    longitude = models.FloatField(null=True, blank=True, help_text="GPS longitude")

    # User Description
    description = models.TextField(
        blank=True, help_text="User's description of the plant"
    )

    plant_size = models.CharField(
        max_length=50,
        choices=[
            ("small", "Small (< 30cm)"),
            ("medium", "Medium (30cm - 1m)"),
            ("large", "Large (1m - 3m)"),
            ("very_large", "Very Large (> 3m)"),
        ],
        blank=True,
        help_text="Approximate size of the plant",
    )

    habitat = models.CharField(
        max_length=100,
        blank=True,
        help_text="Where was the plant growing? (e.g., garden, forest, field)",
    )

    # Request Status
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending Identification"),
            ("processing", "Processing with AI"),
            ("identified", "Identified"),
            ("needs_help", "Needs Community Help"),
            ("failed", "Identification Failed"),
        ],
        default="pending",
    )

    # AI Processing
    processed_by_ai = models.BooleanField(
        default=False, help_text="Has this been processed by AI identification?"
    )

    ai_processing_date = models.DateTimeField(
        null=True, blank=True, help_text="When was this processed by AI?"
    )

    # Community Collection Assignment
    assigned_to_collection = models.ForeignKey(
        "users.UserPlantCollection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="identification_requests",
        help_text="User's collection this plant was added to",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Plant ID Request #{self.request_id.hex[:8]} by {self.user.username}"

    def get_absolute_url(self):
        return reverse(
            "plant_identification:request_detail",
            kwargs={"request_id": self.request_id},
        )

    # images / image_thumbnails provided by RequestImagesMixin (todo 223 / L3)


class PlantIdentificationResult(models.Model):
    """
    Model representing an identification result for a plant request.

    CASCADE POLICY:
    - request: CASCADE (identification results are meaningless without the request)
    - identified_species: SET_NULL (preserves historical research data if species deleted)
    - identified_by: CASCADE (community/expert identifications deleted with user per GDPR)
    """

    # UUID for secure references (prevents IDOR attacks)
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references",
    )

    # Link to the identification request
    request = models.ForeignKey(
        PlantIdentificationRequest,
        on_delete=models.CASCADE,
        related_name="identification_results",
    )

    # Identified species (if matched to database)
    # CASCADE POLICY: SET_NULL to preserve historical identification data
    # If a species is removed from the database, the identification result
    # remains with suggested_scientific_name and suggested_common_name as fallback
    identified_species = models.ForeignKey(
        PlantSpecies,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="identification_results",
        help_text="Identified species from database. SET_NULL preserves research data.",
    )

    # Alternative identification (if species not in database)
    suggested_scientific_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Suggested scientific name if not in our database",
    )

    suggested_common_name = models.CharField(
        max_length=200, blank=True, help_text="Suggested common name"
    )

    # Confidence and Source
    confidence_score = models.FloatField(
        null=False,
        blank=False,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score (0.0 to 1.0)",
    )

    identification_source = models.CharField(
        max_length=20,
        null=False,
        blank=False,
        choices=[
            ("ai_trefle", "AI - Trefle API"),
            ("ai_plantnet", "AI - PlantNet API"),
            ("ai_combined", "AI - Combined APIs"),
            ("community", "Community Identification"),
            ("expert", "Expert Identification"),
            ("user_manual", "Manual User Entry"),
        ],
    )

    # User who provided this identification (for community/expert IDs)
    identified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="plant_identifications_given",
    )

    # Additional Information
    notes = models.TextField(
        blank=True, help_text="Additional notes about this identification"
    )

    # External API Response Data
    api_response_data = models.JSONField(
        null=True, blank=True, help_text="Raw API response data for debugging"
    )

    # Voting System for Community IDs
    upvotes = models.PositiveIntegerField(
        default=0, help_text="Number of users who agree with this identification"
    )

    downvotes = models.PositiveIntegerField(
        default=0, help_text="Number of users who disagree with this identification"
    )

    # Status
    is_accepted = models.BooleanField(
        default=False, help_text="Has the requesting user accepted this identification?"
    )

    is_primary = models.BooleanField(
        default=False,
        help_text="Is this the primary/best identification for this request?",
    )

    # AI-Generated Care Instructions
    ai_care_instructions = models.JSONField(
        null=True, blank=True, help_text="AI-generated care instructions for this plant"
    )

    care_instructions_generated_at = models.DateTimeField(
        null=True, blank=True, help_text="When care instructions were generated"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-confidence_score", "-created_at"]
        indexes = [
            models.Index(fields=["request", "-confidence_score"]),
            models.Index(fields=["identified_species"]),
            models.Index(fields=["-created_at"]),
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
                return (
                    f"{self.suggested_common_name} ({self.suggested_scientific_name})"
                )
            return self.suggested_scientific_name
        return self.suggested_common_name or "Unknown Species"

    @property
    def vote_score(self):
        """Calculate the net vote score."""
        return self.upvotes - self.downvotes


class UserPlant(models.Model):
    """
    Model representing a plant in a user's collection.

    CASCADE POLICY:
    - user: CASCADE (user's plants deleted with user per GDPR right to be forgotten)
    - collection: CASCADE (plants belong to a collection, deleted if collection removed)
    - species: SET_NULL (preserves user's plant records even if species removed from database)
    - from_identification_request: SET_NULL (preserves link to historical identification)
    - from_identification_result: SET_NULL (preserves link to historical identification)
    """

    # UUID for secure references (prevents IDOR attacks)
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references",
    )

    # Link to user and collection
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plants"
    )

    collection = models.ForeignKey(
        "users.UserPlantCollection", on_delete=models.CASCADE, related_name="plants"
    )

    # Plant Information
    # CASCADE POLICY: SET_NULL to preserve user's plant records
    # If a species is removed from the database, the user's plant remains
    # with nickname and other metadata intact
    species = models.ForeignKey(
        PlantSpecies,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_plants",
        help_text="Species from database. SET_NULL preserves user plant records.",
    )

    # Custom name given by user
    nickname = models.CharField(
        max_length=100, blank=True, help_text="Personal name for this plant"
    )

    # Care tracking
    acquisition_date = models.DateField(
        null=True, blank=True, help_text="When did you get this plant?"
    )

    location_in_home = models.CharField(
        max_length=100,
        blank=True,
        help_text="Where is this plant located? (e.g., living room window)",
    )

    notes = models.TextField(blank=True, help_text="Personal notes about this plant")

    # Status
    is_alive = models.BooleanField(default=True, help_text="Is this plant still alive?")

    is_public = models.BooleanField(
        default=True, help_text="Show this plant in your public collection?"
    )

    # Link to original identification request
    from_identification_request = models.ForeignKey(
        PlantIdentificationRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collection_plants",
        help_text="Original identification request that led to this plant",
    )

    # Link to identification result (NEW)
    from_identification_result = models.ForeignKey(
        PlantIdentificationResult,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collection_plants",
        help_text="Specific identification result that was accepted",
    )

    # AI-generated care instructions (NEW)
    care_instructions_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="AI-generated or custom care instructions for this plant",
    )

    # Images
    image = models.ImageField(
        upload_to="plants/collections/",
        null=True,
        blank=True,
        help_text="Current photo of your plant",
    )

    image_thumbnail = ImageSpecField(
        source="image",
        processors=[ResizeToFill(300, 300)],
        format="JPEG",
        options={"quality": 85},
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["user", "collection", "species", "nickname"]

    def __str__(self):
        name = self.nickname or (
            self.species.display_name if self.species else "Unknown Plant"
        )
        return f"{self.user.username}'s {name}"

    def get_absolute_url(self):
        return reverse("plant_identification:user_plant_detail", kwargs={"pk": self.pk})

    @property
    def display_name(self):
        """Return the best display name for this plant."""
        if self.nickname:
            return self.nickname
        elif self.species:
            return self.species.display_name
        return "Unknown Plant"


class PlantDiseaseRequest(RequestImagesMixin, models.Model):
    """
    Model representing a user's request to diagnose plant diseases.
    """

    # Request ID for tracking
    request_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique identifier for this disease diagnosis request",
    )

    # User who made the request
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="plant_disease_requests",
    )

    # Link to original plant identification (optional)
    plant_identification_request = models.ForeignKey(
        PlantIdentificationRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="disease_diagnosis_requests",
        help_text="Original plant ID request this disease diagnosis is based on",
    )

    # Plant species (if known)
    plant_species = models.ForeignKey(
        PlantSpecies,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disease_requests",
        help_text="Known plant species with disease symptoms",
    )

    # Disease Symptom Images
    image_1 = ProcessedImageField(
        upload_to="plants/diseases/",
        processors=[ResizeToFit(1200, 1200)],
        format="JPEG",
        options={"quality": 90},
        validators=[validate_plant_identification_image],
        help_text="Primary image showing disease symptoms",
    )

    image_1_thumbnail = ImageSpecField(
        source="image_1",
        processors=[ResizeToFill(300, 300)],
        format="JPEG",
        options={"quality": 85},
    )

    image_2 = ProcessedImageField(
        upload_to="plants/diseases/",
        processors=[ResizeToFit(1200, 1200)],
        format="JPEG",
        options={"quality": 90},
        validators=[validate_plant_identification_image],
        null=True,
        blank=True,
        help_text="Optional second symptom image",
    )

    image_2_thumbnail = ImageSpecField(
        source="image_2",
        processors=[ResizeToFill(300, 300)],
        format="JPEG",
        options={"quality": 85},
    )

    image_3 = ProcessedImageField(
        upload_to="plants/diseases/",
        processors=[ResizeToFit(1200, 1200)],
        format="JPEG",
        options={"quality": 90},
        validators=[validate_plant_identification_image],
        null=True,
        blank=True,
        help_text="Optional third symptom image",
    )

    image_3_thumbnail = ImageSpecField(
        source="image_3",
        processors=[ResizeToFill(300, 300)],
        format="JPEG",
        options={"quality": 85},
    )

    # Symptom Description
    symptoms_description = models.TextField(
        blank=True, help_text="User's description of symptoms observed"
    )

    # Plant condition details
    plant_condition = models.CharField(
        max_length=20,
        choices=[
            ("excellent", "Excellent - minor symptoms"),
            ("good", "Good - some concerning symptoms"),
            ("fair", "Fair - moderate damage visible"),
            ("poor", "Poor - significant damage"),
            ("critical", "Critical - plant may die"),
        ],
        blank=True,
        help_text="Overall condition of the plant",
    )

    # Location and Environmental Context
    location = models.CharField(
        max_length=200, blank=True, help_text="Where is this plant located?"
    )

    # Environmental factors
    recent_weather = models.CharField(
        max_length=200,
        blank=True,
        help_text="Recent weather conditions (rain, drought, temperature changes)",
    )

    recent_care_changes = models.TextField(
        blank=True,
        help_text="Any recent changes in watering, fertilizing, location, etc.",
    )

    # Request Status
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending Diagnosis"),
            ("processing", "Processing with AI"),
            ("diagnosed", "Disease Diagnosed"),
            ("needs_help", "Needs Community Help"),
            ("failed", "Diagnosis Failed"),
        ],
        default="pending",
    )

    # AI Processing
    processed_by_ai = models.BooleanField(
        default=False, help_text="Has this been processed by AI diagnosis?"
    )

    ai_processing_date = models.DateTimeField(
        null=True, blank=True, help_text="When was this processed by AI?"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Disease Diagnosis #{self.request_id.hex[:8]} by {self.user.username}"

    def get_absolute_url(self):
        return reverse(
            "plant_identification:disease_request_detail",
            kwargs={"request_id": self.request_id},
        )

    # images / image_thumbnails provided by RequestImagesMixin (todo 223 / L3)


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
        help_text="Unique identifier for secure references",
    )

    # Disease Information
    disease_name = models.CharField(
        max_length=200, unique=True, help_text="Common name of the disease"
    )

    scientific_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Scientific name of the pathogen if available",
    )

    disease_type = models.CharField(
        max_length=20,
        choices=[
            ("fungal", "Fungal Disease"),
            ("bacterial", "Bacterial Disease"),
            ("viral", "Viral Disease"),
            ("pest", "Pest/Insect Damage"),
            ("abiotic", "Abiotic/Environmental"),
            ("deficiency", "Nutrient Deficiency"),
            ("toxicity", "Toxicity/Poisoning"),
        ],
        help_text="Type of disease or problem",
    )

    severity_levels = models.JSONField(
        default=list, help_text="Array of severity levels (mild, moderate, severe)"
    )

    # Symptoms
    symptoms = models.JSONField(
        default=dict, help_text="Structured symptom data from API responses"
    )

    # Affected Plants
    affected_plant_families = models.JSONField(
        default=list, help_text="Plant families commonly affected by this disease"
    )

    affected_plants = models.ManyToManyField(
        PlantSpecies,
        blank=True,
        related_name="known_diseases",
        help_text="Specific plant species affected",
    )

    # Environmental factors
    seasonal_patterns = models.JSONField(
        default=dict,
        help_text="When this disease typically occurs (seasons, weather conditions)",
    )

    environmental_triggers = models.JSONField(
        default=list, help_text="Environmental conditions that trigger this disease"
    )

    # Storage metadata
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Minimum confidence score from diagnoses (≥0.5 required)",
    )

    api_source = models.CharField(
        max_length=50,
        choices=[
            ("plant_health", "plant.health API"),
            ("plantnet", "PlantNet API"),
            ("manual", "Manual Entry"),
            ("community", "Community Contributed"),
        ],
        default="plant_health",
        help_text="Source of this disease information",
    )

    diagnosis_count = models.PositiveIntegerField(
        default=1, help_text="Number of times this disease has been diagnosed"
    )

    # Community data
    community_confirmed = models.BooleanField(
        default=False, help_text="Has this been confirmed by community voting?"
    )

    expert_reviewed = models.BooleanField(
        default=False, help_text="Has this been reviewed by a plant health expert?"
    )

    # Additional Information
    description = models.TextField(
        blank=True, help_text="General description of the disease"
    )

    prevention_tips = models.TextField(
        blank=True, help_text="How to prevent this disease"
    )

    # Images
    reference_image = models.ImageField(
        upload_to="diseases/reference/",
        null=True,
        blank=True,
        help_text="Reference image showing typical symptoms",
    )

    reference_image_thumbnail = ImageSpecField(
        source="reference_image",
        processors=[ResizeToFill(300, 300)],
        format="JPEG",
        options={"quality": 85},
    )

    # Timestamps
    first_diagnosed = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-diagnosis_count", "disease_name"]
        verbose_name = "Disease Database Entry"
        verbose_name_plural = "Disease Database Entries"

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
        help_text="Unique identifier for secure references",
    )

    # Link to disease
    disease = models.ForeignKey(
        PlantDiseaseDatabase, on_delete=models.CASCADE, related_name="care_instructions"
    )

    # Treatment Information
    treatment_name = models.CharField(
        max_length=200, help_text="Name of the treatment method"
    )

    treatment_type = models.CharField(
        max_length=20,
        choices=[
            ("organic", "Organic Treatment"),
            ("chemical", "Chemical Treatment"),
            ("cultural", "Cultural/Management"),
            ("biological", "Biological Control"),
            ("preventive", "Preventive Measure"),
        ],
        help_text="Type of treatment approach",
    )

    # Instructions
    instructions = models.TextField(help_text="Detailed treatment instructions")

    application_timing = models.TextField(
        blank=True, help_text="When and how often to apply this treatment"
    )

    materials_needed = models.JSONField(
        default=list, help_text="List of materials/products needed"
    )

    # Effectiveness
    effectiveness_score = models.FloatField(
        default=0.0, help_text="Community-rated effectiveness (0.0 to 1.0)"
    )

    success_rate = models.FloatField(
        null=True, blank=True, help_text="Percentage success rate if known"
    )

    # Community feedback
    community_votes = models.PositiveIntegerField(
        default=0, help_text="Total community votes received"
    )

    positive_votes = models.PositiveIntegerField(
        default=0, help_text="Positive 'this worked for me' votes"
    )

    negative_votes = models.PositiveIntegerField(
        default=0, help_text="Negative 'this didn't work' votes"
    )

    # Additional Information
    cost_estimate = models.CharField(
        max_length=20,
        choices=[
            ("free", "Free"),
            ("low", "Low Cost ($1-10)"),
            ("medium", "Medium Cost ($10-50)"),
            ("high", "High Cost ($50+)"),
        ],
        blank=True,
        help_text="Estimated cost of treatment",
    )

    difficulty_level = models.CharField(
        max_length=20,
        choices=[
            ("easy", "Easy - Anyone can do"),
            ("moderate", "Moderate - Some experience needed"),
            ("difficult", "Difficult - Expert knowledge required"),
        ],
        default="easy",
        help_text="Difficulty level of applying treatment",
    )

    safety_notes = models.TextField(
        blank=True, help_text="Safety precautions and warnings"
    )

    # Source and validation
    source = models.CharField(
        max_length=20,
        choices=[
            ("api", "API Response"),
            ("community", "Community Contributed"),
            ("expert", "Expert Recommendation"),
            ("research", "Research/Scientific"),
        ],
        default="api",
        help_text="Source of this treatment information",
    )

    verified_by_expert = models.BooleanField(
        default=False, help_text="Has this been verified by a plant health expert?"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effectiveness_score", "-positive_votes", "treatment_name"]
        unique_together = ["disease", "treatment_name"]

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

    CASCADE POLICY:
    - request: CASCADE (diagnosis results are meaningless without the request)
    - identified_disease: SET_NULL (preserves historical diagnosis data if disease deleted)
    - diagnosed_by: CASCADE (community/expert diagnoses deleted with user per GDPR)
    """

    # UUID for secure references
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references",
    )

    # Link to the diagnosis request
    request = models.ForeignKey(
        PlantDiseaseRequest, on_delete=models.CASCADE, related_name="diagnosis_results"
    )

    # Disease identification
    # CASCADE POLICY: SET_NULL to preserve historical diagnosis data
    # If a disease is removed from the database, the diagnosis result
    # remains with suggested_disease_name and suggested_disease_type as fallback
    identified_disease = models.ForeignKey(
        PlantDiseaseDatabase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diagnosis_results",
        help_text="Disease identified from our local database. SET_NULL preserves historical data.",
    )

    # Alternative identification (if not in local database yet)
    suggested_disease_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Disease name from API if not in our database",
    )

    suggested_disease_type = models.CharField(
        max_length=20,
        choices=[
            ("fungal", "Fungal Disease"),
            ("bacterial", "Bacterial Disease"),
            ("viral", "Viral Disease"),
            ("pest", "Pest/Insect Damage"),
            ("abiotic", "Abiotic/Environmental"),
            ("deficiency", "Nutrient Deficiency"),
            ("toxicity", "Toxicity/Poisoning"),
        ],
        blank=True,
        help_text="Type of disease suggested by API",
    )

    # Confidence and Source
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score (0.0 to 1.0)",
    )

    diagnosis_source = models.CharField(
        max_length=20,
        choices=[
            ("local_db", "Local Database"),
            ("api_plant_health", "plant.health API"),
            ("api_combined", "Combined APIs"),
            ("community", "Community Diagnosis"),
            ("expert", "Expert Diagnosis"),
        ],
    )

    # User who provided this diagnosis (for community diagnoses)
    diagnosed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="disease_diagnoses_given",
    )

    # Diagnosis details
    symptoms_identified = models.JSONField(
        default=list, help_text="List of symptoms identified in the images"
    )

    severity_assessment = models.CharField(
        max_length=20,
        choices=[
            ("mild", "Mild - Early symptoms"),
            ("moderate", "Moderate - Noticeable damage"),
            ("severe", "Severe - Significant damage"),
            ("critical", "Critical - Plant in danger"),
        ],
        blank=True,
        help_text="Assessed severity of the disease",
    )

    # Treatment recommendations
    recommended_treatments = models.JSONField(
        default=list, help_text="List of recommended treatment IDs or names"
    )

    immediate_actions = models.TextField(
        blank=True, help_text="Immediate actions the user should take"
    )

    # Additional Information
    notes = models.TextField(
        blank=True, help_text="Additional notes about this diagnosis"
    )

    # External API Response Data
    api_response_data = models.JSONField(
        null=True, blank=True, help_text="Raw API response data for debugging"
    )

    # Community validation
    community_confirmed = models.BooleanField(
        default=False, help_text="Has this diagnosis been confirmed by community votes?"
    )

    upvotes = models.PositiveIntegerField(
        default=0, help_text="Number of users who agree with this diagnosis"
    )

    downvotes = models.PositiveIntegerField(
        default=0, help_text="Number of users who disagree with this diagnosis"
    )

    # Status
    is_accepted = models.BooleanField(
        default=False, help_text="Has the requesting user accepted this diagnosis?"
    )

    is_primary = models.BooleanField(
        default=False, help_text="Is this the primary/best diagnosis for this request?"
    )

    # Auto-storage flag
    stored_to_database = models.BooleanField(
        default=False,
        help_text="Has this high-confidence result been stored to local database?",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-confidence_score", "-created_at"]
        indexes = [
            models.Index(fields=["request", "-confidence_score"]),
            models.Index(fields=["identified_disease"]),
            models.Index(fields=["-created_at"]),
            models.Index(
                fields=["confidence_score"]
            ),  # For filtering high-confidence results
        ]

    def __str__(self):
        disease_name = (
            self.identified_disease.disease_name
            if self.identified_disease
            else self.suggested_disease_name
        )
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


class SavedCareInstructions(models.Model):
    """
    Model for user's saved plant care instruction cards.

    CASCADE POLICY:
    - user: CASCADE (user's saved care instructions deleted with user per GDPR)
    - plant_species: SET_NULL (preserves saved instructions with fallback to plant_scientific_name)
    """

    # UUID for secure references
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for secure references",
    )

    # User who saved this care card
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_care_instructions",
    )

    # Plant information
    # CASCADE POLICY: SET_NULL to preserve user's saved care instructions
    # If a species is removed from the database, the care card remains
    # with plant_scientific_name and plant_common_name as fallback
    plant_species = models.ForeignKey(
        PlantSpecies,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Plant species this care card is for. SET_NULL preserves saved care instructions.",
    )

    # Plant identification info (if saved from an identification result)
    plant_scientific_name = models.CharField(
        max_length=200, help_text="Scientific name of the plant"
    )

    plant_common_name = models.CharField(
        max_length=200, blank=True, help_text="Common name of the plant"
    )

    plant_family = models.CharField(
        max_length=100, blank=True, help_text="Plant family"
    )

    # Care instructions data (JSON)
    care_instructions_data = models.JSONField(
        help_text="Full care instructions data from the API"
    )

    # User's notes and experience
    personal_notes = models.TextField(
        blank=True, help_text="User's personal notes and experiences with this plant"
    )

    custom_nickname = models.CharField(
        max_length=100, blank=True, help_text="User's custom nickname for this plant"
    )

    # Care tracking
    care_difficulty_experienced = models.CharField(
        max_length=20,
        choices=[
            ("very_easy", "Very Easy"),
            ("easy", "Easy"),
            ("moderate", "Moderate"),
            ("challenging", "Challenging"),
            ("difficult", "Difficult"),
        ],
        null=True,
        blank=True,
        help_text="User's experienced difficulty level",
    )

    current_status = models.CharField(
        max_length=20,
        choices=[
            ("planning", "Planning to Get"),
            ("newly_acquired", "Recently Acquired"),
            ("thriving", "Thriving"),
            ("struggling", "Having Issues"),
            ("recovered", "Recovered from Problems"),
            ("lost", "Plant Lost"),
        ],
        default="planning",
        help_text="Current status of user's plant",
    )

    # Sharing preferences
    share_with_community = models.BooleanField(
        default=False, help_text="Share this care experience with the community"
    )

    is_favorite = models.BooleanField(
        default=False, help_text="Mark as favorite care card"
    )

    # Timestamps
    saved_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_viewed_at = models.DateTimeField(
        null=True, blank=True, help_text="Last time user viewed this care card"
    )

    class Meta:
        ordering = ["-saved_at"]
        unique_together = ["user", "plant_scientific_name"]

    def __str__(self):
        display_name = (
            self.custom_nickname or self.plant_common_name or self.plant_scientific_name
        )
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
        self.save(update_fields=["last_viewed_at"])


class PlantIdentificationVote(models.Model):
    """
    Model to track user votes on identification results for persistence across sessions.
    """

    VOTE_CHOICES = [
        ("upvote", "Upvote"),
        ("downvote", "Downvote"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="identification_votes",
    )

    result = models.ForeignKey(
        PlantIdentificationResult, on_delete=models.CASCADE, related_name="user_votes"
    )

    vote_type = models.CharField(
        max_length=10, choices=VOTE_CHOICES, help_text="Type of vote cast by the user"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "result"]  # One vote per user per result
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} voted {self.vote_type} on result {self.result.id}"
