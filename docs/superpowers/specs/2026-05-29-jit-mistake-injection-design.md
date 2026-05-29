# Just-in-Time Mistake Injection — Design

- **Date:** 2026-05-29
- **Status:** Revised after review (2026-05-29); awaiting re-approval before implementation plan
- **Author:** Claude + William
- **Topic:** Close the loop from recurring mistakes back into write-time context

## Problem

The harness is heavy on *detection* (kimi-review gate, audit, full-review, 12+
reviewer agents) and *closing* (130 archived todos), but light on *prevention*.
The same bug classes recur — five forum `@action` endpoints shipped without a
rate limit (todos 104–109), repeated non-atomic/`hasattr` mistakes — because the
rules that would have caught them live in `CLAUDE.md` and static
`docs/rules/<domain>.md` docs that, in the user's words, "only work some of the
time."

`inject-patterns.sh` is a PreToolUse hook that *should* fix this, but has four
concrete failure modes:

1. **Path-aware, not content-aware.** It sees the filename, never the code being
   written. It can say "here are all the API rules" but never "you're adding an
   `@action` with no ratelimit."
2. **Static, not mistake-derived.** It injects hand-curated rule docs; it never
   reads `LEARNINGS.md` or recent findings. No closed loop from "what we got
   wrong last session" → "what we warn about now."
3. **Banner blindness.** The same ~40 lines inject on every edit of a file type;
   by the third edit they're wallpaper and get skimmed.
4. **Advisory only.** (Out of scope for v1 — see Non-Goals.)

## Goals

- Inject the **specific** recurring-mistake warning that matches *the code being
  written*, right before the Edit/Write.
- Close the loop: a caught mistake becomes a future just-in-time warning, both
  manually (`/codify`) and automatically (from review).
- Keep an always-on discipline floor on every write.
- Surface the long-form pattern library by **pointer**, not by dumping it.

## Non-Goals (v1)

- **No blocking.** The hook never denies or `ask`s on an edit. Pure context
  injection. (A guard tier is a possible later phase; explicitly out of v1
  because of prior friction with kimi-review false `[CRITICAL]` blocks.)
- **No LSP-first rule yet.** The LSP tool does not work in this repo (no Python
  server; TS/Dart fail on workspace-root mismatch — verified 2026-05-29).
  Standing up LSP is a separate tracked todo; the always-on LSP bullet is added
  only after the tool is verified.
- No migration of the existing `docs/rules/<domain>.md` content into the trigger
  format. They keep working as-is.

## The core invariant (and its honest scope)

The **mistake-trigger tier injects only when a pattern matches the edit.** Zero
matches → zero injected trigger text. This cures banner blindness **for the
variable, high-volume tier** — the v0 wall was ~40 lines of domain rules on
*every* edit; v1 drives the variable content to near-zero on most edits.

It does **not** make the always-on discipline floor immune to blindness — that
tier injects 4 bullets unconditionally, by deliberate user requirement. The bet:
a small fixed floor stays tolerable where a large variable wall does not, and
keeping the variable tiers near-zero (triggers gated, domain rules deduped per
session) is what preserves the floor's salience. If the floor itself goes blind,
that is *measured* (see Efficacy) and addressed later — not claimed solved here.

## Efficacy hypothesis & success metric

**Why a shorter advisory should beat the v0 wall** (the open question: if injected
context already gets skimmed, why will *this* injected context work?): banner
blindness is not "all injected text is ignored" — it is a *relevance + repetition*
failure. v0 injects the same large, mostly-irrelevant checklist on every edit, which
trains skimming. v1 injects a short, *specific*, *novel* line that fires only on the
real risk in the real code ("you're adding an `@action` with no ratelimit, here").
The bet is that specificity + timing + novelty raise the act-on rate — not that
injection is magic. If the bet is wrong, the metric below will show it, and the
deferred `ask`/guard tier becomes justified.

**v1 success metric — recurrence rate of seeded bug-classes.** Baseline: the
104–116 cluster (≥5 ratelimit-missing forum actions, non-atomic counts) plus the
CLAUDE.md gotchas, all caught *after* the fact. After v1 ships, track how often the
seeded trigger-classes reappear in new kimi-review/audit findings and new todos.
Decision rule: if seeded-class recurrence does **not** measurably drop over ~4 weeks
of feature work, escalate to the `ask`/guard tier rather than piling on more
advisory triggers. That is the signal that tells us whether "specificity beats
volume" actually held.

