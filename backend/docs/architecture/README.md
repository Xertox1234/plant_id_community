# System Architecture

This directory contains comprehensive system architecture documentation for the Plant ID Community Django backend.

---

## Documentation

### [Architecture Analysis](./analysis.md)
**Deep dive into system design, patterns, and architectural decisions.**

**Topics:**
- Multi-app Django architecture
- Service layer abstraction patterns
- External API facade pattern
- Real-time capabilities (Django Channels + WebSockets)
- Asynchronous processing (Celery task queue)
- Security middleware stack
- CMS integration (Wagtail)

**Audience:** Backend developers, system architects, technical leads

---

### [Architecture Diagrams](./diagrams.md)
**Visual representations of system components and data flow.**

**Diagrams:**
- High-level system architecture
- Multi-app structure
- API integration patterns
- Database schema relationships
- Request/response flows
- Authentication flows

**Audience:** All technical stakeholders, new team members

---

### [Architecture Summary](./summary.md)
**Executive summary of key architectural decisions and trade-offs.**

**Topics:**
- Technology stack rationale
- Design pattern choices
- Scalability considerations
- Performance optimization strategies
- Security architecture

**Audience:** Technical leads, project managers, architects

---

### [Recommendations](./recommendations.md)
**Future enhancements, best practices, and architectural improvements.**

**Topics:**
- Scalability improvements
- Performance optimizations
- Security enhancements
- Code quality improvements
- DevOps and deployment recommendations

**Audience:** Development team, tech leads, architects

---

## Quick Reference

### Technology Stack

- **Framework:** Django 5.2 LTS + Django REST Framework
- **Database:** PostgreSQL 18 with GIN indexes and trigram search
- **Caching:** Redis for API responses and distributed locks
- **Real-time:** Django Channels + WebSockets (ASGI)
- **CMS:** Wagtail 7.0 LTS
- **Task Queue:** Celery (for async processing)
- **Authentication:** JWT (django-allauth + dj-rest-auth)

### Key Design Patterns

1. **Multi-App Architecture**
   - Pluggable Django apps for domain separation
   - Clean boundaries between features
   - Reusable components

2. **Service Layer Pattern**
   - Business logic abstracted from views
   - External API facades
   - Testable, maintainable code

3. **Repository Pattern**
   - Data access abstraction
   - Centralized query logic
   - Database independence

4. **Event-Driven Architecture**
   - Django signals for cross-app communication
   - Celery tasks for background processing
   - WebSocket events for real-time updates

### System Components

```
Plant ID Community Backend
├── Multi-App Structure
│   ├── plant_identification (Core - AI plant ID)
│   ├── users (Authentication + OAuth)
│   ├── blog (Wagtail CMS)
│   ├── core (Shared services)
│   ├── search (Unified search)
│   ├── garden_calendar (Plant care tracking)
│   └── forum_integration (Django Machina)
├── External APIs
│   ├── Plant.id (Kindwise)
│   └── PlantNet
├── Infrastructure
│   ├── PostgreSQL 18
│   ├── Redis
│   └── Celery Workers
└── Frontend Integrations
    ├── React Web App
    └── Flutter Mobile App
```

---

## Architecture Principles

### 1. Separation of Concerns
- **Apps:** Domain-specific functionality
- **Services:** Business logic abstraction
- **Models:** Data layer only
- **Views/APIs:** Request/response handling

### 2. DRY (Don't Repeat Yourself)
- Shared code in `apps/core/`
- Reusable services and utilities
- Centralized configuration

### 3. SOLID Principles
- Single Responsibility (one app, one domain)
- Open/Closed (extend via plugins)
- Dependency Inversion (service interfaces)

### 4. Performance-First
- Redis caching (40% hit rate)
- Database indexing (100x faster queries)
- Parallel API processing (60% faster)
- Image compression (85% faster uploads)

### 5. Security-First
- Environment-aware authentication
- Rate limiting
- Input validation
- CORS configuration
- HTTPS enforcement (production)

---

## Recent Architectural Changes

### Week 3: Quick Wins (Production Readiness)
**Date:** October 22, 2025

- **Production Authentication** - Environment-aware permissions
- **API Versioning** - /api/v1/ namespace with backward compatibility
- **Circuit Breaker Pattern** - Fast-fail protection for external APIs
- **Distributed Locks** - Cache stampede prevention with Redis

**Impact:**
- 99.97% faster failed API responses
- 90% reduction in duplicate API calls
- Safe API evolution
- Production-grade security

See: [Quick Wins Documentation](../quick-wins/)

### Week 2: Performance Optimizations
**Date:** October 21, 2025

- **Parallel API Processing** - ThreadPoolExecutor for simultaneous calls
- **Redis Caching** - 24-hour TTL, SHA-256 key hashing
- **Database Indexes** - 8 composite GIN indexes
- **Image Compression** - Client-side compression (max 1200px, 85% quality)

**Impact:**
- 60% faster plant identification
- 40% cache hit rate
- 100x faster database queries
- 85% faster image uploads

See: [Performance Documentation](../performance/)

---

## Navigation

- **Start here:** [Architecture Analysis](./analysis.md) for comprehensive system overview
- **Quick reference:** [Architecture Summary](./summary.md) for executive overview
- **Visual learner:** [Architecture Diagrams](./diagrams.md) for system visualizations
- **Planning:** [Recommendations](./recommendations.md) for future improvements

---

## Contributing to Architecture Docs

When updating architecture documentation:

1. **Update relevant section** (analysis.md, summary.md, etc.)
2. **Add diagrams** if introducing new components
3. **Document trade-offs** for architectural decisions
4. **Include performance impact** where applicable
5. **Reference related Quick Wins** or performance work
6. **Update this README** if adding new files

---

**Last Updated:** October 22, 2025
**Maintained By:** Backend Development Team
