---
status: completed
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

- **DONE (2026-09-24).** The `is_uint` check on `EFFECTIVE_BUILD` runs even under `SKIP_BUILD=1`,
  where the comment three lines above says "its number is baked in… Nothing to
  decide". `run_upload.sh` invokes `SKIP_BUILD=1 ./run_archive.sh` and maps any
  failure to `"$IPA FAILED verification"`, so a malformed `pubspec.yaml`
  reports a verification failure about a perfectly good IPA. Guard with
  `[ -z "${SKIP_BUILD:-}" ] &&`.
- ~~`asc_build_numbers.py` `highest = max(numbers) if numbers else 0` conflates
  "no builds exist", "no build's `version` parsed", and "HTTP 200 with no
  `data` key". All three print `0`, which reads as an authoritative pass.~~
  **Declined:** latent (App Store Connect holds builds 1–14 and returns them),
  and the cost of being wrong is altool's own duplicate rejection, not a bad
  ship; testing it needs an ASC response fixture harness that does not exist.
- ~~`find_app_id` does not paginate `/v1/apps?limit=200`. Fail-closed (exits 1),
  so it dies loudly rather than lying — but it dies for the wrong reason.~~
  **Declined:** fail-closed, and the account holds one app against a page of 200.
- The highest build number is taken across *all* marketing versions, while
  Apple's uniqueness is per-version. Fail-closed, but bumping to `1.1.0` and
  restarting the build number at 1 would be refused. Worth documenting as
  deliberate. **DONE (2026-09-24):** documented as deliberate in a comment at
  the comparison in `run_archive.sh`.
- **DONE (2026-09-24).** `is_uint` accepts any digit string; bash `[ -le ]` rejects >19 digits. The
  validator and the comparison disagree about what a number is. Unreachable in
  practice; a length cap in `is_uint` closes it.

### PR #747 — the response-dict drift guards

- **DONE (2026-09-24).** **The highest-value gap.** A provider body assigned to a local first —
  `body = response.text[:100]` then `{"error": f"...{body}"}` — is invisible to
  both guards. That is precisely the refactor the repair commit performs, so
  the next person fixing a sibling leak has a working bypass sitting in the
  diff. Needs a small taint pass over locals.
- ~~Other missed shapes, measured: `response.json()`, `response.raw`,
  `dict(error=...)`, `result["error"] = ...`, a dataclass/TypedDict field, a
  dict key that is a `Name` rather than a literal, and a helper call.~~
  **Declined:** zero instances of any of them on the tree; each is its own
  predicate, and the guard is a tripwire for the observed idiom, not a taint
  analyser. The new local-taint pass deliberately treats a helper call as
  opaque (following calls produced 2 false positives — see Work Log).
- ~~The logging exclusion is both too narrow and too wide. Too narrow:
  `ctx = {...}` then `logger.error(..., extra=ctx)` fires on correct
  structured logging. Too wide: it keys on the *method name*, so
  `sentry.error(extra={"error": str(e)})` is silently exempt.~~
  **Declined:** too-narrow fails LOUD (a red test on correct code, fixed when
  it happens); too-wide exempts another telemetry sink, not a response
  payload. Zero instances of either.
- ~~`BODY_ATTRS` matches by attribute name, so `{"message": comment.body}`,
  `{"detail": email.content}` and `{"message": page.body}` would fire. Zero
  instances today; the tree has 97 `.body`, 91 `.content`, 33 `.text` accesses,
  none under an error key. Clean by data, not by structure.~~
  **Declined:** a false positive fails loud, and the docstring already chose
  "no receiver-name heuristic" on purpose.
- ~~`apps/core/validators.py:134` raises
  `ValidationError(f"Invalid or corrupted image file: {str(e)}")`, which does
  reach API consumers. Same class as todo 377 but via `raise`, not a dict.
  Outside 377's stated scope; PIL exceptions carry no credential.~~
  **Declined:** outside both guards' scope, and a PIL decode error carries no
  credential or provider body.

### PR #748 — placeholder rejection

- **DONE (2026-09-24).** `backend/docs/security/PII_ENCRYPTION_IMPLEMENTATION.md` (18 hits) documents
  `FIELD_ENCRYPTION_KEY` and `EncryptedEmailField` as implemented. The package
  is now uninstalled. Needs the same archival treatment todo 365 applied.