## Design — three injection tiers

| Tier | Fires when | Content | Banner-blindness control |
|------|-----------|---------|--------------------------|
| **Discipline** | every Edit/Write/MultiEdit, unconditionally | `docs/rules/_discipline.md` | short (4 bullets); the always-on floor |
| **Mistake triggers** | a trigger's path glob + content regex match the new code | the specific warning + a one-line `pattern_ref` pointer | content-gated (the invariant) |
| **Domain rules** | file path maps to a domain | `docs/rules/<domain>.md` checklist | **deduped: once per session per domain** (keyed on `session_id`) |

Injection order in the hook output: **discipline → matched triggers → domain
rules.** Triggers lead the variable content because they are the most specific.

### Architecture principle: dumb hook, smart data

The `.claude/` self-mod classifier blocks editing the hook. So the hook is edited
**once** into a generic match-and-inject engine and then never touched again. All
recurring-mistake knowledge and all match logic live **outside** `.claude/`, in
files that can be edited freely:

- Data + logic under `docs/` and `scripts/` → editable directly.
- `.claude/hooks/inject-patterns.sh` and the `/codify` skill → edited once,
  handed to the user as ready-to-apply diffs.

### 1. Trigger index — `docs/rules/triggers.json`

The machine-matchable layer `LEARNINGS.md` lacks. One entry per recurring
mistake:

```json
{
  "id": "drf-action-no-ratelimit",
  "domains": ["api", "security"],
  "path_glob": ["backend/**/views*.py", "backend/**/viewsets*.py"],
  "content_present": "@action\\b",
  "content_absent": "ratelimit|is_ratelimited|Ratelimited",
  "message": "New @action endpoint — confirm a rate limit applies. 5 forum actions shipped without one (todos 104-109).",
  "pattern_ref": "backend/docs/patterns/architecture/rate-limiting.md",
  "source": "todos/archive/104-109",
  "added": "2026-05-29",
  "severity": "warn"
}
```

Field semantics:

- `path_glob` (required, array): repo-relative `fnmatch` globs. Trigger considered
  only if at least one matches the edited file.
- `content_present` (optional regex): tested against the **new edit fragment**
  (the text being introduced). Must match for the trigger to fire. Semantics:
  "are you *introducing* this construct?" If omitted, the trigger is path-only
  (rare).
- `content_absent` (optional regex): tested against the **resulting file**
  (post-edit content), **not** the fragment. If it matches, the trigger is
  **suppressed**. Semantics: "...and is the mitigation missing from the file?"
  This asymmetry is load-bearing — see the matcher section. Testing absence
  against a fragment is unsound (absence-in-a-fragment ≠ absence-in-the-file) and
  was the original false-positive bug.
- `pattern_ref` (optional): path to the relevant long-form pattern doc, surfaced
  as a one-line pointer.
- `severity`: `warn` (human-curated / promoted) | `info` | `candidate`
  (auto-captured, prunable).

### 2. Matcher — `scripts/inject/match_triggers.py`

Pure-stdlib Python, standalone-testable. Reads the PreToolUse JSON from stdin:

1. `tool_name` ∈ {Edit, Write, MultiEdit}, else exit 0.
2. `file_path` ← `tool_input.file_path`; normalize to repo-relative.
3. **Fragment** (newly-introduced text) ←
   `tool_input.new_string` (Edit) /
   `tool_input.content` (Write) /
   `"\n".join(e.new_string for e in tool_input.edits)` (MultiEdit).
4. **Resulting file** (post-edit content), used only for absence checks:
   - Write → `tool_input.content` (already the whole file).
   - Edit → `disk.replace(old_string, new_string)`, reading the pre-edit file
     from `file_path`.
   - MultiEdit → apply each `(old_string → new_string)` to `disk` in order.
   - If the file can't be read, fall back to `disk + "\n" + fragment` as an
     over-approximation that errs toward **suppression** (fewer false positives).
