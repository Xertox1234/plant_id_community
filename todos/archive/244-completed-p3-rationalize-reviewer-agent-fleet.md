---
status: completed
priority: p3
issue_id: "244"
tags: [harness, agents, review, maintainability]
dependencies: ["229"]
---

# Rationalize the reviewer agent fleet against bundled /code-review and /security-review

## Context

Split out from todo 229. Todo 229 discovered the custom review fleet was
non-functional (14 agents failed to load due to malformed frontmatter) and fixed
the frontmatter so the fleet loads again. This todo is the **original 229
rationalization scope**, deferred so it runs against a fleet that actually works.

Do this only after confirming (fresh session) that the 14 agents fixed in todo 229
now register as dispatchable agent types — otherwise the comparison cannot run.

## Problem

The project agents predate Claude Code's bundled `/code-review` and
`/security-review`, which now provide fresh-subagent diff review with
false-positive verification — the same architecture as the custom orchestrator.
The generic reviewers are largely replicated by bundled tooling; maintaining them
is cost without differentiation. There is also no documented boundary between
`code-review-orchestrator` and `full-review-orchestrator`.

## Findings (from 229)

- Generic reviewers with high overlap vs bundled commands: `test-quality-reviewer`,
  `performance-reviewer`, `api-design-reviewer`, `security-reviewer` (bundled
  `/security-review` overlaps the last).
- Differentiated domain reviewers worth keeping: `wagtail-reviewer`,
  `django-drf-reviewer` (project-gotcha-loaded), `flutter-dart-reviewer`,
  `flutter-firebase-reviewer`, `firebase-cloudfunction-reviewer`,
  `celery-async-reviewer`, `react-typescript-reviewer` (project-pattern-loaded).
- `full-review-orchestrator.md` (562 lines) vs `code-review-orchestrator.md`
  (186 lines): no "when to use which" doc; unclear interaction with `/audit`.
- Much of the domain reviewers' enforceable knowledge already lives in
  `docs/rules/<domain>` checklists (auto-injected) + CLAUDE.md "Critical Gotchas".

## Recommended Action

1. Trial: run bundled `/code-review` on a real diff alongside the (now-loadable)
   custom reviewers; compare coverage for the generic dimensions. The 229 trial
   target `c3cbdd3` (forum PR-2a backend write — views/serializers/tests) is a good
   reproducible diff. Setup: `git switch -c trial c3cbdd3 && git reset c3cbdd3~1 && git add -N .`.
2. Retire (git rm) generic reviewers whose findings are subsumed; fold any
   project-specific checks they carried into surviving domain reviewers or
   `docs/rules` checklists.
3. Add a "when to use which" section to CLAUDE.md (Code Review Agents table):
   orchestrator = domain review of a diff; full-review = whole-repo sweep;
   bundled /code-review = quick generic pass. (CLAUDE.md edits are Auto-Mode-gated.)
4. Trim agent frontmatter descriptions to one terse line each.
5. If agents are retired, update `docs/rules/routing.json` `_comment` and consider
   whether the deferred `agents`/`exclusions` routing belongs here.

## Technical Details

- Editing `.claude/` agents and root `CLAUDE.md` is blocked under Auto Mode — ask
  the user to disable it first.
- Keep the kimi-review commit gate untouched; it is a different layer.
- The `c3cbdd3` trial showed the comparison is only meaningful once the fleet loads
  (todo 229) — verify registration in a fresh session before running step 1.

## Acceptance Criteria

- [x] Side-by-side comparison documented (bundled vs custom on the same diff).
- [x] Each retired agent's unique checks are either codified elsewhere or
      explicitly declared redundant in the work log.
- [x] CLAUDE.md documents the orchestrator/full-review/bundled boundaries.

## Work Log

### 2026-06-24 - Created

- Split from todo 229 (fix-vs-rationalize). 229 fixed the broken frontmatter;
  this carries the rationalization once the fleet is confirmed loadable.

### 2026-07-02 - Started by completing-todos skill (run 2026-07-02-2100)

