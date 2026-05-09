# kimi-review and kimi-challenge — Design

**Date:** 2026-05-08
**Status:** Approved, pending implementation

## Goal

Add two new worker delegation scripts to the existing claude-coworker-model setup:

- `kimi-review` — structured code review from a git diff (CRITICAL / WARNING / SUGGESTION tiers)
- `kimi-challenge` — adversarial design review that argues against a decision or approach

Both follow the exact pattern of `ask-kimi` and `kimi-write`: independent Python scripts, same venv shebang, same `WORKER_*` env vars, same stderr cost report.

## Architecture

### Approach

Approach A: independent Python scripts, no shared module. Each file is self-contained and readable in isolation — the same precedent set by `ask-kimi` and `kimi-write`.

### Installation

- Scripts written to `/Users/williamtower/.local/bin/kimi-review` and `/Users/williamtower/.local/bin/kimi-challenge`
- Shebang: `#!/Users/williamtower/.local/share/claude-coworker/venv/bin/python3`
- `chmod +x` both scripts
- No new dependencies — `openai>=1.0` is already installed in the venv

## kimi-review

### CLI

```bash
kimi-review [--base <branch-or-commit>] [--scope "<context>"] [--paths file1 file2 ...]
git diff HEAD~3 | kimi-review [--scope "<context>"] [--paths file1 file2 ...]
```

### Diff resolution (in priority order)

1. **Stdin piped:** use stdin content as the diff. `--base` is ignored when stdin is provided.
2. **`--base` provided, no stdin:** run `git diff <base>..HEAD` via subprocess.
3. **Neither:** fall back to `git diff HEAD~1` via subprocess.

### Git subprocess error handling

If the `git diff` subprocess fails (not in a git repo, invalid ref, etc.), print a clean error to stderr and exit 1:

```text
Error: git diff failed — are you in a git repository?
<stderr from git>
```

Never pass an empty or error string to the model.

### Arguments

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--base` | no | `HEAD~1` | Branch or commit to diff against (ignored if stdin piped) |
| `--scope` | no | — | One-line context string added to system prompt |
| `--paths` | no | — | Files to include as full content for additional context |
| `--max-tokens` | no | `8192` | Total token budget (reasoning + output) |
| `--model` | no | `$WORKER_MODEL` | Model override |

### System prompt

```text
You are a senior code reviewer. You will receive a git diff and optional
file context. Return findings in exactly three tiers:

CRITICAL — bugs, security holes, data loss risks, broken logic
WARNING  — performance issues, bad patterns, missing error handling
SUGGESTION — style, readability, minor improvements

Format each finding as:
[TIER] file.py:42 — short description
  Detail: one or two sentences explaining why and what to fix.

If no findings exist in a tier, omit that section entirely.
Do not summarize the diff. Do not praise. Find problems.
```

If `--scope` is provided, prepend to the user message: `"Focus: <scope>\n\n"`.

### User message structure

```text
[Focus: <scope>]          ← only if --scope provided

<diff>
<git diff content>
</diff>

[<file path='...'>        ← only if --paths provided
...file content...
</file>]
```

### Output

- Findings to stdout
- Cost report to stderr (same format as existing tools)
- Exit 0 on success, exit 1 on any error

### Future extension

`--json` flag (not in scope now) — returns machine-readable findings for Stop hook integration. Noted here so the prompt structure anticipates it: keep finding format parseable.

## kimi-challenge

### Usage

```bash
kimi-challenge --decision "<approach>" [--paths file1 file2 ...]
echo "<design notes>" | kimi-challenge [--paths file1 file2 ...]
```

### Input handling

`--decision` and stdin are mutually exclusive. If both are provided, exit 1 with:

```text
Error: provide either --decision or pipe input, not both
```

If neither is provided, exit 1 with:

```text
Error: provide a decision via --decision or pipe input
```

### Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--decision` | no* | — | The design decision or approach to challenge |
| `--paths` | no | — | Relevant files to include as context (use when decision touches existing code) |
| `--max-tokens` | no | `8192` | Total token budget |
| `--model` | no | `$WORKER_MODEL` | Model override |

