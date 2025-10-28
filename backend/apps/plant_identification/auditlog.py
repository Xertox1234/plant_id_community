"""
Audit log registration for plant_identification app models.

Registers sensitive models for audit trail tracking to comply with:
- GDPR Article 30 (records of processing activities)
- SOC 2 audit trail requirements
- Security monitoring and unauthorized access detection
"""

from auditlog.registry import auditlog
from .models import (
    PlantIdentificationResult,
    PlantIdentificationRequest,
    PlantSpecies,
    UserPlant,
    SavedCareInstructions,
    PlantDiseaseResult,
)


# Register PlantIdentificationResult for comprehensive audit tracking
# Tracks: AI identification results, confidence scores, user acceptance
# Critical for: Answering "Who accessed identification result X?" for GDPR requests
auditlog.register(
    PlantIdentificationResult,
    include_fields=[
        'confidence_score', 'identification_source', 'is_accepted',
        'is_primary', 'upvotes', 'downvotes', 'suggested_scientific_name',
        'suggested_common_name'
    ],
    exclude_fields=['api_response_data'],  # Exclude large JSON blobs for performance
)

# Register PlantIdentificationRequest for data access tracking
# Tracks: User plant identification requests, location data, status changes
auditlog.register(
    PlantIdentificationRequest,
    include_fields=[
        'status', 'location', 'latitude', 'longitude', 'description',
        'plant_size', 'habitat', 'processed_by_ai'
    ],
)

# Register PlantSpecies for data modification tracking
# Tracks: Species database changes, verification status, confidence updates
auditlog.register(
    PlantSpecies,
    include_fields=[
        'scientific_name', 'common_names', 'family', 'genus', 'species',
        'is_verified', 'auto_stored', 'confidence_score',
        'identification_count', 'api_source'
    ],
)

# Register UserPlant for user collection tracking
# Tracks: Plants added to collections, care notes, status changes
auditlog.register(
    UserPlant,
    include_fields=[
        'nickname', 'acquisition_date', 'location_in_home', 'notes',
        'is_alive', 'is_public'
    ],
)

# Register SavedCareInstructions for user data access
# Tracks: Saved care cards, personal notes, sharing preferences
auditlog.register(
    SavedCareInstructions,
    include_fields=[
        'plant_scientific_name', 'plant_common_name', 'custom_nickname',
        'personal_notes', 'care_difficulty_experienced', 'current_status',
        'share_with_community', 'is_favorite'
    ],
    exclude_fields=['care_instructions_data'],  # Exclude large JSON for performance
)

# Register PlantDiseaseResult for health diagnosis tracking
# Tracks: Disease diagnoses, treatment recommendations, user feedback
auditlog.register(
    PlantDiseaseResult,
    include_fields=[
        'confidence_score', 'diagnosis_source', 'severity_assessment',
        'is_accepted', 'is_primary', 'stored_to_database'
    ],
    exclude_fields=['api_response_data'],  # Exclude large JSON blobs
)
