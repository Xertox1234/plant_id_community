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

- [x] ~50 draft care articles exist in the CMS, tagged, unpublished. (completed 2026-09-27: 53 drafts in production, see the Work Log)
- [x] The topic list and the generation command/prompt are recorded here. (completed 2026-09-27, see the Work Log)
- [ ] The owner has spot-checked and published them (owner step; record the date).

## Work Log

### 2026-09-24 - Filed from the gate-removal decisions (todos 330, 386)

### 2026-09-26 - Owner decision: the agent runs it in production

Ship a `generate_care_drafts` management command in a normal PR: the topic
list, drafts only, never published, tagged `care-guide`, and todo 330's
hard-blocked classes excluded. Prove it locally first. After merge, the
agent runs it on Railway (`railway ssh … python manage.py
generate_care_drafts`). **If the auto-mode classifier refuses, stop, and hand
the owner the exact command**; do not re-route. The owner then spot-checks
and publishes (AC 3).

### 2026-09-27 - `generate_care_drafts` shipped; proved locally

- **Topic list:** `backend/apps/blog/care_topics.py` holds 53 topics:
  - watering, light and environment;
  - soil, pots and repotting;
  - feeding and grooming;
  - propagation;
  - problems;
  - four pests, handled with cultural and mechanical control only;
  - 16 plant guides.
  Todo 330's hard-blocked classes are left out. A test checks that every
  topic passes the RAG guardrail's `classify_blocked_question`.
- **Command and prompt:** `manage.py generate_care_drafts --author <username>`.
  The prompt is `PROMPT` in
  `backend/apps/blog/management/commands/generate_care_drafts.py`. It bans
  safety and toxicity or edibility claims, named pest-control products and
  amounts, and asks for JSON (an introduction plus 4–6 sections). Each draft
  is an unpublished `BlogPostPage` under the blog index, tagged
  `care-guide`, with one revision. The command never publishes.
- **Screening:** every generated paragraph is screened with
  `classify_blocked_question`, and a flagged paragraph is dropped. A draft
  with fewer than 4 clean paragraphs is skipped and reported. It is not
  retried, because the AI layer caches identical prompts, so a re-run returns
  the same text.
- **Other options:** `--dry-run` makes no calls and no writes. `--only
  <slug>…` and `--limit N` narrow the run. A re-run skips slugs that already
  exist.
- **Local proof:** a run of `--only pothos-care-guide fungus-gnats` on the
  dev DB (gpt-4o-mini) created 2 drafts, 0 failed, 0 screened out. Both are
  `live=False` with no `first_published_at`, tagged `care-guide`, and have a
  revision. The text reads as real care advice.
- **Next, after merge (owner decision 2026-09-26):**
  - The agent runs it on Railway:
    `railway ssh --service plant_id_community -- bash -lc 'cd /app && python manage.py generate_care_drafts --author <staff username>'`.
  - If the classifier refuses, hand this command to the owner.
  - Then the owner spot-checks and publishes (AC 3).

### 2026-09-27 - PR #855 review round 1

- **Fixed:**
  - The paragraph screen now also flags any named treatment or remedy
    (`_TREATMENT_RE`: neem, rubbing alcohol, dish soap, peroxide and so on).
    The RAG question classifier needs a dose word next to the chemical, so
    "spray with neem oil weekly" passed it.
  - A failed page write now skips only its topic.
  - "Already exists" now means a child of the chosen index, of any page
    type.
  - `--index` is required when there is more than one blog index.
  - Drafts are owned by `--author`, so they show under "My pages".
- **Known limitations** (non-blocking, not fixed):
  - The AI layer caches each prompt's reply for 30 days, even a malformed or
    screened-out one. A re-run cannot refill those topics, so write them by
    hand or change the prompt.
  - `publish_date` is the generation date. Set it when publishing.
  - The run is sequential: 53 calls, up to about 80 minutes in the worst
    case. Use `--limit` batches over `railway ssh`; a dropped session is safe
    to re-run.
  - **Layering.** `apps.blog` now imports
    `apps.forum_host.rag_guardrails.classify_blocked_question`, which
    reverses the documented blog → forum direction. The fix is to move the
    ingestion, toxicity and chemical patterns, plus `_TREATMENT_RE`, into a
    shared `apps/core` content-classification module that both apps import.
    Raised by the wagtail-reviewer in PR #855.

### 2026-09-27 - Production run: 53 drafts (AC 1)

After #855 deployed (`90d87497`), the agent ran it on Railway as
`plantadmin` (the owner supplied the username):

- `--dry-run`: 53 to draft, 0 already exist, one blog index resolved.
- `--limit 10`: 10 created, 0 failed, 0 screened out.
- The rest: 43 created, 10 already existed, 0 failed, 0 screened out.
- 0 paragraphs were dropped by the guardrail in either batch. Nothing was
  published.

AC 3 is the owner's: spot-check the 53 drafts under the blog index in the CMS
(`/cms/`, "My pages" for `plantadmin`) and publish. Set `publish_date` when
publishing. Published `care-guide` posts are what the mobile care guides list
(todo 386).
