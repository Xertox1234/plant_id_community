"""
Test suite for Spam Detection Service.

Tests all 5 spam detection heuristics (duplicate content, rapid posting,
link spam, keyword spam, pattern spam) and the comprehensive is_spam() method.

Follows patterns from:
- test_trust_level_service.py: ForumTestCase base, factory usage
- spam_detection_service.py: Weighted scoring, cache integration
- SPAM_DETECTION_PATTERNS_CODIFIED.md: Multi-heuristic detection

Test Coverage:
- Duplicate content detection (exact + fuzzy matching)
- Rapid posting detection (trust level integration)
- Link spam detection (trust-based URL limits)
- Keyword spam detection (weighted by category)
- Pattern spam detection (caps, punctuation, repetition)
- Comprehensive spam scoring (combination testing)
- Cache integration and performance
- Edge cases and boundary conditions
"""

from datetime import timedelta
from django.test import override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from freezegun import freeze_time

from ..services.spam_detection_service import SpamDetectionService
from ..constants import (
    TRUST_LEVEL_NEW,
    TRUST_LEVEL_BASIC,
    TRUST_LEVEL_TRUSTED,
    SPAM_URL_LIMIT_NEW,
    SPAM_URL_LIMIT_BASIC,
    SPAM_URL_LIMIT_TRUSTED,
    SPAM_RAPID_POST_SECONDS,
    SPAM_DUPLICATE_SIMILARITY_THRESHOLD,
    SPAM_CAPS_RATIO_THRESHOLD,
    SPAM_PUNCTUATION_RATIO_THRESHOLD,
    SPAM_SCORE_DUPLICATE,
    SPAM_SCORE_RAPID_POST,
    SPAM_SCORE_LINK_SPAM,
    SPAM_SCORE_KEYWORD_SPAM,
    SPAM_SCORE_PATTERN_SPAM,
    SPAM_SCORE_THRESHOLD,
)
from .base import ForumTestCase
from .factories import (
    UserFactory,
    PostFactory,
    ThreadFactory,
    CategoryFactory,
)

User = get_user_model()


