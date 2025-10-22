# Logging Standards - Plant ID Community

**Status**: Standardization In Progress
**Date**: 2025-10-22

## Current State

The codebase uses a mix of logging styles:

### ✅ Good Examples (combined_identification_service.py)
```python
logger.info("[INIT] ThreadPoolExecutor initialized with {max_workers} workers")
logger.info("[PARALLEL] Starting parallel API calls (Plant.id + PlantNet)")
logger.info("[SUCCESS] Plant.id completed in {duration:.2f}s")
logger.error("[ERROR] Plant.id API timeout (35s)")
logger.info("[PERF] Total identification time: {total_time:.2f}s")
logger.info("[CACHE] HIT for PlantNet image {image_hash[:8]}...")
logger.info("[SHUTDOWN] Cleaning up ThreadPoolExecutor")
```

### ❌ Inconsistent Examples (other services)
```python
logger.info("Plant.id service initialized")  # No prefix
logger.warning(f"Plant.id service not available: {e}")  # No prefix
logger.info(f"Found {scientific_name} in cache")  # Should be [CACHE]
logger.info(f"Using cached Unsplash results for: {plant_name}")  # Should be [CACHE]
```

## Proposed Standard

### Log Level Prefixes

| Prefix | Usage | Example |
|--------|-------|---------|
| `[CACHE]` | Cache operations (hit/miss/set) | `[CACHE] HIT for image abc123...` |
| `[PERF]` | Performance metrics | `[PERF] API call completed in 2.35s` |
| `[PARALLEL]` | Parallel execution events | `[PARALLEL] Starting 2 API calls` |
| `[SUCCESS]` | Successful operations | `[SUCCESS] Image uploaded to S3` |
| `[ERROR]` | Error conditions | `[ERROR] API timeout after 30s` |
| `[INIT]` | Service initialization | `[INIT] Redis client connected` |
| `[SHUTDOWN]` | Cleanup and shutdown | `[SHUTDOWN] Closing database connections` |
| `[API]` | External API calls | `[API] Calling Plant.id v3/identify` |
| `[DB]` | Database operations | `[DB] Query returned 42 results` |
| `[RATE_LIMIT]` | Rate limiting events | `[RATE_LIMIT] Throttling user 123` |

### Format Template

```python
# INFO level - operational events
logger.info(f"[{PREFIX}] {description} ({details})")

# WARNING level - degraded but functional
logger.warning(f"[{PREFIX}] {issue}: {explanation}")

# ERROR level - failures requiring attention
logger.error(f"[ERROR] {operation} failed: {error}", exc_info=True)

# DEBUG level - detailed diagnostics
logger.debug(f"[DEBUG] {variable_name}={value}")
```

### Examples by Service

#### combined_identification_service.py ✅
Already follows standard:
```python
logger.info("[INIT] ThreadPoolExecutor initialized with 10 workers")
logger.info("[PARALLEL] Starting parallel API calls (Plant.id + PlantNet)")
logger.info("[SUCCESS] Plant.id completed in 2.35s")
logger.info("[PERF] Total identification time: 4.12s (parallel processing)")
```

#### plant_id_service.py (Needs Updates)
Before:
```python
logger.info("Using cached Plant.id result")
logger.info(f"Plant.id API call successful (took {duration:.2f}s)")
```

After:
```python
logger.info(f"[CACHE] HIT for Plant.id image {image_hash[:8]}...")
logger.info(f"[API] Plant.id v3/identify completed in {duration:.2f}s")
```

#### plantnet_service.py ✅
Already follows standard:
```python
logger.info(f"[CACHE] HIT for PlantNet image {image_hash[:8]}...")
logger.info(f"[CACHE] MISS for PlantNet image {image_hash[:8]}... - calling API")
logger.info(f"[CACHE] Stored PlantNet result for image {image_hash[:8]}...")
```

## Implementation Priority

### High Priority (Core Services)
1. ✅ `combined_identification_service.py` - Already standardized
2. ✅ `plantnet_service.py` - Already standardized
3. ⚠️ `plant_id_service.py` - Needs updates
4. ⚠️ `species_lookup_service.py` - Needs [CACHE], [API], [DB] prefixes
5. ⚠️ `identification_service.py` - Needs [API], [ERROR] prefixes

### Medium Priority (Feature Services)
6. `ai_image_service.py` - Needs [API], [CACHE], [ERROR] prefixes
7. `unsplash_service.py` - Needs [CACHE], [API] prefixes
8. `pexels_service.py` - Needs [CACHE], [API] prefixes

### Low Priority (Support Services)
9. `monitoring_service.py` - Already has structured output
10. `health_check_service.py` - Minimal logging

## Benefits

1. **Filtering**: `grep "\[CACHE\]" logs.txt` to see all cache operations
2. **Monitoring**: Alert on `[ERROR]` patterns in production logs
3. **Performance**: Track `[PERF]` metrics for optimization
4. **Debugging**: Follow `[PARALLEL]` execution flow
5. **Consistency**: Uniform logging across all services

## Migration Strategy

1. Update high-priority services first (plant_id_service.py)
2. Run tests to ensure no broken functionality
3. Update documentation with examples
4. Code review to verify consistency
5. Add pre-commit hook to enforce standard (future)

## Notes

- Existing logs with brackets (`[CACHE]`, `[PERF]`, etc.) are working well
- Plain text logs are harder to parse/filter in production
- JSON logging is configured but plain text more readable in development
- Prefixes help distinguish between different operational concerns
- Keep messages concise (<80 chars) for terminal display

## Next Steps

1. Update `plant_id_service.py` with bracketed prefixes
2. Update `species_lookup_service.py` similarly
3. Test all services still function correctly
4. Document in CLAUDE.md
5. Consider adding linting rule for logging format
