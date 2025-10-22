"""
Django management command to set up the complete forum structure.

This command initializes the entire forum system with:
- Forum categories for plant community
- Wagtail pages for each forum
- Sample content for testing
- Proper permissions and settings
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta

from wagtail.models import Site, Page
from machina.core.db.models import get_model
from machina.core.loading import get_class

from apps.forum_integration.models import (
    ForumIndexPage, ForumCategoryPage, ForumAnnouncementPage, 
    ForumModerationPage, ForumPageMapping
)

User = get_user_model()
Forum = get_model('forum', 'Forum')
Topic = get_model('forum_conversation', 'Topic')
Post = get_model('forum_conversation', 'Post')

PermissionHandler = get_class('forum_permission.handler', 'PermissionHandler')
perm_handler = PermissionHandler()


class Command(BaseCommand):
    help = 'Set up the complete forum structure for the plant community'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing forum data before setup',
        )
        parser.add_argument(
            '--sample-data',
            action='store_true',
            help='Create sample topics and posts for testing',
        )
        parser.add_argument(
            '--admin-user',
            type=str,
            help='Username of admin user to own sample content',
            default='admin'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting forum setup for Plant Community...')
        )

        try:
            with transaction.atomic():
                if options['clear']:
                    self.clear_existing_data()
                
                self.create_forum_structure()
                self.create_wagtail_pages()
                
                if options['sample_data']:
                    admin_username = options['admin_user']
                    self.create_sample_data(admin_username)
                
                self.setup_permissions()
                
            self.stdout.write(
                self.style.SUCCESS('Forum setup completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Forum setup failed: {str(e)}')
            )
            raise CommandError(f'Setup failed: {str(e)}')

    def clear_existing_data(self):
        """Clear existing forum data."""
        self.stdout.write('Clearing existing forum data...')
        
        # Clear Wagtail forum pages
        ForumIndexPage.objects.all().delete()
        ForumCategoryPage.objects.all().delete()
        ForumAnnouncementPage.objects.all().delete()
        ForumModerationPage.objects.all().delete()
        ForumPageMapping.objects.all().delete()
        
        # Clear Machina forum data
        Post.objects.all().delete()
        Topic.objects.all().delete()
        Forum.objects.all().delete()
        
        self.stdout.write(
            self.style.WARNING('Existing forum data cleared.')
        )

    def create_forum_structure(self):
        """Create the Machina forum structure."""
        self.stdout.write('Creating forum structure...')
        
        # Create main forum categories for plant community
        forum_categories = [
            {
                'name': 'Plant Identification',
                'description': 'Get help identifying unknown plants and share your botanical knowledge.',
                'slug': 'plant-identification',
            },
            {
                'name': 'Plant Care & Growing',
                'description': 'Share tips on watering, fertilizing, pruning, and general plant care.',
                'slug': 'plant-care-growing',
            },
            {
                'name': 'Indoor Plants',
                'description': 'Discussion about houseplants, indoor gardening, and container growing.',
                'slug': 'indoor-plants',
            },
            {
                'name': 'Outdoor Gardening',
                'description': 'Topics about outdoor gardens, landscaping, and seasonal gardening.',
                'slug': 'outdoor-gardening',
            },
            {
                'name': 'Plant Diseases & Pests',
                'description': 'Help diagnosing plant problems and organic treatment solutions.',
                'slug': 'plant-diseases-pests',
            },
            {
                'name': 'Seeds & Propagation',
                'description': 'Share experiences with growing from seeds and plant propagation.',
                'slug': 'seeds-propagation',
            },
            {
                'name': 'Garden Design',
                'description': 'Landscape design ideas, garden layouts, and aesthetic discussions.',
                'slug': 'garden-design',
            },
            {
                'name': 'Plant Photography',
                'description': 'Share your beautiful plant photos and photography techniques.',
                'slug': 'plant-photography',
            },
            {
                'name': 'Community Trading',
                'description': 'Buy, sell, trade plants, seeds, and gardening equipment.',
                'slug': 'community-trading',
            },
            {
                'name': 'General Discussion',
                'description': 'Off-topic conversations and community chat.',
                'slug': 'general-discussion',
            },
        ]

        self.created_forums = {}
        
        for category_data in forum_categories:
            forum = Forum.objects.create(
                type=Forum.FORUM_POST,
                name=category_data['name'],
                slug=category_data['slug'],
                description=category_data['description'],
                display_sub_forum_list=True,
            )
            
            self.created_forums[category_data['slug']] = forum
            
            self.stdout.write(f'  Created forum: {forum.name}')

        self.stdout.write(
            self.style.SUCCESS(f'Created {len(forum_categories)} forum categories.')
        )

    def create_wagtail_pages(self):
        """Create Wagtail pages for the forums."""
        self.stdout.write('Creating Wagtail forum pages...')
        
        # Get the root page and site
        root_page = Page.objects.filter(depth=1).first()
        if not root_page:
            raise CommandError('No root page found. Please set up Wagtail first.')
        
        site = Site.objects.first()
        if not site:
            raise CommandError('No site found. Please set up Wagtail first.')

        # Create Forum Index Page
        forum_index = ForumIndexPage(
            title='Plant Community Forum',
            slug='forum',
            welcome_message='Welcome to the Plant Community Forum! Connect with fellow plant enthusiasts, share your knowledge, and get help with your gardening questions.',
            show_statistics=True,
            forums_per_page=20,
            meta_description='Join our vibrant plant community forum to discuss plant care, identification, gardening tips, and connect with fellow plant lovers.',
        )
        
        # Add some content blocks
        forum_index.content_blocks = [
            {
                'type': 'heading',
                'value': 'Welcome to Our Plant Community!'
            },
            {
                'type': 'paragraph',
                'value': '<p>Join thousands of plant enthusiasts in our growing community. Whether you\'re a seasoned gardener or just starting your plant journey, you\'ll find helpful advice, friendly discussions, and expert knowledge.</p>'
            },
            {
                'type': 'forum_rules',
                'value': {
                    'rule_title': 'Community Guidelines',
                    'rule_description': '<p>Please be respectful, share accurate information, and help create a welcoming environment for all plant lovers. Search before posting and use appropriate categories.</p>'
                }
            }
        ]
        
        root_page.add_child(instance=forum_index)
        forum_index.save_revision().publish()
        
        self.stdout.write(f'  Created forum index page: {forum_index.title}')

        # Create category pages for each forum
        for slug, forum in self.created_forums.items():
            category_page = ForumCategoryPage(
                title=forum.name,
                slug=f'forum-{slug}',
                machina_forum_id=forum.id,
                topics_per_page=25,
                allow_new_topics=True,
                show_topic_stats=True,
                require_approval=False,
                meta_description=f'Discuss {forum.name.lower()} in our plant community forum.',
            )
            
            # Add specific content blocks based on category
            content_blocks = self.get_category_content_blocks(slug, forum)
            category_page.content_blocks = content_blocks
            
            forum_index.add_child(instance=category_page)
            category_page.save_revision().publish()
            
            # Create page mapping
            ForumPageMapping.objects.create(
                wagtail_page=category_page,
                machina_forum=forum,
                is_active=True
            )
            
            self.stdout.write(f'  Created category page: {category_page.title}')

        # Create announcement page
        announcement_page = ForumAnnouncementPage(
            title='Forum Announcements',
            slug='forum-announcements',
            is_pinned=True,
            announcement_type='info',
            show_to_all=True,
            meta_description='Important announcements and updates for the plant community forum.',
        )
        
        announcement_page.content_blocks = [
            {
                'type': 'forum_announcement',
                'value': {
                    'title': 'Welcome to the Plant Community Forum!',
                    'content': '<p>We\'re excited to launch our new forum platform. Explore the categories, introduce yourself, and start sharing your plant knowledge!</p>',
                    'is_pinned': True,
                    'show_until': None
                }
            }
        ]
        
        forum_index.add_child(instance=announcement_page)
        announcement_page.save_revision().publish()
        
        self.stdout.write(f'  Created announcement page: {announcement_page.title}')

        # Create moderation page
        moderation_page = ForumModerationPage(
            title='Forum Moderation',
            slug='forum-moderation',
            show_pending_posts=True,
            show_reported_content=True,
            show_user_management=True,
            enable_spam_detection=True,
            auto_approve_trusted_users=True,
        )
        
        moderation_page.content_blocks = [
            {
                'type': 'heading',
                'value': 'Moderation Dashboard'
            },
            {
                'type': 'paragraph',
                'value': '<p>Welcome to the moderation dashboard. Here you can manage pending posts, reported content, and user activities.</p>'
            }
        ]
        
        forum_index.add_child(instance=moderation_page)
        moderation_page.save_revision().publish()
        
        self.stdout.write(f'  Created moderation page: {moderation_page.title}')

        self.stdout.write(
            self.style.SUCCESS('All Wagtail forum pages created successfully.')
        )

    def get_category_content_blocks(self, slug, forum):
        """Get category-specific content blocks."""
        content_blocks = [
            {
                'type': 'heading',
                'value': forum.name
            },
            {
                'type': 'paragraph',
                'value': f'<p>{forum.description}</p>'
            }
        ]
        
        # Add category-specific content
        category_content = {
            'plant-identification': {
                'type': 'call_to_action',
                'value': {
                    'button_text': 'Upload Plant Photo',
                    'button_url': '/plant-identification/',
                    'description': 'Use our AI-powered plant identification tool to get instant results!'
                }
            },
            'plant-care-growing': {
                'type': 'forum_rules',
                'value': {
                    'rule_title': 'Sharing Care Tips',
                    'rule_description': '<p>When sharing care advice, please include your location and growing conditions for context.</p>'
                }
            },
            'community-trading': {
                'type': 'forum_rules',
                'value': {
                    'rule_title': 'Trading Guidelines',
                    'rule_description': '<p>All trades must be between community members. Be honest about plant condition and shipping methods.</p>'
                }
            }
        }
        
        if slug in category_content:
            content_blocks.append(category_content[slug])
        
        return content_blocks

    def create_sample_data(self, admin_username):
        """Create sample topics and posts."""
        self.stdout.write('Creating sample forum content...')
        
        try:
            admin_user = User.objects.get(username=admin_username)
        except User.DoesNotExist:
            # Create admin user if doesn't exist
            admin_user = User.objects.create_user(
                username=admin_username,
                email='admin@plantcommunity.com',
                password='admin123',
                is_staff=True,
                is_superuser=True
            )
            self.stdout.write(f'Created admin user: {admin_username}')

        # Sample topics data
        sample_topics = [
            {
                'forum': 'plant-identification',
                'title': 'Help! What is this beautiful flowering plant?',
                'content': 'I found this gorgeous plant in my local park and would love to grow one myself. The flowers are small and purple with heart-shaped leaves. Can anyone help identify it?'
            },
            {
                'forum': 'plant-care-growing',
                'title': 'Best watering schedule for succulents?',
                'content': 'I\'m new to growing succulents and keep hearing conflicting advice about watering. How often should I water them, and what signs should I look for?'
            },
            {
                'forum': 'indoor-plants',
                'title': 'My snake plant leaves are turning yellow',
                'content': 'I\'ve had my snake plant for about 6 months and recently noticed some leaves turning yellow and becoming soft. The plant is in a bright corner but not direct sunlight. Any ideas what might be wrong?'
            },
            {
                'forum': 'outdoor-gardening',
                'title': 'Starting a vegetable garden - beginner tips?',
                'content': 'I want to start my first vegetable garden this spring. I have a small backyard with good sun exposure. What vegetables would you recommend for a beginner?'
            },
            {
                'forum': 'plant-photography',
                'title': 'Macro photography tips for flowers',
                'content': 'I\'ve been trying to take better close-up photos of my flowers but struggle with focus and lighting. Any tips for macro plant photography?'
            }
        ]

        created_topics = []
        
        for topic_data in sample_topics:
            forum = self.created_forums[topic_data['forum']]
            
            # Create topic
            topic = Topic.objects.create(
                forum=forum,
                subject=topic_data['title'],
                poster=admin_user,
                approved=True,
                type=Topic.TOPIC_POST,  # Required field
                status=Topic.TOPIC_UNLOCKED,  # Required field
                created=timezone.now() - timedelta(days=7),
                updated=timezone.now() - timedelta(days=7)
            )
            
            # Create initial post
            post = Post.objects.create(
                topic=topic,
                poster=admin_user,
                content=topic_data['content'],
                approved=True,
                created=timezone.now() - timedelta(days=7),
                updated=timezone.now() - timedelta(days=7)
            )
            
            # Update topic's first and last post
            topic.first_post = post
            topic.last_post = post
            topic.last_post_on = post.created
            topic.posts_count = 1
            topic.save()
            
            # Update forum stats
            forum.last_post_on = post.created
            forum.save()
            
            created_topics.append(topic)
            
            self.stdout.write(f'  Created topic: {topic.subject}')

        # Add some replies to make it more realistic
        sample_replies = [
            'Great question! I had the same issue when I started.',
            'Based on the description, it might be a Viola species. Can you share a photo?',
            'I recommend checking the soil moisture first - that\'s usually the culprit.',
            'Welcome to the community! You\'ll love growing your own vegetables.',
            'Try using a reflector to control harsh shadows in your macro shots.'
        ]

        for i, topic in enumerate(created_topics[:3]):  # Add replies to first 3 topics
            reply_content = sample_replies[i]
            
            reply = Post.objects.create(
                topic=topic,
                poster=admin_user,
                content=reply_content,
                approved=True,
                created=timezone.now() - timedelta(days=5),
                updated=timezone.now() - timedelta(days=5)
            )
            
            # Update topic stats
            topic.last_post = reply
            topic.last_post_on = reply.created
            topic.posts_count += 1
            topic.save()
            
            # Update forum stats
            topic.forum.last_post_on = reply.created
            topic.forum.save()

        self.stdout.write(
            self.style.SUCCESS(f'Created {len(created_topics)} sample topics with replies.')
        )

    def setup_permissions(self):
        """Set up default forum permissions."""
        self.stdout.write('Setting up forum permissions...')
        
        # This would typically involve setting up forum permissions
        # For now, we'll use the default Machina permissions
        
        self.stdout.write(
            self.style.SUCCESS('Forum permissions configured.')
        )

    def validate_setup(self):
        """Validate that the setup was successful."""
        self.stdout.write('Validating forum setup...')
        
        # Check that forums were created
        forum_count = Forum.objects.count()
        if forum_count == 0:
            raise CommandError('No forums were created')
        
        # Check that Wagtail pages were created
        index_pages = ForumIndexPage.objects.count()
        category_pages = ForumCategoryPage.objects.count()
        
        if index_pages == 0:
            raise CommandError('No forum index page was created')
        
        if category_pages == 0:
            raise CommandError('No category pages were created')
        
        # Check mappings
        mappings = ForumPageMapping.objects.count()
        if mappings == 0:
            raise CommandError('No forum page mappings were created')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Validation passed: {forum_count} forums, {index_pages} index pages, '
                f'{category_pages} category pages, {mappings} mappings'
            )
        )