"""
Garden Planner ViewSets

DRF ViewSets for garden planning API with:
- User-scoped data filtering (users see only their own gardens)
- Optimized queries with select_related/prefetch_related
- Rate limiting for resource-intensive operations
- Custom actions for special functionality
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Prefetch, Q
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator

from .models import (
    Garden,
    GardenPlant,
    CareReminder,
    Task,
    PestIssue,
    PestImage,
    JournalEntry,
    JournalImage,
    PlantCareLibrary
)
from .serializers import (
    GardenSerializer,
    GardenListSerializer,
    GardenPlantSerializer,
    CareReminderSerializer,
    TaskSerializer,
    PestIssueSerializer,
    PestImageSerializer,
    JournalEntrySerializer,
    JournalImageSerializer,
    PlantCareLibrarySerializer
)
from .constants import (
    RATE_LIMIT_GARDEN_CREATE,
    MAX_PEST_IMAGES_PER_ISSUE,
    MAX_JOURNAL_IMAGES_PER_ENTRY
)


class PlantCareLibraryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Plant care reference library (read-only).

    Provides care instructions, compatibility data, and frequency defaults.
    Staff can edit via Django admin.
    """
    queryset = PlantCareLibrary.objects.all()
    serializer_class = PlantCareLibrarySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['sunlight', 'water_needs', 'family']
    search_fields = ['scientific_name', 'common_names', 'family']
    ordering_fields = ['scientific_name', 'created_at']
    ordering = ['scientific_name']


class GardenViewSet(viewsets.ModelViewSet):
    """
    Garden CRUD operations with user-scoped filtering.

    Users can only view/edit their own gardens.
    Public gardens visible in separate 'featured' action.
    """
    permission_classes = [IsAuthenticated]
    filterset_fields = ['visibility', 'climate_zone']
    search_fields = ['name', 'description', 'climate_zone']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['-updated_at']

    def get_queryset(self):
        """Return user's gardens with optimized queries."""
        return Garden.objects.filter(
            user=self.request.user
        ).prefetch_related(
            Prefetch(
                'plants',
                queryset=GardenPlant.objects.select_related('plant_species')
            ),
            'tasks',
            'journal_entries'
        )

    def get_serializer_class(self):
        """Use simplified serializer for list view."""
        if self.action == 'list':
            return GardenListSerializer
        return GardenSerializer

    @method_decorator(ratelimit(key='user', rate=RATE_LIMIT_GARDEN_CREATE, method='POST'))
    def create(self, request, *args, **kwargs):
        """Create garden with rate limiting."""
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Set user on creation."""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['GET'])
    def featured(self, request):
        """
        List featured public gardens for community showcase.

        Returns staff-curated gardens for inspiration.
        """
        gardens = Garden.objects.filter(
            visibility='public',
            featured=True
        ).select_related('user').prefetch_related(
            Prefetch(
                'plants',
                queryset=GardenPlant.objects.select_related('plant_species')
            )
        ).order_by('-updated_at')

        page = self.paginate_queryset(gardens)
        if page is not None:
            serializer = GardenSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = GardenSerializer(gardens, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['GET'])
    def public(self, request):
        """
        List all public gardens for community browsing.

        Returns non-featured public gardens.
        """
        gardens = Garden.objects.filter(
            visibility='public'
        ).select_related('user').prefetch_related(
            Prefetch(
                'plants',
                queryset=GardenPlant.objects.select_related('plant_species')
            )
        ).order_by('-updated_at')

        page = self.paginate_queryset(gardens)
        if page is not None:
            serializer = GardenListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = GardenListSerializer(gardens, many=True)
        return Response(serializer.data)


class GardenPlantViewSet(viewsets.ModelViewSet):
    """
    Garden plant CRUD operations.

    Users can only manage plants in their own gardens.
    """
    serializer_class = GardenPlantSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['garden', 'health_status']
    search_fields = ['common_name', 'scientific_name']
    ordering_fields = ['common_name', 'planted_date', 'created_at']
    ordering = ['-planted_date']

    def get_queryset(self):
        """Return plants from user's gardens with optimized queries."""
        return GardenPlant.objects.filter(
            garden__user=self.request.user
        ).select_related(
            'garden',
            'plant_species'
        ).prefetch_related(
            'reminders',
            'pest_issues__images',
            'journal_entries__images'
        )