*One of `--decision` or stdin is required.

### Prompt

```text
You are an adversarial design reviewer. Your job is to find weaknesses,
not validate decisions. You will receive a design decision or approach.

Return three sections:
COUNTER-ARGUMENTS — specific reasons this approach is wrong or risky
ALTERNATIVE APPROACHES — 2-3 concrete alternatives with trade-offs
SPECIFIC RISKS — failure modes, edge cases, things that will bite later

Be direct. Do not soften criticism. Do not acknowledge strengths unless
they create a false sense of security. Your goal is to surface what the
designer hasn't considered.
```

### Message format

```text
Decision: <decision text or piped input>

[<file path='...'>        ← only if --paths provided
...file content...
</file>]
```

### Returns

- Findings to stdout
- Cost report to stderr
- Exit 0 on success, exit 1 on any error

## CLAUDE.md additions

Two additions to the existing `## Cheap-Worker Delegation (Kimi K2.6)` section in the root `CLAUDE.md`.

### New subsections (after kimi-write, before extract-chat)

```markdown
### kimi-review — pre-commit code review

Use before committing any significant implementation:

    kimi-review [--base main] [--scope "feature area"] [--paths relevant_file.py]

Omit --paths for routine commits. Add --paths when the change touches a
complex subsystem where surrounding context matters.

**If kimi-review returns a CRITICAL finding: stop, surface to user, do not
proceed with the commit until it is resolved.** CRITICAL findings are blocking.

### kimi-challenge — adversarial design check

Use before choosing between two approaches or making an architectural decision:

    kimi-challenge --decision "<the approach being considered>"
    kimi-challenge --decision "…" --paths <relevant-file>

Include --paths when the decision involves an existing file or model.
```

### AUTO-delegate block additions

Append to the existing `**AUTO-delegate (no prompt needed):**` list:

```text
- Before committing any significant implementation: `kimi-review` (no --paths
  needed for routine commits; add --paths when the change touches a complex
  subsystem). If output contains CRITICAL, stop and surface to user before commit.
- Before choosing between two approaches or making an architectural decision:
  `kimi-challenge --decision "<the approach being considered>"` with
  `--paths <relevant-files>` when the decision involves existing code.
```

## Test Plan

### 1. Verify installation

```bash
which kimi-review kimi-challenge
```

### 2. kimi-review smoke tests

```bash
# Default fallback: git diff HEAD~1
kimi-review --scope "smoke test"

# Explicit base: diffs <base>..HEAD (not empty)
kimi-review --base HEAD~2 --scope "two commits"

# Piped diff
git diff HEAD~1 | kimi-review --scope "piped"

# With file context
kimi-review --scope "forum serializer" \
  --paths backend/apps/forum/serializers.py
```

### 3. kimi-challenge smoke tests

```bash
# --decision flag
kimi-challenge --decision "store session tokens in localStorage"

# stdin path
echo "Use a global singleton for DB connection" | kimi-challenge

# With file context
kimi-challenge \
  --decision "cache forum post rich_content in PostSerializer" \
  --paths backend/apps/forum/serializers.py
```

### 4. Error handling

```bash
# Both stdin and --decision: explicit error, exit 1
echo "piped" | kimi-challenge --decision "also a decision"

# Not in a git repo: clean error, exit 1
cd /tmp && kimi-review --scope "no git here"
```

### 5. Real diff test

```bash
git diff HEAD~2 HEAD | kimi-review \
  --scope "recent work" \
  --paths backend/apps/forum/serializers.py
```

### Future test (out of scope now)

```bash
# --json flag for Stop hook integration
kimi-review --json --scope "structured output"
```

## Out of Scope

- `--json` flag on kimi-review (future: Stop hook integration for automated quality gates)
- Piped diff + `--base` combination (stdin takes priority; `--base` is silently ignored)
- Additional worker providers — change env vars to switch
