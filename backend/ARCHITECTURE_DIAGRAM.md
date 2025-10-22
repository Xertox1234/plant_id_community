# Plant Community Backend - Architecture Diagrams

This document provides visual representations of the backend architecture.

---

## System Context Diagram (C4 Level 1)

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                     Plant Community System                        │
│                                                                  │
│  ┌────────────────┐         ┌────────────────┐                 │
│  │   React Web    │         │ Flutter Mobile  │                 │
│  │   (Port 5173)  │         │      App        │                 │
│  └────────┬───────┘         └────────┬────────┘                 │
│           │                          │                           │
│           │         HTTP/REST        │                           │
│           └──────────┬───────────────┘                           │
│                      ↓                                           │
│           ┌─────────────────────┐                                │
│           │  Django Backend     │                                │
│           │    (Port 8000)      │                                │
│           │  - REST API (DRF)   │                                │
│           │  - WebSockets       │                                │
│           │  - Celery Tasks     │                                │
│           └──────────┬──────────┘                                │
│                      │                                           │
│        ┌─────────────┼─────────────┬─────────────┐              │
│        ↓             ↓             ↓             ↓              │
│   ┌────────┐   ┌─────────┐   ┌────────┐   ┌──────────┐        │
│   │ Plant  │   │PlantNet │   │ Trefle │   │ OpenAI   │        │
│   │   .id  │   │   API   │   │  API   │   │   API    │        │
│   └────────┘   └─────────┘   └────────┘   └──────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

External Storage:
- PostgreSQL (database)
- Redis (cache + channels)
- Media files (local/S3)
```

---

## Container Diagram (C4 Level 2)

```
┌────────────────────────────────────────────────────────────────────┐
│                         Backend System                              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Web Server Layer                          │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │  │
│  │  │ Gunicorn/    │  │   Daphne     │  │   Static     │      │  │
│  │  │   WSGI       │  │   (ASGI)     │  │   Files      │      │  │
│  │  │ (HTTP/REST)  │  │ (WebSockets) │  │ (WhiteNoise) │      │  │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────────┘      │  │
│  └─────────┼──────────────────┼──────────────────────────────────┘  │
│            │                  │                                     │
│  ┌─────────┼──────────────────┼──────────────────────────────────┐  │
│  │         ↓                  ↓        Django Application        │  │
│  │  ┌────────────────────────────────────────────────────┐      │  │
│  │  │              URL Router + Middleware               │      │  │
│  │  │  - SecurityMiddleware (monitoring)                 │      │  │
│  │  │  - CORS (origin whitelist)                         │      │  │
│  │  │  - CSP (Content Security Policy)                   │      │  │
│  │  │  - Authentication (JWT + Session + OAuth)          │      │  │
│  │  │  - Rate Limiting (django-ratelimit)                │      │  │
│  │  └───────────────────────┬────────────────────────────┘      │  │
│  │                          ↓                                    │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │                Django Apps (Business Logic)             │ │  │
│  │  │                                                         │ │  │
│  │  │  ┌──────────────────┐  ┌──────────────────┐           │ │  │
│  │  │  │ plant_           │  │      users       │           │ │  │
│  │  │  │ identification   │  │ - Custom User    │           │ │  │
│  │  │  │ - Models         │  │ - OAuth adapters │           │ │  │
│  │  │  │ - Services       │  │ - JWT auth       │           │ │  │
│  │  │  │ - ViewSets       │  └──────────────────┘           │ │  │
│  │  │  │ - Consumers      │                                  │ │  │
│  │  │  │ - Tasks          │  ┌──────────────────┐           │ │  │
│  │  │  └──────────────────┘  │      blog        │           │ │  │
│  │  │                        │ - Wagtail CMS    │           │ │  │
│  │  │  ┌──────────────────┐  │ - StreamFields   │           │ │  │
│  │  │  │      core        │  └──────────────────┘           │ │  │
│  │  │  │ - Email service  │                                  │ │  │
│  │  │  │ - Notifications  │  ┌──────────────────┐           │ │  │
│  │  │  │ - Security       │  │ search, calendar │           │ │  │
│  │  │  │ - Validators     │  │ forum_integration│           │ │  │
│  │  │  └──────────────────┘  └──────────────────┘           │ │  │
│  │  └─────────────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  Background Workers                          │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │  │
│  │  │ Celery Worker│  │ Celery Beat  │  │   Flower     │      │  │
│  │  │ (async tasks)│  │ (scheduled)  │  │ (monitoring) │      │  │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────────┘      │  │
│  └─────────┼──────────────────┼──────────────────────────────────┘  │
│            │                  │                                     │
│            └──────────┬───────┘                                     │
│                       ↓                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Data Layer                                │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │  │
│  │  │ PostgreSQL   │  │    Redis     │  │    Media     │      │  │
│  │  │ - Models     │  │ - Cache      │  │ - Uploaded   │      │  │
│  │  │ - Indexes    │  │ - Sessions   │  │   images     │      │  │
│  │  │ - Migrations │  │ - Channels   │  │ - Generated  │      │  │
│  │  │              │  │ - Task queue │  │   content    │      │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘

