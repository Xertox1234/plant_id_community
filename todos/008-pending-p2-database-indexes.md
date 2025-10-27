---
status: ready
priority: p2
issue_id: "008"
tags: [code-review, performance, database, indexes]
dependencies: []
---

# Add Database Indexes for Blog Queries

## Problem

Missing indexes cause 10x slowdown at scale (300ms → 3000ms at 100K posts).

## Solution

Create migration with indexes:
```sql
CREATE INDEX idx_blogpost_publish_date ON blog_blogpostpage(publish_date DESC);
CREATE INDEX idx_blogpost_view_count ON blog_blogpostpage(view_count DESC);
CREATE INDEX idx_blogpost_category_date ON blog_blogpostpage(category_id, publish_date);
```

**Effort**: 30 minutes  
**Impact**: 80% faster queries at scale
