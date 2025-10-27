---
status: ready
priority: p1
issue_id: "001"
tags: [code-review, reliability, performance, circuit-breaker]
dependencies: []
---

# Add Circuit Breaker to PlantNet Service

## Problem Statement

PlantNet API calls lack circuit breaker protection, causing 60-second timeouts instead of fast-failing during service outages. This wastes user time, consumes API quota unnecessarily, and contradicts documentation claims of circuit breaker protection.

## Findings

- **Discovered by**: performance-oracle, architecture-strategist agents
- **Location**: `backend/apps/plant_identification/services/plantnet_service.py:198`
- **Current behavior**: Direct API calls with 60s timeout, no fast-fail mechanism
- **Expected behavior**: Circuit breaker should open after 5 failures, fast-fail in <10ms
- **API constraints**: PlantNet free tier = 500 requests/day (stricter than Plant.id)

## Proposed Solutions

### Option 1: Module-Level Circuit Breaker (Recommended)
- **Implementation**: Same pattern as Plant.id service
- **Configuration**:
  ```python
  _plantnet_circuit, _plantnet_monitor, _plantnet_stats = create_monitored_circuit(
      service_name='plantnet_api',
      fail_max=5,          # More tolerant than Plant.id (free tier)
      reset_timeout=30,     # 30s recovery window
      success_threshold=2,
      timeout=PLANTNET_API_REQUEST_TIMEOUT,
  )
  ```
- **Pros**:
  - Consistent with existing Plant.id pattern
  - Proven reliability (99.97% faster fast-fail)
  - Monitoring integration via CircuitMonitor
  - Bracketed logging: `[CIRCUIT]` prefix
- **Cons**:
  - Module-level singleton adds complexity
  - Requires Redis storage for distributed deployments (optional)
- **Effort**: Medium (2-4 hours)
- **Risk**: Low (established pattern, well-tested)

### Option 2: Simple Timeout Reduction
- **Implementation**: Reduce timeout from 60s to 10s
- **Pros**: Minimal code change
- **Cons**: Still wastes 10s per failure, no quota protection
- **Effort**: Small (15 minutes)
- **Risk**: Low
- **Verdict**: Insufficient - doesn't solve core problem

## Recommended Action

**Implement Option 1** - Module-level circuit breaker matching Plant.id service pattern.

### Implementation Steps:
1. Add module-level circuit breaker creation (lines 46-60 in plantnet_service.py)
2. Wrap API call in `self.circuit.call()` (line 198)
3. Add CircuitMonitor for monitoring integration
4. Update tests to verify circuit breaker behavior
5. Add `[CIRCUIT]` logging prefix for production monitoring

### Success Criteria:
- Circuit opens after 5 consecutive failures
- Fast-fail response in <10ms when circuit open
- Monitoring logs show `[CIRCUIT]` events
- Existing tests still pass
- New test: circuit breaker integration test

## Technical Details

**Affected Files**:
- `backend/apps/plant_identification/services/plantnet_service.py` (primary)
- `backend/apps/plant_identification/services/circuit_monitoring.py` (import)
- `backend/apps/plant_identification/tests/test_circuit_breaker_locks.py` (add tests)

**Related Components**:
- Plant.id service (reference implementation)
- Combined identification service (uses both Plant.id and PlantNet)
- Circuit monitoring system (shared infrastructure)

**Database Changes**: None

**Configuration Changes**:
- Add to `constants.py`:
  ```python
  PLANTNET_CIRCUIT_FAIL_MAX = 5
  PLANTNET_CIRCUIT_RESET_TIMEOUT = 30
  PLANTNET_CIRCUIT_SUCCESS_THRESHOLD = 2
  ```

## Resources

- **Reference implementation**: `backend/apps/plant_identification/services/plant_id_service.py:46-53`
- **Circuit breaker docs**: `/backend/docs/quick-wins/circuit-breaker.md`
- **Related finding**: Finding #12 (ThreadPoolExecutor Over-Engineering) - circuit breakers are necessary complexity
- **Agent reports**: performance-oracle, architecture-strategist

## Acceptance Criteria

- [ ] Module-level circuit breaker created with pybreaker
- [ ] API calls wrapped in `circuit.call()`
- [ ] CircuitMonitor integration added
- [ ] `[CIRCUIT]` logging prefix used
- [ ] Circuit opens after 5 failures
- [ ] Fast-fail response <10ms when open
- [ ] Reset timeout 30s configured
- [ ] Existing tests pass
- [ ] New circuit breaker test added
- [ ] Documentation updated (if needed)

## Work Log

### 2025-10-25 - Code Review Discovery
**By**: Claude Code Review System (12 specialized agents)
**Actions**:
- Discovered during comprehensive codebase audit
- Analyzed by performance-oracle and architecture-strategist agents
- Compared PlantNet service to Plant.id reference implementation
- Identified as CRITICAL due to poor user experience during outages

**Learnings**:
- PlantNet has stricter rate limits (500/day) than Plant.id, making circuit breaker MORE important
- Grep search for "circuit" in plantnet_service.py returned no results
- Plant.id service has exemplary circuit breaker implementation to reference
- This is documented in CLAUDE.md but not implemented in code

## Notes

**Source**: Code review performed on 2025-10-25
**Review command**: `audit codebase and report back to me`
**Priority justification**: CRITICAL because it wastes user time (60s timeout) and API quota during outages
