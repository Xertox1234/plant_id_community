"""
Spam Detection Service for forum content.

Implements basic heuristics to detect spam, duplicate content, and abuse patterns.
Follows patterns from TrustLevelService: static methods, type hints, caching.

Features:
- Duplicate content detection (exact and fuzzy matching)
- Rapid posting detection (time-based)
- Link spam detection (URL counting)
- Keyword spam detection (common spam patterns)
- Pattern detection (caps, repetition, punctuation abuse)
- Trust level integration (stricter checks for new users)

Performance Targets:
- Cache duplicate check results for 5 minutes
- Fuzzy matching: <50ms per check
- False positive rate: <5% (balance security vs UX)
"""

import logging
import re
import hashlib
from typing import Optional, Dict, Any, List
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
from difflib import SequenceMatcher

from ..constants import (
    TRUST_LEVEL_NEW,
    TRUST_LEVEL_BASIC,
    FLAG_REASON_SPAM,
    FLAG_REASON_DUPLICATE,
    SPAM_URL_LIMIT_NEW,
    SPAM_URL_LIMIT_BASIC,
    SPAM_URL_LIMIT_TRUSTED,
    SPAM_RAPID_POST_SECONDS,
    SPAM_DUPLICATE_SIMILARITY_THRESHOLD,
    SPAM_DUPLICATE_CACHE_TIMEOUT,
    SPAM_KEYWORDS,
    SPAM_KEYWORD_WEIGHTS,
    SPAM_CAPS_RATIO_THRESHOLD,
    SPAM_PUNCTUATION_RATIO_THRESHOLD,
    SPAM_REPETITION_PATTERN,
    SPAM_SCORE_DUPLICATE,
    SPAM_SCORE_RAPID_POST,
    SPAM_SCORE_LINK_SPAM,
    SPAM_SCORE_KEYWORD_SPAM,
    SPAM_SCORE_PATTERN_SPAM,
    SPAM_SCORE_THRESHOLD,
    CACHE_KEY_SPAM_CHECK,
    CACHE_TIMEOUT_SPAM_CHECK,
)

logger = logging.getLogger(__name__)


