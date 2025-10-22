"""
Django REST Framework serializers for plant identification.
"""

from rest_framework import serializers
from .models import (
    PlantSpecies,
    PlantIdentificationRequest,
    PlantIdentificationResult,
    UserPlant,
    PlantDiseaseRequest,
    PlantDiseaseResult,
    PlantDiseaseDatabase,
    DiseaseCareInstructions,
    SavedDiagnosis,
    SavedCareInstructions,
    TreatmentAttempt
)


class PlantSpeciesSerializer(serializers.ModelSerializer):
    """Serializer for PlantSpecies model."""
    
    display_name = serializers.ReadOnlyField()
    common_names_list = serializers.ReadOnlyField()
    primary_image_thumbnail = serializers.SerializerMethodField()
    
    class Meta:
        model = PlantSpecies
        fields = [
            'id', 'scientific_name', 'common_names', 'family', 'genus', 'species',
            'trefle_id', 'plantnet_id', 'plant_type', 'growth_habit',
            'mature_height_min', 'mature_height_max', 'light_requirements',
            'water_requirements', 'soil_ph_min', 'soil_ph_max',
            'hardiness_zone_min', 'hardiness_zone_max', 'description',
            'native_regions', 'bloom_time', 'flower_color', 'primary_image',
            'is_verified', 'verification_source', 'created_at', 'updated_at',
            'display_name', 'common_names_list', 'primary_image_thumbnail'
        ]
    
    def get_primary_image_thumbnail(self, obj):
        """Get thumbnail URL for primary image."""
        if obj.primary_image:
            request = self.context.get('request')
            if request and hasattr(obj, 'primary_image_thumbnail'):
                return request.build_absolute_uri(obj.primary_image_thumbnail.url)
        return None