- **DONE (2026-09-24).** The prefix test is not whitespace-tolerant: `value.startswith("REQUIRED__")`
  misses `" REQUIRED__…"`, and `python-decouple` does not strip values read
  from `os.environ` (only from `.env` file lines). Direction is safe — this can
  only weaken the guard, never fire it spuriously — but a paste with a leading
  space into Railway slips it. `value.strip().strip('"\'')` closes it.
- ~15 non-`REQUIRED__` placeholders in `.env.example` remain unguarded,
  including `GITHUB_CLIENT_SECRET`, whose placeholder literally contains
  "secret". Consistent with #748's scope; listed here so it is not lost.
  **Scheduled as todo 436** (12 counted, listed there).
- **Open question, deliberately not answered in-session:** does any
  non-production, non-DEBUG context (a Railway staging/preview environment, or
  an operator running `manage.py` with `DEBUG=False`) hold a hand-chosen
  `JWT_SECRET_KEY`? If every one is `token_urlsafe`/`openssl`-generated, the
  new substring loop cannot fire. Production `web` and `forum-prune-cron` were
  both checked before #748 opened.

### PR #749 — log-prefix sweep

- `backend/packages/` and `backend/plant_community_backend/` are inside the
  trigger's `path_glob` but were never swept and have no stated baseline —
  1/19 and 8/8 unprefixed respectively. **Scheduled as todo 436**, re-measured
  2026-09-24: 1 of 20 and 5 of 8.
- ~~The trigger fires on two `core/` files that are not live-code violations:
  module-docstring examples in `core/utils/pii_safe_logging.py:10-12`, and
  `core/tests/test_requests_exception_drift.py`, which the checker excludes as
  a test file. `path_glob` has no negation, so there is no clean minimal fix —
  it is a limit of the matcher, not a bug in this trigger.~~
  **Declined:** a matcher limit (no glob negation), and the cost is an
  advisory nudge on two files.
- ~~`add_log_prefixes.py` writes file-by-file, so a failure on a later file
  leaves earlier files written, contradicting its own "refusing to write a
  partial sweep" message. Mitigated by idempotency.~~
  **Declined:** a one-shot sweep tool that is idempotent — re-running after
  the fix completes the sweep; no test harness exists to justify one.
- ~~One real checker false negative: `apps/forum_host/tasks.py:71`
  `logger.info("%s (task=%s)", line, self.request.id)` takes the leading-`%s`
  escape hatch while the argument is not a `LOG_PREFIX_*`.~~
  **Corrected, then scheduled:** the CHECKER counts it unprefixed (it is in
  `--list`); the escape hatch is the TRIGGER regex's `%s\s` lookahead, which a
  line regex cannot tighten. The site itself is in todo 436's list.

### PR #750 — rule-injection budget

- **DONE (2026-09-24).** `budget_rules.py` split branch can still emit head-only when
  `boundary_after()` returns `len(text)` — i.e. when the file's final line is
  4–6× longer than today's longest. Latent: current final lines are 14–83 B
  against a 286–486 B tail budget. The tail-only branch guards this with
  `if not body: return ""`; the split branch does not.
- ~~A headers-only payload arms the session dedup markers: if every share drops
  below ~230 B, `assemble()` still emits the `[RULES — d]` headers with empty
  excerpts, and the hook writes the per-domain dedup marker — suppressing those
  domains for the rest of the session having delivered zero rule bytes.
  Unreachable today (needs >2600 B of trigger output; the measured maximum is
  574 B), but nothing caps trigger hit count.~~ **Declined:** unreachable by
  4.5x, and the fix lives in `inject-patterns.sh`'s dedup semantics.
- ~~`RULES_RESERVE=400` now reserves for a branch that can no longer fire —
  post-PR the total is ≤ 8401 against a 9000 threshold. That is ~10% of the
  budget, ~80 B per domain at 5 domains, withheld every time.~~
  **Declined:** a safety margin; reclaiming it couples the hook's arithmetic
  to budget_rules' current bound, for ~80 B per domain.
