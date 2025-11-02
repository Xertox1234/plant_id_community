"""
DRF serializers for plant health diagnosis feature.

Provides serializers for DiagnosisCard and DiagnosisReminder models
with nested data and JSON validation for care instructions.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from typing import Dict, Any, Optional, List

from ..models import DiagnosisCard, DiagnosisReminder, PlantDiseaseResult

User = get_user_model()


def validate_streamfield_care_instructions(value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate StreamField-compatible JSON structure.

    Each block must have 'type' and 'value' keys.
    Valid types: heading, paragraph, treatment_step, symptom_check,
                prevention_tip, list_block, image

    Args:
        value: List of block dictionaries to validate

    Returns:
        Validated list of blocks

    Raises:
        ValidationError: If structure is invalid
    """
    if not isinstance(value, list):
        raise serializers.ValidationError(
            "care_instructions must be a list of blocks"
        )

    valid_block_types = [
        'heading', 'paragraph', 'treatment_step', 'symptom_check',
        'prevention_tip', 'list_block', 'image'
    ]

    for i, block in enumerate(value):
        if not isinstance(block, dict):
            raise serializers.ValidationError(
                f"Block {i} must be a dictionary"
            )

        if 'type' not in block:
            raise serializers.ValidationError(
                f"Block {i} missing required 'type' key"
            )

        if 'value' not in block:
            raise serializers.ValidationError(
                f"Block {i} missing required 'value' key"
            )

        block_type = block['type']
        if block_type not in valid_block_types:
            raise serializers.ValidationError(
                f"Block {i} has invalid type '{block_type}'. "
                f"Valid types: {', '.join(valid_block_types)}"
            )

    return value


class DiagnosisCardListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing diagnosis cards.

    Used for /diagnosis-cards/ list endpoint with minimal data
    for performance optimization.
    """

    display_name = serializers.SerializerMethodField()
    treatment_status_display = serializers.CharField(
        source='get_treatment_status_display',
        read_only=True
    )
    severity_display = serializers.CharField(
        source='get_severity_assessment_display',
        read_only=True
    )
    disease_type_display = serializers.CharField(
        source='get_disease_type_display',
        read_only=True
    )

    class Meta:
        model = DiagnosisCard
        fields = [
            'uuid',
            'display_name',
            'plant_scientific_name',
            'plant_common_name',
            'custom_nickname',
            'disease_name',
            'disease_type',
            'disease_type_display',
            'severity_assessment',
            'severity_display',
            'confidence_score',
            'treatment_status',
            'treatment_status_display',
            'plant_recovered',
            'is_favorite',
            'saved_at',
            'updated_at',
        ]
        read_only_fields = ['uuid', 'saved_at', 'updated_at']

    def get_display_name(self, obj: DiagnosisCard) -> str:
        """Get the best display name for the plant."""
        return obj.display_name


class DiagnosisCardDetailSerializer(serializers.ModelSerializer):
    """
    Complete serializer for diagnosis card detail view.

    Includes all fields including care_instructions JSON and personal notes.
    Used for /diagnosis-cards/{uuid}/ retrieve endpoint.
    """

    display_name = serializers.SerializerMethodField()
    treatment_status_display = serializers.CharField(
        source='get_treatment_status_display',
        read_only=True
    )
    severity_display = serializers.CharField(
        source='get_severity_assessment_display',
        read_only=True
    )
    disease_type_display = serializers.CharField(
        source='get_disease_type_display',
        read_only=True
    )

    # Nested diagnosis result info (optional)
    diagnosis_result_info = serializers.SerializerMethodField()

    # Reminders count
    active_reminders_count = serializers.SerializerMethodField()

    class Meta:
        model = DiagnosisCard
        fields = [
            'uuid',
            'display_name',
            'plant_scientific_name',
            'plant_common_name',
            'custom_nickname',
            'disease_name',
            'disease_type',
            'disease_type_display',
            'severity_assessment',
            'severity_display',
            'confidence_score',
            'care_instructions',  # Full JSON field
            'personal_notes',
            'treatment_status',
            'treatment_status_display',
            'plant_recovered',
            'share_with_community',
            'is_favorite',
            'diagnosis_result_info',
            'active_reminders_count',
            'saved_at',
            'updated_at',
            'last_viewed_at',
        ]
        read_only_fields = ['uuid', 'saved_at', 'updated_at']

    def get_display_name(self, obj: DiagnosisCard) -> str:
        """Get the best display name for the plant."""
        return obj.display_name

    def get_diagnosis_result_info(self, obj: DiagnosisCard) -> Optional[Dict[str, Any]]:
        """Get minimal info about the original diagnosis result."""
        if obj.diagnosis_result:
            return {
                'id': str(obj.diagnosis_result.uuid),
                'diagnosed_at': obj.diagnosis_result.created_at,
                'diagnosis_source': obj.diagnosis_result.diagnosis_source,
            }
        return None

    def get_active_reminders_count(self, obj: DiagnosisCard) -> int:
        """Count active reminders for this card."""
        return obj.reminders.filter(
            is_active=True,
            sent=False,
            cancelled=False
        ).count()

    def validate_care_instructions(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate StreamField-compatible JSON structure."""
        return validate_streamfield_care_instructions(value)


class DiagnosisCardCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new diagnosis cards.

    Used for POST /diagnosis-cards/ endpoint.
    Automatically sets user from request context.
    """

    diagnosis_result = serializers.SlugRelatedField(
        slug_field='uuid',
        queryset=PlantDiseaseResult.objects.all(),
        required=False,
        allow_null=True,
        help_text="UUID of the diagnosis result (optional - can be created from API data)"
    )

    class Meta:
        model = DiagnosisCard
        fields = [
            'uuid',
            'diagnosis_result',
            'plant_scientific_name',
            'plant_common_name',
            'custom_nickname',
            'disease_name',
            'disease_type',
            'severity_assessment',
            'confidence_score',
            'care_instructions',
            'personal_notes',
            'treatment_status',
            'plant_recovered',
            'share_with_community',
            'is_favorite',
        ]
        read_only_fields = ['uuid']

    def validate_diagnosis_result(self, value: Optional[PlantDiseaseResult]) -> Optional[PlantDiseaseResult]:
        """Ensure diagnosis result exists and user can access it (if provided)."""
        if value is None:
            return None

        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context required")

        # Check if diagnosis result belongs to user or is public
        if value.request.user != request.user and not getattr(value.request, 'is_public', False):
            raise serializers.ValidationError(
                "You don't have permission to access this diagnosis result"
            )

        return value

    def validate_care_instructions(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate StreamField-compatible JSON structure."""
        return validate_streamfield_care_instructions(value)

    def create(self, validated_data: Dict[str, Any]) -> DiagnosisCard:
        """Create diagnosis card with user from request."""
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context required")

        validated_data['user'] = request.user
        return super().create(validated_data)


class DiagnosisCardUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing diagnosis cards.

    Used for PATCH /diagnosis-cards/{uuid}/ endpoint.
    Allows updating care instructions, notes, status, etc.
    """

    class Meta:
        model = DiagnosisCard
        fields = [
            'custom_nickname',
            'care_instructions',
            'personal_notes',
            'treatment_status',
            'plant_recovered',
            'share_with_community',
            'is_favorite',
        ]

    def validate_care_instructions(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate StreamField-compatible JSON structure."""
        return validate_streamfield_care_instructions(value)


class DiagnosisReminderSerializer(serializers.ModelSerializer):
    """
    Serializer for diagnosis reminders.

    Handles reminder creation, listing, and updates.
    """

    diagnosis_card = serializers.SlugRelatedField(
        slug_field='uuid',
        queryset=DiagnosisCard.objects.all(),
        help_text="UUID of the diagnosis card this reminder is for"
    )

    reminder_type_display = serializers.CharField(
        source='get_reminder_type_display',
        read_only=True
    )

    class Meta:
        model = DiagnosisReminder
        fields = [
            'uuid',
            'diagnosis_card',
            'reminder_type',
            'reminder_type_display',
            'reminder_title',
            'reminder_message',
            'scheduled_date',
            'sent',
            'sent_at',
            'acknowledged',
            'acknowledged_at',
            'snoozed_until',
            'is_active',
            'cancelled',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'uuid', 'sent', 'sent_at', 'acknowledged', 'acknowledged_at',
            'created_at', 'updated_at'
        ]

    def validate_diagnosis_card(self, value: DiagnosisCard) -> DiagnosisCard:
        """Ensure diagnosis card belongs to user."""
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context required")

        if value.user != request.user:
            raise serializers.ValidationError(
                "You don't have permission to create reminders for this diagnosis card"
            )

        return value

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate reminder data."""
        from django.utils import timezone

        scheduled_date = data.get('scheduled_date')
        if scheduled_date and scheduled_date < timezone.now():
            raise serializers.ValidationError({
                'scheduled_date': 'Scheduled date must be in the future'
            })

        return data
