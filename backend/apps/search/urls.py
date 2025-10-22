"""
URL configuration for the search app.
"""

from django.urls import path
from . import views

app_name = 'search'

urlpatterns = [
    # Main search endpoints
    path('unified/', views.UnifiedSearchView.as_view(), name='unified_search'),
    path('suggestions/', views.SearchSuggestionsView.as_view(), name='search_suggestions'),
    path('filters/', views.SearchFiltersView.as_view(), name='search_filters'),
    
    # User saved searches
    path('saved/', views.SavedSearchListCreateView.as_view(), name='saved_searches'),
    path('saved/<int:pk>/', views.SavedSearchDetailView.as_view(), name='saved_search_detail'),
    
    # User preferences
    path('preferences/', views.UserSearchPreferencesView.as_view(), name='search_preferences'),
    
    # Analytics and tracking
    path('analytics/', views.SearchAnalyticsView.as_view(), name='search_analytics'),
    path('track-click/', views.track_search_click, name='track_search_click'),
]