"""
Serializers for search API endpoints.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import SearchQuery, UserSearchPreferences, SavedSearch

User = get_user_model()


class SearchRequestSerializer(serializers.Serializer):
    """
    Serializer for search request parameters.
    """
    
    CONTENT_TYPE_CHOICES = [
        ('all', 'All Content'),
        ('forum', 'Forum Posts'),
        ('plants', 'Plant Species'),
        ('blog', 'Blog Posts'),
        ('diseases', 'Plant Diseases'),
        ('care_guides', 'Care Guides'),
    ]
    
    SORT_CHOICES = [
        ('relevance', 'Relevance'),
        ('date', 'Date'),
        ('popularity', 'Popularity'),
    ]
    
    query = serializers.CharField(
        min_length=2,
        max_length=500,
        help_text="Search query text"
    )
    
    content_types = serializers.MultipleChoiceField(
        choices=CONTENT_TYPE_CHOICES,
        required=False,
        default=['all'],
        help_text="Types of content to search"
    )
    
    page = serializers.IntegerField(
        min_value=1,
        default=1,
        help_text="Page number for pagination"
    )
    
    per_page = serializers.IntegerField(
        min_value=1,
        max_value=100,
        default=20,
        help_text="Number of results per page"
    )
    
    sort_by = serializers.ChoiceField(
        choices=SORT_CHOICES,
        default='relevance',
        help_text="How to sort the results"
    )
    
    # Filter parameters
    date_from = serializers.DateTimeField(
        required=False,
        help_text="Filter results from this date"
    )
    
    date_to = serializers.DateTimeField(
        required=False,
        help_text="Filter results until this date"
    )
    
    forum_category = serializers.IntegerField(
        required=False,
        help_text="Filter forum results by category ID"
    )
    
    blog_category = serializers.CharField(
        required=False,
        help_text="Filter blog results by category slug"
    )
    
    plant_family = serializers.CharField(
        required=False,
        help_text="Filter plant results by family"
    )
    
    plant_type = serializers.CharField(
        required=False,
        help_text="Filter plant results by type"
    )
    
    care_level = serializers.CharField(
        required=False,
        help_text="Filter plant results by care difficulty"
    )
    
    disease_type = serializers.CharField(
        required=False,
        help_text="Filter disease results by type"
    )
    
    def validate(self, data):
        """Custom validation for search parameters."""
        # Ensure date_from is before date_to
        if data.get('date_from') and data.get('date_to'):
            if data['date_from'] > data['date_to']:
                raise serializers.ValidationError("date_from must be before date_to")
        
        # Clean content_types - remove 'all' if other types are specified
        if 'all' in data.get('content_types', []) and len(data.get('content_types', [])) > 1:
            data['content_types'] = [ct for ct in data['content_types'] if ct != 'all']
        
        if 'all' in data.get('content_types', []):
            data['content_types'] = ['forum', 'plants', 'blog', 'diseases']
        
        return data


class SearchResultSerializer(serializers.Serializer):
    """
    Serializer for individual search results.
    """
    
    type = serializers.CharField(help_text="Type of content")
    id = serializers.CharField(help_text="Unique identifier")
    title = serializers.CharField(help_text="Title or name")
    content = serializers.CharField(help_text="Preview content")
    url = serializers.CharField(help_text="URL to view full content")
    
    author = serializers.DictField(
        required=False,
        allow_null=True,
        help_text="Author information"
    )
    
    created_at = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Creation date (ISO format)"
    )
    
    metadata = serializers.DictField(
        help_text="Additional metadata specific to content type"
    )
    
    rank = serializers.FloatField(
        help_text="Search relevance rank"
    )


class SearchResponseSerializer(serializers.Serializer):
    """
    Serializer for search response.
    """
    
    query = serializers.CharField(help_text="Original search query")
    results = SearchResultSerializer(many=True, help_text="Search results")
    
    pagination = serializers.DictField(help_text="Pagination information")
    result_counts = serializers.DictField(help_text="Result counts by content type")
    total_count = serializers.IntegerField(help_text="Total number of results")
    response_time_ms = serializers.IntegerField(help_text="Response time in milliseconds")
    applied_filters = serializers.DictField(help_text="Filters that were applied")
    content_types_searched = serializers.ListField(help_text="Content types that were searched")
    
    error = serializers.CharField(
        required=False,
        help_text="Error message if search failed"
    )


class SearchSuggestionSerializer(serializers.Serializer):
    """
    Serializer for search suggestions.
    """
    
    text = serializers.CharField(help_text="Suggested search text")
    type = serializers.CharField(help_text="Type of suggestion")
    score = serializers.FloatField(help_text="Relevance score")


class SearchSuggestionsRequestSerializer(serializers.Serializer):
    """
    Serializer for search suggestions request.
    """
    
    query = serializers.CharField(
        min_length=1,
        max_length=100,
        help_text="Partial search query"
    )
    
    limit = serializers.IntegerField(
        min_value=1,
        max_value=20,
        default=10,
        help_text="Maximum number of suggestions"
    )


class SavedSearchSerializer(serializers.ModelSerializer):
    """
    Serializer for saved searches.
    """
    
    class Meta:
        model = SavedSearch
        fields = [
            'id', 'name', 'query_text', 'content_type', 'search_parameters',
            'enable_alerts', 'alert_frequency', 'is_active', 'times_used',
            'last_used', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'times_used', 'last_used', 'created_at', 'updated_at']
    
    def validate_name(self, value):
        """Ensure saved search name is unique for the user."""
        user = self.context['request'].user
        if SavedSearch.objects.filter(user=user, name=value).exists():
            if not self.instance or self.instance.name != value:
                raise serializers.ValidationError("You already have a saved search with this name.")
        return value


class UserSearchPreferencesSerializer(serializers.ModelSerializer):
    """
    Serializer for user search preferences.
    """
    
    class Meta:
        model = UserSearchPreferences
        fields = [
            'default_content_type', 'results_per_page', 'save_search_history',
            'search_history_days', 'enable_personalized_results', 'boost_expert_content',
            'enable_search_alerts'
        ]
    
    def validate_results_per_page(self, value):
        """Validate results per page is within reasonable limits."""
        if value < 5 or value > 100:
            raise serializers.ValidationError("Results per page must be between 5 and 100.")
        return value
    
    def validate_search_history_days(self, value):
        """Validate search history days is reasonable."""
        if value < 1 or value > 365:
            raise serializers.ValidationError("Search history days must be between 1 and 365.")
        return value


class SearchAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for search analytics data.
    """
    
    total_searches = serializers.IntegerField(help_text="Total number of searches")
    unique_queries = serializers.IntegerField(help_text="Number of unique query texts")
    avg_response_time = serializers.FloatField(help_text="Average response time in ms")
    top_queries = serializers.ListField(help_text="Most popular search queries")
    content_type_distribution = serializers.DictField(help_text="Search distribution by content type")
    search_trends = serializers.ListField(help_text="Search volume trends over time")
    zero_result_queries = serializers.ListField(help_text="Queries that returned no results")


class SearchFiltersSerializer(serializers.Serializer):
    """
    Serializer for available search filters.
    """
    
    forum_categories = serializers.ListField(help_text="Available forum categories")
    blog_categories = serializers.ListField(help_text="Available blog categories")
    plant_families = serializers.ListField(help_text="Available plant families")
    plant_types = serializers.ListField(help_text="Available plant types")
    care_levels = serializers.ListField(help_text="Available care difficulty levels")
    disease_types = serializers.ListField(help_text="Available disease types")