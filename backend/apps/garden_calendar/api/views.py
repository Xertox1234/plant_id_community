"""
Garden Calendar API Views

API endpoints for community events, seasonal templates, and weather alerts.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
# GIS imports removed - using simpler location filtering
import math

from ..models import CommunityEvent, EventAttendee, SeasonalTemplate, WeatherAlert
from .serializers import (
    CommunityEventListSerializer, CommunityEventDetailSerializer,
    CommunityEventCreateUpdateSerializer, EventAttendeeSerializer,
    SeasonalTemplateSerializer, WeatherAlertSerializer, RSVPSerializer
)


class CommunityEventViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing community events.
    
    Provides CRUD operations plus RSVP functionality and location-based filtering.
    """
    
    queryset = CommunityEvent.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['event_type', 'privacy_level', 'hardiness_zone', 'city', 'weather_dependent']
    search_fields = ['title', 'description', 'location_name']
    ordering_fields = ['start_datetime', 'created_at', 'title']
    ordering = ['start_datetime']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return CommunityEventListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return CommunityEventCreateUpdateSerializer
        else:
            return CommunityEventDetailSerializer
    
    def get_queryset(self):
        """
        Filter events based on user permissions and location preferences.
        """
        queryset = CommunityEvent.objects.select_related('organizer').prefetch_related('attendees')
        user = self.request.user
        
        # Apply privacy filtering
        if not user.is_authenticated:
            queryset = queryset.filter(privacy_level='public')
        else:
            # Build privacy filter based on user's location and relationships
            privacy_filter = Q(privacy_level='public')
            
            if hasattr(user, 'hardiness_zone') and user.hardiness_zone:
                privacy_filter |= Q(privacy_level='zone', hardiness_zone=user.hardiness_zone)
            
            if hasattr(user, 'location') and user.location:
                privacy_filter |= Q(privacy_level='local', city__icontains=user.location)
            
            # Friends filter - events where user follows organizer
            privacy_filter |= Q(privacy_level='friends', organizer__in=user.following.all())
            
            # Own events
            privacy_filter |= Q(organizer=user)
            
            queryset = queryset.filter(privacy_filter)
        
        # Apply additional filters from query parameters
        upcoming_only = self.request.query_params.get('upcoming_only', 'false').lower() == 'true'
        if upcoming_only:
            queryset = queryset.filter(start_datetime__gte=timezone.now())
        
        # Location-based filtering
        near_me = self.request.query_params.get('near_me', 'false').lower() == 'true'
        if near_me and user.is_authenticated:
            if hasattr(user, 'latitude') and hasattr(user, 'longitude') and user.latitude and user.longitude:
                # Simple distance filtering using haversine formula
                distance_miles = int(self.request.query_params.get('distance_miles', 50))
                
                # Filter events with coordinates within approximate distance
                lat_diff = distance_miles / 69.0  # Approximate miles per degree latitude
                lon_diff = distance_miles / (69.0 * math.cos(math.radians(float(user.latitude))))
                
                queryset = queryset.filter(
                    latitude__isnull=False,
                    longitude__isnull=False,
                    latitude__gte=user.latitude - lat_diff,
                    latitude__lte=user.latitude + lat_diff,
                    longitude__gte=user.longitude - lon_diff,
                    longitude__lte=user.longitude + lon_diff
                )
            elif hasattr(user, 'hardiness_zone') and user.hardiness_zone:
                # Fallback to zone-based filtering
                queryset = queryset.filter(hardiness_zone=user.hardiness_zone)
        return queryset.distinct()
    
    def perform_create(self, serializer):
        """Set the organizer to the current user when creating events."""
        serializer.save(organizer=self.request.user)
    
    def perform_update(self, serializer):
        """Only allow organizers to update their events."""
        event = self.get_object()
        if event.organizer != self.request.user:
            self.permission_denied(self.request, message="Only the organizer can modify this event.")
        serializer.save()
    
    def perform_destroy(self, instance):
        """Only allow organizers to delete their events."""
        if instance.organizer != self.request.user:
            self.permission_denied(self.request, message="Only the organizer can delete this event.")
        super().perform_destroy(instance)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def rsvp(self, request, pk=None):
        """
        RSVP to an event.
        """
        event = self.get_object()
        serializer = RSVPSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user can RSVP
        if event.organizer == request.user:
            return Response(
                {"error": "You cannot RSVP to your own event."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if event.is_past:
            return Response(
                {"error": "Cannot RSVP to past events."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check capacity
        if event.max_attendees and event.spots_remaining == 0:
            # Unless user is changing existing RSVP from 'going' to something else
            try:
                existing_rsvp = event.attendees.get(user=request.user)
                if existing_rsvp.status == 'going' and serializer.validated_data['status'] == 'going':
                    return Response(
                        {"error": "Event is at full capacity."}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except EventAttendee.DoesNotExist:
                return Response(
                    {"error": "Event is at full capacity."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create or update RSVP
        attendee, created = EventAttendee.objects.update_or_create(
            event=event,
            user=request.user,
            defaults={
                'status': serializer.validated_data['status'],
                'notes': serializer.validated_data.get('notes', '')
            }
        )
        
        return Response({
            'message': 'RSVP updated successfully.',
            'status': attendee.status,
            'attendee_count': event.attendee_count,
            'spots_remaining': event.spots_remaining
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def calendar_feed(self, request):
        """
        Get events formatted for calendar display.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Date range filtering for calendar view
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(start_datetime__gte=start_date)
        if end_date:
            queryset = queryset.filter(start_datetime__lte=end_date)
        
        # Limit results to prevent excessive data transfer
        queryset = queryset[:500]
        
        serializer = CommunityEventListSerializer(queryset, many=True, context={'request': request})
        
        # Transform to calendar event format
        calendar_events = []
        for event_data in serializer.data:
            calendar_events.append({
                'id': f"community_{event_data['uuid']}",
                'title': event_data['title'],
                'start': event_data['start_datetime'],
                'end': event_data['end_datetime'] or event_data['start_datetime'],
                'type': 'community_event',
                'event_type': event_data['event_type'],
                'allDay': event_data['is_all_day'],
                'color': self._get_event_color(event_data['event_type']),
                'extendedProps': {
                    'description': event_data['description'][:100] + '...' if len(event_data['description']) > 100 else event_data['description'],
                    'location': event_data['location_name'],
                    'organizer': event_data['organizer']['username'],
                    'attendee_count': event_data['attendee_count'],
                    'user_rsvp_status': event_data['user_rsvp_status'],
                    'requires_rsvp': event_data['requires_rsvp'],
                    'spots_remaining': event_data['spots_remaining']
                }
            })
        
        return Response({
            'events': calendar_events,
            'total_events': len(calendar_events)
        })
    
    def _get_event_color(self, event_type):
        """Get color code for different event types."""
        colors = {
            'plant_swap': '#10B981',      # Green
            'workshop': '#3B82F6',       # Blue
            'garden_tour': '#8B5CF6',    # Purple
            'vendor_sale': '#F59E0B',    # Amber
            'bulk_order': '#EF4444',     # Red
            'meetup': '#6B7280',         # Gray
            'maintenance': '#059669',    # Emerald
            'harvest': '#D97706',        # Orange
            'other': '#6B7280',          # Gray
        }
        return colors.get(event_type, '#6B7280')


class SeasonalTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for seasonal templates (read-only for regular users).
    """
    
    queryset = SeasonalTemplate.objects.filter(is_active=True)
    serializer_class = SeasonalTemplateSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['season', 'task_type', 'priority']
    ordering_fields = ['season', 'start_month', 'priority', 'created_at']
    ordering = ['season', 'start_month', 'day_of_month']
    
    def get_queryset(self):
        """
        Filter templates based on user's location/zone if available.
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # If user is authenticated and has a hardiness zone, filter by zone
        if user.is_authenticated and hasattr(user, 'hardiness_zone') and user.hardiness_zone:
            queryset = queryset.filter(
                Q(hardiness_zones__contains=[user.hardiness_zone]) |
                Q(hardiness_zones=[])  # Include universal templates
            )
        
        # Filter by specific zones from query params
        zones = self.request.query_params.getlist('zone')
        if zones:
            queryset = queryset.filter(hardiness_zones__overlap=zones)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def current_season(self, request):
        """
        Get templates for the current season.
        """
        import datetime
        current_month = timezone.now().month
        
        # Determine current season based on month
        if current_month in [12, 1, 2]:
            current_season = 'winter'
        elif current_month in [3, 4, 5]:
            current_season = 'spring'
        elif current_month in [6, 7, 8]:
            current_season = 'summer'
        else:
            current_season = 'fall'
        
        queryset = self.get_queryset().filter(season=current_season)
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'current_season': current_season,
            'templates': serializer.data,
            'month': current_month
        })


class WeatherAlertViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for weather alerts (read-only).
    """
    
    queryset = WeatherAlert.objects.filter(is_active=True)
    serializer_class = WeatherAlertSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['alert_type', 'severity', 'zip_code', 'city', 'hardiness_zone']
    ordering_fields = ['severity', 'start_datetime', 'created_at']
    ordering = ['-severity', 'start_datetime']
    
    def get_queryset(self):
        """
        Filter alerts based on user's location if available.
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # If user is authenticated, filter by their location
        if user.is_authenticated:
            location_filter = Q()
            
            if hasattr(user, 'zip_code') and user.zip_code:
                location_filter |= Q(zip_code=user.zip_code)
            
            if hasattr(user, 'location') and user.location:
                location_filter |= Q(city__icontains=user.location)
            
            if hasattr(user, 'hardiness_zone') and user.hardiness_zone:
                location_filter |= Q(hardiness_zone=user.hardiness_zone)
            
            if location_filter:
                queryset = queryset.filter(location_filter)
        
        # Show only current alerts by default
        current_only = self.request.query_params.get('current_only', 'true').lower() == 'true'
        if current_only:
            now = timezone.now()
            queryset = queryset.filter(
                start_datetime__lte=now,
                expires_at__gte=now
            )
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def active_alerts(self, request):
        """
        Get currently active alerts for the user's location.
        """
        queryset = self.get_queryset().filter(is_active=True)
        now = timezone.now()
        
        # Filter to currently active alerts
        active_alerts = queryset.filter(
            start_datetime__lte=now,
            expires_at__gte=now
        ).filter(
            Q(end_datetime__isnull=True) | Q(end_datetime__gte=now)
        )
        
        serializer = self.get_serializer(active_alerts, many=True)
        
        return Response({
            'active_alerts': serializer.data,
            'alert_count': active_alerts.count(),
            'high_severity_count': active_alerts.filter(severity__in=['high', 'critical']).count()
        })