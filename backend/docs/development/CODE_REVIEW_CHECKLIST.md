# Code Review Pre-Completion Checklist

## 🚨 BEFORE MARKING ANY TASK COMPLETE 🚨

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                                                             ┃
┃  Did you modify ANY code file (.py, .js, .jsx, .tsx)?      ┃
┃                                                             ┃
┃  ┌─────┐                                  ┌─────┐          ┃
┃  │ YES │ → CODE REVIEW REQUIRED!         │  NO │ → OK     ┃
┃  └─────┘                                  └─────┘          ┃
┃                                                             ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## Quick Checklist

Copy this checklist for every coding task:

```
Task: ___________________________________

Pre-Code:
[ ] Requirements understood
[ ] Files to modify identified
[ ] Approach planned

During Code:
[ ] Code written/modified
[ ] Type hints added (Python)
[ ] Constants used (no magic numbers)
[ ] Logging added with prefixes
[ ] Error handling included

🚨 MANDATORY REVIEW STEP:
[ ] code-review-specialist invoked
[ ] Review completed
[ ] All BLOCKERS fixed
[ ] Important issues addressed

Post-Review:
[ ] Changes committed (if applicable)
[ ] Task marked complete
[ ] Documentation updated (if needed)
```

## The 3-Question Test

Before clicking "complete" or running `git commit`, ask:

### Question 1: Did I modify code?
```
Files modified:
- [ ] .py files?
- [ ] .js/.jsx/.tsx files?
- [ ] .dart files?
- [ ] Any executable code?

If ANY checkbox is checked → Code review REQUIRED
```

### Question 2: Did I run code review?
```
- [ ] code-review-specialist agent invoked?
- [ ] Review report received?
- [ ] Blockers identified and fixed?

If ANY checkbox is unchecked → STOP and run review now
```

### Question 3: Am I truly done?
```
- [ ] All blockers fixed
- [ ] Code committed (if applicable)
- [ ] Tests passing (if applicable)
- [ ] Ready for production

If ALL checkboxes checked → Task complete! ✅
```

## Visual Workflow Reminder

```
┌──────────────┐
│ Write Code   │
└──────┬───────┘
       │
       ▼
┌─────────────────────────┐
│ 🚨 CODE REVIEW 🚨       │  ← NEVER SKIP THIS BOX
│                         │
│ Invoke:                 │
│ code-review-specialist  │
└──────┬──────────────────┘
       │
       ▼
┌──────────────┐
│ Fix Issues   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Commit       │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Complete ✅  │
└──────────────┘
```

## Common Mistakes to Avoid

### ❌ Mistake #1: "It's just a small change"
```
❌ WRONG:
   - Fixed one typo in service.py
   - Commit directly
   - Skip review

✅ RIGHT:
   - Fixed one typo in service.py
   - Invoke code-review-specialist
   - Review catches debug print() left behind
   - Remove print(), then commit
```

### ❌ Mistake #2: "I'll review after committing"
```
❌ WRONG:
   - Write code
   - git commit
   - Run review
   - Find issues
   - git commit --amend

✅ RIGHT:
   - Write code
   - Run review
   - Fix issues
   - git commit (clean, correct code)
```

### ❌ Mistake #3: "I already know it's good"
```
❌ WRONG:
   - Experienced developer
   - "I know this code is clean"
   - Skip review
   - Deploy with AllowAny in production

✅ RIGHT:
   - Experienced developer
   - "Let me verify with review"
   - Run review
   - Review catches AllowAny without DEBUG check
   - Fix critical security issue
```

## File Type Quick Reference

### Always Require Review:
- `.py` - Python (services, models, views, etc.)
- `.js` - JavaScript
- `.jsx` - React components
- `.tsx` - TypeScript React
- `.ts` - TypeScript
- `.dart` - Flutter/Dart

### Sometimes Require Review:
- `.md` - If contains code examples → YES
- `.json` - If contains logic (package.json scripts) → YES
- `.yaml`/`.yml` - If contains config logic → YES

### Never Require Review:
- `.md` - Pure documentation prose → NO
- `.txt` - Plain text → NO
- Image files (.png, .jpg) → NO

## Emergency Stop Signs

If you see yourself about to:

```
🛑 STOP: About to run `git commit` without review
🛑 STOP: About to mark task complete without review
🛑 STOP: About to tell user "done" without review
🛑 STOP: About to move to next task without review
```

**Take 2 minutes to run code review now!**

## The Golden Rule

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                                                         ┃
┃   Code is NOT "done" until code-review-specialist       ┃
┃   has reviewed it and all blockers are fixed.           ┃
┃                                                         ┃
┃   NO EXCEPTIONS. NO SHORTCUTS.                          ┃
┃                                                         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## Success Metrics

Track your compliance:

```
Last 5 Coding Tasks:

Task 1: [✅] Code review before commit
Task 2: [✅] Code review before commit
Task 3: [❌] Forgot review, user reminded
Task 4: [✅] Code review before commit
Task 5: [✅] Code review before commit

Goal: 100% compliance (all ✅)
```

## Remember

**3 seconds to check → 3 hours saved debugging**

Don't skip code review. Ever.

---

**Print this checklist. Pin it. Reference it. Every. Single. Time.**
