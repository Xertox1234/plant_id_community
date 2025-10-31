"""
Forum Test Data Generator

This script creates comprehensive test data for manual QA testing of forum pagination.

Usage:
    python manage.py shell < create_forum_test_data.py

What it creates:
- 3 forum categories (Plant Care, Identification, General)
- 5 threads across categories with varying post counts:
  - Thread 1: 5 posts (no pagination needed)
  - Thread 2: 20 posts (exactly 1 page, no Load More)
  - Thread 3: 35 posts (2 pages, tests Load More)
  - Thread 4: 75 posts (4 pages, tests multiple loads)
  - Thread 5: 120 posts (6 pages, tests large datasets)
- 1 pinned thread
- 1 locked thread
"""

from django.contrib.auth import get_user_model
from apps.forum.models import Category, Thread, Post
from django.utils.text import slugify
import random

User = get_user_model()

def create_forum_test_data():
    """Create comprehensive forum test data for QA testing."""

    print("\n" + "="*70)
    print("🌱 Forum Test Data Generator")
    print("="*70 + "\n")

    # Get or create test user
    print("👤 Creating test users...")
    test_user, created = User.objects.get_or_create(
        username='forum_tester',
        defaults={
            'email': 'tester@plantcommunity.com',
            'first_name': 'Forum',
            'last_name': 'Tester',
        }
    )
    if created:
        test_user.set_password('testpass123')
        test_user.save()
        print(f"   ✅ Created user: {test_user.username}")
    else:
        print(f"   ✅ Using existing user: {test_user.username}")

    # Create moderator user
    moderator, created = User.objects.get_or_create(
        username='test_moderator',
        defaults={
            'email': 'moderator@plantcommunity.com',
            'first_name': 'Test',
            'last_name': 'Moderator',
            'is_staff': True,
        }
    )
    if created:
        moderator.set_password('modpass123')
        moderator.save()
        print(f"   ✅ Created moderator: {moderator.username}")
    else:
        print(f"   ✅ Using existing moderator: {moderator.username}")

    # Create categories
    print("\n📁 Creating categories...")
    categories_data = [
        {
            'name': 'Plant Care Tips',
            'slug': 'plant-care',
            'description': 'Share and learn plant care techniques, watering schedules, and maintenance tips.',
            'icon': '🌱'
        },
        {
            'name': 'Plant Identification',
            'slug': 'identification',
            'description': 'Help identify unknown plants and discuss plant species.',
            'icon': '🔍'
        },
        {
            'name': 'General Discussion',
            'slug': 'general',
            'description': 'General plant-related discussions and community chat.',
            'icon': '💬'
        }
    ]

    categories = []
    for cat_data in categories_data:
        category, created = Category.objects.get_or_create(
            slug=cat_data['slug'],
            defaults=cat_data
        )
        categories.append(category)
        status = "Created" if created else "Using existing"
        print(f"   ✅ {status}: {category.name} ({category.slug})")

    # Create threads with varying post counts
    print("\n💬 Creating test threads...")
    threads_data = [
        {
            'category': categories[0],
            'title': 'Small Thread - 5 Posts (No Pagination)',
            'post_count': 5,
            'is_pinned': False,
            'is_locked': False,
        },
        {
            'category': categories[0],
            'title': 'Exact Page - 20 Posts (No Load More)',
            'post_count': 20,
            'is_pinned': False,
            'is_locked': False,
        },
        {
            'category': categories[1],
            'title': 'Medium Thread - 35 Posts (2 Pages)',
            'post_count': 35,
            'is_pinned': True,  # Test pinned thread
            'is_locked': False,
        },
        {
            'category': categories[1],
            'title': 'Large Thread - 75 Posts (4 Pages)',
            'post_count': 75,
            'is_pinned': False,
            'is_locked': False,
        },
        {
            'category': categories[2],
            'title': 'Very Large Thread - 120 Posts (6 Pages)',
            'post_count': 120,
            'is_pinned': False,
            'is_locked': False,
        },
        {
            'category': categories[2],
            'title': 'Locked Thread - 25 Posts (Testing Locked State)',
            'post_count': 25,
            'is_pinned': False,
            'is_locked': True,  # Test locked thread
        }
    ]

    for idx, thread_data in enumerate(threads_data, 1):
        post_count = thread_data.pop('post_count')
        category = thread_data['category']

        # Create thread
        thread, created = Thread.objects.get_or_create(
            slug=slugify(thread_data['title']),
            defaults={
                **thread_data,
                'author': test_user,
                'excerpt': f'Test thread with {post_count} posts for pagination testing.'
            }
        )

        status = "Created" if created else "Using existing"
        print(f"\n   📌 Thread {idx}: {thread.title}")
        print(f"      Status: {status}")
        print(f"      Category: {category.name}")
        print(f"      Target posts: {post_count}")

        # Count existing posts
        existing_posts = Post.objects.filter(thread=thread).count()

        if existing_posts >= post_count:
            print(f"      ✅ Already has {existing_posts} posts (target: {post_count})")
            continue

        # Create posts
        posts_to_create = post_count - existing_posts
        print(f"      Creating {posts_to_create} posts...")

        for i in range(posts_to_create):
            post_num = existing_posts + i + 1

            # Vary authors to make it more realistic
            author = moderator if i % 5 == 0 else test_user

            # Create varied content
            content = generate_post_content(post_num, thread.title)

            Post.objects.create(
                thread=thread,
                author=author,
                content_raw=content,
                content_format='rich',
                is_first_post=(post_num == 1)
            )

            # Print progress every 20 posts
            if (i + 1) % 20 == 0 or (i + 1) == posts_to_create:
                print(f"         ... {i + 1}/{posts_to_create} posts created")

        # Update thread stats
        thread.post_count = Post.objects.filter(thread=thread).count()
        thread.save()

        print(f"      ✅ Thread has {thread.post_count} posts total")
        if thread.is_pinned:
            print(f"      📌 Thread is PINNED")
        if thread.is_locked:
            print(f"      🔒 Thread is LOCKED")

    # Print summary
    print("\n" + "="*70)
    print("✅ Test Data Generation Complete!")
    print("="*70)

    print("\n📊 Summary:")
    print(f"   Users: {User.objects.filter(username__in=['forum_tester', 'test_moderator']).count()}")
    print(f"   Categories: {Category.objects.count()}")
    print(f"   Threads: {Thread.objects.count()}")
    print(f"   Posts: {Post.objects.count()}")

    print("\n🧪 Test Scenarios Available:")
    print("   1. Small thread (5 posts) - No pagination")
    print("   2. Exact page (20 posts) - No Load More button")
    print("   3. Medium thread (35 posts) - 2 pages, test Load More")
    print("   4. Large thread (75 posts) - 4 pages, multiple loads")
    print("   5. Very large (120 posts) - 6 pages, performance test")
    print("   6. Locked thread (25 posts) - Test locked state")

    print("\n🌐 Access the forum:")
    print("   Frontend: http://localhost:5174/forum")
    print("   Backend Admin: http://localhost:8000/admin/")

    print("\n👤 Test Credentials:")
    print("   Username: forum_tester")
    print("   Password: testpass123")
    print("\n   Moderator: test_moderator")
    print("   Password: modpass123")

    print("\n" + "="*70 + "\n")


