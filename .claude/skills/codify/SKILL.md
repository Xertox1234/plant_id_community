---
name: codify
description: Use at the end of any session to extract and preserve patterns, learnings, and review rules discovered during the session's implementation work
---

# Codify

You are running the codify workflow. Codify patterns, learnings, and agent rules
from the current branch's implementation work. **Never skip steps.**

## Step 1 — Assess the branch diff

**First, check whether local `main` is stale** — in this repo's worktree
convention, local `main` is frequently checked out in a *different*
worktree and can sit behind `origin/main` for many merged PRs. `git diff
main...HEAD` against a stale local `main` silently includes every
already-merged change since the branch point, not just this branch's own
work (verified: an 8-file, ~700-line diff appeared as 60+ files and
~5000 lines this way). Check first:

```bash
git rev-parse main origin/main
```

If they differ, use `origin/main` as the diff base for every command in
this skill instead of `main` (do not `git checkout main` to "fix" it —
that checkout can be blocked entirely if another worktree holds `main`).

Run:

```bash
git diff <main-or-origin/main>...HEAD --stat
```

Derive the changed-file domains from the single source of truth
(`docs/rules/routing.json`) with the shared matcher — the same one the
`inject-patterns.sh` and `kimi-review.sh` hooks use. Do **not** keep a copy of the
path→domain table here:

```bash
git diff <main-or-origin/main>...HEAD --name-only | python3 scripts/inject/route_domains.py
```

This prints the comma-separated domain labels (deduped, e.g. `api,security,database`),
which double as `docs/rules/<domain>` names. If the diff is empty (no output / no
changed files), output "Nothing to codify — no changes on this branch." and stop.

## Step 2 — Run kimi-review on the branch diff

The domain labels from Step 1 double as `docs/rules/` names. Use the same
diff base (`main` or `origin/main`) determined in Step 1. `kimi-review` may
not be on `PATH` — the vendored, canonical copy is `scripts/kimi-review`
(run it as `python3 scripts/kimi-review`, with the `openai` package
available — e.g. via `backend/venv`). A large diff can take several
minutes; don't assume a timeout means failure, retry with a longer one
before concluding the tool is broken.

```bash
git diff <main-or-origin/main>...HEAD | python3 scripts/kimi-review --scope "session: $(git branch --show-current)" --profile plant_id --rules <comma-separated-domains>
```

**Store the full output in working context as `review_output`** — shell variables
do not persist between Bash invocations. Also union in any kimi-review output that
already appeared earlier in this session (the PreToolUse commit hook emits it).

## Step 3 — Apply codification criteria

**Codify if any one is true:**

- The diff contains a workaround or constraint not documented in `docs/rules/`,
  the `*/docs/patterns/` libraries, or `docs/LEARNINGS.md`.
- The diff reveals a library gotcha or platform-specific behavior.
- `review_output` contains a CRITICAL or WARNING finding — even if the fix is
  already in the diff (a finding that required a repair is exactly the kind of
  rule worth preserving).

**Skip if all are true:**

- The diff is a straightforward application of existing documented patterns.
- All `review_output` findings are SUGGESTION-only.
- The only changes are UI text, config values, or copy with no structural lesson.

If nothing qualifies, output "Nothing to codify from this session." and stop.

## Step 4 — Route each candidate

For each codification candidate, pick the destination(s) by **nature of the
finding**. A single finding may write to more than one target.

| Finding nature                                                  | Destination |
| ---------------------------------------------------------------- | ----------- |
| One-line "always do X / never do Y" rule for an existing domain  | append a bullet to `docs/rules/<domain>.md` |
| A reusable, multi-line pattern (code shape, approach, checklist) | the matching `*/docs/patterns/` doc — see table below |
| A bug, incident, or hard-won gotcha with a root cause            | append an entry to `docs/LEARNINGS.md` (append-only log) |
| A new repeatable review check                                   | the relevant review agent — see agent table below |

**Pattern-doc locations** (append a section to the closest existing file; create
a new file in the right subdirectory only if none fits):

- Backend: `backend/docs/patterns/{security,architecture,domain,performance,api,testing}/`
- Web: `web/docs/patterns/` (`react-typescript.md`, `tailwind.md`, `testing.md`)
- Mobile: `plant_community_mobile/docs/patterns/` (`flutter-patterns.md`, `firebase-auth.md`, `riverpod.md`)
- Firebase: `firebase/docs/patterns/` (`cloud-functions.md`, `firestore-rules.md`, `iam.md`)

**Review-agent update routing** (only when the finding reveals a reusable check):

| Finding domain  | Update agent(s)                                                     |
| --------------- | ------------------------------------------------------------------- |
| Security        | `.claude/agents/cross-cutting-reviewer.md`                          |
| Performance     | `.claude/agents/cross-cutting-reviewer.md`                          |
| Django / DRF    | `.claude/agents/django-drf-reviewer.md`                             |
| Wagtail         | `.claude/agents/wagtail-reviewer.md`                                |
| API design      | `.claude/agents/cross-cutting-reviewer.md`                          |
| React / TS      | `.claude/agents/react-typescript-reviewer.md`                       |
| Flutter         | `.claude/agents/flutter-dart-reviewer.md`, `flutter-firebase-reviewer.md` |
| Firebase fns    | `.claude/agents/firebase-cloudfunction-reviewer.md`                 |
| Celery / async  | `.claude/agents/celery-async-reviewer.md`                           |
| Testing         | `.claude/agents/cross-cutting-reviewer.md`                          |

