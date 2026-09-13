---
status: in_progress
priority: p2
issue_id: "369"
tags: [harness, docs-rules, hooks]
dependencies: []
---

# Most binding rules are never actually injected — the 8800-byte cap silently drops them

## Problem

`CLAUDE.md` presents `docs/rules/` as **write-time enforcement** ("Enforced
write-time by `docs/rules/triggers.json`" appears twice in the Critical Gotchas
list). For most rules that is not true today. `inject-patterns.sh` assembles the
discipline preamble plus every routed domain file, then cuts the whole thing at
**8800 bytes** — mid-file, with no regard for rule boundaries.

**This is not a multi-domain problem, and routing is not at fault.** The rule
files are domain-specific by design and `routing.json` works: most paths pull
one or two domains. A single-domain edit still truncates, because
`_discipline.md` (4426 B) is always prepended and consumes half the budget,
leaving roughly **4.4 KB** for the domain's own rules. Measured on the cleanest
possible case — `plant_community_mobile/lib/main.dart` routes to `flutter` and
nothing else:

```text
flutter.md size          : 12127 chars
injected context size    : 8899 chars
truncated?               : True
flutter.md bytes injected: 4227  (34% of the file)
LAST injected line       : '  every'
```

Two thirds of the domain's rules never arrive, and the last one to survive is
cut mid-word. Eight of the thirteen rule files exceed the 8800 B cap **on their
own**, before any second domain is considered:

| file | bytes | |
| --- | --- | --- |
| `testing.md` | 41514 | tail never injects |
| `security.md` | 24517 | tail never injects |
| `react.md` | 20321 | tail never injects |
| `database.md` | 19728 | tail never injects |
| `wagtail.md` | 18298 | tail never injects |
| `api.md` | 16289 | tail never injects |
| `forum.md` | 12347 | tail never injects |
| `flutter.md` | 12204 | tail never injects |
| `celery.md` | 6449 | fits alone, not alongside another |
| `_discipline.md` | 4426 | always first |
| `caching.md` | 2477 | fits |
| `firebase.md` | 1403 | fits |
| `typescript.md` | 1224 | fits |

These files are **append-only by convention**, so the newest rule — the one
written because the mistake just happened — is always the first to be cut.

## Findings

Measured 2026-09-07, not inferred.

- The cap is `head -c 8800` at `.claude/hooks/inject-patterns.sh:116`, applied
  to the **assembled** context (`_discipline.md` + every routed domain file).
  `THRESHOLD=9000` guards it. The stated reason is real and not arbitrary:
  *"Claude Code's hook-output cap is ~10K"*.
- Overflow is copied to `/tmp/plant-id-injection-context.$$.md` with a pointer:
  *"Read that file for the rest before editing."* So nothing is lost on disk —
  but the rule only binds if the agent follows the pointer, which is a much
  weaker guarantee than inline injection and is not what `CLAUDE.md` claims.
- Multi-domain paths compound it but are not the cause.
  `backend/plant_community_backend/settings.py` routes to
  `api,security,database` (~60 KB); the injected context is 8897 chars and
  contains **only** `api` content — `security.md` and `database.md` arrive as
  zero bytes. The single-domain `main.dart` measurement above is the one that
  matters, because it holds even when routing is perfectly selective.
- Concretely, from todo 357: a CORS rule appended to `api.md` lands at char
  **15416** of 16185 and is cut. The same rule in `typescript.md` (1216 B) lands
  at char 634 and injects — verified by running the hook and grepping its output.
- **`kimi-review` has a second, independent cap**: `--pattern-max-chars`
  defaults to **12000, per file** (`scripts/kimi-review:51,179`), and
  `.claude/hooks/kimi-review.sh:59` passes `--rules` from the same
  `route_domains.py`. So the `api.md` rule above is cut at the commit gate too —
  it is documentation, not enforcement, at both gates.
- Compounding: domain rules are deduped **once per session** via
  `/tmp/inject-${SESSION_ID}-${DOMAIN}` markers
  (`inject-patterns.sh:96-100`). A domain is injected once — and if that once is
  the truncated version, the rest of that file is never seen again all session.
- This is the same class of failure as todo 356's false green: the mechanism
  runs, reports success, and covers less than its description claims.

## Recommended Action

Decide the policy first; the implementation is small either way. Options, not a
prescription:

1. **Budget per domain rather than truncating the concatenation.** Give each
   routed domain an equal share of the remaining bytes so a three-domain path
   gets some of all three instead of all of the first and none of the rest.
