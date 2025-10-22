"""
Search models for advanced search functionality.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.contrib.postgres.indexes import GinIndex
import uuid

User = get_user_model()


class SearchQuery(models.Model):
    """
    Model to track search queries for analytics and suggestions.
    """
    
    CONTENT_TYPE_CHOICES = [
        ('all', 'All Content'),
        ('forum', 'Forum Posts'),
        ('plants', 'Plant Species'),
        ('blog', 'Blog Posts'),
        ('diseases', 'Plant Diseases'),
        ('care_guides', 'Care Guides'),
    ]
    
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for the search query"
    )
    
    query_text = models.TextField(
        help_text="The search query text"
    )
    
    content_type = models.CharField(
        max_length=100,
        choices=CONTENT_TYPE_CHOICES,
        default='all',
        help_text="Type of content being searched"
    )
    
    # User tracking (optional for anonymous searches)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="User who performed the search (if logged in)"
    )
    
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        help_text="Session key for anonymous users"
    )
    
    # Search metadata
    results_count = models.IntegerField(
        default=0,
        help_text="Number of results returned"
    )
    
    response_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Search response time in milliseconds"
    )
    
    # Applied filters (JSON field)
    filters_applied = models.JSONField(
        default=dict,
        blank=True,
        help_text="Filters that were applied to the search"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['query_text', 'content_type']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['session_key', '-created_at']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Search: {self.query_text[:50]}... ({self.content_type})"


class UserSearchPreferences(models.Model):
    """
    User preferences for search behavior and saved searches.
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='search_preferences'
    )
    
    # Default search settings
    default_content_type = models.CharField(
        max_length=20,
        choices=SearchQuery.CONTENT_TYPE_CHOICES,
        default='all',
        help_text="Default content type for searches"
    )
    
    results_per_page = models.IntegerField(
        default=20,
        help_text="Number of results to show per page"
    )
    
    # Search history settings
    save_search_history = models.BooleanField(
        default=True,
        help_text="Whether to save search history"
    )
    
    search_history_days = models.IntegerField(
        default=30,
        help_text="Number of days to keep search history"
    )
    
    # Personalization settings
    enable_personalized_results = models.BooleanField(
        default=True,
        help_text="Enable personalized search results based on interests"
    )
    
    boost_expert_content = models.BooleanField(
        default=True,
        help_text="Boost results from expert users"
    )
    
    # Notification preferences
    enable_search_alerts = models.BooleanField(
        default=False,
        help_text="Enable alerts for new content matching saved searches"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Search preferences for {self.user.username}"


class SavedSearch(models.Model):
    """
    User's saved search queries for quick access and alerts.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='saved_searches'
    )
    
    name = models.CharField(
        max_length=100,
        help_text="User-defined name for the saved search"
    )
    
    query_text = models.TextField(
        help_text="The search query text"
    )
    
    content_type = models.CharField(
        max_length=20,
        choices=SearchQuery.CONTENT_TYPE_CHOICES,
        default='all'
    )
    
    # Search parameters (JSON field for filters, sorting, etc.)
    search_parameters = models.JSONField(
        default=dict,
        help_text="Complete search parameters including filters"
    )
    
    # Alert settings
    enable_alerts = models.BooleanField(
        default=False,
        help_text="Send alerts when new content matches this search"
    )
    
    alert_frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Immediate'),
            ('daily', 'Daily Digest'),
            ('weekly', 'Weekly Digest'),
        ],
        default='daily',
        help_text="How often to send search alerts"
    )
    
    last_alert_sent = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last alert was sent"
    )
    
    # Metadata
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this saved search is active"
    )
    
    times_used = models.IntegerField(
        default=0,
        help_text="Number of times this saved search has been used"
    )
    
    last_used = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this saved search was last used"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_used', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['enable_alerts', 'alert_frequency']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"


class SearchResultClick(models.Model):
    """
    Track clicks on search results for analytics and relevance improvement.
    """
    
    search_query = models.ForeignKey(
        SearchQuery,
        on_delete=models.CASCADE,
        related_name='result_clicks'
    )
    
    # Result metadata
    result_type = models.CharField(
        max_length=20,
        help_text="Type of content that was clicked"
    )
    
    result_id = models.CharField(
        max_length=100,
        help_text="ID of the content that was clicked"
    )
    
    result_position = models.IntegerField(
        help_text="Position of the result in the search results (1-based)"
    )
    
    result_page = models.IntegerField(
        default=1,
        help_text="Page number where the result appeared"
    )
    
    # User tracking
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True
    )
    
    clicked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-clicked_at']
        indexes = [
            models.Index(fields=['search_query', 'result_type']),
            models.Index(fields=['result_type', 'result_id']),
            models.Index(fields=['-clicked_at']),
        ]
    
    def __str__(self):
        return f"Click on {self.result_type}:{self.result_id} (pos {self.result_position})"