"""
Serializers for user authentication and profile management.
"""

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, UserPlantCollection


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    
    password = serializers.CharField(write_only=True, min_length=12)
    password_confirm = serializers.CharField(write_only=True, required=False)
    confirmPassword = serializers.CharField(write_only=True, required=False)  # Support frontend field name
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm', 'confirmPassword',
            'first_name', 'last_name', 'bio', 'location', 'gardening_experience'
        ]
    
    def validate(self, data):
        """Validate password confirmation and other fields."""
        # Handle both password_confirm and confirmPassword field names
        password_confirm = data.get('password_confirm') or data.get('confirmPassword')
        
        # Check if password confirmation is provided
        if password_confirm and data.get('password') != password_confirm:
            raise serializers.ValidationError({"confirmPassword": ["Passwords do not match."]})
        
        # Comprehensive password validation using Django's built-in validators
        password = data.get('password')
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                raise serializers.ValidationError({"password": e.messages})
        
        return data
    
    def validate_email(self, value):
        """Ensure email is unique."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def create(self, validated_data):
        """Create new user account."""
        # Remove password confirmation fields from validated_data
        validated_data.pop('password_confirm', None)
        validated_data.pop('confirmPassword', None)
        
        # Create user with hashed password
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        
        return user


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer for public information."""
    
    display_name = serializers.ReadOnlyField()
    follower_count = serializers.ReadOnlyField()
    following_count = serializers.ReadOnlyField()
    avatar_thumbnail = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'display_name',
            'bio', 'location', 'gardening_experience', 'avatar', 'avatar_thumbnail',
            'follower_count', 'following_count', 'plants_identified',
            'identifications_helped', 'forum_posts_count', 'date_joined'
        ]
    
    def get_avatar_thumbnail(self, obj):
        """Get avatar thumbnail URL."""
        if obj.avatar:
            request = self.context.get('request')
            if request and hasattr(obj, 'avatar_thumbnail'):
                return request.build_absolute_uri(obj.avatar_thumbnail.url)
        return None


class UserProfileSerializer(serializers.ModelSerializer):
    """Detailed user serializer for profile management."""
    
    display_name = serializers.ReadOnlyField()
    follower_count = serializers.ReadOnlyField()
    following_count = serializers.ReadOnlyField()
    avatar_thumbnail = serializers.SerializerMethodField()
    plant_collections_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'display_name',
            'bio', 'location', 'website', 'gardening_experience', 'avatar', 'avatar_thumbnail',
            'profile_visibility', 'show_email', 'show_location',
            'email_notifications', 'plant_id_notifications', 'forum_notifications',
            'follower_count', 'following_count', 'plants_identified',
            'identifications_helped', 'forum_posts_count', 'plant_collections_count',
            'date_joined', 'last_login'
        ]
        read_only_fields = [
            'username', 'date_joined', 'last_login', 'plants_identified',
            'identifications_helped', 'forum_posts_count'
        ]
    
    def get_avatar_thumbnail(self, obj):
        """Get avatar thumbnail URL."""
        if obj.avatar:
            request = self.context.get('request')
            if request and hasattr(obj, 'avatar_thumbnail'):
                return request.build_absolute_uri(obj.avatar_thumbnail.url)
        return None
    
    def get_plant_collections_count(self, obj):
        """Get count of user's plant collections."""
        return obj.plant_collections.count()


class UserPlantCollectionSerializer(serializers.ModelSerializer):
    """Serializer for user plant collections."""
    
    user = serializers.StringRelatedField(read_only=True)
    plant_count = serializers.ReadOnlyField()
    plants = serializers.SerializerMethodField()
    
    class Meta:
        model = UserPlantCollection
        fields = [
            'id', 'user', 'name', 'description', 'is_public',
            'plant_count', 'plants', 'created_at', 'updated_at'
        ]
    
    def get_plants(self, obj):
        """Get plants in this collection from UserPlant model."""
        try:
            from apps.plant_identification.models import UserPlant
            from apps.plant_identification.serializers import UserPlantSerializer
            
            plants = UserPlant.objects.filter(collection=obj).select_related(
                'species', 'from_identification_request'
            )
            return UserPlantSerializer(plants, many=True, context=self.context).data
        except ImportError:
            # If plant_identification app is not available, return empty list
            return []
    
    def validate_name(self, value):
        """Ensure collection name is unique for the user."""
        request = self.context.get('request')
        if request and request.user:
            user = request.user
            # Check if collection with this name already exists for this user
            existing_collection = UserPlantCollection.objects.filter(
                user=user, 
                name=value
            )
            
            # If updating, exclude the current instance
            if self.instance:
                existing_collection = existing_collection.exclude(id=self.instance.id)
            
            if existing_collection.exists():
                raise serializers.ValidationError("You already have a collection with this name.")
        
        return value