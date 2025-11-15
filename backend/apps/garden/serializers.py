"""
Garden Planner Serializers

DRF serializers for garden planning API endpoints with:
- Nested relationships for complete data retrieval
- Validation for file uploads and JSON fields
- Read-only computed fields
- User-scoped filtering
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Garden,
    GardenPlant,
    CareReminder,
    Task,
    PestIssue,
    PestImage,
    JournalEntry,
    JournalImage,
    PlantCareLibrary
)
from .constants import (
    MAX_GARDEN_PLANT_IMAGE_SIZE,
    MAX_PEST_IMAGE_SIZE,
    MAX_JOURNAL_IMAGE_SIZE,
    MAX_PEST_IMAGES_PER_ISSUE,
    MAX_JOURNAL_IMAGES_PER_ENTRY,
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_IMAGE_MIME_TYPES,
    MAX_GARDEN_WIDTH_FT,
    MAX_GARDEN_HEIGHT_FT,
    MAX_GARDEN_WIDTH_M,
    MAX_GARDEN_HEIGHT_M
)

User = get_user_model()


class PlantCareLibrarySerializer(serializers.ModelSerializer):
    """
    Plant care reference data serializer.

    Provides care instructions, compatibility, and frequency defaults.
    Read-only for regular users (staff can edit via admin).
    """

    class Meta:
        model = PlantCareLibrary
        fields = [
            'id',
            'scientific_name',
            'common_names',
            'family',
            'sunlight',
            'water_needs',
            'soil_type',
            'hardiness_zones',
            'care_instructions',
            'watering_frequency_days',
            'fertilizing_frequency_days',
            'pruning_frequency_days',
            'companion_plants',
            'enemy_plants',
            'common_pests',
            'common_diseases',
            'notes',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PestImageSerializer(serializers.ModelSerializer):
    """Pest issue image serializer with validation."""

    class Meta:
        model = PestImage
        fields = ['id', 'image', 'uploaded_at']
        read_only_fields = ['uploaded_at']

    def validate_image(self, value):
        """Validate image file size and type."""
        # File size validation
        if value.size > MAX_PEST_IMAGE_SIZE:
            raise serializers.ValidationError(
                f"Image size must not exceed {MAX_PEST_IMAGE_SIZE / (1024*1024):.1f}MB"
            )

        # Extension validation
        file_extension = value.name.split('.')[-1].lower()
        if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise serializers.ValidationError(
                f"Invalid file extension. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
            )

        # MIME type validation (defense in depth)
        if value.content_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise serializers.ValidationError(
                f"Invalid MIME type. Allowed: {', '.join(ALLOWED_IMAGE_MIME_TYPES)}"
            )

        return value


class JournalImageSerializer(serializers.ModelSerializer):
    """Journal entry image serializer with validation."""

    class Meta:
        model = JournalImage
        fields = ['id', 'image', 'caption', 'uploaded_at']
        read_only_fields = ['uploaded_at']

    def validate_image(self, value):
        """Validate image file size and type."""
        # File size validation
        if value.size > MAX_JOURNAL_IMAGE_SIZE:
            raise serializers.ValidationError(
                f"Image size must not exceed {MAX_JOURNAL_IMAGE_SIZE / (1024*1024):.1f}MB"
            )

        # Extension validation
        file_extension = value.name.split('.')[-1].lower()
        if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise serializers.ValidationError(
                f"Invalid file extension. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
            )

        # MIME type validation (defense in depth)
        if value.content_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise serializers.ValidationError(
                f"Invalid MIME type. Allowed: {', '.join(ALLOWED_IMAGE_MIME_TYPES)}"
            )

        return value


class PestIssueSerializer(serializers.ModelSerializer):
    """
    Pest/disease issue serializer with nested images.

    Supports multiple images (max 6) for documentation.
    """
    images = PestImageSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = PestIssue
        fields = [
            'id',
            'user',
            'garden_plant',
            'pest_type',
            'description',
            'identified_date',
            'severity',
            'treatment',
            'treatment_date',
            'resolved',
            'resolved_date',
            'notes',
            'images',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['user', 'identified_date', 'created_at', 'updated_at']


class JournalEntrySerializer(serializers.ModelSerializer):
    """
    Garden journal entry serializer with nested images.

    Supports multiple images (max 10) and weather snapshot data.
    """
    images = JournalImageSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            'id',
            'user',
            'garden',
            'garden_plant',
            'title',
            'content',
            'date',
            'weather_data',
            'tags',
            'images',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']


class CareReminderSerializer(serializers.ModelSerializer):
    """
    Care reminder serializer with recurrence support.

    Weather-aware scheduling handled by service layer.
    """
    user = serializers.StringRelatedField(read_only=True)
    reminder_type_display = serializers.CharField(
        source='get_reminder_type_display',
        read_only=True
    )

    class Meta:
        model = CareReminder
        fields = [
            'id',
            'user',
            'garden_plant',
            'reminder_type',
            'reminder_type_display',
            'custom_type_name',
            'scheduled_date',
            'recurring',
            'interval_days',
            'completed',
            'completed_at',
            'skipped',
            'skip_reason',
            'notes',
            'notification_sent',
            'created_at'
        ]
        read_only_fields = [
            'user',
            'completed_at',
            'notification_sent',
            'created_at'
        ]

    def validate(self, data):
        """Validate reminder type and interval consistency."""
        if data.get('reminder_type') == 'custom' and not data.get('custom_type_name'):
            raise serializers.ValidationError({
                'custom_type_name': 'Required when reminder_type is "custom"'
            })

        if data.get('recurring') and not data.get('interval_days'):
            raise serializers.ValidationError({
                'interval_days': 'Required for recurring reminders'
            })

        return data


class GardenPlantSerializer(serializers.ModelSerializer):
    """
    Garden plant instance serializer.

    Links to PlantSpecies for care data, tracks position and health.
    """
    reminders = CareReminderSerializer(many=True, read_only=True)
    pest_issues = PestIssueSerializer(many=True, read_only=True)
    journal_entries = JournalEntrySerializer(many=True, read_only=True)
    health_status_display = serializers.CharField(
        source='get_health_status_display',
        read_only=True
    )

    class Meta:
        model = GardenPlant
        fields = [
            'id',
            'garden',
            'plant_species',
            'common_name',
            'scientific_name',
            'planted_date',
            'position',
            'image',
            'notes',
            'health_status',
            'health_status_display',
            'reminders',
            'pest_issues',
            'journal_entries',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_image(self, value):
        """Validate plant image file size and type."""
        if value and value.size > MAX_GARDEN_PLANT_IMAGE_SIZE:
            raise serializers.ValidationError(
                f"Image size must not exceed {MAX_GARDEN_PLANT_IMAGE_SIZE / (1024*1024):.1f}MB"
            )

        if value:
            file_extension = value.name.split('.')[-1].lower()
            if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
                raise serializers.ValidationError(
                    f"Invalid file extension. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
                )

            if value.content_type not in ALLOWED_IMAGE_MIME_TYPES:
                raise serializers.ValidationError(
                    f"Invalid MIME type. Allowed: {', '.join(ALLOWED_IMAGE_MIME_TYPES)}"
                )

        return value

    def validate_position(self, value):
        """Validate position JSON format."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Position must be a JSON object")

        if 'x' not in value or 'y' not in value:
            raise serializers.ValidationError(
                "Position must include 'x' and 'y' coordinates"
            )

        if not isinstance(value['x'], (int, float)) or not isinstance(value['y'], (int, float)):
            raise serializers.ValidationError(
                "Position coordinates must be numbers"
            )

        return value


