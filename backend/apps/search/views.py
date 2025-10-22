"""
Search API views.
"""

from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from django.utils import timezone
from django.db.models import Count, Avg, Q
from django.contrib.auth import get_user_model
from machina.apps.forum.models import Forum
from apps.plant_identification.models import PlantSpecies, PlantDiseaseDatabase
from apps.blog.models import BlogCategory
import logging

from .services.search_service import UnifiedSearchService
from .serializers import (
    SearchRequestSerializer, SearchResponseSerializer, SearchSuggestionSerializer,
    SearchSuggestionsRequestSerializer, SavedSearchSerializer, 
    UserSearchPreferencesSerializer, SearchAnalyticsSerializer, SearchFiltersSerializer
)
from .models import SearchQuery, SavedSearch, UserSearchPreferences

User = get_user_model()
logger = logging.getLogger(__name__)


class UnifiedSearchView(APIView):
    """
    Unified search endpoint that searches across all content types.
    """
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """
        Perform unified search.
        
        POST /api/search/unified/
        {
            "query": "rose care",
            "content_types": ["plants", "forum", "blog"],
            "page": 1,
            "per_page": 20,
            "sort_by": "relevance",
            "plant_family": "Rosaceae",
            "date_from": "2024-01-01T00:00:00Z"
        }
        """
        serializer = SearchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        
        # Extract search parameters
        query = validated_data['query']
        content_types = validated_data['content_types']
        page = validated_data['page']
        per_page = validated_data['per_page']
        sort_by = validated_data['sort_by']
        
        # Extract filters
        filters = {}
        filter_fields = [
            'date_from', 'date_to', 'forum_category', 'blog_category',
            'plant_family', 'plant_type', 'care_level', 'disease_type'
        ]
        
        for field in filter_fields:
            if field in validated_data:
                filters[field] = validated_data[field]
        
        # Get user and session for tracking
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key if hasattr(request, 'session') else None
        
        try:
            # Perform search
            search_service = UnifiedSearchService()
            search_results = search_service.search(
                query=query,
                content_types=content_types,
                filters=filters,
                user=user,
                session_key=session_key,
                page=page,
                per_page=per_page,
                sort_by=sort_by
            )
            
            # Serialize response
            response_serializer = SearchResponseSerializer(data=search_results)
            if response_serializer.is_valid():
                return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
            else:
                logger.error(f"Search response serialization failed: {response_serializer.errors}")
                return Response(search_results, status=status.HTTP_200_OK)  # Return raw data if serialization fails
        
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return Response(
                {'error': f'Search failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SearchSuggestionsView(APIView):
    """
    Get search suggestions based on partial query.
    """
    
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """
        Get search suggestions.
        
        GET /api/search/suggestions/?query=rose&limit=10
        """
        serializer = SearchSuggestionsRequestSerializer(data=request.GET)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        query = serializer.validated_data['query']
        limit = serializer.validated_data['limit']
        
        try:
            search_service = UnifiedSearchService()
            suggestions = search_service.get_search_suggestions(query, limit)
            
            suggestion_serializer = SearchSuggestionSerializer(suggestions, many=True)
            return Response(suggestion_serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Search suggestions failed: {str(e)}")
            return Response(
                {'error': f'Failed to get suggestions: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SavedSearchListCreateView(ListCreateAPIView):
    """
    List and create saved searches for authenticated users.
    """
    
    serializer_class = SavedSearchSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return SavedSearch.objects.filter(user=self.request.user, is_active=True)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SavedSearchDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a saved search.
    """
    
    serializer_class = SavedSearchSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return SavedSearch.objects.filter(user=self.request.user)
    
    def perform_destroy(self, instance):
        # Soft delete by marking as inactive
        instance.is_active = False
        instance.save()


class UserSearchPreferencesView(APIView):
    """
    Get and update user search preferences.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get user's search preferences."""
        preferences, created = UserSearchPreferences.objects.get_or_create(
            user=request.user
        )
        serializer = UserSearchPreferencesSerializer(preferences)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request):
        """Update user's search preferences."""
        preferences, created = UserSearchPreferences.objects.get_or_create(
            user=request.user
        )
        serializer = UserSearchPreferencesSerializer(preferences, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SearchFiltersView(APIView):
    """
    Get available search filter options.
    """
    
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """
        Get all available filter options for search.
        
        GET /api/search/filters/
        """
        try:
            # Get forum categories
            forum_categories = []
            for forum in Forum.objects.all():
                forum_categories.append({
                    'id': forum.id,
                    'name': forum.name,
                    'description': getattr(forum, 'description', '')
                })
            
            # Get blog categories
            blog_categories = []
            try:
                for category in BlogCategory.objects.all():
                    blog_categories.append({
                        'slug': category.slug,
                        'name': category.name
                    })
            except Exception:
                # BlogCategory might not exist
                pass
            
            # Get plant families (top 20 most common)
            plant_families = list(
                PlantSpecies.objects.exclude(family='')
                .values_list('family', flat=True)
                .annotate(count=Count('family'))
                .order_by('-count')[:20]
            )
            
            # Get plant types
            plant_types = []
            try:
                plant_type_choices = PlantSpecies._meta.get_field('plant_type').choices
                plant_types = [{'value': choice[0], 'label': choice[1]} for choice in plant_type_choices]
            except Exception:
                pass
            
            # Get care levels
            care_levels = []
            try:
                care_level_choices = PlantSpecies._meta.get_field('care_difficulty').choices
                care_levels = [{'value': choice[0], 'label': choice[1]} for choice in care_level_choices]
            except Exception:
                pass
            
            # Get disease types
            disease_types = []
            try:
                disease_type_choices = PlantDiseaseDatabase._meta.get_field('disease_type').choices
                disease_types = [{'value': choice[0], 'label': choice[1]} for choice in disease_type_choices]
            except Exception:
                pass
            
            filters_data = {
                'forum_categories': forum_categories,
                'blog_categories': blog_categories,
                'plant_families': plant_families,
                'plant_types': plant_types,
                'care_levels': care_levels,
                'disease_types': disease_types,
            }
            
            serializer = SearchFiltersSerializer(data=filters_data)
            if serializer.is_valid():
                return Response(serializer.validated_data, status=status.HTTP_200_OK)
            else:
                return Response(filters_data, status=status.HTTP_200_OK)  # Return raw data if serialization fails
        
        except Exception as e:
            logger.error(f"Failed to get search filters: {str(e)}")
            return Response(
                {'error': f'Failed to get filters: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SearchAnalyticsView(APIView):
    """
    Get search analytics data (admin only).
    """
    
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        """
        Get search analytics data.
        
        GET /api/search/analytics/?days=30
        """
        days = int(request.GET.get('days', 30))
        end_date = timezone.now()
        start_date = end_date - timezone.timedelta(days=days)
        
        try:
            # Query searches within date range
            searches = SearchQuery.objects.filter(
                created_at__range=[start_date, end_date]
            )
            
            # Calculate analytics
            total_searches = searches.count()
            unique_queries = searches.values('query_text').distinct().count()
            avg_response_time = searches.aggregate(avg_time=Avg('response_time_ms'))['avg_time'] or 0
            
            # Top queries
            top_queries = list(
                searches.values('query_text')
                .annotate(count=Count('query_text'))
                .order_by('-count')[:10]
            )
            
            # Content type distribution
            content_type_dist = {}
            for search in searches.values('content_type').annotate(count=Count('content_type')):
                content_type_dist[search['content_type']] = search['count']
            
            # Zero result queries
            zero_result_queries = list(
                searches.filter(results_count=0)
                .values('query_text')
                .annotate(count=Count('query_text'))
                .order_by('-count')[:10]
            )
            
            # Search trends (daily counts)
            search_trends = []
            for i in range(days):
                day = start_date + timezone.timedelta(days=i)
                day_end = day + timezone.timedelta(days=1)
                day_count = searches.filter(created_at__range=[day, day_end]).count()
                search_trends.append({
                    'date': day.date().isoformat(),
                    'count': day_count
                })
            
            analytics_data = {
                'total_searches': total_searches,
                'unique_queries': unique_queries,
                'avg_response_time': round(avg_response_time, 2),
                'top_queries': top_queries,
                'content_type_distribution': content_type_dist,
                'search_trends': search_trends,
                'zero_result_queries': zero_result_queries,
            }
            
            serializer = SearchAnalyticsSerializer(data=analytics_data)
            if serializer.is_valid():
                return Response(serializer.validated_data, status=status.HTTP_200_OK)
            else:
                return Response(analytics_data, status=status.HTTP_200_OK)  # Return raw data if serialization fails
        
        except Exception as e:
            logger.error(f"Failed to get search analytics: {str(e)}")
            return Response(
                {'error': f'Failed to get analytics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def track_search_click(request):
    """
    Track clicks on search results for analytics.
    
    POST /api/search/track-click/
    {
        "search_query_id": "uuid",
        "result_type": "plant_species",
        "result_id": "123",
        "result_position": 1,
        "result_page": 1
    }
    """
    try:
        data = request.data
        search_query_id = data.get('search_query_id')
        result_type = data.get('result_type')
        result_id = data.get('result_id')
        result_position = data.get('result_position', 1)
        result_page = data.get('result_page', 1)
        
        if not all([search_query_id, result_type, result_id]):
            return Response(
                {'error': 'search_query_id, result_type, and result_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find the search query
        try:
            search_query = SearchQuery.objects.get(uuid=search_query_id)
        except SearchQuery.DoesNotExist:
            return Response(
                {'error': 'Search query not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create click tracking record
        from .models import SearchResultClick
        SearchResultClick.objects.create(
            search_query=search_query,
            result_type=result_type,
            result_id=str(result_id),
            result_position=int(result_position),
            result_page=int(result_page),
            user=request.user if request.user.is_authenticated else None,
            session_key=request.session.session_key if hasattr(request, 'session') else None
        )
        
        return Response({'status': 'success'}, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f"Failed to track search click: {str(e)}")
        return Response(
            {'error': f'Failed to track click: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )