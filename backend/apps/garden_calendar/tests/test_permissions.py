"""
Permission tests for garden_calendar app.

Tests authorization for all custom permission classes:
- IsGardenOwner
- IsPlantOwner
- IsCareTaskOwner
- IsOwnerOrReadOnly
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from decimal import Decimal

from ..models import GardenBed, Plant, CareTask, CareLog, Harvest

User = get_user_model()


class IsGardenOwnerPermissionTest(TestCase):
    """Test IsGardenOwner permission class."""

    def setUp(self):
        """Set up test users and garden beds."""
        self.client = APIClient()

        # Create two users
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='testpass123'
        )

        # Create garden bed owned by owner
        self.garden_bed = GardenBed.objects.create(
            owner=self.owner,
            name='Test Bed',
            bed_type='raised'
        )

    def test_unauthenticated_cannot_create_bed(self):
        """Test that unauthenticated users cannot create garden beds."""
        response = self.client.post('/api/v1/calendar/api/garden-beds/', {
            'name': 'New Bed',
            'bed_type': 'raised'
        })
        self.assertEqual(response.status_code, 401)

    def test_authenticated_can_create_bed(self):
        """Test that authenticated users can create garden beds."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.post('/api/v1/calendar/api/garden-beds/', {
            'name': 'New Bed',
            'bed_type': 'raised'
        })
        self.assertEqual(response.status_code, 201)

    def test_owner_can_retrieve_bed(self):
        """Test that owners can retrieve their garden beds."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'/api/v1/calendar/api/garden-beds/{self.garden_bed.uuid}/')
        self.assertEqual(response.status_code, 200)

    def test_non_owner_cannot_retrieve_bed(self):
        """Test that non-owners cannot retrieve other users' beds."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f'/api/v1/calendar/api/garden-beds/{self.garden_bed.uuid}/')
        self.assertEqual(response.status_code, 404)

    def test_owner_can_update_bed(self):
        """Test that owners can update their garden beds."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            f'/api/v1/calendar/api/garden-beds/{self.garden_bed.uuid}/',
            {'name': 'Updated Bed'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Updated Bed')

    def test_non_owner_cannot_update_bed(self):
        """Test that non-owners cannot update other users' beds."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.patch(
            f'/api/v1/calendar/api/garden-beds/{self.garden_bed.uuid}/',
            {'name': 'Hacked Bed'}
        )
        self.assertEqual(response.status_code, 404)


class IsPlantOwnerPermissionTest(TestCase):
    """Test IsPlantOwner permission class."""

    def setUp(self):
        """Set up test users, beds, and plants."""
        self.client = APIClient()

        # Create two users
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='testpass123'
        )

        # Create garden beds
        self.owner_bed = GardenBed.objects.create(
            owner=self.owner,
            name='Owner Bed',
            bed_type='raised'
        )
        self.other_bed = GardenBed.objects.create(
            owner=self.other_user,
            name='Other Bed',
            bed_type='raised'
        )

        # Create plants
        self.owner_plant = Plant.objects.create(
            garden_bed=self.owner_bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=timezone.now().date()
        )
        self.other_plant = Plant.objects.create(
            garden_bed=self.other_bed,
            common_name='Pepper',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=timezone.now().date()
        )

    def test_owner_can_retrieve_plant(self):
        """Test that owners can retrieve their plants."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'/api/v1/calendar/api/plants/{self.owner_plant.uuid}/')
        self.assertEqual(response.status_code, 200)

    def test_non_owner_cannot_retrieve_plant(self):
        """Test that non-owners cannot retrieve other users' plants."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f'/api/v1/calendar/api/plants/{self.owner_plant.uuid}/')
        self.assertEqual(response.status_code, 404)

    def test_owner_can_delete_plant(self):
        """Test that owners can delete their plants."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(f'/api/v1/calendar/api/plants/{self.owner_plant.uuid}/')
        self.assertEqual(response.status_code, 204)

    def test_non_owner_cannot_delete_plant(self):
        """Test that non-owners cannot delete other users' plants."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.delete(f'/api/v1/calendar/api/plants/{self.owner_plant.uuid}/')
        self.assertEqual(response.status_code, 404)


class IsPlantOwnerHarvestPermissionTest(TestCase):
    """Test IsPlantOwner permission for Harvest objects."""

    def setUp(self):
        """Set up test users, beds, plants, and harvests."""
        self.client = APIClient()

        # Create two users
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='testpass123'
        )

        # Create garden beds
        self.owner_bed = GardenBed.objects.create(
            owner=self.owner,
            name='Owner Bed',
            bed_type='raised'
        )

        # Create plant
        self.owner_plant = Plant.objects.create(
            garden_bed=self.owner_bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='fruiting',
            planted_date=timezone.now().date()
        )

        # Create harvest
        self.harvest = Harvest.objects.create(
            plant=self.owner_plant,
            harvest_date=timezone.now().date(),
            quantity=5.0,
            unit='lb'
        )

    def test_owner_can_retrieve_harvest(self):
        """Test that owners can retrieve harvests from their plants."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'/api/v1/calendar/api/harvests/{self.harvest.id}/')
        self.assertEqual(response.status_code, 200)

    def test_non_owner_cannot_retrieve_harvest(self):
        """Test that non-owners cannot retrieve harvests from other users' plants."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f'/api/v1/calendar/api/harvests/{self.harvest.id}/')
        self.assertEqual(response.status_code, 404)

    def test_owner_can_delete_harvest(self):
        """Test that owners can delete harvests from their plants."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(f'/api/v1/calendar/api/harvests/{self.harvest.id}/')
        self.assertEqual(response.status_code, 204)

    def test_non_owner_cannot_delete_harvest(self):
        """Test that non-owners cannot delete harvests from other users' plants."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.delete(f'/api/v1/calendar/api/harvests/{self.harvest.id}/')
        self.assertEqual(response.status_code, 404)


