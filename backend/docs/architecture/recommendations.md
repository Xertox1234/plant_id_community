# Backend Architecture - Recommendations & Roadmap

**Date**: October 22, 2025
**Scope**: Architectural improvements and evolution strategy

---

## Executive Summary

The Plant Community backend has a **solid architectural foundation (Grade A-)** but would benefit from targeted improvements to reach production excellence. This document provides prioritized recommendations organized by impact and effort.

**Quick Wins** (High Impact, Low Effort): Implement first
**Strategic Improvements** (High Impact, High Effort): Plan for Q1 2026
**Nice to Have** (Low Impact, Low Effort): Backlog items

---

## Priority Matrix

```
High Impact │
           │  Circuit        API          Distributed
           │  Breaker      Versioning      Caching
           │    [1]          [2]            [3]
           │
           │  Monitoring    S3 Storage     Queue
           │  Dashboard     Migration    Separation
           │    [4]          [5]           [6]
           │
           │  CSP            GraphQL      ML Model
           │  Reporting      API        Versioning
           │    [7]          [8]           [9]
           │
Low Impact │────────────────────────────────────────
           │  Low Effort            High Effort
```

---

## Quick Wins (Implement in Sprint 1-2)

### [1] Circuit Breaker for External APIs

**Problem**: When Plant.id or PlantNet is down, every request retries and times out (35s wasted per request).

**Solution**: Circuit breaker pattern with state machine:
```
CLOSED → (failures > threshold) → OPEN → (timeout) → HALF_OPEN → (success) → CLOSED
```

**Implementation**:
```python
# Install pybreaker
pip install pybreaker

# apps/plant_identification/services/plant_id_service.py
from pybreaker import CircuitBreaker

plant_id_breaker = CircuitBreaker(
    fail_max=5,           # Open after 5 failures
    timeout_duration=60,  # Stay open for 60 seconds
    name='PlantIDAPI'
)

class PlantIDAPIService:
    @plant_id_breaker
    def identify_plant(self, image_file, include_diseases=True):
        # Existing implementation
        ...
```

**Benefits**:
- Fail fast: No 35s timeout when API is down
- Automatic recovery: Half-open state tests if API is back
- Better UX: Immediate error response instead of long wait

**Effort**: 2-4 hours
**Impact**: Prevents cascading failures, improves response time during outages

---

### [2] Add API Versioning

**Problem**: No version strategy means breaking changes affect all clients immediately.

**Solution**: URL-based versioning:
```python
# OLD (current)
/api/plant-identification/identify/

# NEW (recommended)
/api/v1/plant-identification/identify/
/api/v2/plant-identification/identify/  # Future breaking changes
```

**Implementation**:
```python
# plant_community_backend/urls.py
urlpatterns = [
    # Legacy (redirect to v1)
    path('api/', RedirectView.as_view(url='/api/v1/', permanent=False)),

    # Versioned APIs
    path('api/v1/', include([
        path('auth/', include('apps.users.urls')),
        path('plant-identification/', include('apps.plant_identification.urls')),
        # ... other apps
    ])),

    # Future: v2 with breaking changes
    # path('api/v2/', include('apps.plant_identification.v2_urls')),
]
```

**Migration Strategy**:
1. Week 1: Add `/api/v1/` alongside existing `/api/`
2. Week 2-3: Update mobile apps to use `/api/v1/`
3. Week 4: Deprecate unversioned `/api/` (add warning header)
4. Month 3: Remove unversioned endpoints

**Benefits**:
- Safe to introduce breaking changes
- Gradual client migration
- Industry standard pattern

**Effort**: 4-6 hours
**Impact**: Enables future API evolution without breaking clients

---

### [3] Distributed Lock for Cache Population

**Problem**: Cache stampede - multiple requests can trigger the same expensive API call simultaneously.

**Current Flow**:
```
Request 1: Check cache → MISS → Call API (5s)
Request 2: Check cache → MISS → Call API (5s)  ← Duplicate!
Request 3: Check cache → MISS → Call API (5s)  ← Duplicate!
```

