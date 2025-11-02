# Work Plan Quick Reference Guide

**For**: AI Agents executing Django + React tasks
**Version**: 1.0
**Last Updated**: November 2, 2025

---

## Task Structure Template

```
Epic: [Feature Name]

Task 1: [Atomic Task - Single Responsibility]
├── Acceptance Criteria (Given-When-Then):
│   Given: [Initial state]
│   When: [Action taken]
│   Then: [Expected outcome]
├── Files: [Exact file paths]
├── Tests: [Test method names]
└── Verify: [Command to run]
```

---

## Django Feature Checklist

### 1. Model Layer (15 min)

```python
# backend/apps/YOUR_APP/models.py

class YourModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    # [Add fields with validators]
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['field1', 'field2'])]
```

**Test**: `python manage.py test apps.YOUR_APP.test_models --keepdb`

### 2. Serializer Layer (20 min)

```python
# backend/apps/YOUR_APP/api/serializers.py

class YourSerializer(serializers.ModelSerializer):
    nested = NestedSerializer(read_only=True)
    nested_id = serializers.UUIDField(write_only=True)

    def validate_field(self, value):
        # [Validation logic]
        return value
```

**Test**: `python manage.py test apps.YOUR_APP.test_serializers --keepdb`

### 3. ViewSet Layer (30 min)

```python
# backend/apps/YOUR_APP/api/viewsets.py

class YourViewSet(viewsets.ModelViewSet):
    queryset = YourModel.objects.select_related('foreign_key')
    serializer_class = YourSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]

    def retrieve(self, request, *args, **kwargs):
        cache_key = f"model:{kwargs['id']}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)
        # [Fetch and cache]
```

**Test**: `python manage.py test apps.YOUR_APP.test_api --keepdb`

---

## React Feature Checklist

### 1. Atom Component (10 min)

```jsx
// web/src/components/atoms/Button.jsx

const Button = ({ variant, loading, onClick, children }) => {
  const variants = {
    primary: 'bg-blue-600 hover:bg-blue-700',
    // ...
  };

  return (
    <button
      className={variants[variant]}
      disabled={loading}
      onClick={onClick}
      aria-busy={loading}
    >
      {loading ? <Spinner /> : children}
    </button>
  );
};
```

**Test**: `npm run test -- Button.test.jsx`

### 2. Service Layer (20 min)

```javascript
// web/src/services/yourService.js

class YourService {
  constructor() {
    this.client = axios.create({
      baseURL: `${API_URL}/api/v1`,
    });
  }

  async list(params) {
    const response = await this.client.get('/your-models/', { params });
    return response.data;
  }
}

export default new YourService();
```

**Test**: `npm run test -- yourService.test.js`

### 3. Page Component (30 min)

```jsx
// web/src/pages/YourPage.jsx

function YourPage() {
  const { data, loading, error } = useFetch(
    () => yourService.list()
  );

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;

  return (
    <div>
      {data?.results.map(item => (
        <YourCard key={item.id} item={item} />
      ))}
    </div>
  );
}
```

**Test**: `npm run test -- YourPage.test.jsx`

---

## Acceptance Criteria Formats

### Format 1: Given-When-Then (BDD)

```
Feature: Create forum post

Scenario: Authenticated user creates post
  Given: User is authenticated
    And: Thread is not locked
  When: User submits POST /api/v1/posts/
  Then: System creates ForumPost
    And: System returns 201 with UUID
    And: System invalidates cache

Tests:
  - test_create_post_success()
  - test_create_post_locked_fails()
```

### Format 2: Checklist (Rules)

```
Feature: Model validation

Acceptance Criteria:
  [x] Uses UUID primary key
  [x] JSON field validates schema
  [x] Auto-populates timestamps
  [x] Soft delete sets is_deleted=True
  [x] Index on (field1, field2)

Tests:
  - test_uuid_generation()
  - test_json_validation()
  - test_soft_delete()
```

### Format 3: SMART (Performance)

```
Feature: Optimize queries

Specific: Reduce N+1 queries
Measurable: 150+ → ≤5 queries
Achievable: Use select_related()
Relevant: Forum load time issue
Testable: assertNumQueries(5)
```

---

## TDD Workflow (5-Step)

```
1. RED:    Write failing test
2. GREEN:  Minimum code to pass
3. REFACTOR: Improve code quality
4. VERIFY:   Tests still pass
5. COMMIT:   Save working state
```

---

## Common Test Patterns

### Django API Test

```python
@pytest.mark.django_db
def test_api_create_returns_201(authenticated_client, parent):
    url = reverse('yourmodel-list')
    data = {'name': 'Test', 'parent_id': str(parent.id)}

    response = authenticated_client.post(url, data, format='json')

    assert response.status_code == 201
    assert response.data['name'] == 'Test'
```

### React Component Test

