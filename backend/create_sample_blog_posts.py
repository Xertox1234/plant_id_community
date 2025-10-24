"""
Create sample blog posts for testing the web interface.

Run with: python manage.py shell < create_sample_blog_posts.py
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plant_community_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from wagtail.models import Site, Page, Locale
from apps.blog.models import BlogIndexPage, BlogPostPage, BlogCategory
import json

User = get_user_model()

print("🌱 Creating sample blog posts...")

# Get or create admin user
admin_user, created = User.objects.get_or_create(
    username='admin',
    defaults={
        'email': 'admin@plantcommunity.com',
        'first_name': 'Plant',
        'last_name': 'Expert',
        'is_staff': True,
        'is_superuser': True,
    }
)
if created:
    admin_user.set_password('admin123')
    admin_user.save()
    print(f"✅ Created admin user: {admin_user.username}")
else:
    print(f"✅ Using existing admin user: {admin_user.username}")

# Get or create locale
locale, _ = Locale.objects.get_or_create(language_code='en')

# Get or create site
try:
    site = Site.objects.get(is_default_site=True)
    root_page = site.root_page
    print(f"✅ Using existing site: {site.hostname}")
except Site.DoesNotExist:
    root_page = Page.objects.filter(depth=1).first()
    if not root_page:
        root_page = Page.add_root(title='Root', locale=locale)
    site = Site.objects.create(
        hostname='localhost',
        root_page=root_page,
        is_default_site=True,
        site_name='Plant Community'
    )
    print(f"✅ Created new site: {site.hostname}")

# Get or create BlogIndex
blog_index = BlogIndexPage.objects.filter(slug='blog').first()
if not blog_index:
    blog_index = BlogIndexPage(
        title='Blog',
        slug='blog',
        introduction='Expert guides, tips, and stories from the plant community',
    )
    root_page.add_child(instance=blog_index)
    blog_index.save_revision().publish()
    print("✅ Created Blog Index page")
else:
    print(f"✅ Using existing Blog Index: {blog_index.title}")

# Create categories
categories_data = [
    {'name': 'Care Guides', 'slug': 'care-guides', 'description': 'Learn how to care for your plants'},
    {'name': 'Plant Science', 'slug': 'plant-science', 'description': 'Botanical knowledge and research'},
    {'name': 'Indoor Plants', 'slug': 'indoor-plants', 'description': 'Perfect plants for your home'},
    {'name': 'Gardening Tips', 'slug': 'gardening-tips', 'description': 'Expert gardening advice'},
]

categories = {}
for cat_data in categories_data:
    category, created = BlogCategory.objects.get_or_create(
        slug=cat_data['slug'],
        defaults={
            'name': cat_data['name'],
            'description': cat_data['description'],
        }
    )
    categories[cat_data['slug']] = category
    if created:
        print(f"✅ Created category: {category.name}")

# Sample blog posts data
blog_posts_data = [
    {
        'title': 'The Ultimate Guide to Monstera Deliciosa Care',
        'slug': 'ultimate-monstera-care-guide',
        'introduction': 'Learn everything you need to know about caring for the beloved Swiss Cheese Plant, from watering schedules to propagation techniques.',
        'categories': ['care-guides', 'indoor-plants'],
        'tags': ['monstera', 'tropical', 'beginner-friendly'],
        'view_count': 1547,
        'content_blocks': [
            {
                'type': 'heading',
                'value': 'Why Monstera Deliciosa is Perfect for Beginners'
            },
            {
                'type': 'paragraph',
                'value': '<p>The Monstera Deliciosa, also known as the Swiss Cheese Plant, has become one of the most popular houseplants in recent years. Its large, fenestrated leaves create a stunning tropical aesthetic, while its relatively forgiving nature makes it perfect for both beginners and experienced plant parents.</p>'
            },
            {
                'type': 'heading',
                'value': 'Light Requirements'
            },
            {
                'type': 'paragraph',
                'value': '<p>Monsteras thrive in <strong>bright, indirect light</strong>. While they can tolerate lower light conditions, you\'ll notice faster growth and more dramatic leaf fenestration in brighter spots. Avoid direct sunlight, which can scorch the leaves.</p>'
            },
            {
                'type': 'quote',
                'value': {
                    'quote': 'A happy Monstera in the right light will reward you with massive, beautifully split leaves that can reach over 2 feet in length.',
                    'attribution': 'Sarah Chen, Indoor Plant Specialist'
                }
            },
            {
                'type': 'heading',
                'value': 'Watering Schedule'
            },
            {
                'type': 'paragraph',
                'value': '<p>Water your Monstera when the top 2-3 inches of soil feel dry. In most homes, this means watering every 1-2 weeks. Always ensure good drainage to prevent root rot.</p>'
            },
        ]
    },
    {
        'title': 'Understanding Photosynthesis: How Plants Convert Light to Energy',
        'slug': 'photosynthesis-explained',
        'introduction': 'Dive deep into the fascinating process that powers all plant life on Earth. Discover how chlorophyll, sunlight, and carbon dioxide work together to create the energy plants need to grow.',
        'categories': ['plant-science'],
        'tags': ['science', 'education', 'biology'],
        'view_count': 892,
        'content_blocks': [
            {
                'type': 'heading',
                'value': 'The Chemistry of Life'
            },
            {
                'type': 'paragraph',
                'value': '<p>Photosynthesis is the fundamental process that sustains nearly all life on Earth. Through this remarkable chemical reaction, plants convert light energy into chemical energy stored in glucose molecules.</p>'
            },
            {
                'type': 'heading',
                'value': 'The Two Stages of Photosynthesis'
            },
            {
                'type': 'paragraph',
                'value': '<p>Photosynthesis occurs in two main stages: the <strong>light-dependent reactions</strong> and the <strong>Calvin cycle</strong> (light-independent reactions).</p>'
            },
            {
                'type': 'code',
                'value': {
                    'language': 'text',
                    'code': '6CO₂ + 6H₂O + light energy → C₆H₁₂O₆ + 6O₂\n\nCarbon dioxide + Water + Light → Glucose + Oxygen'
                }
            },
        ]
    },
    {
        'title': '10 Low-Light Indoor Plants That Thrive in Shade',
        'slug': 'low-light-indoor-plants',
        'introduction': 'Not everyone has a south-facing window, but that doesn\'t mean you can\'t enjoy beautiful houseplants! Discover our top picks for plants that excel in low-light conditions.',
        'categories': ['indoor-plants', 'care-guides'],
        'tags': ['low-light', 'apartment', 'easy-care'],
        'view_count': 2341,
        'content_blocks': [
            {
                'type': 'heading',
                'value': '1. Snake Plant (Sansevieria)'
            },
            {
                'type': 'paragraph',
                'value': '<p>Nearly indestructible and tolerant of neglect, the Snake Plant is perfect for beginners. It can survive in very low light and requires minimal watering.</p>'
            },
            {
                'type': 'heading',
                'value': '2. Pothos (Epipremnum aureum)'
            },
            {
                'type': 'paragraph',
                'value': '<p>With its trailing vines and heart-shaped leaves, Pothos is one of the most adaptable houseplants. It thrives in low light and is incredibly easy to propagate.</p>'
            },
            {
                'type': 'plant_spotlight',
                'value': {
                    'heading': 'ZZ Plant (Zamioculcas zamiifolia)',
                    'description': '<p>The ZZ Plant is virtually maintenance-free and can tolerate extremely low light. Its glossy, dark green leaves add elegance to any room.</p>',
                    'care_level': 'Very Easy'
                }
            },
        ]
    },
    {
        'title': 'Composting 101: Turn Kitchen Scraps into Black Gold',
        'slug': 'composting-basics',
        'introduction': 'Learn how to create nutrient-rich compost from everyday kitchen and garden waste. This beginner-friendly guide covers everything from choosing a bin to troubleshooting common problems.',
        'categories': ['gardening-tips'],
        'tags': ['composting', 'sustainability', 'soil'],
        'view_count': 1123,
        'content_blocks': [
            {
                'type': 'heading',
                'value': 'What is Compost?'
            },
            {
                'type': 'paragraph',
                'value': '<p>Compost is decomposed organic matter that enriches soil, improves drainage, and provides essential nutrients to plants. It\'s often called "black gold" by gardeners because of its incredible benefits.</p>'
            },
            {
                'type': 'heading',
                'value': 'The Browns and Greens Rule'
            },
            {
                'type': 'paragraph',
                'value': '<p>Successful composting requires a balance of "brown" materials (carbon-rich) and "green" materials (nitrogen-rich).</p>'
            },
            {
                'type': 'call_to_action',
                'value': {
                    'heading': 'Start Your Composting Journey Today!',
                    'description': 'Download our free composting guide with detailed instructions and troubleshooting tips.',
                    'button_text': 'Get Free Guide',
                    'button_url': '/resources/composting-guide'
                }
            },
        ]
    },
    {
        'title': 'Propagating Succulents: A Step-by-Step Visual Guide',
        'slug': 'succulent-propagation-guide',
        'introduction': 'Multiply your succulent collection for free! This comprehensive guide walks you through leaf propagation, stem cuttings, and offsets with detailed photos and tips.',
        'categories': ['care-guides'],
        'tags': ['succulents', 'propagation', 'how-to'],
        'view_count': 1876,
        'content_blocks': [
            {
                'type': 'heading',
                'value': 'Three Methods of Succulent Propagation'
            },
            {
                'type': 'paragraph',
                'value': '<p>Succulents are incredibly easy to propagate, making them perfect for beginners. Learn the three main methods: leaf propagation, stem cuttings, and division of offsets.</p>'
            },
            {
                'type': 'quote',
                'value': {
                    'quote': 'The best part about propagating succulents? You can create an entire collection from a single plant, completely free!',
                    'attribution': 'Maria Rodriguez, Succulent Enthusiast'
                }
            },
        ]
    },
]

# Create blog posts
print("\n📝 Creating blog posts...")
for post_data in blog_posts_data:
    # Check if post already exists
    if BlogPostPage.objects.filter(slug=post_data['slug']).exists():
        print(f"⏭️  Post already exists: {post_data['title']}")
        continue

    # Create post
    post = BlogPostPage(
        title=post_data['title'],
        slug=post_data['slug'],
        author=admin_user,
        publish_date=timezone.now().date(),
        introduction=post_data['introduction'],
        view_count=post_data['view_count'],
        content_blocks=json.dumps(post_data['content_blocks']),
    )

    # Add to blog index
    blog_index.add_child(instance=post)

    # Add categories (many-to-many relationship)
    for cat_slug in post_data['categories']:
        post.categories.add(categories[cat_slug])

    # Add tags
    post.tags.add(*post_data['tags'])

    # Publish
    revision = post.save_revision()
    revision.publish()

    print(f"✅ Created: {post.title} ({post.view_count:,} views)")

print("\n🎉 Sample blog posts created successfully!")
print(f"\n📊 Summary:")
print(f"   - Blog Index: {blog_index.title}")
print(f"   - Total Posts: {BlogPostPage.objects.count()}")
print(f"   - Categories: {BlogCategory.objects.count()}")
print(f"\n🌐 Visit: http://localhost:5173/blog")