5. For each trigger: fire iff
   `any(fnmatch(path, g) for g in path_glob)`
   **and** (`content_present` absent or `re.search(content_present, fragment)`)
   **and** (`content_absent` absent or **not** `re.search(content_absent, resulting_file)`).
6. Print formatted hits (severity-tagged, with `pattern_ref` pointer), or nothing.

The asymmetry is deliberate: **presence is matched on the fragment** (warn about
what is being *introduced*); **absence is matched on the resulting file** (suppress
only when the mitigation genuinely exists in the post-edit file). Matching absence
on the fragment alone is unsound and is the false-positive bug this section fixes.

**Graceful degradation (requirement, not best-effort):** if `python3` is missing,
the matcher throws, or stdin is malformed, the matcher exits 0 emitting nothing,
and the hook still exits 0 with valid JSON. The injection layer must never block
or malform an edit. **MultiEdit caveat:** its `tool_input` shape is *not* in the
official hooks reference (Edit/Write are confirmed — `file_path/old_string/new_string`
and `file_path/content`). The matcher uses `tool_input.edits[]` (objects with
`old_string`/`new_string`) when present and well-formed, and otherwise falls back to
path-only matching with no content gate — never erroring. Confirm the real shape
from a captured payload during implementation.

### 3. Hook — `.claude/hooks/inject-patterns.sh` (one-time edit, handoff diff)

- **Kill switch (first line of the hook):**
  `[[ -n "${INJECT_PATTERNS_DISABLE:-}" ]] && exit 0` — instant revert with no
  commit, mirroring the existing `SKIP_KIMI_REVIEW=1` convention. (Hard revert is
  still `git checkout` of the hook file.)
- Replace the inline discipline heredoc with `cat docs/rules/_discipline.md`
  (always inject).
- After computing domains, run the matcher on the *same* stdin and append its hits
  after discipline, before domain rules. The invocation must not be able to break
  the hook's JSON output:

  ```bash
  MATCH_OUT=""
  if command -v python3 >/dev/null 2>&1; then
    MATCH_OUT=$(printf '%s' "$INPUT" \
      | python3 "$PROJECT_ROOT/scripts/inject/match_triggers.py" 2>/dev/null) \
      || MATCH_OUT=""
  fi
  [ -n "$MATCH_OUT" ] && \
    printf '\n[RECENT MISTAKES — matched this edit]\n%s\n' "$MATCH_OUT" >> "$TMPFILE"
  ```

  The matcher writes only warning text to stdout and exits 0 even on internal
  error; `2>/dev/null` discards stderr; `|| MATCH_OUT=""` absorbs a non-zero exit.
  The final context is still emitted via `jq -n --arg`, which escapes whatever
  `MATCH_OUT` held — so a malformed match cannot corrupt the hook's JSON.
- Per-session dedup for domain rules: marker file
  `/tmp/inject-<session_id>-<domain>` (`session_id` is a confirmed PreToolUse stdin
  field). Skip a domain's rules if its marker exists this session, else inject +
  create the marker. Discipline and triggers are never deduped.
- Keep the existing 9 KB overflow-spill behaviour.

### 4. Capture loop — "Both"

- **Manual (`/codify`, handoff diff):** when `/codify` writes a `LEARNINGS.md`
  entry, it also calls `capture_trigger.py` with `severity: warn` (human-curated
  → promoted). One authoring action, so the index cannot rot.
- **Auto (`scripts/inject/capture_trigger.py`, editable):** appends a trigger
  with strict dedup-on-`id`, provenance (`source`, `added`), and
  `severity: candidate`. Candidates **inject immediately** (low latency) but are
  flagged, so a later `/codify` can prune noise. **Pruning is optional and never
  required** — the system never becomes a thing to babysit. Auto-*wiring* into the
  review path (kimi-review / reviewer agents calling this script) is the
  fast-follow; the script + candidate staging ship in v1 so "Both" is real from
  day one.

### 5. Seeding `triggers.json`

