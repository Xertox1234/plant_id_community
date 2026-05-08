# Kimi K2.6 Bulk I/O Delegation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install and configure three CLI tools that delegate bulk file reading and boilerplate generation to Kimi K2.6, reducing Claude token consumption by 60-70% on I/O-heavy tasks.

**Architecture:** Clone `claude-coworker-model` to `~/.local/share/claude-coworker/`, run its `setup.sh` to install tools to `~/.local/bin/`, then wire env vars into `~/.claude/settings.json` (for Claude sessions) and `~/.zshrc` (for direct terminal use). Add delegation rules to the project `CLAUDE.md` so Claude auto-delegates without being prompted.

**Tech Stack:** Python 3, `openai>=1.0` (OpenAI-compatible client), OpenRouter API (`https://openrouter.ai/api/v1`), zsh, Claude Code settings.json

---

## File Map

| File | Action | Notes |
| ---- | ------ | ----- |
| `~/.local/share/claude-coworker/` | Create (git clone) | Repo root + venv live here |
| `~/.local/bin/ask-kimi` | Create (by setup.sh) | Already on PATH |
| `~/.local/bin/kimi-write` | Create (by setup.sh) | Already on PATH |
| `~/.local/bin/extract-chat` | Create (by setup.sh) | Symlink, stdlib only |
| `~/.claude/settings.json` | Modify | Add `env` keys + 3 allow-list entries |
| `~/.zshrc` | Modify | Append 3 `export` lines |
| `CLAUDE.md` | Modify | Append delegation rules section |

---

## Task 1: Clone repo and install coworker tools

**Files:**

- Create: `~/.local/share/claude-coworker/` (repo + venv)
- Create: `~/.local/bin/ask-kimi`, `~/.local/bin/kimi-write`, `~/.local/bin/extract-chat`

- [ ] **Step 1: Confirm tools are not yet installed**

  ```bash
  which ask-kimi 2>/dev/null || echo "NOT FOUND"
  which kimi-write 2>/dev/null || echo "NOT FOUND"
  which extract-chat 2>/dev/null || echo "NOT FOUND"
  ```

  Expected: all three print `NOT FOUND`. If any tool already exists, skip to Task 2.

- [ ] **Step 2: Clone the repo**

  ```bash
  git clone https://github.com/imkunal007219/claude-coworker-model.git \
    ~/.local/share/claude-coworker
  ```

  Expected: directory `~/.local/share/claude-coworker` exists with `setup.sh`, `tools/`, `requirements.txt`.

  Verify:

  ```bash
  ls ~/.local/share/claude-coworker/
  ```

  Expected output contains: `setup.sh  tools  requirements.txt  CLAUDE.md.template  README.md`

- [ ] **Step 3: Run setup.sh**

  ```bash
  cd ~/.local/share/claude-coworker && ./setup.sh
  ```

  Expected: prints `=== Done! ===` with no errors. A Python venv is created at `~/.local/share/claude-coworker/venv/`. Tools are written to `~/.local/bin/`.

  If setup.sh prints `⚠  No API key found` — that is expected at this stage (key gets added in Task 2). Continue.

- [ ] **Step 4: Verify tools are on PATH and executable**

  ```bash
  which ask-kimi && ask-kimi --help 2>&1 | head -5
  which kimi-write && kimi-write --help 2>&1 | head -5
  which extract-chat && extract-chat --help 2>&1 | head -5
  ```

  Expected: each `which` prints a path under `~/.local/bin/`. The `--help` output shows usage instructions without a Python traceback.

---

## Task 2: Configure env vars and permissions in `~/.claude/settings.json`

**Files:**

- Modify: `~/.claude/settings.json`

> **Before running Step 1:** You need your OpenRouter API key. If you don't have it set as `$WORKER_API_KEY` in your current shell, ask the user: "What is your OpenRouter API key?" and substitute it for `<YOUR_OPENROUTER_API_KEY>` in the script below.

- [ ] **Step 1: Confirm env vars are not yet set in Claude sessions**

  ```bash
  python3 -c "
  import json
  with open('/Users/williamtower/.claude/settings.json') as f:
      s = json.load(f)
  print('WORKER_API_KEY' in s.get('env', {}))
  "
  ```

  Expected: `False`. If `True`, skip to Task 3.

