#!/usr/bin/env bash
# Tests for format-on-edit.sh — run from anywhere.
# Builds a throwaway fake repo root (FORMAT_ON_EDIT_ROOT) so no real file is
# ever touched. Requires ruff (backend/venv/bin/ruff) and jq on the system.
set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/format-on-edit.sh"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REAL_RUFF="$REPO_ROOT/backend/venv/bin/ruff"
PASS=0; FAIL=0

# The hook fail-opens without ruff, so there is nothing to assert if it is absent.
[ -x "$REAL_RUFF" ] || { echo "SKIP: ruff not installed at $REAL_RUFF (run: backend/venv/bin/pip install -r backend/requirements.txt)"; exit 0; }

# Throwaway fake repo root (FORMAT_ON_EDIT_ROOT) so no real file is touched, and
# the ruff test seam (FORMAT_ON_EDIT_RUFF) so resolution is deterministic.
ROOT="$(mktemp -d)"
export FORMAT_ON_EDIT_RUFF="$REAL_RUFF"
trap 'chmod -R u+w "$ROOT" 2>/dev/null; rm -rf "$ROOT"' EXIT

mkfixture() { # path-under-root, content
  local p="$ROOT/$1"; mkdir -p "$(dirname "$p")"; printf '%b' "$2" > "$p"
}
run() { # file_path (repo-relative), tool_name → runs hook, sets RC/ERR
  local fp="$1" tool="${2:-Edit}"
  ERR=$(printf '{"tool_name":"%s","tool_input":{"file_path":"%s"}}' "$tool" "$fp" \
        | FORMAT_ON_EDIT_ROOT="$ROOT" bash "$HOOK" 2>&1 >/dev/null); RC=$?
}
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
no()   { echo "FAIL: $1"; echo "  $2"; FAIL=$((FAIL+1)); }

# 1. Core: unused import in a normal backend file is auto-removed.
mkfixture backend/apps/scratch.py 'import os\nimport sys\n\nprint(sys.version)\n'
run backend/apps/scratch.py
if ! grep -q '^import os$' "$ROOT/backend/apps/scratch.py" && grep -q 'import sys' "$ROOT/backend/apps/scratch.py"; then
  ok "removes unused import, keeps used one"
else
  no "removes unused import, keeps used one" "file still: $(tr '\n' ' ' < "$ROOT/backend/apps/scratch.py")"
fi

# 2. Skip-list: a per-file-ignore path is left untouched (intentional re-exports).
mkfixture backend/apps/plant_identification/models.py 'import os\n'
run backend/apps/plant_identification/models.py
if grep -q '^import os$' "$ROOT/backend/apps/plant_identification/models.py" && [ "$RC" -eq 0 ]; then
  ok "skip-list file untouched"
else
  no "skip-list file untouched" "rc=$RC content=$(cat "$ROOT/backend/apps/plant_identification/models.py")"
fi

# 3. Non-.py file is ignored.
mkfixture backend/notes.txt 'import os\n'
run backend/notes.txt
[ "$RC" -eq 0 ] && grep -q 'import os' "$ROOT/backend/notes.txt" && ok "non-.py ignored" || no "non-.py ignored" "rc=$RC"

# 4. Non-backend .py is ignored (gate scopes to backend/).
mkfixture web/scripts/foo.py 'import os\n'
run web/scripts/foo.py
[ "$RC" -eq 0 ] && grep -q 'import os' "$ROOT/web/scripts/foo.py" && ok "non-backend .py ignored" || no "non-backend .py ignored" "rc=$RC"

# 5. Missing file_path (e.g. Read-style event) → no-op, exit 0.
ERR=$(printf '{"tool_name":"Edit","tool_input":{}}' | FORMAT_ON_EDIT_ROOT="$ROOT" bash "$HOOK" 2>&1 >/dev/null); RC=$?
[ "$RC" -eq 0 ] && ok "missing file_path → exit 0" || no "missing file_path → exit 0" "rc=$RC"

# 6. Fail-open: ruff absent (seam points at a nonexistent path) → exit 0, untouched.
mkfixture backend/apps/failopen.py 'import os\n'
ERR=$(printf '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/failopen.py"}}' \
      | FORMAT_ON_EDIT_RUFF="$ROOT/no-such-ruff" FORMAT_ON_EDIT_ROOT="$ROOT" bash "$HOOK" 2>&1 >/dev/null); RC=$?
[ "$RC" -eq 0 ] && grep -q 'import os' "$ROOT/backend/apps/failopen.py" && ok "ruff missing → fail-open exit 0" || no "ruff missing → fail-open exit 0" "rc=$RC"

# 7. Residual F401 (read-only DIR blocks ruff's atomic-rename fix; report still
#    works) → exit 2 + stderr. A read-only file alone fails: ruff rewrites via the
#    parent dir, so the dir must be unwritable.
mkdir -p "$ROOT/backend/apps/ro"
mkfixture backend/apps/ro/locked.py 'import os\n'
chmod 555 "$ROOT/backend/apps/ro"
run backend/apps/ro/locked.py
chmod u+w "$ROOT/backend/apps/ro"
if [ "$RC" -eq 2 ] && printf '%s' "$ERR" | grep -qi 'F401\|unused'; then
  ok "unfixable F401 → exit 2 with feedback"
else
  no "unfixable F401 → exit 2 with feedback" "rc=$RC err=$ERR"
fi

echo "----"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
