---
status: completed
priority: p3
issue_id: "097"
tags: [tooling, docs, mcp, agents, dx]
dependencies: []
---

# Wire Context7 in as the project's documentation-research backend

## Problem

The `docs-researcher` agent is meant to fetch current, version-specific library
documentation (and validate audit findings) using **Context7** as its primary
source — but Context7 is only available via a globally-installed Claude Code
**plugin**, not pinned or committed at the project level. So on a fresh clone, a
contributor without the plugin, or CI, the agent's #1 doc source is silently
unavailable and it falls back to web search — defeating the point of
version-accurate docs. Make Context7 a first-class, project-configured,
documented backend for the documentation agent.

## Findings

- `.claude/agents/docs-researcher.md:42-48` **already** prioritizes Context7:
  > "Gather documentation, in priority order: 1. **Context7 MCP** —
  > `mcp__plugin_context7_context7__resolve-library-id` then
  > `mcp__plugin_context7_context7__query-docs`. 2. WebFetch … 3. WebSearch …"
  So the agent design is done; only the wiring/availability is missing.
- `/audit` Phase 2.5 dispatches `docs-researcher` per domain
  (`.claude/skills/audit/SKILL.md:88-92`) and `CLAUDE.md:159` documents it — so
  Context7 reliability directly affects audit-finding validation quality.
- **No project `.mcp.json` exists** (none at repo root). The Context7 tools in
  interactive sessions come from a globally-installed plugin
  (`plugin:context7:context7` → `mcp__plugin_context7_context7__*`), which is
  per-developer and not committed.
- The tool names are namespaced `mcp__plugin_context7_context7__*` (plugin form),
  not the bare `mcp__context7__*` an `.mcp.json` server would produce — so the
  agent's hardcoded tool names may need reconciling depending on how Context7 is
  added (plugin vs. project MCP server use different tool-name prefixes).

## Proposed Solutions

### Option 1: Add Context7 as a committed project MCP server (Recommended)

- **Implementation:** Add a project-root `.mcp.json` with the Context7 MCP server
  so every contributor + the `docs-researcher` agent + CI get it on checkout;
  document it in `CLAUDE.md`; reconcile the agent's tool-name references with the
  resulting prefix.
- **Pros:** Pinned, committed, consistent across environments; no per-dev install;
  makes Context7 the sanctioned doc source it's already documented to be.
- **Cons:** Adds an `npx`/network dependency at MCP startup; tool-name prefix may
  differ from the plugin form (`mcp__context7__*` vs `mcp__plugin_context7_context7__*`)
  — must update `docs-researcher.md` to match (note: editing `.claude/` may be
  blocked in auto-mode; apply manually if so — see [[feedback-harness-self-mod-block]]).
- **Effort:** ~1 hour incl. verification.
- **Risk:** low (additive tooling; falls back to WebFetch/WebSearch if Context7 is down).

### Option 2: Keep plugin-only, just document the install

- **Implementation:** Leave Context7 as a global plugin; add CLAUDE.md setup notes
  telling contributors to install the plugin.
- **Pros:** Zero config churn; keeps the existing `mcp__plugin_context7_context7__*`
  tool names the agent already uses.
- **Cons:** Still per-developer and easy to skip; not available in CI; doesn't make
  it a committed project guarantee.
- **Effort:** ~15 min.
- **Risk:** low, but doesn't actually solve the reliability gap.

## Recommended Action

1. Add a project-root `.mcp.json` with the Context7 server (verify exact package
   and config against Context7's own docs at implementation time — use the
   running Context7 MCP or the `upstash/context7` README; do not assume):

   ```json
   {
     "mcpServers": {
       "context7": {
         "command": "npx",
         "args": ["-y", "@upstash/context7-mcp"]
       }
     }
   }
   ```

2. (Optional, for higher rate limits) Configure `CONTEXT7_API_KEY` via env / the
   harness `settings.json` `env` block — **never commit the key** (the
   `scan-api-keys` / detect-secrets pre-commit hooks will block it; see
   [[project-commit-hook-friction]]).
3. Reconcile tool-name references in `.claude/agents/docs-researcher.md` with the
   prefix the project server produces (likely `mcp__context7__resolve-library-id`
   / `mcp__context7__query-docs`). Keep the priority ordering (Context7 → WebFetch
   → WebSearch → project files).
4. Document Context7 in `CLAUDE.md` (Harness Automation / Code Review Agents
   section) as the sanctioned documentation backend for `docs-researcher` and
   `/audit` Phase 2.5.
