#!/usr/bin/env bash
# Tests for inject-patterns.sh — run from anywhere.
# Requires docs/rules/<domain>.md files to exist (the hook only emits a
# [RULES — domain] block when the corresponding file is present).
set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/inject-patterns.sh"
SPILL_FILE="/tmp/plant-id-injection-context.md"
PASS=0; FAIL=0

run_hook() {
  local input="$1"
  rm -f "$SPILL_FILE"
  local output spill=""
  output=$(echo "$input" | bash "$HOOK" 2>/dev/null || true)
  [ -f "$SPILL_FILE" ] && spill=$(cat "$SPILL_FILE")
  printf '%s\n%s' "$output" "$spill"
}

check() {
  local name="$1" input="$2" pattern="$3" combined
  combined=$(run_hook "$input")
  if echo "$combined" | grep -q "$pattern"; then
    echo "PASS: $name"; PASS=$((PASS + 1))
  else
    echo "FAIL: $name"; echo "  expected to find: $pattern"; FAIL=$((FAIL + 1))
  fi
}

check_no_match() {
  local name="$1" input="$2" pattern="$3" combined
  combined=$(run_hook "$input")
  if echo "$combined" | grep -q "$pattern"; then
    echo "FAIL: $name (expected NOT to find: $pattern)"; FAIL=$((FAIL + 1))
  else
    echo "PASS: $name"; PASS=$((PASS + 1))
  fi
}

check_empty() {
  local name="$1" input="$2" output
  rm -f "$SPILL_FILE"
  output=$(echo "$input" | bash "$HOOK" 2>/dev/null || true)
  if [ -z "$output" ]; then
    echo "PASS: $name"; PASS=$((PASS + 1))
  else
    echo "FAIL: $name (expected empty)"; echo "  got: $(echo "$output" | head -3)"; FAIL=$((FAIL + 1))
  fi
}

# blog → wagtail + api + security
check "blog models → wagtail rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/blog/models.py"}}' \
  "RULES — wagtail"

# migrations → database + security
check "migration → database rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/plant_identification/migrations/0001_initial.py"}}' \
  "RULES — database"

check "migration → security rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/plant_identification/migrations/0001_initial.py"}}' \
  "RULES — security"

# serializers → api
check "serializers → api rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/forum/serializers.py"}}' \
  "RULES — api"

# views → api + security
check "views → api rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/users/views.py"}}' \
  "RULES — api"

check "views → security rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/users/views.py"}}' \
  "RULES — security"

# tasks → celery
check "tasks → celery rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/blog/tasks.py"}}' \
  "RULES — celery"

# React component → react + typescript
check "web component → react rules" \
  '{"tool_name":"Write","tool_input":{"file_path":"web/src/components/BlogCard.tsx"}}' \
  "RULES — react"

# Plain .ts → typescript fallback
check "web .ts → typescript fallback" \
  '{"tool_name":"Edit","tool_input":{"file_path":"web/src/lib/api.ts"}}' \
  "RULES — typescript"

# Flutter → flutter
check "dart file → flutter rules" \
  '{"tool_name":"Write","tool_input":{"file_path":"plant_community_mobile/lib/main.dart"}}' \
  "RULES — flutter"

# Test file → testing (additive)
check "backend test file → testing rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/forum/tests/test_views.py"}}' \
  "RULES — testing"

# Output is valid JSON
check "output is valid JSON with hookSpecificOutput" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/users/views.py"}}' \
  "hookSpecificOutput"

# Discipline preamble always emitted for Edit/Write
check "non-domain file → discipline preamble emitted" \
  '{"tool_name":"Edit","tool_input":{"file_path":"README.md"}}' \
  "DISCIPLINE"

check_no_match "non-domain file → no RULES blocks" \
  '{"tool_name":"Edit","tool_input":{"file_path":"README.md"}}' \
  "RULES — "

# Read tool → no output (not Edit/Write/MultiEdit)
check_empty "Read tool → no output" \
  '{"tool_name":"Read","tool_input":{"file_path":"backend/apps/users/views.py"}}'

# Missing file_path → no output
check_empty "missing file_path → no output" \
  '{"tool_name":"Edit","tool_input":{}}'

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
