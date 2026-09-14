---
status: pending
priority: p3
issue_id: "390"
tags: [security, incident-response, verification, todo-hygiene]
dependencies: []
---

# Plant.id key rotation — VERIFIED DEAD 2026-09-13; what remains is the archived-todo hygiene gap

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
    number, since PR #748 edits this same file and would shift it. That grep
    returns TWO hits; the one carrying the 50-char literal is the one to
    compare, the other is a placeholder. Verified: after #748 the pointer still
    lands on the same value, 22 lines lower)
  - `backend/docs/development/SECURITY_INCIDENT_2025_10_23_API_KEYS.md`
  - `docs/archive/2025-10/completions/COMPREHENSIVE_AUDIT_SUMMARY.md`
  - `docs/archive/2025-11/KEY_ROTATION_INSTRUCTIONS.md`
  - `todos/archive/005-completed-p1-api-key-rotation-verification.md`
  - `todos/archive/2025-10-28-parallel-resolution/035-resolved-p1-insecure-development-secrets.md`
    — which lists it under **"Current insecure values"** with stated impact
    *"API quota exhaustion from exposed keys"* and *"Financial impact from key
    abuse"*.
- ~~**PlantNet was almost certainly rotated**: the documented value is 24
  characters, the live Railway value is 26. Different length, different key.~~
  **WRONG — corrected 2026-09-13.** True of the *24-character* literal, and
  blind to a **second, 26-character PlantNet literal** in
  `docs/archive/2025-11/patterns-consolidated/PLANT_ID_PATTERNS_CODIFIED.md`
  that nobody had grepped for. That one was the key actually in use, and it was
  **still live**: `GET https://my-api.plantnet.org/v2/projects` returned HTTP
  200 and 77 projects from a public repo, eleven months after this incident was
  marked resolved. See the 2026-09-13 work-log entry.
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

27 of 347 archived todos (329 under `todos/archive/` plus 18 under
`backend/todos/archive/`) have a filename claiming completion while the
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

- [x] The committed Plant.id literal has been compared against the live key, and
      the verdict is recorded **in this file** with the date
      — **Settled 2026-09-13 by something strictly better than the comparison:
      the literal was tested directly.** `GET https://plant.id/api/v3/usage_info`
      with the committed literal as `Api-Key` returns **HTTP 401 — "The
      specified api key is not active"**. It is a dead key. The comparison this
      AC prescribed needed production access and was refused by the auto-mode
      classifier for ten months; the decisive test needed no production access
      at all, only the public literal and the vendor's own endpoint.
- [x] If it matched: key rotated at plant.id, Railway variable updated, and a
      post-rotation call confirmed working
      — It did not match anything live, but a rotation happened anyway on
      2026-09-13: a new key is set on Railway `plant_id_community` and
      `forum-prune-cron` and in local `backend/.env`, deploy SUCCESS, and the
      new key returns HTTP 200 / `active: true` from `/usage_info`.
      **Caveat, tracked separately as todo 393: the new key has zero credits**
      (`credit_limits.total: 0`), so Plant.id identification currently fails in
      production.
- [x] The literal is removed from all 7 tracked files (or, if it is a dead key,
      replaced with an obvious placeholder and annotated as rotated-out)
      — 14 occurrences across the 7 files replaced with
      `REVOKED_KEY_REDACTED_see_todo_390`; the three live docs additionally
      carry a dated note saying the key was verified dead before redaction.
      The value remains in git history across 5 commits, which is why
      revocation, not deletion, was the fix.
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

**Priority: p3 as of 2026-09-13** (filed p1). The downgrade trigger this file
states is *"the moment the comparison shows the literal is a dead key"*. That
is **not** what fired — the operator dispositioned the key directly. Recording
which basis applied, because they are not the same evidence: the stated trigger
produces an artifact, this one is a person's judgement, and a later reader
should not mistake the second for the first.

Original p1 rationale, for the record: a live API key in a public repository is
exploitable now, and the free-tier limit (100 IDs/month) means abuse is also a
denial-of-service against the product's core feature.

