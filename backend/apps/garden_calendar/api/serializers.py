"""
Garden Calendar API Serializers

Serializers for community events, seasonal templates, and weather alerts.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..models import CommunityEvent, EventAttendee, SeasonalTemplate, WeatherAlert

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