External Systems:
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Plant.id   │  │   PlantNet   │  │    Trefle    │  │   Sentry     │
│ (identify)   │  │  (species)   │  │  (enrich)    │  │  (errors)    │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

---

## Component Diagram: Plant Identification (C4 Level 3)

```
┌──────────────────────────────────────────────────────────────────────┐
│          apps/plant_identification - Component Architecture          │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  API Layer (Presentation)                    │   │
│  │                                                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │
│  │  │   ViewSets   │  │ Function     │  │  WebSocket       │  │   │
│  │  │ (DRF CRUD)   │  │ Based Views  │  │  Consumer        │  │   │
│  │  │              │  │ (identify)   │  │ (real-time)      │  │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────────┘  │   │
│  └─────────┼──────────────────┼──────────────────┼──────────────┘   │
│            │                  │                  │                   │
│            └──────────────────┼──────────────────┘                   │
│                               ↓                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Service Layer (Business Logic)                  │   │
│  │                                                               │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │   CombinedPlantIdentificationService (Facade)       │    │   │
│  │  │   - Orchestrates parallel API calls                 │    │   │
│  │  │   - Merges results from multiple sources            │    │   │
│  │  │   - Uses ThreadPoolExecutor singleton               │    │   │
│  │  └───────────────┬──────────────┬──────────────────────┘    │   │
│  │                  ↓              ↓                            │   │
│  │  ┌───────────────────────┐  ┌───────────────────────┐      │   │
│  │  │ PlantIDAPIService     │  │ PlantNetAPIService    │      │   │
│  │  │ - SHA-256 image hash  │  │ - Region-based       │      │   │
│  │  │ - Redis caching (30m) │  │   project selection  │      │   │
│  │  │ - Disease detection   │  │ - Redis caching (24h)│      │   │
│  │  │ - Timeout: 35s        │  │ - Timeout: 20s       │      │   │
│  │  └───────────────────────┘  └───────────────────────┘      │   │
│  │                                                               │   │
│  │  ┌───────────────────────┐  ┌───────────────────────┐      │   │
│  │  │ SpeciesLookupService  │  │ DiseaseDiagnosisServ  │      │   │
│  │  │ - Local-first lookup  │  │ - Plant.health API   │      │   │
│  │  │ - API fallback        │  │ - Treatment plans    │      │   │
│  │  └───────────────────────┘  └───────────────────────┘      │   │
│  │                                                               │   │
│  │  ┌───────────────────────┐  ┌───────────────────────┐      │   │
│  │  │ TrefleService         │  │ AIServices           │      │   │
│  │  │ - Species enrichment  │  │ - Care instructions  │      │   │
│  │  │ - Botanical data      │  │ - Image generation   │      │   │
│  │  └───────────────────────┘  └───────────────────────┘      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                 Data Access Layer (ORM)                      │   │
│  │                                                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │
│  │  │ PlantSpecies │  │ Identification│  │  UserPlant   │      │   │
│  │  │   Model      │  │ Request/Result│  │    Model     │      │   │
│  │  │              │  │   Models      │  │              │      │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │   │
│  │                                                               │   │
│  │  Indexes (migration 0012):                                   │   │
│  │  - idx_request_user_created                                  │   │
│  │  - idx_result_confidence                                     │   │
│  │  - idx_species_popularity                                    │   │
│  │  GIN Indexes (migration 0013):                               │   │
│  │  - idx_species_trgm (fuzzy search)                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │               Async Processing (Celery)                      │   │
│  │                                                               │   │
│  │  ┌──────────────────────────────────────────────────────┐   │   │
│  │  │  run_identification task                             │   │   │
│  │  │  - Queues long-running identifications              │   │   │
│  │  │  - Emits progress via WebSocket                     │   │   │
│  │  │  - Auto-retry with exponential backoff              │   │   │
│  │  │  - Rate limit: 100/hour                             │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Sequence Diagram: Plant Identification Flow

```
User          React App       Django API        Combined         Plant.id    PlantNet
│                │                │            Service             API         API
│                │                │                │                │           │
│─ Upload────────>│                │                │                │           │
│   Image        │                │                │                │           │
│                │                │                │                │           │
│                │─ POST /identify/>               │                │           │
│                │   (multipart)  │                │                │           │
│                │                │                │                │           │
│                │                │─ validate()    │                │           │
│                │                │  check size,   │                │           │
│                │                │  file type     │                │           │
│                │                │                │                │           │
│                │                │─ identify_────>│                │           │
│                │                │   plant()      │                │           │
│                │                │                │                │           │
│                │                │                │─ SHA-256 hash──>           │
│                │                │                │  check cache   │           │
│                │                │                │                │           │
│                │                │                │─ ThreadPool────┼───────────┤
│                │                │                │  .submit()     │           │
│                │                │                │                │           │
│                │                │                │        ┌───────┴───────────┴──┐
│                │                │                │        │ PARALLEL EXECUTION   │
│                │                │                │        │ (saves 60% time)     │
│                │                │                │        └───────┬───────────┬──┘
│                │                │                │                │           │
│                │                │                │<── response────┤           │
│                │                │                │    (2-5s)      │           │
│                │                │                │                │           │
│                │                │                │<── response────────────────┤
│                │                │                │    (2-4s)                  │
│                │                │                │                            │
│                │                │                │─ cache results─>           │
│                │                │                │  (24h TTL)                 │
│                │                │                │                            │
│                │                │                │─ merge_results()           │
│                │                │                │  prioritize                │
│                │                │                │  Plant.id                  │
│                │                │                │                            │
│                │                │<── combined────┤                            │
│                │                │    response    │                            │
│                │                │                │                            │
│                │<── 200 OK──────┤                │                            │
│                │   {plant_name, │                │                            │
│                │    suggestions,│                │                            │
│                │    care_info}  │                │                            │
│                │                │                │                            │
│<── Display─────┤                │                │                            │
│    Results     │                │                │                            │
│                │                │                │                            │