class CareReminderViewSet(viewsets.ModelViewSet):
    """
    Care reminder CRUD operations.

    Users can only view/edit reminders for their own garden plants.
    """
    serializer_class = CareReminderSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['garden_plant', 'reminder_type', 'completed', 'recurring']
    search_fields = ['notes']
    ordering_fields = ['scheduled_date', 'created_at']
    ordering = ['scheduled_date']

    def get_queryset(self):
        """Return user's reminders with optimized queries."""
        return CareReminder.objects.filter(
            user=self.request.user
        ).select_related(
            'garden_plant__garden'
        )

    def perform_create(self, serializer):
        """Set user on creation."""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['GET'])
    def upcoming(self, request):
        """
        Get upcoming reminders (next 7 days).

        Returns incomplete reminders scheduled in the near future.
        """
        from datetime import datetime, timedelta

        end_date = datetime.now() + timedelta(days=7)
        reminders = self.get_queryset().filter(
            completed=False,
            scheduled_date__lte=end_date
        ).order_by('scheduled_date')

        page = self.paginate_queryset(reminders)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(reminders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['POST'])
    def complete(self, request, pk=None):
        """
        Mark reminder as completed.

        For recurring reminders, creates next instance based on interval.
        """
        from datetime import datetime, timedelta

        reminder = self.get_object()
        reminder.completed = True
        reminder.completed_at = datetime.now()
        reminder.save()

        # If recurring, create next reminder
        if reminder.recurring and reminder.interval_days:
            next_date = reminder.scheduled_date + timedelta(days=reminder.interval_days)
            CareReminder.objects.create(
                user=reminder.user,
                garden_plant=reminder.garden_plant,
                reminder_type=reminder.reminder_type,
                custom_type_name=reminder.custom_type_name,
                scheduled_date=next_date,
                recurring=True,
                interval_days=reminder.interval_days,
                notes=reminder.notes
            )

        serializer = self.get_serializer(reminder)
        return Response(serializer.data)

    @action(detail=True, methods=['POST'])
    def skip(self, request, pk=None):
        """
        Skip reminder with optional reason (e.g., weather-based).

        For recurring reminders, creates next instance.
        """
        from datetime import datetime, timedelta

        reminder = self.get_object()
        skip_reason = request.data.get('reason', '')

        reminder.skipped = True
        reminder.skip_reason = skip_reason
        reminder.save()

        # If recurring, create next reminder
        if reminder.recurring and reminder.interval_days:
            next_date = reminder.scheduled_date + timedelta(days=reminder.interval_days)
            CareReminder.objects.create(
                user=reminder.user,
                garden_plant=reminder.garden_plant,
                reminder_type=reminder.reminder_type,
                custom_type_name=reminder.custom_type_name,
                scheduled_date=next_date,
                recurring=True,
                interval_days=reminder.interval_days,
                notes=reminder.notes
            )

        serializer = self.get_serializer(reminder)
        return Response(serializer.data)


class TaskViewSet(viewsets.ModelViewSet):
    """
    Seasonal gardening task CRUD operations.

    Users can manage garden-specific or general tasks.
    """
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['garden', 'category', 'season', 'priority', 'completed']
    search_fields = ['title', 'description']
    ordering_fields = ['priority', 'due_date', 'created_at']
    ordering = ['-priority', 'due_date']

    def get_queryset(self):
        """Return user's tasks with optimized queries."""
        return Task.objects.filter(
            user=self.request.user
        ).select_related('garden')

    def perform_create(self, serializer):
        """Set user on creation."""
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['POST'])
    def complete(self, request, pk=None):
        """Mark task as completed."""
        from datetime import datetime

        task = self.get_object()
        task.completed = True
        task.completed_at = datetime.now()
        task.save()

        serializer = self.get_serializer(task)
        return Response(serializer.data)


class PestIssueViewSet(viewsets.ModelViewSet):
    """
    Pest/disease issue CRUD operations.

    Users can track pest problems on their garden plants.
    """
    serializer_class = PestIssueSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['garden_plant', 'severity', 'resolved']
    search_fields = ['pest_type', 'description']
    ordering_fields = ['identified_date', 'severity']
    ordering = ['-identified_date']

    def get_queryset(self):
        """Return pest issues from user's gardens with images."""
        return PestIssue.objects.filter(
            user=self.request.user
        ).select_related(
            'garden_plant__garden'
        ).prefetch_related('images')

    def perform_create(self, serializer):
        """Set user on creation."""
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['POST'])
    def upload_image(self, request, pk=None):
        """
        Upload image for pest issue (max 6 images).

        Validates file size and type.
        """
        pest_issue = self.get_object()

        # Check image count limit
        if pest_issue.images.count() >= MAX_PEST_IMAGES_PER_ISSUE:
            return Response(
                {'error': f'Maximum {MAX_PEST_IMAGES_PER_ISSUE} images allowed per issue'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = PestImageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(pest_issue=pest_issue)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['POST'])
    def resolve(self, request, pk=None):
        """Mark pest issue as resolved."""
        from datetime import date

        pest_issue = self.get_object()
        pest_issue.resolved = True
        pest_issue.resolved_date = date.today()
        pest_issue.save()

        serializer = self.get_serializer(pest_issue)
        return Response(serializer.data)


class JournalEntryViewSet(viewsets.ModelViewSet):
    """
    Garden journal entry CRUD operations.

    Users can document observations with photos and weather data.
    """
    serializer_class = JournalEntrySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['garden', 'garden_plant', 'date']
    search_fields = ['title', 'content', 'tags']
    ordering_fields = ['date', 'created_at']
    ordering = ['-date']

    def get_queryset(self):
        """Return user's journal entries with images."""
        return JournalEntry.objects.filter(
            user=self.request.user
        ).select_related(
            'garden',
            'garden_plant'
        ).prefetch_related('images')

    def perform_create(self, serializer):
        """Set user on creation."""
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['POST'])
    def upload_image(self, request, pk=None):
        """
        Upload image for journal entry (max 10 images).

        Validates file size and type.
        """
        journal_entry = self.get_object()

        # Check image count limit
        if journal_entry.images.count() >= MAX_JOURNAL_IMAGES_PER_ENTRY:
            return Response(
                {'error': f'Maximum {MAX_JOURNAL_IMAGES_PER_ENTRY} images allowed per entry'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = JournalImageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(journal_entry=journal_entry)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
