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

# 6) Map staged files to docs/rules/ domains
PATTERNS=''
add_pattern() {
  case ",$PATTERNS," in
    *,$1,*) ;;
    *) PATTERNS="${PATTERNS:+$PATTERNS,}$1" ;;
  esac
}

while IFS= read -r file; do
  # Directory/file-role classification — first match wins per file.
  case "$file" in
    backend/apps/blog/*)
      add_pattern wagtail; add_pattern api; add_pattern security ;;
    backend/apps/forum/*|backend/apps/forum_host/*|backend/packages/wagtail_forum/*)
      add_pattern forum; add_pattern wagtail; add_pattern security ;;
    */migrations/*)
      add_pattern database; add_pattern security ;;
    */serializers.py)
      add_pattern api ;;
    */tasks.py|*celery*|*/beat*.py)
      add_pattern celery ;;
    */views.py|*/viewsets.py|*/api/*.py|*/permissions.py)
      add_pattern api; add_pattern security ;;
    */models.py)
      add_pattern database; add_pattern security ;;
    */cache*.py|*/signals.py)
      add_pattern caching ;;
    backend/*.py)
      add_pattern api; add_pattern security; add_pattern database; add_pattern caching ;;
    firebase/*|*firebase*)
      add_pattern firebase; add_pattern security ;;
    web/src/*.tsx)
      add_pattern react; add_pattern typescript ;;
    web/src/*.ts)
      add_pattern typescript ;;
    plant_community_mobile/*.dart)
      add_pattern flutter ;;
  esac
  # Extension/test classification — additive, runs for every file.
  case "$file" in
    *test_*.py|*_test.py|*/tests/*|*.test.ts|*.test.tsx|*.spec.ts|*.spec.tsx)
      add_pattern testing ;;
  esac
done <<< "$FILES"

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
