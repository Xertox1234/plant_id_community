"""
Test moderation dashboard API endpoints.

Tests Task 4.5: Moderation Dashboard Enhancements
- Dashboard overview endpoint
- User moderation history endpoint
- Stats endpoint validation
"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.forum.models import (
    UserProfile, Category, Thread, Post, FlaggedContent, ModerationAction
)
from apps.forum.constants import (
    MODERATION_STATUS_PENDING,
    MODERATION_STATUS_APPROVED,
    MODERATION_STATUS_REJECTED,
    MODERATION_STATUS_REMOVED,
    FLAG_REASON_SPAM,
    FLAG_REASON_OFFENSIVE,
    MODERATION_ACTION_APPROVE,
    MODERATION_ACTION_WARNING,
)
from .factories import UserFactory, CategoryFactory, ThreadFactory, PostFactory

User = get_user_model()


class ModerationDashboardTestCase(APITestCase):
    """Test case for moderation dashboard endpoints."""

    def setUp(self):
        """Set up test environment with users, content, and flags."""
        self.client = APIClient()

        # Create moderator (staff user)
        self.moderator = User.objects.create_user(
            username='moderator',
            password='pass',
            is_staff=True
        )
        self.moderator_profile = UserProfile.objects.create(
            user=self.moderator,
            trust_level='expert'
        )

        # Create regular user
        self.regular_user = User.objects.create_user(
            username='regularuser',
            password='pass'
        )
        self.regular_profile = UserProfile.objects.create(
            user=self.regular_user,
            trust_level='basic'
        )

        # Create category and content
        self.category = CategoryFactory.create(name='Test Category')
        self.thread = ThreadFactory.create(
            author=self.regular_user,
            category=self.category
        )
        self.post = PostFactory.create(
            thread=self.thread,
            author=self.regular_user,
            content_raw="Test post content"
        )

    def create_flag(self, post, flag_reason, status=MODERATION_STATUS_PENDING, reviewed_by=None):
        """Helper to create a flag."""
        flag = FlaggedContent.objects.create(
            post=post,
            content_type='post',
            reporter=self.moderator,
            flag_reason=flag_reason,
            explanation=f"Test {flag_reason} flag",
            status=status
        )

        if reviewed_by and status != MODERATION_STATUS_PENDING:
            flag.reviewed_by = reviewed_by
            flag.reviewed_at = timezone.now()
            flag.save(update_fields=['reviewed_by', 'reviewed_at'])

        return flag


class DashboardEndpointTestCase(ModerationDashboardTestCase):
    """Test dashboard overview endpoint."""

    def setUp(self):
        """Set up each test with clean cache (dashboard is cached)."""
        super().setUp()
        from django.core.cache import cache
        cache.clear()

    def test_dashboard_returns_all_expected_fields(self):
        """Dashboard returns overview, flag_breakdown, recent_flags, moderator_stats."""
        self.client.force_authenticate(user=self.moderator)

        # Create some test flags
        self.create_flag(self.post, FLAG_REASON_SPAM)

        response = self.client.get('/api/v1/forum/moderation-queue/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check all top-level keys exist
        self.assertIn('overview', response.data)
        self.assertIn('flag_breakdown', response.data)
        self.assertIn('recent_flags', response.data)
        self.assertIn('moderator_stats', response.data)

        # Check overview keys
        overview = response.data['overview']
        self.assertIn('pending_flags', overview)
        self.assertIn('flags_today', overview)
        self.assertIn('flags_this_week', overview)
        self.assertIn('approval_rate', overview)
        self.assertIn('average_resolution_time_hours', overview)

        # Check moderator_stats keys
        moderator_stats = response.data['moderator_stats']
        self.assertIn('total_moderators', moderator_stats)
        self.assertIn('active_moderators_today', moderator_stats)
        self.assertIn('avg_flags_resolved_per_moderator', moderator_stats)

    def test_overview_metrics_accuracy(self):
        """Overview metrics calculate correctly."""
        self.client.force_authenticate(user=self.moderator)

        # Create pending flag (today)
        self.create_flag(self.post, FLAG_REASON_SPAM, status=MODERATION_STATUS_PENDING)

        # Create approved flag (today)
        post2 = PostFactory.create(thread=self.thread, author=self.regular_user)
        self.create_flag(
            post2,
            FLAG_REASON_OFFENSIVE,
            status=MODERATION_STATUS_APPROVED,
            reviewed_by=self.moderator
        )

        # Create old flag (8 days ago)
        post3 = PostFactory.create(thread=self.thread, author=self.regular_user)
        old_flag = self.create_flag(post3, FLAG_REASON_SPAM, status=MODERATION_STATUS_APPROVED)
        old_flag.created_at = timezone.now() - timedelta(days=8)
        old_flag.save(update_fields=['created_at'])

        response = self.client.get('/api/v1/forum/moderation-queue/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        overview = response.data['overview']

        # Check counts
        self.assertEqual(overview['pending_flags'], 1)
        self.assertEqual(overview['flags_today'], 2)  # 2 created today
        self.assertEqual(overview['flags_this_week'], 2)  # Old flag is >7 days ago

        # Check approval rate (1 approved / 2 reviewed = 0.5)
        # Note: old_flag is also approved, so 2 approved / 3 total reviewed (old + post2 approved) = 0.67
        # Wait, let me recalculate: We have 3 flags total, 1 pending (not reviewed), 2 reviewed (post2 approved, old_flag approved)
        # So approval_rate = 2 approved / 2 reviewed = 1.0
        self.assertEqual(overview['approval_rate'], 1.0)

    def test_flag_breakdown_by_reason(self):
        """Flag breakdown groups pending flags by reason."""
        self.client.force_authenticate(user=self.moderator)

        # Create multiple flags with different reasons (all pending)
        self.create_flag(self.post, FLAG_REASON_SPAM)
        post2 = PostFactory.create(thread=self.thread, author=self.regular_user)
        self.create_flag(post2, FLAG_REASON_SPAM)
        post3 = PostFactory.create(thread=self.thread, author=self.regular_user)
        self.create_flag(post3, FLAG_REASON_OFFENSIVE)

        response = self.client.get('/api/v1/forum/moderation-queue/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        flag_breakdown = response.data['flag_breakdown']

        # Check breakdown counts (only pending flags)
        self.assertEqual(flag_breakdown.get(FLAG_REASON_SPAM, 0), 2)
        self.assertEqual(flag_breakdown.get(FLAG_REASON_OFFENSIVE, 0), 1)

    def test_recent_flags_preview_limit(self):
        """Recent flags preview shows max 5 items."""
        self.client.force_authenticate(user=self.moderator)

        # Create 7 pending flags (should only show 5 most recent)
        for i in range(7):
            post = PostFactory.create(thread=self.thread, author=self.regular_user)
            self.create_flag(post, FLAG_REASON_SPAM)

        response = self.client.get('/api/v1/forum/moderation-queue/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        recent_flags = response.data['recent_flags']
        self.assertEqual(len(recent_flags), 5)

        # Check each flag has required fields
        for flag_data in recent_flags:
            self.assertIn('id', flag_data)
            self.assertIn('flag_reason', flag_data)
            self.assertIn('content_type', flag_data)
            self.assertIn('content_preview', flag_data)
            self.assertIn('reporter', flag_data)
            self.assertIn('created_at', flag_data)

    def test_moderator_stats(self):
        """Moderator stats calculate correctly."""
        self.client.force_authenticate(user=self.moderator)

        # Create second moderator
        moderator2 = User.objects.create_user(
            username='moderator2',
            password='pass',
            is_staff=True
        )
        UserProfile.objects.create(user=moderator2, trust_level='expert')

        # Create and review a flag
        flag = self.create_flag(self.post, FLAG_REASON_SPAM)
        flag.status = MODERATION_STATUS_APPROVED
        flag.reviewed_by = self.moderator
        flag.reviewed_at = timezone.now()
        flag.save()

        response = self.client.get('/api/v1/forum/moderation-queue/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        moderator_stats = response.data['moderator_stats']

        # Check stats
        self.assertEqual(moderator_stats['total_moderators'], 2)  # 2 staff users
        self.assertEqual(moderator_stats['active_moderators_today'], 1)  # 1 reviewed today
        # avg_flags_resolved_per_moderator = 1 flag / 2 moderators = 0.5
        self.assertEqual(moderator_stats['avg_flags_resolved_per_moderator'], 0.5)

    def test_dashboard_with_no_flags(self):
        """Dashboard returns zeros when no flags exist."""
        self.client.force_authenticate(user=self.moderator)

        response = self.client.get('/api/v1/forum/moderation-queue/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        overview = response.data['overview']

        # All counts should be 0
        self.assertEqual(overview['pending_flags'], 0)
        self.assertEqual(overview['flags_today'], 0)
        self.assertEqual(overview['flags_this_week'], 0)
        self.assertEqual(overview['approval_rate'], 0.0)
        self.assertEqual(overview['average_resolution_time_hours'], 0.0)

        # Empty collections
        self.assertEqual(len(response.data['flag_breakdown']), 0)
        self.assertEqual(len(response.data['recent_flags']), 0)

    def test_dashboard_requires_moderator_permission(self):
        """Non-moderators cannot access dashboard."""
        # Try as regular user
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.get('/api/v1/forum/moderation-queue/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_requires_authentication(self):
        """Unauthenticated users cannot access dashboard."""
        response = self.client.get('/api/v1/forum/moderation-queue/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserModerationHistoryTestCase(ModerationDashboardTestCase):
    """Test user moderation history endpoint."""

    def test_user_history_with_flags(self):
        """User history returns all flags for user's content."""
        self.client.force_authenticate(user=self.moderator)

        # Create flags for regular_user's content
        flag1 = self.create_flag(self.post, FLAG_REASON_SPAM)
        post2 = PostFactory.create(thread=self.thread, author=self.regular_user)
        flag2 = self.create_flag(
            post2,
            FLAG_REASON_OFFENSIVE,
            status=MODERATION_STATUS_APPROVED,
            reviewed_by=self.moderator
        )

        response = self.client.get(
            f'/api/v1/forum/moderation-queue/user-history/{self.regular_user.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check user info
        self.assertEqual(response.data['user_id'], self.regular_user.id)
        self.assertEqual(response.data['username'], self.regular_user.username)

        # Check flags
        flags = response.data['flags_received']
        self.assertEqual(len(flags), 2)

        # Check flag data structure
        for flag_data in flags:
            self.assertIn('id', flag_data)
            self.assertIn('flag_reason', flag_data)
            self.assertIn('status', flag_data)
            self.assertIn('created_at', flag_data)
            self.assertIn('content_type', flag_data)
            self.assertIn('content_preview', flag_data)

    def test_user_history_with_actions(self):
        """User history returns all moderation actions targeting user."""
        self.client.force_authenticate(user=self.moderator)

        # Create flag and action
        flag = self.create_flag(
            self.post,
            FLAG_REASON_SPAM,
            status=MODERATION_STATUS_APPROVED,
            reviewed_by=self.moderator
        )

        action = ModerationAction.objects.create(
            flag=flag,
            moderator=self.moderator,
            action_type=MODERATION_ACTION_WARNING,
            reason="Test warning",
            affected_user=self.regular_user
        )

        response = self.client.get(
            f'/api/v1/forum/moderation-queue/user-history/{self.regular_user.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check actions
        actions = response.data['actions_taken']
        self.assertEqual(len(actions), 1)

        action_data = actions[0]
        self.assertEqual(action_data['action_type'], MODERATION_ACTION_WARNING)
        self.assertEqual(action_data['moderator'], self.moderator.username)
        self.assertIn('reason', action_data)

    def test_user_history_summary(self):
        """User history summary calculates correctly."""
        self.client.force_authenticate(user=self.moderator)

        # Create multiple flags with different statuses
        self.create_flag(self.post, FLAG_REASON_SPAM, status=MODERATION_STATUS_PENDING)
        post2 = PostFactory.create(thread=self.thread, author=self.regular_user)
        self.create_flag(
            post2,
            FLAG_REASON_OFFENSIVE,
            status=MODERATION_STATUS_APPROVED,
            reviewed_by=self.moderator
        )
        post3 = PostFactory.create(thread=self.thread, author=self.regular_user)
        flag3 = self.create_flag(
            post3,
            FLAG_REASON_SPAM,
            status=MODERATION_STATUS_REMOVED,
            reviewed_by=self.moderator
        )

        # Create warning action (reuse flag3)
        ModerationAction.objects.create(
            flag=flag3,
            moderator=self.moderator,
            action_type=MODERATION_ACTION_WARNING,
            reason="Test warning",
            affected_user=self.regular_user
        )

        response = self.client.get(
            f'/api/v1/forum/moderation-queue/user-history/{self.regular_user.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        summary = response.data['summary']

        # Check summary counts
        self.assertEqual(summary['total_flags'], 3)
        self.assertEqual(summary['pending_flags'], 1)
        self.assertEqual(summary['approved_flags'], 1)
        self.assertEqual(summary['removed_content_count'], 1)
        self.assertEqual(summary['warnings_count'], 1)

    def test_user_history_with_no_flags(self):
        """User with no flags returns empty history."""
        self.client.force_authenticate(user=self.moderator)

        # Create user with no flags
        clean_user = User.objects.create_user(username='cleanuser', password='pass')
        UserProfile.objects.create(user=clean_user, trust_level='basic')

        response = self.client.get(
            f'/api/v1/forum/moderation-queue/user-history/{clean_user.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check empty collections
        self.assertEqual(len(response.data['flags_received']), 0)
        self.assertEqual(len(response.data['actions_taken']), 0)

        # Check summary is all zeros
        summary = response.data['summary']
        self.assertEqual(summary['total_flags'], 0)
        self.assertEqual(summary['pending_flags'], 0)

    def test_user_history_invalid_user_id(self):
        """Invalid user ID returns 404."""
        self.client.force_authenticate(user=self.moderator)

        response = self.client.get(
            '/api/v1/forum/moderation-queue/user-history/99999/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_history_requires_moderator_permission(self):
        """Non-moderators cannot access user history."""
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.get(
            f'/api/v1/forum/moderation-queue/user-history/{self.regular_user.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class StatsEndpointTestCase(ModerationDashboardTestCase):
    """Test stats endpoint validation."""

    def test_stats_endpoint_returns_expected_fields(self):
        """Stats endpoint returns all expected fields."""
        self.client.force_authenticate(user=self.moderator)

        response = self.client.get('/api/v1/forum/moderation-queue/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check all expected fields
        self.assertIn('pending_count', response.data)
        self.assertIn('pending_posts', response.data)
        self.assertIn('pending_threads', response.data)
        self.assertIn('reviewed_today', response.data)
        self.assertIn('total_flags', response.data)
        self.assertIn('flags_by_reason', response.data)

    def test_stats_pending_counts(self):
        """Stats endpoint calculates pending counts correctly."""
        self.client.force_authenticate(user=self.moderator)

        # Create pending flags for post and thread
        self.create_flag(self.post, FLAG_REASON_SPAM)

        thread2 = ThreadFactory.create(author=self.regular_user, category=self.category)
        thread_flag = FlaggedContent.objects.create(
            thread=thread2,
            content_type='thread',
            reporter=self.moderator,
            flag_reason=FLAG_REASON_OFFENSIVE,
            explanation="Test thread flag",
            status=MODERATION_STATUS_PENDING
        )

        response = self.client.get('/api/v1/forum/moderation-queue/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data['pending_count'], 2)
        self.assertEqual(response.data['pending_posts'], 1)
        self.assertEqual(response.data['pending_threads'], 1)

    def test_stats_flags_by_reason(self):
        """Stats endpoint groups pending flags by reason."""
        self.client.force_authenticate(user=self.moderator)

        # Create flags with different reasons
        self.create_flag(self.post, FLAG_REASON_SPAM)
        post2 = PostFactory.create(thread=self.thread, author=self.regular_user)
        self.create_flag(post2, FLAG_REASON_SPAM)
        post3 = PostFactory.create(thread=self.thread, author=self.regular_user)
        self.create_flag(post3, FLAG_REASON_OFFENSIVE)

        response = self.client.get('/api/v1/forum/moderation-queue/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        flags_by_reason = response.data['flags_by_reason']
        self.assertEqual(flags_by_reason.get(FLAG_REASON_SPAM, 0), 2)
        self.assertEqual(flags_by_reason.get(FLAG_REASON_OFFENSIVE, 0), 1)

    def test_stats_reviewed_today_count(self):
        """Stats endpoint counts flags reviewed today."""
        self.client.force_authenticate(user=self.moderator)

        # Create and review flags
        flag1 = self.create_flag(self.post, FLAG_REASON_SPAM)
        flag1.status = MODERATION_STATUS_APPROVED
        flag1.reviewed_by = self.moderator
        flag1.reviewed_at = timezone.now()
        flag1.save()

        post2 = PostFactory.create(thread=self.thread, author=self.regular_user)
        flag2 = self.create_flag(post2, FLAG_REASON_OFFENSIVE)
        flag2.status = MODERATION_STATUS_REJECTED
        flag2.reviewed_by = self.moderator
        flag2.reviewed_at = timezone.now()
        flag2.save()

        response = self.client.get('/api/v1/forum/moderation-queue/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data['reviewed_today'], 2)

    def test_stats_total_flags_count(self):
        """Stats endpoint counts all flags."""
        self.client.force_authenticate(user=self.moderator)

        # Create flags with different statuses
        self.create_flag(self.post, FLAG_REASON_SPAM, status=MODERATION_STATUS_PENDING)
        post2 = PostFactory.create(thread=self.thread, author=self.regular_user)
        self.create_flag(
            post2,
            FLAG_REASON_OFFENSIVE,
            status=MODERATION_STATUS_APPROVED,
            reviewed_by=self.moderator
        )

        response = self.client.get('/api/v1/forum/moderation-queue/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data['total_flags'], 2)
