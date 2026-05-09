# kimi-review and kimi-challenge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new worker delegation CLI scripts (`kimi-review` and `kimi-challenge`) to the existing claude-coworker-model setup, and wire their delegation rules into `CLAUDE.md` and `~/.claude/settings.json`.

**Architecture:** Two independent Python scripts following the exact pattern of `ask-kimi` and `kimi-write` — same venv shebang, same `WORKER_*` env vars, same stderr cost report. `kimi-review` reads a git diff (piped or subprocess) and returns structured CRITICAL/WARNING/SUGGESTION findings. `kimi-challenge` takes a design decision and returns adversarial counter-arguments, alternatives, and risks.

**Tech Stack:** Python 3 (venv at `~/.local/share/claude-coworker/venv/`), `openai>=1.0` (already installed), argparse, subprocess.

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `/Users/williamtower/.local/bin/kimi-review` | Code review script |
| Create | `/Users/williamtower/.local/bin/kimi-challenge` | Adversarial design review script |
| Modify | `/Users/williamtower/projects/plant_id_community/CLAUDE.md` lines 176, 200–202, 214–219 | Add subsections + AUTO-delegate rules |
| Modify | `~/.claude/settings.json` | Add `Bash(kimi-review:*)` and `Bash(kimi-challenge:*)` to allow list |

---

## Task 1: kimi-review script

**Files:**

- Create: `/Users/williamtower/.local/bin/kimi-review`

- [ ] **Step 1: Verify the command doesn't exist yet**

```bash
kimi-review --scope "smoke test" 2>&1 || true
```

Expected: `command not found: kimi-review`

- [ ] **Step 2: Write the script**

Create `/Users/williamtower/.local/bin/kimi-review` with this exact content:

```python
#!/Users/williamtower/.local/share/claude-coworker/venv/bin/python3
"""Delegate code review to Kimi. Returns CRITICAL / WARNING / SUGGESTION findings."""
import argparse, os, sys, pathlib, subprocess
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("WORKER_API_KEY", os.environ.get("MOONSHOT_API_KEY", "")),
    base_url=os.environ.get("WORKER_BASE_URL", "https://api.moonshot.ai/v1"),
)

p = argparse.ArgumentParser(description="Code review via Kimi")
p.add_argument("--base", default=None,
               help="Branch or commit to diff against (default: HEAD~1; ignored if stdin piped)")
p.add_argument("--scope", default=None, help="One-line context for the reviewer")
p.add_argument("--paths", nargs="+", help="Files to include as full content for context")
p.add_argument("--max-tokens", type=int, default=8192,
               help="Total token budget (reasoning + output)")
p.add_argument("--model", default=os.environ.get("WORKER_MODEL", "kimi-k2.5"))
args = p.parse_args()

# Get the diff: stdin takes priority, then --base, then HEAD~1 fallback
if not sys.stdin.isatty():
    diff = sys.stdin.read()
else:
    ref = f"{args.base}..HEAD" if args.base else "HEAD~1"
    result = subprocess.run(["git", "diff", ref], capture_output=True, text=True)
    if result.returncode != 0:
        print(
            f"Error: git diff failed — are you in a git repository?\n{result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)
    diff = result.stdout
    if not diff.strip():
        print(f"Error: git diff {ref} produced no output — nothing to review.", file=sys.stderr)
        sys.exit(1)

# Build user message
focus = f"Focus: {args.scope}\n\n" if args.scope else ""
file_context = ""
if args.paths:
    blocks = []
    for path in args.paths:
        content = pathlib.Path(path).read_text(errors="replace")
        blocks.append(f"<file path='{path}'>\n{content}\n</file>")
    file_context = "\n\n" + "\n\n".join(blocks)

user_msg = f"{focus}<diff>\n{diff}\n</diff>{file_context}"

resp = client.chat.completions.create(
    model=args.model,
    messages=[
        {
            "role": "system",
            "content": (
                "You are a senior code reviewer. You will receive a git diff and optional "
                "file context. Return findings in exactly three tiers:\n\n"
                "CRITICAL — bugs, security holes, data loss risks, broken logic\n"
                "WARNING  — performance issues, bad patterns, missing error handling\n"
                "SUGGESTION — style, readability, minor improvements\n\n"
                "Format each finding as:\n"
                "[TIER] file.py:42 — short description\n"
                "  Detail: one or two sentences explaining why and what to fix.\n\n"
                "If no findings exist in a tier, omit that section entirely.\n"
                "Do not summarize the diff. Do not praise. Find problems."
            ),
        },
        {"role": "user", "content": user_msg},
    ],
    max_tokens=args.max_tokens,
)

answer = resp.choices[0].message.content
if answer:
    print(answer)
else:
    print("[ERROR: Kimi ran out of tokens. Try --max-tokens 16384]", file=sys.stderr)
    sys.exit(1)

u = resp.usage
cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
print(
    f"\n[kimi: {u.prompt_tokens} in ({cached} cached) / "
    f"{u.completion_tokens} out | finish: {resp.choices[0].finish_reason}]",
    file=sys.stderr,
)
```

