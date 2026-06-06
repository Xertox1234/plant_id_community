---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes
---

# Systematic Debugging

> *Extends the official `superpowers:systematic-debugging` skill with LSP-powered
> evidence gathering for this project's Python and TypeScript codebases. The four
> phases and all iron laws from the official skill apply unchanged.*

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

## The Iron Law

```text
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue: test failures, bugs in production, unexpected behavior,
performance problems, build failures, integration issues.

## The Four Phases

### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. Read error messages carefully — stack traces, line numbers, error codes.
2. Reproduce consistently — can you trigger it reliably?
3. Check recent changes — git diff, recent commits, new dependencies.
4. **Gather evidence with LSP (Python + TypeScript files):**

   At the function where the error surfaces:

```text
a. documentSymbol(filePath) → scan the returned symbol list for the target function → get {line, character}
b. incomingCalls({filePath, line, character}) → who actually calls this?
   (replaces grep-based "who calls X?" chains — no text noise)
c. hover({filePath, line, character of suspicious argument})
   → reveals resolved type; type mismatches show here before the stack trace does
```

   If LSP returns an error or inconclusive result, fall back to grep + Read, then continue with step 5.

1. Trace data flow — where does the bad value originate? Keep tracing up until
   you find the source. Fix at source, not at symptom.

### Phase 2: Pattern Analysis

1. Find working examples — locate similar working code.
2. Compare against references — read the reference implementation completely.
3. Identify differences — list every difference, however small.
4. Understand dependencies — config, environment, assumptions.

### Phase 3: Hypothesis and Testing

**Scientific method:**

1. **Form single hypothesis** — "I think X is the root cause because Y."
2. **Before acting, scope the change with LSP:**

```text
a. findReferences({filePath, line, character of symbol to modify})
   → how many files reference this? A wide blast radius needs a wider fix.
b. outgoingCalls({filePath, line, character of suspect function})
   → any unexpected DB or network call reachable from here?
   Treat unexpected calls as new facts — widen the blast-radius estimate before forming a hypothesis.
```

   If LSP returns empty/inconclusive, use grep to estimate blast radius instead.

1. **Test minimally** — the SMALLEST possible change, one variable at a time.
2. **Verify before continuing** — did it work? Yes → Phase 4. No → new hypothesis.
3. **When you don't know** — say so, don't pretend.

### Phase 4: Implementation

1. Create failing test case (use `superpowers:test-driven-development`).
2. Implement single fix — address the root cause identified.
3. Verify fix — test passes, no other tests broken.
4. **If 3+ fixes failed:** question the architecture. Stop and discuss before
   attempting more fixes.

## Red Flags — STOP and Return to Phase 1

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "I don't fully understand but this might work"
- Proposing solutions before tracing data flow
- "One more fix attempt" when already tried 2+

## Supporting Techniques

- `root-cause-tracing.md` (official skill) — trace bugs backward through call stack
- `defense-in-depth.md` (official skill) — validate at multiple layers
- `lsp-intelligence` skill — full LSP operation catalogue and usage rules

**Related skills:**

- `superpowers:test-driven-development` — for creating the failing test (Phase 4)
- `superpowers:verification-before-completion` — verify fix worked before claiming success
