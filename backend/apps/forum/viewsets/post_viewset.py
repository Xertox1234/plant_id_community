"""
Post viewset for forum API.

Provides CRUD operations for forum posts with full reaction and attachment support.
"""

import logging
from typing import Dict, Any, Type, List
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import IsAuthenticatedOrReadOnly, BasePermission
from rest_framework.serializers import Serializer
from django.db.models import QuerySet

from ..models import Post
from ..serializers import (
    PostSerializer,
    PostCreateSerializer,
    PostUpdateSerializer,
)
from ..permissions import IsAuthorOrReadOnly, IsModerator, IsAuthorOrModerator

logger = logging.getLogger(__name__)


class PostViewSet(viewsets.ModelViewSet):
    """
    ViewSet for forum posts.

    Provides:
    - List: Posts in a thread (filter by thread slug required)
    - Retrieve: Single post detail with reactions and attachments
    - Create: New post in thread (PostCreateSerializer)
    - Update: Edit post (PostUpdateSerializer) - auto-marks as edited
    - Delete: Soft delete (sets is_active=False)

    Query Parameters:
        - thread (slug): Filter by thread slug (required for list)
        - author (username): Filter by author username
        - ordering (str): Sort order (e.g., created_at, -created_at)

    Performance:
        - select_related('author', 'thread', 'edited_by')
        - prefetch_related('reactions', 'attachments')
        - Pagination enabled (default 20 per page)
    """

    queryset = Post.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['created_at']  # Chronological order (oldest first)

    def get_queryset(self) -> QuerySet[Post]:
        """
        Get posts queryset with optimized prefetching.

        Performance optimization:
        - select_related('author', 'thread', 'edited_by')
        - prefetch_related('reactions', 'attachments')

        Returns:
            QuerySet with active posts, optimized for serialization
        """
        qs = super().get_queryset()

        # Filter active posts only
        is_active = self.request.query_params.get('is_active', 'true')
        if is_active.lower() == 'true':
            qs = qs.filter(is_active=True)

        # Always select related for performance
        qs = qs.select_related('author', 'thread', 'edited_by')

        # Prefetch reactions and attachments to avoid N+1
        qs = qs.prefetch_related('reactions', 'attachments')

        # Filter by thread slug (required for list view)
        thread_slug = self.request.query_params.get('thread')
        if thread_slug:
            qs = qs.filter(thread__slug=thread_slug)

        # Filter by author username
        author_username = self.request.query_params.get('author')
        if author_username:
            qs = qs.filter(author__username=author_username)

        return qs

    def get_serializer_class(self) -> Type[Serializer]:
        """
        Use different serializers for different actions.

        Returns:
            - PostCreateSerializer for create action
            - PostUpdateSerializer for update/partial_update actions
            - PostSerializer for list/retrieve (read-only with full nested data)
        """
        if self.action == 'create':
            return PostCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return PostUpdateSerializer
        return PostSerializer

    def get_permissions(self) -> List[BasePermission]:
        """
        Dynamic permissions based on action.

        Returns:
            - IsAuthorOrReadOnly | IsModerator for update/delete
            - IsAuthenticatedOrReadOnly for list/retrieve/create
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            # Editing requires being author OR moderator
            # Use combined permission class for proper OR logic
            return [IsAuthorOrModerator()]
        return [IsAuthenticatedOrReadOnly()]

    def get_serializer_context(self) -> Dict[str, Any]:
        """
        Add request to serializer context for absolute URLs.

        Returns:
            Dict with request object
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def list(self, request: Request, *args, **kwargs) -> Response:
        """
        List posts in a thread.

        Requires thread query parameter.

        Returns:
            List of posts in chronological order
        """
        thread_slug = request.query_params.get('thread')

        if not thread_slug:
            return Response(
                {
                    'error': 'thread parameter is required',
                    'detail': 'Please provide a thread slug to filter posts'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().list(request, *args, **kwargs)

    def create(self, request: Request, *args, **kwargs) -> Response:
        """
        Create a new post.

        Uses PostCreateSerializer for input validation,
        but returns PostSerializer for full response data.

        Returns:
            Full post data including author, timestamps, etc.
        """
        # Validate input with PostCreateSerializer
        create_serializer = self.get_serializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)

        # Create post (calls PostCreateSerializer.create())
        self.perform_create(create_serializer)
        post_instance = create_serializer.instance

        # Return full PostSerializer for response
        response_serializer = PostSerializer(post_instance, context=self.get_serializer_context())
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer) -> None:
        """
        Create post with author set from request user.

        Note:
            Author is set in serializer's create() method from request.user.
        """
        serializer.save()
        logger.info(f"[FORUM] Post created in thread {serializer.instance.thread.slug} by {self.request.user.username}")

    def perform_update(self, serializer) -> None:
        """
        Update post and mark as edited.

        Note:
            PostUpdateSerializer handles setting edited_at and edited_by automatically.
        """
        serializer.save()
        logger.info(f"[FORUM] Post {serializer.instance.id} edited by {self.request.user.username}")

    def perform_destroy(self, instance) -> None:
        """
        Soft delete post by setting is_active=False.

        Note:
            We don't actually delete posts to preserve thread integrity.
            Soft deletion allows restoration if needed.
        """
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        logger.info(f"[FORUM] Post {instance.id} soft deleted by {self.request.user.username}")

    @action(detail=False, methods=['GET'])
    def first_posts(self, request: Request) -> Response:
        """
        Get all first posts (thread starters) with optional filtering.

        GET /api/v1/forum/posts/first_posts/?category=plant-care

        Query Parameters:
            - category (slug): Filter by thread category
            - author (username): Filter by author

        Returns:
            List of first posts (thread starters)
        """
        first_posts = self.get_queryset().filter(is_first_post=True)

        # Additional filtering for first posts
        category_slug = request.query_params.get('category')
        if category_slug:
            first_posts = first_posts.filter(thread__category__slug=category_slug)

        page = self.paginate_queryset(first_posts)

        if page is not None:
            serializer = PostSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)

        serializer = PostSerializer(first_posts, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=True, methods=['POST'], permission_classes=[IsAuthorOrModerator])
    def upload_image(self, request: Request, pk=None) -> Response:
        """
        Upload an image attachment to a post.

        POST /api/v1/forum/posts/{post_id}/upload_image/

        Request:
            - Content-Type: multipart/form-data
            - Body: image file

        Validation:
            - Maximum 6 images per post
            - Allowed formats: JPG, PNG, GIF, WebP
            - Maximum file size: 10MB

        Returns:
            {
                "id": "uuid",
                "image": "https://...",
                "image_thumbnail": "https://...",
                "original_filename": "photo.jpg",
                "file_size": 1024000,
                "created_at": "2025-11-03T..."
            }
        """
        from ..models import Attachment
        from ..serializers import AttachmentSerializer
        from django.core.files.uploadedfile import UploadedFile
        from ..constants import (
            MAX_ATTACHMENTS_PER_POST,
            MAX_ATTACHMENT_SIZE_BYTES,
            ALLOWED_IMAGE_EXTENSIONS,
            ALLOWED_IMAGE_MIME_TYPES
        )

        post = self.get_object()

        # Check max attachments limit
        if post.attachments.count() >= MAX_ATTACHMENTS_PER_POST:
            return Response(
                {
                    "error": f"Maximum {MAX_ATTACHMENTS_PER_POST} images allowed per post",
                    "detail": "Please delete an existing image before uploading a new one"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get uploaded file
        image_file = request.FILES.get('image')
        if not image_file:
            return Response(
                {
                    "error": "No image file provided",
                    "detail": "Please provide an 'image' field in the multipart form data"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file extension
        file_extension = image_file.name.split('.')[-1].lower() if '.' in image_file.name else ''
        if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
            return Response(
                {
                    "error": "Invalid file type",
                    "detail": f"Allowed formats: {', '.join(ext.upper() for ext in ALLOWED_IMAGE_EXTENSIONS)}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate MIME type (defense in depth)
        if image_file.content_type not in ALLOWED_IMAGE_MIME_TYPES:
            return Response(
                {
                    "error": "Invalid file content type",
                    "detail": f"File MIME type '{image_file.content_type}' not allowed. Expected: {', '.join(ALLOWED_IMAGE_MIME_TYPES)}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file size
        if image_file.size > MAX_ATTACHMENT_SIZE_BYTES:
            return Response(
                {
                    "error": "File too large",
                    "detail": f"Maximum file size is {MAX_ATTACHMENT_SIZE_BYTES / 1024 / 1024}MB"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create attachment
        try:
            attachment = Attachment.objects.create(
                post=post,
                image=image_file,
                original_filename=image_file.name,
                file_size=image_file.size
            )

            logger.info(
                f"[FORUM] Image uploaded to post {post.id} by {request.user.username}: "
                f"{image_file.name} ({image_file.size} bytes)"
            )

            serializer = AttachmentSerializer(attachment, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"[FORUM] Image upload failed for post {post.id}: {str(e)}")
            return Response(
                {
                    "error": "Image upload failed",
                    "detail": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['DELETE'], permission_classes=[IsAuthorOrModerator], url_path='delete_image/(?P<attachment_id>[^/.]+)')
    def delete_image(self, request: Request, pk=None, attachment_id=None) -> Response:
        """
        Delete an image attachment from a post.

        DELETE /api/v1/forum/posts/{post_id}/delete_image/{attachment_id}/

        Permissions:
            - Post author or moderator only

        Returns:
            204 No Content on success
        """
        from ..models import Attachment

        post = self.get_object()

        # Get attachment
        try:
            attachment = Attachment.objects.get(id=attachment_id, post=post)
        except Attachment.DoesNotExist:
            return Response(
                {
                    "error": "Attachment not found",
                    "detail": f"No attachment with ID {attachment_id} found for this post"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Delete the attachment (cascades to delete the image file)
        filename = attachment.original_filename
        attachment.delete()

        logger.info(
            f"[FORUM] Image deleted from post {post.id} by {request.user.username}: "
            f"{filename}"
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