- Picked up by automated workflow.
- Fleet registration precondition confirmed: all 12 reviewers + both
  orchestrators + pattern-codifier appear as dispatchable agent types in this
  fresh session's registry.

### 2026-07-02 - Side-by-side trial: bundled /code-review vs custom generics (AC1)

**Setup (reproducible):** `git worktree add --detach <tmp>/trial-244 c3cbdd3 &&
git -C <tmp>/trial-244 reset c3cbdd3~1 && git add -N .` — PR-2a forum backend
write diff (14 source files, +1621/−134) as an uncommitted working-tree change.
Custom side: the 4 generic reviewers dispatched with the orchestrator's own
prompt template on the routed file lists. Bundled side: `/code-review` at xhigh
effort (10 finder angles). Singleton candidates on both sides were then
adversarially verified by dedicated verifier agents (cross-derived findings —
independently produced by 3–4 finders with Wagtail-source citations — were
treated as verified). Deviation from the bundled protocol: no per-candidate
verifier for every candidate and no Phase-3 sweep (conservative — understates
bundled coverage).

**Bundled /code-review — 9 confirmed real correctness bugs, 0 found by the custom fleet:**

1. workflow.py:116 — after one flagged edit, `workflow.start()` always raises
   `ValidationError` (one active WorkflowState per object; NEEDS_CHANGES counts) →
   edits permanently wedged at fake "pending" (4× independently derived, verified
   against installed Wagtail 7.4 source).
2. workflow.py:108 — `ForumProfile.for_user(None)` crash on author-deleted posts →
   moderator redaction silently lost, 200 "pending" (3×).
3. views.py:375 — blanket `except Exception → 'pending'` copied from create path
   where its safety invariant (row persisted pre-submit) doesn't hold on edit (4×).
4. views.py:394 — DELETE skips the closed/locked-topic 409 guard PATCH enforces (4×).
5. views.py:214 (serializers) — `can_edit`/`can_delete` flags omit opening-post and
   closed/locked rules → PR-2b web UI renders buttons that always 409 (verified).
6. views.py:394 — per-post `LockableMixin` lock (admin-lockable via SnippetViewSet)
   never checked → trusted-author PATCH publishes over a moderator-locked post (verified).
7. workflow.py:121 — `moderation_decided` host signal never fired on the edit path,
   unlike create (3×).
8. forumService.ts:208 — web `updatePost` still sent the legacy machina contract
   against the new route (verified; latent — matches the known PR-2b sequencing).
9. views.py:396 — DELETE-opening-post 409 advises "delete the topic" but no
   topic-delete endpoint exists (verified).
   Plus 1 PLAUSIBLE race (PATCH vs concurrent unpublish republish) and 1 REFUTED
   (unpublish/workflow-state "zombie" — NEEDS_CHANGES isn't approvable;
   SpamCheckTask resolves synchronously). Plus ~15 dedup'd cleanup findings
   (visibility-guard triplication, duplicated `get_permissions()` →
   `IsAuthenticatedOrReadOnly`, `PostEditSerializer` byte-copy, redundant
   `refresh_from_db`, fetch-then-check double query, throttle-mirror
   class-of-bug test gap).

**Custom generic fleet — 16 findings, 0 correctness bugs; verified headline verdicts:**

- test-quality-reviewer: 6 findings — CONFIRMED: no unauthenticated-401 test for
  PATCH/DELETE `/posts/{id}/` (dropping `permission_classes` would pass the
  suite); CONFIRMED: `locked=True` half of the closed-or-locked edit guard
  untested (its own forum-audit or-guard check). 4 low style items.
- performance-reviewer: 3 findings — the `serialize_forum_body` StreamValue
  iteration flagged as a future ChooserBlock N+1: **history-validated** (this
  exact bug bit during PR-3a and had to be caught+fixed there).
- api-design-reviewer: 5 findings — CONFIRMED: throttled endpoints return 429
  (test-asserted) but no schema documents it; REFUTED-as-bug: `topic_id`
  missing `read_only=True` (PostSerializer is never an input serializer).
- security-reviewer: 2 findings — BOTH REFUTED (excerpt "XSS": body is
  nh3-sanitized at write + client strips tags; `signature` "unbounded": model
  caps it at CharField(max_length=255)).