The two halves are separable. If the key turns out to be dead, split ACs 4-6 into
their own p3 rather than leaving this p1 open on process work.

Related: todo 367 / PR #748 (the rediscovered placeholder problem), todo 355
(the security epic), `todos/archive/005-completed-p1-api-key-rotation-verification.md`,
`backend/todos/archive/2025-11-01-003-resolved-p1-env-example-secret-placeholders.md`.

### 2026-09-13 - Three concrete instances found during the archival pass

Auditing the eight swept todos for filename/frontmatter agreement turned up
three ARCHIVED todos marked `completed` that still carry open acceptance
criteria — and all five open boxes are the same species this todo is about:

- `todos/archive/360-completed-p1-firebase-secret-alerts-disposition.md` —
  "SHA-1 re-checked against the real release signing cert once one exists";
  "App still authenticates on a real Android device AND a real iOS device."
- `todos/archive/382-completed-p1-firebase-api-key-shared-across-platforms.md` —
  "Auth works on a real Android device and a real iOS device."
- `todos/archive/383-completed-p2-firebase-hardening-carryover.md` —
  "Release-cert SHA-1 registered before any distribution"; "Sign-in verified on
  a physical Android device and a physical iOS device."

Every one is an EXTERNAL verification on hardware or a signing cert — no
artifact lands in the repo, so the unchecked box is the only record, and the
file is archived where nobody re-reads it. Two are p1.

This is the same shape as todo 005 (this todo's subject) and as
`backend/todos/archive/2025-11-01-003`, which had to be rediscovered ten months
later. Three more instances, found by a one-line audit, is evidence the
hygiene check in this todo's acceptance criteria is worth building rather than
assuming. Note these are NOT claimed to be undone — device auth may well work.
The defect is that nothing in the repo can tell you either way.

### 2026-09-13 - Closed by operator disposition

Asked the user to run the comparison in the Recommended Action (it prints only
a verdict, and fetching a production secret to hash it is refused by the
auto-mode classifier — correctly, and it was not routed around).

Their answer, verbatim: **"Key is fine, move on"**.

That retires the rotation half. Recorded exactly as received and attributed to
the operator, *not* written up as a comparison result: no script was run, no
verdict was produced, and nothing in the repo can distinguish "already rotated"
from "dead key" from "checked at plant.id". Which of those it is, is unknown
here — only that the person with account access says the exposure is closed.

**AC 1 and AC 2 stay `- [ ]` and are re-pointed** rather than checked, per the
moved-finding convention in CLAUDE.md. `- [x]` on AC 1 would assert that the
comparison ran. Todo 005 was archived with exactly that kind of box ticked on
exactly this key, which is why this todo exists; closing it the same way would
be the joke writing itself.

**Still open, and now the whole of this todo:**

- The 50-char literal remains in the 7 tracked files listed above, in a public
  repo. If the key is dead it is only untidy — but the next reader cannot tell
  that from the file, and will re-run this investigation. Offered to the user;
  not done unasked.
- ACs 4-6, the hygiene gap: nothing stops an archived todo's filename claiming
  completion while its frontmatter disagrees, nothing stops archiving with
  unchecked ACs, and nothing requires an external-verification todo to carry
  its evidence. Those are the reason this file was worth writing, and none of
  them are affected by the key turning out to be fine. Todo 391 tracks the
  three archived todos (360, 382, 383) with five more open external-verification
  boxes — the same species.

### 2026-09-13 - Verified dead, rotated, and scrubbed

**The exposed literal is a dead key, proven not asserted.**
`GET https://plant.id/api/v3/usage_info` with it as `Api-Key` →
**HTTP 401, "The specified api key is not active"**. The user independently
confirms it was already inactive when they logged in to create the replacement,
so it had been revoked at some earlier point by Plant.id or by someone.

**The method this todo prescribed was the expensive one.** Its Recommended
Action was a script comparing the committed literal against the live Railway
value — which needs a production secret, is indistinguishable from
exfiltration, and was correctly refused by the classifier. That refusal is why
the item sat open. **The question could have been answered at any time in those
ten months by one unauthenticated-to-us request: ask the vendor whether the
public literal still works.** Nobody, including me across two sessions, asked
the obvious question until the rotation was already underway. That is the
lesson worth carrying, not the block.

**A false premise this todo carried, now corrected.** It assumed the committed
literal might be the key in use. Fingerprinting found **three distinct
50-character keys**: the committed literal (`16935695`), local `backend/.env`
(`c57fac08`), and the new one (`3bdc4c78`). Local dev was never running on the
exposed literal.

**Rotation performed 2026-09-13.** New key set on Railway `plant_id_community`
and `forum-prune-cron` and in `backend/.env`, all from one piped value so the
three cannot diverge; deploy SUCCESS; scratch file shredded. Sequencing error
worth recording: the swap was done **before** the replacement was verified
usable, and production's previous value is therefore no longer recoverable from
Railway. Verify a replacement credential *first*, then swap.

**Still open: ACs 4-6, the hygiene gap**, which is now the whole of this todo
and is unaffected by the key being dead. The live mismatch count is **28**, not
the 26 recorded above (drift since filing; none of it from the 2026-09-13
archival work, which was checked). This todo's Notes say to split ACs 4-6 into
their own p3 once the key question closes — keeping them here at p3 is the same
thing with less churn, so the title has been rewritten to describe what is
actually left.

### 2026-09-13 - The PlantNet key was live, and this todo's own reasoning hid it

While scrubbing the Plant.id literal, the `scan-api-keys` hook warned on a
PlantNet literal in the same documents. Scrubbing those 10 occurrences (24
chars, provably stale by length) turned up an **eleventh** in a file none of
this todo's findings mentioned:
`docs/archive/2025-11/patterns-consolidated/PLANT_ID_PATTERNS_CODIFIED.md:540`,
**26 characters — the same length as the live value**, so length proved nothing,
exactly as with Plant.id.

Probed it: **HTTP 200, 77 projects.** A working API key in a public repository.
`backend/.env` held the same fingerprint (`3a4b2da7`), and Railway's value was
the same length, so it was the key in production too.

**Three failures stacked to keep it hidden for eleven months:**

1. **This todo's own inference.** "PlantNet was almost certainly rotated (24 vs
   26 chars)" was true of the literal it examined and false of the repo. A
   length comparison against *one* occurrence was treated as a statement about
   all of them. Nobody fingerprinted every occurrence — which is exactly what
   this todo DID do for Plant.id, and did not do for PlantNet.