5. Verify end-to-end: dispatch `docs-researcher` on a known library (e.g. "DRF
   throttling in the installed version") and confirm it resolves the library id +
   queries docs via Context7 (not just web search); run one `/audit` slice and
   confirm Phase 2.5 validation cites Context7 docs.

## Technical Details

- Agent: `.claude/agents/docs-researcher.md` (Context7 already listed first, lines 42-48).
- Audit usage: `.claude/skills/audit/SKILL.md` Phase 2.5 (line 88+); `CLAUDE.md:159`.
- Config target: new `.mcp.json` at repo root (none today). `.gitignore` does not
  currently exclude it — confirm before committing.
- Tool-name prefixes: plugin form is `mcp__plugin_context7_context7__*`; a project
  `.mcp.json` server named `context7` yields `mcp__context7__*`. Pick one and make
  the agent + any docs consistent.

## Acceptance Criteria

- [x] Context7 is available from a fresh checkout without a per-developer plugin
      install (committed `.mcp.json` or equivalent project config).
- [x] `docs-researcher` tool-name references match the configured server's prefix
      and the Context7-first ordering is intact.
- [x] `CLAUDE.md` documents Context7 as the doc-research backend.
- [x] A verification run shows `docs-researcher` resolving + querying docs via
      Context7 (and `/audit` Phase 2.5 citing Context7), not falling back to web
      search. — LIVE-CONFIRMED 2026-05-29 (post-restart): the `docs-researcher`
      subagent reported `TOOLS USED: mcp__context7__resolve-library-id,
      mcp__context7__query-docs` (the committed-server prefix; plugin gone) and
      returned real version-specific DRF docs cited to Context7, not web search.
      Also confirmed by a direct resolve+query via the committed `mcp__context7__*`
      tools. (Initially accepted at archival on handshake + agent-config evidence.)
- [x] No API key committed (secrets hooks pass).

## Work Log

### 2026-05-25 - Created

- Found that `docs-researcher` already prioritizes Context7 but it's only a global
  plugin with no committed project config. Todo created to make it a first-class,
  project-pinned documentation backend.

### 2026-05-29 - Started by completing-todos skill (run 2026-05-29-1457)

- Picked up by automated workflow.

### 2026-05-29 - BLOCKED by auto-mode self-modification classifier

**Pre-work verification (done, authoritative):**

- `npm view @upstash/context7-mcp version` → `3.0.0` (package exists).
- MCP `tools/list` handshake against the exact command `npx -y @upstash/context7-mcp`
  booted ("Context7 Documentation MCP Server v3.0.0 running on stdio") and reported
  tools: **`resolve-library-id`** and **`query-docs`** (protocol 2024-11-05). So a
  project server named `context7` yields `mcp__context7__resolve-library-id` /
  `mcp__context7__query-docs`. (The historical `get-library-docs` name does NOT apply
  to v3 — bare names match the plugin; only the prefix differs.)

**Block:** Writing `.mcp.json` (repo root) was denied by the auto-mode classifier as
"config the agent loads at startup (Self-Modification)." This todo's assumption that
`.mcp.json` at repo root is "allowed" is WRONG — repo-root MCP config is treated as
self-mod, same class as `.claude/`. By the same rule `CLAUDE.md` (startup instructions)
and `.claude/agents/docs-researcher.md` (agent def) are also blocked. Not bypassed via
Bash (would defeat the block's intent). See [[feedback-harness-self-mod-block]].

**Ready-to-apply changes (verified; apply manually or after granting access):**

1. NEW file `/.mcp.json` (repo root):

   ```json
   {
     "mcpServers": {
       "context7": {
         "command": "npx",
         "args": ["-y", "@upstash/context7-mcp"]
       }
     }
   }
   ```

2. `.claude/agents/docs-researcher.md` — replace the Context7 bullet (currently
   lines 43-44) with the committed-server prefix as primary + plugin fallback note,
   ordering intact:

   ```markdown
      1. **Context7 MCP** — `mcp__context7__resolve-library-id` then
         `mcp__context7__query-docs` (from the committed project `.mcp.json`; if the
         global Context7 plugin is used instead, the equivalent tools are
         `mcp__plugin_context7_context7__resolve-library-id` /
         `mcp__plugin_context7_context7__query-docs`).
   ```

3. `CLAUDE.md` — (a) update the `docs-researcher.md` line under "Non-review agents":

   ```markdown
   - `docs-researcher.md` — validates findings against current library docs via
     Context7 (committed `.mcp.json`; see Harness Automation → Documentation backend),
     used by `/audit` Phase 2.5
   ```

   (b) add a subsection before "## Environment Variables":

   ```markdown
   ### Documentation backend — Context7 (`.mcp.json`)

   A committed project-root `.mcp.json` registers **Context7**
   (`@upstash/context7-mcp`) as the sanctioned, version-accurate documentation source.
   It is the #1 backend for the `docs-researcher` agent and `/audit` Phase 2.5 (ahead
   of WebFetch/WebSearch), so doc research and audit-finding validation no longer
   depend on a per-developer plugin install. Tools: `mcp__context7__resolve-library-id`
   and `mcp__context7__query-docs`. Claude Code asks once to trust the server on first
   use; no API key needed (set optional `CONTEXT7_API_KEY` for higher rate limits —
   never commit it).
   ```

**Remaining after apply:** restart the session (so the committed `mcp__context7__*`
tools load + one trust approval), then dispatch `docs-researcher` on a known library
to confirm it uses Context7 (criterion 4 committed-path leg).

### 2026-05-29 - Implemented (auto-mode disabled by user) + verified

- User disabled auto-mode; all 3 changes applied: `.mcp.json` (new),
  `docs-researcher.md` (committed `mcp__context7__*` prefix + plugin fallback note),
  `CLAUDE.md` (docs-researcher line + new "Documentation backend — Context7" subsection).
- **C1 PASS** — `.mcp.json` valid JSON (`python3 -m json.tool`), not gitignored,
  present as `?? .mcp.json`. Committed command boots (handshake: "Context7 …v3.0.0
  running on stdio").
- **C2 PASS** — grep shows `mcp__context7__resolve-library-id`/`query-docs` (matches
  server name `context7`); ordering intact: 1. Context7 → 2. WebFetch → 3. WebSearch
  → 4. Project files.
- **C3 PASS** — `grep Context7 CLAUDE.md` → docs-researcher line + new subsection.
- **C4 PARTIAL** — live `resolve-library-id` ("Django REST Framework" →
  `/encode/django-rest-framework`) + `query-docs` ("throttling") returned real
  GitHub-sourced DRF docs (ScopedRateThrottle, DEFAULT_THROTTLE_RATES, 429 shape) —
  proves Context7 backend works, not web fallback. Committed-server subagent
  observation deferred to a session restart (MCP config can't hot-load mid-session);
  not flipped per verification discipline.
- **C5 PASS** — no key/secret in `.mcp.json` (keyless); secrets hook confirms at commit.

### RESUME INSTRUCTIONS (post-restart) — only C4 remains

Implementation is DONE (do not redo it). On a fresh session that has loaded the
committed `.mcp.json` (approve the one-time Context7 trust prompt at startup):

1. Confirm `mcp__context7__resolve-library-id` / `mcp__context7__query-docs` are
   available (the committed-server prefix, not `mcp__plugin_context7_context7__*`).
2. Dispatch the `docs-researcher` agent on a known library (e.g. "DRF throttling in
   the installed version") and confirm it resolves + queries via the committed
   `mcp__context7__*` tools, not web search. (A direct call to those tools is an
   acceptable lighter alternative.)
3. Flip C4 to `- [x]` with the observed tool name quoted; then run Step 4 code review
   on the diff and Step 5 archive. Run checkpoint: `.completing-todos-run-2026-05-29-1457.json`.

### 2026-05-29 - Completed by completing-todos skill (run 2026-05-29-1457)

- Closed on gathered evidence per user decision (chose "close it now" over a restart);
  the RESUME INSTRUCTIONS above were therefore NOT executed — no restart performed.
- Verification: C1, C2, C3, C5 passed with quoted evidence (above). C4 accepted on the
  handshake + live resolve/query + agent-config evidence; the committed-subagent
  observation is deferred to the next Claude Code launch.
- Review: independent general-purpose reviewer (dedicated `*-reviewer` subagents are not
  registered in this environment; the diff is config + docs). 1 finding, 0 blocking:
  - Known issue (accepted, LOW) — `.mcp.json` uses unpinned `npx -y @upstash/context7-mcp`;
    a future malicious/breaking publish would auto-execute on cold start. Matches the
    todo's spec and upstream Context7's recommended setup, so kept unpinned. To harden
    later, pin `@upstash/context7-mcp@3.0.0`.

### 2026-05-29 - C4 LIVE-CONFIRMED post-restart

- User restarted Claude Code; the committed `.mcp.json` Context7 server loaded as
  `mcp__context7__resolve-library-id` / `mcp__context7__query-docs`, and the global
  plugin (`mcp__plugin_context7_context7__*`) disconnected — so the committed server
  was the ONLY Context7 backend available.
- Direct call: committed `mcp__context7__resolve-library-id` ("Django REST Framework")
  + `mcp__context7__query-docs` returned real GitHub-sourced DRF throttling docs.
- Agent run: dispatched `docs-researcher`; it reported `TOOLS USED:
  mcp__context7__resolve-library-id, mcp__context7__query-docs` and returned
  version-specific DRF pagination docs (cross-referenced project DRF 3.17.1/3.16.1)
  cited to Context7 `/websites/django-rest-framework` — NOT a web fallback.
- C4's deferred live leg is now fully closed against the committed server; all 5
  acceptance criteria are live-verified.

## Notes

Priority p3 — DX/tooling reliability, not user-facing. Implementation touches
`.mcp.json` (repo root, allowed) + `CLAUDE.md` (allowed); the `docs-researcher.md`
tweak lives under `.claude/` and may be blocked in auto-mode — apply that part
manually if the harness refuses. Verify the exact Context7 package name / config
and whether an API key is needed against Context7's current docs during
implementation rather than trusting this todo's example verbatim.
