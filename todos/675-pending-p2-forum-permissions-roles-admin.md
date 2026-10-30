---
status: pending
priority: p2
issue_id: "675"
tags: [forum, forum-categories, backend, wagtail, permissions, security]
dependencies: ["666"]
triage: ready
triaged: 2026-10-30
blocked_on: "Owner picks the role→flag matrix, how several groups combine and the no-grant default; the user_can test grid depends on all three."
owner_decision: "Role matrix: phpBB (Full and Std+Polls get all six flags; Standard all but poll; Limited list/read/post/reply; Read Only list/read; No Access none). Grants union across a user's groups. A forum with no grant falls back to Standard for registered members and Read Only for guests, so existing forums keep working with no setup. (owner, 2026-10-30)"
---

# Forum categories slice 11a: forum permission roles, per-group grants and copy permissions (admin)

## Problem

phpBB controls who can see, read, post and reply per forum per group via roles. We only have hidden/visible.

## Findings

- phpBB roles, `f_*` flags and the 'new forum is invisible' footgun: `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Permission flags: list, read, post (new topic), reply, poll, attach. Roles: Full, Standard, Standard + Polls, Limited, Read Only, No Access.
2. Model `ForumGrant(forum, group, role)` using Django/Wagtail groups, plus pseudo-groups for anonymous and all-members.
3. **Default inheritance**: a new forum copies its category's grants (no invisible forums); 'copy permissions from [forum]' action overwrites with a confirmation.
4. Admin: *Permissions* tab with a group × role grid. Enforcement comes in 11b/11c — this slice only stores and edits.

## Technical Details

- New `models/permissions.py`, admin tab, service `forum_permissions.user_can(user, forum, flag)` with a per-request cache.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: creating a forum copies the category's grants.
- [ ] Test: copy-permissions overwrites the target's grants exactly.
- [ ] Test: `user_can` returns the expected result for each role × flag, including anonymous.
- [ ] Test: the admin tab requires the change permission.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-30 - Owner decision

- The 2026-10-29 triage question was answered by the owner: Role matrix: phpBB (Full and Std+Polls get all six flags; Standard all but poll; Limited list/read/post/reply; Read Only list/read; No Access none). Grants union across a user's groups. A forum with no grant falls back to Standard for registered members and Read Only for guests, so existing forums keep working with no setup.
