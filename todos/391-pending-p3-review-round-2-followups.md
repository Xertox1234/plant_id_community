---
status: pending
priority: p3
issue_id: "391"
tags: [review-followup, tech-debt]
dependencies: []
---

# Round-2 review leftovers across PRs #743–#752

## Problem

Round 2 of the subagent review across the ten sweep PRs surfaced eight blocking
defects, all repaired in their own PRs. It also surfaced a tail of non-blocking
findings that are real but do not justify a third review round. Collected here
so they survive the archival pass rather than evaporating into commit messages.

None of these is a live bug. Each is either latent (unreachable with today's
data), cosmetic, or a durability limit in a guard.

## Findings

### PR #743 — `run_archive.sh` / `asc_build_numbers.py`

- The `is_uint` check on `EFFECTIVE_BUILD` runs even under `SKIP_BUILD=1`,
  where the comment three lines above says "its number is baked in… Nothing to
  decide". `run_upload.sh` invokes `SKIP_BUILD=1 ./run_archive.sh` and maps any
  failure to `"$IPA FAILED verification"`, so a malformed `pubspec.yaml`
  reports a verification failure about a perfectly good IPA. Guard with
  `[ -z "${SKIP_BUILD:-}" ] &&`.
- `asc_build_numbers.py` `highest = max(numbers) if numbers else 0` conflates
  "no builds exist", "no build's `version` parsed", and "HTTP 200 with no
  `data` key". All three print `0`, which reads as an authoritative pass.
- `find_app_id` does not paginate `/v1/apps?limit=200`. Fail-closed (exits 1),
  so it dies loudly rather than lying — but it dies for the wrong reason.
- The highest build number is taken across *all* marketing versions, while
  Apple's uniqueness is per-version. Fail-closed, but bumping to `1.1.0` and
  restarting the build number at 1 would be refused. Worth documenting as
  deliberate.
- `is_uint` accepts any digit string; bash `[ -le ]` rejects >19 digits. The
  validator and the comparison disagree about what a number is. Unreachable in
  practice; a length cap in `is_uint` closes it.

### PR #747 — the response-dict drift guards

- **The highest-value gap.** A provider body assigned to a local first —
  `body = response.text[:100]` then `{"error": f"...{body}"}` — is invisible to
  both guards. That is precisely the refactor the repair commit performs, so
  the next person fixing a sibling leak has a working bypass sitting in the
  diff. Needs a small taint pass over locals.
- Other missed shapes, measured: `response.json()`, `response.raw`,
  `dict(error=...)`, `result["error"] = ...`, a dataclass/TypedDict field, a
  dict key that is a `Name` rather than a literal, and a helper call.
- The logging exclusion is both too narrow and too wide. Too narrow:
  `ctx = {...}` then `logger.error(..., extra=ctx)` fires on correct
  structured logging. Too wide: it keys on the *method name*, so
  `sentry.error(extra={"error": str(e)})` is silently exempt.
- `BODY_ATTRS` matches by attribute name, so `{"message": comment.body}`,
  `{"detail": email.content}` and `{"message": page.body}` would fire. Zero
  instances today; the tree has 97 `.body`, 91 `.content`, 33 `.text` accesses,
  none under an error key. Clean by data, not by structure.
- `apps/core/validators.py:134` raises
  `ValidationError(f"Invalid or corrupted image file: {str(e)}")`, which does
  reach API consumers. Same class as todo 377 but via `raise`, not a dict.
  Outside 377's stated scope; PIL exceptions carry no credential.

### PR #748 — placeholder rejection

- `backend/docs/security/PII_ENCRYPTION_IMPLEMENTATION.md` (18 hits) documents
  `FIELD_ENCRYPTION_KEY` and `EncryptedEmailField` as implemented. The package
  is now uninstalled. Needs the same archival treatment todo 365 applied.
