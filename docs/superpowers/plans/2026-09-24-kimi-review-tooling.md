# Kimi Review Tooling — Implementation Plan

**Date:** 2026-09-24
**Status:** In progress — Phases 0–3 done; Phases 4–11 not started
**Canonical code:** `~/.local/share/claude-coworker/` (shared by Plant ID Community and OCRecipes)
**Vendored consumer:** `plant_id_community/scripts/kimi-review` (drift-checked)

## Goal

Make `kimi-review` able to review large change-sets thoroughly:

1. **Split** a review into logical groups, each with its own model call and output budget.
2. **Give Kimi local, read-only tools**: repository reads, language-server queries, and
   library documentation.
3. **Write findings to a Markdown report as it goes**, so the calling coding agent reads the
   file instead of blocking on one long reply.
4. **Stay multi-project.** `generic`, `plant_id` and `ocrecipes` profiles all keep working,
   and project-specific behavior lives in profiles, not in tool code.

## Verified starting point

- The canonical engine is `tools/kimi-review` in the coworker checkout. It is a single Python
  file with a one-shot draft call, deterministic verification (Tier A), and a small agentic
  verification loop (Tier B) with `read_file` and `grep` tools.
- The initial draft call has **no tools**. Kimi sees only the diff plus any injected
  rules and files. Tools exist only to verify CRITICAL findings that are already drafted.
- `--max-tokens` defaults to 131072 per call. A `finish_reason == "length"` response is
  rejected outright (exit 1), so a truncated review yields **no findings at all**.
- Profiles are loaded from `kimi-profiles.json` next to the engine. The canonical file holds
  `generic`, `ocrecipes`, `plant_id`; Plant ID's vendored copy holds only `generic` and
  `plant_id` and is intentionally not overwritten by `scripts/sync-kimi-engine.sh`.
- `~/.local/bin/kimi-review` is now a symlink to the canonical engine (installed
  2026-09-24), so both automatic Plant ID gates run it.
- The coworker checkout has **uncommitted changes** (`ask-kimi`, `kimi-write`,
  `extract-chat`, `.gitignore`) and **untracked** `kimi-review`, `kimi-profiles.json`,
  `test-kimi-review.py`. Its `setup.sh` does not install `kimi-review`.
- OCRecipes **deliberately removed** kimi-review on 2026-06-09 (commits `6d1e43f8`,
  `dd4ccfd4`, `e6ad5a79`, `fe83d1f7`) and replaced it with its `code-reviewer` subagent.
  It keeps `ask-kimi`, `kimi-write`, `kimi-challenge`, `extract-chat`. Its hard exclusion:
  never point kimi tools at JWT auth, IAP receipt validation, or user health data.
- Local toolchain: `typescript-language-server` and `node` are installed; `pyright` is not.

## Decisions already made

| Topic | Decision |
|-------|----------|
| Where shared code lives | Canonical coworker repo; projects vendor or call it |
| Docs backend | Pluggable provider interface, Context7 adapter first, local cache fallback |
| Python LSP | `basedpyright` installed into the coworker venv via pip |
| MCP | Not required. Tools are plain local Python, executed by the engine |
| OCRecipes | Plan to re-enable, but see the OCRecipes phase: advisory and on-demand only |

## Architecture

```text
calling agent ──start──▶ kimi-review-batch (detached)
      │                      │
      │                      ├─ profile resolver ──▶ kimi-profiles.json (v2)
      │                      ├─ egress guard (profile excluded_paths + secret defaults)
      │                      ├─ partitioner ──▶ group 1..N
      │                      │
      │                      └─ per group: review loop
      │                           ├─ Kimi (remote) ◀──▶ tool registry (local, read-only)
      │                           │                     ├─ repo: read_file, search, git_show
      │                           │                     ├─ lsp: symbols, definition, refs, hover, diagnostics
      │                           │                     └─ docs: query_library_docs
      │                           ├─ final strict-JSON findings call
      │                           ├─ verification (deterministic | agentic)
      │                           └─ append group section ──▶ report.md + status.json
      │
      └──polls status.json / reads report.md (never blocks on stdout)
```

Kimi never gets a shell or direct filesystem access. It requests a named tool; the local
engine validates the arguments, applies the egress guard, runs the tool with a timeout and a
size cap, and returns the result.

