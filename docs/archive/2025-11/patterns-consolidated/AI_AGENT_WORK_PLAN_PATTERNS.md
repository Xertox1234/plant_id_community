# AI Agent Work Plan Patterns: Best Practices Guide

**Version**: 1.0
**Last Updated**: November 2, 2025
**Status**: Production-Ready Reference
**Context**: Django 5.2 + DRF + Wagtail 7.0.3 + React 19 + PostgreSQL + Redis

---

## Table of Contents

1. [Overview](#overview)
2. [Work Plan Structure](#work-plan-structure)
3. [Task Decomposition Framework](#task-decomposition-framework)
4. [Acceptance Criteria Patterns](#acceptance-criteria-patterns)
5. [Django Feature Development Checklist](#django-feature-development-checklist)
6. [React Feature Development Checklist](#react-feature-development-checklist)
7. [Test-Driven Development Templates](#test-driven-development-templates)
8. [Code Examples and Pseudo-Code](#code-examples-and-pseudo-code)
9. [Verification and Validation](#verification-and-validation)
10. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)

---

## Overview

### What Makes a Work Plan AI Agent-Executable?

Based on 2024-2025 industry research, effective AI agent work plans share these characteristics:

1. **Autonomous Task Breakdown**: AI agents work best when complex goals are decomposed into atomic, verifiable subtasks
2. **Clear Success Criteria**: Each task must have programmatically testable acceptance criteria
3. **Iterative Feedback Loops**: Plans should incorporate test-verify-adapt cycles
4. **Dependency Management**: Explicit task ordering with clear dependencies
5. **Contextual Constraints**: Environment-specific requirements (database, cache, auth)

### Key Statistics (2024-2025)

- **82%** of organizations plan to integrate AI agents by 2026
- **35%** average productivity gains with enterprise AI agents
- **30%** reduction in operational costs
- **95%+** test coverage recommended for AI-generated code
- **100%** pass rate required before merging to production

---

## Work Plan Structure

### Hierarchical Task Organization

Use the **Atomic Design methodology** adapted for backend/frontend development:

#### Backend (Django + DRF)

```
Feature
├── Models (Data Layer)
│   ├── Model definition
│   ├── Field validators
│   ├── Meta configuration
│   └── Unit tests
├── Services (Business Logic)
│   ├── Service class methods
│   ├── External API integration
│   ├── Caching strategy
│   └── Integration tests
├── Serializers (API Layer)
│   ├── Serializer fields
│   ├── Validation rules
│   ├── Nested relationships
│   └── Serializer tests
├── ViewSets/Views (Endpoint Layer)
│   ├── CRUD operations
│   ├── Permissions
│   ├── Filtering/pagination
│   └── API tests
└── Documentation
    ├── OpenAPI schema
    ├── Usage examples
    └── Error handling
```

#### Frontend (React)

```
Feature
├── Atoms (Smallest Components)
│   ├── Buttons, inputs, labels
│   ├── Unit tests
│   └── Storybook stories
├── Molecules (Component Groups)
│   ├── Forms, cards, dialogs
│   ├── Integration tests
│   └── Accessibility tests
├── Organisms (Complex Components)
│   ├── Navigation, headers, footers
│   ├── State management
│   └── E2E tests
├── Templates (Page Layouts)
│   ├── Layout structure
│   ├── Responsive design
│   └── Visual regression tests
└── Pages (Full Views)
    ├── Route configuration
    ├── Data fetching
    └── Full integration tests
```

### Task State Management

Every task must have one of three states:

| State | Description | Agent Behavior |
|-------|-------------|----------------|
| `pending` | Not started | Listed in plan |
| `in_progress` | Currently executing | Only ONE task at a time |
| `completed` | Successfully verified | Marked with ✓ + test results |

**CRITICAL RULE**: Only mark a task as `completed` when:
- All tests pass (100% pass rate)
- No compilation/linting errors
- Acceptance criteria verified programmatically
- No blockers or unresolved errors

---

## Task Decomposition Framework

### The TDD Cycle for AI Agents

Follow the **Red-Green-Refactor** pattern for every feature:

```
1. RED: Write failing test
   ├── Define expected behavior
   ├── Mock dependencies
   └── Verify test fails (confirms test validity)

2. GREEN: Implement minimum code to pass
   ├── Write simplest solution
   ├── Verify test passes
   └── Commit with passing tests

3. REFACTOR: Improve code quality
   ├── Extract constants
   ├── Add type hints
   ├── Optimize performance
   └── Verify tests still pass
```

### Breaking Down Complex Features

**Example: Implementing a "Plant Diagnosis API"**

#### ❌ BAD (Too Large, Not Testable)

```
Task: Add plant diagnosis feature
```

#### ✅ GOOD (Atomic, Testable)

```
Epic: Plant Diagnosis API

Task 1: Create DiagnosisCard model with UUID primary key
├── Acceptance Criteria:
│   ├── Model has UUID as primary key (not auto-increment ID)
│   ├── Foreign key to PlantIdentification model
│   ├── JSON field for diagnosis_data with validation
│   ├── Migration creates model successfully
│   └── Tests: test_diagnosis_card_creation(), test_uuid_generation()
├── Files to modify:
│   ├── backend/apps/plant_identification/models.py
│   └── backend/apps/plant_identification/test_diagnosis_models.py
└── Verification: python manage.py test apps.plant_identification.test_diagnosis_models --keepdb

Task 2: Create DiagnosisSerializer with nested relationships
├── Acceptance Criteria:
│   ├── Serializer handles UUID lookups (not integer IDs)
│   ├── Read-only nested plant identification data
│   ├── Validates diagnosis_data JSON structure
│   ├── Returns 400 for invalid data
│   └── Tests: test_serializer_valid(), test_serializer_invalid()
├── Files to create:
│   ├── backend/apps/plant_identification/api/diagnosis_serializers.py
│   └── backend/apps/plant_identification/test_diagnosis_api.py
└── Verification: python manage.py test apps.plant_identification.test_diagnosis_api::DiagnosisSerializerTest --keepdb

Task 3: Create DiagnosisViewSet with CRUD operations
├── Acceptance Criteria:
│   ├── GET /api/v1/diagnosis/ returns paginated list
│   ├── GET /api/v1/diagnosis/{uuid}/ returns single record
│   ├── POST /api/v1/diagnosis/ creates new record
│   ├── PUT/PATCH /api/v1/diagnosis/{uuid}/ updates record
│   ├── DELETE /api/v1/diagnosis/{uuid}/ soft-deletes record
│   └── Tests: test_list(), test_retrieve(), test_create(), test_update(), test_delete()
├── Files to create:
│   ├── backend/apps/plant_identification/api/diagnosis_viewsets.py
│   └── backend/apps/plant_identification/urls.py (register routes)
└── Verification: python manage.py test apps.plant_identification.test_diagnosis_api::DiagnosisAPITest --keepdb

Task 4: Add Redis caching layer
├── Acceptance Criteria:
│   ├── Cache GET requests with 15-minute TTL
│   ├── Invalidate cache on POST/PUT/DELETE
│   ├── Log cache hits/misses with [CACHE] prefix
│   ├── Cache key format: diagnosis:{uuid}
│   └── Tests: test_cache_hit(), test_cache_invalidation()
├── Files to modify:
│   ├── backend/apps/plant_identification/api/diagnosis_viewsets.py
│   └── backend/apps/plant_identification/test_diagnosis_api.py
└── Verification: redis-cli MONITOR | grep diagnosis (while running tests)

Task 5: Create React DiagnosisCard component
├── Acceptance Criteria:
│   ├── Displays diagnosis data in card format
│   ├── Shows loading state while fetching
│   ├── Handles error states gracefully
│   ├── Accessible (WCAG 2.2 AA compliant)
│   └── Tests: test_renders_loading(), test_renders_data(), test_renders_error()
├── Files to create:
│   ├── web/src/components/diagnosis/DiagnosisCard.jsx
│   └── web/src/components/diagnosis/DiagnosisCard.test.jsx
└── Verification: npm run test -- DiagnosisCard.test.jsx

Task 6: Add E2E test for full flow
├── Acceptance Criteria:
│   ├── Test creates plant identification
│   ├── Test fetches diagnosis via API
│   ├── Test renders diagnosis in UI
│   ├── Test verifies data persistence
│   └── Test runs in isolated environment
├── Files to create:
│   └── web/tests/e2e/diagnosis-flow.spec.js
└── Verification: npm run test:e2e -- diagnosis-flow.spec.js
```

---

## Acceptance Criteria Patterns

### Template 1: Given-When-Then (BDD Style)

**Best for**: API endpoints, user interactions, state changes

```
Feature: User can create a forum post

Scenario: Authenticated user creates a new forum post
  Given: User is authenticated with valid JWT token
    And: User has permission to post in the target thread
    And: Thread is not locked
  When: User submits POST request to /api/v1/forum/posts/
    With: Valid post data (content, thread_id)
  Then: System creates new ForumPost record
    And: System returns 201 Created with post UUID
    And: System invalidates thread cache
    And: System sends notification to thread subscribers

  Test Coverage:
    - test_create_post_authenticated_success()
    - test_create_post_unauthenticated_fails()
    - test_create_post_locked_thread_fails()
    - test_create_post_invalidates_cache()
```

### Template 2: Checklist Format (Rule-Oriented)

**Best for**: Model validation, configuration, security requirements

```
Feature: DiagnosisCard model validation

Acceptance Criteria:
  [x] Model uses UUID primary key (not auto-increment ID)
  [x] diagnosis_data field is JSONB type (PostgreSQL)
  [x] diagnosis_data validates against schema:
      - Required keys: diagnosis_type, confidence, recommendations
      - confidence is float between 0.0 and 1.0
      - recommendations is array of strings
  [x] created_at auto-populated with timezone-aware datetime
  [x] updated_at auto-updated on save()
  [x] soft_delete() sets is_deleted=True (does not hard delete)
  [x] Database index on (plant_identification_id, created_at)
  [x] Foreign key cascade on delete (CASCADE)

  Test Coverage:
    - test_uuid_primary_key()
    - test_diagnosis_data_validation_valid()
    - test_diagnosis_data_validation_invalid()
    - test_auto_timestamps()
    - test_soft_delete()
    - test_cascade_delete()
```

### Template 3: SMART Criteria (Measurable)

**Best for**: Performance requirements, optimization tasks

```
Feature: Optimize forum thread listing performance

Specific: Reduce database queries for thread list endpoint
Measurable:
  - Before: 150+ queries (N+1 problem)
  - After: ≤5 queries (with select_related/prefetch_related)
Achievable:
  - Use Django Debug Toolbar to measure queries
  - Add select_related('category', 'created_by')
  - Add prefetch_related('posts', 'posts__created_by')
Relevant:
  - Addresses user complaint: "Forum is slow to load"
  - Reduces database load on production server
Testable:
  - Test: test_thread_list_query_count()
  - Assert: assertNumQueries(5)
  - Performance: Response time <100ms (tested with locust)

Acceptance Criteria:
  [x] ThreadViewSet.list() uses select_related() for foreign keys
  [x] ThreadViewSet.list() uses prefetch_related() for reverse relations
  [x] Test suite verifies query count ≤5
  [x] Load test confirms <100ms response time for 1000 concurrent users
  [x] Documentation updated with optimization explanation
```

---

## Django Feature Development Checklist

### Phase 1: Models (Data Layer)

```python
# File: backend/apps/YOUR_APP/models.py

import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from typing import Optional, Dict, Any

class YourModel(models.Model):
    """
    Clear docstring explaining model purpose.

    Relationships:
        - Belongs to: ParentModel (ForeignKey)
        - Has many: ChildModel (reverse relation)

    Indexes:
        - (field1, field2) for common query pattern
    """

    # Task 1.1: Primary key (UUID recommended for distributed systems)
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Task 1.2: Core fields with validators
    name = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(3)],
        help_text="User-facing name"
    )

    # Task 1.3: Foreign keys with explicit on_delete
    parent = models.ForeignKey(
        'ParentModel',
        on_delete=models.CASCADE,  # Explicit cascade
        related_name='children',
        help_text="Parent relationship"
    )

    # Task 1.4: JSON fields with validation (PostgreSQL JSONB)
    metadata = models.JSONField(
        default=dict,
        validators=[validate_metadata_schema],
        help_text="Structured metadata"
    )

    # Task 1.5: Timestamps (auto-managed)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Task 1.6: Soft delete pattern
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Task 1.7: Database optimization
        indexes = [
            models.Index(fields=['parent', 'created_at']),
            models.Index(fields=['name'], name='your_model_name_idx'),
        ]
        ordering = ['-created_at']
        verbose_name = 'Your Model'
        verbose_name_plural = 'Your Models'

    # Task 1.8: Custom methods with type hints
    def soft_delete(self) -> None:
        """Soft delete this record (sets is_deleted=True)."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    # Task 1.9: String representation
    def __str__(self) -> str:
        return f"{self.name} ({self.id})"

# Task 1.10: Model tests
# File: backend/apps/YOUR_APP/test_models.py

from django.test import TestCase
from django.core.exceptions import ValidationError
from .models import YourModel

class YourModelTest(TestCase):
    """Test suite for YourModel."""

    def setUp(self):
        """Create test fixtures."""
        self.parent = ParentModel.objects.create(name="Test Parent")

    def test_model_creation_success(self):
        """Test model creates successfully with valid data."""
        obj = YourModel.objects.create(
            name="Test Name",
            parent=self.parent,
            metadata={"key": "value"}
        )
        self.assertIsInstance(obj.id, uuid.UUID)
        self.assertEqual(obj.name, "Test Name")
        self.assertFalse(obj.is_deleted)

    def test_model_validation_fails_invalid_data(self):
        """Test model validation fails with invalid data."""
        with self.assertRaises(ValidationError):
            obj = YourModel(
                name="AB",  # Too short (min 3 chars)
                parent=self.parent
            )
            obj.full_clean()

    def test_soft_delete_sets_flags(self):
        """Test soft delete sets is_deleted and deleted_at."""
        obj = YourModel.objects.create(name="Test", parent=self.parent)
        obj.soft_delete()
        self.assertTrue(obj.is_deleted)
        self.assertIsNotNone(obj.deleted_at)

    def test_cascade_delete_removes_children(self):
        """Test CASCADE on_delete removes children."""
        obj = YourModel.objects.create(name="Test", parent=self.parent)
        self.parent.delete()
        self.assertFalse(YourModel.objects.filter(id=obj.id).exists())
```

**Verification Command:**
```bash
python manage.py test apps.YOUR_APP.test_models --keepdb -v 2
```

### Phase 2: Serializers (API Layer)

```python
# File: backend/apps/YOUR_APP/api/serializers.py

from rest_framework import serializers
from typing import Dict, Any
from ..models import YourModel

class YourModelSerializer(serializers.ModelSerializer):
    """
    Serializer for YourModel API endpoints.

    Read-only fields:
        - id: UUID (auto-generated)
        - created_at, updated_at: Timestamps

    Nested serializers:
        - parent: Nested read-only representation
    """

    # Task 2.1: Nested serializers (read-only for GET requests)
    parent = ParentSerializer(read_only=True)
    parent_id = serializers.UUIDField(write_only=True)

    # Task 2.2: Custom computed fields
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = YourModel
        fields = [
            'id', 'name', 'parent', 'parent_id',
            'metadata', 'full_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    # Task 2.3: Field-level validation
    def validate_name(self, value: str) -> str:
        """Validate name field (min 3 chars, no special chars)."""
        if len(value) < 3:
            raise serializers.ValidationError(
                "Name must be at least 3 characters"
            )
        if not value.replace(' ', '').isalnum():
            raise serializers.ValidationError(
                "Name can only contain letters, numbers, and spaces"
            )
        return value

    # Task 2.4: Object-level validation
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-field validation."""
        parent_id = attrs.get('parent_id')
        if parent_id and not ParentModel.objects.filter(id=parent_id).exists():
            raise serializers.ValidationError({
                'parent_id': 'Parent with this ID does not exist'
            })
        return attrs

    # Task 2.5: Custom create method
    def create(self, validated_data: Dict[str, Any]) -> YourModel:
        """Create instance with custom logic."""
        parent_id = validated_data.pop('parent_id')
        parent = ParentModel.objects.get(id=parent_id)
        return YourModel.objects.create(parent=parent, **validated_data)

    # Task 2.6: Computed field method
    def get_full_name(self, obj: YourModel) -> str:
        """Compute full name with parent."""
        return f"{obj.parent.name} - {obj.name}"

# Task 2.7: Serializer tests
# File: backend/apps/YOUR_APP/test_serializers.py

from django.test import TestCase
from .api.serializers import YourModelSerializer
from .models import YourModel, ParentModel

class YourModelSerializerTest(TestCase):
    """Test suite for YourModelSerializer."""

    def setUp(self):
        """Create test fixtures."""
        self.parent = ParentModel.objects.create(name="Parent")

    def test_serializer_valid_data_creates_instance(self):
        """Test serializer creates instance with valid data."""
        data = {
            'name': 'Test Name',
            'parent_id': str(self.parent.id),
            'metadata': {'key': 'value'}
        }
        serializer = YourModelSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        instance = serializer.save()
        self.assertEqual(instance.name, 'Test Name')

    def test_serializer_invalid_name_raises_error(self):
        """Test serializer rejects invalid name."""
        data = {
            'name': 'AB',  # Too short
            'parent_id': str(self.parent.id)
        }
        serializer = YourModelSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)

    def test_serializer_nested_parent_read_only(self):
        """Test serializer includes nested parent in output."""
        obj = YourModel.objects.create(name="Test", parent=self.parent)
        serializer = YourModelSerializer(instance=obj)
        self.assertIn('parent', serializer.data)
        self.assertEqual(serializer.data['parent']['name'], 'Parent')
```

**Verification Command:**
```bash
python manage.py test apps.YOUR_APP.test_serializers --keepdb -v 2
```

### Phase 3: ViewSets (Endpoint Layer)

```python
# File: backend/apps/YOUR_APP/api/viewsets.py

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from typing import Any
import logging

from ..models import YourModel
from .serializers import YourModelSerializer

logger = logging.getLogger(__name__)

class YourModelViewSet(viewsets.ModelViewSet):
    """
    API endpoints for YourModel.

    Endpoints:
        GET    /api/v1/your-models/          - List all (paginated)
        POST   /api/v1/your-models/          - Create new
        GET    /api/v1/your-models/{uuid}/   - Retrieve single
        PUT    /api/v1/your-models/{uuid}/   - Update (full)
        PATCH  /api/v1/your-models/{uuid}/   - Update (partial)
        DELETE /api/v1/your-models/{uuid}/   - Soft delete

    Custom actions:
        POST   /api/v1/your-models/{uuid}/restore/ - Restore soft-deleted

    Permissions:
        - Read: Anyone (including anonymous)
        - Write: Authenticated users only

    Caching:
        - GET requests cached for 15 minutes
        - Cache key: your_model:{uuid}
    """

    # Task 3.1: Base configuration
    queryset = YourModel.objects.select_related('parent').filter(is_deleted=False)
    serializer_class = YourModelSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'id'  # UUID lookup

    # Task 3.2: Filtering and search
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter
    ]
    filterset_fields = ['parent_id', 'created_at']
    search_fields = ['name', 'metadata']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']

    # Task 3.3: Optimized queryset (prevent N+1 queries)
    def get_queryset(self):
        """
        Optimize queryset with select_related and prefetch_related.

        Performance:
            - Before: 50+ queries
            - After: 3 queries
        """
        return (
            super()
            .get_queryset()
            .select_related('parent')
            .prefetch_related('related_items')
        )

    # Task 3.4: Retrieve with caching
    def retrieve(self, request, *args, **kwargs) -> Response:
        """
        Retrieve single instance with Redis caching.

        Cache TTL: 15 minutes (900 seconds)
        """
        instance_id = kwargs.get('id')
        cache_key = f"your_model:{instance_id}"

        # Check cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"[CACHE] HIT for {cache_key}")
            return Response(cached_data)

        # Cache miss - fetch from database
        logger.info(f"[CACHE] MISS for {cache_key}")
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # Cache for 15 minutes
        cache.set(cache_key, serializer.data, timeout=900)
        return Response(serializer.data)

    # Task 3.5: Create with cache invalidation
    def create(self, request, *args, **kwargs) -> Response:
        """Create instance and invalidate related caches."""
        response = super().create(request, *args, **kwargs)

        # Invalidate parent's cache
        parent_id = request.data.get('parent_id')
        if parent_id:
            cache.delete(f"parent:{parent_id}:children")
            logger.info(f"[CACHE] Invalidated parent:{parent_id}:children")

        return response

    # Task 3.6: Update with cache invalidation
    def update(self, request, *args, **kwargs) -> Response:
        """Update instance and invalidate cache."""
        response = super().update(request, *args, **kwargs)

        # Invalidate this object's cache
        instance_id = kwargs.get('id')
        cache_key = f"your_model:{instance_id}"
        cache.delete(cache_key)
        logger.info(f"[CACHE] Invalidated {cache_key}")

        return response

    # Task 3.7: Soft delete (override destroy)
    def destroy(self, request, *args, **kwargs) -> Response:
        """
        Soft delete instance (sets is_deleted=True).

        Returns 204 No Content on success.
        """
        instance = self.get_object()
        instance.soft_delete()

        # Invalidate cache
        cache_key = f"your_model:{instance.id}"
        cache.delete(cache_key)
        logger.info(f"[CACHE] Invalidated {cache_key} (soft deleted)")

        return Response(status=status.HTTP_204_NO_CONTENT)

    # Task 3.8: Custom action (restore soft-deleted)
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def restore(self, request, id=None) -> Response:
        """
        Restore a soft-deleted instance.

        Requires authentication.
        """
        try:
            instance = YourModel.objects.get(id=id, is_deleted=True)
            instance.is_deleted = False
            instance.deleted_at = None
            instance.save(update_fields=['is_deleted', 'deleted_at'])

            serializer = self.get_serializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except YourModel.DoesNotExist:
            return Response(
                {'error': 'Object not found or not deleted'},
                status=status.HTTP_404_NOT_FOUND
            )

# Task 3.9: URL configuration
# File: backend/apps/YOUR_APP/urls.py

from rest_framework.routers import DefaultRouter
from .api.viewsets import YourModelViewSet

router = DefaultRouter()
router.register(r'your-models', YourModelViewSet, basename='yourmodel')

urlpatterns = router.urls

# Task 3.10: API tests
# File: backend/apps/YOUR_APP/test_api.py

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import YourModel, ParentModel

User = get_user_model()

class YourModelAPITest(TestCase):
    """Test suite for YourModel API endpoints."""

    def setUp(self):
        """Create test fixtures and authenticate client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.parent = ParentModel.objects.create(name="Test Parent")
        self.client.force_authenticate(user=self.user)

    def test_list_returns_200_and_paginated_results(self):
        """Test GET /api/v1/your-models/ returns paginated list."""
        # Create test data
        YourModel.objects.create(name="Test 1", parent=self.parent)
        YourModel.objects.create(name="Test 2", parent=self.parent)

        url = reverse('yourmodel-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 2)

    def test_create_authenticated_returns_201(self):
        """Test POST /api/v1/your-models/ creates instance."""
        url = reverse('yourmodel-list')
        data = {
            'name': 'New Test',
            'parent_id': str(self.parent.id),
            'metadata': {'key': 'value'}
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Test')
        self.assertTrue(YourModel.objects.filter(name='New Test').exists())

    def test_create_unauthenticated_returns_401(self):
        """Test POST /api/v1/your-models/ fails without auth."""
        self.client.force_authenticate(user=None)

        url = reverse('yourmodel-list')
        data = {'name': 'New Test', 'parent_id': str(self.parent.id)}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_returns_200_with_nested_data(self):
        """Test GET /api/v1/your-models/{uuid}/ returns instance."""
        obj = YourModel.objects.create(name="Test", parent=self.parent)

        url = reverse('yourmodel-detail', kwargs={'id': str(obj.id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test')
        self.assertIn('parent', response.data)

    def test_update_returns_200_and_updates_instance(self):
        """Test PUT /api/v1/your-models/{uuid}/ updates instance."""
        obj = YourModel.objects.create(name="Test", parent=self.parent)

        url = reverse('yourmodel-detail', kwargs={'id': str(obj.id)})
        data = {
            'name': 'Updated Name',
            'parent_id': str(self.parent.id),
            'metadata': {}
        }
        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        obj.refresh_from_db()
        self.assertEqual(obj.name, 'Updated Name')

    def test_partial_update_returns_200(self):
        """Test PATCH /api/v1/your-models/{uuid}/ partially updates."""
        obj = YourModel.objects.create(name="Test", parent=self.parent)

        url = reverse('yourmodel-detail', kwargs={'id': str(obj.id)})
        data = {'name': 'Patched Name'}
        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        obj.refresh_from_db()
        self.assertEqual(obj.name, 'Patched Name')

    def test_delete_soft_deletes_instance(self):
        """Test DELETE /api/v1/your-models/{uuid}/ soft-deletes."""
        obj = YourModel.objects.create(name="Test", parent=self.parent)

        url = reverse('yourmodel-detail', kwargs={'id': str(obj.id)})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        obj.refresh_from_db()
        self.assertTrue(obj.is_deleted)
        self.assertIsNotNone(obj.deleted_at)

    def test_restore_action_restores_soft_deleted(self):
        """Test POST /api/v1/your-models/{uuid}/restore/ restores."""
        obj = YourModel.objects.create(name="Test", parent=self.parent)
        obj.soft_delete()

        url = reverse('yourmodel-restore', kwargs={'id': str(obj.id)})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        obj.refresh_from_db()
        self.assertFalse(obj.is_deleted)

    def test_search_filters_by_name(self):
        """Test GET /api/v1/your-models/?search=keyword filters."""
        YourModel.objects.create(name="Apple", parent=self.parent)
        YourModel.objects.create(name="Banana", parent=self.parent)

        url = reverse('yourmodel-list')
        response = self.client.get(url, {'search': 'Apple'})

        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Apple')

    def test_queryset_optimized_no_n_plus_1(self):
        """Test list endpoint doesn't cause N+1 queries."""
        from django.test.utils import override_settings
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        # Create test data
        for i in range(10):
            YourModel.objects.create(name=f"Test {i}", parent=self.parent)

        url = reverse('yourmodel-list')

        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url)

        # Should be ≤5 queries (not 10+ for N+1)
        self.assertLessEqual(len(context.captured_queries), 5)
```

**Verification Command:**
```bash
python manage.py test apps.YOUR_APP.test_api --keepdb -v 2
```

---

## React Feature Development Checklist

### Phase 1: Atomic Components (Atoms)

```javascript
// File: web/src/components/atoms/Button.jsx

import PropTypes from 'prop-types';
import { forwardRef } from 'react';

/**
 * Reusable button component with consistent styling.
 *
 * Variants:
 *   - primary: Main call-to-action
 *   - secondary: Secondary actions
 *   - danger: Destructive actions
 *
 * Accessibility:
 *   - Keyboard navigable (tabindex)
 *   - Screen reader friendly (aria-label)
 *   - Focus visible (outline)
 */
const Button = forwardRef(({
  children,
  variant = 'primary',
  disabled = false,
  loading = false,
  onClick,
  type = 'button',
  className = '',
  ariaLabel,
  ...props
}, ref) => {
  // Task 1.1: Define variant styles
  const variants = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white',
    secondary: 'bg-gray-200 hover:bg-gray-300 text-gray-900',
    danger: 'bg-red-600 hover:bg-red-700 text-white',
  };

  // Task 1.2: Handle disabled/loading states
  const baseClasses = 'px-4 py-2 rounded font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2';
  const variantClasses = variants[variant] || variants.primary;
  const disabledClasses = disabled || loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer';

  const allClasses = `${baseClasses} ${variantClasses} ${disabledClasses} ${className}`;

  // Task 1.3: Handle click with loading state
  const handleClick = (e) => {
    if (disabled || loading) {
      e.preventDefault();
      return;
    }
    onClick?.(e);
  };

  return (
    <button
      ref={ref}
      type={type}
      className={allClasses}
      disabled={disabled || loading}
      onClick={handleClick}
      aria-label={ariaLabel || children}
      aria-busy={loading}
      {...props}
    >
      {loading ? (
        <span className="flex items-center gap-2">
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          Loading...
        </span>
      ) : children}
    </button>
  );
});

Button.displayName = 'Button';

Button.propTypes = {
  children: PropTypes.node.isRequired,
  variant: PropTypes.oneOf(['primary', 'secondary', 'danger']),
  disabled: PropTypes.bool,
  loading: PropTypes.bool,
  onClick: PropTypes.func,
  type: PropTypes.oneOf(['button', 'submit', 'reset']),
  className: PropTypes.string,
  ariaLabel: PropTypes.string,
};

export default Button;

// Task 1.4: Unit tests
// File: web/src/components/atoms/Button.test.jsx

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Button from './Button';

describe('Button', () => {
  it('renders children text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('applies primary variant styles by default', () => {
    render(<Button>Click me</Button>);
    const button = screen.getByRole('button');
    expect(button).toHaveClass('bg-blue-600');
  });

  it('applies secondary variant styles when specified', () => {
    render(<Button variant="secondary">Click me</Button>);
    const button = screen.getByRole('button');
    expect(button).toHaveClass('bg-gray-200');
  });

  it('calls onClick when clicked', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click me</Button>);

    const button = screen.getByRole('button');
    fireEvent.click(button);

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('does not call onClick when disabled', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick} disabled>Click me</Button>);

    const button = screen.getByRole('button');
    fireEvent.click(button);

    expect(handleClick).not.toHaveBeenCalled();
  });

  it('shows loading spinner when loading', () => {
    render(<Button loading>Click me</Button>);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'true');
  });

  it('is keyboard accessible', () => {
    render(<Button>Click me</Button>);
    const button = screen.getByRole('button');

    button.focus();
    expect(button).toHaveFocus();
  });

  it('has proper aria-label', () => {
    render(<Button ariaLabel="Submit form">Submit</Button>);
    expect(screen.getByLabelText('Submit form')).toBeInTheDocument();
  });
});
```

**Verification Command:**
```bash
npm run test -- Button.test.jsx
```

### Phase 2: Molecule Components

```javascript
// File: web/src/components/molecules/FormField.jsx

import PropTypes from 'prop-types';
import { useState } from 'react';

/**
 * Form field with label, input, and error message.
 *
 * Features:
 *   - Floating label animation
 *   - Error state styling
 *   - Accessible (aria-describedby for errors)
 *   - Supports various input types
 */
const FormField = ({
  label,
  name,
  type = 'text',
  value,
  onChange,
  error,
  placeholder,
  required = false,
  disabled = false,
  ...props
}) => {
  const [isFocused, setIsFocused] = useState(false);
  const hasValue = value && value.length > 0;

  // Task 2.1: Dynamic label positioning
  const labelClasses = `
    absolute left-3 transition-all duration-200 pointer-events-none
    ${isFocused || hasValue
      ? '-top-2 text-xs bg-white px-1 text-blue-600'
      : 'top-3 text-gray-500'}
  `;

  // Task 2.2: Error state styling
  const inputClasses = `
    w-full px-3 py-2 border rounded
    focus:outline-none focus:ring-2 focus:ring-blue-500
    ${error ? 'border-red-500 focus:ring-red-500' : 'border-gray-300'}
    ${disabled ? 'bg-gray-100 cursor-not-allowed' : ''}
  `;

  return (
    <div className="mb-4">
      <div className="relative">
        <input
          type={type}
          name={name}
          value={value}
          onChange={onChange}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          required={required}
          disabled={disabled}
          className={inputClasses}
          aria-invalid={!!error}
          aria-describedby={error ? `${name}-error` : undefined}
          {...props}
        />
        <label htmlFor={name} className={labelClasses}>
          {label} {required && <span className="text-red-500">*</span>}
        </label>
      </div>

      {/* Task 2.3: Error message with animation */}
      {error && (
        <p
          id={`${name}-error`}
          className="mt-1 text-sm text-red-600 animate-slide-down"
          role="alert"
        >
          {error}
        </p>
      )}
    </div>
  );
};

FormField.propTypes = {
  label: PropTypes.string.isRequired,
  name: PropTypes.string.isRequired,
  type: PropTypes.string,
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
  error: PropTypes.string,
  placeholder: PropTypes.string,
  required: PropTypes.bool,
  disabled: PropTypes.bool,
};

export default FormField;

// Task 2.4: Integration tests
// File: web/src/components/molecules/FormField.test.jsx

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import FormField from './FormField';

describe('FormField', () => {
  it('renders label and input', () => {
    render(
      <FormField
        label="Email"
        name="email"
        value=""
        onChange={vi.fn()}
      />
    );

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it('shows error message when error prop provided', () => {
    render(
      <FormField
        label="Email"
        name="email"
        value=""
        onChange={vi.fn()}
        error="Invalid email format"
      />
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Invalid email format');
    expect(screen.getByLabelText(/email/i)).toHaveAttribute('aria-invalid', 'true');
  });

  it('calls onChange when input value changes', () => {
    const handleChange = vi.fn();
    render(
      <FormField
        label="Email"
        name="email"
        value=""
        onChange={handleChange}
      />
    );

    const input = screen.getByLabelText(/email/i);
    fireEvent.change(input, { target: { value: 'test@example.com' } });

    expect(handleChange).toHaveBeenCalled();
  });

  it('shows required asterisk when required', () => {
    render(
      <FormField
        label="Email"
        name="email"
        value=""
        onChange={vi.fn()}
        required
      />
    );

    expect(screen.getByText('*')).toBeInTheDocument();
  });

  it('disables input when disabled prop is true', () => {
    render(
      <FormField
        label="Email"
        name="email"
        value=""
        onChange={vi.fn()}
        disabled
      />
    );

    expect(screen.getByLabelText(/email/i)).toBeDisabled();
  });
});
```

### Phase 3: API Service Layer

```javascript
// File: web/src/services/yourModelService.js

import axios from 'axios';
import logger from '../utils/logger';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_VERSION = 'v1';

/**
 * Service for YourModel API interactions.
 *
 * Features:
 *   - Centralized error handling
 *   - Request/response logging
 *   - JWT token injection
 *   - Request cancellation support
 */
class YourModelService {
  constructor() {
    // Task 3.1: Configure axios instance
    this.client = axios.create({
      baseURL: `${API_BASE_URL}/api/${API_VERSION}`,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Task 3.2: Request interceptor (add JWT token)
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        logger.info(`[API] ${config.method.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => {
        logger.error('[API] Request error:', error);
        return Promise.reject(error);
      }
    );

    // Task 3.3: Response interceptor (error handling)
    this.client.interceptors.response.use(
      (response) => {
        logger.info(`[API] ${response.status} ${response.config.url}`);
        return response;
      },
      async (error) => {
        const originalRequest = error.config;

        // Handle 401 Unauthorized (token expired)
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            const refreshToken = localStorage.getItem('refresh_token');
            const response = await axios.post(
              `${API_BASE_URL}/api/token/refresh/`,
              { refresh: refreshToken }
            );

            const { access } = response.data;
            localStorage.setItem('access_token', access);

            originalRequest.headers.Authorization = `Bearer ${access}`;
            return this.client(originalRequest);
          } catch (refreshError) {
            logger.error('[API] Token refresh failed:', refreshError);
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        logger.error('[API] Response error:', error.response?.data || error.message);
        return Promise.reject(error);
      }
    );
  }

  // Task 3.4: List method with query params
  async list(params = {}) {
    try {
      const response = await this.client.get('/your-models/', { params });
      return response.data;
    } catch (error) {
      throw this._handleError(error, 'Failed to fetch list');
    }
  }

  // Task 3.5: Retrieve method
  async retrieve(id) {
    try {
      const response = await this.client.get(`/your-models/${id}/`);
      return response.data;
    } catch (error) {
      throw this._handleError(error, 'Failed to fetch item');
    }
  }

  // Task 3.6: Create method
  async create(data) {
    try {
      const response = await this.client.post('/your-models/', data);
      return response.data;
    } catch (error) {
      throw this._handleError(error, 'Failed to create item');
    }
  }

  // Task 3.7: Update method
  async update(id, data) {
    try {
      const response = await this.client.put(`/your-models/${id}/`, data);
      return response.data;
    } catch (error) {
      throw this._handleError(error, 'Failed to update item');
    }
  }

  // Task 3.8: Partial update method
  async partialUpdate(id, data) {
    try {
      const response = await this.client.patch(`/your-models/${id}/`, data);
      return response.data;
    } catch (error) {
      throw this._handleError(error, 'Failed to partially update item');
    }
  }

  // Task 3.9: Delete method
  async delete(id) {
    try {
      await this.client.delete(`/your-models/${id}/`);
      return { success: true };
    } catch (error) {
      throw this._handleError(error, 'Failed to delete item');
    }
  }

  // Task 3.10: Custom action (restore)
  async restore(id) {
    try {
      const response = await this.client.post(`/your-models/${id}/restore/`);
      return response.data;
    } catch (error) {
      throw this._handleError(error, 'Failed to restore item');
    }
  }

  // Task 3.11: Error handling helper
  _handleError(error, defaultMessage) {
    const message = error.response?.data?.detail
      || error.response?.data?.message
      || defaultMessage;

    const statusCode = error.response?.status;
    const errors = error.response?.data;

    return {
      message,
      statusCode,
      errors,
      originalError: error,
    };
  }
}

export default new YourModelService();

// Task 3.12: Service tests (with mocked API)
// File: web/src/services/yourModelService.test.js

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import yourModelService from './yourModelService';

// Mock axios
vi.mock('axios');

describe('YourModelService', () => {
  beforeEach(() => {
    // Clear mocks before each test
    vi.clearAllMocks();

    // Mock axios.create to return mock instance
    axios.create.mockReturnValue({
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      patch: vi.fn(),
      delete: vi.fn(),
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('list() calls GET /your-models/', async () => {
    const mockData = { results: [], count: 0 };
    yourModelService.client.get.mockResolvedValue({ data: mockData });

    const result = await yourModelService.list();

    expect(yourModelService.client.get).toHaveBeenCalledWith('/your-models/', { params: {} });
    expect(result).toEqual(mockData);
  });

  it('retrieve() calls GET /your-models/{id}/', async () => {
    const mockData = { id: '123', name: 'Test' };
    yourModelService.client.get.mockResolvedValue({ data: mockData });

    const result = await yourModelService.retrieve('123');

    expect(yourModelService.client.get).toHaveBeenCalledWith('/your-models/123/');
    expect(result).toEqual(mockData);
  });

  it('create() calls POST /your-models/', async () => {
    const mockData = { id: '123', name: 'Test' };
    const createData = { name: 'Test', parent_id: '456' };
    yourModelService.client.post.mockResolvedValue({ data: mockData });

    const result = await yourModelService.create(createData);

    expect(yourModelService.client.post).toHaveBeenCalledWith('/your-models/', createData);
    expect(result).toEqual(mockData);
  });

  it('handles errors gracefully', async () => {
    const errorResponse = {
      response: {
        status: 400,
        data: { detail: 'Bad request' },
      },
    };
    yourModelService.client.get.mockRejectedValue(errorResponse);

    await expect(yourModelService.retrieve('123')).rejects.toMatchObject({
      message: 'Bad request',
      statusCode: 400,
    });
  });
});
```

---

## Test-Driven Development Templates

### TDD Workflow for Django + React

```
┌─────────────────────────────────────────────────────────────┐
│                    Feature Request                          │
│  "Allow users to save plant diagnoses to their account"    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              PHASE 1: Write Backend Tests (RED)             │
├─────────────────────────────────────────────────────────────┤
│ 1. test_diagnosis_model_creation()          [FAIL]          │
│ 2. test_diagnosis_serializer_valid()        [FAIL]          │
│ 3. test_diagnosis_api_create()              [FAIL]          │
│ 4. test_diagnosis_api_retrieve()            [FAIL]          │
│ 5. test_diagnosis_cache_invalidation()      [FAIL]          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           PHASE 2: Implement Backend (GREEN)                │
├─────────────────────────────────────────────────────────────┤
│ 1. Create DiagnosisCard model                               │
│ 2. Create DiagnosisSerializer                               │
│ 3. Create DiagnosisViewSet                                  │
│ 4. Add caching logic                                        │
│ 5. Run tests → ALL PASS ✓                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              PHASE 3: Refactor Backend                      │
├─────────────────────────────────────────────────────────────┤
│ 1. Extract constants to constants.py                        │
│ 2. Add type hints to all methods                            │
│ 3. Add docstrings                                           │
│ 4. Optimize queries (select_related)                        │
│ 5. Run tests → STILL ALL PASS ✓                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│             PHASE 4: Write Frontend Tests (RED)             │
├─────────────────────────────────────────────────────────────┤
│ 1. test_diagnosis_card_renders()            [FAIL]          │
│ 2. test_diagnosis_form_submits()            [FAIL]          │
│ 3. test_diagnosis_list_displays()           [FAIL]          │
│ 4. test_diagnosis_error_handling()          [FAIL]          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│          PHASE 5: Implement Frontend (GREEN)                │
├─────────────────────────────────────────────────────────────┤
│ 1. Create DiagnosisCard component                           │
│ 2. Create DiagnosisForm component                           │
│ 3. Create DiagnosisList component                           │
│ 4. Create diagnosisService API layer                        │
│ 5. Run tests → ALL PASS ✓                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│             PHASE 6: Refactor Frontend                      │
├─────────────────────────────────────────────────────────────┤
│ 1. Extract reusable hooks (useDiagnosis)                    │
│ 2. Memoize expensive computations                           │
│ 3. Add accessibility attributes                             │
│ 4. Optimize re-renders                                      │
│ 5. Run tests → STILL ALL PASS ✓                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                PHASE 7: Integration E2E Test                │
├─────────────────────────────────────────────────────────────┤
│ 1. Start Django backend (port 8000)                         │
│ 2. Start React frontend (port 5174)                         │
│ 3. Run Playwright test:                                     │
│    - Navigate to /diagnosis                                 │
│    - Fill form and submit                                   │
│    - Verify API call and response                           │
│    - Verify UI updates with new data                        │
│ 4. Test passes → Feature complete ✓                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Code Examples and Pseudo-Code

### Django pytest Fixture Pattern (Factory-as-Fixture)

```python
# File: backend/apps/YOUR_APP/conftest.py

import pytest
from django.contrib.auth import get_user_model
from .models import YourModel, ParentModel

User = get_user_model()

# Task: Create reusable fixtures for tests

@pytest.fixture
def user():
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )

@pytest.fixture
def parent():
    """Create a test parent model."""
    return ParentModel.objects.create(name="Test Parent")

@pytest.fixture
def your_model_factory(parent):
    """
    Factory fixture for creating YourModel instances.

    Usage:
        def test_something(your_model_factory):
            obj1 = your_model_factory(name="Test 1")
            obj2 = your_model_factory(name="Test 2")
    """
    def _create_your_model(**kwargs):
        defaults = {
            'name': 'Test Model',
            'parent': parent,
            'metadata': {'key': 'value'},
        }
        defaults.update(kwargs)
        return YourModel.objects.create(**defaults)

    return _create_your_model

@pytest.fixture
def api_client():
    """Create an authenticated API client."""
    from rest_framework.test import APIClient
    client = APIClient()
    return client

@pytest.fixture
def authenticated_client(api_client, user):
    """Create an authenticated API client with user."""
    api_client.force_authenticate(user=user)
    return api_client

# Usage in tests:
# File: backend/apps/YOUR_APP/test_api.py

import pytest
from django.urls import reverse
from rest_framework import status

@pytest.mark.django_db
class TestYourModelAPI:
    """Test suite for YourModel API."""

    def test_list_returns_200(self, authenticated_client, your_model_factory):
        """Test GET /api/v1/your-models/ returns list."""
        # Create test data using factory
        your_model_factory(name="Test 1")
        your_model_factory(name="Test 2")

        url = reverse('yourmodel-list')
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2

    def test_create_returns_201(self, authenticated_client, parent):
        """Test POST /api/v1/your-models/ creates instance."""
        url = reverse('yourmodel-list')
        data = {
            'name': 'New Test',
            'parent_id': str(parent.id),
            'metadata': {'key': 'value'}
        }

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'New Test'
```

### React Custom Hook Pattern (useFetch)

```javascript
// File: web/src/hooks/useFetch.js

import { useState, useEffect } from 'react';

/**
 * Generic hook for data fetching with loading/error states.
 *
 * Usage:
 *   const { data, loading, error, refetch } = useFetch(
 *     () => diagnosisService.list()
 *   );
 */
function useFetch(fetchFunction, dependencies = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await fetchFunction();
      setData(result);
    } catch (err) {
      setError(err.message || 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, dependencies);

  return { data, loading, error, refetch: fetchData };
}

export default useFetch;

// Usage in component:
// File: web/src/components/diagnosis/DiagnosisList.jsx

import useFetch from '../../hooks/useFetch';
import diagnosisService from '../../services/diagnosisService';

function DiagnosisList() {
  const { data, loading, error, refetch } = useFetch(
    () => diagnosisService.list(),
    []
  );

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message={error} />;

  return (
    <div>
      <button onClick={refetch}>Refresh</button>
      <ul>
        {data?.results.map(item => (
          <li key={item.id}>{item.name}</li>
        ))}
      </ul>
    </div>
  );
}
```

---

## Verification and Validation

### Programmatic Acceptance Criteria Verification

Every task's acceptance criteria must be verifiable through automated tests:

```bash
# Backend Verification Commands

# Run all tests for an app
python manage.py test apps.YOUR_APP --keepdb -v 2

# Run specific test class
python manage.py test apps.YOUR_APP.test_api::YourModelAPITest --keepdb -v 2

# Run specific test method
python manage.py test apps.YOUR_APP.test_api::YourModelAPITest::test_create_returns_201 --keepdb -v 2

# Check test coverage (should be ≥95%)
pytest --cov=apps.YOUR_APP --cov-report=html

# Type checking
mypy apps/YOUR_APP/

# Linting
flake8 apps/YOUR_APP/
black apps/YOUR_APP/ --check

# Check for N+1 queries
python manage.py test apps.YOUR_APP --debug-sql

# Frontend Verification Commands

# Run all tests
npm run test

# Run specific test file
npm run test -- DiagnosisCard.test.jsx

# Run tests in watch mode
npm run test:watch

# Check test coverage (should be ≥95%)
npm run test:coverage

# Linting
npm run lint

# Type checking (if using TypeScript)
npm run type-check

# E2E tests
npm run test:e2e

# E2E tests with UI
npm run test:e2e:ui

# Integration Tests (Full Stack)

# Start backend
cd backend && python manage.py runserver &

# Start frontend
cd web && npm run dev &

# Run E2E tests
cd web && npm run test:e2e

# Check for console errors in browser
npm run test:e2e -- --headed  # Visual mode
```

### Task Completion Checklist

Before marking any task as **completed**, verify:

- [ ] All new tests pass (100% pass rate)
- [ ] No existing tests broken (regression check)
- [ ] Code coverage ≥95% for new code
- [ ] No linting errors
- [ ] No type checking errors (mypy/TypeScript)
- [ ] Documentation updated (docstrings, comments)
- [ ] OpenAPI schema updated (if API changes)
- [ ] Migration files created (if model changes)
- [ ] No console errors/warnings in browser
- [ ] Accessibility checks pass (WCAG 2.2 AA)
- [ ] Performance tests pass (if applicable)
- [ ] Manual smoke test completed
- [ ] Git commit created with descriptive message
- [ ] PR created with acceptance criteria verified

---

## Anti-Patterns to Avoid

### ❌ DON'T: Write vague tasks

```
Bad:
  Task: Fix the forum

Good:
  Task: Fix N+1 query in ThreadViewSet.list()
  ├── Problem: 150+ queries for 50 threads
  ├── Solution: Add select_related('category', 'created_by')
  ├── Expected: ≤5 queries
  └── Test: test_thread_list_query_count()
```

### ❌ DON'T: Skip writing tests first

```
Bad:
  1. Implement feature
  2. Write tests later (maybe)

Good:
  1. Write failing test (RED)
  2. Implement minimum code (GREEN)
  3. Refactor code (REFACTOR)
  4. Verify tests still pass
```

### ❌ DON'T: Use magic numbers

```python
# Bad
cache.set(key, value, 900)  # What is 900?

# Good
from apps.plant_identification.constants import CACHE_TIMEOUT_15_MIN
cache.set(key, value, CACHE_TIMEOUT_15_MIN)  # Clear intent
```

### ❌ DON'T: Commit without running tests

```bash
# Bad
git add .
git commit -m "Added feature"

# Good
python manage.py test --keepdb -v 2  # All tests pass ✓
npm run test                         # All tests pass ✓
npm run lint                         # No errors ✓
git add .
git commit -m "feat: add plant diagnosis API with caching"
```

### ❌ DON'T: Mark tasks as completed with failing tests

```
Bad:
  Task: Implement diagnosis API [COMPLETED]
  └── Tests: 15/20 passing (5 failures) ❌

Good:
  Task: Implement diagnosis API [COMPLETED]
  └── Tests: 20/20 passing ✓
```

### ❌ DON'T: Ignore accessibility

```jsx
// Bad
<button onClick={handleClick}>Submit</button>

// Good
<button
  onClick={handleClick}
  aria-label="Submit diagnosis form"
  type="submit"
>
  Submit
</button>
```

### ❌ DON'T: Hard-code API URLs

```javascript
// Bad
const response = await fetch('http://localhost:8000/api/v1/diagnosis/');

// Good
import diagnosisService from './services/diagnosisService';
const response = await diagnosisService.list();
```

### ❌ DON'T: Use console.log in production code

```javascript
// Bad
console.log('User data:', userData);

// Good
import logger from './utils/logger';
logger.info('[USER] Fetched user data', { userId: userData.id });
```

---

## Summary

### Key Takeaways

1. **Atomic Tasks**: Break features into smallest testable units
2. **Test-First**: Always write tests before implementation (TDD)
3. **Clear Criteria**: Use Given-When-Then or checklist format
4. **Verification**: Every task must have programmatic verification
5. **Type Safety**: Use type hints (Python) and PropTypes (React)
6. **No Magic**: Extract constants, use meaningful names
7. **Accessibility**: WCAG 2.2 AA compliance required
8. **Performance**: Monitor queries, optimize caching
9. **Documentation**: Update docs with code changes
10. **100% Pass Rate**: Never merge with failing tests

### Work Plan Template (Quick Reference)

```
Epic: [Feature Name]

Task 1: [Atomic Task Name]
├── Acceptance Criteria:
│   ├── [Criterion 1]
│   ├── [Criterion 2]
│   └── [Criterion 3]
├── Files to modify/create:
│   ├── [File 1]
│   └── [File 2]
├── Tests:
│   ├── test_[scenario_1]()
│   └── test_[scenario_2]()
└── Verification:
    └── [Command to verify]

Task 2: [Next Atomic Task]
└── ... (same structure)
```

---

## References

### Industry Sources (2024-2025)

- **AI Agents**: IBM Think Guide, Analytics Vidhya Agentic AI Planning
- **Django TDD**: Real Python, TestDriven.io, Medium (Sarthak Kumar, Moh Ferry)
- **React Testing**: Testing Library, Toptal, SitePoint, Redux Documentation
- **Acceptance Criteria**: AltexSoft, Atlassian, ProductPlan, GeeksForGeeks
- **Atomic Design**: Medium (Janelle Wong, Roopal Jasnani), Andela Insights
- **pytest Fixtures**: Real Python, Velotio, pytest-django docs
- **Wagtail Testing**: CFPB Development Guide, Wagtail docs

### Project-Specific Documentation

- `/backend/docs/README.md` - Backend documentation hub
- `AUTHENTICATION_PATTERNS.md` - React+Django auth integration
- `SERVICE_ARCHITECTURE.md` - Service layer patterns
- `DIAGNOSIS_API_PATTERNS_CODIFIED.md` - DRF UUID patterns
- `FORUM_AUTH_FIXES_CODIFIED.md` - Forum debugging guide

---

**Document Version**: 1.0
**Last Updated**: November 2, 2025
**Maintained By**: AI Agent Development Team
**Status**: Production-Ready Reference