## Step 5 — Write the codification

- **`docs/rules/<domain>.md`** — append the bullet under the existing list. Keep
  it one line, imperative, "always/never" phrased. Do not bloat the file; the
  inject-patterns hook pastes it verbatim before every matching edit.
- **`*/docs/patterns/` doc** — append a new `## <Pattern name>` section to the
  closest existing file. Include a short rationale and a minimal code example.
- **`docs/LEARNINGS.md`** — append a dated entry: what broke, the root cause, and
  the fix. This file is the append-only incident log — never edit prior entries.
- **Review agent** — add a checklist bullet (and a "Common Mistakes to Catch"
  entry if it is a recurring gap).

When unsure how to classify a finding, consult `.claude/agents/pattern-codifier.md`
— it encodes this project's pattern-routing logic.

## Step 5b — Emit a write-time trigger (only if the finding has a textual signature)

For any rule/learning you just codified that has a **clear, regex-matchable
signature** — a specific decorator, import, function call, or code shape that
appears in the code being written — also register a just-in-time trigger so it
fires at write-time, not only in review:

```bash
python3 scripts/inject/capture_trigger.py \
  --id <kebab-id> \
  --domains <d1,d2> \
  --path-glob '<repo-relative fnmatch glob>' \
  --content-present '<regex matched against the NEW edit fragment>' \
  --content-absent '<regex on the RESULTING file that suppresses when the fix is present>' \
  --message '<one-line warning + the fix>' \
  --pattern-ref <path/to/pattern-doc.md> \
  --source "codify: $(git branch --show-current)" \
  --severity warn
```

Rules:

- Use `--severity warn` here (human-curated). Leave `candidate` for review automation.
- Do this ONLY when a real signature exists. A signature-less lesson stays prose —
  forcing it into a trigger manufactures false positives and erodes trust in the
  whole system.
- `--content-present` matches the new fragment ("are you introducing X?");
  `--content-absent` matches the resulting file ("...and is the fix missing?").
  Omit `--content-absent` if there is no clean "already-fixed" marker.
- `--pattern-ref` must resolve to a real file; `capture_trigger.py` drops it with
  a warning if it doesn't (no dangling pointers).
- After capturing, run `python3 scripts/inject/test_match_triggers.py` to confirm
  the index still validates. For a high-traffic trigger, add a positive AND a
  negative fixture to `scripts/inject/test_match_triggers.py` before committing.
- **Build the positive fixture by pasting the REAL code that motivated the rule,
  never an idealised version of it.** A regex written from the lesson rather than
  from the source can miss the exact bug it was created for: `documentElement\.dataset\.`
  looked right and matched nothing, because the real helper aliased the element
  first (`const el = document.documentElement; el.dataset.mode = …`).
- **New fixtures must load the REAL index**, not the module-level fixture list —
  `TRIGGERS` in `test_match_triggers.py` is a hand-built two-trigger set, so a test
  written against it passes while the shipped trigger never fires. Use
  `mt.load_triggers(<repo root>)` in `setUpClass` (see
  `TestE2ESelectorAndStateTriggers`).
- **Check the negative fixture actually exercises the pattern.** A "silent" case
  that contains none of the characters the regex keys on proves nothing. `\s*=`
  matches the first character of `===`, so a read-comparison false-fired while the
  chosen negative (`expect(x).toBe(y)` — no `=` at all) stayed green. Write `=(?!=)`,
  and cover `===`, `==` and `!==` explicitly.
- **Match every spelling the rule text claims.** A rule saying "never set
  `CONN_MAX_AGE`" needs `(?i)` plus the punctuation real code puts between the name
  and the operator (`'CONN_MAX_AGE':`, `['CONN_MAX_AGE'] =`) — a lowercase
  `conn_max_age\s*=` caught only the one kwarg form and missed both canonical
  Django spellings.
- **Then confirm the shipped, already-fixed file does not self-fire** by running
  the real block through the trigger — prose that names the constant and the
  correct gated assignment must both stay silent.

**Before finishing: confirm the rule can actually reach its target files.** A
`docs/rules/<domain>.md` bullet only ships if `docs/rules/routing.json` routes
those paths to that domain — both the inject hook and the kimi gate go through
`route_domains.py`. A bullet written for files that route to no domain is inert
and nothing will ever tell you. Verify with the matcher, not by eye:

```bash
printf '%s\n' <one representative target path per rule> | python3 scripts/inject/route_domains.py
```

Empty output means the rule is undeliverable — extend that rule's `globs` in
`routing.json` first, then re-run `.claude/hooks/test-inject-patterns.sh` (order in
that file is load-bearing). This is not hypothetical: testing rules written for
`web/e2e/*.spec.js` reached nothing, because the testing globs listed `*.spec.ts`
and `*.spec.tsx` but no `.js`, and 9 of the 14 files in `web/e2e/` are `.js`.

## Step 6 — Commit

Stage each file you wrote explicitly — do not `git add` whole directories.

```bash
git add docs/rules/<domain>.md docs/LEARNINGS.md docs/rules/triggers.json .claude/agents/<agent>.md
git commit -m "docs: codify findings from $(git branch --show-current)"
```

The pre-commit `kimi-review` gate re-runs on the staged diff; resolve any
CRITICAL finding before the commit lands. Per project policy, never push to
`main` directly — codification commits ride the feature branch / PR.
