"""
Garden Calendar API Serializers

Serializers for community events, seasonal templates, and weather alerts.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..models import (
    CommunityEvent, EventAttendee, SeasonalTemplate, WeatherAlert,
    GardenBed, Plant, PlantImage, CareTask, CareLog, Harvest, GrowingZone
)

User = get_user_model()


class EventOrganizerSerializer(serializers.ModelSerializer):
    """Basic organizer information for event listings."""
    
    class Meta:
        model = User
        fields = ['uuid', 'username', 'first_name', 'last_name', 'avatar_thumbnail']
        read_only_fields = ['uuid', 'username', 'first_name', 'last_name', 'avatar_thumbnail']


class EventAttendeeSerializer(serializers.ModelSerializer):
    """Serializer for event attendees/RSVPs."""
    
    user = EventOrganizerSerializer(read_only=True)
    
    class Meta:
        model = EventAttendee
        fields = ['user', 'status', 'notes', 'created_at']
        read_only_fields = ['user', 'created_at']


class CommunityEventListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for event listings."""
    
    organizer = EventOrganizerSerializer(read_only=True)
    attendee_count = serializers.IntegerField(read_only=True)
    spots_remaining = serializers.IntegerField(read_only=True)
    is_past = serializers.BooleanField(read_only=True)
    duration_hours = serializers.FloatField(read_only=True)
    user_rsvp_status = serializers.SerializerMethodField()
    
    class Meta:
        model = CommunityEvent
        fields = [
            'uuid', 'title', 'description', 'event_type', 'organizer',
            'start_datetime', 'end_datetime', 'is_all_day',
            'location_name', 'city', 'hardiness_zone',
            'privacy_level', 'max_attendees', 'requires_rsvp',
            'attendee_count', 'spots_remaining', 'is_past', 'duration_hours',
            'weather_dependent', 'external_url', 'user_rsvp_status'
        ]
        read_only_fields = ['uuid', 'organizer', 'attendee_count', 'spots_remaining', 
                           'is_past', 'duration_hours', 'user_rsvp_status']
    
    def get_user_rsvp_status(self, obj):
        """Get current user's RSVP status for this event."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                attendee = obj.attendees.get(user=request.user)
                return attendee.status
            except EventAttendee.DoesNotExist:
                return None
        return None


class CommunityEventDetailSerializer(CommunityEventListSerializer):
    """Detailed serializer for individual events."""
    
    attendees = EventAttendeeSerializer(many=True, read_only=True)
    can_edit = serializers.SerializerMethodField()
    can_rsvp = serializers.SerializerMethodField()
    
    class Meta(CommunityEventListSerializer.Meta):
        fields = CommunityEventListSerializer.Meta.fields + [
            'address', 'latitude', 'longitude', 'contact_email', 
            'contact_phone', 'weather_backup_plan', 'is_recurring',
            'recurrence_rule', 'forum_topic_id', 'attendees',
            'can_edit', 'can_rsvp', 'created_at', 'updated_at'
        ]
    
    def get_can_edit(self, obj):
        """Check if current user can edit this event."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.organizer == request.user
        return False
    
    def get_can_rsvp(self, obj):
        """Check if current user can RSVP to this event."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        # Can't RSVP to your own event
        if obj.organizer == request.user:
            return False
            
        # Can't RSVP to past events
        if obj.is_past:
            return False
            
        # Check if event is at capacity
        if obj.max_attendees and obj.spots_remaining == 0:
            # Unless user is already RSVPed
            try:
                existing_rsvp = obj.attendees.get(user=request.user)
                return existing_rsvp.status != 'going'
            except EventAttendee.DoesNotExist:
                return False
        
        return True


class CommunityEventCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating events."""
    
    class Meta:
        model = CommunityEvent
        fields = [
            'title', 'description', 'event_type',
            'start_datetime', 'end_datetime', 'is_all_day',
            'location_name', 'address', 'city', 'hardiness_zone',
            'latitude', 'longitude', 'privacy_level',
            'max_attendees', 'requires_rsvp', 'contact_email',
            'contact_phone', 'external_url', 'weather_dependent',
            'weather_backup_plan', 'is_recurring', 'recurrence_rule', 'forum_topic_id'
        ]
    
    def validate_end_datetime(self, value):
        """Ensure end datetime is after start datetime."""
        start_datetime = self.initial_data.get('start_datetime')
        if start_datetime and value:
            # Convert string to datetime if needed for comparison
            if isinstance(start_datetime, str):
                start_datetime = serializers.DateTimeField().to_internal_value(start_datetime)
            if value <= start_datetime:
                raise serializers.ValidationError("End time must be after start time.")
        return value
    
    def validate_start_datetime(self, value):
        """Ensure start datetime is not in the past (for new events)."""
        if not self.instance and value < timezone.now():
            raise serializers.ValidationError("Cannot create events in the past.")
        return value
    
    def validate_max_attendees(self, value):
        """Ensure max_attendees is reasonable."""
        if value is not None and value < 1:
            raise serializers.ValidationError("Maximum attendees must be at least 1.")
        if value is not None and value > 10000:
            raise serializers.ValidationError("Maximum attendees cannot exceed 10,000.")
        return value