- [ ] **Step 3: Make it executable**

```bash
chmod +x /Users/williamtower/.local/bin/kimi-review
```

- [ ] **Step 4: Verify it's on PATH**

```bash
which kimi-review
```

Expected: `/Users/williamtower/.local/bin/kimi-review`

- [ ] **Step 5: Smoke test — default diff**

```bash
kimi-review --scope "smoke test"
```

Expected: structured findings to stdout (CRITICAL/WARNING/SUGGESTION tiers), cost report to stderr. No Python traceback.

- [ ] **Step 6: Smoke test — explicit --base flag**

```bash
kimi-review --base HEAD~2 --scope "two commits"
```

Expected: diffs `HEAD~2..HEAD` (not empty, not `HEAD~1`). Findings to stdout.

- [ ] **Step 7: Smoke test — piped diff**

```bash
git diff HEAD~1 | kimi-review --scope "piped"
```

Expected: findings to stdout. `--base` is irrelevant (stdin wins).

- [ ] **Step 8: Error test — not in a git repo**

```bash
(cd /tmp && kimi-review --scope "no git here") 2>&1
```

Expected output to stderr contains: `Error: git diff failed — are you in a git repository?`
Expected exit code: 1

```bash
(cd /tmp && kimi-review --scope "no git here"); echo "exit: $?"
```

Expected: `exit: 1`

- [ ] **Step 9: Commit**

```bash
git add /Users/williamtower/.local/bin/kimi-review
git -C /Users/williamtower/projects/plant_id_community commit -m "feat: add kimi-review worker delegation script"
```

