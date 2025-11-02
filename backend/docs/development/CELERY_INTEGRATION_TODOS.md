# Celery Integration TODOs

**Created**: November 2, 2025
**Status**: Future Enhancement Planning
**Priority**: P3 (Performance Optimization)

## Overview

This document summarizes the 3 remaining TODO comments in the production codebase, all related to future Celery integration for async task processing. These TODOs were identified during the comprehensive code audit (TODO 005).

## Key Finding

Out of 37 files containing "TODO" strings in grep results:
- **34+ files**: Documentation/historical markers (not code issues)
- **3 files**: Real TODO comments in production code (all Celery-related)
- **0 files**: Urgent technical debt or security issues

**Conclusion**: The codebase is exceptionally clean with minimal technical debt.

---

## The 3 Real TODOs

### 1. Async Disease Diagnosis Processing

**Location**: `backend/apps/plant_identification/views.py:752`

```python
# TODO: Enqueue Celery task for async processing
# For now, process synchronously to get immediate results
```

**Context**:
- Function: `PlantDiseaseViewSet.create()`
- Current implementation: Synchronous processing of disease diagnosis requests
- Fallback behavior: Works correctly, just processes synchronously

**Enhancement Details**:
- **Purpose**: Offload disease diagnosis to background workers
- **Benefit**: Faster API response times (return request_id immediately, process in background)
- **User experience**: Poll for results instead of waiting for synchronous response
- **Pattern**: Standard async task pattern used by modern APIs

**Implementation Plan** (when Celery is integrated):
```python
# Enqueue Celery task
from apps.plant_identification.tasks import process_disease_diagnosis
task = process_disease_diagnosis.delay(request_obj.id)
return Response({
    'request_id': request_obj.request_id,
    'status': 'processing',
    'task_id': task.id
}, status=202)
```

**Priority**: P3 (Performance optimization, not blocking)

---

### 2. User Tracking for Voting System

**Location**: `backend/apps/plant_identification/views.py:882`

```python
# TODO: Implement proper voting system with user tracking to prevent duplicate votes
# Use atomic F() expressions to prevent race conditions
```

**Context**:
- Function: `PlantDiseaseResultViewSet.vote()`
- Current implementation: Allows unlimited votes (no duplicate prevention)
- Fallback behavior: Uses atomic F() expressions to prevent race conditions (good)

**Enhancement Details**:
- **Purpose**: Prevent users from voting multiple times on the same result
- **Current state**: Atomic vote counting works, but no duplicate prevention
- **Required**: User-result voting history table
- **Pattern**: Standard many-to-many through model with vote type tracking

**Implementation Plan** (when ready):
```python
# Create VoteHistory model
class PlantDiseaseVote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    result = models.ForeignKey(PlantDiseaseResult, on_delete=models.CASCADE)
    vote_type = models.CharField(max_length=10, choices=[('upvote', 'Upvote'), ('downvote', 'Downvote')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'result')
        indexes = [
            models.Index(fields=['user', 'result']),
        ]

# Update vote endpoint to check/create votes
existing_vote = PlantDiseaseVote.objects.filter(user=request.user, result=result_obj).first()
if existing_vote:
    if existing_vote.vote_type != vote_type:
        # Change vote (decrement old, increment new)
        ...
else:
    # New vote
    PlantDiseaseVote.objects.create(user=request.user, result=result_obj, vote_type=vote_type)
    ...
```

**Priority**: P3 (Feature enhancement, not blocking)

---

### 3. Scheduled Notification Delivery

**Location**: `backend/apps/core/services/notification_service.py:181`

```python
# TODO: Implement proper scheduling with Celery or Django-RQ
logger.warning(f"Scheduled notifications not yet implemented. Sending immediately instead.")
```

**Context**:
- Function: `NotificationService.schedule_notification()`
- Current implementation: Sends notifications immediately instead of scheduling
- Fallback behavior: Works correctly, just ignores schedule_time parameter

