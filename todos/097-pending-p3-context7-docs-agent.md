---
status: pending
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

- [ ] Context7 is available from a fresh checkout without a per-developer plugin
      install (committed `.mcp.json` or equivalent project config).
- [ ] `docs-researcher` tool-name references match the configured server's prefix
      and the Context7-first ordering is intact.
- [ ] `CLAUDE.md` documents Context7 as the doc-research backend.
- [ ] A verification run shows `docs-researcher` resolving + querying docs via
      Context7 (and `/audit` Phase 2.5 citing Context7), not falling back to web
      search.
- [ ] No API key committed (secrets hooks pass).

## Work Log

### 2026-05-25 - Created

- Found that `docs-researcher` already prioritizes Context7 but it's only a global
  plugin with no committed project config. Todo created to make it a first-class,
  project-pinned documentation backend.

## Notes

Priority p3 — DX/tooling reliability, not user-facing. Implementation touches
`.mcp.json` (repo root, allowed) + `CLAUDE.md` (allowed); the `docs-researcher.md`
tweak lives under `.claude/` and may be blocked in auto-mode — apply that part
manually if the harness refuses. Verify the exact Context7 package name / config
and whether an API key is needed against Context7's current docs during
implementation rather than trusting this todo's example verbatim.
