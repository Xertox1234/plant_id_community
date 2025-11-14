"""
Garden Calendar Admin Configuration

Django admin interface for managing community events, seasonal templates,
and weather alerts.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    CommunityEvent, EventAttendee, SeasonalTemplate, WeatherAlert,
    GrowingZone, GardenBed, Plant, PlantImage, CareTask, CareLog, Harvest
)


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


# =============================================================================
# Garden Planner Admin (Phase 1 - Nov 2025)
# =============================================================================


@admin.register(GrowingZone)
class GrowingZoneAdmin(admin.ModelAdmin):
    """Admin for USDA Hardiness Zones"""

    list_display = [
        'zone_code', 'temp_range_display', 'growing_season_days',
        'frost_dates_display'
    ]
    search_fields = ['zone_code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['zone_code']

    fieldsets = (
        ('Zone Information', {
            'fields': ('zone_code', 'temp_min', 'temp_max', 'description')
        }),
        ('Frost Dates', {
            'fields': ('first_frost_date', 'last_frost_date', 'growing_season_days')
        }),
        ('System Fields', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def temp_range_display(self, obj):
        return f"{obj.temp_min}°F to {obj.temp_max}°F"
    temp_range_display.short_description = 'Temperature Range'

    def frost_dates_display(self, obj):
        if obj.first_frost_date and obj.last_frost_date:
            return f"{obj.last_frost_date} to {obj.first_frost_date}"
        return "Not set"
    frost_dates_display.short_description = 'Frost-Free Period'


class PlantImageInline(admin.TabularInline):
    """Inline for managing plant images"""
    model = PlantImage
    extra = 1
    fields = ['image', 'caption', 'is_primary', 'taken_date']
    readonly_fields = ['taken_date', 'uploaded_at']


@admin.register(GardenBed)
class GardenBedAdmin(admin.ModelAdmin):
    """Admin for garden beds"""

    list_display = [
        'name', 'owner', 'bed_type', 'area_display',
        'plant_count', 'utilization_display', 'is_active'
    ]
    list_filter = ['bed_type', 'sun_exposure', 'is_active', 'hardiness_zone']
    search_fields = ['name', 'description', 'owner__username', 'location_name']
    readonly_fields = [
        'uuid', 'created_at', 'updated_at', 'area_square_feet',
        'area_square_inches', 'volume_cubic_inches', 'plant_count',
        'utilization_rate'
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': ('owner', 'name', 'description', 'bed_type', 'is_active')
        }),
        ('Dimensions', {
            'fields': (
                'length_inches', 'width_inches', 'depth_inches',
                'area_square_feet', 'volume_cubic_inches'
            )
        }),
        ('Location & Climate', {
            'fields': (
                'location_name', 'sun_exposure', 'hardiness_zone'
            )
        }),
        ('Soil Information', {
            'fields': ('soil_type', 'soil_ph')
        }),
        ('Layout Data', {
            'fields': ('layout_data',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('plant_count', 'utilization_rate'),
            'classes': ('collapse',)
        }),
        ('Notes & System', {
            'fields': ('notes', 'uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def area_display(self, obj):
        area = obj.area_square_feet
        if area:
            return f"{area} sq ft"
        return "Not set"
    area_display.short_description = 'Area'

    def utilization_display(self, obj):
        rate = obj.utilization_rate
        if rate is not None:
            percentage = int(rate * 100)
            if percentage < 25:
                color = 'red'
            elif percentage < 60:
                color = 'orange'
            elif percentage < 85:
                color = 'green'
            else:
                color = 'blue'
            return format_html(
                '<span style="color: {};">{:d}%</span>',
                color, percentage
            )
        return "N/A"
    utilization_display.short_description = 'Utilization'


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    """Admin for individual plants"""

    list_display = [
        'common_name', 'garden_bed', 'health_status_display',
        'growth_stage', 'age_display', 'planted_date', 'is_active'
    ]
    list_filter = [
        'health_status', 'growth_stage', 'is_active',
        'garden_bed__bed_type', 'planted_date'
    ]
    search_fields = [
        'common_name', 'scientific_name', 'variety',
        'garden_bed__name', 'garden_bed__owner__username'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at', 'days_since_planted',
        'age_display', 'pending_care_tasks_count'
    ]
    inlines = [PlantImageInline]

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'garden_bed', 'common_name', 'scientific_name',
                'variety', 'plant_species'
            )
        }),
        ('Planting Details', {
            'fields': ('planted_date', 'source', 'age_display', 'days_since_planted')
        }),
        ('Position (Canvas Layout)', {
            'fields': ('position_x', 'position_y'),
            'classes': ('collapse',)
        }),
        ('Health & Growth', {
            'fields': ('health_status', 'growth_stage')
        }),
        ('Status', {
            'fields': ('is_active', 'removed_date', 'removal_reason')
        }),
        ('Care Tasks', {
            'fields': ('pending_care_tasks_count',),
            'classes': ('collapse',)
        }),
        ('Notes & System', {
            'fields': ('notes', 'uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def health_status_display(self, obj):
        from .constants import HEALTH_STATUS_COLORS
        color = HEALTH_STATUS_COLORS.get(obj.health_status, '#6B7280')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_health_status_display()
        )
    health_status_display.short_description = 'Health'


@admin.register(PlantImage)
class PlantImageAdmin(admin.ModelAdmin):
    """Admin for plant images"""

    list_display = ['plant', 'caption', 'taken_date', 'is_primary', 'uploaded_at']
    list_filter = ['is_primary', 'taken_date']
    search_fields = ['plant__common_name', 'caption']
    readonly_fields = ['taken_date', 'uploaded_at']


@admin.register(CareTask)
class CareTaskAdmin(admin.ModelAdmin):
    """Admin for care tasks and reminders"""

    list_display = [
        'title', 'plant', 'task_type', 'priority_display',
        'scheduled_date', 'status_display', 'is_recurring'
    ]
    list_filter = [
        'task_type', 'priority', 'completed', 'skipped',
        'is_recurring', 'scheduled_date'
    ]
    search_fields = [
        'title', 'notes', 'plant__common_name',
        'plant__garden_bed__name', 'created_by__username'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at', 'completed_at',
        'skipped_at', 'is_overdue', 'is_pending'
    ]

    fieldsets = (
        ('Task Details', {
            'fields': (
                'plant', 'created_by', 'task_type',
                'custom_task_name', 'title', 'notes', 'priority'
            )
        }),
        ('Scheduling', {
            'fields': (
                'scheduled_date', 'is_recurring',
                'recurrence_interval_days', 'recurrence_end_date'
            )
        }),
        ('Completion', {
            'fields': (
                'completed', 'completed_at', 'completed_by'
            )
        }),
        ('Skip Status', {
            'fields': ('skipped', 'skip_reason', 'skipped_at'),
            'classes': ('collapse',)
        }),
        ('Status Info', {
            'fields': ('is_overdue', 'is_pending', 'notification_sent'),
            'classes': ('collapse',)
        }),
        ('System Fields', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def priority_display(self, obj):
        colors = {
            'low': '#10B981',       # Green
            'medium': '#F59E0B',    # Amber
            'high': '#EF4444',      # Red
            'urgent': '#991B1B'     # Dark Red
        }
        color = colors.get(obj.priority, '#6B7280')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_display.short_description = 'Priority'

    def status_display(self, obj):
        if obj.completed:
            return format_html('<span style="color: green;">✓ Completed</span>')
        elif obj.skipped:
            return format_html('<span style="color: gray;">⊘ Skipped</span>')
        elif obj.is_overdue:
            return format_html('<span style="color: red;">⚠ Overdue</span>')
        else:
            return format_html('<span style="color: blue;">○ Pending</span>')
    status_display.short_description = 'Status'


@admin.register(CareLog)
class CareLogAdmin(admin.ModelAdmin):
    """Admin for care logs"""

    list_display = [
        'plant', 'user', 'activity_type', 'log_date',
        'temperature', 'humidity'
    ]
    list_filter = ['activity_type', 'log_date']
    search_fields = [
        'content', 'plant__common_name', 'user__username',
        'activity_type'
    ]
    readonly_fields = ['log_date']

    fieldsets = (
        ('Log Information', {
            'fields': ('plant', 'user', 'activity_type', 'content')
        }),
        ('Environmental Data', {
            'fields': ('temperature', 'humidity'),
            'classes': ('collapse',)
        }),
        ('Tags & Metadata', {
            'fields': ('tags', 'log_date'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Harvest)
class HarvestAdmin(admin.ModelAdmin):
    """Admin for harvest records"""

    list_display = [
        'plant', 'harvest_date', 'quantity_display',
        'quality_rating', 'days_from_planting'
    ]
    list_filter = ['unit', 'quality_rating', 'harvest_date']
    search_fields = ['plant__common_name', 'notes']
    readonly_fields = ['created_at', 'days_from_planting']

    fieldsets = (
        ('Harvest Information', {
            'fields': ('plant', 'harvest_date', 'quantity', 'unit')
        }),
        ('Quality & Notes', {
            'fields': ('quality_rating', 'notes')
        }),
        ('Statistics', {
            'fields': ('days_from_planting', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def quantity_display(self, obj):
        return f"{obj.quantity} {obj.get_unit_display()}"
    quantity_display.short_description = 'Quantity'