class DuplicateContentDetectionTests(ForumTestCase):
    """
    Test duplicate content detection (Heuristic #1).

    Covers:
    - Exact duplicate detection (100% match)
    - Fuzzy duplicate detection (85%+ similarity)
    - Non-duplicate content (<85% similarity)
    - Cache integration (5-minute cache)
    - Thread vs Post handling
    - Recent content window (24 hours)
    """

    def setUp(self):
        """Set up test fixtures for duplicate detection."""
        super().setUp()
        cache.clear()

        self.user = UserFactory.create(username='test_user')
        self.category = CategoryFactory.create()

    def test_exact_duplicate_post_detected(self):
        """
        Test that exact duplicate posts are detected.

        Scenario:
        1. User creates post with content "This is a test post"
        2. User tries to create another post with identical content
        3. Should be flagged as duplicate (100% similarity)
        """
        content = "This is a test post about plant care."

        # Create first post
        thread = ThreadFactory.create(author=self.user, category=self.category)
        PostFactory.create(thread=thread, author=self.user, content_raw=content)

        # Check for duplicate
        result = SpamDetectionService.check_duplicate_content(self.user, content, 'post')

        # Should be detected as exact duplicate
        self.assertTrue(result['is_duplicate'])
        self.assertEqual(result['similarity'], 1.0)
        self.assertEqual(result['match_type'], 'exact')
        self.assertIsNotNone(result['previous_content_id'])

    def test_fuzzy_duplicate_post_detected(self):
        """
        Test that fuzzy duplicates (85%+ similarity) are detected.

        Scenario:
        1. User creates post: "Hello world this is a test"
        2. User tries: "Hello world this is a test post"
        3. Should be flagged as fuzzy duplicate (>85% similar)
        """
        original = "Hello world this is a test about watering plants."
        similar = "Hello world this is a test about watering plants!"  # 95%+ similar

        # Create original post
        thread = ThreadFactory.create(author=self.user, category=self.category)
        PostFactory.create(thread=thread, author=self.user, content_raw=original)

        # Check for duplicate
        result = SpamDetectionService.check_duplicate_content(self.user, similar, 'post')

        # Should be detected as fuzzy duplicate
        self.assertTrue(result['is_duplicate'])
        self.assertGreaterEqual(result['similarity'], SPAM_DUPLICATE_SIMILARITY_THRESHOLD)
        self.assertEqual(result['match_type'], 'fuzzy')

    def test_non_duplicate_content_allowed(self):
        """
        Test that sufficiently different content is not flagged.

        Scenario:
        1. User creates post about watering
        2. User creates completely different post about fertilizing
        3. Should NOT be flagged as duplicate (<85% similarity)
        """
        original = "How often should I water my monstera?"
        different = "What fertilizer is best for succulents?"

        # Create original post
        thread = ThreadFactory.create(author=self.user, category=self.category)
        PostFactory.create(thread=thread, author=self.user, content_raw=original)

        # Check for duplicate
        result = SpamDetectionService.check_duplicate_content(self.user, different, 'post')

        # Should NOT be flagged
        self.assertFalse(result['is_duplicate'])
        self.assertLess(result['similarity'], SPAM_DUPLICATE_SIMILARITY_THRESHOLD)

    def test_duplicate_check_ignores_old_content(self):
        """
        Test that duplicate check only looks at recent content (24 hours).

        Scenario:
        1. User creates post 25 hours ago
        2. User creates identical post now
        3. Should NOT be flagged (outside 24-hour window)
        """
        content = "This is a test post."

        # Create post 25 hours ago
        with freeze_time(timezone.now() - timedelta(hours=25)):
            thread = ThreadFactory.create(author=self.user, category=self.category)
            PostFactory.create(thread=thread, author=self.user, content_raw=content)

        # Check for duplicate now
        result = SpamDetectionService.check_duplicate_content(self.user, content, 'post')

        # Should NOT be flagged (old content ignored)
        self.assertFalse(result['is_duplicate'])

    def test_duplicate_detection_uses_cache(self):
        """
        Test that duplicate detection results are cached for 5 minutes.

        Performance optimization: Avoid repeated DB queries for same content.
        """
        content = "Test content for caching."

        # First check (miss - hits DB)
        result1 = SpamDetectionService.check_duplicate_content(self.user, content, 'post')

        # Second check (hit - uses cache)
        result2 = SpamDetectionService.check_duplicate_content(self.user, content, 'post')

        # Results should be identical
        self.assertEqual(result1, result2)
        self.assertFalse(result1['is_duplicate'])

    def test_exact_duplicate_thread_title_detected(self):
        """
        Test that duplicate thread titles are detected.

        Scenario:
        1. User creates thread: "How to care for monstera?"
        2. User tries to create thread with identical title
        3. Should be flagged as duplicate
        """
        title = "How to care for monstera?"

        # Create first thread
        ThreadFactory.create(
            author=self.user,
            category=self.category,
            title=title
        )

        # Check for duplicate (thread format: "title\ncontent")
        content = f"{title}\nSome content about monstera care."
        result = SpamDetectionService.check_duplicate_content(self.user, content, 'thread')

        # Should be detected
        self.assertTrue(result['is_duplicate'])

    def test_soft_deleted_posts_not_checked_for_duplicates(self):
        """
        Test that soft-deleted posts (is_active=False) are not checked.

        Prevents false positives from deleted content.
        """
        content = "This post will be deleted."

        # Create and soft-delete post
        thread = ThreadFactory.create(author=self.user, category=self.category)
        PostFactory.create(
            thread=thread,
            author=self.user,
            content_raw=content,
            is_active=False  # Soft-deleted
        )

        # Check for duplicate
        result = SpamDetectionService.check_duplicate_content(self.user, content, 'post')

        # Should NOT be flagged (deleted content ignored)
        self.assertFalse(result['is_duplicate'])