Target **~6–8 high-value, regex-able triggers — not "all of `LEARNINGS.md`."** Only
mistakes with a clear textual signature qualify; entries without a reliable
signature stay as prose rules and are deliberately *not* forced into triggers (that
would manufacture false positives). v1 needs to *prove the mechanism* on the worst
recurring offenders, not be exhaustive. Concrete seed set:

- CLAUDE.md "Critical Gotchas": f-string SQL identifiers in migrations,
  `from 'react-router'` import, `useState` debounce timer, `get_permissions()`
  missing `super()`, ratelimit 403-vs-429.
- `LEARNINGS.md` entries with a regex-able signature (`hasattr` on Wagtail pages,
  etc.).
- Forum bug classes (todos 104–116): `@action` without ratelimit, non-atomic
  count updates.

### 6. Testing

Two layers, because the risky artifact is the hook, not just the matcher:

- **`scripts/inject/test_match_triggers.py`** (matcher unit tests): fixture stdin
  payloads asserting each seeded trigger fires on a positive case and stays
  silent on a negative case. Fixtures **must use realistic edit fragments**
  (a partial `new_string`/`old_string`), not whole files — otherwise they pass
  while missing the bug class above. At least one fixture per `content_absent`
  trigger must cover the **false-positive case**: an Edit whose fragment lacks the
  mitigation but whose *resulting file* (disk + edit) contains it → assert the
  trigger stays silent. The matcher reads the on-disk file for absence checks, so
  these fixtures write a real temp file and point `file_path` at it.
- **`.claude/hooks/test-inject-patterns.sh`** (hook integration, handoff diff):
  the existing test pipes JSON stdin to the hook and asserts on its output. Extend
  it with cases that pass a realistic `new_string`/`content` (not just `file_path`)
  and assert: (a) **matcher integration** — a payload that should match a seeded
  trigger produces the `[RECENT MISTAKES]` block; a non-matching payload does not;
  (b) **session dedup** — two invocations with the same `session_id` + domain
  inject domain rules only the first time, while discipline + triggers inject both
  times; (c) **discipline-from-file** — output contains the contents of
  `docs/rules/_discipline.md`; (d) **kill switch** — `INJECT_PATTERNS_DISABLE=1`
  yields empty output; (e) **degradation** — a malformed body still produces valid
  hook JSON.

## File inventory

**Created directly (under `docs/`, `scripts/` — not blocked):**

- `docs/rules/triggers.json` — seeded trigger index
- `docs/rules/_discipline.md` — always-on discipline floor (4 bullets, no LSP yet)
- `scripts/inject/match_triggers.py` — matcher
- `scripts/inject/test_match_triggers.py` — matcher tests
- `scripts/inject/capture_trigger.py` — dedup append, candidate staging
- `todos/NNN-…-stand-up-working-lsp.md` — deferred LSP work
- this spec

**Handed as ready-to-apply diffs (under `.claude/` — self-mod blocked):**

- `.claude/hooks/inject-patterns.sh` — the one-time engine edit
- `/codify` skill — manual capture integration

No `.claude/settings.json` change: the hook is already registered on
`Edit|Write|MultiEdit`.

> Contingency: if the self-mod block is inactive this session, the two handoff
> files are applied directly instead.

## Sequencing

Re-tiered so a provable spine ships before the capture machinery:

- **v1 spine (independently shippable + testable):** `triggers.json` seeded with
  ~6–8 high-value triggers + `match_triggers.py` + matcher tests + the one hook
  edit (diff, incl. kill switch + dedup) + `_discipline.md`. This alone closes the
  path-aware → content-aware gap and is verifiable end-to-end.
- **v1.1 capture ("Both"):** `capture_trigger.py` (dedup + candidate staging) + the
  `/codify` manual-capture diff. Lands after the spine proves out, so a
  capture-writer bug cannot compromise the core injection.
- **Fast-follow:** auto-wire `capture_trigger.py` into the review path; optionally
  give domain-rule docs their own triggers.
- **Deferred (separate todo):** stand up a working LSP (Python server, fix
  TS/Dart workspace-root launch, verify `findReferences`), then add the LSP-first
  bullet to `_discipline.md`.

## Verification status (checked 2026-05-29, official Claude Code docs)

- ✅ **`session_id` in PreToolUse stdin** — confirmed a top-level field, alongside
  `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`, `tool_name`,
  `tool_input`, `tool_use_id`. Domain dedup is safe to key on it.
