"""
Django management command to create demo blog posts for the Plant Community.

This command creates three comprehensive demo blog articles showcasing
the full capabilities of the Wagtail blog system including:
- Plant-specific StreamField blocks
- Rich content with care instructions
- Plant spotlight features
- Gallery and media embeds
- Call-to-action blocks
- Proper categorization and tagging
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
import json

from apps.blog.models import (
    BlogCategory, 
    BlogPostPage, 
    BlogIndexPage,
    BlogSeries
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Create three demo blog posts showcasing plant care content'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without making changes',
        )
        parser.add_argument(
            '--author-email',
            type=str,
            default='demo@plantcommunity.com',
            help='Email of user to assign as blog post author',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing demo posts if they exist',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        author_email = options['author_email']
        overwrite = options['overwrite']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        try:
            with transaction.atomic():
                # Step 1: Setup blog structure
                author = self.setup_author(author_email, dry_run)
                blog_index = self.setup_blog_index(dry_run)
                categories = self.setup_categories(dry_run)
                
                # Step 2: Create demo articles
                demo_posts = self.create_demo_posts(author, blog_index, categories, dry_run, overwrite)
                
                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(f'DRY RUN: Would create {len(demo_posts)} demo blog posts')
                    )
                    transaction.set_rollback(True)
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully created {len(demo_posts)} demo blog posts')
                    )
                    self.stdout.write('')
                    self.stdout.write(self.style.SUCCESS('Demo blog posts:'))
                    for post in demo_posts:
                        if post:
                            self.stdout.write(f'  ✓ {post.title} - /blog/{post.slug}/')
                    
        except Exception as e:
            raise CommandError(f'Failed to create demo blog posts: {e}')
    
    def setup_author(self, author_email, dry_run):
        """Get or create the blog author."""
        try:
            author = User.objects.get(email=author_email)
            self.stdout.write(f'Using existing author: {author.username} ({author.email})')
            return author
        except User.DoesNotExist:
            if dry_run:
                self.stdout.write(f'Would create demo author with email: {author_email}')
                return None
            
            # Create demo author
            author = User.objects.create_user(
                username='plant_blogger',
                email=author_email,
                first_name='Plant',
                last_name='Expert',
                password='demo_password_change_immediately',
                is_staff=True,
                is_superuser=False
            )
            self.stdout.write(
                self.style.SUCCESS(f'Created demo author: {author.username}')
            )
            self.stdout.write(
                self.style.WARNING('IMPORTANT: Change the demo author password!')
            )
            return author
    
    def setup_blog_index(self, dry_run):
        """Get or create the blog index page."""
        try:
            blog_index = BlogIndexPage.objects.get()
            self.stdout.write(f'Using existing blog index: {blog_index.title}')
            return blog_index
        except BlogIndexPage.DoesNotExist:
            if dry_run:
                self.stdout.write('Would create BlogIndexPage')
                return None
            
            # Get the home page to add blog index under it
            from wagtail.models import Page
            home_page = Page.objects.filter(depth=2).first()
            if not home_page:
                raise CommandError('No home page found to create blog index under')
            
            blog_index = BlogIndexPage(
                title='Blog',
                slug='blog',
                introduction='<p>Welcome to the Plant Community blog! Discover plant care tips, identification guides, and growing advice from our community of plant enthusiasts.</p>',
                show_featured_posts=True,
                show_categories=True,
                posts_per_page=12,
                meta_description='Discover plant care tips, identification guides, and growing advice from our plant community.',
            )
            
            home_page.add_child(instance=blog_index)
            blog_index.save_revision().publish()
            
            self.stdout.write(self.style.SUCCESS('Created BlogIndexPage'))
            return blog_index
        except BlogIndexPage.MultipleObjectsReturned:
            blog_index = BlogIndexPage.objects.first()
            self.stdout.write(
                self.style.WARNING(f'Multiple blog indexes found, using: {blog_index.title}')
            )
            return blog_index
    
    def setup_categories(self, dry_run):
        """Create demo blog categories."""
        categories_data = [
            {
                'name': 'Plant Care',
                'slug': 'plant-care',
                'description': 'Comprehensive guides for caring for your plants',
                'icon': 'fas fa-seedling',
                'color': '#28a745',
                'is_featured': True,
            },
            {
                'name': 'Indoor Gardening',
                'slug': 'indoor-gardening',
                'description': 'Tips and tricks for successful indoor plant growing',
                'icon': 'fas fa-home',
                'color': '#17a2b8',
                'is_featured': True,
            },
            {
                'name': 'Beginner Tips',
                'slug': 'beginner-tips',
                'description': 'Essential knowledge for new plant parents',
                'icon': 'fas fa-leaf',
                'color': '#fd7e14',
                'is_featured': True,
            },
        ]
        
        categories = {}
        for cat_data in categories_data:
            if dry_run:
                self.stdout.write(f'Would create/verify category: {cat_data["name"]}')
                categories[cat_data['slug']] = None
                continue
            
            category, created = BlogCategory.objects.get_or_create(
                slug=cat_data['slug'],
                defaults=cat_data
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Created category: {category.name}'))
            else:
                self.stdout.write(f'Category already exists: {category.name}')
            
            categories[cat_data['slug']] = category
        
        return categories
    
    def create_demo_posts(self, author, blog_index, categories, dry_run, overwrite):
        """Create the three demo blog posts."""
        demo_posts_data = [
            {
                'title': 'Complete Guide to Monstera Deliciosa Care',
                'slug': 'monstera-deliciosa-care-guide',
                'category': 'plant-care',
                'difficulty': 'beginner',
                'is_featured': True,
                'tags': ['monstera', 'tropical plants', 'houseplants', 'care guide'],
                'introduction': 'The Monstera Deliciosa, also known as the Swiss Cheese Plant, has become one of the most popular houseplants. Learn everything you need to know to keep your Monstera thriving with this comprehensive care guide.',
                'content_blocks': self.get_monstera_content_blocks(),
                'meta_description': 'Complete care guide for Monstera Deliciosa. Learn about watering, lighting, humidity, and common problems to keep your Swiss Cheese Plant healthy.',
                'publish_date': timezone.now().date() - timedelta(days=7),
            },
            {
                'title': 'Top 10 Low-Light Indoor Plants for Dark Spaces',
                'slug': 'best-low-light-indoor-plants',
                'category': 'indoor-gardening',
                'difficulty': 'beginner',
                'is_featured': True,
                'tags': ['low light', 'indoor plants', 'dark spaces', 'apartment living'],
                'introduction': 'Transform your dimly lit spaces into green oases! These 10 incredible plants thrive in low-light conditions, making them perfect for apartments, offices, and rooms with limited natural light.',
                'content_blocks': self.get_low_light_content_blocks(),
                'meta_description': 'Discover the best low-light indoor plants that thrive in dark spaces. Perfect for apartments and offices with limited natural light.',
                'publish_date': timezone.now().date() - timedelta(days=3),
            },
            {
                'title': 'Spring Plant Propagation: When and How to Start',
                'slug': 'spring-plant-propagation-guide',
                'category': 'beginner-tips',
                'difficulty': 'intermediate',
                'is_featured': False,
                'tags': ['propagation', 'spring', 'plant babies', 'growing tips'],
                'introduction': 'Spring is the perfect time to multiply your plant collection! Learn the best techniques for propagating your favorite plants and discover which species are easiest for beginners to start with.',
                'content_blocks': self.get_propagation_content_blocks(),
                'meta_description': 'Learn when and how to propagate plants in spring. Step-by-step guide to creating new plants from your existing collection.',
                'publish_date': timezone.now().date() - timedelta(days=1),
            },
        ]
        
        created_posts = []
        
        for post_data in demo_posts_data:
            try:
                # Check if post already exists
                existing_post = BlogPostPage.objects.filter(slug=post_data['slug']).first()
                if existing_post and not overwrite:
                    self.stdout.write(f'Post already exists: {post_data["title"]}')
                    created_posts.append(existing_post)
                    continue
                elif existing_post and overwrite:
                    if not dry_run:
                        existing_post.delete()
                    self.stdout.write(f'Overwriting existing post: {post_data["title"]}')
                
                if dry_run:
                    self.stdout.write(f'Would create post: {post_data["title"]}')
                    created_posts.append(None)
                    continue
                
                # Create the blog post
                blog_post = BlogPostPage(
                    title=post_data['title'],
                    slug=post_data['slug'],
                    author=author,
                    publish_date=post_data['publish_date'],
                    introduction=post_data['introduction'],
                    content_blocks=post_data['content_blocks'],
                    difficulty_level=post_data['difficulty'],
                    is_featured=post_data['is_featured'],
                    allow_comments=True,
                    meta_description=post_data['meta_description'],
                )
                
                # Add to blog index
                blog_index.add_child(instance=blog_post)
                
                # Associate with category
                if categories[post_data['category']]:
                    blog_post.categories.add(categories[post_data['category']])
                
                # Add tags
                for tag_name in post_data['tags']:
                    blog_post.tags.add(tag_name)
                
                # Save and publish
                blog_post.save_revision().publish()
                
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created post: {blog_post.title}')
                )
                created_posts.append(blog_post)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to create {post_data["title"]}: {e}')
                )
                if not dry_run:
                    raise
                created_posts.append(None)
        
        return created_posts
    
    def get_monstera_content_blocks(self):
        """Content blocks for the Monstera care guide."""
        return [
            ('heading', 'Why Monstera Deliciosa is Perfect for Plant Parents'),
            ('paragraph', '<p>The Monstera Deliciosa has captured the hearts of plant enthusiasts worldwide with its iconic split leaves and easy-going nature. Originally from the rainforests of Central America, this stunning plant has adapted beautifully to indoor life, making it perfect for both beginners and experienced plant parents.</p>'),
            
            ('plant_spotlight', {
                'plant_name': 'Monstera Deliciosa',
                'scientific_name': 'Monstera deliciosa',
                'description': '<p>A stunning tropical plant known for its large, glossy leaves with natural splits and holes called fenestrations. As the plant matures, the leaves develop more dramatic splits, creating an impressive architectural presence in any space.</p>',
                'care_difficulty': 'easy',
            }),
            
            ('heading', 'Essential Care Requirements'),
            ('care_instructions', {
                'care_title': 'Monstera Deliciosa Care Essentials',
                'watering': '<p>Water when the top 1-2 inches of soil feel dry. Monsteras prefer consistent moisture but not soggy soil. In summer, this typically means watering every 1-2 weeks, and less frequently in winter. Always check the soil rather than following a strict schedule.</p>',
                'lighting': '<p>Bright, indirect light is ideal. Direct sunlight can scorch the leaves, while too little light will slow growth and reduce fenestration. A spot near a north or east-facing window, or a few feet back from a south-facing window works perfectly.</p>',
                'temperature': '65-85°F (18-29°C) - avoid cold drafts',
                'humidity': '40-60% - appreciates extra humidity but adapts to average home conditions',
                'fertilizing': '<p>Feed monthly during spring and summer with a balanced liquid fertilizer diluted to half strength. No fertilizer needed in fall and winter when growth naturally slows.</p>',
                'special_notes': '<p>Provide a moss pole or trellis for support as the plant grows. Clean leaves regularly with a damp cloth to keep them glossy and help with photosynthesis.</p>'
            }),
            
            ('heading', 'Common Problems and Solutions'),
            ('paragraph', '<p><strong>Yellow leaves:</strong> Usually indicates overwatering. Check soil moisture and adjust watering schedule. Remove yellow leaves at the base.</p><p><strong>Brown leaf tips:</strong> Often caused by low humidity or water quality issues. Try using filtered water and increasing humidity around the plant.</p><p><strong>No fenestrations:</strong> Young plants have solid leaves. Fenestrations develop with age and adequate light. Be patient and ensure your plant gets enough bright, indirect light.</p>'),
            
            ('heading', 'Pro Tips for Maximum Growth'),
            ('paragraph', '<p>• Rotate your Monstera weekly for even growth<br>• Wipe leaves monthly to remove dust<br>• Propagate from stem cuttings with aerial roots<br>• Repot every 2-3 years or when rootbound<br>• Use well-draining potting mix with perlite or orchid bark</p>'),
            
            ('call_to_action', {
                'cta_title': 'Need Help Identifying Your Plant?',
                'cta_description': '<p>Not sure if your plant is a true Monstera Deliciosa? Use our AI-powered plant identification tool to get instant, accurate results!</p>',
                'button_text': 'Identify My Plant',
                'button_url': '/identify/',
                'button_style': 'primary'
            }),
        ]
    
    def get_low_light_content_blocks(self):
        """Content blocks for the low-light plants article."""
        return [
            ('heading', 'Why Low-Light Plants Are Game Changers'),
            ('paragraph', '<p>Living in a space with limited natural light doesn\'t mean you have to give up your plant dreams! These incredible low-light champions have evolved to thrive in the understory of forests, making them perfectly adapted to dimmer indoor conditions.</p>'),
            
            ('heading', '1. ZZ Plant (Zamioculcas zamiifolia)'),
            ('plant_spotlight', {
                'plant_name': 'ZZ Plant',
                'scientific_name': 'Zamioculcas zamiifolia',
                'description': '<p>The ultimate low-maintenance plant with glossy, architectural leaves that seem to glow even in low light. This African native stores water in its rhizomes, making it incredibly drought-tolerant.</p>',
                'care_difficulty': 'easy',
            }),
            
            ('heading', '2. Pothos (Epipremnum aureum)'),
            ('plant_spotlight', {
                'plant_name': 'Golden Pothos',
                'scientific_name': 'Epipremnum aureum',
                'description': '<p>A vining beauty that thrives in almost any condition. Its heart-shaped leaves with golden variegation brighten up any dark corner, and it\'s virtually indestructible for beginners.</p>',
                'care_difficulty': 'easy',
            }),
            
            ('heading', '3. Snake Plant (Sansevieria trifasciata)'),
            ('plant_spotlight', {
                'plant_name': 'Snake Plant',
                'scientific_name': 'Sansevieria trifasciata',
                'description': '<p>With its striking upright leaves and incredible tolerance for neglect, the snake plant is perfect for busy plant parents. It even purifies air while you sleep!</p>',
                'care_difficulty': 'easy',
            }),
            
            ('heading', 'Quick Care Tips for Low-Light Success'),
            ('paragraph', '<p><strong>Watering:</strong> Less light = less growth = less water needed. Always check soil moisture before watering.</p><p><strong>Rotation:</strong> Turn plants weekly so all sides get equal light exposure.</p><p><strong>Dusting:</strong> Clean leaves monthly to maximize light absorption.</p><p><strong>Patience:</strong> Growth will be slower in low light, and that\'s perfectly normal!</p>'),
            
            ('heading', 'More Low-Light Champions'),
            ('paragraph', '<p>• <strong>Peace Lily:</strong> Beautiful white blooms in low light<br>• <strong>Cast Iron Plant:</strong> Lives up to its tough name<br>• <strong>Chinese Evergreen:</strong> Stunning patterned foliage<br>• <strong>Philodendron:</strong> Heart-shaped leaves, various varieties<br>• <strong>Dracaena:</strong> Tree-like structure, easy care<br>• <strong>Parlor Palm:</strong> Adds tropical vibes to any space<br>• <strong>Monstera Adansonii:</strong> Mini monstera with delicate fenestrations</p>'),
            
            ('call_to_action', {
                'cta_title': 'Join Our Plant Community',
                'cta_description': '<p>Connect with fellow plant lovers, share your low-light setups, and get personalized advice from experienced growers!</p>',
                'button_text': 'Join the Forum',
                'button_url': '/forum/',
                'button_style': 'secondary'
            }),
        ]
    
    def get_propagation_content_blocks(self):
        """Content blocks for the propagation guide."""
        return [
            ('heading', 'Why Spring is Propagation Season'),
            ('paragraph', '<p>As daylight hours increase and temperatures warm up, plants naturally enter their most active growth phase. This makes spring the ideal time to take cuttings, as plants have the energy to develop new roots and recover quickly from pruning.</p>'),
            
            ('heading', 'Best Plants for Beginner Propagators'),
            ('plant_spotlight', {
                'plant_name': 'Pothos',
                'scientific_name': 'Epipremnum aureum',
                'description': '<p>The perfect starter plant for propagation! Pothos roots readily in water, showing visible progress within days. Each cutting with a node can become a new plant.</p>',
                'care_difficulty': 'easy',
            }),
            
            ('plant_spotlight', {
                'plant_name': 'Rubber Tree',
                'scientific_name': 'Ficus elastica',
                'description': '<p>Rubber trees propagate beautifully from stem cuttings. Their thick stems root reliably, and you can even propagate from single leaves with stems attached.</p>',
                'care_difficulty': 'easy',
            }),
            
            ('heading', 'Water Propagation: The Easiest Method'),
            ('paragraph', '<p><strong>Step 1:</strong> Cut a 4-6 inch stem with at least one node (the bump where leaves grow from)<br><strong>Step 2:</strong> Remove lower leaves that would sit underwater<br><strong>Step 3:</strong> Place cutting in clean water, change water every 3-5 days<br><strong>Step 4:</strong> Wait for roots to develop (1-4 weeks depending on plant)<br><strong>Step 5:</strong> Plant in soil when roots are 1-2 inches long</p>'),
            
            ('heading', 'Soil Propagation: For Faster Establishment'),
            ('paragraph', '<p>Some plants prefer to root directly in soil. Use a well-draining potting mix, keep consistently moist (not soggy), and provide bright, indirect light. Cover with a clear plastic bag to maintain humidity if needed.</p>'),
            
            ('care_instructions', {
                'care_title': 'Propagation Care Essentials',
                'watering': '<p>Keep water cuttings in clean, room-temperature water. For soil propagation, maintain consistent moisture without waterlogging.</p>',
                'lighting': '<p>Bright, indirect light is ideal. Avoid direct sun which can stress new cuttings. A north or east-facing window works perfectly.</p>',
                'temperature': '65-75°F (18-24°C) for optimal rooting',
                'humidity': 'Higher humidity helps - cover with plastic bag or use humidity dome',
                'fertilizing': '<p>No fertilizer needed until new growth appears, then use diluted fertilizer monthly.</p>',
                'special_notes': '<p>Be patient! Root development can take 2-8 weeks depending on the plant species and conditions.</p>'
            }),
            
            ('heading', 'Troubleshooting Common Issues'),
            ('paragraph', '<p><strong>Cutting wilts:</strong> Normal for first few days as plant adjusts. Increase humidity and ensure adequate moisture.</p><p><strong>Mushy stems:</strong> Sign of rot. Trim affected area and start fresh with clean tools and water.</p><p><strong>No root development:</strong> Some plants are slower than others. Ensure cutting has nodes and try rooting hormone if available.</p>'),
            
            ('video_embed', {
                'video_title': 'Visual Propagation Guide',
                'video_url': 'https://youtube.com/watch?v=dQw4w9WgXcQ',
                'description': '<p>Watch our step-by-step video guide showing propagation techniques for common houseplants. Perfect for visual learners!</p>'
            }),
            
            ('call_to_action', {
                'cta_title': 'Share Your Propagation Success!',
                'cta_description': '<p>We\'d love to see your plant babies! Share photos of your propagation journey and get tips from our community.</p>',
                'button_text': 'Share in Forum',
                'button_url': '/forum/',
                'button_style': 'primary'
            }),
        ]