Note: `/Users/williamtower/.local/bin/` is outside the project repo. Commit only the plan/config changes from within the project. The script itself does not need to be committed to the project repo (it lives in the user's local bin alongside `ask-kimi`).

**Revised Step 9:**

```bash
# No project-repo commit needed for this task — script lives outside the repo.
# Confirm it's working before moving on.
which kimi-review && echo "kimi-review installed OK"
```

---

## Task 2: kimi-challenge script

**Files:**

- Create: `/Users/williamtower/.local/bin/kimi-challenge`

- [ ] **Step 1: Verify the command doesn't exist yet**

```bash
kimi-challenge --decision "test" 2>&1 || true
```

Expected: `command not found: kimi-challenge`

- [ ] **Step 2: Write the script**

Create `/Users/williamtower/.local/bin/kimi-challenge` with this exact content:

```python
#!/Users/williamtower/.local/share/claude-coworker/venv/bin/python3
"""Delegate adversarial design review to Kimi. Returns COUNTER-ARGUMENTS, ALTERNATIVES, RISKS."""
import argparse, os, sys, pathlib
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("WORKER_API_KEY", os.environ.get("MOONSHOT_API_KEY", "")),
    base_url=os.environ.get("WORKER_BASE_URL", "https://api.moonshot.ai/v1"),
)

p = argparse.ArgumentParser(description="Adversarial design review via Kimi")
p.add_argument("--decision", default=None, help="The design decision or approach to challenge")
p.add_argument("--paths", nargs="+", help="Relevant files to include as context")
p.add_argument("--max-tokens", type=int, default=8192,
               help="Total token budget (reasoning + output)")
p.add_argument("--model", default=os.environ.get("WORKER_MODEL", "kimi-k2.5"))
args = p.parse_args()

# Validate input — exactly one of stdin or --decision, not both, not neither
stdin_piped = not sys.stdin.isatty()
if stdin_piped and args.decision:
    print("Error: provide either --decision or pipe input, not both", file=sys.stderr)
    sys.exit(1)
if not stdin_piped and not args.decision:
    print("Error: provide a decision via --decision or pipe input", file=sys.stderr)
    sys.exit(1)

decision = sys.stdin.read() if stdin_piped else args.decision

# Build user message
file_context = ""
if args.paths:
    blocks = []
    for path in args.paths:
        content = pathlib.Path(path).read_text(errors="replace")
        blocks.append(f"<file path='{path}'>\n{content}\n</file>")
    file_context = "\n\n" + "\n\n".join(blocks)

user_msg = f"Decision: {decision}{file_context}"

resp = client.chat.completions.create(
    model=args.model,
    messages=[
        {
            "role": "system",
            "content": (
                "You are an adversarial design reviewer. Your job is to find weaknesses, "
                "not validate decisions. You will receive a design decision or approach.\n\n"
                "Return three sections:\n"
                "COUNTER-ARGUMENTS — specific reasons this approach is wrong or risky\n"
                "ALTERNATIVE APPROACHES — 2-3 concrete alternatives with trade-offs\n"
                "SPECIFIC RISKS — failure modes, edge cases, things that will bite later\n\n"
                "Be direct. Do not soften criticism. Do not acknowledge strengths unless "
                "they create a false sense of security. Your goal is to surface what the "
                "designer hasn't considered."
            ),
        },
        {"role": "user", "content": user_msg},
    ],
    max_tokens=args.max_tokens,
)

answer = resp.choices[0].message.content
if answer:
    print(answer)
else:
    print("[ERROR: Kimi ran out of tokens. Try --max-tokens 16384]", file=sys.stderr)
    sys.exit(1)

u = resp.usage
cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
print(
    f"\n[kimi: {u.prompt_tokens} in ({cached} cached) / "
    f"{u.completion_tokens} out | finish: {resp.choices[0].finish_reason}]",
    file=sys.stderr,
)
```

- [ ] **Step 3: Make it executable**

```bash
chmod +x /Users/williamtower/.local/bin/kimi-challenge
```

- [ ] **Step 4: Verify it's on PATH**

```bash
which kimi-challenge
```

Expected: `/Users/williamtower/.local/bin/kimi-challenge`

- [ ] **Step 5: Smoke test — --decision flag**

```bash
kimi-challenge --decision "store session tokens in localStorage"
```

Expected: three sections (COUNTER-ARGUMENTS, ALTERNATIVE APPROACHES, SPECIFIC RISKS) to stdout. Cost report to stderr.

- [ ] **Step 6: Smoke test — stdin path**

```bash
echo "Use a global singleton for DB connection pool" | kimi-challenge
```

Expected: same three-section output. No error.

- [ ] **Step 7: Error test — both stdin and --decision**

```bash
echo "piped" | kimi-challenge --decision "also a decision" 2>&1; echo "exit: $?"
```

Expected stderr: `Error: provide either --decision or pipe input, not both`
Expected exit code: `exit: 1`

- [ ] **Step 8: Error test — neither provided**

```bash
kimi-challenge 2>&1; echo "exit: $?"
```

Expected stderr: `Error: provide a decision via --decision or pipe input`
Expected exit code: `exit: 1`

- [ ] **Step 9: Confirm installation**

```bash
which kimi-review kimi-challenge && echo "both installed OK"
```

---

## Task 3: CLAUDE.md additions

**Files:**

- Modify: `/Users/williamtower/projects/plant_id_community/CLAUDE.md`

Four edits needed:

- [ ] **Step 1: Update the tool count in the section intro (line 176)**

Change:

```text
Three CLI tools delegate bulk I/O to a cheap worker model (Kimi K2.6 via OpenRouter).
```

To:

```text
Five CLI tools delegate bulk I/O to a cheap worker model (Kimi K2.6 via OpenRouter).
```

- [ ] **Step 2: Insert two new subsections after the kimi-write block (after line 200, before `### extract-chat`)**

Insert after the line `Then review the output and edit only what needs fixing.`:

````markdown

### kimi-review — pre-commit code review

Use before committing any significant implementation:

```bash
kimi-review [--base main] [--scope "feature area"] [--paths relevant_file.py]
```

Omit `--paths` for routine commits. Add `--paths` when the change touches a complex subsystem where surrounding context matters.

**If `kimi-review` returns a CRITICAL finding: stop, surface to user, do not proceed with the commit until it is resolved.** CRITICAL findings are blocking.

### kimi-challenge — adversarial design check

Use before choosing between two approaches or making an architectural decision:

```bash
kimi-challenge --decision "<the approach being considered>"
kimi-challenge --decision "…" --paths <relevant-file>
```

Include `--paths` when the decision involves an existing file or model.

````

- [ ] **Step 3: Append two new AUTO-delegate rules (after the existing bullet for "Post-session documentation updates", before `**NEVER delegate:**`)**

Change the AUTO-delegate block from:

```text
**AUTO-delegate (no prompt needed):**

- Reading 3+ files for exploration or context
- Single file >400 lines when goal is understanding (not editing)
- Boilerplate: pytest tests, DRF viewsets/serializers, Flutter widgets, Riverpod providers
- Post-session documentation updates
```

To:

```text
**AUTO-delegate (no prompt needed):**

- Reading 3+ files for exploration or context
- Single file >400 lines when goal is understanding (not editing)
- Boilerplate: pytest tests, DRF viewsets/serializers, Flutter widgets, Riverpod providers
- Post-session documentation updates
- Before committing any significant implementation: `kimi-review` (no `--paths` needed for routine commits; add `--paths` when the change touches a complex subsystem). If output contains CRITICAL, stop and surface to user before commit.
- Before choosing between two approaches or making an architectural decision: `kimi-challenge --decision "<the approach being considered>"` with `--paths <relevant-files>` when the decision involves existing code.
```

- [ ] **Step 4: Commit CLAUDE.md**

```bash
git add CLAUDE.md
git commit -m "docs: add kimi-review and kimi-challenge delegation rules to CLAUDE.md"
```

---

## Task 4: settings.json permissions

**Files:**

- Modify: `~/.claude/settings.json`

- [ ] **Step 1: Add the two new allow entries**

In `~/.claude/settings.json`, add to the `permissions.allow` array (after `"Bash(kimi-write:*)"` for readability):

```json
"Bash(kimi-review:*)",
"Bash(kimi-challenge:*)",
```

The allow array should now include (among others):

```json
"Bash(ask-kimi:*)",
"Bash(kimi-write:*)",
"Bash(kimi-review:*)",
"Bash(kimi-challenge:*)",
"Bash(extract-chat:*)"
```

- [ ] **Step 2: Verify the JSON is valid**

```bash
python3 -m json.tool ~/.claude/settings.json > /dev/null && echo "JSON valid"
```

Expected: `JSON valid`

- [ ] **Step 3: Verify the entries are present**

```bash
grep "kimi-review\|kimi-challenge" ~/.claude/settings.json
```

Expected:

```text
"Bash(kimi-review:*)",
"Bash(kimi-challenge:*)",
```

Note: `settings.json` lives outside the project repo — no git commit needed for this step.

---

## Task 5: Integration tests

These are the real-diff tests from the spec's test plan, run in order.

- [ ] **Step 1: Real diff test — kimi-review with file context**

```bash
cd /Users/williamtower/projects/plant_id_community
git diff HEAD~2 HEAD | kimi-review \
  --scope "recent work" \
  --paths backend/apps/forum/serializers.py
```

Expected: meaningful CRITICAL/WARNING/SUGGESTION output (not all tiers empty). Cost report to stderr. No Python traceback.

- [ ] **Step 2: Real challenge test — cached rich_content decision**

```bash
cd /Users/williamtower/projects/plant_id_community
kimi-challenge \
  --decision "cache forum post rich_content in PostSerializer" \
  --paths backend/apps/forum/serializers.py
```

Expected: COUNTER-ARGUMENTS section mentions cache invalidation or stale content risks. Three sections present. Cost report to stderr.

- [ ] **Step 3: kimi-review with --base flag against main**

```bash
cd /Users/williamtower/projects/plant_id_community
kimi-review --base main --scope "branch review"
```

Expected: diffs current branch against main (non-empty if branch has commits). Findings to stdout.

- [ ] **Step 4: Confirm both scripts are findable and exit cleanly on --help**

```bash
kimi-review --help && kimi-challenge --help
```

Expected: argparse help text for both, exit 0.

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task covering it |
|-----------------|-----------------|
| kimi-review: --base flag | Task 1 Step 2 (implementation), Step 6 (test) |
| kimi-review: --scope flag | Task 1 Step 2 (implementation), Step 5 (test) |
| kimi-review: --paths flag | Task 1 Step 2 (implementation), Task 5 Step 1 (real diff test) |
| kimi-review: stdin fallback to git diff HEAD~1 | Task 1 Step 2 (implementation), Step 5 |
| kimi-review: --base without stdin diffs base..HEAD | Task 1 Step 2 (implementation), Step 6 |
| kimi-review: clean error if not in git repo | Task 1 Step 8 |
| kimi-review: CRITICAL/WARNING/SUGGESTION output format | Task 1 Step 2 (system prompt) |
| kimi-review: max 8192 tokens | Task 1 Step 2 (default arg) |
| kimi-challenge: --decision flag | Task 2 Step 2 (implementation), Step 5 |
| kimi-challenge: stdin input | Task 2 Step 2 (implementation), Step 6 |
| kimi-challenge: mutual exclusivity with explicit error | Task 2 Step 2 (implementation), Steps 7–8 |
| kimi-challenge: --paths flag | Task 2 Step 2 (implementation), Task 5 Step 2 |
| kimi-challenge: adversarial system prompt | Task 2 Step 2 |
| kimi-challenge: max 8192 tokens | Task 2 Step 2 (default arg) |
| Both scripts: same PATH as ask-kimi | Task 1 Step 4, Task 2 Step 4 |
| Both scripts: chmod +x | Task 1 Step 3, Task 2 Step 3 |
| CLAUDE.md: new subsections | Task 3 Steps 1–2 |
| CLAUDE.md: AUTO-delegate rules | Task 3 Step 3 |
| CLAUDE.md: CRITICAL findings are blocking | Task 3 Step 3 (in the AUTO-delegate bullet) |
| settings.json: allowlist entries | Task 4 |
| Test with real diff | Task 5 |

All requirements covered. No gaps.