class SpamDetectionService:
    """
    Service for detecting spam, duplicate content, and abuse patterns.

    All methods are static for stateless operation.
    Follows caching patterns from TrustLevelService.
    """

    # ==================== Duplicate Content Detection ====================

    @staticmethod
    def check_duplicate_content(user, content: str, content_type: str = 'post') -> Dict[str, Any]:
        """
        Check if user has posted identical or very similar content recently.

        Args:
            user: Django User instance
            content: Text content to check
            content_type: 'post' or 'thread'

        Returns:
            Dict with 'is_duplicate', 'similarity', 'previous_content_id'

        Performance:
            Results cached for 5 minutes per user to reduce DB queries
            during rapid posting attempts by bots.

        Example:
            result = SpamDetectionService.check_duplicate_content(user, "Test post")
            if result['is_duplicate']:
                return Response({"error": "Duplicate content detected"}, status=400)
        """
        # Generate cache key using standardized format: forum:spam:{content_type}:{user_id}:{hash}
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
        cache_key = CACHE_KEY_SPAM_CHECK.format(
            content_type=content_type,
            user_id=user.id,
            content_hash=content_hash
        )

        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.debug(f"[SPAM] Cache hit for duplicate check: {cache_key}")
            return cached_result

        # Get user's recent content (last 24 hours)
        recent_cutoff = timezone.now() - timedelta(hours=24)

        if content_type == 'post':
            from ..models import Post
            recent_items = Post.objects.filter(
                author=user,
                created_at__gte=recent_cutoff,
                is_active=True
            ).values('id', 'content_raw')
        else:  # thread
            from ..models import Thread
            recent_items = Thread.objects.filter(
                author=user,
                created_at__gte=recent_cutoff,
                is_active=True
            ).values('id', 'title')

        # Check for exact or fuzzy duplicates
        # For threads, content is "title\ncontent", so extract just title for comparison
        if content_type == 'thread' and '\n' in content:
            content_to_check = content.split('\n')[0]  # Just the title
        else:
            content_to_check = content

        content_lower = content_to_check.lower().strip()

        for item in recent_items:
            existing_content = (item.get('content_raw') or item.get('title', '')).lower().strip()

            # Exact match
            if content_lower == existing_content:
                logger.warning(
                    f"[SPAM] Exact duplicate detected for {user.username}: "
                    f"{content_type} ID {item['id']}"
                )
                result = {
                    'is_duplicate': True,
                    'similarity': 1.0,
                    'previous_content_id': item['id'],
                    'match_type': 'exact'
                }
                # Cache duplicate result
                cache.set(cache_key, result, SPAM_DUPLICATE_CACHE_TIMEOUT)
                return result

            # Fuzzy match (85%+ similarity)
            similarity = SequenceMatcher(None, content_lower, existing_content).ratio()
            if similarity >= SPAM_DUPLICATE_SIMILARITY_THRESHOLD:
                logger.warning(
                    f"[SPAM] Fuzzy duplicate detected for {user.username}: "
                    f"{content_type} ID {item['id']} (similarity: {similarity:.2f})"
                )
                result = {
                    'is_duplicate': True,
                    'similarity': similarity,
                    'previous_content_id': item['id'],
                    'match_type': 'fuzzy'
                }
                # Cache duplicate result (5 minutes)
                cache.set(cache_key, result, CACHE_TIMEOUT_SPAM_CHECK)
                return result

        result = {
            'is_duplicate': False,
            'similarity': 0.0,
            'previous_content_id': None,
            'match_type': None
        }

        # Cache result for 5 minutes (standardized cache timeout)
        cache.set(cache_key, result, CACHE_TIMEOUT_SPAM_CHECK)
        logger.debug(f"[SPAM] Cache set for duplicate check: {cache_key}")

        return result

    # ==================== Rapid Posting Detection ====================

    @staticmethod
    def check_rapid_posting(user, content_type: str = 'post') -> Dict[str, Any]:
        """
        Check if user is posting too quickly (anti-bot protection).

        Args:
            user: Django User instance
            content_type: 'post' or 'thread'

        Returns:
            Dict with 'is_rapid', 'seconds_since_last', 'minimum_wait'

        Note:
            Only enforced for NEW and BASIC users (TRUSTED+ exempt)
        """
        from ..services.trust_level_service import TrustLevelService

        # Get user's trust level
        trust_level = TrustLevelService.get_user_trust_level(user)

        # Only enforce for NEW/BASIC users
        if trust_level not in [TRUST_LEVEL_NEW, TRUST_LEVEL_BASIC]:
            return {
                'is_rapid': False,
                'seconds_since_last': 0,
                'minimum_wait': 0
            }

        # Get last content creation time
        if content_type == 'post':
            from ..models import Post
            last_item = Post.objects.filter(
                author=user,
                is_active=True
            ).order_by('-created_at').first()
        else:  # thread
            from ..models import Thread
            last_item = Thread.objects.filter(
                author=user,
                is_active=True
            ).order_by('-created_at').first()

        if not last_item:
            return {
                'is_rapid': False,
                'seconds_since_last': 0,
                'minimum_wait': SPAM_RAPID_POST_SECONDS
            }

        # Check time difference
        time_diff = timezone.now() - last_item.created_at
        seconds_since_last = int(time_diff.total_seconds())

        if seconds_since_last < SPAM_RAPID_POST_SECONDS:
            logger.warning(
                f"[SPAM] Rapid posting detected for {user.username}: "
                f"{seconds_since_last}s since last {content_type} (min: {SPAM_RAPID_POST_SECONDS}s)"
            )
            return {
                'is_rapid': True,
                'seconds_since_last': seconds_since_last,
                'minimum_wait': SPAM_RAPID_POST_SECONDS
            }

        return {
            'is_rapid': False,
            'seconds_since_last': seconds_since_last,
            'minimum_wait': SPAM_RAPID_POST_SECONDS
        }

    # ==================== Link Spam Detection ====================

    @staticmethod
    def check_link_spam(user, content: str) -> Dict[str, Any]:
        """
        Check if content contains excessive URLs (link spam).

        Args:
            user: Django User instance
            content: Text content to check

        Returns:
            Dict with 'is_spam', 'url_count', 'url_limit'

        Note:
            URL limits vary by trust level (NEW: 2, BASIC: 5, TRUSTED+: 10)
        """
        from ..services.trust_level_service import TrustLevelService

        # Count URLs in content
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, content)
        url_count = len(urls)

        # Get user's trust level
        trust_level = TrustLevelService.get_user_trust_level(user)

        # Determine URL limit based on trust level
        if trust_level == TRUST_LEVEL_NEW:
            url_limit = SPAM_URL_LIMIT_NEW
        elif trust_level == TRUST_LEVEL_BASIC:
            url_limit = SPAM_URL_LIMIT_BASIC
        else:  # TRUSTED+
            url_limit = SPAM_URL_LIMIT_TRUSTED

        if url_count > url_limit:
            logger.warning(
                f"[SPAM] Link spam detected for {user.username}: "
                f"{url_count} URLs (limit: {url_limit} for {trust_level})"
            )
            return {
                'is_spam': True,
                'url_count': url_count,
                'url_limit': url_limit,
                'urls': urls
            }

        return {
            'is_spam': False,
            'url_count': url_count,
            'url_limit': url_limit,
            'urls': urls
        }

    # ==================== Keyword Spam Detection ====================

    @staticmethod
    def check_keyword_spam(content: str) -> Dict[str, Any]:
        """
        Check if content contains common spam keywords using weighted scoring.

        Args:
            content: Text content to check

        Returns:
            Dict with 'is_spam', 'matched_keywords', 'keyword_count', 'weighted_score'

        Note:
            Uses weighted keyword scoring by category:
            - Commercial spam (buy now, click here): 10 points each
            - Financial spam (free money, bitcoin): 20 points each
            - Phishing (verify account, suspended): 30 points each (highest risk)

            Threshold: weighted score >= 50 points = spam
            Example: 2 phishing keywords (30+30=60) = SPAM
            Example: 5 commercial keywords (10*5=50) = SPAM
        """
        content_lower = content.lower()
        matched_keywords = []
        weighted_score = 0

        # Calculate weighted score for all matched keywords
        for keyword in SPAM_KEYWORDS:
            if keyword in content_lower:
                matched_keywords.append(keyword)
                weight = SPAM_KEYWORD_WEIGHTS.get(keyword, 10)  # Default weight: 10
                weighted_score += weight

        # Threshold: weighted score >= 50 = likely spam
        # This allows high-risk keywords (phishing) to trigger alone,
        # while low-risk keywords (commercial) require multiple matches
        is_spam = weighted_score >= SPAM_SCORE_KEYWORD_SPAM

        if is_spam:
            logger.warning(
                f"[SPAM] Keyword spam detected: {matched_keywords} "
                f"(weighted score: {weighted_score})"
            )

        return {
            'is_spam': is_spam,
            'matched_keywords': matched_keywords,
            'keyword_count': len(matched_keywords),
            'weighted_score': weighted_score
        }

    # ==================== Pattern Detection ====================

    @staticmethod
    def check_spam_patterns(content: str) -> Dict[str, Any]:
        """
        Check for spam patterns (caps abuse, repetition, punctuation abuse).

        Args:
            content: Text content to check

        Returns:
            Dict with 'is_spam', 'patterns_detected', 'details'

        Patterns:
            - ALL CAPS (>70% uppercase)
            - Excessive punctuation (>30% of text)
            - Character repetition (5+ repeated chars)
        """
        patterns_detected = []
        details = {}

        # Skip very short content (<=10 chars)
        if len(content) <= 10:
            return {
                'is_spam': False,
                'patterns_detected': [],
                'details': {}
            }

        # Check for ALL CAPS abuse
        alpha_chars = [c for c in content if c.isalpha()]
        if alpha_chars:
            caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if caps_ratio >= SPAM_CAPS_RATIO_THRESHOLD:
                patterns_detected.append('excessive_caps')
                details['caps_ratio'] = caps_ratio

        # Check for punctuation abuse
        punctuation_chars = [c for c in content if not c.isalnum() and not c.isspace()]
        punctuation_ratio = len(punctuation_chars) / len(content) if content else 0
        if punctuation_ratio >= SPAM_PUNCTUATION_RATIO_THRESHOLD:
            patterns_detected.append('excessive_punctuation')
            details['punctuation_ratio'] = punctuation_ratio

        # Check for character repetition (e.g., "!!!!!", "aaaaa")
        repetition_matches = re.findall(SPAM_REPETITION_PATTERN, content)
        if repetition_matches:
            patterns_detected.append('character_repetition')
            details['repetition_count'] = len(repetition_matches)

        is_spam = len(patterns_detected) >= 2  # 2+ patterns = likely spam

        if is_spam:
            logger.warning(
                f"[SPAM] Pattern spam detected: {patterns_detected}"
            )

        return {
            'is_spam': is_spam,
            'patterns_detected': patterns_detected,
            'details': details
        }

    # ==================== Comprehensive Spam Check ====================

    @staticmethod
    def is_spam(user, content: str, content_type: str = 'post') -> Dict[str, Any]:
        """
        Run all spam detection checks and return comprehensive result.

        Args:
            user: Django User instance
            content: Text content to check
            content_type: 'post' or 'thread'

        Returns:
            Dict with 'is_spam', 'spam_score', 'reasons', 'details'

        Spam Score Calculation:
            - Duplicate content: +{SPAM_SCORE_DUPLICATE} points
            - Rapid posting: +{SPAM_SCORE_RAPID_POST} points
            - Link spam: +{SPAM_SCORE_LINK_SPAM} points
            - Keyword spam: +{SPAM_SCORE_KEYWORD_SPAM} points
            - Pattern spam: +{SPAM_SCORE_PATTERN_SPAM} points
            - Total >={SPAM_SCORE_THRESHOLD} = SPAM

        Example:
            result = SpamDetectionService.is_spam(user, "BUY NOW!!! http://spam.com")
            if result['is_spam']:
                # Auto-flag for moderation
                FlaggedContent.objects.create(
                    content_type=content_type,
                    reason=FLAG_REASON_SPAM,
                    explanation=f"Auto-flagged: {result['reasons']}"
                )
        """
        spam_score = 0
        reasons = []
        details = {}

        # 1. Check duplicate content
        duplicate_result = SpamDetectionService.check_duplicate_content(user, content, content_type)
        if duplicate_result['is_duplicate']:
            spam_score += SPAM_SCORE_DUPLICATE
            reasons.append('duplicate_content')
            details['duplicate'] = duplicate_result

        # 2. Check rapid posting
        rapid_result = SpamDetectionService.check_rapid_posting(user, content_type)
        if rapid_result['is_rapid']:
            spam_score += SPAM_SCORE_RAPID_POST
            reasons.append('rapid_posting')
            details['rapid'] = rapid_result

        # 3. Check link spam
        link_result = SpamDetectionService.check_link_spam(user, content)
        if link_result['is_spam']:
            spam_score += SPAM_SCORE_LINK_SPAM
            reasons.append('link_spam')
            details['links'] = link_result

        # 4. Check keyword spam
        keyword_result = SpamDetectionService.check_keyword_spam(content)
        if keyword_result['is_spam']:
            spam_score += SPAM_SCORE_KEYWORD_SPAM
            reasons.append('keyword_spam')
            details['keywords'] = keyword_result

        # 5. Check spam patterns
        pattern_result = SpamDetectionService.check_spam_patterns(content)
        if pattern_result['is_spam']:
            spam_score += SPAM_SCORE_PATTERN_SPAM
            reasons.append('spam_patterns')
            details['patterns'] = pattern_result

        # Determine if spam based on threshold
        is_spam = spam_score >= SPAM_SCORE_THRESHOLD

        if is_spam:
            logger.warning(
                f"[SPAM] Content flagged as spam for {user.username}: "
                f"score={spam_score}, reasons={reasons}"
            )

        return {
            'is_spam': is_spam,
            'spam_score': spam_score,
            'reasons': reasons,
            'details': details
        }
