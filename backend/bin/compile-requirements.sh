#!/usr/bin/env bash
# Compile requirements.in -> requirements.txt and requirements-dev.in ->
# requirements-dev.txt with pip-tools (todo 708). The ONE way the locks are
# written: CI's backend-checks job runs this script and fails when either lock
# differs from what it produces, so a hand edit of a .txt file cannot merge.
#
# pip-compile keeps every pin already in the lock that still satisfies the .in
# files, so re-running it changes nothing. To take an upgrade, pass pip-tools'
# own flags through, e.g. `bash bin/compile-requirements.sh --upgrade-package
# django`, then re-run without flags to settle the dev lock.
#
# Needs pip-tools on PYTHON (default `python`); it is pinned in
# requirements-dev.txt. Network access to PyPI is required.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python}"

# The header names this script, not the pip-compile command line, so the
# output is the same whoever runs it and from wherever.
export CUSTOM_COMPILE_COMMAND="bash bin/compile-requirements.sh"

# --strip-extras writes `uvicorn==x`, not `uvicorn[standard]==x` (the extra's
# packages are pinned on their own lines), which is pip-tools 8's default.
# --allow-unsafe pins setuptools/pip when something depends on them instead of
# leaving them unpinned under a comment. No --generate-hashes: the editable
# wagtail_forum line cannot be hashed (owner decision 2026-11-17).
common=(--quiet --strip-extras --allow-unsafe --no-emit-index-url --resolver=backtracking)

# pip-compile writes the editable line as an absolute file:// URL of THIS
# checkout. Put the relative path back, so the lock is the same on every
# machine (and names no home directory in a public repo).
relativise() {
    local here
    for here in "$(pwd -P)" "$PWD"; do
        sed -i.bak "s#^-e file://${here}/packages/#-e ./packages/#" "$1"
    done
    rm -f "$1.bak"
}

# Production lock first: the dev lock reads it (`-r requirements.txt`).
"$PYTHON" -m piptools compile "${common[@]}" "$@" \
    --output-file=requirements.txt requirements.in
relativise requirements.txt
"$PYTHON" -m piptools compile "${common[@]}" "$@" \
    --output-file=requirements-dev.txt requirements-dev.in
relativise requirements-dev.txt
