"""
Test forum ThreadViewSet.

Tests CRUD operations, filtering, custom actions, permissions, and view tracking.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from ..models import Thread, Post, Category, UserProfile

User = get_user_model()


class ThreadViewSetTests(TestCase):
    """Test ThreadViewSet API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create users with different trust levels
        self.new_user = User.objects.create_user(username='newuser', password='pass')
        UserProfile.objects.create(user=self.new_user, trust_level='new')

        self.basic_user = User.objects.create_user(username='basic', password='pass')
        UserProfile.objects.create(user=self.basic_user, trust_level='basic')

        self.author = User.objects.create_user(username='author', password='pass')
        UserProfile.objects.create(user=self.author, trust_level='trusted')

        self.other_user = User.objects.create_user(username='other', password='pass')
        UserProfile.objects.create(user=self.other_user, trust_level='basic')

        # Create moderator
        self.moderator_group = Group.objects.get_or_create(name="Moderators")[0]
        self.moderator = User.objects.create_user(username='moderator', password='pass')
        self.moderator.groups.add(self.moderator_group)
        UserProfile.objects.create(user=self.moderator, trust_level='expert')

        # Create category
        self.category = Category.objects.create(
            name='Plant Care',
            slug='plant-care',
            description='General plant care topics',
            is_active=True
        )

        # Create threads
        self.thread1 = Thread.objects.create(
            title='How to water succulents',
            slug='how-to-water-succulents',
            author=self.author,
            category=self.category,
            excerpt='Tips for watering succulents',
            is_pinned=False,
            is_locked=False,
            is_active=True
        )

        self.thread2 = Thread.objects.create(
            title='Pinned: Community Guidelines',
            slug='community-guidelines',
            author=self.moderator,
            category=self.category,
            excerpt='Please read before posting',
            is_pinned=True,
            is_locked=True,
            is_active=True
        )

        self.inactive_thread = Thread.objects.create(
            title='Inactive Thread',
            slug='inactive-thread',
            author=self.author,
            category=self.category,
            excerpt='This thread is inactive',
            is_active=False
        )

        # Create first posts
        Post.objects.create(
            thread=self.thread1,
            author=self.author,
            content_raw='Detailed watering guide...',
            is_first_post=True,
            is_active=True
        )

        Post.objects.create(
            thread=self.thread2,
            author=self.moderator,
            content_raw='Community guidelines content...',
            is_first_post=True,
            is_active=True
        )

    def test_list_threads(self):
        """GET /threads/ returns active threads ordered by pinned then activity."""
        response = self.client.get('/api/v1/forum/threads/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

        results = response.data['results']
        slugs = [thread['slug'] for thread in results]

        # Active threads included
        self.assertIn('how-to-water-succulents', slugs)
        self.assertIn('community-guidelines', slugs)

        # Inactive threads excluded
        self.assertNotIn('inactive-thread', slugs)

        # Pinned thread should come first
        self.assertEqual(results[0]['slug'], 'community-guidelines')
        self.assertTrue(results[0]['is_pinned'])

    def test_filter_by_category(self):
        """GET /threads/?category=plant-care filters by category slug."""
        response = self.client.get('/api/v1/forum/threads/?category=plant-care')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        # All threads should be in plant-care category
        for thread in results:
            self.assertEqual(thread['category']['slug'], 'plant-care')

    def test_filter_by_author(self):
        """GET /threads/?author=author filters by author username."""
        response = self.client.get('/api/v1/forum/threads/?author=author')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        # All threads should be by author
        for thread in results:
            self.assertEqual(thread['author']['username'], 'author')

    def test_filter_by_pinned(self):
        """GET /threads/?is_pinned=true filters pinned threads."""
        response = self.client.get('/api/v1/forum/threads/?is_pinned=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        # All threads should be pinned
        for thread in results:
            self.assertTrue(thread['is_pinned'])

        slugs = [thread['slug'] for thread in results]
        self.assertIn('community-guidelines', slugs)
        self.assertNotIn('how-to-water-succulents', slugs)

    def test_filter_by_locked(self):
        """GET /threads/?is_locked=true filters locked threads."""
        response = self.client.get('/api/v1/forum/threads/?is_locked=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        # All threads should be locked
        for thread in results:
            self.assertTrue(thread['is_locked'])

        slugs = [thread['slug'] for thread in results]
        self.assertIn('community-guidelines', slugs)
        self.assertNotIn('how-to-water-succulents', slugs)

    def test_search_threads(self):
        """GET /threads/?search=succulents searches in title and excerpt."""
        response = self.client.get('/api/v1/forum/threads/?search=succulents')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        slugs = [thread['slug'] for thread in results]
        self.assertIn('how-to-water-succulents', slugs)
        self.assertNotIn('community-guidelines', slugs)

    def test_retrieve_thread_increments_view_count(self):
        """GET /threads/{slug}/ increments view_count."""
        initial_views = self.thread1.view_count

        response = self.client.get(f'/api/v1/forum/threads/{self.thread1.slug}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['slug'], self.thread1.slug)

        # Refresh from database
        self.thread1.refresh_from_db()
        self.assertEqual(self.thread1.view_count, initial_views + 1)

    def test_retrieve_thread_includes_first_post(self):
        """GET /threads/{slug}/ includes first post content."""
        response = self.client.get(f'/api/v1/forum/threads/{self.thread1.slug}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('first_post', response.data)
        self.assertIsNotNone(response.data['first_post'])
        self.assertEqual(
            response.data['first_post']['content_raw'],
            'Detailed watering guide...'
        )

    def test_create_thread_requires_trust_level(self):
        """POST /threads/ requires trust_level != 'new'."""
        # New user denied
        self.client.force_authenticate(user=self.new_user)
        response = self.client.post(
            '/api/v1/forum/threads/',
            {
                'title': 'New Thread',
                'category': str(self.category.id),
                'excerpt': 'A new thread',
                'first_post_content': 'This is the first post content.'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Basic user allowed
        self.client.force_authenticate(user=self.basic_user)
        response = self.client.post(
            '/api/v1/forum/threads/',
            {
                'title': 'New Thread',
                'category': str(self.category.id),
                'excerpt': 'A new thread',
                'first_post_content': 'This is the first post content.'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'New Thread')

    def test_create_thread_creates_first_post(self):
        """POST /threads/ creates thread and first post atomically."""
        self.client.force_authenticate(user=self.basic_user)

        response = self.client.post(
            '/api/v1/forum/threads/',
            {
                'title': 'Thread with First Post',
                'category': str(self.category.id),
                'excerpt': 'A test thread',
                'first_post_content': 'This is my first post content.'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify thread created (check by title, not slug since it's auto-generated)
        thread = Thread.objects.get(title='Thread with First Post')
        self.assertEqual(thread.author, self.basic_user)

        # Verify first post created
        first_post = Post.objects.get(thread=thread, is_first_post=True)
        self.assertEqual(first_post.author, self.basic_user)
        self.assertEqual(first_post.content_raw, 'This is my first post content.')

    def test_update_thread_requires_author_or_moderator(self):
        """PATCH /threads/{slug}/ requires author or moderator."""
        # Other user denied
        self.client.force_authenticate(user=self.other_user)
        response = self.client.patch(
            f'/api/v1/forum/threads/{self.thread1.slug}/',
            {'title': 'Updated Title'}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Author allowed
        self.client.force_authenticate(user=self.author)
        response = self.client.patch(
            f'/api/v1/forum/threads/{self.thread1.slug}/',
            {'title': 'Updated by Author'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated by Author')

        # Moderator allowed (even though not author)
        self.client.force_authenticate(user=self.moderator)
        response = self.client.patch(
            f'/api/v1/forum/threads/{self.thread1.slug}/',
            {'title': 'Updated by Moderator'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated by Moderator')

    def test_delete_thread_requires_author_or_moderator(self):
        """DELETE /threads/{slug}/ requires author or moderator."""
        test_thread = Thread.objects.create(
            title='To Delete',
            slug='to-delete',
            author=self.author,
            category=self.category,
            is_active=True
        )

        # Other user denied
        self.client.force_authenticate(user=self.other_user)
        response = self.client.delete(f'/api/v1/forum/threads/{test_thread.slug}/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Author allowed
        self.client.force_authenticate(user=self.author)
        response = self.client.delete(f'/api/v1/forum/threads/{test_thread.slug}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deletion
        self.assertFalse(Thread.objects.filter(slug='to-delete').exists())

    def test_pinned_action_returns_pinned_threads(self):
        """GET /threads/pinned/ returns only pinned threads."""
        response = self.client.get('/api/v1/forum/threads/pinned/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        # All threads should be pinned
        for thread in results:
            self.assertTrue(thread['is_pinned'])

        slugs = [thread['slug'] for thread in results]
        self.assertIn('community-guidelines', slugs)
        self.assertNotIn('how-to-water-succulents', slugs)

    def test_recent_action_returns_recent_threads(self):
        """GET /threads/recent/ returns recently active threads."""
        # Update last_activity_at for thread1 to be recent
        self.thread1.last_activity_at = timezone.now()
        self.thread1.save()

        # Update thread2 to be old (8 days ago)
        old_date = timezone.now() - timezone.timedelta(days=8)
        self.thread2.last_activity_at = old_date
        self.thread2.save()

        # Default 7 days
        response = self.client.get('/api/v1/forum/threads/recent/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        slugs = [thread['slug'] for thread in results]
        self.assertIn('how-to-water-succulents', slugs)
        self.assertNotIn('community-guidelines', slugs)

    def test_recent_action_with_custom_days(self):
        """GET /threads/recent/?days=10 accepts custom time window."""
        # Update thread2 to be 8 days old
        old_date = timezone.now() - timezone.timedelta(days=8)
        self.thread2.last_activity_at = old_date
        self.thread2.save()

        # 10 day window should include thread2
        response = self.client.get('/api/v1/forum/threads/recent/?days=10')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        slugs = [thread['slug'] for thread in results]
        self.assertIn('community-guidelines', slugs)

    def test_anonymous_can_read_threads(self):
        """Anonymous users can list and retrieve threads."""
        # Unauthenticated client
        response = self.client.get('/api/v1/forum/threads/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(f'/api/v1/forum/threads/{self.thread1.slug}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get('/api/v1/forum/threads/pinned/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get('/api/v1/forum/threads/recent/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_cannot_create_threads(self):
        """Anonymous users cannot create threads."""
        response = self.client.post(
            '/api/v1/forum/threads/',
            {
                'title': 'Test Thread',
                'category': str(self.category.id),
                'excerpt': 'Test excerpt',
                'first_post_content': 'Test content'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
