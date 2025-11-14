"""
ViewSet tests for garden_calendar app.

Tests CRUD operations, permissions, filtering, and custom actions.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from rest_framework.test import APIClient
from rest_framework import status

from ..models import (
    GrowingZone, GardenBed, Plant, PlantImage, CareTask, CareLog, Harvest
)

User = get_user_model()


class GardenBedViewSetTest(TestCase):
    """Test GardenBedViewSet CRUD operations."""

    def setUp(self):
        """Set up test users and client."""
        self.user1 = User.objects.create_user(
            username='gardener1',
            email='gardener1@test.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='gardener2',
            email='gardener2@test.com',
            password='testpass123'
        )

        self.client = APIClient()

    def test_create_garden_bed_authenticated(self):
        """Test creating a garden bed as authenticated user."""
        self.client.force_authenticate(user=self.user1)

        data = {
            'name': 'My First Garden',
            'bed_type': 'raised',
            'length_inches': 96,
            'width_inches': 48,
            'depth_inches': 12,
            'sun_exposure': 'full_sun',
            'soil_type': 'loam',
            'soil_ph': '6.5'
        }

        response = self.client.post('/api/v1/calendar/api/garden-beds/', data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'My First Garden')
        self.assertEqual(response.data['owner'], self.user1.id)
        self.assertIsNotNone(response.data['uuid'])

    def test_create_garden_bed_unauthenticated(self):
        """Test that unauthenticated users cannot create garden beds."""
        data = {
            'name': 'My First Garden',
            'bed_type': 'raised'
        }

        response = self.client.post('/api/v1/calendar/api/garden-beds/', data)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_garden_beds_only_own(self):
        """Test that users only see their own garden beds."""
        self.client.force_authenticate(user=self.user1)

        # Create beds for both users
        GardenBed.objects.create(
            owner=self.user1,
            name='User 1 Bed',
            bed_type='raised'
        )
        GardenBed.objects.create(
            owner=self.user2,
            name='User 2 Bed',
            bed_type='raised'
        )

        response = self.client.get('/api/v1/calendar/api/garden-beds/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'User 1 Bed')

    def test_retrieve_garden_bed(self):
        """Test retrieving a single garden bed."""
        self.client.force_authenticate(user=self.user1)

        bed = GardenBed.objects.create(
            owner=self.user1,
            name='Test Bed',
            bed_type='raised',
            length_inches=96,
            width_inches=48
        )

        response = self.client.get(f'/api/v1/calendar/api/garden-beds/{bed.uuid}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Bed')
        self.assertEqual(response.data['area_square_feet'], 32.0)

    def test_retrieve_other_user_bed_forbidden(self):
        """Test that users cannot retrieve other users' beds."""
        self.client.force_authenticate(user=self.user1)

        bed = GardenBed.objects.create(
            owner=self.user2,
            name='User 2 Bed',
            bed_type='raised'
        )

        response = self.client.get(f'/api/v1/calendar/api/garden-beds/{bed.uuid}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_garden_bed(self):
        """Test updating a garden bed."""
        self.client.force_authenticate(user=self.user1)

        bed = GardenBed.objects.create(
            owner=self.user1,
            name='Old Name',
            bed_type='raised'
        )

        data = {
            'name': 'New Name',
            'bed_type': 'raised',
            'soil_ph': '7.0'
        }

        response = self.client.put(
            f'/api/v1/calendar/api/garden-beds/{bed.uuid}/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'New Name')

        bed.refresh_from_db()
        self.assertEqual(bed.name, 'New Name')
        self.assertEqual(bed.soil_ph, Decimal('7.0'))

    def test_partial_update_garden_bed(self):
        """Test partial update (PATCH) of a garden bed."""
        self.client.force_authenticate(user=self.user1)

        bed = GardenBed.objects.create(
            owner=self.user1,
            name='Original Name',
            bed_type='raised'
        )

        data = {'name': 'Updated Name'}

        response = self.client.patch(
            f'/api/v1/calendar/api/garden-beds/{bed.uuid}/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Name')

        bed.refresh_from_db()
        self.assertEqual(bed.name, 'Updated Name')
        self.assertEqual(bed.bed_type, 'raised')  # Unchanged

    def test_delete_garden_bed(self):
        """Test deleting a garden bed."""
        self.client.force_authenticate(user=self.user1)

        bed = GardenBed.objects.create(
            owner=self.user1,
            name='Bed to Delete',
            bed_type='raised'
        )

        response = self.client.delete(f'/api/v1/calendar/api/garden-beds/{bed.uuid}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(GardenBed.objects.filter(uuid=bed.uuid).exists())

    def test_update_other_user_bed_forbidden(self):
        """Test that users cannot update other users' beds."""
        self.client.force_authenticate(user=self.user1)

        bed = GardenBed.objects.create(
            owner=self.user2,
            name='User 2 Bed',
            bed_type='raised'
        )

        data = {'name': 'Hacked Name'}

        response = self.client.put(
            f'/api/v1/calendar/api/garden-beds/{bed.uuid}/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PlantViewSetTest(TestCase):
    """Test PlantViewSet CRUD operations."""

    def setUp(self):
        """Set up test users, garden bed, and client."""
        self.user = User.objects.create_user(
            username='gardener',
            email='gardener@test.com',
            password='testpass123'
        )

        self.bed = GardenBed.objects.create(
            owner=self.user,
            name='Test Bed',
            bed_type='raised'
        )

        self.client = APIClient()

    def test_create_plant(self):
        """Test creating a plant."""
        self.client.force_authenticate(user=self.user)

        data = {
            'garden_bed': str(self.bed.uuid),
            'common_name': 'Tomato',
            'variety': 'Cherry',
            'planted_date': '2024-11-01',
            'health_status': 'healthy',
            'growth_stage': 'seedling'
        }

        response = self.client.post('/api/v1/calendar/api/plants/', data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['common_name'], 'Tomato')
        self.assertIsNotNone(response.data['uuid'])

    def test_list_plants_filtered_by_bed(self):
        """Test listing plants with garden bed filter."""
        self.client.force_authenticate(user=self.user)

        # Create plants in this bed
        Plant.objects.create(
            garden_bed=self.bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='seedling',
            planted_date=timezone.now().date()
        )
        Plant.objects.create(
            garden_bed=self.bed,
            common_name='Basil',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=timezone.now().date()
        )

        # Create another bed with plant
        other_bed = GardenBed.objects.create(
            owner=self.user,
            name='Other Bed',
            bed_type='container'
        )
        Plant.objects.create(
            garden_bed=other_bed,
            common_name='Mint',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=timezone.now().date()
        )

        response = self.client.get(
            f'/api/v1/calendar/api/plants/?garden_bed={self.bed.uuid}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_update_plant_health_status(self):
        """Test updating plant health status."""
        self.client.force_authenticate(user=self.user)

        plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=timezone.now().date()
        )

        data = {
            'garden_bed': str(self.bed.uuid),
            'common_name': 'Tomato',
            'health_status': 'struggling',
            'growth_stage': 'vegetative',
            'planted_date': plant.planted_date.isoformat()
        }

        response = self.client.put(
            f'/api/v1/calendar/api/plants/{plant.uuid}/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['health_status'], 'struggling')

    def test_delete_plant(self):
        """Test deleting a plant."""
        self.client.force_authenticate(user=self.user)

        plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name='Dead Plant',
            health_status='dead',
            growth_stage='declining',
            planted_date=timezone.now().date()
        )

        response = self.client.delete(f'/api/v1/calendar/api/plants/{plant.uuid}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Plant.objects.filter(uuid=plant.uuid).exists())


class CareTaskViewSetTest(TestCase):
    """Test CareTaskViewSet operations."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='gardener',
            email='gardener@test.com',
            password='testpass123'
        )

        self.bed = GardenBed.objects.create(
            owner=self.user,
            name='Test Bed',
            bed_type='raised'
        )

        self.plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=timezone.now().date()
        )

        self.client = APIClient()

    def test_create_care_task(self):
        """Test creating a care task."""
        self.client.force_authenticate(user=self.user)

        data = {
            'plant': str(self.plant.uuid),
            'task_type': 'watering',
            'title': 'Water tomato plant',
            'priority': 'high',
            'scheduled_date': (timezone.now() + timedelta(days=1)).isoformat()
        }

        response = self.client.post('/api/v1/calendar/api/care-tasks/', data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['task_type'], 'watering')
        self.assertEqual(response.data['title'], 'Water tomato plant')

    def test_list_care_tasks_pending_only(self):
        """Test filtering care tasks to show only pending."""
        self.client.force_authenticate(user=self.user)

        # Create pending task
        CareTask.objects.create(
            plant=self.plant,
            created_by=self.user,
            task_type='watering',
            title='Pending task',
            priority='high',
            scheduled_date=timezone.now() + timedelta(days=1)
        )

        # Create completed task
        CareTask.objects.create(
            plant=self.plant,
            created_by=self.user,
            task_type='fertilizing',
            title='Completed task',
            priority='medium',
            scheduled_date=timezone.now(),
            completed=True
        )

        response = self.client.get('/api/v1/calendar/api/care-tasks/?completed=false')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Pending task')

    def test_mark_task_complete_action(self):
        """Test mark_complete custom action."""
        self.client.force_authenticate(user=self.user)

        task = CareTask.objects.create(
            plant=self.plant,
            created_by=self.user,
            task_type='watering',
            title='Water plant',
            priority='high',
            scheduled_date=timezone.now()
        )

        response = self.client.post(
            f'/api/v1/calendar/api/care-tasks/{task.uuid}/mark_complete/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        task.refresh_from_db()
        self.assertTrue(task.completed)
        self.assertIsNotNone(task.completed_at)
        self.assertEqual(task.completed_by, self.user)

    def test_mark_task_skip_action(self):
        """Test mark_skip custom action."""
        self.client.force_authenticate(user=self.user)

        task = CareTask.objects.create(
            plant=self.plant,
            created_by=self.user,
            task_type='watering',
            title='Water plant',
            priority='high',
            scheduled_date=timezone.now()
        )

        data = {'reason': 'Heavy rainfall'}

        response = self.client.post(
            f'/api/v1/calendar/api/care-tasks/{task.uuid}/mark_skip/',
            data
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        task.refresh_from_db()
        self.assertTrue(task.skipped)
        self.assertEqual(task.skip_reason, 'Heavy rainfall')


class HarvestViewSetTest(TestCase):
    """Test HarvestViewSet operations."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='gardener',
            email='gardener@test.com',
            password='testpass123'
        )

        self.bed = GardenBed.objects.create(
            owner=self.user,
            name='Test Bed',
            bed_type='raised'
        )

        self.plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='fruiting',
            planted_date=timezone.now().date() - timedelta(days=60)
        )

        self.client = APIClient()

    def test_create_harvest_record(self):
        """Test creating a harvest record."""
        self.client.force_authenticate(user=self.user)

        data = {
            'plant': str(self.plant.uuid),
            'harvest_date': timezone.now().date().isoformat(),
            'quantity': '3.5',
            'unit': 'lb',
            'quality_rating': 5,
            'notes': 'Excellent first harvest!'
        }

        response = self.client.post('/api/v1/calendar/api/harvests/', data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['quantity'], '3.50')
        self.assertEqual(response.data['unit'], 'lb')
        self.assertEqual(response.data['quality_rating'], 5)

    def test_list_harvests_by_plant(self):
        """Test filtering harvests by plant."""
        self.client.force_authenticate(user=self.user)

        # Create harvests for this plant
        Harvest.objects.create(
            plant=self.plant,
            harvest_date=timezone.now().date(),
            quantity=2.0,
            unit='lb'
        )
        Harvest.objects.create(
            plant=self.plant,
            harvest_date=timezone.now().date() - timedelta(days=3),
            quantity=1.5,
            unit='lb'
        )

        # Create another plant with harvest
        other_plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name='Basil',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=timezone.now().date()
        )
        Harvest.objects.create(
            plant=other_plant,
            harvest_date=timezone.now().date(),
            quantity=0.5,
            unit='oz'
        )

        response = self.client.get(
            f'/api/v1/calendar/api/harvests/?plant={self.plant.uuid}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_delete_harvest_record(self):
        """Test deleting a harvest record."""
        self.client.force_authenticate(user=self.user)

        harvest = Harvest.objects.create(
            plant=self.plant,
            harvest_date=timezone.now().date(),
            quantity=1.0,
            unit='lb'
        )

        response = self.client.delete(
            f'/api/v1/calendar/api/harvests/{harvest.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Harvest.objects.filter(id=harvest.id).exists())
