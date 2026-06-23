#!/usr/bin/env bash
# PreToolUse hook for Bash — when the about-to-run command is a real `git commit`,
# run kimi-review over the staged diff. CRITICAL findings block the commit;
# WARNING findings are surfaced as additionalContext but do not block.
#
# Skip semantics (all early exit 0, silently):
#   - $SKIP_KIMI_REVIEW=1                  → user opt-out (CI, rebases, known-good)
#   - `kimi-review` not on PATH            → dev without the tool installed
#   - `jq` not on PATH                     → cannot parse hook event or build JSON safely
# Tests: .claude/hooks/test-kimi-review.sh

set -uo pipefail

# 1) Explicit opt-out
[ -n "${SKIP_KIMI_REVIEW:-}" ] && exit 0

# 2) Required tooling — auto-skip if missing
command -v jq >/dev/null 2>&1 || exit 0
command -v kimi-review >/dev/null 2>&1 || exit 0

# 3) Read the hook event JSON and extract the pending Bash command
INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -re '.tool_input.command' 2>/dev/null) || exit 0

# 4) Match only real `git commit` invocations. Anchored at ^ so substrings like
#    `echo git commit ...` are rejected; trailing ([[:space:]]|$) so `commit-graph`
#    and other `commit*` subcommands are rejected. Allows leading VAR=val env
#    prefixes and `git -c key=val commit ...` chains.
GIT_COMMIT_RE='^([[:space:]]*[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]+[[:space:]]+)*git([[:space:]]+-c[[:space:]]+[^[:space:]]+)*[[:space:]]+commit([[:space:]]|$)'
[[ "$COMMAND" =~ $GIT_COMMIT_RE ]] || exit 0

# 5) No staged changes → nothing to review
FILES=$(git diff --cached --name-only 2>/dev/null)
[ -n "$FILES" ] || exit 0

# 6) Map staged files to docs/rules/ domains via the shared matcher. Single source
#    of truth: docs/rules/routing.json (also consumed by inject-patterns.sh and the
#    codify skill). The matcher is additive (this normalizes the old first-match-wins
#    case to the additive model inject-patterns.sh already used — strictly more
#    thorough for the gate). Fail-open: missing python3 or unreadable routing →
#    empty PATTERNS, so the review below still runs, just unscoped.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PATTERNS=''
if command -v python3 >/dev/null 2>&1; then
  PATTERNS=$(printf '%s' "$FILES" \
    | python3 "$PROJECT_ROOT/scripts/inject/route_domains.py" 2>/dev/null) \
    || PATTERNS=''
fi

# 7) Run review on the staged diff with Tier A deterministic verification. Only
#    CRITICAL + WARNING (project convention). docs/rules/ holds the compact
#    binding-rule checklists; missing files are silently skipped by kimi-review,
#    so passing names freely is safe.
if [ -n "$PATTERNS" ]; then
  REVIEW=$(git diff --cached | kimi-review \
    --scope "staged for commit" \
    --profile plant_id \
    --rules "$PATTERNS" \
    --verify deterministic \
    --tiers CRITICAL,WARNING 2>&1)
else
  REVIEW=$(git diff --cached | kimi-review \
    --scope "staged for commit" \
    --profile plant_id \
    --verify deterministic \
    --tiers CRITICAL,WARNING 2>&1)
fi
REVIEW_STATUS=$?

# 8) Block only on the engine's blocking exit code (2 = a CRITICAL survived
#    verification). The engine emits structured findings and owns the blocking
#    decision, so the hook no longer parses prose. Any other non-zero exit is a
#    tool error (timeout, missing key) which falls through to additionalContext
#    (fail-open) rather than blocking.
if [ "$REVIEW_STATUS" -eq 2 ]; then
  REASON=$(printf 'kimi-review blocked the commit — verified CRITICAL finding present.\n\n%s\n\n%s' \
    "${PATTERNS:+rules: $PATTERNS}" \
    "$REVIEW")
  jq -n --arg reason "$REASON" \
    '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$reason}}'
  exit 0
fi

# 9) No CRITICAL — surface review (including any WARNING) as additionalContext.
jq -n --arg r "$REVIEW" --arg p "$PATTERNS" \
  '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":((if ($p | length) > 0 then "kimi-review rules: " + $p + "\n" else "" end) + "kimi-review findings (WARNING is non-blocking; CRITICAL would have blocked):\n" + $r)}}' \
  2>/dev/null || true
exit 0