class PlantIdentificationRequestSerializer(serializers.ModelSerializer):
    """Serializer for PlantIdentificationRequest model."""
    
    request_id = serializers.UUIDField(read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    images = serializers.SerializerMethodField()
    image_thumbnails = serializers.SerializerMethodField()
    results_count = serializers.SerializerMethodField()
    
    class Meta:
        model = PlantIdentificationRequest
        fields = [
            'id', 'request_id', 'user', 'image_1', 'image_2', 'image_3',
            'location', 'latitude', 'longitude', 'description', 'plant_size',
            'habitat', 'status', 'processed_by_ai', 'ai_processing_date',
            'created_at', 'updated_at', 'images', 'image_thumbnails', 'results_count'
        ]
        read_only_fields = ['status', 'processed_by_ai', 'ai_processing_date']
    
    def get_images(self, obj):
        """Get list of all uploaded image URLs."""
        images = []
        
        for image in obj.images:
            # Return relative URLs so the frontend proxy (/media) can serve them
            if image:
                images.append(image.url)
        
        return images
    
    def get_image_thumbnails(self, obj):
        """Get list of all image thumbnail URLs."""
        thumbnails = []
        
        for thumbnail in obj.image_thumbnails:
            # Return relative URLs so the frontend proxy (/media) can serve them
            if thumbnail:
                thumbnails.append(thumbnail.url)
        
        return thumbnails
    
    def get_results_count(self, obj):
        """Get count of identification results."""
        return obj.identification_results.count()


# =============================================================================
# Disease Diagnosis Serializers
# =============================================================================

class PlantDiseaseRequestSerializer(serializers.ModelSerializer):
    """Serializer for PlantDiseaseRequest model."""
    
    request_id = serializers.UUIDField(read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    plant_species_data = PlantSpeciesSerializer(source='plant_species', read_only=True)
    images = serializers.SerializerMethodField()
    image_thumbnails = serializers.SerializerMethodField()
    results_count = serializers.SerializerMethodField()
    
    class Meta:
        model = PlantDiseaseRequest
        fields = [
            'id', 'request_id', 'user', 'plant_identification_request',
            'plant_species', 'plant_species_data', 'image_1', 'image_2', 'image_3',
            'symptoms_description', 'plant_condition', 'location', 'recent_weather',
            'recent_care_changes', 'status', 'processed_by_ai', 'ai_processing_date',
            'created_at', 'updated_at', 'images', 'image_thumbnails', 'results_count'
        ]
        read_only_fields = ['status', 'processed_by_ai', 'ai_processing_date']
    
    def get_images(self, obj):
        """Get list of all uploaded symptom image URLs."""
        request = self.context.get('request')
        images = []
        
        for image in obj.images:
            if image and request:
                images.append(request.build_absolute_uri(image.url))
        
        return images
    
    def get_image_thumbnails(self, obj):
        """Get list of all image thumbnail URLs."""
        request = self.context.get('request')
        thumbnails = []
        
        for thumbnail in obj.image_thumbnails:
            if thumbnail and request:
                thumbnails.append(request.build_absolute_uri(thumbnail.url))
        
        return thumbnails
    
    def get_results_count(self, obj):
        """Get count of diagnosis results."""
        return obj.diagnosis_results.count()


class PlantDiseaseRequestCreateSerializer(serializers.ModelSerializer):
    """Specialized serializer for creating disease diagnosis requests."""
    
    class Meta:
        model = PlantDiseaseRequest
        fields = [
            'plant_identification_request', 'plant_species', 'image_1', 'image_2', 'image_3',
            'symptoms_description', 'plant_condition', 'location', 'recent_weather',
            'recent_care_changes'
        ]
    
    def validate(self, data):
        """Validate that at least one image and symptom description are provided."""
        if not data.get('image_1'):
            raise serializers.ValidationError("At least one symptom image is required for disease diagnosis.")
        
        if not data.get('symptoms_description'):
            raise serializers.ValidationError("Please describe the symptoms you're observing.")
        
        return data


class PlantDiseaseResultSerializer(serializers.ModelSerializer):
    """Serializer for PlantDiseaseResult model."""
    
    request_id = serializers.UUIDField(source='request.request_id', read_only=True)
    diagnosed_by_username = serializers.CharField(source='diagnosed_by.username', read_only=True)
    display_name = serializers.ReadOnlyField()
    vote_score = serializers.ReadOnlyField()
    confidence_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = PlantDiseaseResult
        fields = [
            'id', 'uuid', 'request', 'request_id', 'identified_disease',
            'suggested_disease_name', 'suggested_disease_type', 'confidence_score',
            'confidence_percentage', 'diagnosis_source', 'diagnosed_by', 'diagnosed_by_username',
            'symptoms_identified', 'severity_assessment', 'recommended_treatments',
            'immediate_actions', 'notes', 'community_confirmed', 'upvotes', 'downvotes',
            'vote_score', 'is_accepted', 'is_primary', 'stored_to_database',
            'created_at', 'updated_at', 'display_name'
        ]
    
    def get_confidence_percentage(self, obj):
        """Convert confidence score to percentage."""
        return round(obj.confidence_score * 100, 1) if obj.confidence_score else 0


class PlantIdentificationResultSerializer(serializers.ModelSerializer):
    """Serializer for PlantIdentificationResult model."""
    
    request_id = serializers.CharField(source='request.request_id', read_only=True)
    identified_species_data = PlantSpeciesSerializer(source='identified_species', read_only=True)
    identified_by_username = serializers.CharField(source='identified_by.username', read_only=True)
    display_name = serializers.ReadOnlyField()
    vote_score = serializers.ReadOnlyField()
    confidence_percentage = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()
    
    class Meta:
        model = PlantIdentificationResult
        fields = [
            'id', 'request_id', 'identified_species', 'identified_species_data',
            'suggested_scientific_name', 'suggested_common_name',
            'confidence_score', 'confidence_percentage', 'identification_source',
            'identified_by', 'identified_by_username', 'notes', 'upvotes', 'downvotes',
            'vote_score', 'is_accepted', 'is_primary', 'created_at', 'updated_at',
            'display_name', 'ai_care_instructions', 'care_instructions_generated_at',
            'user_vote'
        ]
    
    def get_confidence_percentage(self, obj):
        """Convert confidence score to percentage."""
        return round(obj.confidence_score * 100, 1) if obj.confidence_score else 0
    
    def get_user_vote(self, obj):
        """Get the current user's vote for this result."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        try:
            from .models import PlantIdentificationVote
            vote = PlantIdentificationVote.objects.get(user=request.user, result=obj)
            return vote.vote_type
        except PlantIdentificationVote.DoesNotExist:
            return None


class UserPlantSerializer(serializers.ModelSerializer):
    """Serializer for UserPlant model."""
    
    user = serializers.StringRelatedField(read_only=True)
    species_data = PlantSpeciesSerializer(source='species', read_only=True)
    collection_name = serializers.CharField(source='collection.name', read_only=True)
    display_name = serializers.ReadOnlyField()
    image_thumbnail = serializers.SerializerMethodField()
    from_identification_request_id = serializers.CharField(
        source='from_identification_request.request_id', 
        read_only=True
    )
    
    class Meta:
        model = UserPlant
        fields = [
            'id', 'user', 'collection', 'collection_name', 'species',
            'species_data', 'nickname', 'acquisition_date', 'location_in_home',
            'notes', 'is_alive', 'is_public', 'from_identification_request',
            'from_identification_request_id', 'from_identification_result',
            'care_instructions_json', 'image', 'image_thumbnail',
            'created_at', 'updated_at', 'display_name'
        ]
    
    def get_image_thumbnail(self, obj):
        """Get thumbnail URL for plant image."""
        if obj.image:
            request = self.context.get('request')
            if request and hasattr(obj, 'image_thumbnail'):
                return request.build_absolute_uri(obj.image_thumbnail.url)
        return None


class PlantIdentificationRequestCreateSerializer(serializers.ModelSerializer):
    """Specialized serializer for creating identification requests."""
    
    class Meta:
        model = PlantIdentificationRequest
        fields = [
            'image_1', 'image_2', 'image_3', 'location', 'latitude', 
            'longitude', 'description', 'plant_size', 'habitat'
        ]
    
    def validate(self, data):
        """Validate that at least one image is provided."""
        if not data.get('image_1'):
            raise serializers.ValidationError("At least one image is required for plant identification.")
        return data


class PlantIdentificationRequestWithResultsSerializer(serializers.ModelSerializer):
    """Serializer for PlantIdentificationRequest with full identification results."""
    
    request_id = serializers.UUIDField(read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    images = serializers.SerializerMethodField()
    image_thumbnails = serializers.SerializerMethodField()
    results_count = serializers.SerializerMethodField()
    identification_results = PlantIdentificationResultSerializer(many=True, read_only=True)
    
    class Meta:
        model = PlantIdentificationRequest
        fields = [
            'id', 'request_id', 'user', 'image_1', 'image_2', 'image_3',
            'location', 'latitude', 'longitude', 'description', 'plant_size',
            'habitat', 'status', 'processed_by_ai', 'ai_processing_date',
            'created_at', 'updated_at', 'images', 'image_thumbnails', 
            'results_count', 'identification_results'
        ]
        read_only_fields = ['status', 'processed_by_ai', 'ai_processing_date']
    
    def get_images(self, obj):
        """Get list of all uploaded image URLs."""
        request = self.context.get('request')
        images = []
        
        for image in obj.images:
            if image and request:
                images.append(request.build_absolute_uri(image.url))
        
        return images
    
    def get_image_thumbnails(self, obj):
        """Get list of all image thumbnail URLs."""
        request = self.context.get('request')
        thumbnails = []
        
        for thumbnail in obj.image_thumbnails:
            if thumbnail and request:
                thumbnails.append(request.build_absolute_uri(thumbnail.url))
        
        return thumbnails
    
    def get_results_count(self, obj):
        """Get count of identification results."""
        return obj.identification_results.count()


# =============================================================================
# Disease Diagnosis Serializers
# =============================================================================

class PlantDiseaseRequestSerializer(serializers.ModelSerializer):
    """Serializer for PlantDiseaseRequest model."""
    
    request_id = serializers.UUIDField(read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    plant_species_data = PlantSpeciesSerializer(source='plant_species', read_only=True)
    images = serializers.SerializerMethodField()
    image_thumbnails = serializers.SerializerMethodField()
    results_count = serializers.SerializerMethodField()
    
    class Meta:
        model = PlantDiseaseRequest
        fields = [
            'id', 'request_id', 'user', 'plant_identification_request',
            'plant_species', 'plant_species_data', 'image_1', 'image_2', 'image_3',
            'symptoms_description', 'plant_condition', 'location', 'recent_weather',
            'recent_care_changes', 'status', 'processed_by_ai', 'ai_processing_date',
            'created_at', 'updated_at', 'images', 'image_thumbnails', 'results_count'
        ]
        read_only_fields = ['status', 'processed_by_ai', 'ai_processing_date']
    
    def get_images(self, obj):
        """Get list of all uploaded symptom image URLs."""
        request = self.context.get('request')
        images = []
        
        for image in obj.images:
            if image and request:
                images.append(request.build_absolute_uri(image.url))
        
        return images
    
    def get_image_thumbnails(self, obj):
        """Get list of all image thumbnail URLs."""
        request = self.context.get('request')
        thumbnails = []
        
        for thumbnail in obj.image_thumbnails:
            if thumbnail and request:
                thumbnails.append(request.build_absolute_uri(thumbnail.url))
        
        return thumbnails
    
    def get_results_count(self, obj):
        """Get count of diagnosis results."""
        return obj.diagnosis_results.count()


class PlantDiseaseRequestCreateSerializer(serializers.ModelSerializer):
    """Specialized serializer for creating disease diagnosis requests."""
    
    class Meta:
        model = PlantDiseaseRequest
        fields = [
            'plant_identification_request', 'plant_species', 'image_1', 'image_2', 'image_3',
            'symptoms_description', 'plant_condition', 'location', 'recent_weather',
            'recent_care_changes'
        ]
    
    def validate(self, data):
        """Validate that at least one image and symptom description are provided."""
        if not data.get('image_1'):
            raise serializers.ValidationError("At least one symptom image is required for disease diagnosis.")
        
        if not data.get('symptoms_description'):
            raise serializers.ValidationError("Please describe the symptoms you're observing.")
        
        return data


class PlantDiseaseResultSerializer(serializers.ModelSerializer):
    """Serializer for PlantDiseaseResult model."""
    
    request_id = serializers.UUIDField(source='request.request_id', read_only=True)
    diagnosed_by_username = serializers.CharField(source='diagnosed_by.username', read_only=True)
    display_name = serializers.ReadOnlyField()
    vote_score = serializers.ReadOnlyField()
    confidence_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = PlantDiseaseResult
        fields = [
            'id', 'uuid', 'request', 'request_id', 'identified_disease',
            'suggested_disease_name', 'suggested_disease_type', 'confidence_score',
            'confidence_percentage', 'diagnosis_source', 'diagnosed_by', 'diagnosed_by_username',
            'symptoms_identified', 'severity_assessment', 'recommended_treatments',
            'immediate_actions', 'notes', 'community_confirmed', 'upvotes', 'downvotes',
            'vote_score', 'is_accepted', 'is_primary', 'stored_to_database',
            'created_at', 'updated_at', 'display_name'
        ]
    
    def get_confidence_percentage(self, obj):
        """Convert confidence score to percentage."""
        return round(obj.confidence_score * 100, 1) if obj.confidence_score else 0


# Missing serializers for the disease diagnosis models
class DiseaseCareInstructionsSerializer(serializers.ModelSerializer):
    """Serializer for DiseaseCareInstructions model."""
    
    disease_name = serializers.CharField(source='disease.disease_name', read_only=True)
    
    class Meta:
        model = DiseaseCareInstructions
        fields = [
            'id', 'uuid', 'disease', 'disease_name', 'treatment_name', 'treatment_type',
            'instructions', 'application_method', 'frequency', 'duration',
            'effectiveness_score', 'source', 'user_contributed', 'created_at', 'updated_at'
        ]


class PlantDiseaseDatabaseSerializer(serializers.ModelSerializer):
    """Serializer for PlantDiseaseDatabase model."""
    
    confidence_percentage = serializers.SerializerMethodField()
    affected_plant_count = serializers.SerializerMethodField()
    
    class Meta:
        model = PlantDiseaseDatabase
        fields = [
            'id', 'uuid', 'disease_name', 'disease_type', 'confidence_score',
            'confidence_percentage', 'api_source', 'diagnosis_count', 'symptoms',
            'description', 'affected_plants', 'affected_plant_count', 'created_at', 'updated_at'
        ]
    
    def get_confidence_percentage(self, obj):
        """Convert confidence score to percentage."""
        return round(obj.confidence_score * 100, 1) if obj.confidence_score else 0
    
    def get_affected_plant_count(self, obj):
        """Get count of affected plant species."""
        return obj.affected_plants.count()


class SavedDiagnosisSerializer(serializers.ModelSerializer):
    """Serializer for SavedDiagnosis model."""
    
    diagnosis_data = PlantDiseaseResultSerializer(source='diagnosis_result', read_only=True)
    disease_name = serializers.CharField(source='diagnosis_result.suggested_disease_name', read_only=True)
    
    class Meta:
        model = SavedDiagnosis
        fields = [
            'id', 'uuid', 'user', 'diagnosis_result', 'diagnosis_data', 'disease_name',
            'personal_notes', 'treatment_status', 'plant_recovered', 'share_with_community',
            'saved_at', 'updated_at'
        ]


class SavedCareInstructionsSerializer(serializers.ModelSerializer):
    """Serializer for SavedCareInstructions model."""
    
    plant_species_data = PlantSpeciesSerializer(source='plant_species', read_only=True)
    care_difficulty_display = serializers.CharField(source='get_care_difficulty_experienced_display', read_only=True)
    status_display = serializers.CharField(source='get_current_status_display', read_only=True)
    display_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = SavedCareInstructions
        fields = [
            'id', 'uuid', 'user', 'plant_species', 'plant_species_data',
            'plant_scientific_name', 'plant_common_name', 'plant_family',
            'care_instructions_data', 'personal_notes', 'custom_nickname',
            'care_difficulty_experienced', 'care_difficulty_display', 
            'current_status', 'status_display', 'share_with_community',
            'is_favorite', 'display_name', 'saved_at', 'updated_at', 'last_viewed_at'
        ]
        read_only_fields = ['uuid', 'user', 'saved_at', 'updated_at']


class TreatmentAttemptSerializer(serializers.ModelSerializer):
    """Serializer for TreatmentAttempt model."""
    
    diagnosis_info = PlantDiseaseResultSerializer(source='diagnosis_result', read_only=True)
    disease_name = serializers.CharField(source='diagnosis_result.suggested_disease_name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = TreatmentAttempt
        fields = [
            'id', 'uuid', 'user', 'username', 'diagnosis_result', 'diagnosis_info', 'disease_name',
            'treatment_name', 'treatment_type', 'application_method', 'dosage_frequency',
            'start_date', 'expected_duration', 'completed', 'completion_date',
            'effectiveness', 'notes', 'completion_notes', 'created_at', 'updated_at'
        ]


class PlantDiseaseRequestWithResultsSerializer(serializers.ModelSerializer):
    """Serializer for PlantDiseaseRequest with full diagnosis results."""
    
    request_id = serializers.UUIDField(read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    images = serializers.SerializerMethodField()
    image_thumbnails = serializers.SerializerMethodField()
    results_count = serializers.SerializerMethodField()
    diagnosis_results = PlantDiseaseResultSerializer(many=True, read_only=True)
    plant_species_data = PlantSpeciesSerializer(source='plant_species', read_only=True)
    
    class Meta:
        model = PlantDiseaseRequest
        fields = [
            'id', 'request_id', 'user', 'plant_identification_request',
            'plant_species', 'plant_species_data', 'image_1', 'image_2', 'image_3',
            'symptoms_description', 'plant_condition', 'location', 'recent_weather',
            'recent_care_changes', 'status', 'processed_by_ai', 'ai_processing_date',
            'created_at', 'updated_at', 'images', 'image_thumbnails', 
            'results_count', 'diagnosis_results'
        ]
        read_only_fields = ['status', 'processed_by_ai', 'ai_processing_date']
    
    def get_images(self, obj):
        """Get list of all uploaded symptom image URLs."""
        request = self.context.get('request')
        images = []
        
        for image in obj.images:
            if image and request:
                images.append(request.build_absolute_uri(image.url))
        
        return images
    
    def get_image_thumbnails(self, obj):
        """Get list of all image thumbnail URLs."""
        request = self.context.get('request')
        thumbnails = []
        
        for thumbnail in obj.image_thumbnails:
            if thumbnail and request:
                thumbnails.append(request.build_absolute_uri(thumbnail.url))
        
        return thumbnails
    
    def get_results_count(self, obj):
        """Get count of diagnosis results."""
        return obj.diagnosis_results.count()