class SeasonalTemplateSerializer(serializers.ModelSerializer):
    """Serializer for seasonal templates."""
    
    created_by = EventOrganizerSerializer(read_only=True)
    applicable_zones_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = SeasonalTemplate
        fields = [
            'id', 'name', 'description', 'hardiness_zones', 'season',
            'task_type', 'plant_types', 'start_month', 'end_month',
            'day_of_month', 'frequency_days', 'temperature_min',
            'temperature_max', 'requires_no_frost', 'requires_no_rain',
            'instructions', 'tips', 'priority', 'is_active',
            'created_by', 'applicable_zones_display', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'applicable_zones_display',
                           'created_at', 'updated_at']
    
    def validate_hardiness_zones(self, value):
        """Validate hardiness zone format."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Hardiness zones must be a list.")
        
        valid_zones = []
        for zone in value:
            if not isinstance(zone, str) or not zone:
                raise serializers.ValidationError("Each zone must be a non-empty string.")
            # Basic validation for USDA zone format (e.g., '7a', '9b', '10')
            zone = zone.strip().lower()
            if len(zone) < 1 or len(zone) > 3:
                raise serializers.ValidationError(f"Invalid zone format: {zone}")
            valid_zones.append(zone)
        
        return valid_zones
    
    def validate_plant_types(self, value):
        """Validate plant types format."""
        if value is not None and not isinstance(value, list):
            raise serializers.ValidationError("Plant types must be a list.")
        return value


class WeatherAlertSerializer(serializers.ModelSerializer):
    """Serializer for weather alerts."""
    
    is_current = serializers.BooleanField(read_only=True)
    color_code = serializers.CharField(read_only=True)
    city_or_zip = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = WeatherAlert
        fields = [
            'id', 'alert_type', 'severity', 'zip_code', 'city',
            'hardiness_zone', 'title', 'message', 'recommendations',
            'start_datetime', 'end_datetime', 'expires_at',
            'temperature_low', 'temperature_high', 'wind_speed',
            'precipitation_chance', 'precipitation_amount',
            'is_active', 'is_current', 'color_code', 'city_or_zip',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_current', 'color_code', 'city_or_zip',
                           'created_at', 'updated_at']
    
    def get_city_or_zip(self, obj):
        """Get display location (city if available, otherwise ZIP)."""
        return obj.city if obj.city else obj.zip_code


class RSVPSerializer(serializers.Serializer):
    """Serializer for RSVP actions."""

    status = serializers.ChoiceField(choices=EventAttendee.RSVP_STATUS)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_status(self, value):
        """Additional validation for RSVP status."""
        if value not in ['going', 'maybe', 'not_going']:
            raise serializers.ValidationError("Invalid RSVP status.")
        return value


# ============================================================================
# Garden Planner Serializers
# ============================================================================


class GardenOwnerSerializer(serializers.ModelSerializer):
    """Basic owner information for garden listings."""

    class Meta:
        model = User
        fields = ['uuid', 'username', 'first_name', 'last_name']
        read_only_fields = ['uuid', 'username', 'first_name', 'last_name']


class PlantImageSerializer(serializers.ModelSerializer):
    """Serializer for plant images."""

    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = PlantImage
        fields = [
            'uuid', 'image', 'image_url', 'thumbnail_url',
            'caption', 'is_primary', 'created_at'
        ]
        read_only_fields = ['uuid', 'image_url', 'thumbnail_url', 'created_at']

    def get_image_url(self, obj):
        """Get full image URL."""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

    def get_thumbnail_url(self, obj):
        """Get thumbnail URL (could use image service in future)."""
        return self.get_image_url(obj)


class PlantListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for plant listings."""

    garden_bed_name = serializers.CharField(source='garden_bed.name', read_only=True)
    primary_image = serializers.SerializerMethodField()
    health_status_display = serializers.CharField(source='get_health_status_display', read_only=True)
    growth_stage_display = serializers.CharField(source='get_growth_stage_display', read_only=True)
    days_since_planted = serializers.IntegerField(read_only=True)
    age_display = serializers.CharField(read_only=True)

    class Meta:
        model = Plant
        fields = [
            'uuid', 'garden_bed', 'garden_bed_name', 'common_name', 'variety',
            'health_status', 'health_status_display', 'growth_stage', 'growth_stage_display',
            'planted_date', 'primary_image',
            'days_since_planted', 'age_display', 'is_active'
        ]
        read_only_fields = [
            'uuid', 'garden_bed_name', 'health_status_display', 'growth_stage_display',
            'days_since_planted', 'age_display', 'primary_image'
        ]

    def get_primary_image(self, obj):
        """Get primary image for plant."""
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            return PlantImageSerializer(primary, context=self.context).data
        return None