def generate_post_content(post_num, thread_title):
    """Generate varied post content for testing."""

    content_templates = [
        f'<p>This is test post #{post_num} in the "{thread_title}" thread.</p><p>Testing pagination functionality with realistic content.</p>',
        f'<p><strong>Post #{post_num}:</strong> Great discussion! I have some thoughts on this topic.</p><p>Here are my observations based on experience...</p>',
        f'<p>Post #{post_num} - Adding to the conversation with some helpful tips:</p><ul><li>Tip 1: Regular watering is key</li><li>Tip 2: Monitor for pests</li><li>Tip 3: Provide adequate sunlight</li></ul>',
        f'<p>Thanks for sharing! This is post #{post_num}.</p><blockquote>Very informative thread!</blockquote>',
        f'<h2>Post #{post_num} Analysis</h2><p>After reviewing the information, here are my conclusions...</p><p>This pagination test is working well!</p>',
        f'<p>Post number {post_num} checking in! 👋</p><p>The forum is looking great with proper pagination support.</p>',
        f'<p><em>Quick update from post #{post_num}:</em></p><p>Everything seems to be functioning correctly. Load More is smooth!</p>',
        f'<p>Post #{post_num}: <code>Testing inline code</code> and formatting options.</p><p>Pagination handles all content types well.</p>',
    ]

    # Pick a template based on post number for variety
    template_idx = post_num % len(content_templates)
    return content_templates[template_idx]


# Run the data generation
if __name__ == '__main__':
    create_forum_test_data()
else:
    # When run via shell, execute automatically
    create_forum_test_data()
