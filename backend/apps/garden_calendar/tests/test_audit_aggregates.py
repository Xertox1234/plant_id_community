"""
Regression tests for the 2026-06-02 audit aggregate rewrites.

These endpoints had NO test coverage, which is how a `Count(<wrong-pk>)`
FieldError shipped (audit C1 regression + C2 pre-existing bug). Each test hits
the real endpoint so a 500 cannot regress unnoticed, and pins the query count so
the Python-loop / per-unit-loop aggregation cannot return (audit M9, M10).
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..models import CareTask, CommunityEvent, EventAttendee, GardenBed, Harvest, Plant

User = get_user_model()


class GardenBedAnalyticsAggregateTest(TestCase):
    """`analytics` action — audit M9 (loop→aggregate) + C1 (`Count("id")` on a
    `uuid`-PK model → FieldError → 500)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="analytics_user",
            email="a@test.com",
            password="testpass123",  # pragma: allowlist secret
        )
        self.client.force_authenticate(user=self.user)
        self.bed = GardenBed.objects.create(
            owner=self.user, name="Bed", bed_type="raised"
        )
        for hs in ("healthy", "healthy", "stressed"):
            Plant.objects.create(
                garden_bed=self.bed,
                common_name="P",
                health_status=hs,
                growth_stage="seedling",
                planted_date=timezone.now().date(),
            )
        plant = self.bed.plants.first()
        CareTask.objects.create(
            plant=plant,
            created_by=self.user,
            task_type="watering",
            title="overdue",
            priority="high",
            scheduled_date=timezone.now() - timedelta(days=1),
        )
        CareTask.objects.create(
            plant=plant,
            created_by=self.user,
            task_type="watering",
            title="future",
            priority="low",
            scheduled_date=timezone.now() + timedelta(days=1),
        )
        self.url = f"/api/v1/calendar/api/garden-beds/{self.bed.uuid}/analytics/"

    def test_analytics_returns_200_with_correct_breakdown(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["health_status_breakdown"], {"healthy": 2, "stressed": 1})
        self.assertEqual(data["care_tasks"]["total"], 2)
        self.assertEqual(data["care_tasks"]["overdue"], 1)

    def test_analytics_query_count_does_not_scale_with_plants(self):
        # Add more plants; query count must stay constant (no per-plant loop).
        for _ in range(5):
            Plant.objects.create(
                garden_bed=self.bed,
                common_name="extra",
                health_status="healthy",
                growth_stage="seedling",
                planted_date=timezone.now().date(),
            )
        # get_object + 2 aggregates; constant, no per-plant loop
        with self.assertNumQueries(3):
            self.client.get(self.url)


class HarvestStatisticsAggregateTest(TestCase):
    """`statistics` action — audit M10 (6 queries→1 aggregate) + C2 (pre-existing
    `Count("uuid")` on `Harvest`, whose PK is `id` → FieldError → 500)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="harvest_user",
            email="h@test.com",
            password="testpass123",  # pragma: allowlist secret
        )
        self.client.force_authenticate(user=self.user)
        self.bed = GardenBed.objects.create(
            owner=self.user, name="Bed", bed_type="raised"
        )
        self.plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name="Tomato",
            health_status="healthy",
            growth_stage="fruiting",
            planted_date=timezone.now().date(),
        )
        for qty in (3, 2):
            Harvest.objects.create(
                plant=self.plant,
                harvest_date=timezone.now().date(),
                quantity=qty,
                unit="count",  # matches the stats key "count"
                quality_rating=4,
            )
        self.url = "/api/v1/calendar/api/harvests/statistics/"

    def test_statistics_returns_200_with_totals(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_harvests"], 2)
        self.assertEqual(float(data["total_quantity_by_unit"]["count"]), 5.0)
        self.assertEqual(float(data["average_quality_rating"]), 4.0)

    def test_statistics_query_count_does_not_scale_with_harvests(self):
        for _ in range(5):
            Harvest.objects.create(
                plant=self.plant,
                harvest_date=timezone.now().date(),
                quantity=1,
                unit="count",
                quality_rating=3,
            )
        # 1 combined aggregate + 1 by_plant; constant, no per-unit loop
        with self.assertNumQueries(2):
            self.client.get(self.url)

    def test_statistics_includes_lb_unit(self):
        # Audit C3 regression: the per-unit keys were "lbs"/"bunches" but the
        # model's HARVEST_UNITS codes are "lb"/"bunch", so lb/bunch harvests never
        # appeared in total_quantity_by_unit. Now derived from the model constant.
        Harvest.objects.create(
            plant=self.plant,
            harvest_date=timezone.now().date(),
            quantity=7,
            unit="lb",
            quality_rating=5,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        by_unit = response.json()["total_quantity_by_unit"]
        self.assertIn("lb", by_unit)
        self.assertEqual(float(by_unit["lb"]), 7.0)


class CommunityEventDetailRSVPQueryTest(TestCase):
    """Detail `can_rsvp` reuses the prefetched `attendees` instead of a per-event
    `obj.attendees.get(user=...)` (audit L4)."""

    def setUp(self):
        self.client = APIClient()
        self.viewer = User.objects.create_user(
            username="rsvp_viewer",
            email="v@test.com",
            password="testpass123",  # pragma: allowlist secret
        )
        self.organizer = User.objects.create_user(
            username="rsvp_organizer",
            email="o@test.com",
            password="testpass123",  # pragma: allowlist secret
        )
        self.client.force_authenticate(user=self.viewer)
        self.event = CommunityEvent.objects.create(
            organizer=self.organizer,
            title="Full event",
            description="At capacity",
            start_datetime=timezone.now() + timedelta(days=1),
            privacy_level="public",
            max_attendees=1,
        )
        # Viewer has RSVP'd and the event is now at capacity (spots_remaining == 0)
        # — exactly the branch that previously issued obj.attendees.get(user=...).
        EventAttendee.objects.create(event=self.event, user=self.viewer, status="going")
        self.url = f"/api/v1/calendar/api/events/{self.event.pk}/"

    def test_detail_can_rsvp_resolves_from_prefetch(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        # Viewer already RSVP'd "going" → can_rsvp is False.
        self.assertIs(response.json()["can_rsvp"], False)

    def test_detail_can_rsvp_does_not_issue_extra_query(self):
        # Pin the exact count for the fixed at-capacity + viewer-RSVP'd scenario:
        # can_rsvp reads the prefetched attendees (0 extra queries). A revert to
        # obj.attendees.get(user=...) adds one query and trips this. (Attendee
        # count is fixed at 1; the detail view's attendee→user serialization is a
        # separate pre-existing concern, out of this finding's scope.)
        with self.assertNumQueries(3):
            self.client.get(self.url)