2. **`.secrets.baseline` has no entry for that file**, so detect-secrets never
   looked at it. The baseline is hand-maintained, not a scan.
3. **The incident was marked `✅ RESOLVED (Verified 2025-10-27)`** while the key
   was live, which is the defect this todo was filed about, recurring on the
   other half of the same incident.

**Rotated 2026-09-13.** New key verified working against PlantNet BEFORE the
swap (HTTP 200), then set on Railway `plant_id_community` and `backend/.env`;
`forum-prune-cron` has no PlantNet variable. The exposed literal now returns
**HTTP 401 "Bad token"** — verified, not assumed, because this incident is a
case study in the difference.

**A sequencing hazard worth its own rule:** creating a key at my.plantnet.org
*destroys the previous one*. So the replacement existed, and production's key
was dead, before the swap was staged — PlantNet was down in that gap. For a
vendor that auto-revokes, stage the new value everywhere first, then generate,
then swap immediately. For a vendor that does not (Plant.id), verify the
replacement is usable before swapping. Both hazards bit in the same session.

**The full sweep, so this is not re-derived.** Every tracked file was scanned
for credential-shaped values. Apart from the PlantNet key, nothing live was
exposed: five documented `JWT_SECRET_KEY` values are 40-45 chars against a live
86; two `FIELD_ENCRYPTION_KEY` values match neither local nor prod (and todo 367
established that variable is never read); the `backend/Dockerfile` JWT value is
a documented build-time throwaway; the short `PLANT_ID_API_KEY` strings are
20-21 chars against a real 50.