**Solution**: Redis distributed lock:
```python
# apps/plant_identification/services/plant_id_service.py
from django.core.cache import cache
import time

def identify_plant(self, image_file, include_diseases=True):
    cache_key = f"plant_id:{image_hash}:{include_diseases}"
    lock_key = f"lock:{cache_key}"

    # Try to get from cache
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result

    # Try to acquire lock (only one request proceeds)
    lock_acquired = cache.add(lock_key, "1", timeout=30)

    if lock_acquired:
        # This request does the work
        try:
            result = self._call_api(image_file, include_diseases)
            cache.set(cache_key, result, timeout=CACHE_TIMEOUT_24_HOURS)
            return result
        finally:
            cache.delete(lock_key)
    else:
        # Another request is working on it, wait and retry
        for _ in range(30):  # Wait up to 30 seconds
            time.sleep(1)
            result = cache.get(cache_key)
            if result:
                return result

        # Timeout: proceed without lock (fallback)
        return self._call_api(image_file, include_diseases)
```

**Benefits**:
- Prevents duplicate API calls (saves money)
- Reduces load on external APIs
- Better cache efficiency

**Effort**: 3-4 hours
**Impact**: Saves 2-3x API calls during traffic spikes

---

### [4] Enhanced Monitoring Dashboard

**Problem**: No visibility into system health without manual log review.

**Solution**: Prometheus + Grafana stack with custom metrics.

**Metrics to Track**:
```python
# apps/plant_identification/services/monitoring_service.py
from prometheus_client import Counter, Histogram, Gauge

# API call metrics
plant_id_calls = Counter('plant_id_api_calls_total', 'Total Plant.id API calls')
plant_id_errors = Counter('plant_id_api_errors_total', 'Plant.id API errors')
plant_id_duration = Histogram('plant_id_api_duration_seconds', 'Plant.id response time')

# Cache metrics
cache_hits = Counter('cache_hits_total', 'Cache hits')
cache_misses = Counter('cache_misses_total', 'Cache misses')

# Business metrics
identifications_total = Counter('identifications_total', 'Total plant identifications')
identifications_success = Counter('identifications_success_total', 'Successful identifications')
```

**Dashboard Panels**:
1. Request rate (req/s)
2. Response time (p50, p95, p99)
3. Error rate (%)
4. Cache hit rate (%)
5. API usage by provider
6. Active users
7. Database query time
8. Celery queue depth

**Implementation Steps**:
1. Install `django-prometheus` package
2. Add `/metrics` endpoint
3. Configure Prometheus scraping
4. Import Grafana dashboard templates
5. Set up alerting rules

**Effort**: 1-2 days
**Impact**: Proactive incident detection, performance visibility

---

## Strategic Improvements (Plan for Q1 2026)

### [5] Migrate Media Storage to S3