- ✅ **Edit / Write `tool_input` shapes** — confirmed: Edit =
  `{file_path, old_string, new_string, replace_all}`; Write = `{file_path, content}`.
- ✅ **Disk is authoritative** — Edit requires the file be unchanged on disk since
  the last read (else the edit fails before string-matching); no IDE/unsaved-buffer
  divergence. Reconstructing post-edit content as `(disk with old→new applied)` is
  reliable for Claude Code's tools; the generic "unsaved editor buffer" concern does
  not apply to this tool model.
- ⚠️ **MultiEdit `tool_input` shape** — *not* in the official hooks reference.
  Handled defensively (see matcher); confirm from a captured payload at
  implementation time.
- ⚠️ **`pattern_ref` targets resolve** — verify each referenced pattern doc exists
  while seeding (e.g. `backend/docs/patterns/architecture/rate-limiting.md`). Ship
  no dangling pointers — a pointer to nothing trains the model to ignore pointers.

## Risks & mitigations

- **False-positive injections** → asymmetric matching (presence on fragment,
  absence on resulting file); tests assert positive *and* negative per trigger,
  including the absence-on-resulting-file case using realistic fragments.
- **Auto-capture noise** → candidates are flagged + provenance-stamped + dedup'd;
  pruning is optional, not load-bearing.
- **Self-mod block** → minimized to two handoff diffs; all iteration-heavy parts
  live outside `.claude/`.
- **`jq`/`python3` availability** → `jq` already a hook dependency; matcher is
  stdlib-only Python. Graceful degradation is a hard requirement (matcher section):
  missing `python3` / thrown matcher / bad stdin → hook still exits 0 with valid
  JSON, never blocks or malforms an edit.
- **`/tmp/inject-<session_id>-<domain>` markers accumulate** unbounded across
  sessions. Minor; clean opportunistically (e.g. a SessionStart sweep) — noted, not
  blocking.

## Implementation status — v1 spine (2026-05-29)

Built and verified on branch `feat/jit-mistake-injection`:

- `scripts/inject/match_triggers.py` — matcher (asymmetric matching, graceful
  degradation). ✅
- `scripts/inject/test_match_triggers.py` — 31 tests green, incl. the
  absence-on-resulting-file false-positive guard and per-trigger fire/silent. ✅
- `docs/rules/triggers.json` — 6 seed triggers, all `pattern_ref`s verified. ✅
- `docs/rules/_discipline.md` — always-on floor. ✅
- `.claude/hooks/inject-patterns.sh` — **blocked by the self-mod classifier
  (confirmed live).** Full proposed replacement shipped as
  `scripts/inject/inject-patterns.sh.proposed`. Apply with:
  `cp scripts/inject/inject-patterns.sh.proposed .claude/hooks/inject-patterns.sh`.
  Executed directly against crafted payloads — discipline + matched-mistake +
  deduped domain rules, ratelimit suppression, kill switch, and malformed-input
  degradation all verified. ⏳ awaiting user apply.

## Implementation status — v1.1 capture (2026-05-29)

Built and verified on branch `feat/jit-injection-capture` (spine merged to main
via #298):

- `scripts/inject/capture_trigger.py` — appends a trigger to `triggers.json`;
  strict dedup-on-`id` (idempotent), canonical key order, validates required
  fields + regex, drops a non-resolving `pattern_ref` with a warning. `--severity
  warn` for `/codify` (human-curated), default `candidate` for review automation. ✅
- `scripts/inject/test_capture_trigger.py` — 13 tests (build/validate, dedup,
  update, captured-then-matches end-to-end, pattern_ref resolution, CLI). ✅
- `scripts/inject/codify-capture-step.md` — handoff doc to add Step 5b + the
  Step 6 `git add` change to the (self-mod-blocked) `/codify` skill. ⏳ awaiting
  user apply.

Remaining follow-ups: auto-*wire* `capture_trigger.py` into the review path
(kimi-review / reviewers calling it with `--severity candidate` — the script
already supports it); the `test-inject-patterns.sh` hook-test extension; and the
LSP todo.