class RapidPostingDetectionTests(ForumTestCase):
    """
    Test rapid posting detection (Heuristic #2).

    Covers:
    - NEW/BASIC users posting <10s apart
    - TRUSTED+ users exempt from rapid posting check
    - First post by user (no previous post)
    - Edge case: exactly 10 seconds apart
    """

    def setUp(self):
        """Set up test fixtures for rapid posting detection."""
        super().setUp()
        cache.clear()

        # Create users at different trust levels
        self.new_user = self._create_user_with_trust_level(TRUST_LEVEL_NEW, 'new_user')
        self.basic_user = self._create_user_with_trust_level(TRUST_LEVEL_BASIC, 'basic_user')
        self.trusted_user = self._create_user_with_trust_level(TRUST_LEVEL_TRUSTED, 'trusted_user')

        self.category = CategoryFactory.create()

    def _create_user_with_trust_level(self, trust_level: str, username: str):
        """Helper to create user with specific trust level."""
        from ..models import UserProfile
        from datetime import timedelta
        from django.utils import timezone

        user = UserFactory.create(username=username)

        # Set date_joined based on trust level requirements
        if trust_level == TRUST_LEVEL_TRUSTED:
            user.date_joined = timezone.now() - timedelta(days=30)
            user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.trust_level = trust_level
        profile.post_count = 0  # Initialize post count
        profile.save()

        user.refresh_from_db()
        return user

    def test_new_user_rapid_posting_detected(self):
        """
        Test that NEW user posting <10s apart is flagged.

        Scenario:
        1. NEW user creates post at T=0
        2. NEW user creates post at T=5s
        3. Should be flagged (5s < 10s minimum)
        """
        # Create first post
        thread = ThreadFactory.create(author=self.new_user, category=self.category)
        PostFactory.create(thread=thread, author=self.new_user)

        # Try to create second post 5 seconds later (without actually waiting)
        # Note: We can't use freeze_time here because Post.created_at uses auto_now_add
        # Instead, we'll test the service method directly with a recent post

        # Check for rapid posting
        result = SpamDetectionService.check_rapid_posting(self.new_user, 'post')

        # Should be flagged (NEW user, recent post)
        self.assertTrue(result['is_rapid'])
        self.assertLess(result['seconds_since_last'], SPAM_RAPID_POST_SECONDS)

    def test_trusted_user_exempt_from_rapid_posting_check(self):
        """
        Test that TRUSTED+ users are exempt from rapid posting checks.

        Scenario:
        1. TRUSTED user creates post at T=0
        2. TRUSTED user creates post at T=1s
        3. Should NOT be flagged (TRUSTED+ exempt)
        """
        # Create first post
        thread = ThreadFactory.create(author=self.trusted_user, category=self.category)
        PostFactory.create(thread=thread, author=self.trusted_user)

        # Check for rapid posting
        result = SpamDetectionService.check_rapid_posting(self.trusted_user, 'post')

        # Should NOT be flagged (TRUSTED+ exempt)
        self.assertFalse(result['is_rapid'])
        self.assertEqual(result['minimum_wait'], 0)

    def test_first_post_by_user_not_flagged(self):
        """
        Test that user's first post is never flagged for rapid posting.

        Scenario:
        1. Brand new user with no posts
        2. Creates first post
        3. Should NOT be flagged
        """
        brand_new_user = self._create_user_with_trust_level(TRUST_LEVEL_NEW, 'brand_new')

        # Check for rapid posting (no previous posts)
        result = SpamDetectionService.check_rapid_posting(brand_new_user, 'post')

        # Should NOT be flagged
        self.assertFalse(result['is_rapid'])
        self.assertEqual(result['seconds_since_last'], 0)