### Proposed coworker layout

```text
~/.local/share/claude-coworker/
  tools/
    kimi-review              # CLI entry, same flags and exit codes as today
    kimi-review-batch        # new orchestrator CLI
    kimi-profiles.json       # v2 schema, legacy string values still accepted
    kimi_runtime/            # new package, stdlib + openai only
      profiles.py            # load, validate, resolve, detect
      egress.py              # path exclusion for diffs and every tool
      tools/registry.py      # tool schemas, dispatch, bounds, call log
      tools/repo.py
      tools/lsp.py           # minimal stdio JSON-RPC client + server lifecycle
      tools/docs.py          # provider interface, context7 + cache adapters
      review_loop.py         # tool-assisted draft, then final findings call
      partition.py
      report.py              # atomic Markdown + status.json writer
      usage.py               # append to usage.jsonl like the other tools
    tests/                   # hermetic: fake model, fake LSP, fake docs
  setup.sh                   # installs all CLIs + basedpyright
```

The single-file engine becomes a CLI plus a package. That changes vendoring (see Phase 9).

## Agent-facing contract (report file, not reply)

This is the contract the calling coding agent relies on.

**Start** returns immediately:

```bash
kimi-review-batch start --base origin/main --profile auto
# stdout, one JSON line:
# {"run_id":"20260924-1412-a1b2","report":"…/report.md","status":"…/status.json"}
```

The review keeps running detached (`nohup` / `start_new_session`), so it survives the agent's
tool timeout and the shell exiting.

**`status.json`** is rewritten atomically (temp file + `os.replace`) after every change:

```json
{
  "run_id": "20260924-1412-a1b2",
  "profile": "plant_id",
  "state": "running",
  "groups_total": 5,
  "groups_done": 2,
  "current_group": "3: forum API serializers",
  "critical": 0,
  "warning": 3,
  "errors": [],
  "report": ".../report.md",
  "updated_at": "2026-09-24T14:15:03Z"
}
```

`state` is one of `running`, `complete`, `partial` (some groups errored), `failed`.

**`report.md`** is append-only. Each group section is appended whole when that group
finishes, so a reader never sees half a section. The file ends with a final summary and a
fixed marker line `<!-- kimi-review: complete -->` once `state` is terminal.

**Agent commands:**

```bash
kimi-review-batch status <run_id>              # prints status.json
kimi-review-batch wait <run_id> --timeout 60   # returns when terminal or on timeout
kimi-review-batch list                          # recent runs for this project
```

