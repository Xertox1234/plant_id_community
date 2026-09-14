---
status: in_progress
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

- [x] Settings refuse to boot (`not DEBUG`) with ANY verbatim `REQUIRED__` value,
      `JWT_SECRET_KEY` included — demonstrated by a failing-then-passing test.
- [x] The test enumerates `.env.example` rather than hardcoding key names.
- [x] `FIELD_ENCRYPTION_KEY` is either wired up or removed along with
      `django-encrypted-model-fields`.
- [x] `backend/docs/patterns/security/secret-management.md`'s enforcement table
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

### 2026-09-13 - Enforced (PR pending review)

`reject_insecure_value(name, value)` in `settings.py` raises
`ImproperlyConfigured` for a value starting with `REQUIRED_PLACEHOLDER_PREFIX`
(`"REQUIRED__"`), or containing any `INSECURE_PATTERNS` substring. The prefix is
reported separately, because its remedy differs: "you copied `.env.example` and
did not fill this in" is a different mistake from "you chose a weak value".

Applied at three sites, per Recommended Action 1 and 2 -- one helper rather than
a loop copied per key, since the copied loop is exactly why `JWT_SECRET_KEY` had
no check at all:

- `SECRET_KEY`, replacing the inline loop (production branch)
- `JWT_SECRET_KEY`, guarded on `not DEBUG` to match, and placed **before**
  `SIMPLE_JWT["SIGNING_KEY"]` is assigned
- both API keys, as a prefix branch **ahead of** the length floor in
  `validate_environment()`'s `api_key_checks` loop

`FIELD_ENCRYPTION_KEY`: **removed**, with `django-encrypted-model-fields` from
`requirements.txt`. Re-confirmed unreferenced first --
`grep -rn "encrypted_model_fields|EncryptedCharField|EncryptedTextField|FIELD_ENCRYPTION_KEY"`
over all `.py` returned nothing. An unused crypto dependency is attack surface
and audit noise.

**The test drives itself off `.env.example`**
(`apps/core/tests/test_env_example_placeholders.py`): it parses the file,
parametrises over every `REQUIRED__` line, and boots settings in a **clean
subprocess** per case. A subprocess because "refuses to boot" is an
import-time property -- re-importing settings in-process returns the cached
module and proves nothing, and the checks are gated on `not DEBUG` while the
suite runs otherwise.

Three anti-false-green guards in the test itself: a `test_env_example_still_has_placeholders`
floor so the parametrisation cannot silently collapse to zero cases; a
`test_the_baseline_environment_boots` **control**, without which a baseline
broken for an unrelated reason makes every rejection pass for the wrong cause;
and an assertion that the failure message actually **names the key**, since an
operator who cannot tell which value is wrong is not helped.

**Failing-then-passing, demonstrated by mutation.** With the JWT and API-key
guards disabled:

```
FAILED …[PLANT_ID_API_KEY-REQUIRED__GET_FROM__https://we]
FAILED …[PLANTNET_API_KEY-REQUIRED__GET_FROM__https://my]
FAILED …[JWT_SECRET_KEY-REQUIRED__GENERATE_WITH__pytho]
3 failed, 4 passed
```

Exactly the three predicted -- and `SECRET_KEY` still passed while mutated,
which **confirms the todo's claim that its guard is a coincidence.** Proven
directly as well: running the old `INSECURE_PATTERNS`-only logic against a
reworded hint of identical meaning
(`REQUIRED__GENERATE_WITH__django_core_management_utils_make_random_signing_value`)
returns `False` -- the only thing catching `SECRET_KEY` was the word "secret"
in the hint text.

`settings.py` was restored from a copy and the restoration verified by grep
(0 `MUTATED` markers, both guards present), not assumed.

Also worth recording: **a length floor is not a placeholder check.** Both API
placeholders are *longer* than their minimums (41 and 44 against 32 and 20), and
the JWT placeholder's 66 characters cleared all three of that key's own checks.

Verification:

| Check | Result |
| --- | --- |
| `pytest test_env_example_placeholders.py` | **7 passed** |
| same, with the guards mutated off | **3 failed, 4 passed** (the predicted three) |
| `pytest apps/core apps/users` | **364 passed** |
| baseline production env boots | yes (the control) |
| `FIELD_ENCRYPTION_KEY` / `django-encrypted-model-fields` remaining | **0 / 0** |

`backend/docs/patterns/security/secret-management.md`'s enforcement section is
rewritten from "NONE, and the one case that IS caught is caught by accident" to
the enforced table, naming the mechanism per key, and keeping both lessons (the
accidental guard; the wrong-property validation) rather than deleting the
history.

### 2026-09-13 - CI caught the control; test hardened

The first CI run **failed on `test_the_baseline_environment_boots`** — the very
control the test carries. It passed locally and failed in CI because the local
baseline booted only with help this test should never have depended on:

- `validate_environment()` requires `CSRF_TRUSTED_ORIGINS` and
  `CORS_ALLOWED_ORIGINS` in production, and the developer `.env` supplied both
  (`python-decouple` consults `os.environ` first, then falls back to `.env` —
  so a "clean" subprocess environment was still not clean);
- it also **pings Redis**, which CI's pytest job has and a developer machine may
  not.

Asserting `returncode == 0` therefore asserted "this machine has a dev `.env`
and a running Redis", not "the baseline is a valid production config".

Fixed by asserting on **what the message says**, not on the exit code:

- `PLACEHOLDER_MARKERS` names the wording `reject_insecure_value()` and the
  `api_key_checks` loop use for a placeholder specifically.
- The control now asserts the baseline produces **no placeholder complaint**.
- Each case now asserts it was rejected **as a placeholder**, not merely
  rejected — without that, a missing Redis would make all four pass while
  proving nothing.

The two missing env vars were added to `BASELINE` as well, so the baseline is a
genuinely valid production config rather than one propped up by `.env`.

Proven environment-independent by pointing `REDIS_URL` at a dead port:

```
baseline boots?           False
baseline mentions redis?  True
CONTROL passes:           True
  SECRET_KEY        rejected AS A PLACEHOLDER: True
  PLANT_ID_API_KEY  rejected AS A PLACEHOLDER: True
  PLANTNET_API_KEY  rejected AS A PLACEHOLDER: True
  JWT_SECRET_KEY    rejected AS A PLACEHOLDER: True
```

Mutation re-run after hardening: with the JWT and API-key guards disabled, the
same three cases fail. The assertions got stricter, not looser.

**The lesson is the control's, though.** A test that asserts a whole environment
boots is asserting far more than it means to, and every extra requirement is a
way for it to fail for the wrong reason. Assert the specific behaviour.

### 2026-09-13 - Drive-by: the CI step that generated the removed key

`.github/workflows/backend-ci.yml` had **two** copies of a
"Generate CI-only field encryption key" step writing `FIELD_ENCRYPTION_KEY` into
`$GITHUB_ENV`. Nothing has ever read that variable — it appears in no `.py` and
`encrypted_model_fields` was never in `INSTALLED_APPS` — so the steps were dead
before this todo and unambiguously dead after it. Both removed; YAML and
`actionlint` clean, and `FIELD_ENCRYPTION_KEY` now appears nowhere in the
workflow.

`cryptography` stays in `requirements.txt` — it has other users; only
`django-encrypted-model-fields` went.

## Review round 1

No code defect. Two things resolved.

**The one blocking item was an operator check, and it is now cleared.** This PR
applies the six-substring `INSECURE_PATTERNS` loop to `JWT_SECRET_KEY` for the
first time -- on main it guarded `SECRET_KEY` only. A live value containing any
of those substrings would raise `ImproperlyConfigured` at import on the next
deploy, taking down the web service **and** `forum-prune-cron`, which imports the
same settings and fails silently.

Checked against the live Railway values on both services, testing substrings
locally so no secret was printed or pulled into the session:

| value | web | forum-prune-cron |
| --- | --- | --- |
| SECRET_KEY | 86 ch, clean | 86 ch, clean |
| JWT_SECRET_KEY | 86 ch, clean | 86 ch, clean |
| PLANT_ID_API_KEY | 50 ch, clean | 50 ch, clean |
| PLANTNET_API_KEY | 26 ch, clean | not set |

None matches any of the six patterns; none carries the `REQUIRED__` prefix. The
unset key on the cron service is safe: `reject_insecure_value` returns on a
falsy value, and the API-key check at settings.py:1625 is guarded by
`if key_value and ...`.

On the false-positive concern generally: for machine-generated keys the risk is
negligible, not merely small -- about 3e-9 that a random 50-char Django key
contains "secret". The real exposure was always a hand-chosen operator value,
which is why the live check above was the thing worth doing rather than
more analysis.

**Doc overclaim corrected.** `secret-management.md` said the suite "carries a
baseline-boots control". It does not: the control asserts the absence of a
*placeholder* complaint, which is deliberately weaker, because asserting a clean
exit is exactly what broke this test in CI earlier in this todo. Stating the
stronger property is the same mistake todo 367 already shipped once -- an
enforcement claim written from intent rather than from the code.

### Follow-ups, not fixed here

- ~15 non-`REQUIRED__` placeholders in `.env.example` remain unguarded
  (`DATABASE_URL`, `GITHUB_CLIENT_SECRET` -- whose placeholder literally contains
  "secret" -- `OPENAI_API_KEY`, `EMAIL_HOST_PASSWORD`, ...). Consistent with this
  PR's scope; worth extending the convention.
- `backend/docs/security/PII_ENCRYPTION_IMPLEMENTATION.md` still documents
  `FIELD_ENCRYPTION_KEY` as implemented. This PR removed the dependency and the
  `.env.example` entry, so that doc is now actively misleading.
