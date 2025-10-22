"""
DRF Serializers for Forum API endpoints.
"""

from rest_framework import serializers
from machina.apps.forum.models import Forum
from machina.apps.forum_conversation.models import Topic, Post
from django.contrib.auth import get_user_model
from apps.plant_identification.models import PlantSpeciesPage
from .models import RichPost, PostTemplate, ForumAIUsage, ForumPostImage

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer for forum data."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


class ForumCategorySerializer(serializers.ModelSerializer):
    """Serializer for forum categories."""
    
    topics_count = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    last_activity = serializers.SerializerMethodField()
    
    class Meta:
        model = Forum
        fields = [
            'id', 'name', 'description', 'topics_count', 
            'posts_count', 'last_activity'
        ]
    
    def get_topics_count(self, obj):
        """Get number of topics in this forum."""
        return Topic.objects.filter(forum=obj, approved=True).count()
    
    def get_posts_count(self, obj):
        """Get number of posts in this forum."""
        return Post.objects.filter(topic__forum=obj, approved=True).count()
    
    def get_last_activity(self, obj):
        """Get last activity timestamp."""
        last_post = Post.objects.filter(
            topic__forum=obj, 
            approved=True
        ).order_by('-created').first()
        
        if last_post:
            return last_post.created.isoformat()
        return None


class SimpleTopicSerializer(serializers.ModelSerializer):
    """Simple serializer for topic listings without expensive queries."""
    
    poster = UserSerializer(read_only=True)
    forum = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Topic
        fields = [
            'id', 'subject', 'poster', 'forum', 'created', 'posts_count',
            'last_post_on', 'replies_count', 'views_count'
        ]
    
    def get_forum(self, obj):
        """Get basic forum information."""
        if obj.forum:
            return {
                'id': obj.forum.id,
                'name': obj.forum.name,
                'slug': getattr(obj.forum, 'slug', None)
            }
        return None
    
    def get_replies_count(self, obj):
        """Get number of replies (posts - 1 for original post)."""
        return max(0, obj.posts_count - 1)


class TopicSerializer(serializers.ModelSerializer):
    """Serializer for forum topics."""
    
    poster = UserSerializer(read_only=True)
    forum = serializers.SerializerMethodField()
    last_poster = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Topic
        fields = [
            'id', 'subject', 'poster', 'forum', 'created', 'posts_count',
            'last_post_on', 'last_poster', 'replies_count', 'views_count'
        ]
    
    def get_forum(self, obj):
        """Get basic forum information."""
        if obj.forum:
            return {
                'id': obj.forum.id,
                'name': obj.forum.name,
                'slug': getattr(obj.forum, 'slug', None)
            }
        return None
    
    def get_last_poster(self, obj):
        """Get the user who made the last post."""
        if obj.last_post and obj.last_post.poster:
            return UserSerializer(obj.last_post.poster).data
        return None
    
    def get_replies_count(self, obj):
        """Get number of replies (posts - 1 for original post)."""
        return max(0, obj.posts_count - 1)


class PostSerializer(serializers.ModelSerializer):
    """Serializer for forum posts with rich content support."""
    
    poster = UserSerializer(read_only=True)
    rich_content = serializers.SerializerMethodField()
    content_format = serializers.SerializerMethodField()
    ai_assisted = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            'id', 'content', 'poster', 'created', 'updated',
            'rich_content', 'content_format', 'ai_assisted'
        ]
    
    def get_rich_content(self, obj):
        """Get rich content if available, expanding plant_mention metadata."""
        try:
            rich_post = obj.rich_content
            if rich_post.rich_content:
                return self._expand_rich_content(rich_post.rich_content)
        except RichPost.DoesNotExist:
            pass
        return None
    
    def get_content_format(self, obj):
        """Get content format."""
        try:
            return obj.rich_content.content_format
        except RichPost.DoesNotExist:
            return 'plain'
    
    def get_ai_assisted(self, obj):
        """Check if AI was used."""
        try:
            return obj.rich_content.ai_assisted
        except RichPost.DoesNotExist:
            return False

    def _expand_rich_content(self, content):
        """
        For outbound responses, enrich plant_mention blocks with basic page metadata
        to avoid extra client lookups. Structure is preserved and additional fields are
        additive and backward compatible.
        """
        if not isinstance(content, (list, tuple)):
            return content

        # Collect plant_page IDs in one pass
        ids = []
        for block in content:
            if isinstance(block, dict) and (block.get('type') or block.get('block')) == 'plant_mention':
                value = block.get('value') or {}
                plant_id = value.get('plant_page')
                if isinstance(plant_id, dict):
                    plant_id = plant_id.get('id') or plant_id.get('pk')
                try:
                    plant_id = int(plant_id)
                except (TypeError, ValueError):
                    plant_id = None
                if plant_id:
                    ids.append(plant_id)

        pages = {}
        if ids:
            for page in PlantSpeciesPage.objects.filter(id__in=set(ids)):
                pages[page.id] = {
                    'id': page.id,
                    'title': page.title,
                    'slug': page.slug,
                }

        expanded = []
        for block in content:
            if not isinstance(block, dict):
                expanded.append(block)
                continue
            btype = block.get('type') or block.get('block')
            if btype != 'plant_mention':
                expanded.append(block)
                continue
            value = block.get('value') or {}
            plant_page_ref = value.get('plant_page')
            try:
                plant_id = int(plant_page_ref['id'] if isinstance(plant_page_ref, dict) else plant_page_ref)
            except (TypeError, ValueError, KeyError):
                plant_id = None

            meta = pages.get(plant_id)
            # Merge metadata under 'page' to avoid breaking clients that expect 'plant_page' as id
            new_value = {
                **value,
                'page': meta if meta else None,
            }
            expanded.append({
                **block,
                'value': new_value,
            })

        return expanded


