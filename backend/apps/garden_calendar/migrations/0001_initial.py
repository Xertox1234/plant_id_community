# Generated migration for garden_calendar app

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CommunityEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Unique identifier for secure references', unique=True)),
                ('title', models.CharField(help_text='Event title/name', max_length=200)),
                ('description', models.TextField(help_text='Detailed event description')),
                ('event_type', models.CharField(choices=[('plant_swap', 'Plant Swap'), ('workshop', 'Workshop/Class'), ('garden_tour', 'Garden Tour'), ('vendor_sale', 'Plant Sale/Vendor'), ('bulk_order', 'Group/Bulk Order'), ('meetup', 'General Meetup'), ('maintenance', 'Community Garden Maintenance'), ('harvest', 'Community Harvest'), ('other', 'Other Event')], help_text='Type of community event', max_length=20)),
                ('start_datetime', models.DateTimeField(help_text='Event start date and time')),
                ('end_datetime', models.DateTimeField(blank=True, help_text='Event end date and time (optional for short events)', null=True)),
                ('is_all_day', models.BooleanField(default=False, help_text='Is this an all-day event?')),
                ('location_name', models.CharField(blank=True, help_text='Venue name or general location description', max_length=200)),
                ('address', models.TextField(blank=True, help_text='Full address (will be masked based on privacy settings)')),
                ('city', models.CharField(blank=True, help_text='City for regional filtering', max_length=100)),
                ('hardiness_zone', models.CharField(blank=True, help_text='USDA Hardiness Zone for climate-relevant events', max_length=5)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, help_text='Latitude for precise location (optional)', max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, help_text='Longitude for precise location (optional)', max_digits=9, null=True)),
                ('privacy_level', models.CharField(choices=[('public', 'Public - Anyone can see'), ('local', 'Local - People in same city/region'), ('zone', 'Zone - People in same hardiness zone'), ('friends', 'Friends - Only people I follow'), ('private', 'Private - Invitation only')], default='local', help_text='Who can see this event', max_length=10)),
                ('max_attendees', models.PositiveIntegerField(blank=True, help_text='Maximum number of attendees (leave blank for unlimited)', null=True)),
                ('requires_rsvp', models.BooleanField(default=False, help_text='Does this event require RSVP?')),
                ('is_recurring', models.BooleanField(default=False, help_text='Is this a recurring event?')),
                ('recurrence_rule', models.JSONField(blank=True, help_text='JSON data for recurring event rules (RRULE format)', null=True)),
                ('contact_email', models.EmailField(blank=True, help_text='Contact email for event questions', max_length=254)),
                ('contact_phone', models.CharField(blank=True, help_text='Contact phone number (will be masked based on privacy)', max_length=20)),
                ('external_url', models.URLField(blank=True, help_text='External link for more information or registration')),
                ('weather_dependent', models.BooleanField(default=False, help_text='Should this event be canceled/postponed due to bad weather?')),
                ('weather_backup_plan', models.TextField(blank=True, help_text='What happens if weather is bad? (indoor venue, reschedule, etc.)')),
                ('forum_topic_id', models.PositiveIntegerField(blank=True, help_text='ID of associated forum discussion topic (if forum enabled)', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organizer', models.ForeignKey(help_text='User who created this event', on_delete=django.db.models.deletion.CASCADE, related_name='organized_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Community Event',
                'verbose_name_plural': 'Community Events',
                'ordering': ['start_datetime'],
            },
        ),
        migrations.CreateModel(
            name='SeasonalTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Template name (e.g., \'Spring Tomato Care - Zone 7\')', max_length=200)),
                ('description', models.TextField(help_text='Detailed description of this seasonal template')),
                ('hardiness_zones', models.JSONField(help_text='List of USDA zones this template applies to (e.g., [\'7a\', \'7b\', \'8a\'])')),
                ('season', models.CharField(choices=[('spring', 'Spring'), ('summer', 'Summer'), ('fall', 'Fall/Autumn'), ('winter', 'Winter')], help_text='Primary season for this template', max_length=10)),
                ('task_type', models.CharField(choices=[('watering', 'Watering'), ('fertilizing', 'Fertilizing'), ('pruning', 'Pruning'), ('planting', 'Planting'), ('harvesting', 'Harvesting'), ('pest_control', 'Pest Control'), ('disease_prevention', 'Disease Prevention'), ('soil_preparation', 'Soil Preparation'), ('mulching', 'Mulching'), ('winterization', 'Winter Preparation'), ('spring_cleanup', 'Spring Cleanup'), ('inspection', 'Plant Inspection'), ('other', 'Other Task')], help_text='Type of gardening task', max_length=20)),
                ('plant_types', models.JSONField(blank=True, help_text='List of plant types this applies to (e.g., [\'tomatoes\', \'roses\', \'succulents\'])', null=True)),
                ('start_month', models.PositiveSmallIntegerField(help_text='Month to start this task (1-12)', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(12)])),
                ('end_month', models.PositiveSmallIntegerField(blank=True, help_text='Month to end this task (optional, for multi-month tasks)', null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(12)])),
                ('day_of_month', models.PositiveSmallIntegerField(blank=True, help_text='Specific day of month (optional, defaults to 1st)', null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(31)])),
                ('frequency_days', models.PositiveIntegerField(default=7, help_text='How often to repeat this task (in days)')),
                ('temperature_min', models.SmallIntegerField(blank=True, help_text='Minimum temperature (Fahrenheit) for this task', null=True)),
                ('temperature_max', models.SmallIntegerField(blank=True, help_text='Maximum temperature (Fahrenheit) for this task', null=True)),
                ('requires_no_frost', models.BooleanField(default=False, help_text='Should this task wait until frost danger has passed?')),
                ('requires_no_rain', models.BooleanField(default=False, help_text='Should this task be skipped during rainy weather?')),
                ('instructions', models.TextField(help_text='Detailed instructions for this seasonal task')),
                ('tips', models.TextField(blank=True, help_text='Additional tips and advice')),
                ('priority', models.CharField(choices=[('low', 'Low Priority'), ('medium', 'Medium Priority'), ('high', 'High Priority'), ('critical', 'Critical/Time Sensitive')], default='medium', max_length=10)),
                ('is_active', models.BooleanField(default=True, help_text='Is this template active and should generate tasks?')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this template (optional for system templates)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_templates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Seasonal Template',
                'verbose_name_plural': 'Seasonal Templates',
                'ordering': ['season', 'start_month', 'day_of_month', 'task_type'],
            },
        ),
        migrations.CreateModel(
            name='WeatherAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_type', models.CharField(choices=[('frost', 'Frost Warning'), ('freeze', 'Freeze Warning'), ('high_wind', 'High Wind Alert'), ('heavy_rain', 'Heavy Rain Alert'), ('drought', 'Drought Conditions'), ('heat_wave', 'Excessive Heat'), ('severe_weather', 'Severe Weather Warning'), ('good_conditions', 'Favorable Conditions')], help_text='Type of weather alert', max_length=20)),
                ('severity', models.CharField(choices=[('info', 'Informational'), ('low', 'Low Impact'), ('medium', 'Medium Impact'), ('high', 'High Impact'), ('critical', 'Critical/Emergency')], default='medium', help_text='Severity level of this alert', max_length=10)),
                ('zip_code', models.CharField(help_text='ZIP code this alert applies to', max_length=10)),
                ('city', models.CharField(blank=True, help_text='City name for display', max_length=100)),
                ('hardiness_zone', models.CharField(blank=True, help_text='USDA zone this alert applies to', max_length=5)),
                ('title', models.CharField(help_text='Alert title/headline', max_length=200)),
                ('message', models.TextField(help_text='Detailed alert message')),
                ('recommendations', models.TextField(blank=True, help_text='Recommended actions for gardeners')),
                ('start_datetime', models.DateTimeField(help_text='When the weather condition starts')),
                ('end_datetime', models.DateTimeField(blank=True, help_text='When the weather condition ends (if known)', null=True)),
                ('expires_at', models.DateTimeField(help_text='When this alert expires and should be removed')),
                ('temperature_low', models.SmallIntegerField(blank=True, help_text='Predicted low temperature (Fahrenheit)', null=True)),
                ('temperature_high', models.SmallIntegerField(blank=True, help_text='Predicted high temperature (Fahrenheit)', null=True)),
                ('wind_speed', models.PositiveSmallIntegerField(blank=True, help_text='Wind speed in MPH', null=True)),
                ('precipitation_chance', models.PositiveSmallIntegerField(blank=True, help_text='Chance of precipitation (0-100%)', null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('precipitation_amount', models.DecimalField(blank=True, decimal_places=2, help_text='Expected precipitation in inches', max_digits=4, null=True)),
                ('is_active', models.BooleanField(default=True, help_text='Is this alert currently active?')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Weather Alert',
                'verbose_name_plural': 'Weather Alerts',
                'ordering': ['-severity', '-start_datetime'],
            },
        ),
        migrations.CreateModel(
            name='EventAttendee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('going', 'Going'), ('maybe', 'Maybe'), ('not_going', 'Not Going'), ('invited', 'Invited (No Response)')], default='going', max_length=10)),
                ('notes', models.TextField(blank=True, help_text='Optional notes from the attendee')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendees', to='garden_calendar.communityevent')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='event_attendances', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Event Attendee',
                'verbose_name_plural': 'Event Attendees',
            },
        ),
        migrations.AddIndex(
            model_name='weatheralert',
            index=models.Index(fields=['zip_code', 'is_active'], name='garden_cale_zip_cod_dbc1b9_idx'),
        ),
        migrations.AddIndex(
            model_name='weatheralert',
            index=models.Index(fields=['start_datetime', 'end_datetime'], name='garden_cale_start_d_5e7b21_idx'),
        ),
        migrations.AddIndex(
            model_name='weatheralert',
            index=models.Index(fields=['alert_type', 'severity'], name='garden_cale_alert_t_aefd24_idx'),
        ),
        migrations.AddIndex(
            model_name='seasonaltemplate',
            index=models.Index(fields=['season', 'start_month'], name='garden_cale_season_127445_idx'),
        ),
        migrations.AddIndex(
            model_name='seasonaltemplate',
            index=models.Index(fields=['task_type', 'is_active'], name='garden_cale_task_ty_fa4977_idx'),
        ),
        migrations.AddIndex(
            model_name='communityevent',
            index=models.Index(fields=['start_datetime', 'privacy_level'], name='garden_cale_start_d_431460_idx'),
        ),
        migrations.AddIndex(
            model_name='communityevent',
            index=models.Index(fields=['city', 'hardiness_zone'], name='garden_cale_city_635b34_idx'),
        ),
        migrations.AddIndex(
            model_name='communityevent',
            index=models.Index(fields=['event_type', 'start_datetime'], name='garden_cale_event_t_871d8c_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='eventattendee',
            unique_together={('event', 'user')},
        ),
    ]