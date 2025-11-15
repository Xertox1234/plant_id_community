"""
Garden Model Tests

Tests for garden planner data models.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from datetime import date, datetime, timedelta

from ..models import (
    Garden,
    GardenPlant,
    CareReminder,
    Task,
    PestIssue,
    JournalEntry,
    PlantCareLibrary
)

User = get_user_model()


class GardenModelTests(TestCase):
    """Tests for Garden model."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_garden(self):
        """Test creating a garden with required fields."""
        garden = Garden.objects.create(
            user=self.user,
            name='My Test Garden',
            description='A beautiful test garden',
            dimensions={'width': 20, 'height': 10, 'unit': 'ft'},
            layout_data={'plants': [], 'gridSize': 12},
            climate_zone='7a',
            visibility='private'
        )

        self.assertEqual(garden.name, 'My Test Garden')
        self.assertEqual(garden.user, self.user)
        self.assertEqual(garden.dimensions['width'], 20)
        self.assertEqual(garden.climate_zone, '7a')
        self.assertEqual(garden.visibility, 'private')
        self.assertFalse(garden.featured)

    def test_garden_with_location(self):
        """Test creating a garden with location data."""
        garden = Garden.objects.create(
            user=self.user,
            name='Garden with Location',
            dimensions={'width': 15, 'height': 15, 'unit': 'm'},
            location={'lat': 40.7128, 'lng': -74.0060, 'city': 'New York'},
            visibility='public'
        )

        self.assertEqual(garden.location['city'], 'New York')
        self.assertEqual(garden.location['lat'], 40.7128)
        self.assertEqual(garden.visibility, 'public')

    def test_garden_str_representation(self):
        """Test garden string representation."""
        garden = Garden.objects.create(
            user=self.user,
            name='Test Garden',
            dimensions={'width': 10, 'height': 10, 'unit': 'ft'}
        )

        self.assertEqual(str(garden), 'Test Garden (testuser)')


class GardenPlantModelTests(TestCase):
    """Tests for GardenPlant model."""

    def setUp(self):
        """Create test user and garden."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.garden = Garden.objects.create(
            user=self.user,
            name='Test Garden',
            dimensions={'width': 10, 'height': 10, 'unit': 'ft'}
        )

    def test_create_garden_plant(self):
        """Test creating a plant in the garden."""
        plant = GardenPlant.objects.create(
            garden=self.garden,
            common_name='Tomato',
            scientific_name='Solanum lycopersicum',
            planted_date=date.today(),
            position={'x': 5, 'y': 3},
            health_status='healthy'
        )

        self.assertEqual(plant.common_name, 'Tomato')
        self.assertEqual(plant.position['x'], 5)
        self.assertEqual(plant.health_status, 'healthy')

    def test_plant_str_representation(self):
        """Test plant string representation."""
        plant = GardenPlant.objects.create(
            garden=self.garden,
            common_name='Basil',
            planted_date=date.today(),
            position={'x': 2, 'y': 2}
        )

        self.assertEqual(str(plant), 'Basil in Test Garden')


class CareReminderModelTests(TestCase):
    """Tests for CareReminder model."""

    def setUp(self):
        """Create test user, garden, and plant."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.garden = Garden.objects.create(
            user=self.user,
            name='Test Garden',
            dimensions={'width': 10, 'height': 10, 'unit': 'ft'}
        )
        self.plant = GardenPlant.objects.create(
            garden=self.garden,
            common_name='Tomato',
            planted_date=date.today(),
            position={'x': 5, 'y': 3}
        )

    def test_create_care_reminder(self):
        """Test creating a care reminder."""
        reminder = CareReminder.objects.create(
            user=self.user,
            garden_plant=self.plant,
            reminder_type='watering',
            scheduled_date=datetime.now() + timedelta(days=1),
            recurring=True,
            interval_days=3
        )

        self.assertEqual(reminder.reminder_type, 'watering')
        self.assertTrue(reminder.recurring)
        self.assertEqual(reminder.interval_days, 3)
        self.assertFalse(reminder.completed)

    def test_custom_reminder_type(self):
        """Test creating a custom reminder type."""
        reminder = CareReminder.objects.create(
            user=self.user,
            garden_plant=self.plant,
            reminder_type='custom',
            custom_type_name='Check for aphids',
            scheduled_date=datetime.now() + timedelta(days=7)
        )

        self.assertEqual(reminder.reminder_type, 'custom')
        self.assertEqual(reminder.custom_type_name, 'Check for aphids')