- ~~`kimi-review`'s own truncation is still `content[:max]` — head-only, counted
  in characters. The append-only bias returns there if any rules file passes
  60000 chars. Largest today is 45,916.~~ **Declined:** `scripts/kimi-review`
  is a drift-locked vendored engine (trigger `kimi-review-engine-drift-locked`;
  a direct edit fails the pre-commit gate) — fix it upstream if ever needed.
  Largest rules file re-measured 2026-09-24: 46,741 B.

### PR #751 — the shell trigger

- **DONE (2026-09-24).** `**/*.sh` cannot reach three repo-root scripts (`fnmatch`'s `*` crosses `/`,
  but the pattern still requires one): `create_github_issues.sh`,
  `create_github_labels.sh`, `setup_project_board.sh`.

### PR #744 — archived dependency docs

- ~~Unmarked stale version caps remain in QUICKREF/SECURITY_AUDIT (Django `<5.3`
  vs 6.1.1, Pillow `<12.0` vs 12.3.0, wagtail `<7.2` vs 8.0, pytest `<9.0` vs
  9.0.3, sentry-sdk `>=3.0.0` vs a 2.68.1 pin). Covered by the banner's
  explicit "not exhaustive" hedge, and none is knowingly vulnerable — they are
  stale, not dangerous.~~ **Declined:** 20 cap lines, all covered by the
  banner's "not exhaustive" hedge; none is knowingly vulnerable.
- ~~Todo 365's AC 1 ("Neither file prescribes installing django-celery-beat") is
  checked while the `pip install` lines still exist with a `do not run` marker.
  Defensible on intent, literally false.~~ **Declined:** 365 is an archived
  record; the marked lines no longer prescribe anything.
- **DONE (2026-09-24).** QUICKREF's "Contact & References" cites `/KEY_ROTATION_INSTRUCTIONS.md` at
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
- [x] Slice 1 (guard durability) is either implemented or explicitly declined
      per item, with the reason recorded here.
- [x] Slice 2 (doc archival) is complete: no auto-discoverable doc describes
      `FIELD_ENCRYPTION_KEY` or `EncryptedEmailField` as implemented.
- [x] Slice 3 (coverage extension) is either scheduled as its own todo or
      declined, with the baseline counts recorded.
- [x] Any item declined is struck from this file with a one-line reason, so a
      later reader cannot mistake "not done" for "not decided".

## Work Log

### 2026-09-24 - every finding done, declined or scheduled

Each "done" item has a test that failed before the fix and passes after, and a
mutation check. Each declined item is struck through above with its reason.

**Slice 1 — guard durability**

- #743 `SKIP_BUILD` guard → **done.** New
  `plant_community_mobile/scripts/test_run_archive.sh` runs a copy of the
  script against fake config, a stubbed ASC query and a `flutter` that refuses
  to run. Before: `SKIP_BUILD=1` + `version: 1.0.0` died "build number must be
  a bare integer" (5 cases, 2 passed / 3 failed); after: it reaches "no ipa
  at", 5/5. A no-`SKIP_BUILD` control proves validation still fires.
- #743 `is_uint` length cap (18 digits) → **done.** Before, a 20-digit
  `BUILD_NUMBER` or ASC value made `[ -le ]` error inside the `elif`, the
  duplicate check was skipped and `flutter build` ran (reproduced:
  `FLUTTER_WAS_CALLED`); after, both are refused first. Wired into
  `harness-ci.yml`. shellcheck clean.
- #743 per-version highest → **documented** as deliberate (fail-closed) at the
  comparison. `highest=0` conflation and apps pagination → declined.
- #747 local-taint gap → **done**, in both response guards
  (`test_requests_exception_drift.py`: `_tainted_names` + `_carried`). New
  planted test `test_the_guards_follow_a_local_one_hop_and_further` covers
  one hop, two hops, and three quiet shapes (logged body, subscript target,
  same name in another function). Mutation `return set()` → it fails. **The
  measurement changed the design:** following taint through every call found
  2 false positives on the tree (`error = readable_message(e)` in
  `plant_identification/api/simple_views.py`, the todo-320 sanitiser; and
  `data = json.loads(request.body)` in `blog/api_views.py`, the client's own
  body). Taint now follows value-preserving expressions only (slices,
  f-strings, method calls on the value, `str`/`repr`/`.format`); the sweep is
  back to 0 offenders, 1166 passed.