**Conclusion:** near-disjoint coverage — complementary, not subsumed. Bundled
owns correctness (9–0); the generics' surviving value is checklist-compliance
auditing (coverage prescriptions, schema completeness), ~half of whose content
already duplicated docs/rules. Token cost observed: bundled xhigh ≈ 1.0M+
subagent tokens vs ≈ 155k for the 4 generics.

### 2026-07-02 - Decision: consolidate 4 generics into cross-cutting-reviewer

kimi-challenge pressure-test surfaced: (1) the trial refutes plain retirement —
the generics catch what bundled doesn't; (2) performance/security route on
any-.py/sensitive-paths, so retirement leaves non-domain files with no custom
review-time owner; (3) Phase 2.5 trigger capture feeds on reviewer findings.
Its "keep all four — cost is near-zero" claim is contradicted by todo 229 (fleet
silently broken for weeks, unnoticed) and by checklist drift (test-quality still
carried a django-machina INSTALLED_APPS check — machina was retired in PR #362).
Adopted its Alternative 1, refined: ONE consolidated `cross-cutting-reviewer`
that Reads `docs/rules/{security,api,testing,database,caching}.md` at runtime
(single source of truth, no duplicated checklists) plus a residue list of checks
that exist nowhere else. Preserves the review-time checklist pass, repair mode,
and trigger capture at 1/4 the file count.

### 2026-07-02 - Retired-agent check disposition (AC2)

Every checklist item of the four retired agents is accounted for:

- **Already in docs/rules (now read at runtime by cross-cutting-reviewer):**
  DB-mock ban, `--keepdb`/`--noinput`, strict/exact assertions, DraftStateMixin
  live-flag fixture rule (testing.md); 429-vs-403 + `Retry-After`, service-layer
  type hints, choices=-breaking-change (api.md); SQL identifier/f-string ban,
  wildcard escaping, 4-layer upload, DOMPurify/XSS, OAuth verified-email +
  ImmediateHttpResponse + strip-guard fail-closed, spectacular SERVE_PERMISSIONS
  gating, no-accounts-in-migrations, SECRET_KEY rules (security.md);
  select/prefetch N+1 basics, shared-serializer prefetch-all-consumers,
  query-count pins (database.md); Redis-required, invalidate-on-write, key
  isolation, TTLs (caching.md).
- **Folded into cross-cutting-reviewer residue:** coverage prescriptions
  (service happy+error, endpoint 401/400/success, permission allow+deny),
  or-guard operand coverage, route-parity callback pins, external-API mock
  shapes (Plant.id v3 2-call), test naming/structure, React
  behavior-not-implementation + act() + E2E-guide, SerializerMethodField-N+1 +
  conditional annotation, prefetch-vs-Count, reverse-OneToOne consolidation,
  instance-cache staleness, Wagtail StreamValue raw_data N+1 (todo 231 nuance
  preserved verbatim), iterator/only/defer, cache hit-rate targets + warming,
  /api/v1/ versioning + deprecation notes, error shape, read_only/write_only +
  nested source=, extend_schema + 429-in-schema + trust-level docs +
  extend_schema_field, UUID conventions, secret-pattern greps + .gitignore,
  upload constants + per-resource count limits, CORS 5174, CSRF header pairing,
  JWT-not-in-localStorage, firestore/storage rules + IAM least-privilege.
- **Declared redundant (dropped):** django-machina INSTALLED_APPS loader check —
  stale; machina was fully retired (PR #362); Plant.id "2 API calls" retained but
  flagged for re-verification next time plant ID mocks change; test-quality's
  "e.g. max 10 images per plant" example folded as the generic per-resource
  count-limit line.

### 2026-07-02 - Implementation

- NEW `.claude/agents/cross-cutting-reviewer.md` (thin auditor over docs/rules +
  residue; same output/repair contracts; model sonnet).
- `git rm` test-quality-reviewer.md, performance-reviewer.md,
  api-design-reviewer.md, security-reviewer.md.
- Routing updates: code-review-orchestrator.md (4 rows + Phase-5 example),
  full-review-orchestrator.md (skip-list, routing table, precedence rules,
  invocation example, findings example, repair-filter example),
  pattern-codifier.md (process list + codifier routing), .claude/skills/audit/
  SKILL.md (security/performance/django-drf/testing rows),
  .claude/skills/codify/SKILL.md (review-agent update routing).
- Frontmatter: all 14 agents now have single terse `description:` lines
  (script-verified, `<example>` blocks gone; frontend-developer 2.3k→157 chars,
  wagtail-cms-orchestrator 3.6k→230 chars).
- CLAUDE.md: "Which review tool when" table (bundled /code-review,
  /security-review, both orchestrators, /audit) + agents table updated.
- docs/rules/routing.json `_comment`: deferred agents/exclusions routing
  RESOLVED as won't-move — agent routing stays in the two orchestrator files
  (primary/secondary semantics don't fit the flat path→domain format);
  JSON validity + route_domains.py smoke-tested after the edit.
- Trial artifacts (finder/reviewer outputs + verifier verdicts) preserved in the
  session scratchpad; trial worktree to be removed at wrap-up.

### 2026-07-02 - Verification gate (acceptance criteria evidence)

```text
=== AC1: comparison documented ===
$ grep -c "Side-by-side trial: bundled /code-review vs custom generics" todos/244-…md
1
=== AC2: disposition section ===
$ grep -c "Retired-agent check disposition (AC2)" todos/244-…md
1
=== AC3: CLAUDE.md boundaries ===
$ grep -n "Which review tool when" CLAUDE.md
164:### Which review tool when
=== no retired-agent refs in live harness (.claude/, CLAUDE.md, docs/rules/) ===
0
=== .claude/agents/ after consolidation ===
14 files; cross-cutting-reviewer.md present; the 4 retired reviewers absent
=== frontmatter loadability ===
script-verified: all 14 descriptions single-line < 260 chars, no <example> blocks
=== routing.json ===
JSON valid; scripts/inject/route_domains.py backend/apps/forum_host/api.py
→ forum,wagtail,security (unchanged behavior)
```

### 2026-07-02 - Completed by completing-todos skill (run 2026-07-02-2100)

- Verification: all 3 acceptance criteria passed (evidence quoted above).
- Review: code-review-orchestrator triaged the diff — 0 findings, 0 blocking
  ("harness reconfiguration only; no domain routing pattern matches").
- Live loadability proof: the session's agent registry hot-reloaded after the
  file changes — `cross-cutting-reviewer` appeared as a dispatchable agent type
  and the four retired reviewers disappeared, confirming the new frontmatter
  registers (the exact failure mode todo 229 was about).

### 2026-07-03 - Post-review corrections (/review 244 follow-up)

A precision review of the diff surfaced 3 low/medium quality issues (0
correctness bugs); all fixed:

- **AC2 accuracy**: two `test-quality`/`performance` assertion-quality checks
  were dropped without being folded or declared redundant — "assertion failure
  messages cite the issue number" and "query-count docstring states WHY N".
  Both re-added to the `cross-cutting-reviewer` Test-coverage residue, so the
  AC2 "codified elsewhere OR declared redundant" claim now holds in full.
- **Residue vs docs/rules duplication**: the residue header claimed its checks
  "live only here (not in docs/rules)", but the Security bullets duplicated
  `security.md` (4-layer upload, secrets) and `firebase.md` (firestore/IAM).
  Added `docs/rules/firebase.md` to the Step-1 read list, reworded the header
  to "specifics that sharpen/extend the Step-1 rules (which stay canonical)",
  and trimmed the firestore/IAM bullet to the storage-size/MIME specifics
  `firebase.md` doesn't carry.
- **Review-doc checkoff**: `docs/reviews/2026-07-02-2252-…` Finding Status note
  clarified (one-line-per-todo grouping is intentional; 6 todos ↔ 6 lines is
  1:1 so auto-checkoff completes) and hardened against the `#1` vs `#11`/`#12`
  prefix collision (match the lead token with its trailing space).