Note: Cache hit path (40% of requests):
      identify_plant() → check cache → instant return (<10ms)
```

---

## Data Flow Diagram: Caching Strategy

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Request Flow with Caching                        │
└──────────────────────────────────────────────────────────────────────┘

Request arrives
     │
     ↓
┌─────────────────┐
│ Generate cache  │ SHA-256(image) + API_VERSION + params
│ key             │ → "plant_id:v3:abc123...:true"
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Check Redis     │◄───────────────┐
│ cache.get(key)  │                │
└────────┬────────┘                │
         │                         │
    ┌────┴────┐                    │
    │ Found?  │                    │
    └────┬────┘                    │
         │                         │
    ┌────┴─────┬─────────┐         │
    │          │         │         │
   YES        NO         │         │
    │          │         │         │
    ↓          ↓         │         │
┌────────┐ ┌──────────┐ │         │
│ Return │ │ Call API │ │         │
│ cached │ │ (2-5s)   │ │         │
│ result │ │          │ │         │
│ <10ms  │ └────┬─────┘ │         │
└────────┘      │        │         │
                ↓        │         │
         ┌─────────────┐ │         │
         │ Store in    │ │         │
         │ Redis       │─┴─────────┘
         │ cache.set() │ TTL: 24h
         │ (key,result)│
         └─────────────┘

Cache Hit Rate Tracking:
┌────────────────────────────────────────┐
│ Metrics stored in Redis:               │
│ - cache:hits                           │
│ - cache:misses                         │
│ - cache:hit_rate (calculated)          │
│                                        │
│ Week 2 Performance:                    │
│ - Hit rate: 40%                        │
│ - Avg response (hit): <10ms            │
│ - Avg response (miss): 2-5s            │
│ - Improvement: 100x on cache hits      │
└────────────────────────────────────────┘
```

---