- #750 split-branch head-only → **done.** `budget_rules.excerpt()` now falls to
  the tail-only path when the tail is empty, via one `tail_only()` helper (the
  block was duplicated, and the copy lacked the `if not body` guard). New
  `scripts/inject/test_budget_rules.py` reproduced it (3 shares, head + marker
  + nothing) and passes after; a control proves ordinary files still split.
  `.claude/hooks/test-inject-patterns.sh` 29/29 (run outside the sandbox — it
  writes `/tmp`; inside, it fails 21/29 identically before and after the fix).
- #748 whitespace-tolerant prefix → **done**, at BOTH sites:
  `reject_insecure_value()` and `validate_environment()`'s `api_key_checks`
  loop now call `is_required_placeholder()`. New
  `test_a_padded_placeholder_refuses_to_boot` (value wrapped as ` '…' `): 4/4
  failed before, 11/11 in the file after. Mutation: reverting only the loop
  site fails exactly PLANT_ID and PLANTNET. `secret-management.md` updated.
- #751 root-level `.sh` → **done.** `path_glob` `**/*.sh` → `*.sh`; new
  `TestShellNumericCompareReachesRootScripts` failed on
  `create_github_issues.sh` before, 106/106 after.
- Declined (struck above): the other #747 shapes, the logging-exclusion and
  `BODY_ATTRS` notes, `validators.py:134`, headers-only dedup, `RULES_RESERVE`,
  kimi-review truncation, the `core/` trigger fires, `add_log_prefixes.py`
  partial write.

**Slice 2 — doc archival**

Mirrors todo 365: `git mv` of `PII_ENCRYPTION_IMPLEMENTATION.md` to
`docs/archive/implementations/` (markdownlint-excluded), then an ARCHIVED
banner saying it was **never implemented** (no model used
`EncryptedEmailField`; `User` inherits the plain `EmailField`) with a
what-exists-instead table, inline `SUPERSEDED (todo 367)` markers on every
actionable fenced block and on each false "implemented" claim, an index line in
`docs/archive/README.md`, and the `.secrets.baseline` entry re-pointed rather
than regenerated. Todo 023's citation of the old path is a point-in-time
record and left as written. Verification: `git grep -l
'EncryptedEmailField\|FIELD_ENCRYPTION_KEY'` outside the archives returns only
files that say "removed". #744's stale `/KEY_ROTATION_INSTRUCTIONS.md` link
re-pointed; the version caps and 365's AC wording declined.

**Slice 3 — coverage extension** → scheduled as **todo 436**, with baselines
re-measured today: packages 1 of 20, `plant_community_backend` 5 of 8, apps
tail 7 of 671; 12 non-`REQUIRED__` placeholders listed. The "#749 checker
false negative" at `forum_host/tasks.py:71` was a misdiagnosis: the checker
counts it; the trigger regex is what exempts it.

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

### 2026-09-24 - Review round 1 (bundled /code-review, PR #822): 5 repaired

- **`--next` still died under SKIP_BUILD.** `BUILD_NUMBER=next` exported for
  a build is inherited by `run_upload.sh`'s `SKIP_BUILD=1 ./run_archive.sh`,
  which skips the App Store Connect query, so the `--next` branch died and a
  good IPA was reported as failing verification. The branch now runs only
  without SKIP_BUILD. New case 1b in `test_run_archive.sh` (6/6; red with
  the guard removed).
- **The new head-only guard missed a trailing blank line.** A final rule
  ending in `"\n\n"` left a lone `"\n"` tail. The guard is now
  `not text[tail_start:].strip()`. New test red with the old guard.
- **`is_required_placeholder` still missed paste shapes**: quote-then-space,
  backticks, a whole `KEY=REQUIRED__...` line. It is now a substring test
  (no real key contains `REQUIRED__`). The padded-placeholder test now
  asserts a non-zero exit and covers all four shapes; 4 of them go red with
  the stripped-prefix check.
- `triggers.json`: `**/*.bash` → `*.bash`, so repo-root `.bash` scripts
  fire the trigger too.
- Deferred to todo 440: the drift guards' remaining reach limits (exception
  taint after the handler, `str.join`, loop/`with`/comprehension targets,
  nested-def scoping) and `budget_rules`' tail-only fallback returning `""`
  (predates this PR).
