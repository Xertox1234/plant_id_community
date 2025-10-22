"""
Core search service that orchestrates searching across all content types.
"""

from django.db import models
from django.contrib.postgres.search import (
    SearchVector, SearchQuery as PgSearchQuery, SearchRank, SearchHeadline
)
from django.utils import timezone
from typing import Dict, List, Optional, Tuple, Any
import time
import logging

# Import models from different apps
from machina.apps.forum_conversation.models import Topic, Post
from apps.plant_identification.models import PlantSpecies, PlantDiseaseDatabase
from apps.blog.models import BlogPostPage
from ..models import SearchQuery, SearchResultClick

logger = logging.getLogger(__name__)


class UnifiedSearchService:
    """
    Service class that provides unified search across all content types.
    """
    
    def __init__(self):
        self.search_weights = {
            'title': 'A',  # Highest weight
            'content': 'B',  # Medium weight  
            'tags': 'C',   # Lower weight
            'metadata': 'D'  # Lowest weight
        }
    
    def search(
        self,
        query: str,
        content_types: List[str] = None,
        filters: Dict[str, Any] = None,
        user=None,
        session_key: str = None,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = 'relevance'
    ) -> Dict[str, Any]:
        """
        Perform unified search across all content types.
        
        Args:
            query: Search query string
            content_types: List of content types to search ['forum', 'plants', 'blog', 'diseases']
            filters: Additional filters to apply
            user: User performing the search (optional)
            session_key: Session key for anonymous users
            page: Page number for pagination
            per_page: Results per page
            sort_by: Sorting method ('relevance', 'date', 'popularity')
            
        Returns:
            Dictionary with search results and metadata
        """
        start_time = time.time()
        
        if not query or len(query.strip()) < 2:
            return self._empty_results("Query too short")
        
        query = query.strip()
        content_types = content_types or ['forum', 'plants', 'blog', 'diseases']
        filters = filters or {}
        
        try:
            # Create PostgreSQL search query
            search_query = PgSearchQuery(query)
            
            # Search each content type
            all_results = []
            result_counts = {}
            
            if 'forum' in content_types:
                forum_results, forum_count = self._search_forum(search_query, query, filters)
                all_results.extend(forum_results)
                result_counts['forum'] = forum_count
            
            if 'plants' in content_types:
                plant_results, plant_count = self._search_plants(search_query, query, filters)
                all_results.extend(plant_results)
                result_counts['plants'] = plant_count
            
            if 'blog' in content_types:
                blog_results, blog_count = self._search_blog(search_query, query, filters)
                all_results.extend(blog_results)
                result_counts['blog'] = blog_count
            
            if 'diseases' in content_types:
                disease_results, disease_count = self._search_diseases(search_query, query, filters)
                all_results.extend(disease_results)
                result_counts['diseases'] = disease_count
            
            # Sort results
            sorted_results = self._sort_results(all_results, sort_by)
            
            # Apply pagination
            total_results = len(sorted_results)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_results = sorted_results[start_idx:end_idx]
            
            # Calculate response time
            response_time = int((time.time() - start_time) * 1000)
            
            # Log search query
            self._log_search_query(
                query=query,
                content_types=content_types,
                filters=filters,
                user=user,
                session_key=session_key,
                results_count=total_results,
                response_time=response_time
            )
            
            return {
                'query': query,
                'results': paginated_results,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_results': total_results,
                    'total_pages': (total_results + per_page - 1) // per_page,
                    'has_next': end_idx < total_results,
                    'has_previous': page > 1,
                },
                'result_counts': result_counts,
                'total_count': total_results,
                'response_time_ms': response_time,
                'applied_filters': filters,
                'content_types_searched': content_types,
            }
            
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {str(e)}")
            return self._empty_results(f"Search error: {str(e)}")
    
    def _search_forum(self, search_query, query_text: str, filters: Dict) -> Tuple[List[Dict], int]:
        """Search forum topics and posts."""
        results = []
        
        # Search topics
        topics_qs = Topic.objects.filter(approved=True)
        
        # Apply filters
        if filters.get('forum_category'):
            topics_qs = topics_qs.filter(forum_id=filters['forum_category'])
        
        if filters.get('date_from'):
            topics_qs = topics_qs.filter(created__gte=filters['date_from'])
        
        if filters.get('date_to'):
            topics_qs = topics_qs.filter(created__lte=filters['date_to'])
        
        # Apply full-text search
        topics_qs = topics_qs.annotate(
            search=SearchVector('subject', weight='A') + SearchVector('first_post__content', weight='B'),
            rank=SearchRank(SearchVector('subject', weight='A') + SearchVector('first_post__content', weight='B'), search_query)
        ).filter(search=search_query).order_by('-rank')
        
        # Convert topics to unified format
        for topic in topics_qs.select_related('poster', 'forum')[:20]:  # Limit per content type
            results.append({
                'type': 'forum_topic',
                'id': str(topic.id),
                'title': topic.subject,
                'content': getattr(topic.first_post, 'content', '')[:200] + '...' if getattr(topic.first_post, 'content', '') else '',
                'url': f'/forum/topic/{topic.id}',
                'author': {
                    'username': topic.poster.username if topic.poster else 'Unknown',
                    'id': topic.poster.id if topic.poster else None,
                },
                'created_at': topic.created.isoformat() if topic.created else None,
                'metadata': {
                    'forum_name': topic.forum.name if topic.forum else '',
                    'replies_count': getattr(topic, 'posts_count', 0) - 1,  # Subtract first post
                    'views_count': getattr(topic, 'views_count', 0),
                },
                'rank': float(getattr(topic, 'rank', 0)),
            })
        
        return results, topics_qs.count()
    
    def _search_plants(self, search_query, query_text: str, filters: Dict) -> Tuple[List[Dict], int]:
        """Search plant species."""
        results = []
        
        plants_qs = PlantSpecies.objects.all()
        
        # Apply filters
        if filters.get('plant_family'):
            plants_qs = plants_qs.filter(family__icontains=filters['plant_family'])
        
        if filters.get('plant_type'):
            plants_qs = plants_qs.filter(plant_type=filters['plant_type'])
        
        if filters.get('care_level'):
            plants_qs = plants_qs.filter(care_difficulty=filters['care_level'])
        
        # Apply full-text search
        plants_qs = plants_qs.annotate(
            search=SearchVector('scientific_name', weight='A') + 
                   SearchVector('common_names', weight='A') + 
                   SearchVector('family', weight='B'),
            rank=SearchRank(
                SearchVector('scientific_name', weight='A') + 
                SearchVector('common_names', weight='A') + 
                SearchVector('family', weight='B'), 
                search_query
            )
        ).filter(search=search_query).order_by('-rank')
        
        # Convert plants to unified format
        for plant in plants_qs[:20]:  # Limit per content type
            results.append({
                'type': 'plant_species',
                'id': str(plant.uuid),
                'title': plant.scientific_name,
                'content': f"Family: {plant.family}. Common names: {plant.common_names}",
                'url': f'/plants/{plant.uuid}',
                'author': None,  # Plants don't have authors
                'created_at': plant.created_at.isoformat() if hasattr(plant, 'created_at') else None,
                'metadata': {
                    'family': plant.family,
                    'common_names': plant.common_names,
                    'plant_type': plant.plant_type,
                    'care_difficulty': getattr(plant, 'care_difficulty', 'Unknown'),
                },
                'rank': float(getattr(plant, 'rank', 0)),
            })
        
        return results, plants_qs.count()
    
    def _search_blog(self, search_query, query_text: str, filters: Dict) -> Tuple[List[Dict], int]:
        """Search blog posts."""
        results = []
        
        # Only search live blog pages
        blog_qs = BlogPostPage.objects.live()
        
        # Apply filters
        if filters.get('blog_category'):
            blog_qs = blog_qs.filter(categories__slug=filters['blog_category'])
        
        if filters.get('date_from'):
            blog_qs = blog_qs.filter(first_published_at__gte=filters['date_from'])
        
        if filters.get('date_to'):
            blog_qs = blog_qs.filter(first_published_at__lte=filters['date_to'])
        
        # Apply full-text search on title and introduction
        # Note: Using Wagtail Page.title field and BlogPostPage.introduction field
        blog_qs = blog_qs.annotate(
            search=SearchVector('title', weight='A') + 
                   SearchVector('introduction', weight='B') + 
                   SearchVector('meta_description', weight='C'),
            rank=SearchRank(
                SearchVector('title', weight='A') + 
                SearchVector('introduction', weight='B') + 
                SearchVector('meta_description', weight='C'), 
                search_query
            )
        ).filter(search=search_query).order_by('-rank')
        
        # Convert blog posts to unified format
        for post in blog_qs.select_related('owner')[:20]:  # Limit per content type
            results.append({
                'type': 'blog_post',
                'id': str(post.id),
                'title': post.title,
                'content': post.introduction or (post.meta_description[:200] + '...' if post.meta_description else ''),
                'url': post.get_url(),
                'author': {
                    'username': post.owner.username if post.owner else 'Unknown',
                    'id': post.owner.id if post.owner else None,
                },
                'created_at': post.first_published_at.isoformat() if post.first_published_at else None,
                'metadata': {
                    'reading_time': getattr(post, 'reading_time', 'Unknown'),
                    'categories': [cat.name for cat in post.categories.all()],
                    'is_featured': getattr(post, 'is_featured', False),
                },
                'rank': float(getattr(post, 'rank', 0)),
            })
        
        return results, blog_qs.count()
    
    def _search_diseases(self, search_query, query_text: str, filters: Dict) -> Tuple[List[Dict], int]:
        """Search plant diseases."""
        results = []
        
        diseases_qs = PlantDiseaseDatabase.objects.all()
        
        # Apply filters
        if filters.get('disease_type'):
            diseases_qs = diseases_qs.filter(disease_type=filters['disease_type'])
        
        if filters.get('affected_plants'):
            diseases_qs = diseases_qs.filter(affected_plants__icontains=filters['affected_plants'])
        
        # Apply full-text search
        diseases_qs = diseases_qs.annotate(
            search=SearchVector('disease_name', weight='A') + 
                   SearchVector('description', weight='B') + 
                   SearchVector('symptoms', weight='B'),
            rank=SearchRank(
                SearchVector('disease_name', weight='A') + 
                SearchVector('description', weight='B') + 
                SearchVector('symptoms', weight='B'), 
                search_query
            )
        ).filter(search=search_query).order_by('-rank')
        
        # Convert diseases to unified format
        for disease in diseases_qs[:20]:  # Limit per content type
            results.append({
                'type': 'plant_disease',
                'id': str(disease.uuid),
                'title': disease.disease_name,
                'content': disease.description[:200] + '...' if disease.description else '',
                'url': f'/diseases/{disease.uuid}',
                'author': None,  # Diseases don't have authors
                'created_at': disease.created_at.isoformat() if hasattr(disease, 'created_at') else None,
                'metadata': {
                    'disease_type': disease.disease_type,
                    'severity': getattr(disease, 'severity', 'Unknown'),
                    'affected_plants': disease.affected_plants,
                    'symptoms': disease.symptoms[:100] + '...' if disease.symptoms else '',
                },
                'rank': float(getattr(disease, 'rank', 0)),
            })
        
        return results, diseases_qs.count()
    
    def _sort_results(self, results: List[Dict], sort_by: str) -> List[Dict]:
        """Sort search results by the specified criteria."""
        if sort_by == 'relevance':
            return sorted(results, key=lambda x: x.get('rank', 0), reverse=True)
        elif sort_by == 'date':
            return sorted(results, key=lambda x: x.get('created_at', ''), reverse=True)
        elif sort_by == 'popularity':
            # Sort by view count, replies, etc. (metadata-dependent)
            return sorted(results, key=lambda x: x.get('metadata', {}).get('views_count', 0), reverse=True)
        else:
            return results
    
    def _log_search_query(
        self,
        query: str,
        content_types: List[str],
        filters: Dict,
        user,
        session_key: str,
        results_count: int,
        response_time: int
    ):
        """Log the search query for analytics."""
        try:
            SearchQuery.objects.create(
                query_text=query,
                content_type=','.join(content_types) if len(content_types) > 1 else content_types[0],
                user=user,
                session_key=session_key,
                results_count=results_count,
                response_time_ms=response_time,
                filters_applied=filters
            )
        except Exception as e:
            logger.error(f"Failed to log search query: {str(e)}")
    
    def _empty_results(self, message: str = "No results found") -> Dict[str, Any]:
        """Return empty results structure."""
        return {
            'query': '',
            'results': [],
            'pagination': {
                'page': 1,
                'per_page': 20,
                'total_results': 0,
                'total_pages': 0,
                'has_next': False,
                'has_previous': False,
            },
            'result_counts': {},
            'total_count': 0,
            'response_time_ms': 0,
            'error': message,
            'applied_filters': {},
            'content_types_searched': [],
        }
    
    def get_search_suggestions(self, partial_query: str, limit: int = 10) -> List[Dict]:
        """Get search suggestions based on partial query."""
        if len(partial_query) < 2:
            return []
        
        suggestions = []
        
        # Get suggestions from recent searches
        recent_searches = SearchQuery.objects.filter(
            query_text__icontains=partial_query
        ).values_list('query_text', flat=True).distinct()[:limit//2]
        
        for query in recent_searches:
            suggestions.append({
                'text': query,
                'type': 'recent_search',
                'score': 1.0
            })
        
        # Get suggestions from plant names
        plant_names = PlantSpecies.objects.filter(
            models.Q(scientific_name__icontains=partial_query) |
            models.Q(common_names__icontains=partial_query)
        ).values_list('scientific_name', flat=True)[:limit//2]
        
        for name in plant_names:
            suggestions.append({
                'text': name,
                'type': 'plant_name',
                'score': 0.8
            })
        
        # Sort by score and limit
        suggestions.sort(key=lambda x: x['score'], reverse=True)
        return suggestions[:limit]