"""
Garden Planner URL Configuration

API v1 endpoints for garden planning features.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import (
    GardenViewSet,
    GardenPlantViewSet,
    CareReminderViewSet,
    TaskViewSet,
    PestIssueViewSet,
    JournalEntryViewSet,
    PlantCareLibraryViewSet
)

app_name = 'garden'

# DRF router for ViewSets
router = DefaultRouter()
router.register(r'gardens', GardenViewSet, basename='garden')
router.register(r'plants', GardenPlantViewSet, basename='garden-plant')
router.register(r'reminders', CareReminderViewSet, basename='care-reminder')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'pest-issues', PestIssueViewSet, basename='pest-issue')
router.register(r'journal', JournalEntryViewSet, basename='journal-entry')
router.register(r'plant-care', PlantCareLibraryViewSet, basename='plant-care')

urlpatterns = [
    path('', include(router.urls)),
]
