"""
Test forum ReactionViewSet.

Tests reaction toggle pattern, aggregation, and filtering.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from ..models import Thread, Post, Category, Reaction

User = get_user_model()


class ReactionViewSetTests(TestCase):
    """Test ReactionViewSet API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create users
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')

        # Create category, thread, and post
        self.category = Category.objects.create(
            name='Plant Care',
            slug='plant-care',
            is_active=True
        )

        self.thread = Thread.objects.create(
            title='Test Thread',
            slug='test-thread',
            author=self.user1,
            category=self.category,
            is_active=True
        )

        self.post = Post.objects.create(
            thread=self.thread,
            author=self.user1,
            content_raw='Test post content',
            is_first_post=True,
            is_active=True
        )

        # Create reactions
        self.reaction1 = Reaction.objects.create(
            post=self.post,
            user=self.user1,
            reaction_type='like',
            is_active=True
        )

        self.reaction2 = Reaction.objects.create(
            post=self.post,
            user=self.user2,
            reaction_type='helpful',
            is_active=True
        )

        self.inactive_reaction = Reaction.objects.create(
            post=self.post,
            user=self.user1,
            reaction_type='love',
            is_active=False
        )

    def test_list_reactions_requires_post_parameter(self):
        """GET /reactions/ without post parameter returns 400."""
        response = self.client.get('/api/v1/forum/reactions/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_list_reactions_by_post(self):
        """GET /reactions/?post=uuid returns reactions for post."""
        response = self.client.get(
            f'/api/v1/forum/reactions/?post={self.post.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

        results = response.data['results']
        self.assertEqual(len(results), 2)  # Only active reactions

        reaction_types = [r['reaction_type'] for r in results]
        self.assertIn('like', reaction_types)
        self.assertIn('helpful', reaction_types)

    def test_list_reactions_excludes_inactive_by_default(self):
        """GET /reactions/?post=uuid excludes inactive reactions."""
        response = self.client.get(
            f'/api/v1/forum/reactions/?post={self.post.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        reaction_ids = [r['id'] for r in response.data['results']]
        self.assertNotIn(str(self.inactive_reaction.id), reaction_ids)

    def test_list_reactions_includes_inactive_with_parameter(self):
        """GET /reactions/?post=uuid&is_active=false includes inactive."""
        response = self.client.get(
            f'/api/v1/forum/reactions/?post={self.post.id}&is_active=false'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        reaction_ids = [r['id'] for r in response.data['results']]
        self.assertIn(str(self.inactive_reaction.id), reaction_ids)

    def test_filter_by_reaction_type(self):
        """GET /reactions/?post=uuid&reaction_type=like filters by type."""
        response = self.client.get(
            f'/api/v1/forum/reactions/?post={self.post.id}&reaction_type=like'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        # All reactions should be 'like'
        for reaction in results:
            self.assertEqual(reaction['reaction_type'], 'like')

        self.assertEqual(len(results), 1)

    def test_filter_by_user(self):
        """GET /reactions/?post=uuid&user=uuid filters by user."""
        response = self.client.get(
            f'/api/v1/forum/reactions/?post={self.post.id}&user={self.user1.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        # All reactions should be from user1 (user.id is integer, not UUID)
        for reaction in results:
            self.assertEqual(reaction['user'], self.user1.id)

    def test_toggle_creates_new_reaction(self):
        """POST /reactions/toggle/ creates new reaction if doesn't exist."""
        self.client.force_authenticate(user=self.user2)

        response = self.client.post(
            '/api/v1/forum/reactions/toggle/',
            {
                'post': str(self.post.id),
                'reaction_type': 'like'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['created'])
        self.assertTrue(response.data['is_active'])
        self.assertEqual(response.data['reaction']['reaction_type'], 'like')
        self.assertEqual(response.data['reaction']['user'], self.user2.id)

        # Verify reaction created in database
        reaction = Reaction.objects.get(
            post=self.post,
            user=self.user2,
            reaction_type='like'
        )
        self.assertTrue(reaction.is_active)

    def test_toggle_deactivates_existing_reaction(self):
        """POST /reactions/toggle/ deactivates existing active reaction."""
        self.client.force_authenticate(user=self.user1)

        # User1 already has active 'like' reaction
        response = self.client.post(
            '/api/v1/forum/reactions/toggle/',
            {
                'post': str(self.post.id),
                'reaction_type': 'like'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['created'])
        self.assertFalse(response.data['is_active'])  # Now inactive

        # Verify reaction deactivated in database
        self.reaction1.refresh_from_db()
        self.assertFalse(self.reaction1.is_active)

    def test_toggle_reactivates_inactive_reaction(self):
        """POST /reactions/toggle/ reactivates inactive reaction."""
        self.client.force_authenticate(user=self.user1)

        # User1 has inactive 'love' reaction
        response = self.client.post(
            '/api/v1/forum/reactions/toggle/',
            {
                'post': str(self.post.id),
                'reaction_type': 'love'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['created'])  # Not newly created
        self.assertTrue(response.data['is_active'])  # Now active

        # Verify reaction reactivated in database
        self.inactive_reaction.refresh_from_db()
        self.assertTrue(self.inactive_reaction.is_active)

    def test_toggle_requires_authentication(self):
        """POST /reactions/toggle/ requires authentication."""
        # Unauthenticated request
        response = self.client.post(
            '/api/v1/forum/reactions/toggle/',
            {
                'post': str(self.post.id),
                'reaction_type': 'like'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_aggregate_returns_counts(self):
        """GET /reactions/aggregate/?post=uuid returns reaction counts."""
        # Add more reactions for variety
        Reaction.objects.create(
            post=self.post,
            user=self.user2,
            reaction_type='like',
            is_active=True
        )

        response = self.client.get(
            f'/api/v1/forum/reactions/aggregate/?post={self.post.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('counts', response.data)

        counts = response.data['counts']
        self.assertEqual(counts['like'], 2)  # user1 + user2
        self.assertEqual(counts['helpful'], 1)  # user2
        self.assertEqual(counts.get('love', 0), 0)  # inactive, shouldn't count

    def test_aggregate_returns_user_reactions(self):
        """GET /reactions/aggregate/?post=uuid returns user's active reactions."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(
            f'/api/v1/forum/reactions/aggregate/?post={self.post.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user_reactions', response.data)

        user_reactions = response.data['user_reactions']
        self.assertIn('like', user_reactions)  # Active
        self.assertNotIn('love', user_reactions)  # Inactive
        self.assertNotIn('helpful', user_reactions)  # Different user

    def test_aggregate_anonymous_user_gets_empty_reactions(self):
        """GET /reactions/aggregate/?post=uuid for anonymous returns empty user_reactions."""
        # Unauthenticated request
        response = self.client.get(
            f'/api/v1/forum/reactions/aggregate/?post={self.post.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user_reactions', response.data)
        self.assertEqual(response.data['user_reactions'], [])

    def test_aggregate_requires_post_parameter(self):
        """GET /reactions/aggregate/ without post parameter returns 400."""
        response = self.client.get('/api/v1/forum/reactions/aggregate/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_aggregate_invalid_post_returns_404(self):
        """GET /reactions/aggregate/?post=invalid-uuid returns 404."""
        import uuid

        fake_uuid = uuid.uuid4()

        response = self.client.get(
            f'/api/v1/forum/reactions/aggregate/?post={fake_uuid}'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_can_read_reactions(self):
        """Anonymous users can list and aggregate reactions."""
        # Unauthenticated client
        response = self.client.get(f'/api/v1/forum/reactions/?post={self.post.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            f'/api/v1/forum/reactions/aggregate/?post={self.post.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_cannot_toggle_reactions(self):
        """Anonymous users cannot toggle reactions."""
        response = self.client.post(
            '/api/v1/forum/reactions/toggle/',
            {
                'post': str(self.post.id),
                'reaction_type': 'like'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