## Deployment Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Production Deployment                            │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Load Balancer (nginx)                    │    │
│  │  - SSL termination                                          │    │
│  │  - Rate limiting (IP-based)                                 │    │
│  │  - Static file caching                                      │    │
│  └─────────────────────────┬───────────────────────────────────┘    │
│                            │                                         │
│            ┌───────────────┼───────────────┐                         │
│            │               │               │                         │
│            ↓               ↓               ↓                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Gunicorn 1  │  │  Gunicorn 2  │  │  Gunicorn N  │              │
│  │  (WSGI)      │  │  (WSGI)      │  │  (WSGI)      │              │
│  │  - 4 workers │  │  - 4 workers │  │  - 4 workers │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Daphne 1    │  │  Daphne 2    │  │  Daphne N    │              │
│  │  (ASGI)      │  │  (ASGI)      │  │  (ASGI)      │              │
│  │  - WebSocket │  │  - WebSocket │  │  - WebSocket │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│          │                 │                 │                       │
│          └─────────────────┼─────────────────┘                       │
│                            │                                         │
│                            ↓                                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                      Redis Cluster                           │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │
│  │  │   Master     │  │   Replica 1  │  │   Replica 2  │      │   │
│  │  │  - Cache     │  │  - Failover  │  │  - Failover  │      │   │
│  │  │  - Sessions  │  │              │  │              │      │   │
│  │  │  - Channels  │  │              │  │              │      │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   PostgreSQL Cluster                         │   │
│  │  ┌──────────────┐                  ┌──────────────┐         │   │
│  │  │   Primary    │──replication────>│   Standby    │         │   │
│  │  │  (write)     │                  │  (read-only) │         │   │
│  │  └──────────────┘                  └──────────────┘         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Celery Workers                            │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │
│  │  │   Worker 1   │  │   Worker 2   │  │   Worker N   │      │   │
│  │  │  - Fast lane │  │  - Slow lane │  │  - Priority  │      │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │   │
│  │                                                               │   │
│  │  ┌──────────────┐                                            │   │
│  │  │ Celery Beat  │  (Scheduled tasks)                        │   │
│  │  └──────────────┘                                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Media Storage                             │   │
│  │  ┌──────────────┐              ┌──────────────┐             │   │
│  │  │  S3/Cloud    │──CDN────────>│  CloudFront  │             │   │
│  │  │  Storage     │              │  (Edge cache)│             │   │
│  │  └──────────────┘              └──────────────┘             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  Monitoring & Logging                        │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │
│  │  │   Sentry     │  │  Prometheus  │  │  Grafana     │      │   │
│  │  │  (errors)    │  │  (metrics)   │  │ (dashboards) │      │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Architectural Decision Records (ADR) Summary

### ADR-001: Multi-App Architecture
**Decision**: Split backend into focused Django apps
**Rationale**: Separation of concerns, modularity, team scalability
**Status**: Implemented ✅

### ADR-002: Dual API Integration
**Decision**: Use both Plant.id and PlantNet for identification
**Rationale**: Maximize accuracy, control costs, redundancy
**Status**: Implemented ✅

### ADR-003: Parallel API Processing
**Decision**: Call external APIs in parallel using ThreadPoolExecutor
**Rationale**: 60% performance improvement (4-9s → 2-5s)
**Status**: Implemented ✅ (Week 2)

### ADR-004: Redis for Caching
**Decision**: Use Redis for API response caching
**Rationale**: 40% cache hit rate, instant responses on hits
**Status**: Implemented ✅ (Week 2)

### ADR-005: PostgreSQL with Advanced Indexes
**Decision**: Use PostgreSQL with GIN indexes and trigrams
**Rationale**: Full-text search, 100x query performance improvement
**Status**: Implemented ✅ (Week 2)

### ADR-006: Django Channels for WebSockets
**Decision**: Use Channels for real-time progress updates
**Rationale**: Native Django integration, Redis channel layer
**Status**: Implemented ✅

### ADR-007: Celery for Background Tasks
**Decision**: Use Celery for long-running identifications
**Rationale**: Scalable, retry logic, progress tracking
**Status**: Implemented ✅

### ADR-008: Wagtail CMS Integration
**Decision**: Use Wagtail for blog and editorial content
**Rationale**: Rich content modeling, editorial workflow, Django integration
**Status**: Implemented ✅

### ADR-009: UUID for External References
**Decision**: Use UUIDs instead of integer IDs in APIs
**Rationale**: IDOR prevention, security
**Status**: Implemented ✅

### ADR-010: Service Layer Pattern
**Decision**: Extract business logic to service classes
**Rationale**: Testability, reusability, separation from views
**Status**: Implemented ✅

---

**Document Version**: 1.0
**Last Updated**: October 22, 2025
