# Wagtail AI Integration - GitHub Project Board Setup Guide

## Quick Setup (5 minutes)

### Step 1: Create New Project

1. Go to: https://github.com/Xertox1234/plant_id_community/projects
2. Click **"New project"** button
3. Choose **"Table"** view template
4. Name: **"Wagtail AI Integration"**
5. Description: **"Track Wagtail CMS upgrade (prerequisite) and Wagtail AI 3.0 integration across 3 phases"**
6. Click **"Create project"**

---

## Step 2: Add Issues to Project

**Add both issues**:
1. Click **"Add item"** in the project
2. Search for: `#158` (Wagtail upgrade prerequisite)
3. Click to add it
4. Repeat for: `#157` (Wagtail AI integration)

---

## Step 3: Configure Status Column

GitHub Projects automatically creates a **Status** field. Customize it:

**Edit Status Values**:
1. Click **"Status"** column header → **"Edit values"**
2. Create these statuses (in order):

| Status | Description | Color |
|--------|-------------|-------|
| **📋 Backlog** | Not started, awaiting prerequisites | Gray |
| **🔓 Ready** | Prerequisites met, ready to start | Blue |
| **🚧 In Progress** | Currently being worked on | Yellow |
| **👀 In Review** | Implementation complete, in code review | Orange |
| **✅ Done** | Completed and verified | Green |

**Initial Status Assignment**:
- Issue #158 (Wagtail Upgrade): Set to **"🔓 Ready"** (can start immediately)
- Issue #157 (Wagtail AI): Set to **"📋 Backlog"** (blocked by #158)

---

## Step 4: Add Custom Fields

Click **"+"** next to column headers to add custom fields:

### Field 1: Phase (Single Select)

