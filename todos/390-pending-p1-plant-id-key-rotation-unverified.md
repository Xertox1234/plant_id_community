---
status: pending
priority: p1
issue_id: "390"
tags: [security, incident-response, verification, todo-hygiene]
dependencies: []
---

# Plant.id key rotation was never verified, and the todo that would have caught it was archived as done

## Problem

The Plant.id API key exposed in the 2025-10-23 git-history incident has never
been confirmed rotated. The todo whose entire purpose was to confirm it —
`todos/archive/005-completed-p1-api-key-rotation-verification.md` — is filed
under `archive/` with `completed` in its filename while its own frontmatter says
`status: ready` and every acceptance criterion is unchecked. The key literal is
still present in seven tracked files of a **public** repository.

## Findings

Discovered 2026-09-13 while reviewing PR #748; surfaced by the `scan-api-keys`
pre-commit hook, which warns but does not block.

- `todos/archive/005-completed-p1-api-key-rotation-verification.md` — filename
  says `completed`, frontmatter says `status: ready`, 7 unchecked ACs including
  `- [ ] Plant.id key rotation verified or completed`. The rotation date is still
  the literal template `✅ Plant.id API key rotated on: [DATE]`. Plant.id entry
  reads `Status: Unknown`. Its own words: *"Keys still work in git history until
  rotated on external services."*
- Incident: 2025-10-23. Keys exposed across 5 commits
  (`e43a7e1 763028f 0eff76f f54e282 0794d26`); removed from code in `ba256af`.
  **Removal is not rotation.**
