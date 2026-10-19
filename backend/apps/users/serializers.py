"""
Serializers for user authentication and profile management.
"""

import logging

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import User, UserPlantCollection

logger = logging.getLogger(__name__)


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""

    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True, required=False)
    confirmPassword = serializers.CharField(
        write_only=True, required=False
    )  # Support frontend field name

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "password_confirm",
            "confirmPassword",
            "first_name",
            "last_name",
            "bio",
            "location",
            "gardening_experience",
        ]

    def validate(self, data):
        """
        Validate password confirmation and check for duplicate accounts.

        Security (Issue #155 - CWE-204):
        Returns generic error message for duplicate username OR email to prevent
        account enumeration attacks. Attacker cannot distinguish which field is duplicate.
        """
        password = data.get("password")
        password_confirm = data.get("password_confirm") or data.get("confirmPassword")
        username = data.get("username")
        email = data.get("email")

        # Validate password strength FIRST (better UX - show strength issues before confirmation)
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                raise serializers.ValidationError({"password": e.messages}) from e

        # Then check confirmation match
        if password_confirm and password != password_confirm:
            raise serializers.ValidationError(
                {"confirmPassword": ["Passwords do not match."]}
            )

        # SECURITY FIX (Issue #155): Check for duplicate username OR email
        # Return generic error to prevent enumeration
        if username and User.objects.filter(username=username).exists():
            raise serializers.ValidationError(
                "An account with these credentials already exists. "
                "Please use a different username or email."
            )

        if email and User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "An account with these credentials already exists. "
                "Please use a different username or email."
            )

        return data

    def create(self, validated_data):
        """Create new user account."""
        # Remove password confirmation fields from validated_data
        validated_data.pop("password_confirm", None)
        validated_data.pop("confirmPassword", None)

        # Create user with hashed password
        password = validated_data.pop("password")
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
            "id",
            "username",
            "first_name",
            "last_name",
            "display_name",
            "bio",
            "location",
            "gardening_experience",
            "avatar",
            "avatar_thumbnail",
            "follower_count",
            "following_count",
            "plants_identified",
            "identifications_helped",
            "forum_posts_count",
            "date_joined",
        ]

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_avatar_thumbnail(self, obj):
        """Get avatar thumbnail URL."""
        if obj.avatar:
            request = self.context.get("request")
            if request and hasattr(obj, "avatar_thumbnail"):
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
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "display_name",
            "bio",
            "location",
            "website",
            "gardening_experience",
            "avatar",
            "avatar_thumbnail",
            "profile_visibility",
            "show_email",
            "show_location",
            "email_notifications",
            "plant_id_notifications",
            "forum_notifications",
            # Care-task push opt-out read by the reminder sweep (todo 410).
            "care_reminder_notifications",
            "follower_count",
            "following_count",
            "plants_identified",
            "identifications_helped",
            "forum_posts_count",
            "plant_collections_count",
            "date_joined",
            "last_login",
        ]
        read_only_fields = [
            "username",
            # Identity, not profile data (todo 404): web OAuth, password login and
            # the Firebase legacy fallback all look accounts up by email, and
            # email is not DB-unique. A change needs re-auth + verification.
            "email",
            "date_joined",
            "last_login",
            "plants_identified",
            "identifications_helped",
            "forum_posts_count",
        ]

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_avatar_thumbnail(self, obj):
        """Get avatar thumbnail URL, or None if it cannot be generated.

        The profile views pass the request since todo 455, so this now runs
        on every GET /auth/user/. The thumbnail is generated on first access:
        a missing or unreadable source file must not 500 the whole profile.
        """
        if obj.avatar:
            request = self.context.get("request")
            if request and hasattr(obj, "avatar_thumbnail"):
                try:
                    return request.build_absolute_uri(obj.avatar_thumbnail.url)
                except Exception:
                    # Still a null thumbnail, never a 500, but logged at ERROR
                    # with the traceback: a storage outage or a config bug on
                    # every GET /auth/user/ must reach Sentry as what it is,
                    # not as a bare exception type (todo 565 finding 4).
                    logger.exception("[PROFILE] Avatar thumbnail unavailable")
        return None

    def validate_avatar(self, value):
        """Store the photo without its metadata: EXIF (GPS included) would be
        served to anyone who sees the avatar (todo 565 finding 6). Runs after
        the field's own validators, so ``value`` is a valid image."""
        if not value:
            return value
        from apps.core.validators import MAX_AVATAR_SIZE

        from .avatars import (
            AvatarTooLargeError,
            AvatarUnreadableError,
            strip_image_metadata,
        )

        try:
            return strip_image_metadata(value)
        except AvatarUnreadableError as exc:
            raise serializers.ValidationError("This image could not be read.") from exc
        except AvatarTooLargeError as exc:
            raise serializers.ValidationError(
                f"This image is larger than {MAX_AVATAR_SIZE // (1024 * 1024)} MB"
                " once its metadata is removed."
            ) from exc

    @extend_schema_field(serializers.IntegerField())
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
            "id",
            "user",
            "name",
            "description",
            "is_public",
            "plant_count",
            "plants",
            "created_at",
            "updated_at",
        ]

    # A list of UserPlantSerializer objects (that module imports this one).
    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_plants(self, obj):
        """Get plants in this collection from UserPlant model."""
        try:
            from apps.plant_identification.models import UserPlant
            from apps.plant_identification.serializers import UserPlantSerializer

            plants = UserPlant.objects.filter(collection=obj).select_related(
                "species", "from_identification_request"
            )
            return UserPlantSerializer(plants, many=True, context=self.context).data
        except ImportError:
            # If plant_identification app is not available, return empty list
            return []

    def validate_name(self, value):
        """Ensure collection name is unique for the user."""
        request = self.context.get("request")
        if request and request.user:
            user = request.user
            # Check if collection with this name already exists for this user
            existing_collection = UserPlantCollection.objects.filter(
                user=user, name=value
            )

            # If updating, exclude the current instance
            if self.instance:
                existing_collection = existing_collection.exclude(id=self.instance.id)

            if existing_collection.exists():
                raise serializers.ValidationError(
                    "You already have a collection with this name."
                )

        return value
