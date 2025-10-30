"""
Attachment serializer for forum API.

Provides ImageKit rendition URLs for different sizes.
"""

from rest_framework import serializers
from typing import Dict, Any, Optional

from ..models import Attachment


class AttachmentSerializer(serializers.ModelSerializer):
    """
    Serializer for forum post attachments.

    Provides URLs for original image and ImageKit renditions (thumbnail, medium, large).
    """

    # ImageKit rendition URLs
    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    medium_url = serializers.SerializerMethodField()
    large_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = [
            'id',
            'post',
            'image_url',  # Original image URL
            'thumbnail_url',  # 200x200
            'medium_url',  # 800x600
            'large_url',  # 1200x900
            'original_filename',
            'file_size',
            'mime_type',
            'display_order',
            'alt_text',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'original_filename',  # Set on upload
            'file_size',  # Set on upload
            'mime_type',  # Set on upload (Pillow detection)
            'created_at',
        ]

    def get_image_url(self, obj: Attachment) -> Optional[str]:
        """
        Get original image URL.

        Returns absolute URL if request is available in context.
        """
        if not obj.image:
            return None

        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url

    def get_thumbnail_url(self, obj: Attachment) -> Optional[str]:
        """
        Get thumbnail rendition URL (200x200).

        ImageKit generates this automatically on first access.
        """
        if not obj.image:
            return None

        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return obj.thumbnail.url

    def get_medium_url(self, obj: Attachment) -> Optional[str]:
        """
        Get medium rendition URL (800x600).

        Good for modal/lightbox display.
        """
        if not obj.image:
            return None

        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.medium.url)
        return obj.medium.url

    def get_large_url(self, obj: Attachment) -> Optional[str]:
        """
        Get large rendition URL (1200x900).

        For high-DPI displays or full-screen viewing.
        """
        if not obj.image:
            return None

        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.large.url)
        return obj.large.url
