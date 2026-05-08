# Kimi K2.5 Bulk I/O Delegation — Design

**Date:** 2026-05-08
**Status:** Approved, pending implementation

## Goal

Reduce Claude Code token consumption by delegating bulk file reading and boilerplate generation to a cheap worker model (Kimi K2.5 via Moonshot AI). Claude handles architecture and reasoning; the worker handles token-heavy I/O.

## Source Repo

`https://github.com/imkunal007219/claude-coworker-model`
MIT license. Python, uses `openai>=1.0` against any OpenAI-compatible provider.

## Architecture

### Installation

- Clone repo to `~/.local/share/claude-coworker/`
- Run `setup.sh` — creates a Python venv, installs `openai` package, copies/symlinks three tools to `~/.local/bin/` (already on PATH)

### Tools

| Tool | Purpose |
|------|---------|
| `ask-kimi` | Reads N files, returns structured bullet summary |
| `kimi-write` | Generates boilerplate to a target file using an existing file as style reference |
| `extract-chat` | Converts `.jsonl` session logs to readable text (stdlib only, no API call) |

### Environment Variables

Set in two places:

**`~/.claude/settings.json` `env` block** — injected into every Claude Code session automatically:

```json
"WORKER_API_KEY": "<moonshot key>",
"WORKER_BASE_URL": "https://api.moonshot.ai/v1",
"WORKER_MODEL": "kimi-k2.5"
```

**`~/.zshrc`** — same three exports for manual terminal use.

### Permissions

Add to `~/.claude/settings.json` allow list so Claude never prompts:

```text
Bash(ask-kimi:*)
Bash(kimi-write:*)
Bash(extract-chat:*)
```

## Delegation Rules (CLAUDE.md)

A new section `## Cheap-Worker Delegation (Kimi K2.5)` is appended to the project `CLAUDE.md`. Nothing existing is removed.

### AUTO-delegate (no prompt)

- Reading 3+ files for exploration/context → `ask-kimi --paths <files> --question "<question>"`
- Single file over ~400 lines when the goal is understanding (not editing) — e.g. `backend/apps/*/models.py`, serializers, large Flutter screens
- Generating boilerplate that follows an existing pattern: pytest tests, DRF viewsets/serializers, Flutter widgets, Riverpod providers → `kimi-write --spec "<what>" --context <existing-similar-file> --target <output>`
- Post-session documentation updates → `extract-chat <session.jsonl>` then `ask-kimi` to suggest doc changes

### NEVER delegate

- Architecture decisions, refactoring plans, feature design
- Debugging (requires reasoning about error state)
- Security-sensitive code: auth, permissions, input validation, migrations
- Any task requiring exact line numbers for editing — read the file directly
- Tasks under ~2000 tokens (delegation overhead not worth it)

### AMBIGUOUS — ask first

- "Summarize what changed in this PR" (may need reasoning)
- Anything touching auth or permissions even if mechanical

## Data Flow

```text
Claude encounters bulk work
  → checks CLAUDE.md rules
  → Bash: ask-kimi --paths <files> --question "<specific question>"
  → worker calls Moonshot API, returns structured bullets
  → Claude reads ~200-token summary instead of ~4000+ token raw files
  → Claude reasons/edits using the summary

Claude identifies boilerplate task
  → Bash: kimi-write --spec "<what>" --context <existing-file> --target <output>
  → worker writes the file
  → Claude reviews and edits only what needs fixing
```

## Test Plan

All four steps runnable via Bash in a Claude Code session:

1. **Tool smoke test**

   ```bash
   ask-kimi --paths backend/apps/plant_identification/models.py \
     --question "list the models and their key fields"
   ```

   Expected: structured bullet list, no errors.

2. **Write smoke test**

   ```bash
   kimi-write \
     --spec "stub pytest test class for PlantIdentificationViewSet" \
     --context backend/apps/plant_identification/tests.py \
     --target /tmp/test_stub.py
   ```

   Expected: `/tmp/test_stub.py` created with valid Python.

3. **Extract smoke test**

   ```bash
   extract-chat $(ls -t ~/.claude/projects/*/sessions/*.jsonl 2>/dev/null | head -1) \
     -o /tmp/chat.txt
   ```

   Expected: `/tmp/chat.txt` contains human-readable conversation text.

4. **Delegation in-session**
   Ask Claude a question about a 500+ line file. Confirm it calls `ask-kimi` rather than using the Read tool.

## Out of Scope

- mcp-memory-service (existing file-based memory at `~/.claude/projects/.../memory/` is sufficient and already loading)
- SessionEnd auto-harvest hooks (not needed; memory is curated manually)
- Additional worker providers (DeepSeek, Ollama) — can be added later by changing env vars
