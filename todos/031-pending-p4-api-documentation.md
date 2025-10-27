---
status: ready
priority: p4
issue_id: "031"
tags: [documentation, api, openapi]
dependencies: []
---

# Add API Documentation (OpenAPI/Swagger)

## Problem

No interactive API documentation. Developers must read code to understand endpoints.

## Findings

**best-practices-researcher**:
- No `/api/docs/` or `/api/swagger/` endpoint
- No OpenAPI (Swagger) schema
- README lists endpoints but no interactive docs
- DRF has built-in schema generation not utilized

**pattern-recognition-specialist**:
- 15+ API endpoints across plant_identification, users, blog
- No standardized request/response documentation
- No example requests in docs

## Proposed Solutions

### Option 1: drf-spectacular (OpenAPI 3.0) (Recommended)
```python
# settings.py
INSTALLED_APPS += ['drf_spectacular']

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Plant ID Community API',
    'DESCRIPTION': 'Plant identification and community platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# urls.py
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns += [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
```

**Pros**: Auto-generated, interactive UI, OpenAPI 3.0 standard
**Cons**: Requires library, docstrings for good descriptions
**Effort**: 4 hours (setup + docstrings)
**Risk**: Low

### Option 2: DRF Built-in Schema Generator
```python
from rest_framework.schemas import get_schema_view

urlpatterns += [
    path('api/schema/', get_schema_view(title='Plant ID API'), name='schema'),
]
```

**Pros**: No extra dependency, built-in
**Cons**: OpenAPI 2.0 (older spec), less feature-rich UI
**Effort**: 2 hours
**Risk**: Very low

### Option 3: Manual Documentation (Markdown)
Create `docs/api/API_REFERENCE.md` with endpoint descriptions

**Pros**: Simple, no code changes
**Cons**: Manually maintained, no interactive testing
**Effort**: 8 hours (comprehensive docs)
**Risk**: High (documentation drift)

## Recommended Action

**Option 1** - drf-spectacular:
1. Install: `pip install drf-spectacular`
2. Configure settings as above
3. Add docstrings to viewsets:
```python
class PlantIdentificationViewSet(viewsets.ViewSet):
    """
    Plant Identification API

    Endpoints:
    - POST /identify/ - Upload image for plant identification
    - GET /history/ - Retrieve identification history
    """

    @extend_schema(
        request=PlantIdentificationSerializer,
        responses={200: PlantResultSerializer},
        description="Identify a plant from an uploaded image"
    )
    def identify(self, request):
        ...
```
4. Deploy and test at `/api/docs/`

## Technical Details

**Current API endpoints** (from grep):
- `/api/v1/plant-identification/identify/` - POST
- `/api/v1/plant-identification/history/` - GET
- `/api/auth/login/` - POST
- `/api/auth/register/` - POST
- `/api/auth/token/refresh/` - POST
- `/api/v2/blog-posts/` - GET
- `/api/v2/blog-posts/{slug}/` - GET
- `/api/v2/blog-categories/` - GET

**Documentation locations**:
- README.md (basic endpoint list)
- CLAUDE.md (developer guidance)
- No interactive API docs

**drf-spectacular features**:
- Auto-generated OpenAPI 3.0 schema
- Swagger UI at `/api/docs/`
- ReDoc UI at `/api/redoc/` (alternative)
- Schema download at `/api/schema/`
- Request/response examples
- Authentication documentation

## Resources

- drf-spectacular: https://drf-spectacular.readthedocs.io/
- OpenAPI 3.0 Specification: https://swagger.io/specification/
- DRF Schema Generation: https://www.django-rest-framework.org/api-guide/schemas/

## Acceptance Criteria

- [ ] Interactive API docs available at `/api/docs/`
- [ ] All endpoints documented with descriptions
- [ ] Request/response schemas auto-generated
- [ ] Authentication methods documented (JWT)
- [ ] Example requests shown in UI
- [ ] Schema downloadable at `/api/schema/`
- [ ] Link to docs in README.md

## Work Log

- 2025-10-25: Issue identified by best-practices-researcher agent

## Notes

**Priority rationale**: P4 (Low) - Developer convenience, not production-critical
**User impact**: Improves developer experience for API consumers
**Maintenance**: Auto-generated docs reduce documentation drift
**Alternative**: Postman collection (less ideal than interactive docs)