- [ ] **Step 2: Add env vars and permissions to `~/.claude/settings.json`**

  Replace `<YOUR_OPENROUTER_API_KEY>` with the actual key before running:

  ```bash
  python3 - <<'PYEOF'
  import json

  path = '/Users/williamtower/.claude/settings.json'
  with open(path) as f:
      s = json.load(f)

  # Add worker env vars
  s.setdefault('env', {})
  s['env']['WORKER_API_KEY'] = '<YOUR_OPENROUTER_API_KEY>'
  s['env']['WORKER_BASE_URL'] = 'https://openrouter.ai/api/v1'
  s['env']['WORKER_MODEL'] = 'moonshotai/kimi-k2.6'

  # Add bash permissions
  new_perms = ['Bash(ask-kimi:*)', 'Bash(kimi-write:*)', 'Bash(extract-chat:*)']
  allow = s.setdefault('permissions', {}).setdefault('allow', [])
  for p in new_perms:
      if p not in allow:
          allow.append(p)

  with open(path, 'w') as f:
      json.dump(s, f, indent=2)
  print('Done')
  PYEOF
  ```

  Expected: prints `Done` with no errors.

- [ ] **Step 3: Verify the changes are present**

  ```bash
  python3 -c "
  import json
  with open('/Users/williamtower/.claude/settings.json') as f:
      s = json.load(f)
  env = s.get('env', {})
  allow = s.get('permissions', {}).get('allow', [])
  print('WORKER_API_KEY present:', 'WORKER_API_KEY' in env)
  print('WORKER_BASE_URL:', env.get('WORKER_BASE_URL'))
  print('WORKER_MODEL:', env.get('WORKER_MODEL'))
  print('ask-kimi permitted:', 'Bash(ask-kimi:*)' in allow)
  print('kimi-write permitted:', 'Bash(kimi-write:*)' in allow)
  print('extract-chat permitted:', 'Bash(extract-chat:*)' in allow)
  "
  ```

  Expected output:

  ```text
  WORKER_API_KEY present: True
  WORKER_BASE_URL: https://openrouter.ai/api/v1
  WORKER_MODEL: moonshotai/kimi-k2.6
  ask-kimi permitted: True
  kimi-write permitted: True
  extract-chat permitted: True
  ```

---

## Task 3: Add WORKER_* exports to `~/.zshrc`

**Files:**

- Modify: `~/.zshrc`

- [ ] **Step 1: Check that exports are not already present**

  ```bash
  grep -c 'WORKER_API_KEY' ~/.zshrc 2>/dev/null || echo "0"
  ```

  Expected: `0`. If non-zero, skip this task.

- [ ] **Step 2: Append exports to `~/.zshrc`**

  Replace `<YOUR_OPENROUTER_API_KEY>` with the actual key (same value used in Task 2):

  ```bash
  cat >> ~/.zshrc << 'EOF'

  # Kimi K2.6 worker delegation (claude-coworker-model)
  export WORKER_API_KEY="<YOUR_OPENROUTER_API_KEY>"
  export WORKER_BASE_URL="https://openrouter.ai/api/v1"
  export WORKER_MODEL="moonshotai/kimi-k2.6"
  EOF
  ```

- [ ] **Step 3: Verify exports load in a new shell**

  ```bash
  zsh -c 'source ~/.zshrc && echo "KEY=${WORKER_API_KEY:0:8}... URL=$WORKER_BASE_URL MODEL=$WORKER_MODEL"'
  ```

  Expected: prints the first 8 chars of the key (confirming it loaded), the URL, and `moonshotai/kimi-k2.6`. If `KEY=...` shows blank, the export line was not appended correctly — re-check Step 2.

---

## Task 4: Append delegation rules to `CLAUDE.md`

**Files:**

- Modify: `CLAUDE.md` (project root, line 138 is current end)

- [ ] **Step 1: Confirm the section does not already exist**

  ```bash
  grep -c 'Cheap-Worker Delegation' CLAUDE.md
  ```

  Expected: `0`. If non-zero, skip this task.

- [ ] **Step 2: Append the delegation rules section**

  Run from the project root (`/Users/williamtower/projects/plant_id_community`).
  This uses Python to write the content so that inner code-fence markers are preserved correctly:

  ````bash
  python3 - << 'PYEOF'
  section = """
  ## Cheap-Worker Delegation (Kimi K2.6)

  Three CLI tools delegate bulk I/O to a cheap worker model (Kimi K2.6 via OpenRouter).
  Claude handles reasoning and architecture; the worker handles token-heavy reading/writing.

  ### ask-kimi — bulk file reading

  Use when reading 3+ files for context, or any single file >400 lines when the goal is
  understanding (not editing):

  ```bash
  ask-kimi --paths <file1> <file2>... --question "<specific question>"
  ```

  Returns structured bullets. Read the summary instead of the raw files.
  Only use Read directly when you need exact line numbers for editing.

  ### kimi-write — boilerplate generation

  Use for pytest tests, DRF viewsets/serializers, Flutter widgets, Riverpod providers —
  anything that follows an existing pattern:

  ```bash
  kimi-write --spec "<what to write>" --context <existing-similar-file> --target <output-path>
  ```

  Then review the output and edit only what needs fixing.

  ### extract-chat — session transcript extraction

  Converts Claude Code JSONL session logs to readable text (no API call, stdlib only):

  ```bash
  extract-chat <session.jsonl> -o /tmp/chat.txt
  ```

  Use before post-session doc updates: extract → ask-kimi to suggest changes → apply with Edit.

  ### Delegation rules

  **AUTO-delegate (no prompt needed):**

  - Reading 3+ files for exploration or context
  - Single file >400 lines when goal is understanding (not editing)
  - Boilerplate: pytest tests, DRF viewsets/serializers, Flutter widgets, Riverpod providers
  - Post-session documentation updates

  **NEVER delegate:**

  - Architecture decisions, refactoring plans, feature design
  - Debugging (requires reasoning about error state)
  - Security-sensitive code: auth, permissions, input validation, migrations
  - Tasks requiring exact line numbers for editing — use Read directly
  - Tasks under ~2000 tokens (overhead not worth it)

  **Ask first (ambiguous):**

  - "Summarize what changed in this PR"
  - Anything touching auth or permissions even if it seems mechanical
  """
  with open("CLAUDE.md", "a") as f:
      f.write(section)
  print("Done")
  PYEOF
  ````

  Expected: prints `Done` with no errors.