2. **Cut on rule boundaries, never mid-bullet.** Truncating between `- **…**`
   items keeps every surviving rule readable; today a rule can be cut mid
   sentence.
3. **Inject the newest rules first.** These files are append-only and the
   newest entry is the one most likely to be load-bearing, yet it is always
   first to be dropped. Reversing within a file inverts the bias at no cost.
4. **Split the oversized files** so each stays under budget (e.g. `testing.md`
   at 41 KB is 9× the effective budget). This is the only option that fixes
   `kimi-review`'s per-file 12000 cut as well.
5. **Raise `--pattern-max-chars`** for `kimi-review`, which is not bound by the
   hook-output cap at all — a cheap, independent win.

Whatever is chosen, make the guarantee honest: either the rules bind at write
time, or `CLAUDE.md` should stop saying they do.

## Scope

- `.claude/hooks/inject-patterns.sh` (the cap, the assembly order, the dedup)
- `.claude/hooks/test-inject-patterns.sh` (add coverage for the truncation path)
- `scripts/kimi-review` / `.claude/hooks/kimi-review.sh` (the 12000/file cap)
- `docs/rules/*.md` if splitting is chosen
- `CLAUDE.md`'s "Enforced write-time" wording if it is not

Out of scope: rewriting rule *content*, and the `triggers.json` mechanism, which
is separate and matches on patterns rather than being subject to this cap.

## Acceptance Criteria

- [x] A **single-domain** edit receives that domain's rules in full, or a
      documented, deliberate subset — proven by driving `inject-patterns.sh`
      with a synthetic event. `main.dart` → `flutter` is the reference case;
      today it gets 34%.
- [x] A path routing to 3 domains injects content from **all three**, proven the
      same way by grepping for a distinctive string from each file.
- [x] Truncation never cuts mid-bullet: the last surviving line of a truncated
      injection is a complete rule.
- [x] A rule appended to the end of the largest routed file is reachable at
      write time, or `CLAUDE.md` no longer claims write-time enforcement for
      that domain — state which was chosen and why.
- [ ] `kimi-review`'s per-file cut is addressed or explicitly accepted with a
      recorded reason.
- [ ] `.claude/hooks/test-inject-patterns.sh` covers the truncation path and
      passes; harness CI green.
- [ ] Evidence quoted in the Work Log for each of the above — the byte counts
      before and after, not a description.

## Technical Details

- `.claude/hooks/inject-patterns.sh:95-121` — assembly, dedup markers, `THRESHOLD=9000`, `head -c 8800`
- `scripts/kimi-review:51,179` — `--pattern-max-chars` default 12000, per file
- `.claude/hooks/kimi-review.sh:47,59` — routes via `route_domains.py`, passes `--rules`
- `scripts/inject/route_domains.py`, `docs/rules/routing.json` — routing (order is load-bearing)
- `docs/rules/_discipline.md` — 4426 B, always prepended

## Notes

p2, not p1: nothing is broken at runtime and the spill file means no rule is
lost on disk. It is p2 rather than p3 because the gap is **invisible** — the
hook reports success, the rule exists, `route_domains.py` confirms the path
routes, and every one of those checks passes while the rule is never shown. That
is precisely how todo 357's CORS rule would have been believed shipped when only
one of its two copies actually binds.

Editing `.claude/` may require the user to disable Auto Mode's harness
self-modification block first.

## Work Log

### 2026-09-07 - Filed while verifying todo 357's rule actually shipped

- Found by running `inject-patterns.sh` directly with a synthetic `Write` event
  rather than trusting `route_domains.py`, after the CORS regression in todo 357
  made "the mechanism ran" versus "the mechanism covered this" a live
  distinction.
- All byte counts and character offsets above were measured, not estimated.

## Concrete instance: todo 379's rule never ships (measured 2026-09-08)

A rule appended to `docs/rules/testing.md` by todo 379 — "a revert control is
not a control while both arms share uncommitted files" — **does not reach the
model at all.** Measured by running the hook, not by reading `route_domains.py`:

```
$ jq -n --arg fp "$PWD/backend/conftest.py" '{tool_name:"Write",session_id:"probe",
    tool_input:{file_path:$fp,content:"x"}}' | bash .claude/hooks/inject-patterns.sh
injected bytes: 8898        (of 111,822 assembled)
TRUNCATED marker: True
[RULES — testing] section reached at all: False
```

