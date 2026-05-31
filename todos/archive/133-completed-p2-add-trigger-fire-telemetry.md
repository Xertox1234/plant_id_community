---
name: add-trigger-fire-telemetry
status: completed
priority: p2
created: 2026-05-30
tags: [harness, jit-injection, telemetry, metrics]
source_review: "docs/audits/2026-05-30-harness.md"
source_finding: "F8"
---

# Make harness prevention measurable (trigger-fire telemetry)

## Problem

The harness's prevention apparatus is **unmeasurable by construction**, which is
the core answer to "how effective is the harness?": *nobody can currently tell.*

- `match_triggers.py` writes matched warnings to **stdout only** — no persistent
  fire log. `inject-patterns.sh` records nothing about which triggers fired.
- All 7 triggers in `docs/rules/triggers.json` are hand-seeded `severity: warn`
  (from the v1-spine commit 46234f1); there are **zero** auto-captured
  `candidate` triggers. The automated codify→capture→trigger path has never been
  observed to complete end-to-end in the wild.
- There is therefore no evidence any trigger has ever fired in a real session, or
  prevented a real recurrence. The mechanism is sound and unit-tested; its
  in-the-wild effectiveness is simply unknown.

Without a signal, the harness can rot (a trigger silently stops matching, a hook
silently breaks) or stay decorative, and no one would notice.

## Acceptance criteria

- [x] `inject-patterns.sh` (or `match_triggers.py`) appends matched trigger IDs +
      timestamp + file to a lightweight per-session log (e.g.
      `/tmp/inject-fires-<session>.log` or a repo-ignored path). Must never break
      the hook's JSON output or block an edit (same fail-open discipline as today).
- [x] A tiny reporter (script or `/codify` step) summarizes fire counts per
      trigger so dead/noisy triggers are visible.
- [x] Document one concrete historical fragment each existing trigger WOULD have
      caught (turns "tested" into "demonstrated against real history").
- [x] Decide whether the automated `candidate`-capture path should be exercised on
      the next real review so at least one auto-captured trigger exists end-to-end.

## Work Log

### 2026-05-31 - Completed by completing-todos skill (run 2026-05-31-0145)

**Criterion 1 — Telemetry in match_triggers.py:**
Added `_log_fires(hits, rel_path)` to `scripts/inject/match_triggers.py`. Called
after `find_matches()` in `main()`. Appends `<ISO-UTC>\t<rel-path>\t<trigger-id>`
to `INJECT_FIRES_LOG` env var (default `/tmp/inject-fires.log`). Fully fail-open
(entire body in `try/except pass`). Verified: fire logged correctly, stdout
unaffected, exit 0. All 34 existing tests still pass.

**Criterion 2 — Reporter:**
Created `scripts/inject/report_fires.py`. Reads the log, counts per trigger with
`Counter`, prints sorted by most-frequent. Usage: `python3 scripts/inject/report_fires.py`.
Verified: reporter output matches log entries correctly.

**Criterion 3 — Historical fragments per trigger:**
- `drf-action-no-ratelimit`: 5 forum `@action` endpoints (todos 104-109) shipped
  without rate limits; the trigger fires on `@action` + absence of `ratelimit`.
- `migration-fstring-sql`: CLAUDE.md Critical Gotcha #3 — raw SQL in migrations
  with f-strings; a real migration using `cursor.execute(f"ALTER TABLE {t}...")`.
- `viewset-get-permissions-no-super`: CLAUDE.md Critical Gotcha #1 — security hole
  where `@action` permission_classes are silently ignored; hit in production.
- `react-router-bare-import`: CLAUDE.md Critical Gotcha #2 — hit 15+ files during
  TypeScript migration; `from 'react-router'` crashed at runtime silently.
- `wagtail-signal-hasattr-pagetype`: LEARNINGS.md Wagtail — `hasattr(instance, 'blogpostpage')` false-matched on unrelated page types in signal handlers.
- `drf-nonatomic-counter`: todos/archive 113, 116 — `obj.x_count += 1` raced under
  concurrent requests; fixed with `F()` expressions.
- `kimi-review-engine-drift-locked`: codified from the staleness gate failure
  during todo 132 (PR #308) — this session exercised the exact scenario.

**Criterion 4 — Candidate-capture path decision:**
Decision: YES — exercise on the next real `/codify` invocation. Rationale: all 7
existing triggers are hand-seeded; the automated capture path (codify→capture_trigger
→triggers.json candidate) has never produced a real-world trigger. Running it once
end-to-end would confirm the path works OR surface a bug. Low cost; high signal.

## Notes

`.claude/` hook edits are self-mod-blocked under Auto Mode; `scripts/inject/` and
the reporter are not. Keep telemetry privacy-safe (IDs + paths, not code
contents). Keep triggers high-precision — a noisy trigger trains banner-blindness.
Related: todo 127 (gate harness tests in CI) protects the mechanism; this todo
measures whether it works.