class TaskSerializer(serializers.ModelSerializer):
    """
    Seasonal gardening task serializer.

    Can be garden-specific or general user tasks.
    """
    user = serializers.StringRelatedField(read_only=True)
    category_display = serializers.CharField(
        source='get_category_display',
        read_only=True
    )
    season_display = serializers.CharField(
        source='get_season_display',
        read_only=True
    )
    priority_display = serializers.CharField(
        source='get_priority_display',
        read_only=True
    )

    class Meta:
        model = Task
        fields = [
            'id',
            'user',
            'garden',
            'title',
            'description',
            'due_date',
            'completed',
            'completed_at',
            'category',
            'category_display',
            'season',
            'season_display',
            'priority',
            'priority_display',
            'created_at'
        ]
        read_only_fields = ['user', 'completed_at', 'created_at']


class GardenSerializer(serializers.ModelSerializer):
    """
    Garden serializer with nested plants and layout data.

    Includes visual layout for drag-and-drop designer.
    """
    user = serializers.StringRelatedField(read_only=True)
    plants = GardenPlantSerializer(many=True, read_only=True)
    tasks = TaskSerializer(many=True, read_only=True)
    journal_entries = JournalEntrySerializer(many=True, read_only=True)
    visibility_display = serializers.CharField(
        source='get_visibility_display',
        read_only=True
    )
    plant_count = serializers.SerializerMethodField()

    class Meta:
        model = Garden
        fields = [
            'id',
            'user',
            'name',
            'description',
            'dimensions',
            'layout_data',
            'location',
            'climate_zone',
            'visibility',
            'visibility_display',
            'featured',
            'plants',
            'tasks',
            'journal_entries',
            'plant_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['user', 'featured', 'created_at', 'updated_at']

    def get_plant_count(self, obj):
        """Return total number of plants in garden."""
        return obj.plants.count()

    def validate_dimensions(self, value):
        """Validate dimensions JSON format and limits."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Dimensions must be a JSON object")

        required_fields = ['width', 'height', 'unit']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(
                    f"Dimensions must include '{field}'"
                )

        unit = value['unit']
        if unit not in ['ft', 'm']:
            raise serializers.ValidationError(
                "Unit must be 'ft' (feet) or 'm' (meters)"
            )

        width = value['width']
        height = value['height']

        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
            raise serializers.ValidationError(
                "Width and height must be numbers"
            )

        # Validate maximum dimensions
        if unit == 'ft':
            if width > MAX_GARDEN_WIDTH_FT or height > MAX_GARDEN_HEIGHT_FT:
                raise serializers.ValidationError(
                    f"Maximum dimensions: {MAX_GARDEN_WIDTH_FT}ft x {MAX_GARDEN_HEIGHT_FT}ft"
                )
        elif unit == 'm':
            if width > MAX_GARDEN_WIDTH_M or height > MAX_GARDEN_HEIGHT_M:
                raise serializers.ValidationError(
                    f"Maximum dimensions: {MAX_GARDEN_WIDTH_M}m x {MAX_GARDEN_HEIGHT_M}m"
                )

        if width <= 0 or height <= 0:
            raise serializers.ValidationError(
                "Width and height must be positive numbers"
            )

        return value

    def validate_location(self, value):
        """Validate location JSON format."""
        if value is None:
            return value

        if not isinstance(value, dict):
            raise serializers.ValidationError("Location must be a JSON object")

        if 'lat' in value and 'lng' in value:
            lat = value['lat']
            lng = value['lng']

            if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
                raise serializers.ValidationError(
                    "Latitude and longitude must be numbers"
                )

            if not (-90 <= lat <= 90):
                raise serializers.ValidationError(
                    "Latitude must be between -90 and 90"
                )

            if not (-180 <= lng <= 180):
                raise serializers.ValidationError(
                    "Longitude must be between -180 and 180"
                )

        return value

    def validate_layout_data(self, value):
        """Validate layout data JSON format."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Layout data must be a JSON object")

        return value


class GardenListSerializer(serializers.ModelSerializer):
    """
    Simplified garden serializer for list views.

    Excludes nested relationships for performance.
    """
    user = serializers.StringRelatedField(read_only=True)
    visibility_display = serializers.CharField(
        source='get_visibility_display',
        read_only=True
    )
    plant_count = serializers.SerializerMethodField()

    class Meta:
        model = Garden
        fields = [
            'id',
            'user',
            'name',
            'description',
            'dimensions',
            'climate_zone',
            'visibility',
            'visibility_display',
            'featured',
            'plant_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['user', 'featured', 'created_at', 'updated_at']

    def get_plant_count(self, obj):
        """Return total number of plants in garden."""
        return obj.plants.count()
