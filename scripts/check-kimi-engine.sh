#!/usr/bin/env bash
# Drift check: vendored scripts/kimi-review must match the canonical engine
# (modulo the shebang line). Skips silently when the canonical is absent (CI,
# other machines); enforces when present (developer machines).
set -euo pipefail

CANON="${KIMI_ENGINE_CANONICAL:-$HOME/.local/share/claude-coworker/tools/kimi-review}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDORED="$REPO_ROOT/scripts/kimi-review"

if [ ! -f "$CANON" ]; then
  echo "[kimi:engine:check] canonical engine absent — skipping drift check."
  exit 0
fi

# Temp files, not `diff <(…) <(…)`: process substitution needs /dev/fd, which the
# Claude Code sandbox blocks, and that made this check report a false STALE for
# every sandboxed commit (memory: project_sandbox_devfd_false_stale_kimi).
CANON_BODY=""
VENDORED_BODY=""
trap 'rm -f "$CANON_BODY" "$VENDORED_BODY"' EXIT
CANON_BODY=$(mktemp "${TMPDIR:-/tmp}/kimi-engine.XXXXXX") || {
  echo "[kimi:engine:check] cannot create temp files in ${TMPDIR:-/tmp}; engine NOT checked." >&2
  exit 1
}
VENDORED_BODY=$(mktemp "${TMPDIR:-/tmp}/kimi-engine.XXXXXX") || {
  echo "[kimi:engine:check] cannot create temp files in ${TMPDIR:-/tmp}; engine NOT checked." >&2
  exit 1
}
tail -n +2 "$CANON" > "$CANON_BODY"
tail -n +2 "$VENDORED" > "$VENDORED_BODY"
if cmp -s "$CANON_BODY" "$VENDORED_BODY"; then
  echo "[kimi:engine:check] vendored scripts/kimi-review matches canonical."
  exit 0
fi

echo "[kimi:engine:check] scripts/kimi-review is STALE vs canonical." >&2
echo "Run 'bash scripts/sync-kimi-engine.sh' and commit the result." >&2
exit 1