- The prefix test is not whitespace-tolerant: `value.startswith("REQUIRED__")`
  misses `" REQUIRED__…"`, and `python-decouple` does not strip values read
  from `os.environ` (only from `.env` file lines). Direction is safe — this can
  only weaken the guard, never fire it spuriously — but a paste with a leading
  space into Railway slips it. `value.strip().strip('"\'')` closes it.
- ~15 non-`REQUIRED__` placeholders in `.env.example` remain unguarded,
  including `GITHUB_CLIENT_SECRET`, whose placeholder literally contains
  "secret". Consistent with #748's scope; listed here so it is not lost.
- **Open question, deliberately not answered in-session:** does any
  non-production, non-DEBUG context (a Railway staging/preview environment, or
  an operator running `manage.py` with `DEBUG=False`) hold a hand-chosen
  `JWT_SECRET_KEY`? If every one is `token_urlsafe`/`openssl`-generated, the
  new substring loop cannot fire. Production `web` and `forum-prune-cron` were
  both checked before #748 opened.

### PR #749 — log-prefix sweep

- `backend/packages/` and `backend/plant_community_backend/` are inside the
  trigger's `path_glob` but were never swept and have no stated baseline —
  1/19 and 8/8 unprefixed respectively.
- The trigger fires on two `core/` files that are not live-code violations:
  module-docstring examples in `core/utils/pii_safe_logging.py:10-12`, and
  `core/tests/test_requests_exception_drift.py`, which the checker excludes as
  a test file. `path_glob` has no negation, so there is no clean minimal fix —
  it is a limit of the matcher, not a bug in this trigger.
- `add_log_prefixes.py` writes file-by-file, so a failure on a later file
  leaves earlier files written, contradicting its own "refusing to write a
  partial sweep" message. Mitigated by idempotency.
- One real checker false negative: `apps/forum_host/tasks.py:71`
  `logger.info("%s (task=%s)", line, self.request.id)` takes the leading-`%s`
  escape hatch while the argument is not a `LOG_PREFIX_*`.

### PR #750 — rule-injection budget

- `budget_rules.py` split branch can still emit head-only when
  `boundary_after()` returns `len(text)` — i.e. when the file's final line is
  4–6× longer than today's longest. Latent: current final lines are 14–83 B
  against a 286–486 B tail budget. The tail-only branch guards this with
  `if not body: return ""`; the split branch does not.
- A headers-only payload arms the session dedup markers: if every share drops
  below ~230 B, `assemble()` still emits the `[RULES — d]` headers with empty
  excerpts, and the hook writes the per-domain dedup marker — suppressing those
  domains for the rest of the session having delivered zero rule bytes.
  Unreachable today (needs >2600 B of trigger output; the measured maximum is
  574 B), but nothing caps trigger hit count.
- `RULES_RESERVE=400` now reserves for a branch that can no longer fire —
  post-PR the total is ≤ 8401 against a 9000 threshold. That is ~10% of the
  budget, ~80 B per domain at 5 domains, withheld every time.
- `kimi-review`'s own truncation is still `content[:max]` — head-only, counted
  in characters. The append-only bias returns there if any rules file passes
  60000 chars. Largest today is 45,916.

### PR #751 — the shell trigger

- `**/*.sh` cannot reach three repo-root scripts (`fnmatch`'s `*` crosses `/`,
  but the pattern still requires one): `create_github_issues.sh`,
  `create_github_labels.sh`, `setup_project_board.sh`.

### PR #744 — archived dependency docs

- Unmarked stale version caps remain in QUICKREF/SECURITY_AUDIT (Django `<5.3`
  vs 6.1.1, Pillow `<12.0` vs 12.3.0, wagtail `<7.2` vs 8.0, pytest `<9.0` vs
  9.0.3, sentry-sdk `>=3.0.0` vs a 2.68.1 pin). Covered by the banner's
  explicit "not exhaustive" hedge, and none is knowingly vulnerable — they are
  stale, not dangerous.