class PlantDetailSerializer(PlantListSerializer):
    """Detailed serializer for individual plants."""

    plant_species = serializers.StringRelatedField(read_only=True)
    images = PlantImageSerializer(many=True, read_only=True)
    upcoming_tasks = serializers.SerializerMethodField()
    recent_logs = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta(PlantListSerializer.Meta):
        fields = PlantListSerializer.Meta.fields + [
            'plant_species', 'position_x', 'position_y', 'notes',
            'images', 'upcoming_tasks', 'recent_logs', 'can_edit',
            'created_at', 'updated_at'
        ]

    def get_upcoming_tasks(self, obj):
        """Get next 3 upcoming care tasks."""
        from django.utils import timezone
        tasks = obj.care_tasks.filter(
            completed=False,
            skipped=False,
            scheduled_date__gte=timezone.now()
        ).order_by('scheduled_date')[:3]
        return CareTaskListSerializer(tasks, many=True, context=self.context).data

    def get_recent_logs(self, obj):
        """Get last 5 care logs."""
        logs = obj.care_logs.order_by('-log_date')[:5]
        return CareLogSerializer(logs, many=True, context=self.context).data

    def get_can_edit(self, obj):
        """Check if current user can edit this plant."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.garden_bed.owner == request.user
        return False


class PlantCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating plants."""

    class Meta:
        model = Plant
        fields = [
            'uuid', 'garden_bed', 'plant_species', 'common_name', 'variety',
            'health_status', 'growth_stage', 'planted_date',
            'position_x', 'position_y', 'notes', 'is_active'
        ]
        read_only_fields = ['uuid']

    def validate_garden_bed(self, value):
        """Ensure user owns the garden bed."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if value.owner != request.user:
                raise serializers.ValidationError("You can only add plants to your own garden beds.")
        return value

    def validate(self, data):
        """Validate plant limit per bed."""
        from ..constants import MAX_PLANTS_PER_GARDEN_BED

        garden_bed = data.get('garden_bed')
        if garden_bed:
            # For updates, exclude current plant from count
            current_count = garden_bed.plants.filter(is_active=True).count()
            if self.instance:
                current_count -= 1

            if current_count >= MAX_PLANTS_PER_GARDEN_BED:
                raise serializers.ValidationError({
                    'garden_bed': f"Garden bed already has maximum of {MAX_PLANTS_PER_GARDEN_BED} plants."
                })

        return data


class CareTaskListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for care task listings."""

    plant_name = serializers.CharField(source='plant.common_name', read_only=True)
    task_type_display = serializers.CharField(source='get_task_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = CareTask
        fields = [
            'uuid', 'plant', 'plant_name', 'task_type', 'task_type_display',
            'title', 'priority', 'priority_display', 'scheduled_date', 'completed',
            'skipped', 'is_recurring', 'is_overdue'
        ]
        read_only_fields = [
            'uuid', 'plant_name', 'task_type_display', 'priority_display', 'is_overdue', 'title'
        ]


class CareTaskDetailSerializer(CareTaskListSerializer):
    """Detailed serializer for individual care tasks."""

    completed_by = GardenOwnerSerializer(read_only=True)
    can_edit = serializers.SerializerMethodField()

    class Meta(CareTaskListSerializer.Meta):
        fields = CareTaskListSerializer.Meta.fields + [
            'notes', 'completed_at', 'completed_by', 'recurrence_interval_days',
            'can_edit', 'created_at', 'updated_at'
        ]

    def get_can_edit(self, obj):
        """Check if current user can edit this task."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.plant.garden_bed.owner == request.user
        return False


class CareTaskCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating care tasks."""

    class Meta:
        model = CareTask
        fields = [
            'uuid', 'plant', 'task_type', 'title', 'priority', 'scheduled_date',
            'is_recurring', 'recurrence_interval_days', 'notes'
        ]
        read_only_fields = ['uuid']

    def validate_plant(self, value):
        """Ensure user owns the plant."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if value.garden_bed.owner != request.user:
                raise serializers.ValidationError("You can only create tasks for your own plants.")
        return value

    def validate(self, data):
        """Validate recurring task configuration."""
        is_recurring = data.get('is_recurring', False)
        recurrence_interval = data.get('recurrence_interval_days')

        if is_recurring and not recurrence_interval:
            raise serializers.ValidationError({
                'recurrence_interval_days': "Recurring tasks must have a recurrence interval."
            })

        if recurrence_interval and recurrence_interval < 1:
            raise serializers.ValidationError({
                'recurrence_interval_days': "Recurrence interval must be at least 1 day."
            })

        return data


class CareLogSerializer(serializers.ModelSerializer):
    """Serializer for care logs."""

    logged_by = GardenOwnerSerializer(source='user', read_only=True)
    plant_name = serializers.CharField(source='plant.common_name', read_only=True)
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)

    class Meta:
        model = CareLog
        fields = [
            'uuid', 'plant', 'plant_name', 'activity_type', 'activity_type_display',
            'notes', 'plant_health_before', 'plant_health_after', 'hours_spent',
            'materials_used', 'cost', 'weather_conditions', 'logged_by',
            'log_date'
        ]
        read_only_fields = ['uuid', 'plant_name', 'activity_type_display', 'logged_by', 'log_date']


class HarvestSerializer(serializers.ModelSerializer):
    """Serializer for harvest records."""

    plant_name = serializers.CharField(source='plant.common_name', read_only=True)
    days_from_planting = serializers.IntegerField(read_only=True)

    class Meta:
        model = Harvest
        fields = [
            'id', 'plant', 'plant_name', 'harvest_date', 'quantity', 'unit',
            'quality_rating', 'notes',
            'days_from_planting', 'created_at'
        ]
        read_only_fields = ['id', 'plant_name', 'days_from_planting', 'created_at']

    def validate_quality_rating(self, value):
        """Validate quality rating range."""
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError("Quality rating must be between 1 and 5.")
        return value

    def validate_taste_rating(self, value):
        """Validate taste rating range."""
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError("Taste rating must be between 1 and 5.")
        return value


class GardenBedListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for garden bed listings."""

    owner = GardenOwnerSerializer(read_only=True)
    bed_type_display = serializers.CharField(source='get_bed_type_display', read_only=True)
    sun_exposure_display = serializers.CharField(source='get_sun_exposure_display', read_only=True)
    plant_count = serializers.IntegerField(read_only=True)
    area_square_feet = serializers.FloatField(read_only=True)
    utilization_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = GardenBed
        fields = [
            'uuid', 'owner', 'name', 'bed_type', 'bed_type_display',
            'length_inches', 'width_inches', 'depth_inches',
            'sun_exposure', 'sun_exposure_display', 'soil_type', 'soil_ph',
            'plant_count', 'area_square_feet', 'utilization_rate', 'is_active'
        ]
        read_only_fields = [
            'uuid', 'owner', 'bed_type_display', 'sun_exposure_display',
            'plant_count', 'area_square_feet', 'utilization_rate'
        ]


class GardenBedDetailSerializer(GardenBedListSerializer):
    """Detailed serializer for individual garden beds."""

    plants = PlantListSerializer(many=True, read_only=True)
    can_edit = serializers.SerializerMethodField()

    class Meta(GardenBedListSerializer.Meta):
        fields = GardenBedListSerializer.Meta.fields + [
            'notes', 'layout_data',
            'plants', 'can_edit', 'created_at', 'updated_at'
        ]

    def get_can_edit(self, obj):
        """Check if current user can edit this garden bed."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.owner == request.user
        return False


class GardenBedCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating garden beds."""

    owner = GardenOwnerSerializer(read_only=True)

    class Meta:
        model = GardenBed
        fields = [
            'uuid', 'owner',
            'name', 'bed_type', 'length_inches', 'width_inches', 'depth_inches',
            'sun_exposure', 'soil_type', 'soil_ph', 'notes',
            'layout_data', 'is_active'
        ]
        read_only_fields = ['uuid', 'owner']

    def validate_soil_ph(self, value):
        """Validate soil pH range."""
        if value is not None and (value < 0 or value > 14):
            raise serializers.ValidationError("Soil pH must be between 0 and 14.")
        return value

    def validate(self, data):
        """Validate bed dimensions and user limits."""
        from ..constants import MAX_GARDEN_BEDS_PER_USER

        # Check user bed limit for new beds
        if not self.instance:
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                current_count = GardenBed.objects.filter(
                    owner=request.user,
                    is_active=True
                ).count()

                if current_count >= MAX_GARDEN_BEDS_PER_USER:
                    raise serializers.ValidationError({
                        'non_field_errors': f"You have reached the maximum of {MAX_GARDEN_BEDS_PER_USER} active garden beds."
                    })

        # Validate dimensions make sense
        length = data.get('length_inches')
        width = data.get('width_inches')

        if length is not None and width is not None:
            if length < 1 or width < 1:
                raise serializers.ValidationError({
                    'non_field_errors': "Garden bed dimensions must be at least 1 inch."
                })

            # Reasonable maximum (100 feet = 1200 inches)
            if length > 1200 or width > 1200:
                raise serializers.ValidationError({
                    'non_field_errors': "Garden bed dimensions cannot exceed 100 feet (1200 inches)."
                })

        return data


class GrowingZoneSerializer(serializers.ModelSerializer):
    """Serializer for growing zone reference data."""

    class Meta:
        model = GrowingZone
        fields = [
            'id', 'zone_code', 'temp_min', 'temp_max',
            'first_frost_date', 'last_frost_date', 'growing_season_days'
        ]
        read_only_fields = ['id']