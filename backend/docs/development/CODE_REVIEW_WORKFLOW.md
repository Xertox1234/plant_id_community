# Mandatory Code Review Workflow

## Overview

This document codifies the **mandatory code review workflow** for all code changes in the Plant ID Community project. This requirement is defined in the project's `CLAUDE.md` file and is **NON-NEGOTIABLE** for production code.

## The Core Requirement

**After completing ANY coding task, you MUST:**

1. Automatically invoke the `code-review-specialist` sub-agent to review changes
2. Wait for the review to complete
3. Address any blockers identified
4. Only then consider the task complete

**This applies to ALL code modifications, no matter how small.**

## Why This Matters

### The Problem Pattern

In multiple sessions, code changes have been completed and committed **without running the mandatory code review step**. This creates:

1. **Risk of Production Issues**: Debug code, security vulnerabilities, or performance issues may slip into production
2. **Inconsistent Quality**: Without systematic review, code quality varies
3. **Lost Learning**: Review feedback helps improve future code
4. **User Frustration**: Users shouldn't have to remind us about documented processes

### Real Example from Sessions

**What Happened:**
```
Session: Issue #5 - Add Missing Type Hints
1. ✅ Modified 3 service files to add type hints
2. ✅ Created comprehensive documentation
3. ✅ Committed changes to git
4. ✅ Marked task complete
5. ❌ Forgot to run code-review-specialist
6. 👤 User: "according to claude.md we are supposed to invoke the code review specialist..."
7. ✅ Ran code-review-specialist (should have been step 5)
```

**This was the SECOND time the user had to remind about this requirement.**

## The Correct Workflow