**Field Name**: `Phase`
**Type**: Single select
**Options**:
- **Prerequisite** (for Issue #158)
- **Phase 1: Foundation** (Wagtail AI setup)
- **Phase 2: Blog Integration** (AI panels, caching)
- **Phase 3: Advanced** (Vector indexing, forum AI)

**Assignment**:
- #158 → **Prerequisite**
- #157 → Leave empty initially (will be updated as phases progress)

---

### Field 2: Effort (Single Select)

**Field Name**: `Effort`
**Type**: Single select
**Options**:
- **XS** (< 2 hours)
- **S** (2-4 hours) ← Issue #158
- **M** (1-2 days)
- **L** (3-5 days) ← Issue #157 (each phase)
- **XL** (1-2 weeks)

**Assignment**:
- #158 → **S** (4-5 hours)
- #157 → **XL** (2-3 weeks total)

---

### Field 3: Priority (Single Select)

**Field Name**: `Priority`
**Type**: Single select
**Options**:
- **🔴 Critical** (P1 - fix within 24-48 hours)
- **🟠 High** (P2 - 1 week) ← Issue #158
- **🟡 Medium** (P3 - 2-4 weeks) ← Issue #157
- **🟢 Low** (P4 - fix when possible)

**Assignment**:
- #158 → **🟠 High**
- #157 → **🟡 Medium**

---

### Field 4: Type (Single Select)

**Field Name**: `Type`
**Type**: Single select
**Options**:
- **🔧 Refactor** ← Issue #158
- **✨ Enhancement** ← Issue #157
- **🐛 Bug**
- **📚 Documentation**

**Assignment**:
- #158 → **🔧 Refactor**
- #157 → **✨ Enhancement**

---

### Field 5: Blocks/Blocked By (Text)

**Field Name**: `Dependencies`
**Type**: Text

**Assignment**:
- #158 → **"Blocks: #157"**
- #157 → **"Blocked by: #158"**

---

## Step 5: Create Saved Views

Click **"New view"** to create filtered views:

### View 1: Board View (Default)

**Name**: "📊 Board View"
**Type**: Board
**Group by**: Status
**Sort by**: Priority (High → Low)

This gives you a Kanban-style board:
```
┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│   Backlog   │    Ready    │ In Progress │  In Review  │    Done     │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│   #157      │   #158      │             │             │             │
│ (Wagtail AI)│  (Upgrade)  │             │             │             │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
```

---

### View 2: Table View (Detailed)

**Name**: "📋 Table View"
**Type**: Table
**Columns to show**:
- Title
- Status
- Phase
- Priority
- Effort
- Dependencies
- Assignees

**Sort**: Priority (High → Low), then Status

---

### View 3: Timeline View (Gantt Chart)

**Name**: "📅 Timeline"
**Type**: Roadmap
**Group by**: Phase
**Date field**: Start date / Target date

This shows the sequential nature:
```
Prerequisite     ████ (1-2 days)
                      ↓
Phase 1          ────██ (2-3 hours)
                         ↓
Phase 2          ────────████ (1-2 days)
                             ↓
Phase 3          ────────────████████ (1 week)
```

---

### View 4: Phase View (Grouped)

**Name**: "🎯 By Phase"
**Type**: Board
**Group by**: Phase
**Sort by**: Priority

Shows all work grouped by implementation phase.

---

## Step 6: Configure Automation (Optional)

GitHub Projects has built-in automation. Set these up:

### Auto-Archive

**When**: Item status changes to **Done**
**Action**: Auto-archive after 7 days

### Auto-Set Status

**When**: Issue is closed
**Action**: Set status to **Done**

**When**: Issue is reopened
**Action**: Set status to **In Progress**

### Auto-Assign

**When**: Status changes to **In Progress**
**Action**: Require assignee (prompt to assign)

---

## Step 7: Add Project Description & README

1. Click **"⋯"** (three dots) in top right
2. Select **"Edit project"**
3. Add description:

```markdown
# Wagtail AI Integration Project

Track the implementation of Wagtail AI 3.0 for the Plant ID Community CMS.

## Phases

**Prerequisite** (Issue #158):
- Upgrade Wagtail 7.0.3 → 7.1+
- Timeline: 1-2 days
- **MUST complete before AI integration**

**Phase 1 - Foundation** (Issue #157):
- AI provider configuration
- Basic setup and testing
- Timeline: 2-3 hours

**Phase 2 - Blog Integration** (Issue #157):
- AI panels for title/description
- Contextual image alt text
- Caching layer
- Timeline: 1-2 days

**Phase 3 - Advanced Features** (Issue #157):
- Vector indexing for related pages
- Forum AI quality feedback
- Cost monitoring and rate limiting
- Timeline: 1 week

## Success Metrics

- ✅ All 232+ tests passing
- ✅ 30% reduction in content creation time
- ✅ 100% images with contextual alt text
- ✅ API costs <$5/month with caching

## Links

- [Issue #158: Wagtail Upgrade](https://github.com/Xertox1234/plant_id_community/issues/158)
- [Issue #157: Wagtail AI Integration](https://github.com/Xertox1234/plant_id_community/issues/157)
- [Wagtail AI Docs](https://wagtail-ai.readthedocs.io/)
```

---

## Step 8: Initial Board State

After setup, your board should look like this:

### Table View

| Title | Status | Phase | Priority | Effort | Dependencies | Assignee |
|-------|--------|-------|----------|--------|-------------|----------|
| #158: Wagtail Upgrade | 🔓 Ready | Prerequisite | 🟠 High | S (4-5h) | Blocks: #157 | [Assign] |
| #157: Wagtail AI | 📋 Backlog | (TBD) | 🟡 Medium | XL (2-3w) | Blocked by: #158 | - |

---

## Step 9: Workflow - How to Use the Board

### When Starting Issue #158 (Prerequisite)

1. **Assign** the issue to yourself
2. **Move** status: Ready → **In Progress**
3. **Create a branch**: `git checkout -b wagtail-upgrade-7.1`
4. **Update** the issue with progress comments
5. When complete:
   - **Create PR** with reference to #158
   - **Move** status: In Progress → **In Review**
6. After PR merged:
   - **Move** status: In Review → **Done**
   - **Unblock** Issue #157: Move from Backlog → **Ready**

### When Starting Issue #157 (Wagtail AI)

After #158 is complete:

1. **Move** #157: Backlog → **Ready**
2. **Update** Phase field to **Phase 1: Foundation**
3. **Assign** to yourself
4. **Move** status: Ready → **In Progress**
5. Work in phases:
   - Complete Phase 1 → Create PR → Review → Merge
   - Update Phase field to **Phase 2**
   - Repeat for Phases 2 and 3
6. When all phases complete:
   - **Move** status: In Review → **Done**
   - **Close** issue #157

---

## Step 10: Additional Customizations (Optional)

### Add Milestone Field

**Field Name**: `Milestone`
**Type**: Single select
**Options**:
- **Sprint 1** (Prerequisite - Issue #158)
- **Sprint 2** (Phase 1 & 2 - Issue #157)
- **Sprint 3** (Phase 3 - Issue #157)

### Add Labels Field

GitHub automatically syncs labels from issues. No setup needed.

### Add Linked PRs Field

**Field Name**: `Pull Requests`
**Type**: Linked Pull Requests (automatic)

This will auto-populate when you create PRs that reference the issues.

---

## Quick Reference Commands

### Link Issues in PRs

When creating PRs, use these keywords in the PR description to auto-link:

```markdown
Closes #158
Resolves #157
Fixes #158
Part of #157
```

### Update Project from CLI (After Auth Setup)

```bash
# Add issue to project
gh project item-add [PROJECT_NUMBER] --owner Xertox1234 --url https://github.com/Xertox1234/plant_id_community/issues/158

# List all project items
gh project item-list [PROJECT_NUMBER] --owner Xertox1234

# Update item status
gh project item-edit --project-id [PROJECT_ID] --id [ITEM_ID] --field-id [STATUS_FIELD_ID] --single-select-option-id [OPTION_ID]
```

---

## Visual Project Board Layout

### Recommended Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🎯 Wagtail AI Integration                                   ⚙️ ⋯  │
├─────────────────────────────────────────────────────────────────────┤
│ Track Wagtail CMS upgrade and AI integration                       │
│                                                                     │
│ 📊 Views: [Board] [Table] [Timeline] [By Phase]                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  📋 Backlog          🔓 Ready           🚧 In Progress              │
│ ┌──────────────┐   ┌──────────────┐   ┌──────────────┐            │
│ │ #157         │   │ #158         │   │              │            │
│ │ Wagtail AI   │   │ Wagtail 7.1  │   │              │            │
│ │              │   │ Upgrade      │   │              │            │
│ │ 🟡 Medium    │   │ 🟠 High      │   │              │            │
│ │ XL (2-3w)    │   │ S (4-5h)     │   │              │            │
│ │              │   │              │   │              │            │
│ │ Blocked by   │   │ Blocks #157  │   │              │            │
│ │ #158         │   │              │   │              │            │
│ └──────────────┘   └──────────────┘   └──────────────┘            │
│                                                                     │
│  👀 In Review        ✅ Done                                        │
│ ┌──────────────┐   ┌──────────────┐                               │
│ │              │   │              │                               │
│ │              │   │              │                               │
│ └──────────────┘   └──────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Success Checklist

After completing setup, verify:

- [x] Project created with descriptive name
- [x] Both issues (#157, #158) added to project
- [x] Status column configured with 5 states
- [x] Custom fields added (Phase, Effort, Priority, Type, Dependencies)
- [x] 4 saved views created (Board, Table, Timeline, Phase)
- [x] Automation rules configured
- [x] Project description added with links
- [x] Initial statuses set (#158 = Ready, #157 = Backlog)
- [x] Dependencies documented in custom field

---

## Next Steps

1. **Review the board**: https://github.com/Xertox1234/plant_id_community/projects/[YOUR_PROJECT_NUMBER]
2. **Assign Issue #158** to yourself or team member
3. **Start work** on prerequisite upgrade
4. **Update board** as you progress through phases

**Estimated Setup Time**: 5-10 minutes
**Result**: Professional project tracking with clear dependencies and phase visibility

---

## Tips for Success

✅ **Update status frequently** - Keep the board current
✅ **Use comments** - Document progress on issues
✅ **Link PRs** - Use "Closes #158" in PR descriptions
✅ **One task in progress** - Avoid multitasking
✅ **Review regularly** - Weekly check-ins on progress

---

## Alternative: Simple Milestone Approach

If a full project board feels like overkill, you can use GitHub Milestones instead:

**Milestone 1**: "Wagtail AI Integration - Prerequisite"
- Due date: 1 week from now
- Issues: #158

**Milestone 2**: "Wagtail AI Integration - Implementation"
- Due date: 4 weeks from now
- Issues: #157

This gives you a simpler progress view at: https://github.com/Xertox1234/plant_id_community/milestones