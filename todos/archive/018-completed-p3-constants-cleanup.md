---
status: resolved
priority: p3
issue_id: "018"
tags: [cleanup, constants]
dependencies: []
---

# Reduce constants.py from 222 → 50 Lines

## Problem

80% of constants unused (16 cache timeout variants, 24 lines geo boundaries for unimplemented features).

## Solution

Remove unused constants, keep only:
- API timeouts (4)
- Cache timeouts (2)
- Circuit breaker config (6)
- Lock config (5)

**Effort**: 1 hour  
**Benefit**: 222 → 50 lines