```javascript
it('renders data when loaded', () => {
  render(<YourComponent data={mockData} />);

  expect(screen.getByText('Expected Text')).toBeInTheDocument();
});

it('calls onClick when clicked', () => {
  const onClick = vi.fn();
  render(<Button onClick={onClick}>Click</Button>);

  fireEvent.click(screen.getByRole('button'));

  expect(onClick).toHaveBeenCalledTimes(1);
});
```

---

## Verification Commands

### Backend

```bash
# All tests
python manage.py test --keepdb -v 2

# Specific app
python manage.py test apps.YOUR_APP --keepdb

# Specific test
python manage.py test apps.YOUR_APP.test_api::TestClass::test_method --keepdb

# Coverage
pytest --cov=apps.YOUR_APP --cov-report=html

# Type check
mypy apps/YOUR_APP/

# Lint
flake8 apps/YOUR_APP/
black apps/YOUR_APP/ --check
```

### Frontend

```bash
# All tests
npm run test

# Specific file
npm run test -- YourComponent.test.jsx

# Watch mode
npm run test:watch

# Coverage
npm run test:coverage

# Lint
npm run lint

# E2E
npm run test:e2e
```

---

## Task Completion Criteria

Only mark task as **COMPLETED** when:

- [ ] All new tests pass (100%)
- [ ] No regressions (existing tests pass)
- [ ] Coverage ≥95%
- [ ] No linting/type errors
- [ ] Documentation updated
- [ ] Manual smoke test passed
- [ ] Acceptance criteria verified

---

## Quick Decision Tree

```
Is this a new feature?
  YES → Start with tests (TDD)
  NO  → Is it a bug?
        YES → Write reproduction test first
        NO  → Is it refactoring?
              YES → Ensure tests pass before/after
              NO  → Document why no tests needed

Does this touch the database?
  YES → Add migration + test migration
  NO  → Continue

Does this expose an API?
  YES → Update OpenAPI schema
  NO  → Continue

Does this affect UI?
  YES → Add accessibility tests
  NO  → Continue

Is performance critical?
  YES → Add performance test (assertNumQueries)
  NO  → Continue

Ready to commit?
  → Run all verification commands
  → Create descriptive commit message
  → Include acceptance criteria in PR
```

---

## Anti-Patterns

| ❌ DON'T | ✅ DO |
|----------|-------|
| Vague task names | Atomic, specific tasks |
| Skip writing tests | Test-first (TDD) |
| Magic numbers | Constants with names |
| console.log() | Structured logging |
| Hard-code URLs | Service layer abstraction |
| Ignore accessibility | WCAG 2.2 compliance |
| Commit without tests | Verify all tests pass |
| Mark complete with failures | 100% pass rate required |

---

## Example: Complete Feature Flow

```
Epic: Add plant diagnosis favorites

Task 1: Create FavoriteDiagnosis model [30 min]
├── AC: UUID primary key, unique (user, diagnosis)
├── Files: models.py, test_models.py
├── Tests: test_favorite_creation(), test_unique_constraint()
└── Verify: python manage.py test apps.plant_identification.test_models --keepdb

Task 2: Create FavoriteDiagnosisSerializer [20 min]
├── AC: Validates diagnosis exists, prevents duplicates
├── Files: api/serializers.py, test_serializers.py
├── Tests: test_valid_data(), test_duplicate_fails()
└── Verify: python manage.py test apps.plant_identification.test_serializers --keepdb

Task 3: Add favorites endpoint to DiagnosisViewSet [40 min]
├── AC: POST /diagnosis/{id}/favorite/ toggles favorite
├── Files: api/viewsets.py, test_api.py
├── Tests: test_favorite_creates(), test_unfavorite_deletes()
└── Verify: python manage.py test apps.plant_identification.test_api --keepdb

Task 4: Create FavoriteButton component [30 min]
├── AC: Shows filled/outline heart, toggles on click
├── Files: FavoriteButton.jsx, FavoriteButton.test.jsx
├── Tests: test_renders_filled(), test_toggles_on_click()
└── Verify: npm run test -- FavoriteButton.test.jsx

Task 5: Integrate favorites in DiagnosisCard [20 min]
├── AC: Shows favorite count, button persists state
├── Files: DiagnosisCard.jsx, DiagnosisCard.test.jsx
├── Tests: test_shows_count(), test_updates_on_favorite()
└── Verify: npm run test -- DiagnosisCard.test.jsx

Task 6: E2E test full flow [30 min]
├── AC: User can favorite/unfavorite diagnosis
├── Files: tests/e2e/diagnosis-favorites.spec.js
├── Tests: Full click-through test
└── Verify: npm run test:e2e -- diagnosis-favorites.spec.js

Total: ~2.5 hours (with 100% test coverage)
```

---

## Resources

- **Full Guide**: `/AI_AGENT_WORK_PLAN_PATTERNS.md`
- **Project Docs**: `/backend/docs/README.md`
- **Auth Patterns**: `/AUTHENTICATION_PATTERNS.md`
- **Service Arch**: `/SERVICE_ARCHITECTURE.md`

---

**Quick Reference Version**: 1.0
**For Full Details**: See `AI_AGENT_WORK_PLAN_PATTERNS.md`