`testing.md` is 44.6 KB and the rule is at line ~593 of 603. The cut lands
inside the *api* rules, so the testing section never starts. An independent
review pass reproduced this (`grep -c 'revert'` on the emitted context → 0).

This is the append-only trap this todo already names, with a price attached: a
rule written specifically to prevent a repeat of a wrong report to the user is
documentation only until this todo lands. Hoisting it to the top of
`testing.md` would only evict a different rule — the fix has to be structural.

### 2026-09-13 - Fixed (PR pending review)

Options 1, 2 and 5 from Recommended Action, plus a variant of 3. Option 4
(splitting the eight oversized files) was **not** taken: it is a large,
churn-heavy edit to append-only documents that would have to be repeated every
time a file grows again, and raising `kimi-review`'s cap solves the half of the
problem that motivated it.

`scripts/inject/budget_rules.py` (new) assembles the routed rule files to fit a
byte budget:

1. **Budget per domain, not per concatenation.** Equal shares, with the slack
   from files smaller than their allocation redistributed to the ones that need
   it — otherwise a `typescript` (1.2 KB) + `testing` (46 KB) route wastes most
   of typescript's half.
2. **Head + tail, not head alone.** An over-budget file contributes its opening
   (framing and oldest, most-settled rules) and its **ending** (the newest
   rules), with a marker naming exactly how many bytes were elided. This is the
   part that fixes the append-only bias.
3. **Cut on rule boundaries** — before a top-level list bullet, a `#` heading
   or a blank line, never mid-sentence.

`.claude/hooks/inject-patterns.sh` computes the budget as whatever is left of
the 8800-byte cap after the discipline floor and any triggers, and fails open the
same way the router already does.

**Verified by running the hook with synthetic events:**

| Case | Before | After |
| --- | --- | --- |
| `main.dart` → `flutter` alone | 4227 of 12127 B (34%), cut mid-word at `'  every'` | complete rules, head+tail, last line a whole sentence |
| `settings.py` → `api,security,database` | `api` only; the other two **0 bytes** | all three present, ~1.3 KB each |
| payload size | 8899 B | 8236 B (under the cap) |
| elision markers | n/a | 3, **all** starting their own line |

**AC 4, the decisive one, mutation-tested.** A sentinel appended to the very end
of `testing.md` — the largest file, 46 KB, on a four-domain route — **is now
injected**. It sits at offset 45921 against an old effective budget of ~4332, so
the old hook could never have reached it. `testing.md` was restored from a copy
and the restoration verified by grep.

So the answer to "rules bind, or `CLAUDE.md` stops claiming they do" is **both,
honestly**: the claim now holds for the newest rules and for every routed domain,
and `CLAUDE.md` gained a "What 'injected' actually guarantees" paragraph saying
plainly that a rule in the **middle** of a large file may still be elided, and
that a rule which must bind at the exact line belongs in `triggers.json` — which
is not subject to this budget.

**AC 5 — `kimi-review`'s independent cap.** `--pattern-max-chars` defaults to
**12000 per file**, cutting 8 of the 13 rule files at the commit gate
(`testing.md` 46 KB, `security.md` 26 KB, `react.md` 20 KB, …). It is not bound
by the hook-output limit at all, so `.claude/hooks/kimi-review.sh` now passes
**60000**: covers every rule file today with headroom, and still bounds growth —
the widest route is 4 domains, and 4 × 60000 chars is ~60k tokens against
kimi-review's 131072 `--max-tokens`, leaving room for the diff. Changed in the
**hook**, not in `scripts/kimi-review`, which is a vendored copy under a
canonical-match check.

**Tests.** `.claude/hooks/test-inject-patterns.sh` gains four, 22 → **27
passing**. Mutation-checked against the pre-369 hook restored from `main`:
**3 of the 4 fail** there (all-three-domains, elision markers, newest-rule). The
fourth is a payload-size regression guard and correctly passes either way.

The elision-marker test was tightened after that mutation run: its first version
used `|| ! grep`, which made it pass **vacuously** on the old hook that emitted
no markers at all. It now asserts markers exist *and* are well-placed.

**Accepted, not fixed:** the per-session per-domain dedup
(`inject-patterns.sh` `/tmp/inject-${SESSION_ID}-${DOMAIN}` markers) still marks
a domain seen after one injection, even when that injection was a subset.
Re-injecting the same head+tail on every edit is noise, and with the tail now
guaranteed the once-per-session copy is representative rather than arbitrary.
Changing dedup semantics is a separate decision.
