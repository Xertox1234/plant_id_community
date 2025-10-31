"""
Test forum UserProfileViewSet.

Tests read-only profile access, leaderboards, and filtering.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from ..models import UserProfile

User = get_user_model()


class UserProfileViewSetTests(TestCase):
    """Test UserProfileViewSet API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create users with different profiles
        self.new_user = User.objects.create_user(username='newuser', password='pass')
        self.new_profile = UserProfile.objects.create(
            user=self.new_user,
            trust_level='new',
            post_count=1,
            thread_count=0,
            helpful_count=0
        )

        self.basic_user = User.objects.create_user(username='basic', password='pass')
        self.basic_profile = UserProfile.objects.create(
            user=self.basic_user,
            trust_level='basic',
            post_count=10,
            thread_count=2,
            helpful_count=5
        )

        self.trusted_user = User.objects.create_user(username='trusted', password='pass')
        self.trusted_profile = UserProfile.objects.create(
            user=self.trusted_user,
            trust_level='trusted',
            post_count=50,
            thread_count=10,
            helpful_count=25
        )

        self.veteran_user = User.objects.create_user(username='veteran', password='pass')
        self.veteran_profile = UserProfile.objects.create(
            user=self.veteran_user,
            trust_level='veteran',
            post_count=200,
            thread_count=50,
            helpful_count=100
        )

        self.expert_user = User.objects.create_user(username='expert', password='pass')
        self.expert_profile = UserProfile.objects.create(
            user=self.expert_user,
            trust_level='expert',
            post_count=500,
            thread_count=100,
            helpful_count=250
        )

    def test_list_user_profiles(self):
        """GET /profiles/ returns all user profiles."""
        response = self.client.get('/api/v1/forum/profiles/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

        results = response.data['results']
        self.assertEqual(len(results), 5)

    def test_list_profiles_default_ordering(self):
        """GET /profiles/ orders by helpful_count, then post_count by default."""
        response = self.client.get('/api/v1/forum/profiles/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        # Expert should be first (highest helpful_count)
        self.assertEqual(results[0]['user_info']['username'], 'expert')

        # Veteran should be second
        self.assertEqual(results[1]['user_info']['username'], 'veteran')

    def test_retrieve_profile_by_user_id(self):
        """GET /profiles/{user_id}/ returns single profile."""
        response = self.client.get(
            f'/api/v1/forum/profiles/{self.trusted_user.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_info']['username'], 'trusted')
        self.assertEqual(response.data['trust_level'], 'trusted')
        self.assertEqual(response.data['post_count'], 50)
        self.assertEqual(response.data['helpful_count'], 25)

    def test_filter_by_trust_level(self):
        """GET /profiles/?trust_level=veteran filters by trust level."""
        response = self.client.get('/api/v1/forum/profiles/?trust_level=veteran')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        # Should only return veteran user
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['user_info']['username'], 'veteran')
        self.assertEqual(results[0]['trust_level'], 'veteran')

    def test_ordering_by_post_count(self):
        """GET /profiles/?ordering=-post_count orders by post count."""
        response = self.client.get('/api/v1/forum/profiles/?ordering=-post_count')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        # Expert should be first (500 posts)
        self.assertEqual(results[0]['user_info']['username'], 'expert')
        self.assertEqual(results[0]['post_count'], 500)

        # Veteran should be second (200 posts)
        self.assertEqual(results[1]['user_info']['username'], 'veteran')
        self.assertEqual(results[1]['post_count'], 200)

    def test_top_contributors_default_limit(self):
        """GET /profiles/top_contributors/ returns top 10 by post count."""
        response = self.client.get('/api/v1/forum/profiles/top_contributors/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

        # Should return all 5 profiles (less than default limit of 10)
        self.assertEqual(len(response.data), 5)

        # Verify ordering by post_count
        self.assertEqual(response.data[0]['user_info']['username'], 'expert')
        self.assertEqual(response.data[1]['user_info']['username'], 'veteran')

    def test_top_contributors_custom_limit(self):
        """GET /profiles/top_contributors/?limit=2 respects custom limit."""
        response = self.client.get('/api/v1/forum/profiles/top_contributors/?limit=2')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Top 2 should be expert and veteran
        usernames = [profile['user_info']['username'] for profile in response.data]
        self.assertEqual(usernames, ['expert', 'veteran'])

    def test_top_contributors_max_limit_cap(self):
        """GET /profiles/top_contributors/?limit=200 caps at 100."""
        response = self.client.get('/api/v1/forum/profiles/top_contributors/?limit=200')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return 5 profiles (all we have, capped at 100 max)
        self.assertEqual(len(response.data), 5)

    def test_most_helpful_default_limit(self):
        """GET /profiles/most_helpful/ returns top 10 by helpful count."""
        response = self.client.get('/api/v1/forum/profiles/most_helpful/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)

        # Verify ordering by helpful_count
        self.assertEqual(response.data[0]['user_info']['username'], 'expert')
        self.assertEqual(response.data[0]['helpful_count'], 250)

    def test_most_helpful_custom_limit(self):
        """GET /profiles/most_helpful/?limit=3 respects custom limit."""
        response = self.client.get('/api/v1/forum/profiles/most_helpful/?limit=3')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

        usernames = [profile['user_info']['username'] for profile in response.data]
        self.assertEqual(usernames, ['expert', 'veteran', 'trusted'])

    def test_veterans_action_filters_veteran_and_expert(self):
        """GET /profiles/veterans/ returns only veteran and expert users."""
        response = self.client.get('/api/v1/forum/profiles/veterans/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        # Should return 2 profiles (veteran + expert)
        self.assertEqual(len(results), 2)

        trust_levels = [profile['trust_level'] for profile in results]
        self.assertIn('veteran', trust_levels)
        self.assertIn('expert', trust_levels)

        # Verify ordering (expert has higher helpful_count)
        self.assertEqual(results[0]['user_info']['username'], 'expert')
        self.assertEqual(results[1]['user_info']['username'], 'veteran')

    def test_new_members_default_limit(self):
        """GET /profiles/new_members/ returns 10 newest members."""
        response = self.client.get('/api/v1/forum/profiles/new_members/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)  # All 5 profiles

        # Verify ordering by created_at (newest first)
        # The last created profile should be first
        self.assertEqual(response.data[0]['user_info']['username'], 'expert')

    def test_new_members_custom_limit(self):
        """GET /profiles/new_members/?limit=2 respects custom limit."""
        response = self.client.get('/api/v1/forum/profiles/new_members/?limit=2')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_anonymous_can_read_profiles(self):
        """Anonymous users can list and retrieve profiles (AllowAny)."""
        # Unauthenticated client
        response = self.client.get('/api/v1/forum/profiles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(f'/api/v1/forum/profiles/{self.expert_user.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get('/api/v1/forum/profiles/top_contributors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get('/api/v1/forum/profiles/most_helpful/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get('/api/v1/forum/profiles/veterans/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get('/api/v1/forum/profiles/new_members/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_read_only_no_create(self):
        """POST /profiles/ not allowed (ReadOnlyModelViewSet)."""
        self.client.force_authenticate(user=self.basic_user)

        response = self.client.post(
            '/api/v1/forum/profiles/',
            {
                'user': self.new_user.id,
                'trust_level': 'expert'
            }
        )

        # ReadOnlyModelViewSet should not allow POST
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_read_only_no_update(self):
        """PUT/PATCH /profiles/{id}/ not allowed (ReadOnlyModelViewSet)."""
        self.client.force_authenticate(user=self.basic_user)

        response = self.client.patch(
            f'/api/v1/forum/profiles/{self.basic_user.id}/',
            {'trust_level': 'expert'}
        )

        # ReadOnlyModelViewSet should not allow PATCH
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_read_only_no_delete(self):
        """DELETE /profiles/{id}/ not allowed (ReadOnlyModelViewSet)."""
        self.client.force_authenticate(user=self.basic_user)

        response = self.client.delete(f'/api/v1/forum/profiles/{self.basic_user.id}/')

        # ReadOnlyModelViewSet should not allow DELETE
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