class CreateTopicSerializer(serializers.ModelSerializer):
    """Serializer for creating new topics with rich content support."""
    
    content = serializers.CharField(write_only=True, help_text="First post content")
    rich_content = serializers.JSONField(required=False, write_only=True, help_text="Rich content JSON (Stream-like blocks)")
    content_format = serializers.CharField(required=False, write_only=True, default='plain')
    ai_assisted = serializers.BooleanField(required=False, write_only=True, default=False)
    ai_prompts_used = serializers.JSONField(required=False, write_only=True)
    
    class Meta:
        model = Topic
        fields = ['subject', 'content', 'rich_content', 'content_format', 'ai_assisted', 'ai_prompts_used']
    
    def create(self, validated_data):
        """Create topic and first post with rich content support."""
        content = validated_data.pop('content')
        rich_content = validated_data.pop('rich_content', None)
        content_format = validated_data.pop('content_format', 'plain')
        ai_assisted = validated_data.pop('ai_assisted', False)
        ai_prompts_used = validated_data.pop('ai_prompts_used', None)
        
        forum = self.context['forum']
        user = self.context['request'].user
        
        # Extract subject before creating topic
        subject = validated_data.get('subject', '')
        
        # Create topic
        topic = Topic.objects.create(
            forum=forum,
            poster=user,
            subject=subject,
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True
        )
        
        # Create first post
        post = Post.objects.create(
            topic=topic,
            poster=user,
            content=content,
            approved=True
        )
        
        # WORKAROUND: Django Machina has a bug where creating a Post 
        # clears the topic's subject. We need to restore it.
        topic.subject = subject
        
        # Normalize plant mentions within rich_content, if any
        if rich_content is not None:
            rich_content = self._normalize_rich_content(rich_content)

        # Create rich content if provided
        if rich_content or content_format != 'plain':
            RichPost.objects.create(
                post=post,
                rich_content=rich_content,
                content_format=content_format,
                ai_assisted=ai_assisted,
                ai_prompts_used=ai_prompts_used
            )
        
        # Update topic references
        topic.first_post = post
        topic.last_post = post
        topic.posts_count = 1
        topic.save()
        
        return topic

    def _normalize_rich_content(self, rich_content):
        """
        Normalize incoming rich_content to ensure plant_mention blocks use a valid
        PlantSpeciesPage id and have a consistent structure.

        Expected block format (Stream-like):
        {"type": "plant_mention", "value": {"plant_page": <id|obj>, "display_text": str}}
        """
        # Only process list-like content; otherwise pass through
        if not isinstance(rich_content, (list, tuple)):
            return rich_content

        normalized = []
        for block in rich_content:
            if not isinstance(block, dict):
                normalized.append(block)
                continue

            btype = block.get('type') or block.get('block')  # tolerate alternate key
            if btype != 'plant_mention':
                normalized.append(block)
                continue

            value = block.get('value') or {}
            plant_ref = value.get('plant_page')

            # Coerce plant_page to an integer id
            plant_id = None
            if isinstance(plant_ref, dict):
                plant_id = plant_ref.get('id') or plant_ref.get('pk')
            elif isinstance(plant_ref, (int, str)):
                try:
                    plant_id = int(plant_ref)
                except (TypeError, ValueError):
                    plant_id = None

            if not plant_id:
                raise serializers.ValidationError({
                    'rich_content': 'plant_mention block requires a valid plant_page id'
                })

            # Validate existence
            if not PlantSpeciesPage.objects.filter(id=plant_id).exists():
                raise serializers.ValidationError({
                    'rich_content': f'Invalid plant_page id {plant_id} in plant_mention block'
                })

            normalized.append({
                'type': 'plant_mention',
                'value': {
                    'plant_page': plant_id,
                    'display_text': value.get('display_text') or ''
                }
            })

        return normalized