- The Plant.id literal (50 chars, high entropy) appears in **7 tracked files**.
  All 5 `PLANT_ID_API_KEY=` occurrences are the same value — fingerprinted by
  hashing each match, not compared by eye:
  - `backend/docs/development/SECURITY_PATTERNS_CODIFIED.md` (×3)
  - `backend/docs/patterns/security/secret-management.md` (locate with
    `grep -n 'export PLANT_ID_API_KEY=' <file>` — deliberately not a line
    number, since PR #748 edits this same file and would shift it)
  - `backend/docs/development/SECURITY_INCIDENT_2025_10_23_API_KEYS.md`
  - `docs/archive/2025-10/completions/COMPREHENSIVE_AUDIT_SUMMARY.md`
  - `docs/archive/2025-11/KEY_ROTATION_INSTRUCTIONS.md`
  - `todos/archive/005-completed-p1-api-key-rotation-verification.md`
  - `todos/archive/2025-10-28-parallel-resolution/035-resolved-p1-insecure-development-secrets.md`
    — which lists it under **"Current insecure values"** with stated impact
    *"API quota exhaustion from exposed keys"* and *"Financial impact from key
    abuse"*.
- **PlantNet was almost certainly rotated**: the documented value is 24
  characters, the live Railway value is 26. Different length, different key.
- **Plant.id cannot be distinguished by length**: documented 50, live 50, and
  Plant.id keys are fixed-length. Only a direct comparison settles it.
- It is not in `.secrets.baseline` — that file records four entries for
  `secret-management.md` and none of them is this literal — so detect-secrets
  passes it. The custom
  `scan-api-keys` hook flags it as a non-blocking `WARNING`, which is how it
  survived ~10 months.

### Why an agent could not close this

Comparing the doc literal against the live Railway value is refused by the
auto-mode classifier — fetching a production secret and hashing it is
indistinguishable from exfiltration, regardless of intent. **That block is
correct; do not route around it.** Reading the live value's *length* and testing
substrings locally IS permitted, and is how PR #748's `INSECURE_PATTERNS` check
was cleared. This item needs a human with plant.id account access.

### The class of mistake, and what it already cost

27 of 340 archived todos have a filename claiming completion while the
frontmatter disagrees — but **26 are bookkeeping noise**. Spot-checked three of
the most alarming and all are genuinely implemented:
`CSRF_COOKIE_HTTPONLY = True` (settings.py:1250), the security headers
(`SECURE_BROWSER_XSS_FILTER`, `SECURE_CONTENT_TYPE_NOSNIFF`,
`X_FRAME_OPTIONS = "DENY"`, `SECURE_HSTS_SECONDS`, settings.py:1180-1204), and
Vite on port 5174 (`web/vite.config.ts:25`).

The dangerous ones are todos whose deliverable is an **external verification**.
They leave no artifact in the repo, so the unchecked box is the only record and
nothing can confirm them later. Todo 005 is one.

So is `backend/todos/archive/2025-11-01-003-resolved-p1-env-example-secret-placeholders.md`
— `status: pending`, 6 unchecked ACs, archived as "resolved". Its subject is
`.env.example` placeholder quality. **Ten months later todo 367 / PR #748 had to
rediscover the same problem**, by which point `JWT_SECRET_KEY`'s 66-character
placeholder was *accepted in production and signing every JWT* (it cleared
set / `!= SECRET_KEY` / `len >= 50`). That is the concrete price of archiving a
security todo without doing it.

## Recommended Action

1. **Verify the key** (human, needs plant.id account):

   ```bash
   # prints only a verdict, never either secret
   python3 - <<'PY'
   import re, pathlib, subprocess, json
   doc = pathlib.Path("backend/docs/patterns/security/secret-management.md").read_text()
   lit = re.search(r'PLANT_ID_API_KEY[ ]*=[ ]*([A-Za-z0-9]{40,})', doc).group(1)
   live = json.loads(subprocess.run(
       ["railway","variables","--service","plant_id_community","--json"],
       capture_output=True, text=True).stdout)["PLANT_ID_API_KEY"]
   print("MATCH — the committed literal IS the live key" if lit == live
         else "no match — the committed literal is a dead key")
   PY
   ```

2. **If it matches**: rotate at <https://web.plant.id/>, update the Railway
   variable on `plant_id_community` (and `forum-prune-cron` if set there), then
   scrub the literal from the 7 files. Deleting the files is **not** sufficient —
   the value is in 5 commits of history, which is why rotation is the fix.
3. **If it does not match**: the literal is a dead key. Still scrub it, so the
   next reader does not repeat this investigation.
4. **Close the hygiene gap** so a verification todo cannot be archived on vibes
   again — see AC 4-6 below.

## Technical Details

- `completing-todos` skill: `.claude/skills/completing-todos/`
- The filename/frontmatter rule already exists and is stated in
  `todos/TEMPLATE.md`: *"The filename status segment MUST match the frontmatter
  status value."* Nothing enforces it.
- A detector for the mismatch is ~15 lines: walk `todos/archive/**` and
  `backend/todos/archive/**`, match `-(complete|completed|resolved|done)-` in the
  filename, compare against `^status:`. It found the 27 above.
- Related: `backend/docs/patterns/security/secret-management.md`,
  `docs/archive/2025-11/KEY_ROTATION_INSTRUCTIONS.md`.

## Acceptance Criteria

- [ ] The committed Plant.id literal has been compared against the live key, and
      the verdict is recorded **in this file** with the date
- [ ] If it matched: key rotated at plant.id, Railway variable updated, and a
      post-rotation call confirmed working
- [ ] The literal is removed from all 7 tracked files (or, if it is a dead key,
      replaced with an obvious placeholder and annotated as rotated-out)
- [ ] A check fails when an archived todo's filename claims completion but its
      frontmatter status disagrees — the 26 known bookkeeping-only mismatches
      either fixed or explicitly allowlisted, so the check starts green
- [ ] `completing-todos` refuses to archive a todo with unchecked ACs unless each
      is re-pointed with a reason (the existing convention for moved findings)
- [ ] A todo whose AC is an external verification must carry the evidence
      (date + observed result) in-file before it can be archived — documented in
      `todos/TEMPLATE.md` and the `completing-todos` skill

## Work Log

### 2026-09-13 - Filed

- Found while reviewing PR #748 (todo 367). The `scan-api-keys` hook warned on
  `secret-management.md`; the 50-char literal did not look like the placeholders
  around it.
- Established without prod access: 5 identical occurrences by fingerprint, 7
  tracked files total, PlantNet length mismatch (24 vs 26) implying it was
  rotated, Plant.id length match (50 vs 50) implying nothing either way.
- Two attempts to compare against the live value were refused by the auto-mode
  classifier. Not routed around; handed to the user instead.
- Nothing about the nine open sweep PRs (#743–#751) depends on this; all nine are
  green and unaffected.

## Notes

**Priority rationale: p1.** A live API key in a public repository is exploitable
now, and the free-tier limit (100 IDs/month) means abuse is also a
denial-of-service against the product's core feature. Downgrade to p3 the moment
the comparison shows the literal is a dead key — at that point only the cleanup
and the hygiene ACs remain.

The two halves are separable. If the key turns out to be dead, split ACs 4-6 into
their own p3 rather than leaving this p1 open on process work.

Related: todo 367 / PR #748 (the rediscovered placeholder problem), todo 355
(the security epic), `todos/archive/005-completed-p1-api-key-rotation-verification.md`,
`backend/todos/archive/2025-11-01-003-resolved-p1-env-example-secret-placeholders.md`.
