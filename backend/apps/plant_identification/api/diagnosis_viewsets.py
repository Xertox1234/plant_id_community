"""
ViewSets for plant health diagnosis feature.

Provides CRUD operations for DiagnosisCard and DiagnosisReminder models
with user-scoped access control and filtering capabilities.
"""

import logging
from typing import Dict, Any, Type, List
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.serializers import Serializer
from django.db.models import QuerySet, Q

from ..models import DiagnosisCard, DiagnosisReminder
from .diagnosis_serializers import (
    DiagnosisCardListSerializer,
    DiagnosisCardDetailSerializer,
    DiagnosisCardCreateSerializer,
    DiagnosisCardUpdateSerializer,
    DiagnosisReminderSerializer,
)

logger = logging.getLogger(__name__)


class DiagnosisCardViewSet(viewsets.ModelViewSet):
    """
    ViewSet for diagnosis cards.

    Provides:
    - List: User's saved diagnosis cards (paginated)
    - Retrieve: Single card detail with full care instructions
    - Create: New diagnosis card from PlantDiseaseResult
    - Update: Modify care instructions, notes, status, etc.
    - Delete: Hard delete diagnosis card

    Query Parameters:
        - treatment_status (str): Filter by status (not_started, in_progress, successful, failed, monitoring)
        - is_favorite (bool): Filter favorite cards only
        - plant_recovered (bool): Filter by recovery status
        - search (str): Search in plant names and disease names
        - ordering (str): Sort order (e.g., -saved_at, disease_name)

    Permissions:
        - User can only access their own diagnosis cards
        - All actions require authentication

    Performance:
        - select_related('user', 'diagnosis_result')
        - prefetch_related('reminders') for detail view
        - Pagination enabled (default 20 per page)
    """

    permission_classes = [IsAuthenticated]
    lookup_field = 'uuid'  # Use UUID instead of integer ID
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['saved_at', 'updated_at', 'disease_name', 'treatment_status']
    ordering = ['-saved_at']  # Most recent first
    search_fields = ['plant_scientific_name', 'plant_common_name', 'custom_nickname', 'disease_name']

    def get_queryset(self) -> QuerySet[DiagnosisCard]:
        """
        Get diagnosis cards queryset scoped to current user.

        Returns:
            QuerySet with user's diagnosis cards only
        """
        # User can only see their own cards
        qs = DiagnosisCard.objects.filter(user=self.request.user)

        # Always select related for performance
        qs = qs.select_related('user', 'diagnosis_result')

        # For detail view, prefetch reminders
        if self.action == 'retrieve':
            qs = qs.prefetch_related('reminders')

        # Filter by treatment status
        treatment_status = self.request.query_params.get('treatment_status')
        if treatment_status:
            qs = qs.filter(treatment_status=treatment_status)

        # Filter by favorite status
        is_favorite = self.request.query_params.get('is_favorite')
        if is_favorite and is_favorite.lower() in ['true', '1']:
            qs = qs.filter(is_favorite=True)

        # Filter by plant recovery status
        plant_recovered = self.request.query_params.get('plant_recovered')
        if plant_recovered:
            if plant_recovered.lower() in ['true', '1']:
                qs = qs.filter(plant_recovered=True)
            elif plant_recovered.lower() in ['false', '0']:
                qs = qs.filter(plant_recovered=False)

        # Filter by disease type
        disease_type = self.request.query_params.get('disease_type')
        if disease_type:
            qs = qs.filter(disease_type=disease_type)

        return qs

    def get_serializer_class(self) -> Type[Serializer]:
        """
        Use different serializers for different actions.

        Returns:
            - DiagnosisCardCreateSerializer for create action
            - DiagnosisCardUpdateSerializer for update/partial_update actions
            - DiagnosisCardDetailSerializer for retrieve (full data)
            - DiagnosisCardListSerializer for list (lightweight)
        """
        if self.action == 'create':
            return DiagnosisCardCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DiagnosisCardUpdateSerializer
        elif self.action == 'retrieve':
            return DiagnosisCardDetailSerializer
        return DiagnosisCardListSerializer

    def get_serializer_context(self) -> Dict[str, Any]:
        """
        Add request to serializer context.

        Returns:
            Dict with request object for user validation
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """
        Retrieve single diagnosis card and update last_viewed_at.

        Returns:
            DiagnosisCard detail with all fields
        """
        instance = self.get_object()

        # Update last viewed timestamp
        instance.update_last_viewed()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def favorites(self, request: Request) -> Response:
        """
        Get user's favorite diagnosis cards.

        Returns:
            List of favorite cards
        """
        favorites = self.get_queryset().filter(is_favorite=True)

        page = self.paginate_queryset(favorites)
        if page is not None:
            serializer = DiagnosisCardListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = DiagnosisCardListSerializer(favorites, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def active_treatments(self, request: Request) -> Response:
        """
        Get cards with active treatments (in_progress status).

        Returns:
            List of cards with ongoing treatments
        """
        active = self.get_queryset().filter(treatment_status='in_progress')

        serializer = DiagnosisCardListSerializer(active, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def successful_treatments(self, request: Request) -> Response:
        """
        Get cards with successful treatments (plant recovered).

        Returns:
            List of successfully treated cards
        """
        successful = self.get_queryset().filter(
            Q(treatment_status='successful') | Q(plant_recovered=True)
        )

        serializer = DiagnosisCardListSerializer(successful, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def toggle_favorite(self, request: Request, uuid=None) -> Response:
        """
        Toggle favorite status of a diagnosis card.

        Returns:
            Updated card with new favorite status
        """
        card = self.get_object()
        card.is_favorite = not card.is_favorite
        card.save(update_fields=['is_favorite'])

        serializer = DiagnosisCardDetailSerializer(card, context={'request': request})
        return Response(serializer.data)


class DiagnosisReminderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for diagnosis reminders.

    Provides:
    - List: User's reminders (all cards or specific card)
    - Retrieve: Single reminder detail
    - Create: New reminder for a diagnosis card
    - Update: Modify reminder (title, message, date)
    - Delete: Hard delete reminder

    Query Parameters:
        - diagnosis_card (uuid): Filter by diagnosis card UUID
        - is_active (bool): Filter active reminders only
        - sent (bool): Filter by sent status
        - reminder_type (str): Filter by type (check_progress, treatment_step, follow_up, reapply)

    Permissions:
        - User can only access reminders for their own diagnosis cards
        - All actions require authentication

    Performance:
        - select_related('diagnosis_card', 'diagnosis_card__user')
        - Pagination enabled (default 20 per page)
    """

    permission_classes = [IsAuthenticated]
    lookup_field = 'uuid'  # Use UUID instead of integer ID
    serializer_class = DiagnosisReminderSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['scheduled_date', 'created_at']
    ordering = ['scheduled_date']  # Soonest first

    def get_queryset(self) -> QuerySet[DiagnosisReminder]:
        """
        Get reminders queryset scoped to current user's diagnosis cards.

        Returns:
            QuerySet with reminders for user's cards only
        """
        # User can only see reminders for their own diagnosis cards
        qs = DiagnosisReminder.objects.filter(diagnosis_card__user=self.request.user)

        # Always select related for performance
        qs = qs.select_related('diagnosis_card', 'diagnosis_card__user')

        # Filter by diagnosis card UUID
        card_uuid = self.request.query_params.get('diagnosis_card')
        if card_uuid:
            qs = qs.filter(diagnosis_card__uuid=card_uuid)

        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active and is_active.lower() in ['true', '1']:
            qs = qs.filter(is_active=True, sent=False, cancelled=False)

        # Filter by sent status
        sent = self.request.query_params.get('sent')
        if sent:
            if sent.lower() in ['true', '1']:
                qs = qs.filter(sent=True)
            elif sent.lower() in ['false', '0']:
                qs = qs.filter(sent=False)

        # Filter by reminder type
        reminder_type = self.request.query_params.get('reminder_type')
        if reminder_type:
            qs = qs.filter(reminder_type=reminder_type)

        return qs

    def get_serializer_context(self) -> Dict[str, Any]:
        """
        Add request to serializer context.

        Returns:
            Dict with request object for card ownership validation
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=False, methods=['get'])
    def upcoming(self, request: Request) -> Response:
        """
        Get upcoming active reminders (next 30 days).

        Returns:
            List of upcoming reminders sorted by scheduled_date
        """
        from django.utils import timezone
        from datetime import timedelta

        end_date = timezone.now() + timedelta(days=30)

        upcoming = self.get_queryset().filter(
            is_active=True,
            sent=False,
            cancelled=False,
            scheduled_date__lte=end_date,
            scheduled_date__gte=timezone.now()
        ).order_by('scheduled_date')

        serializer = DiagnosisReminderSerializer(upcoming, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def snooze(self, request: Request, uuid=None) -> Response:
        """
        Snooze a reminder by specified hours (default 24).

        Body Parameters:
            - hours (int): Number of hours to snooze (default 24)

        Returns:
            Updated reminder with new snoozed_until timestamp
        """
        reminder = self.get_object()
        hours = int(request.data.get('hours', 24))

        reminder.snooze(hours=hours)

        serializer = DiagnosisReminderSerializer(reminder, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cancel(self, request: Request, uuid=None) -> Response:
        """
        Cancel a reminder (sets cancelled=True, is_active=False).

        Returns:
            Updated reminder with cancelled status
        """
        reminder = self.get_object()
        reminder.cancel()

        serializer = DiagnosisReminderSerializer(reminder, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def acknowledge(self, request: Request, uuid=None) -> Response:
        """
        Acknowledge a sent reminder (user has seen it).

        Returns:
            Updated reminder with acknowledged timestamp
        """
        reminder = self.get_object()

        if not reminder.sent:
            return Response(
                {
                    'error': 'Reminder not sent yet',
                    'detail': 'Can only acknowledge reminders that have been sent'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        reminder.acknowledge()

        serializer = DiagnosisReminderSerializer(reminder, context={'request': request})
        return Response(serializer.data)