**Problem**: Local filesystem prevents horizontal scaling (can't add more servers).

**Solution**: AWS S3 with CloudFront CDN.

**Architecture**:
```
Upload → Django → S3 Bucket → CloudFront (global CDN)
                     ↓
               S3 Lifecycle Rules:
               - Transition to Glacier after 90 days
               - Delete after 365 days
```

**Implementation**:
```python
# Install boto3
pip install django-storages[boto3]

# settings.py
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_STORAGE_BUCKET_NAME = 'plant-community-media'
AWS_S3_REGION_NAME = 'us-west-2'
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'

# CloudFront (optional, recommended)
AWS_S3_CUSTOM_DOMAIN = 'd123456abcdef.cloudfront.net'
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',  # 24 hours
}
```

**Migration Strategy**:
1. Set up S3 bucket with correct permissions
2. Configure CloudFront distribution
3. Test uploads in staging environment
4. Migrate existing files (`python manage.py migrate_to_s3`)
5. Monitor costs and performance
6. Remove local file storage

**Benefits**:
- Horizontal scaling: Add servers without shared filesystem
- CDN: Faster image delivery globally
- Reliability: 99.999999999% durability
- Cost: Pay-per-use (vs. disk space)

**Costs** (estimated):
- Storage: $0.023/GB/month (~$2-5/month for 100GB)
- Transfer: $0.09/GB (~$10/month for 100GB transfer)
- Requests: $0.005/1000 requests

**Effort**: 3-5 days
**Impact**: Enables horizontal scaling, improves performance

---

### [6] Separate Celery Queues by Priority

**Problem**: Long-running tasks (10-minute plant research) block short tasks (1-second notifications).

**Solution**: Multi-queue architecture with dedicated workers.

**Queue Strategy**:
```python
# celery.py
app.conf.task_routes = {
    # Fast lane (< 5 seconds)
    'apps.users.tasks.send_email': {'queue': 'fast'},
    'apps.core.tasks.send_notification': {'queue': 'fast'},

    # Default lane (5-30 seconds)
    'apps.plant_identification.tasks.run_identification': {'queue': 'default'},

    # Slow lane (> 30 seconds)
    'apps.plant_identification.tasks.batch_identification': {'queue': 'slow'},
    'apps.blog.tasks.generate_ai_content': {'queue': 'slow'},
}

# Priority queue (VIP users)
app.conf.task_routes = {
    'apps.plant_identification.tasks.premium_identification': {
        'queue': 'priority',
        'priority': 10,
    },
}
```

**Worker Configuration**:
```bash
# Fast workers (many, quick restart)
celery -A plant_community_backend worker -Q fast -c 10 --loglevel=info

# Default workers (balanced)
celery -A plant_community_backend worker -Q default -c 4 --loglevel=info

# Slow workers (few, long-running)
celery -A plant_community_backend worker -Q slow -c 2 --loglevel=info --time-limit=600

# Priority workers (reserved capacity)
celery -A plant_community_backend worker -Q priority -c 2 --loglevel=info
```

**Benefits**:
- No head-of-line blocking
- Better resource utilization
- Predictable latency for critical tasks
- Can scale queues independently

**Effort**: 2-3 days (routing + worker config + monitoring)
**Impact**: Improves task processing latency by 50-80%

---

### [7] CSP Violation Reporting

**Problem**: Content Security Policy enforced but no visibility into violations.

**Solution**: CSP reporting endpoint + monitoring.

**Implementation**:
```python
# settings.py (production)
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        # ... existing directives
    },
    'REPORT_URI': '/api/security/csp-report/',
}

# apps/core/views.py
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import logging

logger = logging.getLogger('security.csp')

@csrf_exempt
def csp_report(request):
    """Handle CSP violation reports"""
    if request.method == 'POST':
        try:
            report = json.loads(request.body)

            # Log violation
            logger.warning('CSP Violation', extra={
                'document_uri': report.get('csp-report', {}).get('document-uri'),
                'violated_directive': report.get('csp-report', {}).get('violated-directive'),
                'blocked_uri': report.get('csp-report', {}).get('blocked-uri'),
            })

            # Send to Sentry
            sentry_sdk.capture_message('CSP Violation', level='warning', extra=report)

            return JsonResponse({'status': 'ok'})
        except Exception as e:
            logger.error(f'CSP report parsing error: {e}')
            return JsonResponse({'status': 'error'}, status=400)

    return JsonResponse({'status': 'method not allowed'}, status=405)
```

**Monitoring**:
- Daily reports of top CSP violations
- Alerts for new violation types
- Dashboard showing violation trends

**Benefits**:
- Detect XSS attempts
- Find legitimate CSP issues before users report
- Security posture visibility

**Effort**: 4-6 hours
**Impact**: Improves security monitoring, prevents false positives

---

## Advanced Features (Q2 2026+)

### [8] GraphQL API for Mobile Apps

**Why**: Mobile apps need flexible querying to reduce API calls and over-fetching.

**Benefits**:
- Single request for multiple resources
- Client-specified fields (no over-fetching)
- Strong typing (auto-generated schemas)
- Real-time subscriptions (WebSocket alternative)

**Example Query**:
```graphql
query GetPlantDetails($id: ID!) {
  plant(id: $id) {
    id
    scientificName
    commonNames
    identifications(limit: 5) {
      edges {
        node {
          id
          confidenceScore
          image {
            url
            thumbnailUrl
          }
        }
      }
    }
    careInstructions {
      watering
      light
      temperature
    }
  }
}
```

**Implementation**:
```python
# Install Graphene-Django
pip install graphene-django

# apps/plant_identification/schema.py
import graphene
from graphene_django import DjangoObjectType
from .models import PlantSpecies

class PlantSpeciesType(DjangoObjectType):
    class Meta:
        model = PlantSpecies
        fields = '__all__'

class Query(graphene.ObjectType):
    plant = graphene.Field(PlantSpeciesType, id=graphene.ID())
    plants = graphene.List(PlantSpeciesType)

    def resolve_plant(self, info, id):
        return PlantSpecies.objects.get(pk=id)

    def resolve_plants(self, info):
        return PlantSpecies.objects.all()

schema = graphene.Schema(query=Query)
```

**Effort**: 2-3 weeks
**Impact**: Better mobile UX, reduced API calls

---

### [9] Machine Learning Model Versioning

**Why**: As plant identification models improve, need to track which version was used.

**Solution**: Model registry with versioning + A/B testing framework.

**Architecture**:
```
PlantIdentificationRequest
    ↓
    ├── model_version: "plant_id_v3.0"
    ├── model_confidence: 0.95
    └── model_metadata: {
            "trained_date": "2025-01-15",
            "training_samples": 1000000,
            "accuracy": 0.97
        }
```

**Implementation**:
```python
# apps/plant_identification/models.py
class PlantIdentificationResult(models.Model):
    # ... existing fields

    model_version = models.CharField(max_length=50, default='plant_id_v3.0')
    model_confidence = models.FloatField()
    model_metadata = models.JSONField(default=dict)

    # A/B testing
    experiment_group = models.CharField(
        max_length=20,
        choices=[
            ('control', 'Control (v3.0)'),
            ('variant_a', 'Variant A (v3.1)'),
            ('variant_b', 'Variant B (custom)'),
        ],
        default='control'
    )
```

**A/B Testing Framework**:
```python
from typing import Literal

def select_model_version(user) -> Literal['control', 'variant_a', 'variant_b']:
    """Randomly assign users to experiment groups"""
    user_hash = int(hashlib.sha256(str(user.id).encode()).hexdigest(), 16)
    bucket = user_hash % 100

    if bucket < 10:  # 10% to variant_a
        return 'variant_a'
    elif bucket < 20:  # 10% to variant_b
        return 'variant_b'
    else:  # 80% to control
        return 'control'
```

**Analytics Queries**:
```sql
-- Compare model performance
SELECT
    model_version,
    AVG(confidence_score) as avg_confidence,
    COUNT(*) as total_identifications,
    SUM(CASE WHEN confidence_score > 0.8 THEN 1 ELSE 0 END) / COUNT(*) as high_conf_rate
FROM plant_identification_result
GROUP BY model_version;
```

**Benefits**:
- Data-driven model selection
- A/B testing for new models
- Audit trail for identification decisions
- Performance comparison over time

**Effort**: 1-2 weeks
**Impact**: Enables continuous model improvement

---

## Infrastructure Improvements

### [10] Database Read Replicas

**When**: After reaching 1,000+ concurrent users

**Setup**:
```python
# settings.py
DATABASES = {
    'default': {  # Write operations
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'plant_community',
        'HOST': 'primary.db.internal',
    },
    'replica': {  # Read operations
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'plant_community',
        'HOST': 'replica.db.internal',
    }
}

DATABASE_ROUTERS = ['apps.core.routers.ReadReplicaRouter']
```

**Router**:
```python
# apps/core/routers.py
class ReadReplicaRouter:
    def db_for_read(self, model, **hints):
        return 'replica'

    def db_for_write(self, model, **hints):
        return 'default'
```

**Benefits**:
- Distribute read load (80% of queries)
- Primary database reserved for writes
- Better response times

**Effort**: 1 day (setup) + ongoing maintenance
**Cost**: +$50-100/month for replica

---

### [11] Redis Sentinel for High Availability

**When**: After moving to production

**Setup**:
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': [
            'redis://sentinel1:26379/1',
            'redis://sentinel2:26379/1',
            'redis://sentinel3:26379/1',
        ],
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.SentinelClient',
            'SENTINELS': [
                ('sentinel1', 26379),
                ('sentinel2', 26379),
                ('sentinel3', 26379),
            ],
            'SENTINEL_KWARGS': {
                'password': config('REDIS_PASSWORD'),
            },
        }
    }
}
```

**Benefits**:
- Automatic failover (< 30 seconds)
- No data loss
- 99.9% uptime

**Effort**: 1-2 days
**Cost**: +$30-50/month for sentinel nodes

---

## Architectural Principles Going Forward

### 1. API Design
- ✅ RESTful conventions (verbs, status codes)
- ✅ Versioning (URL-based: `/api/v1/`)
- ✅ Pagination (for all list endpoints)
- ✅ Filtering (django-filter backend)
- ✅ Rate limiting (per endpoint, per user)
- ⚠️ Add: Hypermedia links (HATEOAS)
- ⚠️ Add: GraphQL for complex queries

### 2. Database Design
- ✅ Normalized schema (3NF minimum)
- ✅ Composite indexes for query patterns
- ✅ UUID for external references
- ✅ Audit timestamps (created_at, updated_at)
- ⚠️ Add: Soft deletes (is_deleted flag)
- ⚠️ Add: Change tracking (django-simple-history)

### 3. Caching Strategy
- ✅ Redis for API responses
- ✅ SHA-256 hash keys
- ✅ Appropriate TTLs per service
- ⚠️ Add: Distributed locks (prevent stampede)
- ⚠️ Add: Cache tags (for invalidation)
- ⚠️ Add: Cache warming (pre-populate)

### 4. Security
- ✅ Defense in depth (multiple layers)
- ✅ HTTPS only
- ✅ CSP enforced
- ✅ Rate limiting
- ⚠️ Add: API key authentication
- ⚠️ Add: OAuth scopes (fine-grained permissions)
- ⚠️ Add: Audit logging (who changed what when)

### 5. Observability
- ✅ Structured logging
- ✅ Error tracking (Sentry)
- ⚠️ Add: Metrics (Prometheus)
- ⚠️ Add: Tracing (Jaeger/OpenTelemetry)
- ⚠️ Add: Dashboards (Grafana)

---

## Implementation Roadmap

### Phase 1: Quick Wins (Weeks 1-2)
- [ ] Circuit breaker pattern (2-4 hours)
- [ ] API versioning (4-6 hours)
- [ ] Distributed cache locks (3-4 hours)
- [ ] Monitoring dashboard (1-2 days)

**Outcome**: Improved reliability, better observability

---

### Phase 2: Scaling Prep (Weeks 3-6)
- [ ] S3 media storage migration (3-5 days)
- [ ] Separate Celery queues (2-3 days)
- [ ] CSP violation reporting (4-6 hours)
- [ ] Load testing & optimization (1 week)

**Outcome**: Ready for 10x user growth

---

### Phase 3: Advanced Features (Months 2-3)
- [ ] GraphQL API (2-3 weeks)
- [ ] ML model versioning (1-2 weeks)
- [ ] Database read replicas (1 day)
- [ ] Redis Sentinel HA (1-2 days)

**Outcome**: Enterprise-grade features, 99.9% uptime

---

### Phase 4: Long-Term Evolution (Q2 2026+)
- [ ] Multi-region deployment
- [ ] Real-time collaboration features
- [ ] Advanced ML pipeline
- [ ] Microservices extraction (if needed)

**Outcome**: Global scale, advanced capabilities

---

## Success Metrics

### Performance
- [ ] API response time p95 < 200ms (currently: varies)
- [ ] Plant identification < 3s (currently: 2-5s) ✅ Achieved
- [ ] Cache hit rate > 50% (currently: 40%)
- [ ] Database queries < 10ms (currently: 3-8ms) ✅ Achieved

### Reliability
- [ ] Uptime > 99.9% (three 9's)
- [ ] Error rate < 0.1%
- [ ] Zero data loss incidents
- [ ] Mean time to recovery (MTTR) < 5 minutes

### Scalability
- [ ] Support 10,000 concurrent users
- [ ] Handle 1,000 req/s sustained
- [ ] Process 100,000 identifications/day
- [ ] Scale horizontally without code changes

### Security
- [ ] Zero critical vulnerabilities
- [ ] Automated security scanning (CI/CD)
- [ ] Penetration testing passed
- [ ] GDPR/SOC2 compliance ready

---

## Conclusion

The Plant Community backend has a **strong architectural foundation** with clear paths for improvement. Prioritize:

1. **Quick wins** (circuit breaker, versioning, locks) for immediate reliability gains
2. **S3 migration + queue separation** to enable horizontal scaling
3. **Monitoring dashboard** for operational excellence
4. **GraphQL + ML versioning** for advanced features

Following this roadmap will evolve the system from **production-ready (A-)** to **enterprise-grade (A+)** over the next 3-6 months.

---

**Next Steps**:
1. Review recommendations with team
2. Prioritize based on business needs
3. Create detailed implementation tickets
4. Schedule sprints for Phase 1 quick wins
5. Set up monitoring to track improvements

---

**Document Version**: 1.0
**Last Updated**: October 22, 2025
**Contact**: System Architecture Team