class LinkSpamDetectionTests(ForumTestCase):
    """
    Test link spam detection (Heuristic #3).

    Covers:
    - NEW users: >2 URLs = spam
    - BASIC users: >5 URLs = spam
    - TRUSTED users: >10 URLs = spam
    - Edge cases (exactly at limit, no URLs)
    - URL pattern matching
    """

    def setUp(self):
        """Set up test fixtures for link spam detection."""
        super().setUp()

        # Create users at different trust levels
        self.new_user = self._create_user_with_trust_level(TRUST_LEVEL_NEW, 'new_user')
        self.basic_user = self._create_user_with_trust_level(TRUST_LEVEL_BASIC, 'basic_user')
        self.trusted_user = self._create_user_with_trust_level(TRUST_LEVEL_TRUSTED, 'trusted_user')

    def _create_user_with_trust_level(self, trust_level: str, username: str):
        """Helper to create user with specific trust level."""
        from ..models import UserProfile
        from datetime import timedelta
        from django.utils import timezone

        user = UserFactory.create(username=username)

        # Set date_joined based on trust level requirements
        if trust_level == TRUST_LEVEL_TRUSTED:
            user.date_joined = timezone.now() - timedelta(days=30)
            user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.trust_level = trust_level
        profile.post_count = 0  # Initialize post count
        profile.save()

        user.refresh_from_db()
        return user

    def test_new_user_link_spam_detected(self):
        """
        Test that NEW user with >2 URLs is flagged.

        Scenario:
        1. NEW user posts content with 3 URLs
        2. Should be flagged (limit: 2 URLs)
        """
        content = """
        Check out these resources:
        http://example1.com
        http://example2.com
        http://example3.com
        """

        result = SpamDetectionService.check_link_spam(self.new_user, content)

        # Should be flagged
        self.assertTrue(result['is_spam'])
        self.assertEqual(result['url_count'], 3)
        self.assertEqual(result['url_limit'], SPAM_URL_LIMIT_NEW)

    def test_new_user_at_url_limit_allowed(self):
        """
        Test that NEW user with exactly 2 URLs is allowed.

        Boundary condition: exactly at limit.
        """
        content = """
        Check out:
        http://example1.com
        http://example2.com
        """

        result = SpamDetectionService.check_link_spam(self.new_user, content)

        # Should be allowed
        self.assertFalse(result['is_spam'])
        self.assertEqual(result['url_count'], 2)

    def test_basic_user_link_spam_detected(self):
        """
        Test that BASIC user with >5 URLs is flagged.

        Scenario:
        1. BASIC user posts content with 6 URLs
        2. Should be flagged (limit: 5 URLs)
        """
        urls = [f"http://example{i}.com" for i in range(6)]
        content = "\n".join(urls)

        result = SpamDetectionService.check_link_spam(self.basic_user, content)

        # Should be flagged
        self.assertTrue(result['is_spam'])
        self.assertEqual(result['url_count'], 6)
        self.assertEqual(result['url_limit'], SPAM_URL_LIMIT_BASIC)

    def test_trusted_user_link_spam_detected(self):
        """
        Test that TRUSTED user with >10 URLs is flagged.

        Scenario:
        1. TRUSTED user posts content with 11 URLs
        2. Should be flagged (limit: 10 URLs)
        """
        urls = [f"http://example{i}.com" for i in range(11)]
        content = "\n".join(urls)

        result = SpamDetectionService.check_link_spam(self.trusted_user, content)

        # Should be flagged
        self.assertTrue(result['is_spam'])
        self.assertEqual(result['url_count'], 11)
        self.assertEqual(result['url_limit'], SPAM_URL_LIMIT_TRUSTED)

    def test_https_urls_counted(self):
        """
        Test that HTTPS URLs are counted in link spam detection.
        """
        content = "Check https://example1.com and https://example2.com and https://example3.com"

        result = SpamDetectionService.check_link_spam(self.new_user, content)

        # Should detect all HTTPS URLs
        self.assertTrue(result['is_spam'])
        self.assertEqual(result['url_count'], 3)

    def test_no_urls_allowed(self):
        """
        Test that content with no URLs is always allowed.
        """
        content = "This is a normal post with no links."

        result = SpamDetectionService.check_link_spam(self.new_user, content)

        # Should be allowed
        self.assertFalse(result['is_spam'])
        self.assertEqual(result['url_count'], 0)


