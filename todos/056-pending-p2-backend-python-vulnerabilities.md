---
status: pending
priority: p2
issue_id: "056"
tags: [security, backend, python, dependencies, ci]
dependencies: []
---

# Resolve Backend Python Dependency Vulnerabilities

## Problem

The `Backend Python Security Scan` job in `.github/workflows/security-scan.yml` runs `safety check -r backend/requirements.txt` and has been failing on `main` for some time. The failure pre-dates PR #251 and is unrelated to its content (PR #251 only touches agent prompts and docs), but it leaves `main`'s CI in a permanent red state and masks any new vulnerabilities that might land.

The companion `Security Scan Summary` job rolls this failure up, so two checks fail on every PR until this is resolved.

## Findings

Discovered during merge of PR #251, run [25508486985](https://github.com/Xertox1234/plant_id_community/actions/runs/25508486985).

### Vulnerable packages flagged by Safety

The `--bare` output (no per-CVE detail) listed these six packages:

```
pygments pyasn1 pytest nltk marshmallow markdown
```

These are mostly transitive dependencies — `pygments` (syntax highlighting, often pulled in by docs/admin tooling), `pyasn1` (cryptography helper), `pytest` (test runner), `nltk` (Wagtail content tooling pulls it via `wagtail-airtable` or similar), `marshmallow` (likely transitive via `safety` itself), `markdown` (rendering). Run `safety scan -r backend/requirements.txt --output json` locally for current CVE IDs and fix versions before pinning.

### Workflow uses deprecated Safety command

The job runs `safety check`, which has been deprecated since 2024-06-01:

> DEPRECATED: this command (`check`) has been DEPRECATED, and will be unsupported beyond 01 June 2024. We highly encourage switching to the new `scan` command.

The deprecation message is printed alongside results on every run, adding noise. `safety scan` is the supported replacement.

### Bot permissions issue (separate)

The `Comment PR with vulnerabilities (if any)` step also fails with `Resource not accessible by integration` — the workflow's GITHUB_TOKEN lacks `pull-requests: write` permission, so the auto-comment never lands. This is a workflow config bug, not a vuln.

## Recommended Action

1. **Triage the six packages.** Run `safety scan -r backend/requirements.txt --output json` locally (or in a fresh CI run with the upgraded command) to map each flagged package to its CVE(s), severity, affected versions, and fix versions.
2. **Bump direct deps where possible.** Some of these (`pytest`, `markdown`) may be direct entries in `requirements.txt` or `requirements-dev.txt` and can be updated in place.
3. **For transitive deps**, decide between (a) pinning a safe version explicitly in `requirements.txt`, (b) updating the parent package, or (c) accepting + suppressing if no fix exists.
4. **Migrate workflow to `safety scan`** in `.github/workflows/security-scan.yml`. The `scan` command supports the same JSON output and exit codes; mostly a verb swap.
5. **Add `pull-requests: write` to the workflow's permissions block** so the auto-comment step works (or remove the step if not desired).
6. **Verify on a follow-up PR** that the `Backend Python Security Scan` job goes green.

## Technical Details

Key files:
- `backend/requirements.txt` — direct dependencies
- `backend/requirements-dev.txt` — dev-only direct dependencies
- `.github/workflows/security-scan.yml` — Safety scan job + permissions

Reference run: https://github.com/Xertox1234/plant_id_community/actions/runs/25508486985

## Out of Scope

- Frontend (`Frontend npm Security Scan`) and Mobile (`Flutter Dependency Security Check`) jobs are passing (0 vulnerabilities). This todo covers only the backend Python pipeline.