### Standard Pattern (ALWAYS Follow This)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Plan Implementation                                       │
│    - Understand requirements                                │
│    - Identify files to modify                               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Write the Code                                           │
│    - Make necessary changes                                 │
│    - Follow project standards                               │
│    - Add type hints, docstrings, etc.                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. 🚨 INVOKE code-review-specialist 🚨                      │
│    - MANDATORY STEP - DO NOT SKIP                           │
│    - This is part of "done"                                 │
│    - Reviews ALL modified files                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Wait for Review Completion                               │
│    - Review will identify: blockers, important issues       │
│    - Blockers MUST be fixed                                 │
│    - Important issues SHOULD be fixed                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Address Findings                                         │
│    - Fix all BLOCKER issues immediately                     │
│    - Fix IMPORTANT issues before committing                 │
│    - Consider SUGGESTIONS for improvement                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Commit Changes (if not already committed)                │
│    - Use descriptive commit message                         │
│    - Include Co-Authored-By: Claude                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Mark Task Complete                                       │
│    - All blockers fixed                                     │
│    - Code reviewed and approved                             │
│    - Now truly "done"                                       │
└─────────────────────────────────────────────────────────────┘
```

## When Code Review is REQUIRED

### Always Required For:

- ✅ **Service Layer Changes** - Any modification to `services/*.py`
- ✅ **API Endpoints** - New or modified views, serializers
- ✅ **Models & Migrations** - Database schema changes
- ✅ **Configuration** - Changes to `settings.py`, `urls.py`, `constants.py`
- ✅ **Bug Fixes** - Any code fix, no matter how small
- ✅ **New Features** - Any new functionality
- ✅ **Utilities & Helpers** - Shared code modifications
- ✅ **Frontend Components** - React/JSX/TSX changes
- ✅ **Test Files** - Even test code should be reviewed
- ✅ **Documentation with Code Examples** - Ensure examples are correct

### Simple Rule

**If you modified a file with code in it, code review is REQUIRED.**

File extensions that always trigger code review:
- `.py` (Python)
- `.js`, `.jsx` (JavaScript, React)
- `.ts`, `.tsx` (TypeScript)
- `.dart` (Flutter)
- Any file with executable code

## Pre-Completion Checklist

Before marking ANY task complete, verify:

```
Pre-Completion Checklist for Task: _______________________

[ ] All planned code modifications completed
[ ] Type hints added to all modified functions (Python)
[ ] Constants extracted to constants.py (no magic numbers)
[ ] Logging added with bracketed prefixes ([SERVICE], [CACHE], etc.)
[ ] 🚨 code-review-specialist invoked and completed
[ ] All BLOCKER issues from review fixed
[ ] All IMPORTANT issues from review addressed
[ ] Git commit created (if applicable)
[ ] Task marked complete in todo list (if applicable)

⚠️  If code-review-specialist checkbox is unchecked, task is NOT done!
```

## What Code Review Checks

The `code-review-specialist` agent systematically checks for:

### 🚫 BLOCKERS (Must Fix Immediately)

1. **Debug Code in Production**
   - `console.log`, `console.debug`, `debugger` in JS/React
   - `print()`, `pdb`, `breakpoint()` in Python
   - `TODO`, `FIXME`, `HACK`, `XXX` comments

2. **Security Vulnerabilities**
   - `AllowAny` permissions without `settings.DEBUG` check
   - External API calls without circuit breaker protection
   - Hardcoded secrets or API keys
   - SQL injection risks
   - XSS vulnerabilities (`dangerouslySetInnerHTML`, `eval()`)

3. **Production Readiness Issues**
   - Missing distributed locks on expensive operations
   - API endpoints without versioning (`/api/v1/`)
   - Public endpoints without rate limiting
   - Hardcoded timeouts/TTLs instead of constants

### ⚠️ IMPORTANT ISSUES (Should Fix)

1. **Code Quality**
   - Missing type hints on function signatures
   - N+1 query problems (missing `select_related`)
   - Accessibility issues (missing ARIA labels)
   - Missing error handling

2. **Performance**
   - Inefficient database queries
   - Missing caching opportunities
   - Expensive computations without memoization

3. **Testing**
   - Missing unit tests for new code
   - Insufficient test coverage

### 💡 SUGGESTIONS (Consider)

- Code organization improvements
- Refactoring opportunities
- Better naming conventions
- Documentation enhancements

## Integration with Development Workflow

### When Writing Code

As you work through a coding task:

1. **Keep a mental note**: "I'm modifying code, I'll need code review after this"
2. **Before the final step**: Check if code-review-specialist has been invoked
3. **Use the checklist**: Verify all pre-completion items checked
4. **Don't rush**: Taking 2-3 minutes for review saves hours of debugging later

### When Committing Code

**Ideal Pattern (Preferred):**
```bash
# 1. Write code
# 2. Invoke code-review-specialist
# 3. Fix issues found
# 4. THEN commit
git add .
git commit -m "fix: implement type hints for all service methods"
```

**Acceptable Pattern (If Already Committed):**
```bash
# 1. Write code
# 2. Commit code
git add .
git commit -m "fix: implement type hints for all service methods"

# 3. IMMEDIATELY invoke code-review-specialist
# 4. If issues found, fix and amend commit
git add .
git commit --amend --no-edit
```

**Never Acceptable:**
```bash
# 1. Write code
# 2. Commit code
# 3. Mark complete
# 4. Skip code review ❌ WRONG!
```

## How to Invoke Code Review

### Using Claude Code Agent System

When you have `code-review-specialist` agent configured:

```
# After completing code changes:
"Let me now invoke the code-review-specialist agent to review these changes."

[Invoke code-review-specialist agent]
[Wait for review to complete]
[Address any findings]
```

### Manual Invocation Pattern

If agent system is not available, manually follow the review checklist:

1. List all modified files
2. Check each file for debug code
3. Check for security issues
4. Verify production readiness patterns
5. Check testing status
6. Document findings

## Examples from Real Sessions

### Example 1: Type Hints (Issue #5)

**What Should Have Happened:**
```
✅ Modified plant_id_service.py - added type hints
✅ Modified plantnet_service.py - added type hints
✅ Modified combined_identification_service.py - added type hints
🚨 INVOKE code-review-specialist ← Should happen here
✅ Review completed, no blockers found
✅ Commit changes
✅ Mark complete
```

**What Actually Happened:**
```
✅ Modified plant_id_service.py - added type hints
✅ Modified plantnet_service.py - added type hints
✅ Modified combined_identification_service.py - added type hints
❌ Skipped code review ← ERROR
✅ Commit changes
✅ Mark complete
👤 User: "Why didn't you run code review?"
🚨 THEN invoke code-review-specialist ← Too late!
```

### Example 2: Security Fixes (Issues #2-5)

**Correct Pattern That Was Followed:**
```
✅ Fixed AllowAny permissions
✅ Added circuit breakers
✅ Added distributed locks
✅ Added constants
🚨 INVOKE code-review-specialist ← Done correctly!
✅ Review found one minor issue with lock naming
✅ Fixed the issue
✅ Commit changes
✅ Mark complete
```

This is the pattern to replicate for ALL code changes!

## Trigger Recognition Patterns

### Automatic Triggers

Learn to recognize these situations as **automatic code review triggers**:

1. **Just used Edit/Write tool on .py/.js/.jsx/.tsx file** → Code review required
2. **About to run `git commit`** → Code review required first
3. **About to mark task as "completed" in todo list** → Code review required
4. **Just finished implementing a feature** → Code review required
5. **Just fixed a bug** → Code review required
6. **About to tell user "task complete"** → Code review required

### Self-Check Questions

Before proceeding to completion, ask yourself:

- "Did I modify any code files in this session?"
  - **YES** → Code review required
  - **NO** → No code review needed (docs only, etc.)

- "Have I invoked code-review-specialist yet?"
  - **YES** → Proceed with completion
  - **NO** → Stop and invoke it now

- "Am I about to commit or mark complete?"
  - **YES** → Has code review been done?
  - **NO** → Continue working

## Best Practices

### Do This ✅

1. **Invoke review immediately after code changes**
   - Don't wait until commit time
   - Don't batch multiple tasks before review

2. **Fix all blockers immediately**
   - Blockers indicate production risks
   - Never commit code with blockers

3. **Take review feedback seriously**
   - Reviews catch real issues
   - Learn from patterns identified

4. **Make it a habit**
   - Muscle memory: "code → review → commit"
   - Check the pre-completion checklist every time

### Don't Do This ❌

1. **Skip review because "it's a small change"**
   - Small changes can have big impacts
   - Debug code in one line can break production

2. **Review after commit**
   - Review should inform the commit
   - Amending commits is extra work

3. **Ignore "non-blocker" issues**
   - Important issues become blockers later
   - Suggestions improve code quality

4. **Rush through the workflow**
   - 2-3 minutes now saves hours later
   - Quality over speed

## FAQ

### Q: Do I need code review for documentation changes?

**A:** If documentation contains code examples (Python, JavaScript, etc.), YES. If it's pure prose with no code, NO.

### Q: What if code review finds issues after I've committed?

**A:** Fix the issues and amend your commit:
```bash
# Fix the issues
git add .
git commit --amend --no-edit
```

### Q: Can I batch multiple tasks before running code review?

**A:** NO. Run code review after EACH coding task. This ensures issues are caught early and don't compound.

### Q: What if I disagree with a code review finding?

**A:** For BLOCKERS, they must be fixed (production risks). For other issues, document why you're not addressing it and get user confirmation.

### Q: How long should code review take?

**A:** Typically 2-5 minutes for a focused review of changed files. The agent is efficient and targeted.

## Conclusion

**The mandatory code review workflow is not optional.** It's a core part of the development process that ensures production-ready code.

**Remember:** Code is not "done" until it has been reviewed by code-review-specialist and all blockers have been addressed.

**Workflow Summary:**
```
Write Code → Review Code → Fix Issues → Commit → Complete ✅
```

**Not:**
```
Write Code → Commit → Complete → "Oops, forgot review!" ❌
```

Make code review an automatic, non-negotiable step in every coding task.

---

**Last Updated:** 2025-10-23
**Related Documents:**
- `/CLAUDE.md` - Project-wide development workflow
- `/.claude/agents/code-review-specialist.md` - Agent configuration
- `/backend/docs/development/github-issue-best-practices.md` - Issue workflow