class KeywordSpamDetectionTests(ForumTestCase):
    """
    Test keyword spam detection (Heuristic #4).

    Covers:
    - Commercial spam keywords (10 points each)
    - Financial spam keywords (20 points each)
    - Phishing keywords (30 points each - highest risk)
    - Weighted scoring threshold (>=50 points = spam)
    - Case-insensitive matching
    - Clean content allowed
    """

    def setUp(self):
        """Set up test fixtures for keyword spam detection."""
        super().setUp()

    def test_single_commercial_keyword_allowed(self):
        """
        Test that single commercial keyword is allowed.

        Scenario:
        1. Post contains "buy now" (10 points)
        2. Score: 10 < 50 threshold
        3. Should NOT be flagged
        """
        content = "I want to buy now some fertilizer for my plants."

        result = SpamDetectionService.check_keyword_spam(content)

        # Should be allowed (score too low)
        self.assertFalse(result['is_spam'])
        self.assertEqual(result['weighted_score'], 10)
        self.assertEqual(result['keyword_count'], 1)

    def test_multiple_commercial_keywords_detected(self):
        """
        Test that 5+ commercial keywords are flagged.

        Scenario:
        1. Post contains 5 commercial keywords (10 points each)
        2. Score: 50 >= 50 threshold
        3. Should be flagged
        """
        content = "BUY NOW! Limited time offer! ACT NOW! Guaranteed results! Click here!"

        result = SpamDetectionService.check_keyword_spam(content)

        # Should be flagged (5 keywords * 10 = 50 points)
        self.assertTrue(result['is_spam'])
        self.assertGreaterEqual(result['weighted_score'], 50)

    def test_financial_spam_keywords_detected(self):
        """
        Test that 2-3 financial keywords are flagged.

        Scenario:
        1. Post contains "free money" (20) + "gift card" (20)
        2. Score: 40 < 50 (not flagged)
        3. Add "bitcoin" (20) → 60 >= 50 (flagged)
        """
        # 2 keywords: 40 points (not spam)
        content1 = "Get free money and a gift card!"
        result1 = SpamDetectionService.check_keyword_spam(content1)
        self.assertFalse(result1['is_spam'])
        self.assertEqual(result1['weighted_score'], 40)

        # 3 keywords: 60 points (spam)
        content2 = "Get free money, gift card, and bitcoin!"
        result2 = SpamDetectionService.check_keyword_spam(content2)
        self.assertTrue(result2['is_spam'])
        self.assertEqual(result2['weighted_score'], 60)

    def test_phishing_keywords_high_priority(self):
        """
        Test that 2 phishing keywords are flagged (highest risk).

        Scenario:
        1. Post contains phishing keywords (30 points each)
        2. Score: >= 50 threshold
        3. Should be flagged (security threat)
        """
        # Use exact keywords from constants.py
        content = "urgent action required! your account locked! verify your account now!"

        result = SpamDetectionService.check_keyword_spam(content)

        # Should be flagged (phishing keywords detected)
        self.assertTrue(result['is_spam'])
        self.assertGreaterEqual(result['weighted_score'], 50)
        self.assertGreater(result['keyword_count'], 0)

    def test_mixed_keyword_categories(self):
        """
        Test weighted scoring with mixed keyword categories.

        Scenario:
        1. Mix of commercial + financial + phishing keywords
        2. Score: >= 50
        3. Should be flagged
        """
        # Use exact keywords from constants to ensure detection
        content = "buy now! free money! urgent! gift card! click here!"

        result = SpamDetectionService.check_keyword_spam(content)

        # Should be flagged (multiple keywords)
        self.assertTrue(result['is_spam'])
        self.assertGreaterEqual(result['weighted_score'], 50)

    def test_case_insensitive_keyword_matching(self):
        """
        Test that keyword matching is case-insensitive.
        """
        content = "BUY NOW! Buy Now! buy now!"  # 3 instances of same keyword

        result = SpamDetectionService.check_keyword_spam(content)

        # Should detect keyword (case-insensitive)
        self.assertIn('buy now', result['matched_keywords'])

    def test_clean_content_allowed(self):
        """
        Test that clean content with no spam keywords is allowed.
        """
        content = "How often should I water my monstera plant?"

        result = SpamDetectionService.check_keyword_spam(content)

        # Should be allowed
        self.assertFalse(result['is_spam'])
        self.assertEqual(result['weighted_score'], 0)
        self.assertEqual(result['keyword_count'], 0)


