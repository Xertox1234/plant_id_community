#!/usr/bin/env bash
# PreToolUse hook — inject relevant binding rules before Edit/Write/MultiEdit.
# Reads tool event JSON from stdin; outputs additionalContext JSON or exits 0 silently.
# Rules live in docs/rules/<domain>.md (short by design). Long-form detail stays
# in the per-stack */docs/patterns/ libraries — this hook only surfaces the
# compact checklists plus a discipline preamble.
#
# Just-in-time mistake injection — injects domain rules + matched recurring-mistake
# warnings before Edit/Write. Features: kill switch, deduped domain rules, triggers.
# Tests: .claude/hooks/test-inject-patterns.sh
set -uo pipefail

# (1) Kill switch: instant disable with no commit (mirrors SKIP_KIMI_REVIEW=1).
[[ -n "${INJECT_PATTERNS_DISABLE:-}" ]] && exit 0

INPUT=$(cat)

TOOL_NAME=$(printf '%s' "$INPUT" | jq -re '.tool_name' 2>/dev/null) || exit 0
FILE_PATH=$(printf '%s' "$INPUT" | jq -re '.tool_input.file_path' 2>/dev/null) || exit 0

[[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "MultiEdit" ]] || exit 0

# session_id drives per-session dedup of the domain-rule tier (confirmed
# PreToolUse stdin field). Empty on parse failure → dedup disabled (always inject).
SESSION_ID=$(printf '%s' "$INPUT" | jq -re '.session_id' 2>/dev/null) || SESSION_ID=""

# Resolve paths relative to project root (two levels up from .claude/hooks/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RULES_DIR="$PROJECT_ROOT/docs/rules"

# Normalize to a repo-relative path so the matchers below are uniform whether
# the Edit tool sent an absolute path or a relative one. A leading "/" is
# stripped only when the path is under PROJECT_ROOT; paths outside it are left
# as-is and simply fall through to no domain match.
REL="${FILE_PATH#"$PROJECT_ROOT"/}"

# Map file path to domains. Independent if-blocks so multiple rows can match.
DOMAINS=""
add_domain() {
  case ",$DOMAINS," in
    *,"$1",*) ;;
    *) DOMAINS="${DOMAINS:+$DOMAINS,}$1" ;;
  esac
}

[[ "$REL" == backend/apps/blog/* ]] && \
  { add_domain wagtail; add_domain api; add_domain security; }

[[ "$REL" == */migrations/* ]] && \
  { add_domain database; add_domain security; }

[[ "$REL" == */serializers.py ]] && add_domain api

[[ "$REL" == */tasks.py || "$REL" == *celery* || "$REL" == */beat*.py ]] && \
  add_domain celery

[[ "$REL" == */views.py || "$REL" == */viewsets.py || \
   "$REL" == */permissions.py ]] && \
  { add_domain api; add_domain security; }

[[ "$REL" == */models.py ]] && { add_domain database; add_domain security; }

[[ "$REL" == */cache*.py || "$REL" == */signals.py ]] && add_domain caching

# Generic backend Python catch-all (only if nothing more specific matched).
if [ -z "$DOMAINS" ]; then
  [[ "$REL" == backend/*.py ]] && \
    { add_domain api; add_domain security; add_domain database; }
fi

[[ "$REL" == firebase/* || "$REL" == *firebase* ]] && \
  { add_domain firebase; add_domain security; }

[[ "$REL" == *.dart ]] && add_domain flutter

[[ "$REL" == web/src/*.tsx ]] && { add_domain react; add_domain typescript; }

# Test files accumulate the testing domain regardless of enclosing directory.
[[ "$REL" == */tests/* || "$REL" == *test_*.py || "$REL" == *_test.py || \
   "$REL" == *.test.ts || "$REL" == *.test.tsx || \
   "$REL" == *.spec.ts || "$REL" == *.spec.tsx ]] && \
  add_domain testing

# typescript fallback for .ts/.tsx files when no more-specific domain matched.
if [ -z "$DOMAINS" ]; then
  case "$REL" in
    *.ts|*.tsx) add_domain typescript ;;
  esac
fi

# Build context in a temp file (avoids subshell newline stripping)
TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT

printf '=== Pre-write context for %s ===\n' "$FILE_PATH" >> "$TMPFILE"

# (2) Always-on discipline floor, read from an editable data file. Never deduped.
printf '\n' >> "$TMPFILE"
cat "$RULES_DIR/_discipline.md" >> "$TMPFILE" 2>/dev/null

# (3) Content-matched recurring-mistake warnings. Fires only on a real match;
# can never break the hook's JSON (stderr discarded, non-zero exit absorbed,
# final output escaped by jq --arg below).
MATCH_OUT=""
if command -v python3 >/dev/null 2>&1; then
  MATCH_OUT=$(printf '%s' "$INPUT" \
    | python3 "$PROJECT_ROOT/scripts/inject/match_triggers.py" 2>/dev/null) \
    || MATCH_OUT=""
fi
if [ -n "$MATCH_OUT" ]; then
  printf '\n[RECENT MISTAKES — matched this edit]\n%s\n' "$MATCH_OUT" >> "$TMPFILE"
fi

# (4) Domain-rule checklists, deduped once per session per domain.
if [ -n "$DOMAINS" ]; then
  IFS=',' read -ra DOMAIN_LIST <<< "$DOMAINS"
  for DOMAIN in "${DOMAIN_LIST[@]}"; do
    RULES_FILE="$RULES_DIR/${DOMAIN}.md"
    [ -f "$RULES_FILE" ] || continue
    MARKER=""
    if [ -n "$SESSION_ID" ]; then
      SAFE_ID=$(printf '%s' "$SESSION_ID" | tr -c 'A-Za-z0-9._-' '_')
      MARKER="/tmp/inject-${SAFE_ID}-${DOMAIN}"
      [ -f "$MARKER" ] && continue
    fi
    printf '\n[RULES — %s]\n' "$DOMAIN" >> "$TMPFILE"
    cat "$RULES_FILE" >> "$TMPFILE"
    [ -n "$MARKER" ] && : > "$MARKER" 2>/dev/null || true
  done
fi

# Spill overflow to a per-invocation temp file so the agent can read the rest.
# Claude Code's hook-output cap is ~10K; multi-domain injections can exceed this.
# The `$$` PID suffix keeps concurrent hook invocations from clobbering each
# other's spill file.
THRESHOLD=9000
SPILL_FILE="/tmp/plant-id-injection-context.$$.md"
CONTEXT_SIZE=$(wc -c < "$TMPFILE")
if [ "$CONTEXT_SIZE" -gt "$THRESHOLD" ]; then
  cp "$TMPFILE" "$SPILL_FILE"
  head -c 8800 "$TMPFILE" > "${TMPFILE}.trunc"
  mv "${TMPFILE}.trunc" "$TMPFILE"
  printf '\n\n[TRUNCATED — %d bytes total. Full rule context written to %s. Read that file for the rest before editing.]\n' \
    "$CONTEXT_SIZE" "$SPILL_FILE" >> "$TMPFILE"
fi

CONTEXT=$(cat "$TMPFILE")
jq -n --arg ctx "$CONTEXT" \
  '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":$ctx}}'
