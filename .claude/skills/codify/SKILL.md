---
name: codify
description: Use at the end of any session to extract and preserve patterns, learnings, and review rules discovered during the session's implementation work
---

# Codify

You are running the codify workflow. Codify patterns, learnings, and agent rules
from the current branch's implementation work. **Never skip steps.**

## Step 1 — Assess the branch diff

Run:

```bash
git diff main...HEAD --stat
```

Build a list of changed-file domains (read top-to-bottom, a path may match
several rows):

| Changed path matches                                    | Domain label(s)            |
| -------------------------------------------------------- | -------------------------- |
| `backend/apps/**/migrations/*`                           | `database`, `security`     |
| `backend/apps/blog/**`                                   | `wagtail`, `api`           |
| `backend/apps/**/serializers.py`, `**/api/**`            | `api`                      |
| `backend/apps/**/views.py`, `**/viewsets.py`, `**/permissions.py` | `api`, `security` |
| `backend/apps/**/models.py`                              | `database`, `security`     |
| `backend/apps/**/tasks.py`, `**/celery*`                 | `celery`                   |
| `backend/apps/**/cache*.py`, `**/signals.py`             | `caching`                  |
| `backend/**/*.py` (other)                                | `security`                 |
| `web/src/**/*.tsx`                                       | `react`, `typescript`      |
| `web/src/**/*.ts`                                        | `typescript`               |
| `plant_community_mobile/**/*.dart`                       | `flutter`                  |
| `firebase/**`, `**/firebase*`                            | `firebase`, `security`     |
| `**/tests/**`, `**/test_*.py`, `**/*.test.ts*`, `**/*.spec.ts*` | `testing`           |

Combine all matched labels. If the diff is empty, output "Nothing to codify —
no changes on this branch." and stop.

## Step 2 — Run kimi-review on the branch diff

The domain labels from Step 1 double as `docs/rules/` names. Run:

```bash
git diff main...HEAD | kimi-review --scope "session: $(git branch --show-current)" --profile plant_id --rules <comma-separated-domains>
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
| Security        | `.claude/agents/security-reviewer.md`                               |
| Performance     | `.claude/agents/performance-reviewer.md`                            |
| Django / DRF    | `.claude/agents/django-drf-reviewer.md`                             |
| Wagtail         | `.claude/agents/wagtail-reviewer.md`                                |
| API design      | `.claude/agents/api-design-reviewer.md`                             |
| React / TS      | `.claude/agents/react-typescript-reviewer.md`                       |
| Flutter         | `.claude/agents/flutter-dart-reviewer.md`, `flutter-firebase-reviewer.md` |
| Firebase fns    | `.claude/agents/firebase-cloudfunction-reviewer.md`                 |
| Celery / async  | `.claude/agents/celery-async-reviewer.md`                           |
| Testing         | `.claude/agents/test-quality-reviewer.md`                           |

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

## Step 6 — Commit

Stage each file you wrote explicitly — do not `git add` whole directories.

```bash
git add docs/rules/<domain>.md docs/LEARNINGS.md .claude/agents/<agent>.md
git commit -m "docs: codify findings from $(git branch --show-current)"
```

The pre-commit `kimi-review` gate re-runs on the staged diff; resolve any
CRITICAL finding before the commit lands. Per project policy, never push to
`main` directly — codification commits ride the feature branch / PR.