**Agent instructions** (added to each project's docs and to the batch `--help`):

1. Start the run and record the report path.
2. Continue other work. Check `status.json` between tasks, or call `wait` with a short
   timeout. Never run the review in the foreground and wait for stdout.
3. Read new sections of `report.md` as `groups_done` rises and act on findings per group.
4. Treat the run as finished only when `state` is terminal **and** the marker line exists.

**Where runs are written:** default `~/.local/share/claude-coworker/runs/<profile>/<run_id>/`,
outside every repository, so a report is never staged or reviewed by the next commit.
`--out-dir` overrides it (OCRecipes' worktree rule can point it into a worktree's
ignored scratch path).

**Commit gates stay synchronous.** A pre-commit gate has to block, so it cannot be async.
Plant ID's existing hook keeps running the one-shot `kimi-review`. The batch reviewer is for
branch-level and on-demand reviews.

## Profiles v2

A profile value may stay a plain string (legacy guidance), or become an object:

```json
{
  "plant_id": {
    "guidance": "Project profile: Plant ID Community ...",
    "detect": {"root_names": ["plant_id_community"], "claude_md_markers": ["Plant ID Community"]},
    "languages": ["python", "typescript", "dart"],
    "lsp": {"python": "basedpyright", "typescript": "typescript-language-server"},
    "docs_libraries": ["django", "djangorestframework", "wagtail", "react", "flutter"],
    "rules_dir": "docs/rules",
    "rules_router": "scripts/inject/route_domains.py",
    "excluded_paths": [],
    "enabled_tools": ["repo", "lsp", "docs"],
    "partition": {"max_group_chars": 120000, "pair_tests_with_source": true}
  }
}
```

Rules:

- Tool code never branches on a profile name. It reads profile fields.
- Resolution: explicit `--profile` wins; `auto` uses `detect`; nothing matches → `generic`.
- `auto` resolving to a profile different from an explicit one is an error for the batch
  reviewer and a warning for the one-shot CLI.
- The active profile, its source file, and enabled tools are printed in the report header.
- Schema validation fails fast with a clear message. A missing or broken profile file must
  not silently fall back to `generic` for the batch reviewer.

## Egress guard

Everything sent to the remote model passes through one guard.

- **Default denies for every profile:** `.env*` (except `.env.example`), `*.pem`, `*.key`,
  `*.p12`, `id_*`, `*secrets*`, `credentials*`, `.git/`, `node_modules/`, `venv/`.
- **Profile `excluded_paths`:** dropped from the diff before sending (listed by name only in
  `<changed-files>` as `excluded by policy`), and refused by every tool (`read_file`,
  `search` results, LSP locations and hover text).
- **Docs queries** carry only a library name and a short topic string. Queries longer than
  a cap, or containing newlines or code-like content, are refused, so source cannot leak to
  a third-party docs API through a query.
- Every tool call (name, arguments, bytes returned, refused or not) is written to a
  per-run `tools.jsonl` and summarized in the report.

## Phases

Each phase ends with its tests passing. Phases 1–8 are in the coworker repo.

### Phase 0 — Baseline and safety

- [x] Show the user the coworker repo's current `git status`/`git diff`; with approval,
      commit the existing modified files and the untracked `kimi-review`,
      `kimi-profiles.json`, `test-kimi-review.py` as a baseline on a new branch. Nothing is
      discarded. **Done 2026-09-24:** branch `kimi-review-tooling`, commit `9807cee`.
- [x] Found during inventory: the installed `~/.local/bin` copies of `ask-kimi` and
      `kimi-write` were newer than `tools/` (OpenRouter defaults, `usage.jsonl` ledger,
      numbered-line citations), and `kimi-challenge` and `kimi-gain` existed only in
      `~/.local/bin`. With approval, all four were imported with the portable shebang
      (commit `77f6586`). The repo now matches what runs. Nothing is pushed: `origin` is
      the upstream author's GitHub repository.
- [x] Run `tools/test-kimi-review.py` and Plant ID's `.claude/hooks/test-kimi-review.sh` and
      record the passing baseline. **Result:** coworker assertions OK; Plant ID 20/20;
      vendored engine matches canonical.
- [x] Confirm the configured `WORKER_MODEL` supports tool calls through the configured
      endpoint, with one tiny tool-call request. **Result:** the configured model is
      `deepseek/deepseek-v4-flash` via OpenRouter, not a Kimi model. It issued a correct
      `read_file` call (`finish_reason=tool_calls`, 2.5 s), answered after the tool result,
      and returned valid strict-schema JSON when asked after a tool-call history. So the
      Phase 7 loop and its separate final JSON call are both supported.

### Phase 1 — Package split without behavior change

**Where the work happens (decided 2026-09-24):** changing the live canonical
`tools/kimi-review` would make Plant ID's drift check fail on every commit until Phase 9.
So Phases 1–8 are built in a separate worktree, `~/.local/share/claude-coworker-dev`,
on branch `kimi-runtime-dev` (branched from `kimi-review-tooling`). The live checkout
and the PATH tool stay on the single-file engine until Phase 9 switches both sides
together. Test against the dev engine with
`KIMI_ENGINE_CANONICAL=~/.local/share/claude-coworker-dev/tools/kimi-review`.

- [x] Move engine internals into `kimi_runtime/`; `tools/kimi-review` becomes a thin CLI.
      Package: `engine.py` (the old file, moved with history) and `usage.py`. The CLI
      forwards module attributes to the engine, so tests that import the CLI file still
      work. `kimi-profiles.json` still resolves beside the CLI. Commit `43d84e7`.
- [x] Same flags, same output text, same exit codes (`0` clean/warnings, `1` tool error,
      `2` verified CRITICAL). `--help` output is byte-identical to the live engine.
- [x] Make argument errors exit `64`, not argparse's `2`, so an unknown flag can never look
      like a verified CRITICAL to the hooks (todo 369 deferred finding). An invalid or
      empty `--tiers` also exited `2` and now exits `64`.
- [x] Log usage to `usage.jsonl` like `ask-kimi` and `kimi-write`, so `kimi-gain` counts it.
      One row per run for the draft call, written before the truncation check because a
      truncated draft is still billed. Agentic-verify calls are not logged yet.
- [x] Existing tests pass unchanged against the split. Coworker suite adds offline tests:
      profile resolution for all three profiles, ledger records and fail-silence, and CLI
      end-to-end runs with a fake `openai` module (exit `0`/`1`/`2`/`64`, output strings,
      ledger rows). Plant ID hook tests pass 20/20 against both the live and the dev
      engine. One live smoke run through the dev CLI returned exit `0` and wrote one row.

### Phase 2 — Profiles v2

- [x] Loader accepting legacy strings and v2 objects; schema validation.
      `kimi_runtime/profiles.py` (commit `1df5a27`). Unknown fields, bad types, invalid
      ids (`auto` is reserved) and unknown `enabled_tools` groups fail with a message that
      names the profile and field. The one-shot CLI still fails open to `generic` on a
      broken file, now with a stderr warning, because the commit gates fail open.
- [x] Convert `plant_id` and `ocrecipes` to v2 with the same guidance text (checked
      byte-for-byte). Only fields verified today were added: `detect`, `languages`,
      `rules_dir`, and `rules_router` for Plant ID. `lsp`, `docs_libraries`,
      `excluded_paths`, `enabled_tools` and `partition` are filled in by the phases that
      use them. `ocrecipes.excluded_paths` waits for the Phase 10 checkpoint.
- [x] Move detection markers from code into profile `detect` blocks. The first matching
      profile in file order wins. A legacy string profile has no `detect`, so `auto` only
      finds it by explicit `--profile`. Every Plant ID caller passes `--profile plant_id`,
      and Plant ID's vendored file converts to v2 in Phase 9.
- [x] Tests: each profile resolves explicitly and by `auto` from a fake repo root; mismatch
      handling; broken file handling. A mismatch only counts when both profiles are project
      profiles. Explicit `generic` never conflicts. The CLI tests check that each profile's
      guidance reaches the prompt. Plant ID hook tests pass 20/20 against the live and dev
      engines, and Plant ID's legacy `scripts/kimi-profiles.json` loads in the new loader.

### Phase 3 — Egress guard

- [x] Default denies plus profile `excluded_paths`, applied to diff hunks and tool results.
      `kimi_runtime/egress.py` (commit `dfd673d`) holds one `Guard` used by every surface:
      diff sections (a section is dropped if its old, new, rename or copy path is denied),
      `--paths`/`--patterns`/`--rules` context files, and the `read_file`/`grep` tools on
      both the working tree and `KIMI_REVIEW_HEAD_SHA`. `run_tool` applies the default denies
      even when no guard is passed. Denied diff files are named in `<changed-files>` with
      `(excluded by policy)`, added to the block if `--changed-files` did not list them.
      - **Pattern rules:** case-insensitive and gitignore-like. A pattern with no inner `/`
        matches any path component; an inner or leading `/` anchors it at the repo root.
        Symlinks are checked after resolving, so a link to `.env` is refused.
        `.env.example` is exempt from the default denies only.
      - **Over-exclusion, accepted as fail-safe:** `*secrets*` and `.env*` also catch
        `.secrets.baseline`, `backend/.env.template`, a few `*secrets*` scripts and todo
        files in Plant ID, and 3 `*secrets*` files in OCRecipes. Their names still reach
        the model; their content does not.
      - **Refusal log (decided):** each refusal calls `on_refusal(surface, path)`. The
        default writes one `[kimi egress: refused <surface>: <path>]` line to stderr, one
        per diff file, context file, `read_file` call, and path dropped from a `grep`.
        The Phase 8 run dir passes a callback that writes `tools.jsonl` instead.
      - **Whole diff denied (decided):** no model call and no usage row. The CLI prints
        the normal `No findings in requested tiers: …` line, adds a stderr line saying
        every file was excluded, and exits `0`. Exit `1` would fail CI on any change that
        only touches denied files. Those files are for human review.
- [x] Tests with a fake repo containing `.env`, a key file, and an excluded directory:
      nothing from them reaches the fake model, and each refusal is logged.
      - The fake `openai` module can now follow a scripted list of responses, including
        tool calls, and record every request.
      - For each of `generic`, `plant_id` and `ocrecipes`, the fake repo has `.env`,
        `deploy/server.key`, `node_modules/`, and a symlink to `.env`. None of their bytes
        reach the model through the diff, `--paths`, or an agentic verify run that asks for
        them with `read_file` (including a `./x/../.env` path) and `grep`.
      - `.env.example` and `app.py` do get through.
      - The exact set of stderr refusal lines is checked.
      - A diff made only of denied files exits `0` without calling the model.
      - In-process tests cover a profile `excluded_paths` directory on every surface. No
        shipped profile set `excluded_paths` at this phase. The dev `plant_id` profile
        gained the list from open decision 1 afterwards (commit `431b7ac`).
      - Removing the guard from the diff, the context files or `grep` each makes the suite
        fail.
      - Plant ID hook tests pass 20/20 against the live and dev engines, and `--help` is
        unchanged.

### Phase 4 — Tool registry and repo tools

- [ ] Registry: JSON schemas, argument validation, per-call timeout, byte cap, call log.
- [ ] Tools: `read_file(path, start_line?, end_line?)`, `search(pattern, glob?)` (fixed
      string via `git grep`), `git_show(ref, path)` for staged/base/head trees,
      `list_changed_files()`.
- [ ] Reuse the Tier B path-escape checks; Tier B verification uses the same registry.

### Phase 5 — LSP tools

- [ ] Minimal stdio JSON-RPC client: `initialize`, `didOpen`, request/response, `shutdown`.
- [ ] Server lifecycle: start lazily per language on first use, reuse for the run, stop at
      the end; warm-up request before the first real query.
- [ ] Tools: `lsp_document_symbols`, `lsp_definition`, `lsp_references`, `lsp_hover`,
      `lsp_diagnostics`. Kimi can pass a `symbol` name instead of a position; the tool
      resolves the position through document symbols.
- [ ] Servers: `typescript-language-server` (installed) and `basedpyright` (pip, coworker
      venv). Dart (`dart language-server`) is optional and only enabled if `dart` is on PATH.
- [ ] Result caps: references ranked by changed-file proximity and truncated with a count.
- [ ] Tests against a fake LSP server script; one opt-in live test per real server.

### Phase 6 — Documentation provider

- [ ] Interface: `query_library_docs(library, topic, version?)`.
- [ ] Context7 adapter over HTTP, per Context7's API guide (checked 2026-09-24):
  - Base URL `https://context7.com`; auth header `Authorization: Bearer $CONTEXT7_API_KEY`.
    `CONTEXT7_API_KEY` was not set on 2026-09-24; it is set in the shell as of 2026-09-30.
    Phase 6 still checks that the engine's process sees it (open decision 2).
  - Default call: `GET /api/v3/search` with `query`, up to four `library` hints, optional
    `version` (needs a library hint), optional `language`, and `type=json`. One request per
    lookup.
  - Pinned-library call: `GET /api/v2/libs/search` (`libraryName`, `query`), then
    `GET /api/v2/context` (`libraryId`, `query`, `type=json`). Two requests. Used when a
    profile pins a library ID such as `/vercel/next.js` or `/owner/repo@<version>`.
  - Response fields used: `codeSnippets[].libraryId`, `codeTitle`, `codeList[].code`, and
    `infoSnippets[].content`. Snippets are trimmed to the tool byte cap.
  - `404 no_documentation_found` means an empty result, not an error. `503 search_failed` is
    retried. `429` is retried after `Retry-After`, within the group deadline.
  - Without a key the API has low rate limits, so the adapter warns once per run when no key
    is set and relies more on the cache.
  - Uses the stdlib `urllib`, so the coworker venv needs no new dependency.
- [ ] Profiles may list `docs_libraries` as names or exact Context7 library IDs.
- [ ] Local cache adapter under `~/.local/share/claude-coworker/cache/docs/`, keyed by
      library + topic + version, with a default TTL of 72 hours (Context7 recommends caching
      for hours or days). Context7 responses are written to it; when Context7 is unreachable
      or rate-limited, the cache answers and the report says so.
- [ ] Profiles limit `docs_libraries`; unknown libraries are allowed but logged.
- [ ] Tests with a fake HTTP server; no network in the default suite.

### Phase 7 — Tool-assisted draft

- [ ] New flag `--tool-mode off|local`, default `local` (open decision 3). The Plant ID
      hooks and CI pass `--tool-mode off` explicitly, in the same change, so gates keep
      today's behavior.
- [ ] Loop: send diff + guidance + tool schemas; run requested tools; repeat until Kimi
      stops calling tools or limits hit (max turns, max tool calls, group deadline).
- [ ] Then a separate final call with the strict findings JSON schema, so tool calls and
      strict JSON output never have to share one request.
- [ ] If the endpoint rejects tools, fall back to one-shot and record the fallback.
- [ ] Verification runs as today on the final findings.

### Phase 8 — Batch orchestrator

- [ ] `kimi-review-batch start|status|wait|list` per the agent-facing contract above.
- [ ] Partitioner: route files with the profile's rules router when present; keep a source
      file with its tests; keep migrations with their models; cap each group by
      `max_group_chars`; never split a file's hunks across groups.
- [ ] Every group gets the full `<changed-files>` manifest, so it knows the rest of the
      change exists.
- [ ] Groups run 3 at a time by default (open decision 4); `--jobs N` changes it and
      `--jobs 1` runs them in order.
- [ ] On a length-truncated group: split it once and retry the halves; if that still
      fails, record the group as errored and continue.
- [ ] Final pass: deduplicate findings across groups by file + line + symbol; no extra model
      call required for that. Optional `--summarize` adds one model call over the findings
      only, not the code.
- [ ] Exit codes for `wait`: `0` no CRITICAL, `2` verified CRITICAL, `1` run failed or
      partial, `124` timeout.

### Phase 9 — Plant ID integration

- [ ] Merge `kimi-runtime-dev` into the live coworker checkout in the same step as the
      sync below, so the drift check never sees a half-switched state.
- [ ] Sync and drift check cover the CLI **and** the `kimi_runtime/` package (CI runs
      `python3 scripts/kimi-review`, so the package must be vendored beside it). Profiles
      stay hand-maintained per repo.
- [ ] Convert the vendored `scripts/kimi-profiles.json` to v2 (plant_id + generic only),
      including `plant_id.excluded_paths` from open decision 1.
- [ ] Extend `.claude/hooks/test-kimi-review.sh` parity checks to the package.
- [ ] Hooks unchanged in behavior: one-shot, deterministic verify, synchronous.
- [ ] Update root `CLAUDE.md` Cheap-Worker section: when to use `kimi-review-batch`, and the
      start-then-poll rule for agents.
- [x] Decide the auth/permissions question below before enabling tools by default here.
      Decided: exclude by path (open decision 1).

### Phase 10 — OCRecipes integration

OCRecipes removed kimi-review on purpose in favor of its `code-reviewer` subagent. Re-adding
it as a gate would reverse that decision, so this phase is deliberately narrow:

- [x] **Checkpoint with the user** before any OCRecipes change: confirm re-enablement and its
      role (proposed: an extra advisory reviewer, not a replacement for `code-reviewer`).
      Decided: advisory and on explicit request only (open decision 5).
- [ ] No pre-commit, Claude hook, or CI gate. `kimi-review-batch` is listed under **ad-hoc**
      (explicit request only) in `docs/AI_WORKFLOW.md`, matching that project's two-tier rule.
- [ ] `ocrecipes` profile `excluded_paths` enumerates the JWT auth, IAP receipt validation,
      and health-data paths (to be listed from the codebase and confirmed by the user), so the
      hard exclusion is enforced by the tool rather than by memory.
- [ ] No vendoring: OCRecipes calls the PATH-installed canonical CLI.
- [ ] Follows OCRecipes' own flow: feature branch, TDD where code changes, PR.

### Phase 11 — Install and docs

- [ ] `setup.sh`: install `kimi-review`, `kimi-review-batch`, `kimi-challenge` and
      `kimi-gain` (today it installs only `ask-kimi`, `kimi-write`, `extract-chat`),
      `pip install basedpyright` into the venv, and check `typescript-language-server`.
- [ ] Decide whether `~/.local/bin` tools become symlinks to `tools/` (like `kimi-review`
      and `extract-chat`) instead of copies, so installed and repo versions cannot drift
      apart again.
- [ ] `kimi-gain` reports `kimi-review` and `kimi-review-batch` usage once Phase 1 logs it.
- [ ] README section for the batch reviewer, tools, profiles v2, and the agent contract.

## Testing strategy

- Hermetic by default: a fake OpenAI-compatible client that replays scripted tool calls and
  findings, a fake LSP server, a fake docs HTTP server. No API key needed.
- Profile matrix: every test that touches profile behavior runs for `generic`, `plant_id`,
  `ocrecipes`.
- Egress tests are mandatory and assert on bytes sent to the fake model.
- Contract tests for the batch reviewer: status transitions, atomic writes, append-only
  report, completion marker, a detached run surviving the parent exiting.
- Plant ID: `.claude/hooks/test-kimi-review.sh` and harness CI stay green.
- Manual smoke before calling it done: one real batch run on a Plant ID branch and one on an
  OCRecipes branch, each with the report read by an agent through `status`/`wait`.

## Open decisions

1. **Auth and security code in Plant ID.** The global rule says cheap workers are never
   pointed at authentication, permissions, input validation, migrations, or security logic,
   yet Plant ID's commit gate reviews every staged diff. Tools that read beyond the diff
   widen that. Choose: add those paths to `plant_id.excluded_paths`, or explicitly accept the
   commit-gate exception for review only. **Decided 2026-09-24:** exclude them. They go in
   `plant_id.excluded_paths`, so the commit gate and every tool see their names only, and
   humans review their content. The user confirmed the drafted list, which is 189 of 2,193
   tracked files beyond the defaults (coworker commit `431b7ac`):
   - `backend/apps/users/`, all `migrations/`, and `permissions.py` / `test_permissions.py`
     at any depth;
   - the core security, validator and sanitizer modules, and the forum sanitize and
     upload-validation modules;
   - the JWT WebSocket middleware, `firebase/firestore.rules`, and the web and mobile auth
     screens, services and CSRF / sanitize helpers;
   - the tests for all of the above.

   Input validation spread through serializers and views can't be excluded by path.
   `docs/rules/security.md` stays allowed because the gate loads it as its checklist.
   Plant ID's vendored `scripts/kimi-profiles.json` gets the list in Phase 9.
2. **Context7 API key.** The API works without a key, but with low rate limits. A
   tool-assisted batch run can make many lookups, so a key from the Context7 dashboard,
   exported as `CONTEXT7_API_KEY`, is recommended. **Decided 2026-09-24:** the user is
   generating a key; Phase 6 verifies it is visible to the engine before live tests.
3. **Default `--tool-mode` for manual `kimi-review`.** Proposed: `off` until Phase 7 has been
   used for a while, then `local`. **Decided 2026-09-24:** `local` from the start for
   manual runs. The commit gates pass `--tool-mode off` explicitly, so their behavior does
   not change.
4. **Parallelism default.** Sequential is cheaper and gentler on rate limits; `--jobs` is
   faster. **Decided 2026-09-24:** small parallel by default (`--jobs 3`), which
   `--jobs 1` makes sequential.
5. **OCRecipes role**, per the Phase 10 checkpoint. **Decided 2026-09-24:** an extra
   advisory reviewer, run only on explicit request, with no hooks, gates or CI. The JWT
   auth, IAP receipt validation and health-data paths still need listing and confirming
   before Phase 10 writes `ocrecipes.excluded_paths`.

## Risks

- **Cost and rate limits** grow with groups × turns × tool calls. Mitigation: per-run caps
  on groups, turns, and tool calls, and usage logging from Phase 1.
- **Cross-group bugs** can still be missed. Mitigation: shared changed-file manifest, and
  tools let a group read code outside its slice.
- **Model tool-calling quality varies** by provider/model. Mitigation: Phase 0 capability
  check and the one-shot fallback.
- **LSP servers are slow to start** and can hang. Mitigation: lazy start, warm-up, timeouts,
  and a failed server disables only its tools, not the review.
- **Vendoring grows** from one file to a package. Mitigation: sync and drift check both
  cover the package; the parity test runs in harness CI.
