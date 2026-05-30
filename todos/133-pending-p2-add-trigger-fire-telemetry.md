---
name: add-trigger-fire-telemetry
status: pending
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

- [ ] `inject-patterns.sh` (or `match_triggers.py`) appends matched trigger IDs +
      timestamp + file to a lightweight per-session log (e.g.
      `/tmp/inject-fires-<session>.log` or a repo-ignored path). Must never break
      the hook's JSON output or block an edit (same fail-open discipline as today).
- [ ] A tiny reporter (script or `/codify` step) summarizes fire counts per
      trigger so dead/noisy triggers are visible.
- [ ] Document one concrete historical fragment each existing trigger WOULD have
      caught (turns "tested" into "demonstrated against real history").
- [ ] Decide whether the automated `candidate`-capture path should be exercised on
      the next real review so at least one auto-captured trigger exists end-to-end.

## Notes

`.claude/` hook edits are self-mod-blocked under Auto Mode; `scripts/inject/` and
the reporter are not. Keep telemetry privacy-safe (IDs + paths, not code
contents). Keep triggers high-precision — a noisy trigger trains banner-blindness.
Related: todo 127 (gate harness tests in CI) protects the mechanism; this todo
measures whether it works.
