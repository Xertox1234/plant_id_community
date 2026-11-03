---
status: pending
priority: p3
issue_id: "690"
tags: [harness, sandbox, permissions, owner]
dependencies: []
---

# Owner settings: sandbox network allowlist, railway ssh policy, routine merge rule

## Problem

Three blockers recur, and only the owner can clear them, because they live in Claude Code settings files that agents cannot write. Each one costs every agent a retry, a sandbox-off prompt or a stop.

## Findings

- **1. Railway API host not allowlisted.** `railway deployment list` failed in the sandbox (`deny network-outbound backboard.railway.com:443`) until the command listed it in `allowed_domains`. Read-only probes of the public API (`api.houseplant-md.com`) hit the same wall. (2026-11-03)
- **2. `railway ssh` cannot run in the sandbox.** It runs plain `ssh -i ~/.ssh/id_ed25519 -T <instance>@ssh.railway.com <cmd>` (CLI 5.59.0, observed through a shim), and `ssh` does not use the sandbox's HTTP proxy, so it fails with "Could not resolve hostname".
  - An authenticated CONNECT through the proxy *does* reach the server: `200 Connection Established`, then `SSH-2.0-Go`.
  - A `ProxyCommand` script plus install notes are in `~/Library/Application Support/Claude/side-session-notes/local_4e3922c8-d2bf-4ddd-9f8a-6aed00e242c4/ssh-via-proxy{.py,-INSTALL.md}`.
  - However, the auto-mode classifier refused the end-to-end test as **"Containment Escape"**. So that route will likely be refused for Claude in auto mode. Today every prod command runs with the sandbox off behind a permission prompt.
- **3. Merging an owner-approved PR.** `gh pr merge 1252 --squash` was refused as "Merge Without Review". It went through on retry after the owner said "Allow, then merge" in chat. Without a rule, every merge needs that exchange.

## Proposed Solutions

### Option 1: settings changes by the owner (recommended)

- **Implementation** (all through `/sandbox` or `/permissions` in an interactive `claude` terminal):
  1. Add `backboard.railway.com` and `api.houseplant-md.com` to the sandbox network allowlist. Both are first-party services.
  2. Choose a `railway ssh` policy:
     - (a) keep the per-command sandbox-off prompt (recommended for prod writes), or
     - (b) add `railway` to the sandbox's excluded commands.
     The ProxyCommand route is not recommended while the classifier treats it as containment escape.
  3. Optional: a permission rule allowing `gh pr merge * --squash`. Keep the habit of reviewing the PR diff first (memory: "prefer auto-merge").
- **Effort:** 15 min.
- **Risk:** (1) low. (2b) widens what runs unsandboxed. (3) removes one review checkpoint.

## Recommended Action

1. The owner applies 1, chooses for 2, and decides on 3.
2. Record each decision with its date in the Work Log, then archive.

## Technical Details

- Settings live in `~/.claude/settings.json` / `.claude/settings.json`. Both are in the sandbox's write deny list, by design.
- Evidence: the session that fixed the username email leak (PR #1252, 2026-11-03).

## Acceptance Criteria

- [ ] `railway deployment list --service plant_id_community` succeeds sandboxed with no `allowed_domains` (date + output recorded here).
- [ ] The `railway ssh` policy is decided and recorded with its date.
- [ ] The merge-rule decision is recorded with its date (adopted or declined).

## Work Log

### 2026-11-03 - Filed

- Collected from the username-leak session. The owner asked for todos so agents stop working around the same blockers.
