---
status: pending
priority: p3
issue_id: "445"
tags: [blog, content, ai, rag]
dependencies: []
---

# Draft ~50 AI care articles in the CMS for the owner to spot-check

## Problem

Two todos need a body of plant-care articles: todo 330 (RAG corpus gate:
≥50 articles covering the common care questions) and todo 386 (mobile care
guides open CMS content). The owner decided on 2026-09-24 that AI-generated
articles are allowed, spot-checked by the owner before publishing.

## Recommended Action

1. Pick ~50 common houseplant care questions (watering, light, humidity,
   repotting, pests, yellow leaves, propagation, per-plant guides for the most
   common species). Record the list here first.
2. Generate each as a **draft** `BlogPostPage` with the blog's existing AI
   pipeline (`apps/blog/wagtail_ai_v3_integration.py`), tagged so todo 386's
   care cards can list them (e.g. a `care-guide` tag).
3. Never publish: the owner spot-checks and publishes. Leave the ingestion /
   toxicity / pesticide-dosing topics out entirely (todo 330's hard-blocked
   classes).

## Acceptance Criteria

- [ ] ~50 draft care articles exist in the CMS, tagged, unpublished.
- [ ] The topic list and the generation command/prompt are recorded here.
- [ ] The owner has spot-checked and published them (owner step; record the date).

## Work Log

### 2026-09-24 - Filed from the gate-removal decisions (todos 330, 386)