class CreatePostSerializer(serializers.ModelSerializer):
    """Serializer for creating new posts with rich content support."""
    
    rich_content = serializers.JSONField(required=False, write_only=True, help_text="Rich content JSON (Stream-like blocks)")
    content_format = serializers.CharField(required=False, write_only=True, default='plain')
    ai_assisted = serializers.BooleanField(required=False, write_only=True, default=False)
    ai_prompts_used = serializers.JSONField(required=False, write_only=True)
    
    class Meta:
        model = Post
        fields = ['content', 'rich_content', 'content_format', 'ai_assisted', 'ai_prompts_used']
    
    def create(self, validated_data):
        """Create new post with rich content support."""
        rich_content = validated_data.pop('rich_content', None)
        content_format = validated_data.pop('content_format', 'plain')
        ai_assisted = validated_data.pop('ai_assisted', False)
        ai_prompts_used = validated_data.pop('ai_prompts_used', None)
        
        topic = self.context['topic']
        user = self.context['request'].user
        
        post = Post.objects.create(
            topic=topic,
            poster=user,
            approved=True,
            **validated_data
        )
        
        # Normalize plant mentions within rich_content, if any
        if rich_content is not None:
            rich_content = self._normalize_rich_content(rich_content)

        # Create rich content if provided
        if rich_content or content_format != 'plain':
            RichPost.objects.create(
                post=post,
                rich_content=rich_content,
                content_format=content_format,
                ai_assisted=ai_assisted,
                ai_prompts_used=ai_prompts_used
            )
        
        # Update topic
        topic.last_post = post
        topic.posts_count = Post.objects.filter(topic=topic, approved=True).count()
        topic.save()
        
        return post

    def _normalize_rich_content(self, rich_content):
        """Delegate to CreateTopicSerializer's normalization for consistency."""
        return CreateTopicSerializer._normalize_rich_content(self, rich_content)


class ForumPostImageSerializer(serializers.ModelSerializer):
    """Serializer for forum post images."""
    
    url = serializers.CharField(source='image.url', read_only=True)
    thumbnail_url = serializers.CharField(source='thumbnail.url', read_only=True)
    width = serializers.IntegerField(source='image.width', read_only=True)
    height = serializers.IntegerField(source='image.height', read_only=True)
    
    class Meta:
        model = ForumPostImage
        fields = [
            'id', 'url', 'thumbnail_url', 'alt_text', 'caption',
            'original_filename', 'file_size', 'upload_order',
            'width', 'height', 'uploaded_at'
        ]


class PostWithImagesSerializer(PostSerializer):
    """Post serializer that includes images for feed display."""
    
    images = ForumPostImageSerializer(many=True, read_only=True)
    
    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + ['images']


class TopicWithFirstPostSerializer(serializers.ModelSerializer):
    """Enhanced topic serializer that includes first post content and images for feed display."""
    
    poster = UserSerializer(read_only=True)
    forum = serializers.SerializerMethodField()
    last_poster = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    first_post = PostWithImagesSerializer(read_only=True)
    
    class Meta:
        model = Topic
        fields = [
            'id', 'subject', 'poster', 'forum', 'created', 'posts_count',
            'last_post_on', 'last_poster', 'replies_count', 'views_count',
            'first_post'
        ]
    
    def get_forum(self, obj):
        """Get basic forum information."""
        if obj.forum:
            return {
                'id': obj.forum.id,
                'name': obj.forum.name,
                'slug': getattr(obj.forum, 'slug', None)
            }
        return None
    
    def get_last_poster(self, obj):
        """Get the user who made the last post."""
        if obj.last_post and obj.last_post.poster:
            return UserSerializer(obj.last_post.poster).data
        return None
    
    def get_replies_count(self, obj):
        """Get number of replies (posts - 1 for original post)."""
        return max(0, obj.posts_count - 1)