- [ ] **Step 3: Verify section was appended**

  ```bash
  grep -n 'Cheap-Worker Delegation' CLAUDE.md
  ```

  Expected: prints a line number followed by `## Cheap-Worker Delegation (Kimi K2.6)`.

- [ ] **Step 4: Lint the markdown**

  ```bash
  npx markdownlint CLAUDE.md
  ```

  Expected: no output (clean). If errors appear, fix them using the Edit tool before committing.

- [ ] **Step 5: Commit**

  ```bash
  git add CLAUDE.md
  git commit -m "feat(claude): add Kimi K2.6 bulk I/O delegation rules"
  ```

  Expected: commit succeeds (pre-commit hooks pass).

---

## Task 5: Run smoke tests

All tests run from the project root. Tasks 1–4 must be complete and a **new Claude Code session must be started** (so the `settings.json` env vars are injected).

- [ ] **Step 1: Confirm env vars are visible inside the Claude session**

  ```bash
  echo "KEY=${WORKER_API_KEY:0:8}... MODEL=$WORKER_MODEL"
  ```

  Expected: prints the first 8 chars of your key and `moonshotai/kimi-k2.6`. If blank, the session was not restarted after Task 2 — restart and retry.

- [ ] **Step 2: ask-kimi smoke test**

  ```bash
  ask-kimi \
    --paths backend/apps/plant_identification/models.py \
    --question "list the models defined in this file and their primary fields"
  ```

  Expected: structured bullet output naming models (e.g. `PlantIdentification`, `Diagnosis`) with field names. No Python traceback. No `AuthenticationError` (would indicate bad API key).

  If you see `AuthenticationError` or `401`: the API key in `~/.claude/settings.json` is incorrect. Re-run Task 2 Step 2 with the correct key.

- [ ] **Step 3: kimi-write smoke test**

  ```bash
  kimi-write \
    --spec "write a stub pytest test class for PlantIdentificationViewSet with one placeholder test" \
    --context backend/apps/plant_identification/tests.py \
    --target /tmp/test_stub.py
  ```

  Then verify:

  ```bash
  python3 -c "
  import ast, sys
  try:
      ast.parse(open('/tmp/test_stub.py').read())
      print('PASS: valid Python')
  except SyntaxError as e:
      print('FAIL:', e)
      sys.exit(1)
  "
  ```

  Expected: `PASS: valid Python`

- [ ] **Step 4: extract-chat smoke test**

  ```bash
  LATEST=$(ls -t ~/.claude/projects/*/sessions/*.jsonl 2>/dev/null | head -1)
  if [ -z "$LATEST" ]; then
    echo "No session JSONL found — skip this step"
  else
    extract-chat "$LATEST" -o /tmp/chat.txt
    wc -l /tmp/chat.txt
    head -3 /tmp/chat.txt
  fi
  ```

  Expected: prints a line count and the first 3 lines of human-readable conversation text. If no JSONL files exist, the step is skipped (that's fine — `extract-chat` is used for post-session doc updates once more sessions accumulate).

- [ ] **Step 5: Delegation behavior verification**

  Ask Claude (in the same session) to explain a large file without using the Read tool:

  > "What models are defined in `backend/apps/plant_identification/models.py` and what are their key fields?"

  Expected: Claude issues a Bash call to `ask-kimi --paths backend/apps/plant_identification/models.py --question "..."` rather than calling the Read tool. If Claude uses Read instead, check that the CLAUDE.md section was appended correctly in Task 4 and that the session was started after that commit.

- [ ] **Step 6: Clean up temp files**

  ```bash
  rm -f /tmp/test_stub.py /tmp/chat.txt
  ```