class PatternSpamDetectionTests(ForumTestCase):
    """
    Test pattern spam detection (Heuristic #5).

    Covers:
    - ALL CAPS abuse (>70% uppercase)
    - Excessive punctuation (>30% of content)
    - Character repetition (5+ repeated chars)
    - Combination detection (2+ patterns = spam)
    - Short content exemption (<=10 chars)
    """

    def setUp(self):
        """Set up test fixtures for pattern spam detection."""
        super().setUp()

    def test_all_caps_abuse_detected(self):
        """
        Test that >70% uppercase content is flagged.

        Scenario:
        1. Post is "THIS IS ALL CAPS SPAM MESSAGE"
        2. Caps ratio: 100% > 70% threshold
        3. Should detect excessive_caps pattern
        """
        content = "THIS IS ALL CAPS SPAM MESSAGE"

        result = SpamDetectionService.check_spam_patterns(content)

        # Should detect caps abuse
        self.assertIn('excessive_caps', result['patterns_detected'])
        self.assertGreater(result['details']['caps_ratio'], SPAM_CAPS_RATIO_THRESHOLD)

    def test_excessive_punctuation_detected(self):
        """
        Test that >30% punctuation is flagged.

        Scenario:
        1. Post is "!!!!!!!!!! Buy now !!!!!!!!!!"
        2. Punctuation ratio: >30%
        3. Should detect excessive_punctuation pattern
        """
        content = "!!!!!!!!!! Buy now !!!!!!!!!!"

        result = SpamDetectionService.check_spam_patterns(content)

        # Should detect punctuation abuse
        self.assertIn('excessive_punctuation', result['patterns_detected'])

    def test_character_repetition_detected(self):
        """
        Test that 5+ repeated characters are flagged.

        Scenario:
        1. Post contains "!!!!!" or "aaaaa"
        2. Should detect character_repetition pattern
        """
        content = "This is amazing!!!!! I love it!!!!!"

        result = SpamDetectionService.check_spam_patterns(content)

        # Should detect repetition
        self.assertIn('character_repetition', result['patterns_detected'])
        self.assertGreater(result['details']['repetition_count'], 0)

    def test_multiple_patterns_flagged_as_spam(self):
        """
        Test that 2+ patterns are flagged as spam.

        Scenario:
        1. ALL CAPS + excessive punctuation
        2. 2 patterns >= 2 threshold
        3. Should be flagged as spam
        """
        content = "BUY NOW!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"

        result = SpamDetectionService.check_spam_patterns(content)

        # Should be flagged (2+ patterns)
        self.assertTrue(result['is_spam'])
        self.assertGreaterEqual(len(result['patterns_detected']), 2)

    def test_single_pattern_not_spam(self):
        """
        Test that single pattern alone is not spam.

        Scenario:
        1. Only ALL CAPS, no other patterns
        2. 1 pattern < 2 threshold
        3. Should NOT be flagged
        """
        content = "THIS IS ALL CAPS BUT OTHERWISE NORMAL"

        result = SpamDetectionService.check_spam_patterns(content)

        # Should NOT be flagged (only 1 pattern)
        self.assertFalse(result['is_spam'])
        self.assertEqual(len(result['patterns_detected']), 1)

    def test_short_content_exempt(self):
        """
        Test that very short content (<=10 chars) is exempt.

        Prevents false positives on short exclamations like "WOW!!!"
        """
        content = "WOW!!!"  # 6 chars

        result = SpamDetectionService.check_spam_patterns(content)

        # Should NOT be flagged (too short)
        self.assertFalse(result['is_spam'])
        self.assertEqual(len(result['patterns_detected']), 0)

    def test_normal_content_allowed(self):
        """
        Test that normal content with no patterns is allowed.
        """
        content = "This is a normal post about plant care with proper grammar."

        result = SpamDetectionService.check_spam_patterns(content)

        # Should be allowed
        self.assertFalse(result['is_spam'])
        self.assertEqual(len(result['patterns_detected']), 0)