- Todo 365's AC 1 ("Neither file prescribes installing django-celery-beat") is
  checked while the `pip install` lines still exist with a `do not run` marker.
  Defensible on intent, literally false.
- QUICKREF's "Contact & References" cites `/KEY_ROTATION_INSTRUCTIONS.md` at
  repo root; it now lives in `docs/archive/2025-11/`.

## Recommended Action

Take these in three independent slices; none blocks another.

1. **Guard durability** (#747 taint pass, #750 split-branch head-only guard,
   #743 `is_uint` length cap and `SKIP_BUILD` guard). These are the ones with
   a real failure mode behind them.
2. **Doc archival** (#748's `PII_ENCRYPTION_IMPLEMENTATION.md`, #744's
   unmarked caps and the stale cross-reference). Mechanical, low risk.
3. **Coverage extension** (#749's unswept `packages/` and
   `plant_community_backend/`, #748's non-`REQUIRED__` placeholders). Each is
   a new slice of an existing sweep, not new machinery.

Settle the #748 open question first — it is one lookup and it is the only item
here that could bear on a live deploy.

## Technical Details

Every finding above was produced by a read-only subagent review of the repair
commits on PRs #743–#752 (round 2 of the two-round budget in `CLAUDE.md`), and
each was independently re-verified before being written down. Items marked
"latent" or "unreachable today" were measured, not assumed — the margins are
quoted where they matter.

Deliberately NOT included: anything already repaired in its own PR, and the
blocking findings, which are described in those PRs' commit messages.

## Acceptance Criteria

- [x] The #748 open question is answered: no non-production, non-DEBUG context
      holds a hand-chosen `JWT_SECRET_KEY`, or the ones that do are rotated to
      generated values. **Answered 2026-09-13 — no such context exists.**
- [ ] Slice 1 (guard durability) is either implemented or explicitly declined
      per item, with the reason recorded here.
- [ ] Slice 2 (doc archival) is complete: no auto-discoverable doc describes
      `FIELD_ENCRYPTION_KEY` or `EncryptedEmailField` as implemented.
- [ ] Slice 3 (coverage extension) is either scheduled as its own todo or
      declined, with the baseline counts recorded.
- [ ] Any item declined is struck from this file with a one-line reason, so a
      later reader cannot mistake "not done" for "not decided".

## Work Log

### 2026-09-13 - the #748 open question is closed

The only item here that could have bearing on a live deploy is answered, and
the answer is no. Nothing can trip #748's boot refusal.

- **Railway has exactly one environment: `production`.** (`railway status
  --json` -> `environments` = `['production']`.) There is no staging or preview
  environment, so the whole class of "some other non-DEBUG context holds a
  hand-chosen key" has no instances.
- Services are `plant_id_community`, `forum-prune-cron`, `Postgres`, `Redis`.
  Production `JWT_SECRET_KEY` is **86 chars** — `token_urlsafe(64)`, i.e.
  generated, not hand-chosen.
- `backend/.env` (the local `DEBUG=False` path) also clears the guard:
  `SECRET_KEY` and `JWT_SECRET_KEY` both have `startswith("REQUIRED__")` false
  and **zero** `INSECURE_PATTERNS` substring hits.

Checked by reading lengths and booleans only — no secret value entered the
session, which is the same method used to clear the guard before #748 opened.

Incidental, and it confirms todo 390's premise rather than this one: live
`PLANT_ID_API_KEY` is **50 chars** against a documented literal of **50**, so
length cannot distinguish them and only a direct comparison will settle it.
`PLANTNET_API_KEY` is 26 against a documented 24 — which is how we know
PlantNet was rotated and Plant.id cannot be assumed to have been.

### 2026-09-13 - Filed

- Collected from round-2 subagent review of PRs #743–#752. Eight blocking
  findings were repaired in their own PRs; this file is the non-blocking
  remainder, filed before the merges so it is not lost in the archival pass.
