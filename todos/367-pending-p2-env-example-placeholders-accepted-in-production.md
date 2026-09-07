---
status: pending
priority: p2
issue_id: "367"
tags: [security, configuration, settings, prevention]
dependencies: []
---

# Four of five `.env.example` placeholders boot clean in production

## Problem

`backend/.env.example` marks every must-replace value with a
`REQUIRED__GENERATE_WITH__<cmd>` / `REQUIRED__GET_FROM__<url>` placeholder. The
convention is good and is now documented in
`backend/docs/patterns/security/secret-management.md`. **Nothing enforces it** —
`REQUIRED__` appears in `.env.example`, that pattern doc, and two archived todos,
and in no validator.

Measured 2026-09-07 against `backend/plant_community_backend/settings.py`:

| Placeholder | Verbatim in production | Why |
|---|---|---|
| `SECRET_KEY` | **rejected at boot** | coincidence — `INSECURE_PATTERNS` (`:84`) contains the matching word, and this key's generation *hint text* happens to include it |
| `JWT_SECRET_KEY` | **accepted, and signs every JWT** | `INSECURE_PATTERNS` is applied to `SECRET_KEY` alone (`:94`). JWT's own checks are set / `!= SECRET_KEY` / `len >= 50`; the 66-char placeholder clears all three and lands in `SIMPLE_JWT["SIGNING_KEY"]` (`:731`) |
| `FIELD_ENCRYPTION_KEY` | **accepted, never read** | no `.py` references it; `encrypted_model_fields` is not in `INSTALLED_APPS` |
| `PLANT_ID_API_KEY` | accepted | `validate_environment()` floor is 32; placeholder is 41 |
| `PLANTNET_API_KEY` | accepted | floor is 20; placeholder is 44 |

## Findings

- **The `JWT_SECRET_KEY` case is the one with teeth.** An operator deploying from
  `.env.example` hits the `SECRET_KEY` `ImproperlyConfigured` — which helpfully
  prints the generate command — fixes that one line, and boots clean. Every JWT
  is then signed with a value published in a committed file on a **public**
  repo. Anyone who reads the repo can forge tokens. Nothing catches it.
- The `SECRET_KEY` case looks like enforcement and is not. It survives only
  because someone wrote "get_random_secret_key" in the hint text. Reword that
  hint and the last remaining guard disappears silently.
- `FIELD_ENCRYPTION_KEY` is inert: `django-encrypted-model-fields==0.6.5`
  (`requirements.txt:47`) is an unused dependency carrying an unused setting.
  Either wire it up or drop both — an unused crypto dependency is attack surface
  and audit noise.

## Recommended Action

1. Add `"required__"` to `INSECURE_PATTERNS` **and apply that loop to
   `JWT_SECRET_KEY` as well** — adding the pattern alone only re-hardens the key
   that is already caught. Prefer extracting a small
   `reject_insecure_value(name, value)` helper over copying the loop.
2. Extend the check to the API keys, or add a `REQUIRED__` prefix test to
   `validate_environment()` so the rule is one assertion rather than per-key.
3. Decide `FIELD_ENCRYPTION_KEY`: wire up `encrypted_model_fields`, or remove the
   setting from `.env.example` and drop `django-encrypted-model-fields` from
   `requirements.txt`.
4. Add a test that boots settings with each `.env.example` value verbatim and
   asserts every one is rejected. **Drive it from `.env.example` itself**, so a
   newly added placeholder is covered without anyone remembering to add a case.

## Acceptance Criteria

- [ ] Settings refuse to boot (`not DEBUG`) with ANY verbatim `REQUIRED__` value,
      `JWT_SECRET_KEY` included — demonstrated by a failing-then-passing test.
- [ ] The test enumerates `.env.example` rather than hardcoding key names.
- [ ] `FIELD_ENCRYPTION_KEY` is either wired up or removed along with
      `django-encrypted-model-fields`.
- [ ] `backend/docs/patterns/security/secret-management.md`'s enforcement table
      is updated to say the convention is enforced, with the mechanism named.

## Technical Details

- `backend/plant_community_backend/settings.py` — `INSECURE_PATTERNS` `:84-98`,
  JWT block `:655-731`, `validate_environment()` API-key floors `:1520-1535`.
- `backend/.env.example` — the five placeholders.

## Work Log

### 2026-09-07 - Filed from PR #701 code review

Found while rescuing the `REQUIRED__*` pattern out of the archived
`CODE_AUDIT_PATTERNS_CODIFIED.md`. The stale doc claimed a "Validation Pattern"
at a settings path that does not exist; checking what actually enforced it turned
up that almost nothing does. Two rows of my first corrected table were themselves
wrong (`JWT_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`) and were caught by the round-1
review — see `docs/LEARNINGS.md` 2026-09-07.

## Notes

p2 not p1: exploiting it requires an operator to actually deploy `.env.example`
values, which has not happened — prod runs real keys. But the repo is public, the
failure is silent, and the one guard that exists is an accident of wording.