class TaskModelTests(TestCase):
    """Tests for Task model."""

    def setUp(self):
        """Create test user and garden."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.garden = Garden.objects.create(
            user=self.user,
            name='Test Garden',
            dimensions={'width': 10, 'height': 10, 'unit': 'ft'}
        )

    def test_create_task(self):
        """Test creating a gardening task."""
        task = Task.objects.create(
            user=self.user,
            garden=self.garden,
            title='Plant spring vegetables',
            description='Plant tomatoes and peppers',
            due_date=date.today() + timedelta(days=14),
            category='planting',
            season='spring',
            priority='high'
        )

        self.assertEqual(task.title, 'Plant spring vegetables')
        self.assertEqual(task.category, 'planting')
        self.assertEqual(task.priority, 'high')
        self.assertFalse(task.completed)

    def test_task_str_representation(self):
        """Test task string representation."""
        task = Task.objects.create(
            user=self.user,
            title='Fertilize lawn',
            category='maintenance',
            priority='medium'
        )

        self.assertEqual(str(task), 'Fertilize lawn')


class PestIssueModelTests(TestCase):
    """Tests for PestIssue model."""

    def setUp(self):
        """Create test user, garden, and plant."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.garden = Garden.objects.create(
            user=self.user,
            name='Test Garden',
            dimensions={'width': 10, 'height': 10, 'unit': 'ft'}
        )
        self.plant = GardenPlant.objects.create(
            garden=self.garden,
            common_name='Tomato',
            planted_date=date.today(),
            position={'x': 5, 'y': 3}
        )

    def test_create_pest_issue(self):
        """Test creating a pest issue."""
        issue = PestIssue.objects.create(
            user=self.user,
            garden_plant=self.plant,
            pest_type='Aphids',
            description='Small green insects on leaves',
            severity='medium',
            treatment='Neem oil spray'
        )

        self.assertEqual(issue.pest_type, 'Aphids')
        self.assertEqual(issue.severity, 'medium')
        self.assertFalse(issue.resolved)

    def test_pest_issue_str_representation(self):
        """Test pest issue string representation."""
        issue = PestIssue.objects.create(
            user=self.user,
            garden_plant=self.plant,
            pest_type='Spider Mites',
            description='Tiny red mites',
            severity='high'
        )

        self.assertEqual(str(issue), 'Spider Mites on Tomato')


class JournalEntryModelTests(TestCase):
    """Tests for JournalEntry model."""

    def setUp(self):
        """Create test user and garden."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.garden = Garden.objects.create(
            user=self.user,
            name='Test Garden',
            dimensions={'width': 10, 'height': 10, 'unit': 'ft'}
        )

    def test_create_journal_entry(self):
        """Test creating a journal entry."""
        entry = JournalEntry.objects.create(
            user=self.user,
            garden=self.garden,
            title='First Harvest!',
            content='Harvested 5 tomatoes today. Looking great!',
            date=date.today(),
            tags=['harvest', 'tomatoes', 'summer']
        )

        self.assertEqual(entry.title, 'First Harvest!')
        self.assertEqual(len(entry.tags), 3)
        self.assertIn('harvest', entry.tags)

    def test_journal_entry_with_weather(self):
        """Test creating a journal entry with weather data."""
        entry = JournalEntry.objects.create(
            user=self.user,
            garden=self.garden,
            title='Hot day in the garden',
            content='Watered extra due to heat',
            date=date.today(),
            weather_data={'temp': 95, 'conditions': 'sunny', 'humidity': 45}
        )

        self.assertEqual(entry.weather_data['temp'], 95)
        self.assertEqual(entry.weather_data['conditions'], 'sunny')


class PlantCareLibraryModelTests(TestCase):
    """Tests for PlantCareLibrary model."""

    def test_create_plant_care_entry(self):
        """Test creating a plant care library entry."""
        care_entry = PlantCareLibrary.objects.create(
            scientific_name='Solanum lycopersicum',
            common_names=['Tomato', 'Garden Tomato'],
            family='Solanaceae',
            sunlight='full_sun',
            water_needs='medium',
            soil_type='Well-drained, rich in organic matter',
            hardiness_zones=['3a', '10b'],
            care_instructions='Full sun, regular watering, support stakes',
            watering_frequency_days=3,
            fertilizing_frequency_days=14,
            companion_plants=['Basil', 'Carrots', 'Marigolds'],
            enemy_plants=['Cabbage', 'Fennel'],
            common_pests=['Aphids', 'Tomato hornworm', 'Whiteflies']
        )

        self.assertEqual(care_entry.scientific_name, 'Solanum lycopersicum')
        self.assertIn('Tomato', care_entry.common_names)
        self.assertEqual(care_entry.watering_frequency_days, 3)
        self.assertIn('Basil', care_entry.companion_plants)
        self.assertEqual(str(care_entry), 'Solanum lycopersicum')
