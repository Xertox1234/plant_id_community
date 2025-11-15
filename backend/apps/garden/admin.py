from django.contrib import admin
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


@admin.register(Garden)
class GardenAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'visibility', 'featured', 'created_at']
    list_filter = ['visibility', 'featured', 'created_at']
    search_fields = ['name', 'user__username', 'climate_zone']
    date_hierarchy = 'created_at'


@admin.register(GardenPlant)
class GardenPlantAdmin(admin.ModelAdmin):
    list_display = ['common_name', 'garden', 'health_status', 'planted_date']
    list_filter = ['health_status', 'planted_date']
    search_fields = ['common_name', 'scientific_name', 'garden__name']
    date_hierarchy = 'planted_date'


@admin.register(CareReminder)
class CareReminderAdmin(admin.ModelAdmin):
    list_display = ['garden_plant', 'reminder_type', 'scheduled_date', 'completed', 'notification_sent']
    list_filter = ['reminder_type', 'completed', 'recurring', 'notification_sent']
    search_fields = ['garden_plant__common_name', 'notes']
    date_hierarchy = 'scheduled_date'


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'category', 'season', 'priority', 'completed', 'due_date']
    list_filter = ['category', 'season', 'priority', 'completed']
    search_fields = ['title', 'description']
    date_hierarchy = 'due_date'


@admin.register(PestIssue)
class PestIssueAdmin(admin.ModelAdmin):
    list_display = ['pest_type', 'garden_plant', 'severity', 'resolved', 'identified_date']
    list_filter = ['severity', 'resolved', 'identified_date']
    search_fields = ['pest_type', 'description', 'garden_plant__common_name']
    date_hierarchy = 'identified_date'


@admin.register(PestImage)
class PestImageAdmin(admin.ModelAdmin):
    list_display = ['pest_issue', 'uploaded_at']
    date_hierarchy = 'uploaded_at'


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'garden', 'date', 'created_at']
    list_filter = ['date', 'tags']
    search_fields = ['title', 'content', 'garden__name']
    date_hierarchy = 'date'


@admin.register(JournalImage)
class JournalImageAdmin(admin.ModelAdmin):
    list_display = ['journal_entry', 'caption', 'uploaded_at']
    search_fields = ['caption', 'journal_entry__title']
    date_hierarchy = 'uploaded_at'


@admin.register(PlantCareLibrary)
class PlantCareLibraryAdmin(admin.ModelAdmin):
    list_display = ['scientific_name', 'sunlight', 'water_needs', 'family']
    list_filter = ['sunlight', 'water_needs']
    search_fields = ['scientific_name', 'family', 'common_names']