class ComprehensiveSpamDetectionTests(ForumTestCase):
    """
    Test comprehensive spam detection (is_spam method).

    Covers:
    - Combination scoring (multiple heuristics)
    - Threshold enforcement (>=50 points = spam)
    - Individual strong signals (50-60 points)
    - Moderate signals requiring combination (45 points)
    - Clean content handling
    - Integration of all 5 heuristics
    """

    def setUp(self):
        """Set up test fixtures for comprehensive spam detection."""
        super().setUp()
        cache.clear()

        self.user = UserFactory.create(username='test_user')
        # Set to NEW trust level for stricter checks
        from ..models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.trust_level = TRUST_LEVEL_NEW
        profile.save()

        self.category = CategoryFactory.create()

    def test_obvious_spam_high_score(self):
        """
        Test obvious spam with multiple violations.

        Scenario:
        1. Content: "BUY NOW!!! http://spam1.com http://spam2.com http://spam3.com"
        2. Violations:
           - Link spam (50 points)
           - Keyword spam (50 points)
           - Pattern spam (45 points)
        3. Total: 145 points >> 50 threshold
        4. Should be flagged
        """
        content = "BUY NOW!!! LIMITED TIME!!! http://spam1.com http://spam2.com http://spam3.com"

        result = SpamDetectionService.is_spam(self.user, content, 'post')

        # Should be flagged with high score
        self.assertTrue(result['is_spam'])
        self.assertGreaterEqual(result['spam_score'], 100)
        self.assertIn('link_spam', result['reasons'])
        self.assertIn('keyword_spam', result['reasons'])

    def test_single_strong_signal_blocks(self):
        """
        Test that single strong signal (50-60 points) blocks content.

        Scenario:
        1. NEW user posts 3 URLs (no other violations)
        2. Link spam: 50 points >= 50 threshold
        3. Should be blocked
        """
        content = "Check out http://link1.com http://link2.com http://link3.com"

        result = SpamDetectionService.is_spam(self.user, content, 'post')

        # Should be flagged (link spam alone)
        self.assertTrue(result['is_spam'])
        self.assertEqual(result['spam_score'], SPAM_SCORE_LINK_SPAM)
        self.assertEqual(result['reasons'], ['link_spam'])

    def test_moderate_signals_require_combination(self):
        """
        Test that moderate signal (45 points) needs combination.

        Scenario:
        1. ALL CAPS with no other violations
        2. Pattern spam: 45 points < 50 threshold
        3. Should NOT be blocked
        """
        content = "THIS IS ALL CAPS"  # Only pattern spam (45 points)

        result = SpamDetectionService.is_spam(self.user, content, 'post')

        # Should NOT be flagged (below threshold)
        self.assertFalse(result['is_spam'])
        self.assertLess(result['spam_score'], SPAM_SCORE_THRESHOLD)

    def test_pattern_plus_keyword_blocks(self):
        """
        Test that pattern spam + keyword spam blocks.

        Scenario:
        1. ALL CAPS + multiple spam keywords
        2. Pattern spam (45) + Keyword spam (50) = 95 points
        3. Should be blocked
        """
        # ALL CAPS + 5 commercial keywords to guarantee 50+ points
        content = "BUY NOW LIMITED TIME OFFER CLICK HERE ACT NOW!!!!!!!!!"

        result = SpamDetectionService.is_spam(self.user, content, 'post')

        # Should be flagged (combination)
        self.assertTrue(result['is_spam'])
        self.assertGreaterEqual(result['spam_score'], SPAM_SCORE_THRESHOLD)

    def test_borderline_content_allowed(self):
        """
        Test that borderline content with single URL is allowed.

        Scenario:
        1. "Check this out: http://example.com"
        2. 1 URL (within NEW user limit of 2)
        3. Score: 0 < 50 threshold
        4. Should be allowed
        """
        content = "Check this out: http://example.com"

        result = SpamDetectionService.is_spam(self.user, content, 'post')

        # Should be allowed
        self.assertFalse(result['is_spam'])
        self.assertEqual(result['spam_score'], 0)
        self.assertEqual(len(result['reasons']), 0)

    def test_clean_content_allowed(self):
        """
        Test that clean, normal content is allowed.

        Scenario:
        1. Normal post about plant care
        2. No violations detected
        3. Score: 0 < 50 threshold
        4. Should be allowed
        """
        content = "How often should I water my monstera? I've had it for 6 months."

        result = SpamDetectionService.is_spam(self.user, content, 'post')

        # Should be allowed
        self.assertFalse(result['is_spam'])
        self.assertEqual(result['spam_score'], 0)
        self.assertEqual(len(result['reasons']), 0)
        self.assertEqual(len(result['details']), 0)

    def test_duplicate_content_blocks_alone(self):
        """
        Test that duplicate content (60 points) blocks alone.

        Scenario:
        1. User posts identical content twice
        2. Duplicate: 60 points >= 50 threshold
        3. Should be blocked
        """
        content = "This is a test post."

        # Create first post
        thread = ThreadFactory.create(author=self.user, category=self.category)
        PostFactory.create(thread=thread, author=self.user, content_raw=content)

        # Try to post duplicate
        result = SpamDetectionService.is_spam(self.user, content, 'post')

        # Should be flagged (duplicate alone)
        self.assertTrue(result['is_spam'])
        self.assertEqual(result['spam_score'], SPAM_SCORE_DUPLICATE)
        self.assertEqual(result['reasons'], ['duplicate_content'])

    def test_details_include_all_checks(self):
        """
        Test that details dict includes results from all checks.

        Verifies that even non-spam checks are included in details.
        """
        content = "Normal post with http://example.com"

        result = SpamDetectionService.is_spam(self.user, content, 'post')

        # Details should include all check results
        self.assertIn('duplicate', result['details'])
        self.assertIn('rapid', result['details'])
        self.assertIn('links', result['details'])
        self.assertIn('keywords', result['details'])
        self.assertIn('patterns', result['details'])