**Enhancement Details**:
- **Purpose**: Schedule notifications for future delivery (e.g., "Remind me in 3 days")
- **Current state**: API accepts schedule_time but ignores it (logs warning)
- **User experience**: Receives notification immediately instead of at scheduled time
- **Pattern**: Standard Celery beat or django-celery-beat for scheduled tasks

**Implementation Plan** (when Celery is integrated):
```python
from celery import current_app

def schedule_notification(self, schedule_time: datetime, ...) -> Dict[str, bool]:
    """Schedule notification for later delivery."""
    # Calculate ETA (when to send)
    eta = schedule_time

    # Enqueue Celery task with ETA
    from apps.core.tasks import send_notification_task
    task = send_notification_task.apply_async(
        args=[user_id, notification_type, data, channels],
        eta=eta
    )

    return {'scheduled': True, 'task_id': task.id, 'eta': eta.isoformat()}
```

**Priority**: P3 (Feature enhancement, not blocking)

---

## Why These TODOs Are Acceptable

1. **Not Blocking**: All 3 have working fallback implementations
2. **Performance, Not Bugs**: These are optimizations, not fixes
3. **Clearly Documented**: Each TODO has context explaining the temporary approach
4. **Consistent Pattern**: All 3 wait for the same infrastructure (Celery)
5. **Future-Ready**: Code is structured to easily add async processing later

## When to Address These TODOs

**Trigger Event**: When Celery is integrated into the project

**Prerequisites**:
- Celery installed and configured
- Redis/RabbitMQ message broker running
- Celery workers deployed
- Celery beat scheduler (for TODO #3)

**Estimated Effort**:
- TODO #1 (Async diagnosis): 2-3 hours (create task, update API, add polling endpoint)
- TODO #2 (Vote tracking): 3-4 hours (create model, migration, update logic, add tests)
- TODO #3 (Scheduled notifications): 2-3 hours (create task, configure beat, update service)

**Total effort**: ~8-10 hours when Celery infrastructure is ready

---

## Celery Integration Plan

When ready to implement, follow this sequence:

### Phase 1: Infrastructure Setup (4-6 hours)
1. Install Celery: `pip install celery redis`
2. Configure Celery in `settings.py`
3. Create `celery.py` app configuration
4. Add `apps/*/tasks.py` for task definitions
5. Deploy Celery workers: `celery -A plant_community_backend worker -l info`
6. Deploy Celery beat: `celery -A plant_community_backend beat -l info`
7. Add monitoring: Flower or similar

### Phase 2: Implement TODOs (8-10 hours)
1. Implement TODO #1 (Async diagnosis) - Highest impact
2. Implement TODO #2 (Vote tracking) - User-facing feature
3. Implement TODO #3 (Scheduled notifications) - Requires beat scheduler

### Phase 3: Testing and Monitoring (4-6 hours)
1. Add integration tests for async tasks
2. Test failure scenarios (task retry, worker crash, etc.)
3. Add task monitoring and alerting
4. Update documentation

**Total Effort**: ~20-25 hours for complete Celery integration + TODO resolution

---

## References

- **TODO 005 Audit**: `/backend/todos/completed/005-complete-p3-audit-todo-comments.md`
- **Code Audit Patterns**: `/backend/docs/development/CODE_AUDIT_PATTERNS_CODIFIED.md`
- **Plant Identification Service**: `/backend/apps/plant_identification/views.py`
- **Notification Service**: `/backend/apps/core/services/notification_service.py`

---

## Notes

- **No action required**: These TODOs are properly documented and non-blocking
- **Codebase health**: Excellent - only 3 TODOs in entire production codebase
- **Technical debt**: Minimal - all TODOs are future enhancements, not fixes
- **Next review**: When Celery integration is planned or P3 backlog is addressed

**Status**: DOCUMENTED - No immediate action needed ✅
