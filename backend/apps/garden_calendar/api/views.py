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

from ..models import (
    CommunityEvent, EventAttendee, SeasonalTemplate, WeatherAlert,
    GardenBed, Plant, PlantImage, CareTask, CareLog, Harvest, GrowingZone
)
from .serializers import (
    CommunityEventListSerializer, CommunityEventDetailSerializer,
    CommunityEventCreateUpdateSerializer, EventAttendeeSerializer,
    SeasonalTemplateSerializer, WeatherAlertSerializer, RSVPSerializer,
    GardenBedListSerializer, GardenBedDetailSerializer, GardenBedCreateUpdateSerializer,
    PlantListSerializer, PlantDetailSerializer, PlantCreateUpdateSerializer,
    PlantImageSerializer, CareTaskListSerializer, CareTaskDetailSerializer,
    CareTaskCreateUpdateSerializer, CareLogSerializer, HarvestSerializer,
    GrowingZoneSerializer
)
from ..permissions import IsGardenOwner, IsPlantOwner, IsCareTaskOwner


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


# ============================================================================
# Garden Planner ViewSets
# ============================================================================


class GardenBedViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing garden beds.

    Provides CRUD operations for user garden beds with query optimization.

    Performance:
        - select_related('owner')
        - prefetch_related('plants') for detail view
        - Annotates plant_count for list view
    """

    queryset = GardenBed.objects.all()
    permission_classes = [IsGardenOwner]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['bed_type', 'sun_exposure', 'soil_type', 'is_active']
    search_fields = ['name', 'notes']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['-created_at']
    lookup_field = 'uuid'

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return GardenBedListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return GardenBedCreateUpdateSerializer
        else:
            return GardenBedDetailSerializer

    def get_queryset(self):
        """
        Filter garden beds to user's own beds with query optimization.

        Performance optimizations:
        - select_related('owner')
        - Annotates plant_count for list view
        - Prefetches plants for detail view
        """
        qs = super().get_queryset()

        # Filter to user's own garden beds
        if self.request.user.is_authenticated:
            qs = qs.filter(owner=self.request.user)

        # Always select related for performance
        qs = qs.select_related('owner')

        # Conditional optimization based on action
        if self.action == 'retrieve':
            # Prefetch plants for detail view
            from django.db.models import Prefetch
            qs = qs.prefetch_related(
                Prefetch(
                    'plants',
                    queryset=Plant.objects.filter(is_active=True).select_related('plant_species')
                )
            )

        return qs

    def perform_create(self, serializer):
        """Set the owner to the current user when creating garden beds."""
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['get'])
    def analytics(self, request, uuid=None):
        """
        Get analytics for a garden bed.

        Returns:
        - Plant count by health status
        - Bed utilization rate
        - Care task statistics
        """
        garden_bed = self.get_object()

        # Health status breakdown
        health_stats = {}
        for plant in garden_bed.plants.filter(is_active=True):
            health_stats[plant.health_status] = health_stats.get(plant.health_status, 0) + 1

        # Care task statistics
        from django.db.models import Q
        total_tasks = CareTask.objects.filter(
            plant__garden_bed=garden_bed,
            plant__is_active=True
        ).count()

        overdue_tasks = CareTask.objects.filter(
            plant__garden_bed=garden_bed,
            plant__is_active=True,
            completed=False,
            skipped=False,
            scheduled_date__lt=timezone.now()
        ).count()

        return Response({
            'uuid': str(garden_bed.uuid),
            'name': garden_bed.name,
            'plant_count': garden_bed.plant_count,
            'utilization_rate': garden_bed.utilization_rate,
            'area_square_feet': garden_bed.area_square_feet,
            'health_status_breakdown': health_stats,
            'care_tasks': {
                'total': total_tasks,
                'overdue': overdue_tasks,
                'completion_rate': round((total_tasks - overdue_tasks) / total_tasks * 100, 1) if total_tasks > 0 else 0
            }
        })


class PlantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing plants.

    Provides CRUD operations for plants with filtering and image management.

    Performance:
        - select_related('garden_bed', 'plant_species')
        - prefetch_related('images', 'care_tasks') for detail view
    """

    queryset = Plant.objects.all()
    permission_classes = [IsPlantOwner]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['garden_bed__uuid', 'health_status', 'growth_stage', 'is_active']
    search_fields = ['common_name', 'variety', 'notes']
    ordering_fields = ['common_name', 'planted_date', 'created_at']
    ordering = ['-planted_date']
    lookup_field = 'uuid'

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return PlantListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return PlantCreateUpdateSerializer
        else:
            return PlantDetailSerializer

    def get_queryset(self):
        """
        Filter plants to user's own plants with query optimization.

        Performance optimizations:
        - select_related('garden_bed__owner', 'plant_species')
        - Prefetches images and tasks for detail view
        """
        qs = super().get_queryset()

        # Filter to user's own plants
        if self.request.user.is_authenticated:
            qs = qs.filter(garden_bed__owner=self.request.user)

        # Always select related for performance
        qs = qs.select_related('garden_bed', 'garden_bed__owner', 'plant_species')

        # Conditional optimization based on action
        if self.action == 'retrieve':
            # Prefetch related data for detail view
            from django.db.models import Prefetch
            qs = qs.prefetch_related(
                'images',
                Prefetch(
                    'care_tasks',
                    queryset=CareTask.objects.filter(
                        completed=False,
                        skipped=False
                    ).order_by('scheduled_date')
                ),
                Prefetch(
                    'care_logs',
                    queryset=CareLog.objects.order_by('-created_at')[:5]
                )
            )

        return qs

    @action(detail=True, methods=['post'])
    def upload_image(self, request, uuid=None):
        """
        Upload an image for a plant.

        Request body:
        - image: Image file
        - caption: Optional caption
        - is_primary: Boolean (default: False)
        """
        plant = self.get_object()

        # Check image count limit
        from ..constants import MAX_IMAGES_PER_PLANT
        if plant.images.count() >= MAX_IMAGES_PER_PLANT:
            return Response(
                {"error": f"Maximum {MAX_IMAGES_PER_PLANT} images allowed per plant."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = PlantImageSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            # If setting as primary, unset other primary images
            if request.data.get('is_primary', False):
                plant.images.filter(is_primary=True).update(is_primary=False)

            serializer.save(plant=plant)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def care_schedule(self, request, uuid=None):
        """
        Get upcoming care schedule for a plant.

        Returns next 30 days of care tasks.
        """
        plant = self.get_object()

        # Get tasks for next 30 days
        from datetime import timedelta
        end_date = timezone.now() + timedelta(days=30)

        upcoming_tasks = plant.care_tasks.filter(
            completed=False,
            skipped=False,
            scheduled_date__lte=end_date
        ).order_by('scheduled_date')

        serializer = CareTaskListSerializer(upcoming_tasks, many=True, context={'request': request})

        return Response({
            'plant_uuid': str(plant.uuid),
            'plant_name': plant.common_name,
            'tasks': serializer.data,
            'task_count': upcoming_tasks.count()
        })


class CareTaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing care tasks.

    Provides CRUD operations plus complete/skip actions for task management.

    Performance:
        - select_related('plant', 'plant__garden_bed')
    """

    queryset = CareTask.objects.all()
    permission_classes = [IsCareTaskOwner]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['plant__uuid', 'task_type', 'priority', 'completed', 'skipped', 'is_recurring']
    ordering_fields = ['scheduled_date', 'priority', 'created_at']
    ordering = ['scheduled_date']
    lookup_field = 'uuid'

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return CareTaskListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return CareTaskCreateUpdateSerializer
        else:
            return CareTaskDetailSerializer

    def get_queryset(self):
        """
        Filter care tasks to user's own tasks with query optimization.

        Performance optimizations:
        - select_related('plant__garden_bed__owner')
        """
        qs = super().get_queryset()

        # Filter to user's own tasks
        if self.request.user.is_authenticated:
            qs = qs.filter(plant__garden_bed__owner=self.request.user)

        # Always select related for performance
        qs = qs.select_related(
            'plant',
            'plant__garden_bed',
            'plant__garden_bed__owner',
            'completed_by'
        )

        # Filter by overdue status if requested
        overdue_only = self.request.query_params.get('overdue_only', 'false').lower() == 'true'
        if overdue_only:
            qs = qs.filter(
                completed=False,
                skipped=False,
                scheduled_date__lt=timezone.now()
            )

        # Filter by date range
        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')

        if from_date:
            qs = qs.filter(scheduled_date__gte=from_date)
        if to_date:
            qs = qs.filter(scheduled_date__lte=to_date)

        return qs

    def perform_create(self, serializer):
        """Set created_by to current user."""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def complete(self, request, uuid=None):
        """
        Mark a care task as completed.

        For recurring tasks, creates the next occurrence automatically.
        """
        task = self.get_object()

        if task.completed:
            return Response(
                {"error": "Task is already completed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if task.skipped:
            return Response(
                {"error": "Cannot complete a skipped task. Create a new task instead."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Use model method to handle completion and recurrence
        task.mark_complete(request.user)

        return Response({
            'message': 'Task completed successfully.',
            'uuid': str(task.uuid),
            'completed_at': task.completed_at,
            'next_occurrence_created': task.is_recurring
        })

    @action(detail=True, methods=['post'])
    def skip(self, request, uuid=None):
        """
        Skip a care task.

        For recurring tasks, creates the next occurrence automatically.
        """
        task = self.get_object()

        if task.completed:
            return Response(
                {"error": "Cannot skip a completed task."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if task.skipped:
            return Response(
                {"error": "Task is already skipped."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Use model method to handle skipping and recurrence
        task.mark_skip(request.user, reason=request.data.get('reason', ''))

        return Response({
            'message': 'Task skipped successfully.',
            'uuid': str(task.uuid),
            'next_occurrence_created': task.is_recurring
        })

    @action(detail=False, methods=['get'])
    def calendar_feed(self, request):
        """
        Get care tasks formatted for calendar display.

        Returns tasks in calendar event format.
        """
        queryset = self.filter_queryset(self.get_queryset())

        # Date range filtering for calendar view
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if start_date:
            queryset = queryset.filter(scheduled_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(scheduled_date__lte=end_date)

        # Limit results
        queryset = queryset[:500]

        serializer = CareTaskListSerializer(queryset, many=True, context={'request': request})

        # Transform to calendar event format
        calendar_events = []
        for task_data in serializer.data:
            calendar_events.append({
                'id': f"task_{task_data['uuid']}",
                'title': f"{task_data['task_type_display']} - {task_data['plant_name']}",
                'start': task_data['scheduled_date'],
                'type': 'care_task',
                'allDay': False,
                'color': self._get_task_color(task_data),
                'extendedProps': {
                    'plant_name': task_data['plant_name'],
                    'task_type': task_data['task_type'],
                    'priority': task_data['priority'],
                    'is_recurring': task_data['is_recurring'],
                    'is_overdue': task_data['is_overdue'],
                    'completed': task_data['completed'],
                    'skipped': task_data['skipped']
                }
            })

        return Response({
            'events': calendar_events,
            'total_tasks': len(calendar_events)
        })

    def _get_task_color(self, task_data):
        """Get color code based on task status and priority."""
        if task_data['completed']:
            return '#10B981'  # Green
        elif task_data['skipped']:
            return '#6B7280'  # Gray
        elif task_data['is_overdue']:
            return '#EF4444'  # Red
        elif task_data['priority'] == 'high':
            return '#F59E0B'  # Amber
        else:
            return '#3B82F6'  # Blue


class CareLogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing care logs.

    Provides CRUD operations for logging plant care activities.
    """

    queryset = CareLog.objects.all()
    permission_classes = [IsPlantOwner]  # Uses same permission check via plant
    serializer_class = CareLogSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['plant__uuid', 'activity_type']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    lookup_field = 'uuid'

    def get_queryset(self):
        """Filter care logs to user's own plants."""
        qs = super().get_queryset()

        # Filter to user's own logs
        if self.request.user.is_authenticated:
            qs = qs.filter(plant__garden_bed__owner=self.request.user)

        # Select related for performance
        qs = qs.select_related(
            'plant',
            'plant__garden_bed',
            'logged_by'
        )

        return qs

    def perform_create(self, serializer):
        """Set logged_by to current user."""
        serializer.save(logged_by=self.request.user)


class HarvestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing harvest records.

    Provides CRUD operations for tracking harvests.
    """

    queryset = Harvest.objects.all()
    permission_classes = [IsPlantOwner]  # Uses same permission check via plant
    serializer_class = HarvestSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['plant__uuid', 'harvest_date']
    ordering_fields = ['harvest_date', 'created_at']
    ordering = ['-harvest_date']
    lookup_field = 'uuid'

    def get_queryset(self):
        """Filter harvests to user's own plants."""
        qs = super().get_queryset()

        # Filter to user's own harvests
        if self.request.user.is_authenticated:
            qs = qs.filter(plant__garden_bed__owner=self.request.user)

        # Select related for performance
        qs = qs.select_related(
            'plant',
            'plant__garden_bed'
        )

        return qs

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get harvest statistics for the user.

        Returns:
        - Total harvests
        - Total quantity by unit
        - Average quality/taste ratings
        - Harvests by plant
        """
        queryset = self.get_queryset()

        # Total harvests
        total_harvests = queryset.count()

        # Quantity by unit
        from django.db.models import Sum
        quantities = {}
        for unit in ['lbs', 'oz', 'count', 'bunches']:
            total = queryset.filter(unit=unit).aggregate(total=Sum('quantity'))['total'] or 0
            if total > 0:
                quantities[unit] = total

        # Average ratings
        from django.db.models import Avg
        avg_quality = queryset.aggregate(avg=Avg('quality_rating'))['avg']
        avg_taste = queryset.aggregate(avg=Avg('taste_rating'))['avg']

        # Harvests by plant
        from django.db.models import Count
        by_plant = queryset.values(
            'plant__uuid',
            'plant__common_name'
        ).annotate(
            harvest_count=Count('uuid'),
            total_quantity=Sum('quantity')
        ).order_by('-harvest_count')[:10]

        return Response({
            'total_harvests': total_harvests,
            'total_quantity_by_unit': quantities,
            'average_quality_rating': round(avg_quality, 1) if avg_quality else None,
            'average_taste_rating': round(avg_taste, 1) if avg_taste else None,
            'top_producers': list(by_plant)
        })


class PlantImageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing plant images.

    Provides CRUD operations for plant images with primary image management.
    """

    queryset = PlantImage.objects.all()
    permission_classes = [IsPlantOwner]  # Uses same permission check via plant
    serializer_class = PlantImageSerializer
    lookup_field = 'uuid'

    def get_queryset(self):
        """Filter images to user's own plants."""
        qs = super().get_queryset()

        # Filter to user's own plant images
        if self.request.user.is_authenticated:
            qs = qs.filter(plant__garden_bed__owner=self.request.user)

        # Select related for performance
        qs = qs.select_related('plant', 'plant__garden_bed')

        # Filter by plant UUID if provided
        plant_uuid = self.request.query_params.get('plant__uuid')
        if plant_uuid:
            qs = qs.filter(plant__uuid=plant_uuid)

        return qs.order_by('-is_primary', '-created_at')

    def perform_update(self, serializer):
        """
        Handle primary image logic on update.

        If setting is_primary=True, unset other images for the same plant.
        """
        if serializer.validated_data.get('is_primary', False):
            plant = serializer.instance.plant
            plant.images.exclude(uuid=serializer.instance.uuid).update(is_primary=False)

        serializer.save()


class GrowingZoneViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for growing zone reference data (read-only).

    Provides USDA hardiness zone information.
    """

    queryset = GrowingZone.objects.all()
    serializer_class = GrowingZoneSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [OrderingFilter]
    ordering_fields = ['zone_code', 'temp_min']
    ordering = ['zone_code']

    @action(detail=False, methods=['get'])
    def lookup(self, request):
        """
        Lookup zone by code.

        Query params:
        - zone_code: USDA zone code (e.g., '7a', '9b')
        """
        zone_code = request.query_params.get('zone_code')
        if not zone_code:
            return Response(
                {"error": "zone_code parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            zone = GrowingZone.objects.get(zone_code=zone_code.lower())
            serializer = self.get_serializer(zone)
            return Response(serializer.data)
        except GrowingZone.DoesNotExist:
            return Response(
                {"error": f"Zone '{zone_code}' not found."},
                status=status.HTTP_404_NOT_FOUND
            )