"""
DRF API Views for Forum Integration.
"""

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.db.models import F
from django.utils import timezone
from machina.core.loading import get_class

from machina.apps.forum.models import Forum
from machina.apps.forum_conversation.models import Topic, Post

# Import Django Machina permission handler
PermissionHandler = get_class('forum_permission.handler', 'PermissionHandler')

from .serializers import (
    ForumCategorySerializer, TopicSerializer, SimpleTopicSerializer, PostSerializer,
    CreateTopicSerializer, CreatePostSerializer, TopicWithFirstPostSerializer
)
from .models import ForumAIUsage, ForumPostImage, PostReaction


class ForumCategoryListView(generics.ListAPIView):
    """List all forum categories."""
    
    serializer_class = ForumCategorySerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        """Return all forum categories."""
        return Forum.objects.filter(
            type=Forum.FORUM_POST
        ).order_by('name')


class ForumTopicsListView(generics.ListAPIView):
    """List topics in a specific forum category."""
    
    serializer_class = TopicSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        """Return topics for specific forum."""
        forum_id = self.kwargs['forum_id']
        return Topic.objects.filter(
            forum_id=forum_id,
            approved=True
        ).select_related('poster', 'last_post', 'last_post__poster').order_by('-last_post_on')


def all_topics_list(request):
    """Simple function-based view for all topics."""
    from django.http import JsonResponse
    from django.core.paginator import Paginator
    
    try:
        # Get topics with simple select_related
        topics = Topic.objects.filter(
            approved=True
        ).select_related('poster', 'forum').order_by('-created')
        
        # Simple pagination
        page_size = int(request.GET.get('page_size', 25))
        page = int(request.GET.get('page', 1))
        
        paginator = Paginator(topics, page_size)
        page_obj = paginator.get_page(page)
        
        # Manual serialization to avoid any serializer issues
        results = []
        for topic in page_obj:
            topic_data = {
                'id': topic.id,
                'subject': topic.subject or 'Untitled Topic',
                'poster': {
                    'id': topic.poster.id,
                    'username': topic.poster.username,
                    'first_name': topic.poster.first_name,
                    'last_name': topic.poster.last_name
                } if topic.poster else None,
                'forum': {
                    'id': topic.forum.id,
                    'name': topic.forum.name
                } if topic.forum else None,
                'created': topic.created.isoformat(),
                'posts_count': topic.posts_count,
                'last_post_on': topic.last_post_on.isoformat() if topic.last_post_on else None,
                'views_count': topic.views_count,
                'replies_count': max(0, topic.posts_count - 1)
            }
            results.append(topic_data)
        
        return JsonResponse({
            'count': paginator.count,
            'next': f'?page={page + 1}' if page_obj.has_next() else None,
            'previous': f'?page={page - 1}' if page_obj.has_previous() else None,
            'results': results
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


class TopicDetailView(generics.RetrieveAPIView):
    """Get topic details and its posts."""
    
    serializer_class = TopicSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_object(self):
        """Get topic by ID."""
        return get_object_or_404(Topic, id=self.kwargs['topic_id'], approved=True)
    
    def retrieve(self, request, *args, **kwargs):
        """Get topic with its posts."""
        topic = self.get_object()
        
        # Get posts with pagination
        posts = Post.objects.filter(
            topic=topic,
            approved=True
        ).select_related('poster').order_by('created')
        
        # Pagination
        page_number = request.GET.get('page', 1)
        paginator = Paginator(posts, 10)  # 10 posts per page
        page_obj = paginator.get_page(page_number)
        
        # Serialize data
        topic_data = self.get_serializer(topic).data
        posts_data = PostSerializer(page_obj.object_list, many=True).data
        
        return Response({
            'topic': topic_data,
            'posts': {
                'results': posts_data,
                'count': paginator.count,
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        })


class CreateTopicView(generics.CreateAPIView):
    """Create a new topic."""
    
    serializer_class = CreateTopicSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_context(self):
        """Add forum to serializer context."""
        context = super().get_serializer_context()
        forum_id = self.kwargs['forum_id']
        context['forum'] = get_object_or_404(Forum, id=forum_id)
        return context
    
    def create(self, request, *args, **kwargs):
        """Create topic and return success response."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        topic = serializer.save()
        
        # Return topic data with first post ID for image uploads
        topic_serializer = TopicSerializer(topic)
        response_data = {
            'message': 'Topic created successfully',
            'topic': topic_serializer.data
        }
        
        # Include first post ID for image uploads
        if topic.first_post:
            response_data['first_post_id'] = topic.first_post.id
        
        return Response(response_data, status=status.HTTP_201_CREATED)


class CreatePostView(generics.CreateAPIView):
    """Create a new post (reply)."""
    
    serializer_class = CreatePostSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_context(self):
        """Add topic to serializer context."""
        context = super().get_serializer_context()
        topic_id = self.kwargs['topic_id']
        context['topic'] = get_object_or_404(Topic, id=topic_id)
        return context
    
    def create(self, request, *args, **kwargs):
        """Create post and return success response."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = serializer.save()
        
        # Return post data
        post_serializer = PostSerializer(post)
        return Response(
            {
                'message': 'Reply posted successfully',
                'post': post_serializer.data
            },
            status=status.HTTP_201_CREATED
        )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def forum_search(request):
    """Search forum topics and posts."""
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 3:
        return Response({
            'error': 'Search query must be at least 3 characters long'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Search topics
    topics = Topic.objects.filter(
        subject__icontains=query,
        approved=True
    ).select_related('forum', 'poster')[:10]
    
    # Search posts
    posts = Post.objects.filter(
        content__icontains=query,
        approved=True
    ).select_related('topic', 'topic__forum', 'poster')[:10]
    
    return Response({
        'query': query,
        'topics': TopicSerializer(topics, many=True).data,
        'posts': PostSerializer(posts, many=True).data
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def forum_stats(request):
    """Get forum statistics."""
    total_topics = Topic.objects.filter(approved=True).count()
    total_posts = Post.objects.filter(approved=True).count()
    
    # Get active users (users who posted in last 30 days)
    from django.utils import timezone
    from datetime import timedelta
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    active_users = Post.objects.filter(
        created__gte=thirty_days_ago,
        approved=True
    ).values('poster').distinct().count()
    
    # Mock online users for now (would need real session tracking)
    online_users = max(1, active_users // 20)  # Rough estimate
    
    return Response({
        'data': {
            'total_topics': total_topics,
            'total_posts': total_posts,
            'total_members': active_users,
            'online_members': online_users
        }
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def forum_ai_assist(request):
    """AI assistance for forum post creation."""
    
    prompt_type = request.data.get('prompt')
    context = request.data.get('context', '')
    selected_text = request.data.get('selectedText', '')
    prompt_label = request.data.get('promptLabel', '')
    
    if not prompt_type:
        return Response(
            {'error': 'Prompt type is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Import AI service (similar to blog AI)
        from apps.blog.ai_prompts import PlantAIPrompts
        
        # Generate forum-specific AI content
        ai_content = generate_forum_ai_content(
            prompt_type=prompt_type,
            context=context,
            selected_text=selected_text,
            user=request.user
        )
        
        return Response({
            'content': ai_content,
            'prompt_type': prompt_type,
            'success': True
        })
        
    except Exception as e:
        return Response(
            {'error': f'AI assistance failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class PostListView(generics.ListAPIView):
    """List posts for a specific topic."""
    
    serializer_class = PostSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        """Return posts for specific topic."""
        topic_id = self.request.GET.get('topic')
        if topic_id:
            return Post.objects.filter(
                topic_id=topic_id,
                approved=True
            ).select_related('poster').order_by('created')
        return Post.objects.none()


class PostCreateView(generics.CreateAPIView):
    """Create a new post (reply)."""
    
    serializer_class = CreatePostSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        """Create post and return success response."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get topic from request data
        topic_id = request.data.get('topic')
        topic = get_object_or_404(Topic, id=topic_id)
        
        # Save with topic context
        serializer.context['topic'] = topic
        serializer.context['request'] = request
        post = serializer.save()
        
        # Return post data
        post_serializer = PostSerializer(post)
        return Response(
            {
                'message': 'Reply posted successfully',
                'data': post_serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class PostUpdateView(generics.UpdateAPIView):
    """Update an existing post."""
    
    serializer_class = CreatePostSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        """Get post by ID and check permissions."""
        post = get_object_or_404(Post, id=self.kwargs['post_id'])
        
        # Check if user can edit this post
        if post.poster != self.request.user and not self.request.user.is_staff:
            raise permissions.PermissionDenied("You cannot edit this post")
        
        return post
    
    def update(self, request, *args, **kwargs):
        """Update post and return updated data."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Return updated post data
        post_serializer = PostSerializer(instance)
        return Response({
            'message': 'Post updated successfully',
            'data': post_serializer.data
        })


class PostDeleteView(generics.DestroyAPIView):
    """Delete a post."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        """Get post by ID and check permissions."""
        post = get_object_or_404(Post, id=self.kwargs['post_id'])
        
        # Check if user can delete this post
        if post.poster != self.request.user and not self.request.user.is_staff:
            raise permissions.PermissionDenied("You cannot delete this post")
        
        return post
    
    def destroy(self, request, *args, **kwargs):
        """Delete post and return success message."""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {'message': 'Post deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )


class TopicMarkViewedView(APIView):
    """Mark a topic as viewed."""
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, topic_id):
        """Mark topic as viewed and increment view count."""
        topic = get_object_or_404(Topic, id=topic_id)
        
        # Increment view count
        topic.views_count = F('views_count') + 1
        topic.save(update_fields=['views_count'])
        
        # If user is authenticated, track their view
        if request.user.is_authenticated:
            # This would typically create a TopicReadTrack entry
            # For now, just increment the count
            pass
        
        return Response({'message': 'Topic marked as viewed'})


class TopicUpdateView(generics.UpdateAPIView):
    """Update topic properties (pin, lock, solve)."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        """Get topic by ID."""
        return get_object_or_404(Topic, id=self.kwargs['topic_id'])
    
    def patch(self, request, *args, **kwargs):
        """Update topic properties."""
        topic = self.get_object()
        
        # Check permissions for moderation actions
        if not (request.user.is_staff or request.user == topic.poster):
            return Response(
                {'error': 'You do not have permission to modify this topic'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update allowed fields
        if 'is_pinned' in request.data and request.user.is_staff:
            topic.type = Topic.TOPIC_STICKY if request.data['is_pinned'] else Topic.TOPIC_POST
        
        if 'is_locked' in request.data and request.user.is_staff:
            topic.status = Topic.TOPIC_LOCKED if request.data['is_locked'] else Topic.TOPIC_UNLOCKED
        
        if 'is_solved' in request.data and (request.user == topic.poster or request.user.is_staff):
            # This is a custom field that might need to be added to the Topic model
            # For now, we'll store it in the topic type
            pass
        
        topic.save()
        
        return Response({
            'message': 'Topic updated successfully',
            'data': TopicSerializer(topic).data
        })


class PostReactionView(APIView):
    """Create, update, or remove reactions on forum posts."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, post_id):
        """Toggle a reaction on a post."""
        reaction_type = request.data.get('reaction_type')
        
        # Validate reaction type
        valid_reactions = ['like', 'love', 'helpful', 'thanks']
        if not reaction_type or reaction_type not in valid_reactions:
            return Response(
                {
                    'error': 'Invalid reaction type',
                    'valid_types': valid_reactions
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate post exists
        post = get_object_or_404(Post, id=post_id, approved=True)
        
        try:
            # Toggle the reaction
            reaction, created = PostReaction.toggle_reaction(
                post_id=post_id,
                user_id=request.user.id,
                reaction_type=reaction_type
            )
            
            # Get updated reaction counts for this post
            reaction_counts = {}
            user_reactions = []
            
            for count_data in PostReaction.get_post_reaction_counts(post_id):
                reaction_counts[count_data['reaction_type']] = {
                    'count': count_data['count'],
                    'users': []  # We don't expose user lists for privacy
                }
            
            # Get current user's reactions
            user_reactions = list(PostReaction.get_user_reactions_for_post(post_id, request.user.id))
            
            return Response({
                'success': True,
                'reaction_type': reaction_type,
                'is_active': reaction.is_active,
                'action': 'added' if (created or reaction.is_active) else 'removed',
                'post_id': post_id,
                'reactions': reaction_counts,
                'user_reactions': user_reactions,
                'message': f'Reaction {reaction_type} {"added" if (created or reaction.is_active) else "removed"}'
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to update reaction: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get(self, request, post_id):
        """Get all reactions for a post."""
        # Validate post exists
        post = get_object_or_404(Post, id=post_id, approved=True)
        
        # Get reaction counts
        reaction_counts = {}
        for count_data in PostReaction.get_post_reaction_counts(post_id):
            reaction_counts[count_data['reaction_type']] = {
                'count': count_data['count'],
                'users': []  # We don't expose user lists for privacy
            }
        
        # Get current user's reactions if authenticated
        user_reactions = []
        if request.user.is_authenticated:
            user_reactions = list(PostReaction.get_user_reactions_for_post(post_id, request.user.id))
        
        return Response({
            'post_id': post_id,
            'reactions': reaction_counts,
            'user_reactions': user_reactions,
            'total_reactions': sum(data['count'] for data in reaction_counts.values())
        })


class PostImageListView(generics.ListAPIView):
    """List images for a specific post."""
    
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, post_id):
        """Get all images for a post."""
        post = get_object_or_404(Post, id=post_id)
        images = ForumPostImage.objects.filter(post=post).order_by('upload_order')
        
        image_data = []
        for image in images:
            image_data.append({
                'id': image.id,
                'original_filename': image.original_filename,
                'file_size': image.file_size,
                'file_size_mb': image.file_size_mb,
                'upload_order': image.upload_order,
                'alt_text': image.alt_text,
                'display_name': image.display_name,
                'image_url': image.image.url if image.image else None,
                'thumbnail_url': image.thumbnail.url if image.thumbnail else None,
                'large_thumbnail_url': image.large_thumbnail.url if image.large_thumbnail else None,
                'created_at': image.created_at.isoformat(),
            })
        
        return Response({
            'post_id': post_id,
            'images': image_data,
            'count': len(image_data)
        })


class PostImageUploadView(APIView):
    """Upload images to a forum post."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, post_id):
        """Upload one or more images to a post."""
        post = get_object_or_404(Post, id=post_id)
        
        # Use Django Machina permission system for file attachments
        perm_handler = PermissionHandler()
        
        # Check if user can attach files to this forum
        if not perm_handler.can_attach_files(post.topic.forum, request.user):
            return Response(
                {
                    'error': 'You do not have permission to upload images',
                    'detail': 'Image uploads require trusted member status. Participate in discussions to gain this privilege.',
                    'permission_required': 'can_attach_file',
                    'help_url': '/help/forum-permissions'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if user can add images to this specific post (ownership or moderation)
        if post.poster != request.user and not request.user.is_staff:
            return Response(
                {'error': 'You can only add images to your own posts'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if images were provided
        if 'images' not in request.FILES:
            return Response(
                {'error': 'No images provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_files = request.FILES.getlist('images')
        
        # Validate number of images (max 6 per post)
        existing_count = ForumPostImage.objects.filter(post=post).count()
        total_count = existing_count + len(uploaded_files)
        
        if total_count > 6:
            return Response(
                {'error': f'Maximum 6 images per post. You have {existing_count} images and are trying to add {len(uploaded_files)} more.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file sizes and types
        max_size = 5 * 1024 * 1024  # 5MB
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        
        uploaded_images = []
        errors = []
        
        for i, uploaded_file in enumerate(uploaded_files):
            # Validate file size
            if uploaded_file.size > max_size:
                errors.append(f'File {uploaded_file.name} is too large. Maximum size is 5MB.')
                continue
            
            # Validate file type
            if uploaded_file.content_type not in allowed_types:
                errors.append(f'File {uploaded_file.name} is not a supported image type.')
                continue
            
            try:
                # Create ForumPostImage
                image = ForumPostImage.objects.create(
                    post=post,
                    image=uploaded_file,
                    original_filename=uploaded_file.name,
                    file_size=uploaded_file.size,
                    alt_text=request.data.get(f'alt_text_{i}', ''),
                    # upload_order will be set automatically in the model's save method
                )
                
                uploaded_images.append({
                    'id': image.id,
                    'original_filename': image.original_filename,
                    'file_size': image.file_size,
                    'file_size_mb': image.file_size_mb,
                    'upload_order': image.upload_order,
                    'alt_text': image.alt_text,
                    'display_name': image.display_name,
                    'image_url': image.image.url,
                    'thumbnail_url': image.thumbnail.url,
                    'large_thumbnail_url': image.large_thumbnail.url,
                    'created_at': image.created_at.isoformat(),
                })
                
            except Exception as e:
                errors.append(f'Failed to upload {uploaded_file.name}: {str(e)}')
        
        response_data = {
            'message': f'Successfully uploaded {len(uploaded_images)} images',
            'images': uploaded_images,
            'post_id': post_id
        }
        
        if errors:
            response_data['errors'] = errors
            response_data['message'] += f' ({len(errors)} failed)'
        
        status_code = status.HTTP_201_CREATED if uploaded_images else status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=status_code)


class PostImageDeleteView(APIView):
    """Delete a specific image from a forum post."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def delete(self, request, post_id, image_id):
        """Delete a specific image."""
        post = get_object_or_404(Post, id=post_id)
        image = get_object_or_404(ForumPostImage, id=image_id, post=post)
        
        # Use Django Machina permission system for file management
        perm_handler = PermissionHandler()
        
        # Check if user can manage files in this forum (basic permission check)
        if not perm_handler.can_attach_files(post.topic.forum, request.user):
            return Response(
                {
                    'error': 'You do not have permission to manage images',
                    'detail': 'Image management requires trusted member status.',
                    'permission_required': 'can_attach_file'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if user can delete this specific image (ownership or moderation)
        if post.poster != request.user and not request.user.is_staff:
            return Response(
                {'error': 'You can only delete images from your own posts'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Store image info before deletion
        image_info = {
            'id': image.id,
            'original_filename': image.original_filename,
            'upload_order': image.upload_order
        }
        
        # Delete the image (this will also delete the files due to ImageKit cleanup)
        image.delete()
        
        return Response({
            'message': 'Image deleted successfully',
            'deleted_image': image_info,
            'post_id': post_id
        })


class PostImageUpdateView(APIView):
    """Update image metadata (alt text, order)."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def patch(self, request, post_id, image_id):
        """Update image metadata."""
        post = get_object_or_404(Post, id=post_id)
        image = get_object_or_404(ForumPostImage, id=image_id, post=post)
        
        # Use Django Machina permission system for file management
        perm_handler = PermissionHandler()
        
        # Check if user can manage files in this forum
        if not perm_handler.can_attach_files(post.topic.forum, request.user):
            return Response(
                {
                    'error': 'You do not have permission to edit images',
                    'detail': 'Image editing requires trusted member status.',
                    'permission_required': 'can_attach_file'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if user can edit this specific image (ownership or moderation)
        if post.poster != request.user and not request.user.is_staff:
            return Response(
                {'error': 'You can only edit images from your own posts'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update allowed fields
        if 'alt_text' in request.data:
            image.alt_text = request.data['alt_text'][:255]  # Limit to field max length
        
        if 'upload_order' in request.data:
            try:
                new_order = int(request.data['upload_order'])
                if 0 <= new_order <= 5:  # Valid range for 6 images (0-5)
                    image.upload_order = new_order
                else:
                    return Response(
                        {'error': 'Upload order must be between 0 and 5'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except (ValueError, TypeError):
                return Response(
                    {'error': 'Invalid upload order value'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        image.save()
        
        return Response({
            'message': 'Image updated successfully',
            'image': {
                'id': image.id,
                'original_filename': image.original_filename,
                'alt_text': image.alt_text,
                'upload_order': image.upload_order,
                'display_name': image.display_name,
                'image_url': image.image.url,
                'thumbnail_url': image.thumbnail.url,
                'large_thumbnail_url': image.large_thumbnail.url,
            }
        })


def generate_forum_ai_content(prompt_type, context, selected_text, user):
    """Generate AI content for forum posts based on prompt type."""
    
    # Forum-specific AI prompts
    prompts = {
        'plant_problem': """
        Based on the plant problem description provided, help create a clear and detailed problem statement.
        Include symptoms, timeline, care history, and environmental conditions.
        
        Context: {context}
        Selected text: {selected_text}
        
        Generate a well-structured plant problem description:
        """,
        
        'care_routine': """
        Create a detailed plant care routine based on the plant information provided.
        Include watering schedule, lighting requirements, feeding, and seasonal care.
        
        Context: {context}
        Selected text: {selected_text}
        
        Generate a comprehensive care routine:
        """,
        
        'solution_steps': """
        Create step-by-step solution instructions for the plant problem described.
        Make it actionable and easy to follow.
        
        Context: {context}
        Selected text: {selected_text}
        
        Generate numbered solution steps:
        """,
        
        'continue': """
        Continue writing the following forum post in a helpful and engaging way:
        
        {context}
        
        Continue from where it left off:
        """,
        
        'correct': """
        Improve the grammar, clarity, and readability of this forum post while keeping the original meaning:
        
        {selected_text if selected_text else context}
        
        Corrected version:
        """
    }
    
    prompt_template = prompts.get(prompt_type, prompts['continue'])
    
    # Format the prompt
    formatted_prompt = prompt_template.format(
        context=context,
        selected_text=selected_text
    )
    
    # For now, return a mock response (in real implementation, call OpenAI API)
    mock_responses = {
        'plant_problem': """**Problem Description:**

My plant is showing the following symptoms:
- Yellowing leaves starting from the bottom
- Drooping despite regular watering  
- Brown tips on leaf edges

**Timeline:** Started about 2 weeks ago
**Care routine:** Watering twice weekly, bright indirect light
**Recent changes:** Moved to a new location near the window

Has anyone experienced similar issues? Looking for advice on diagnosis and treatment.""",

        'care_routine': """**Daily Care:**
- Check soil moisture with finger test
- Rotate plant 1/4 turn for even growth

**Weekly Care:**
- Water when top 1-2 inches of soil are dry
- Wipe leaves with damp cloth
- Check for pests

**Monthly Care:**
- Fertilize with balanced liquid fertilizer (diluted)
- Prune dead or yellowing leaves
- Check if repotting is needed

**Seasonal Notes:**
- Reduce watering in winter
- Increase humidity during dry months""",

        'solution_steps': """1. **Immediate Assessment**
   - Check soil moisture level
   - Examine roots for rot or damage
   - Look for pest signs on leaves and stems

2. **Address Root Issues** 
   - If overwatered, allow soil to dry completely
   - If underwatered, water thoroughly until drainage occurs
   - Consider repotting if root bound

3. **Environmental Adjustment**
   - Move to bright, indirect light location
   - Ensure proper air circulation
   - Maintain consistent temperature

4. **Monitor and Maintain**
   - Check plant daily for first week
   - Adjust care routine based on response
   - Document changes and improvements""",

        'continue': "I'd recommend checking the soil moisture first, as this is often the root cause of many plant issues. You can also examine the roots to see if there's any rot or if the plant has become root-bound.",

        'correct': context  # Return cleaned up version
    }
    
    return mock_responses.get(prompt_type, "I'd be happy to help! Could you provide more details about your specific situation?")


class TopicsFeedView(generics.ListAPIView):
    """
    Enhanced topics list with first post content and images for community feed display.
    
    This endpoint provides rich topic data including:
    - First post content (both plain and rich text)
    - Post images with thumbnails
    - Engagement metrics (views, replies)
    - Author information
    - Forum context
    """
    
    serializer_class = TopicWithFirstPostSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        """Return recent topics with optimized queries for feed display."""
        queryset = Topic.objects.filter(
            approved=True
        ).select_related(
            'poster',           # Topic author
            'forum',            # Forum category
            'first_post',       # First post content
            'first_post__poster',  # First post author
            'last_post',        # Last post for metadata
            'last_post__poster' # Last poster for metadata
        ).prefetch_related(
            'first_post__images'  # Post images
        ).order_by('-last_post_on')  # Most recent activity first
        
        # Optional filtering by forum category
        forum_id = self.request.query_params.get('forum')
        if forum_id:
            queryset = queryset.filter(forum_id=forum_id)
        
        # Optional limit for performance
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                limit = int(limit)
                queryset = queryset[:min(limit, 50)]  # Max 50 items for performance
            except (ValueError, TypeError):
                pass
        
        return queryset


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_trust_level(request):
    """
    Get current user's trust level and permissions.
    
    Returns trust level information, current permissions, and guidance
    on how to improve trust level for forum participation.
    """
    user = request.user
    
    # Check if user is authenticated
    if not user or not user.is_authenticated:
        return Response(
            {'error': 'Authentication required'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    try:
        # Use Django Machina permission handler to check current permissions
        perm_handler = PermissionHandler()
        
        # Check permissions for a sample forum (use first available forum)
        sample_forum = Forum.objects.filter(type=Forum.FORUM_POST).first()
        if not sample_forum:
            return Response(
                {'error': 'No forums available to check permissions'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Check various permission levels with error handling
        permissions_check = {}
        try:
            permissions_check = {
                'can_read_forum': perm_handler.can_read_forum(sample_forum, user),
                'can_start_new_topics': perm_handler.can_start_new_topics(sample_forum, user),
                'can_reply_to_topics': perm_handler.can_reply_to_topics(sample_forum, user),
                'can_attach_files': perm_handler.can_attach_files(sample_forum, user),
                'can_download_files': perm_handler.can_download_files(sample_forum, user),
            }
        except Exception as perm_error:
            # Fallback permissions for authenticated users
            permissions_check = {
                'can_read_forum': True,
                'can_start_new_topics': True,
                'can_reply_to_topics': True,
                'can_attach_files': user.is_staff,
                'can_download_files': True,
            }
        
    except Exception as e:
        return Response(
            {'error': f'Failed to check permissions: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Calculate trust level based on user activity
    user_stats = {
        'posts_count': Post.objects.filter(poster=user, approved=True).count(),
        'topics_count': Topic.objects.filter(poster=user, approved=True).count(),
        'account_age_days': (timezone.now() - user.date_joined).days if user.date_joined else 0,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
    }
    
    # Determine trust level (simple algorithm - can be enhanced)
    trust_level = calculate_trust_level(user_stats, permissions_check)
    
    # Get improvement suggestions
    suggestions = get_trust_level_suggestions(trust_level, user_stats, permissions_check)
    
    return Response({
        'user_id': user.id,
        'username': user.username,
        'trust_level': trust_level,
        'permissions': permissions_check,
        'stats': user_stats,
        'suggestions': suggestions,
        'help_url': '/help/forum-permissions',
        'last_checked': timezone.now().isoformat()
    })


def calculate_trust_level(user_stats, permissions):
    """Calculate user trust level based on activity and permissions."""
    
    # Trust levels:
    # 0: New User (just registered)
    # 1: Basic User (can read and post)
    # 2: Regular User (can upload images)
    # 3: Trusted User (advanced permissions)
    # 4: Veteran User (long-time contributor)
    
    posts = user_stats['posts_count']
    topics = user_stats['topics_count']
    age_days = user_stats['account_age_days']
    
    # Staff always get highest trust level
    if user_stats['is_staff'] or user_stats['is_superuser']:
        return {
            'level': 4,
            'name': 'Staff',
            'description': 'Staff member with full forum privileges'
        }
    
    # Calculate based on activity
    if posts >= 50 and topics >= 10 and age_days >= 30:
        level = 4
        name = 'Veteran User'
        description = 'Long-time active community member'
    elif posts >= 20 and topics >= 5 and age_days >= 14:
        level = 3
        name = 'Trusted User'
        description = 'Regular contributor with advanced privileges'
    elif posts >= 5 and topics >= 1 and age_days >= 7:
        level = 2
        name = 'Regular User'
        description = 'Active member who can upload images'
    elif posts >= 1 or topics >= 1:
        level = 1
        name = 'Basic User'
        description = 'Can participate in discussions'
    else:
        level = 0
        name = 'New User'
        description = 'Welcome! Start participating to unlock features'
    
    return {
        'level': level,
        'name': name,
        'description': description
    }


def get_trust_level_suggestions(trust_level, user_stats, permissions):
    """Get suggestions for improving trust level."""
    
    suggestions = []
    
    # If user cannot attach files (main issue we're solving)
    if not permissions['can_attach_files']:
        if user_stats['posts_count'] < 5:
            needed_posts = 5 - user_stats['posts_count']
            suggestions.append({
                'type': 'posts',
                'message': f'Create {needed_posts} more helpful posts to unlock image uploads',
                'action': 'Reply to topics and share your plant knowledge',
                'progress': user_stats['posts_count'],
                'target': 5
            })
        
        if user_stats['topics_count'] < 1:
            suggestions.append({
                'type': 'topics',
                'message': 'Start your first discussion topic',
                'action': 'Ask a question or share plant care tips',
                'progress': user_stats['topics_count'],
                'target': 1
            })
        
        if user_stats['account_age_days'] < 7:
            remaining_days = 7 - user_stats['account_age_days']
            suggestions.append({
                'type': 'time',
                'message': f'Account needs to be active for {remaining_days} more days',
                'action': 'Keep participating in the community',
                'progress': user_stats['account_age_days'],
                'target': 7
            })
    
    # General engagement suggestions
    if trust_level['level'] < 3:
        suggestions.append({
            'type': 'engagement',
            'message': 'Engage with other members\' posts',
            'action': 'Like helpful posts and provide constructive feedback',
            'progress': None,
            'target': None
        })
    
    if not suggestions:
        suggestions.append({
            'type': 'achievement',
            'message': 'Great job! You have full forum privileges',
            'action': 'Keep being an awesome community member',
            'progress': None,
            'target': None
        })
    
    return suggestions


class UserTopicsListView(generics.ListAPIView):
    """
    List topics created by a specific user.
    
    Provides paginated list of topics created by the specified user,
    with proper permission checks and filtering.
    """
    serializer_class = SimpleTopicSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user_id = self.kwargs['user_id']
        
        # Get topics created by this user
        queryset = Topic.objects.filter(
            poster_id=user_id,
            approved=True
        ).select_related(
            'poster', 'forum', 'last_post', 'last_post__poster'
        ).order_by('-last_post_on')
        
        # Apply permission filtering (only show topics from forums user can access)
        perm_handler = PermissionHandler()
        accessible_forums = []
        
        for forum in Forum.objects.filter(type=Forum.FORUM_POST):
            if perm_handler.can_read_forum(forum, self.request.user):
                accessible_forums.append(forum.id)
        
        queryset = queryset.filter(forum_id__in=accessible_forums)
        
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class UserWatchedTopicsListView(generics.ListAPIView):
    """
    List topics watched by a specific user.
    
    Provides paginated list of topics that the specified user is watching,
    with proper permission checks.
    """
    serializer_class = SimpleTopicSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user_id = self.kwargs['user_id']
        
        # For now, return topics the user has participated in recently
        # This is a simplified implementation - Django Machina has a more complex watching system
        user_posts = Post.objects.filter(
            poster_id=user_id,
            approved=True
        ).values_list('topic_id', flat=True).distinct()
        
        queryset = Topic.objects.filter(
            id__in=user_posts,
            approved=True
        ).select_related(
            'poster', 'forum', 'last_post', 'last_post__poster'
        ).order_by('-last_post_on')
        
        # Apply permission filtering
        perm_handler = PermissionHandler()
        accessible_forums = []
        
        for forum in Forum.objects.filter(type=Forum.FORUM_POST):
            if perm_handler.can_read_forum(forum, self.request.user):
                accessible_forums.append(forum.id)
        
        queryset = queryset.filter(forum_id__in=accessible_forums)
        
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context