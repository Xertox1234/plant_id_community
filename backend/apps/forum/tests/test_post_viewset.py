"""
Test forum PostViewSet.

Tests CRUD operations, filtering, soft deletion, and edit tracking.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework import status

from ..models import Thread, Post, Category

User = get_user_model()


class PostViewSetTests(TestCase):
    """Test PostViewSet API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create users
        self.author = User.objects.create_user(username='author', password='pass')
        self.other_user = User.objects.create_user(username='other', password='pass')

        # Create moderator
        self.moderator_group = Group.objects.get_or_create(name="Moderators")[0]
        self.moderator = User.objects.create_user(username='moderator', password='pass')
        self.moderator.groups.add(self.moderator_group)

        # Create category and thread
        self.category = Category.objects.create(
            name='Plant Care',
            slug='plant-care',
            description='General plant care topics',
            is_active=True
        )

        self.thread = Thread.objects.create(
            title='How to water succulents',
            slug='how-to-water-succulents',
            author=self.author,
            category=self.category,
            excerpt='Tips for watering succulents',
            is_active=True
        )

        # Create posts
        self.first_post = Post.objects.create(
            thread=self.thread,
            author=self.author,
            content_raw='This is the first post with detailed watering tips.',
            is_first_post=True,
            is_active=True
        )

        self.reply_post = Post.objects.create(
            thread=self.thread,
            author=self.other_user,
            content_raw='Thanks for the tips! Very helpful.',
            is_first_post=False,
            is_active=True
        )

        self.inactive_post = Post.objects.create(
            thread=self.thread,
            author=self.author,
            content_raw='This post was deleted.',
            is_first_post=False,
            is_active=False
        )

    def test_list_posts_requires_thread_parameter(self):
        """GET /posts/ without thread parameter returns 400."""
        self.client.force_authenticate(user=self.author)

        response = self.client.get('/api/v1/forum/posts/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_list_posts_by_thread(self):
        """GET /posts/?thread=slug returns posts in chronological order."""
        response = self.client.get(
            f'/api/v1/forum/posts/?thread={self.thread.slug}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

        results = response.data['results']
        self.assertEqual(len(results), 2)  # Only active posts

        # Verify chronological order (oldest first)
        self.assertEqual(results[0]['id'], str(self.first_post.id))
        self.assertEqual(results[1]['id'], str(self.reply_post.id))

    def test_list_posts_excludes_inactive_by_default(self):
        """GET /posts/?thread=slug excludes inactive posts."""
        response = self.client.get(
            f'/api/v1/forum/posts/?thread={self.thread.slug}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        post_ids = [post['id'] for post in response.data['results']]
        self.assertNotIn(str(self.inactive_post.id), post_ids)

    def test_list_posts_includes_inactive_with_parameter(self):
        """GET /posts/?thread=slug&is_active=false includes inactive posts."""
        response = self.client.get(
            f'/api/v1/forum/posts/?thread={self.thread.slug}&is_active=false'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        post_ids = [post['id'] for post in response.data['results']]
        self.assertIn(str(self.inactive_post.id), post_ids)

    def test_filter_posts_by_author(self):
        """GET /posts/?thread=slug&author=username filters by author."""
        response = self.client.get(
            f'/api/v1/forum/posts/?thread={self.thread.slug}&author=author'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        # All posts should be by author
        for post in results:
            self.assertEqual(post['author']['username'], 'author')

        post_ids = [post['id'] for post in results]
        self.assertIn(str(self.first_post.id), post_ids)
        self.assertNotIn(str(self.reply_post.id), post_ids)

    def test_retrieve_post(self):
        """GET /posts/{id}/ returns single post detail."""
        response = self.client.get(f'/api/v1/forum/posts/{self.first_post.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.first_post.id))
        self.assertEqual(response.data['content_raw'], self.first_post.content_raw)
        self.assertTrue(response.data['is_first_post'])

    def test_create_post_requires_authentication(self):
        """POST /posts/ requires authentication."""
        # Unauthenticated request
        response = self.client.post(
            '/api/v1/forum/posts/',
            {
                'thread': str(self.thread.id),
                'content_raw': 'Test post content'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_post_as_authenticated_user(self):
        """POST /posts/ creates new post."""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            '/api/v1/forum/posts/',
            {
                'thread': str(self.thread.id),
                'content_raw': 'This is my new reply post.'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['content_raw'], 'This is my new reply post.')
        self.assertEqual(response.data['author']['username'], 'other')

        # Verify post created in database
        post = Post.objects.get(id=response.data['id'])
        self.assertEqual(post.author, self.other_user)
        self.assertEqual(post.thread, self.thread)

    def test_update_post_requires_author_or_moderator(self):
        """PATCH /posts/{id}/ requires author or moderator."""
        # Other user denied
        self.client.force_authenticate(user=self.other_user)
        response = self.client.patch(
            f'/api/v1/forum/posts/{self.first_post.id}/',
            {'content_raw': 'Updated content'}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Author allowed
        self.client.force_authenticate(user=self.author)
        response = self.client.patch(
            f'/api/v1/forum/posts/{self.first_post.id}/',
            {'content_raw': 'Updated by author'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['content_raw'], 'Updated by author')

    def test_update_post_sets_edited_fields(self):
        """PATCH /posts/{id}/ sets edited_at and edited_by."""
        self.client.force_authenticate(user=self.author)

        # Verify initial state
        self.assertIsNone(self.first_post.edited_at)
        self.assertIsNone(self.first_post.edited_by)

        response = self.client.patch(
            f'/api/v1/forum/posts/{self.first_post.id}/',
            {'content_raw': 'Edited content'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh from database
        self.first_post.refresh_from_db()
        self.assertIsNotNone(self.first_post.edited_at)
        self.assertEqual(self.first_post.edited_by, self.author)

    def test_moderator_can_update_any_post(self):
        """Moderators can update posts they didn't author."""
        self.client.force_authenticate(user=self.moderator)

        response = self.client.patch(
            f'/api/v1/forum/posts/{self.first_post.id}/',
            {'content_raw': 'Moderated content'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['content_raw'], 'Moderated content')

    def test_delete_post_soft_deletes(self):
        """DELETE /posts/{id}/ soft deletes (sets is_active=False)."""
        self.client.force_authenticate(user=self.author)

        response = self.client.delete(f'/api/v1/forum/posts/{self.reply_post.id}/')

        # Note: reply_post was created by other_user, but we're testing as author
        # This should fail permission check
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Now authenticate as the actual author
        self.client.force_authenticate(user=self.other_user)
        response = self.client.delete(f'/api/v1/forum/posts/{self.reply_post.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify post still exists but is inactive
        self.reply_post.refresh_from_db()
        self.assertFalse(self.reply_post.is_active)

    def test_moderator_can_delete_any_post(self):
        """Moderators can delete posts they didn't author."""
        self.client.force_authenticate(user=self.moderator)

        response = self.client.delete(f'/api/v1/forum/posts/{self.first_post.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify soft deletion
        self.first_post.refresh_from_db()
        self.assertFalse(self.first_post.is_active)

    def test_first_posts_action_returns_thread_starters(self):
        """GET /posts/first_posts/ returns all first posts."""
        # Create another thread with first post
        thread2 = Thread.objects.create(
            title='Another Thread',
            slug='another-thread',
            author=self.other_user,
            category=self.category,
            is_active=True
        )

        first_post2 = Post.objects.create(
            thread=thread2,
            author=self.other_user,
            content_raw='First post of second thread',
            is_first_post=True,
            is_active=True
        )

        response = self.client.get('/api/v1/forum/posts/first_posts/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        post_ids = [post['id'] for post in response.data['results']]
        self.assertIn(str(self.first_post.id), post_ids)
        self.assertIn(str(first_post2.id), post_ids)
        self.assertNotIn(str(self.reply_post.id), post_ids)

    def test_first_posts_filter_by_category(self):
        """GET /posts/first_posts/?category=slug filters by thread category."""
        # Create different category
        other_category = Category.objects.create(
            name='Other',
            slug='other',
            is_active=True
        )

        other_thread = Thread.objects.create(
            title='Other Thread',
            slug='other-thread',
            author=self.author,
            category=other_category,
            is_active=True
        )

        other_first_post = Post.objects.create(
            thread=other_thread,
            author=self.author,
            content_raw='First post in other category',
            is_first_post=True,
            is_active=True
        )

        response = self.client.get('/api/v1/forum/posts/first_posts/?category=plant-care')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        post_ids = [post['id'] for post in response.data['results']]
        self.assertIn(str(self.first_post.id), post_ids)
        self.assertNotIn(str(other_first_post.id), post_ids)

    def test_anonymous_can_read_posts(self):
        """Anonymous users can list and retrieve posts."""
        # Unauthenticated client
        response = self.client.get(f'/api/v1/forum/posts/?thread={self.thread.slug}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(f'/api/v1/forum/posts/{self.first_post.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get('/api/v1/forum/posts/first_posts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