class IsCareTaskOwnerPermissionTest(TestCase):
    """Test IsCareTaskOwner permission class."""

    def setUp(self):
        """Set up test users, beds, plants, and care tasks."""
        self.client = APIClient()

        # Create two users
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='testpass123'
        )

        # Create garden bed
        self.owner_bed = GardenBed.objects.create(
            owner=self.owner,
            name='Owner Bed',
            bed_type='raised'
        )

        # Create plant
        self.owner_plant = Plant.objects.create(
            garden_bed=self.owner_bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=timezone.now().date()
        )

        # Create care task
        self.care_task = CareTask.objects.create(
            plant=self.owner_plant,
            created_by=self.owner,
            task_type='watering',
            title='Water tomato',
            priority='high',
            scheduled_date=timezone.now()
        )

    def test_owner_can_retrieve_care_task(self):
        """Test that owners can retrieve care tasks for their plants."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'/api/v1/calendar/api/care-tasks/{self.care_task.uuid}/')
        self.assertEqual(response.status_code, 200)

    def test_non_owner_cannot_retrieve_care_task(self):
        """Test that non-owners cannot retrieve care tasks for other users' plants."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f'/api/v1/calendar/api/care-tasks/{self.care_task.uuid}/')
        self.assertEqual(response.status_code, 404)

    def test_owner_can_mark_task_complete(self):
        """Test that owners can mark their care tasks as complete."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            f'/api/v1/calendar/api/care-tasks/{self.care_task.uuid}/complete/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('message', response.data)
        self.assertIsNotNone(response.data['completed_at'])

    def test_non_owner_cannot_mark_task_complete(self):
        """Test that non-owners cannot mark other users' care tasks as complete."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.post(
            f'/api/v1/calendar/api/care-tasks/{self.care_task.uuid}/complete/'
        )
        self.assertEqual(response.status_code, 404)


class IsCareLogOwnerPermissionTest(TestCase):
    """Test IsPlantOwner permission for CareLog objects."""

    def setUp(self):
        """Set up test users, beds, plants, and care logs."""
        self.client = APIClient()

        # Create two users
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='testpass123'
        )

        # Create garden bed
        self.owner_bed = GardenBed.objects.create(
            owner=self.owner,
            name='Owner Bed',
            bed_type='raised'
        )

        # Create plant
        self.owner_plant = Plant.objects.create(
            garden_bed=self.owner_bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=timezone.now().date()
        )

        # Create care log
        self.care_log = CareLog.objects.create(
            plant=self.owner_plant,
            user=self.owner,
            activity_type='watering',
            notes='Watered plants'
        )

    def test_unauthenticated_cannot_create_care_log(self):
        """Test that unauthenticated users cannot create care logs."""
        response = self.client.post('/api/v1/calendar/api/care-logs/', {
            'plant': str(self.owner_plant.uuid),
            'notes': 'Test log'
        })
        self.assertEqual(response.status_code, 401)

    def test_authenticated_can_create_care_log(self):
        """Test that authenticated users can create care logs for their plants."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.post('/api/v1/calendar/api/care-logs/', {
            'plant': str(self.owner_plant.uuid),
            'activity_type': 'fertilizing',
            'notes': 'Applied fertilizer'
        })
        self.assertEqual(response.status_code, 201)

    def test_owner_can_retrieve_care_log(self):
        """Test that owners can retrieve care logs from their plants."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'/api/v1/calendar/api/care-logs/{self.care_log.uuid}/')
        self.assertEqual(response.status_code, 200)

    def test_non_owner_cannot_retrieve_care_log(self):
        """Test that non-owners cannot retrieve care logs from other users' plants."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f'/api/v1/calendar/api/care-logs/{self.care_log.uuid}/')
        self.assertEqual(response.status_code, 404)

    def test_owner_can_update_care_log(self):
        """Test that owners can update care logs for their plants."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            f'/api/v1/calendar/api/care-logs/{self.care_log.uuid}/',
            {'notes': 'Updated notes'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['notes'], 'Updated notes')

    def test_non_owner_cannot_update_care_log(self):
        """Test that non-owners cannot update care logs from other users' plants."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.patch(
            f'/api/v1/calendar/api/care-logs/{self.care_log.uuid}/',
            {'notes': 'Hacked notes'}
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_can_delete_care_log(self):
        """Test that owners can delete care logs from their plants."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(f'/api/v1/calendar/api/care-logs/{self.care_log.uuid}/')
        self.assertEqual(response.status_code, 204)

    def test_non_owner_cannot_delete_care_log(self):
        """Test that non-owners cannot delete care logs from other users' plants."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.delete(f'/api/v1/calendar/api/care-logs/{self.care_log.uuid}/')
        self.assertEqual(response.status_code, 404)
