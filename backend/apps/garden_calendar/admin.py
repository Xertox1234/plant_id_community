"""
Garden Calendar Admin Configuration

Django admin interface for managing community events, seasonal templates,
and weather alerts.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import CommunityEvent, EventAttendee, SeasonalTemplate, WeatherAlert


@admin.register(CommunityEvent)
class CommunityEventAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'organizer', 'event_type', 'start_datetime', 
        'privacy_level', 'attendee_count_display', 'is_past'
    ]
    list_filter = [
        'event_type', 'privacy_level', 'is_all_day', 'weather_dependent',
        'requires_rsvp', 'is_recurring', 'hardiness_zone'
    ]
    search_fields = ['title', 'description', 'organizer__username', 'city']
    readonly_fields = ['uuid', 'created_at', 'updated_at', 'attendee_count_display']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'organizer', 'event_type', 'description')
        }),
        ('Date & Time', {
            'fields': ('start_datetime', 'end_datetime', 'is_all_day')
        }),
        ('Location', {
            'fields': ('location_name', 'address', 'city', 'hardiness_zone', 'latitude', 'longitude')
        }),
        ('Privacy & Attendance', {
            'fields': ('privacy_level', 'max_attendees', 'requires_rsvp')
        }),
        ('Contact Information', {
            'fields': ('contact_email', 'contact_phone', 'external_url')
        }),
        ('Weather & Forum', {
            'fields': ('weather_dependent', 'weather_backup_plan', 'forum_topic')
        }),
        ('Recurring Events', {
            'fields': ('is_recurring', 'recurrence_rule'),
            'classes': ('collapse',)
        }),
        ('System Fields', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def attendee_count_display(self, obj):
        count = obj.attendee_count
        if obj.max_attendees:
            return f"{count}/{obj.max_attendees}"
        return str(count)
    attendee_count_display.short_description = 'Attendees'
    
    def is_past(self, obj):
        return obj.is_past
    is_past.boolean = True
    is_past.short_description = 'Past Event'


class EventAttendeeInline(admin.TabularInline):
    model = EventAttendee
    extra = 0
    fields = ['user', 'status', 'notes', 'created_at']
    readonly_fields = ['created_at']


@admin.register(EventAttendee)
class EventAttendeeAdmin(admin.ModelAdmin):
    list_display = ['user', 'event', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'event__title']


@admin.register(SeasonalTemplate)
class SeasonalTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'season', 'task_type', 'zones_display',
        'start_month', 'priority', 'is_active'
    ]
    list_filter = [
        'season', 'task_type', 'priority', 'is_active',
        'requires_no_frost', 'requires_no_rain'
    ]
    search_fields = ['name', 'description', 'instructions']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'task_type', 'priority', 'is_active')
        }),
        ('Location & Season', {
            'fields': ('hardiness_zones', 'season', 'plant_types')
        }),
        ('Timing', {
            'fields': ('start_month', 'end_month', 'day_of_month', 'frequency_days')
        }),
        ('Weather Conditions', {
            'fields': (
                'temperature_min', 'temperature_max', 
                'requires_no_frost', 'requires_no_rain'
            )
        }),
        ('Content', {
            'fields': ('instructions', 'tips')
        }),
        ('System Fields', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def zones_display(self, obj):
        return obj.applicable_zones_display
    zones_display.short_description = 'Zones'


@admin.register(WeatherAlert)
class WeatherAlertAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'alert_type', 'severity', 'city_or_zip',
        'start_datetime', 'is_current', 'is_active'
    ]
    list_filter = [
        'alert_type', 'severity', 'is_active',
        'hardiness_zone', 'start_datetime'
    ]
    search_fields = ['title', 'message', 'city', 'zip_code']
    readonly_fields = ['created_at', 'updated_at', 'is_current']
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('alert_type', 'severity', 'title', 'message', 'recommendations')
        }),
        ('Location', {
            'fields': ('zip_code', 'city', 'hardiness_zone')
        }),
        ('Timing', {
            'fields': ('start_datetime', 'end_datetime', 'expires_at')
        }),
        ('Weather Data', {
            'fields': (
                'temperature_low', 'temperature_high', 'wind_speed',
                'precipitation_chance', 'precipitation_amount'
            )
        }),
        ('System Fields', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def city_or_zip(self, obj):
        return obj.city if obj.city else obj.zip_code
    city_or_zip.short_description = 'Location'
    
    def is_current(self, obj):
        return obj.is_current
    is_current.boolean = True
    is_current.short_description = 'Currently Active'