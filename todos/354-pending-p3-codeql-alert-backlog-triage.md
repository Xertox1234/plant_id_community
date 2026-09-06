---
status: pending
priority: p3
issue_id: "354"
tags: [security, codeql, backend, web, ci]
dependencies: []
---

# Triage the 51-alert CodeQL backlog on a public repo

## Problem

GitHub code scanning holds **51 open alerts** on `main`, the oldest from
2025-10-23. Todo 353 triaged exactly one of them (#116). CodeQL is not a
required check, so the backlog has never blocked a merge and has never been
assessed as a whole — but this repository is **public**, so 16 open
`py/clear-text-logging-sensitive-data` alerts are visible to anyone. The
backlog needs a single triage pass that either fixes or dismisses each
cluster, so that "1 new alert" on a PR becomes a signal again instead of
noise on top of 51.

## Findings

Inventory taken 2026-09-05 via
`gh api --paginate "repos/:owner/:repo/code-scanning/alerts?state=open"`.
Full dump kept at the alert numbers below; clusters, not individual alerts,
are the unit of work.

| n | Rule | Severity | Where |
| --- | ------ | ---------- | ------- |
| 16 | `py/clear-text-logging-sensitive-data` | high | 8× `weather_service.py`, 2× `settings.py`, `care_assistant_service.py`, `ratelimit.py:143`, plus 4 in dev/test scripts |
| 12 | `py/stack-trace-exposure` | medium | 5× `blog/api_views.py`, 2× `plant_identification/urls.py`, 2× `simple_views.py`, `simple_urls.py`, `file_validation.py`, `wagtail_forum/api/serializers.py:1471` |
| 8 | `py/url-redirection` | medium | all 8 in `apps/users/oauth_views.py` (lines 129–189) |
| 8 | `actions/missing-workflow-permissions` | medium | `mobile-ci.yml` ×3, `backend-ci.yml` ×2, `web-ci.yml`, `harness-ci.yml`, `kimi-review.yml` |
| 3 | `js/incomplete-multi-character-sanitization` | high | `SearchPage.tsx:19`, `ThreadDetailPage.tsx:66`, `NewThreadPage.tsx:33` |
| 1 | `js/xss-through-dom` (#122) | high | `TipTapEditor.tsx:438` |
| 3 | test-only | mixed | `py/bad-tag-filter` #87, `py/incomplete-url-substring-sanitization` #115, `js/clear-text-cookie` #82 |

Two clusters were read during triage and are **already understood** — record
the reasoning rather than re-deriving it:

- **`py/url-redirection` ×8 — false positive, settled by the route
  definition.** Every flagged redirect builds its target as
  `f"{frontend_base}/auth/{provider}/callback"`. Two facts close it:
  `frontend_base` is `settings.FRONTEND_BASE_URL` (`oauth_views.py:23-29`),
  so the **host** is not attacker-controlled; and the route is
  `oauth/<str:provider>/...` (`apps/users/urls.py:25,27`;
  `plant_community_backend/urls.py:148`), and Django's `str` converter
  matches any non-empty string **except `/`** — so the **path prefix**
  cannot be escaped upward either. It is not an open redirect.
  What remains is same-origin noise: `provider` can still carry `?` or `#`,
  so a crafted value shifts the query/fragment of a URL on our own frontend
  (`.../auth/x?a=b/callback?error=no_code`). The handler only supports
  `google`/`github` but emits several redirects containing the raw
  `provider` **before** reaching the `unsupported_provider` branch.
  Validating `provider` against an allowlist at the top of the view closes
  all 8 alerts and is tidier regardless — but it is hygiene, not a
  vulnerability fix, and should not be priced as one.
- **`js/incomplete-multi-character-sanitization` ×3 — false positive.** All
  three are the same `html.replace(/<[^>]*>/g, '')` idiom, and none is a
  sanitizer. `SearchPage.stripTags` feeds `highlightText`, whose output is
  rendered as JSX text children (`SearchPage.tsx:387-430`), and the file
  already carries the comment "Strip tags so we render plain text only —
  never dangerouslySetInnerHTML". The other two are `isBlankHtml`, an
  emptiness check for a rich-text body. Worth noting separately: `isBlankHtml`
  is duplicated **verbatim** in `ThreadDetailPage.tsx` and `NewThreadPage.tsx`
  — a real dedup target regardless of the alert.

## Recommended Action

Work cluster by cluster, cheapest and most real first. Do not batch-dismiss.

1. **`actions/missing-workflow-permissions` (8 alerts, 5 files).** The only
   cluster that is a genuine fix with no analysis needed: add a least-privilege
   top-level `permissions:` block (usually `contents: read`) to
   `.github/workflows/{mobile-ci,backend-ci,web-ci,harness-ci,kimi-review}.yml`.
   Check first whether the harness guard blocks `.github/` edits the way it
   blocks `.claude/`; if it does, hand the user the diff to apply.
2. **`py/url-redirection` (8 alerts, 1 file).** Per the finding above this is
   a false positive, so the choice is dismiss-or-tidy, not fix. Preferred:
   add the provider allowlist in `oauth_views.py` with a test that an unknown
   provider never reaches a redirect carrying its raw value — that closes all
   8 by making the taint unreachable. Acceptable alternative: dismiss all 8 as
   false positives citing the `str`-converter reasoning.
3. **`py/stack-trace-exposure` (12 alerts).** Cross-check against the DRF
   error-envelope work from todo 320 — several sites may already be covered by
   the handler and only need the local `str(exc)` removed from the response
   body. Sites in `backend/simple_urls.py` and `simple_views.py` should be
   confirmed as still-reachable code before spending effort.
4. **`py/clear-text-logging-sensitive-data` (16 alerts).** Split live code
   (`weather_service.py`, `settings.py`, `care_assistant_service.py`,
   `ratelimit.py`) from dev/test scripts (`security_tests.py`,
   `test_plantnet_api.py`). Live code: redact or drop the value. Test scripts:
   dismiss as "used in tests" — that is what the dismissal reason exists for.
5. **`js/xss-through-dom` #122 (`TipTapEditor.tsx:438`).** This is the sibling
   of #116, which todo 353 already traced. Reuse that analysis; per 353's
   own lesson, **a suppression comment is not a fix** — code scanning ignores
   `// codeql[...]` and the alert returns under a new number when the
   fingerprint shifts. Break the path structurally or dismiss through the API.
6. **The 3 test-only alerts.** Dismiss as "used in tests" with a one-line
   rationale each.
7. **False positives** get dismissed through the API/UI with a written reason,
   never with an in-source comment:
   `gh api -X PATCH repos/:owner/:repo/code-scanning/alerts/NNN -f state=dismissed -f dismissed_reason=false\ positive -f dismissed_comment="..."`

## Technical Details

- Alert list: `gh api --paginate "repos/:owner/:repo/code-scanning/alerts?state=open&per_page=100"`
- Dismissal reasons accepted by the API: `false positive`, `won't fix`, `used in tests`.
- Related pattern docs: `backend/docs/patterns/security/input-validation.md`,
  `backend/docs/patterns/security/authentication.md` (OAuth),
  `backend/docs/patterns/architecture/rate-limiting.md` (`ratelimit.py:143`).
- Precedent for a single-alert triage writeup: `todos/archive/353-completed-p3-codeql-xss-through-dom-forumbody.md`.

## Acceptance Criteria

- [ ] Every one of the 51 alerts is either fixed on `main` or dismissed with a written reason
- [ ] All 5 workflow files carry an explicit top-level `permissions:` block
- [ ] The 8 `py/url-redirection` alerts are closed — preferably by an allowlist check on `provider` in `oauth_views.py` with a regression test, otherwise dismissed with the `str`-converter rationale
- [ ] No alert is "resolved" by an in-source suppression comment alone (353's lesson)
- [ ] `gh api "repos/:owner/:repo/code-scanning/alerts?state=open"` returns 0 alerts, or the residue is listed here with the reason it stays open

## Work Log

### 2026-09-05 - Filed during a GitHub cleanup pass

- Backlog surfaced while auditing GitHub state after the 338–353 sweep: 0 open
  PRs, 0 stale remote branches, `main` green on all 5 required checks — the
  CodeQL backlog was the only substantive finding.
- Inventoried all 51 alerts and pre-triaged the two largest analysable
  clusters (`py/url-redirection`, `js/incomplete-multi-character-sanitization`)
  so the eventual fix pass does not repeat the reading.
- Dependabot alerts + automated security updates were enabled on the repo in
  the same pass; expect a separate stream of dependency alerts unrelated to
  these 51.

### 2026-09-06 - Triaged in full; four slices shipped, dismissal sweep pending

**The backlog was 43, not 51, before this session started.** Step 1 of the
Recommended Action — `actions/missing-workflow-permissions`, 8 alerts — was
already closed by commit `7db347a` / PR #657 ("least-privilege permissions on
the 5 workflows missing them"), landed as part of todo 355's prevention work.
All five workflow files carry a top-level `permissions:` block, so **AC 2 was
satisfied before this todo was picked up**. That is why the todo read as done.

**The real finding: two credential leaks CodeQL never flagged.** Reading the
16 `py/clear-text-logging-sensitive-data` alerts turned up two live leaks that
are not in the backlog at all:

1. `plant_community_backend/settings.py:1562` logged `REDIS_URL` verbatim.
   On Railway that URL carries a password, and `validate_environment()` runs
   unconditionally at import — so gunicorn *and* the co-located Celery worker
   each wrote it to the log stream on every process start.
2. Both weather services pass the OpenWeather key as `?appid=` and call
   `raise_for_status()`. `requests.HTTPError.__str__` is
   `"401 Client Error: ... for url: <prepared URL>"`, so
   `logger.error(f"...: {e}")` wrote `OPENWEATHER_API_KEY` to the log on any
   401/429/timeout. Four sites, two of them in the *live* service
   (`apps/garden/services/weather_service.py:126,221` — called by
   `smart_reminder_service`).

Both verified on the real code paths, not by reading: a `REDIS_URL` carrying a
password now logs `localhost:6379/1`, and a mocked 401 whose exception text
embeds the key now logs `HTTPError (status=401)` with neither key nor host.

**Lesson: a SAST backlog is not a log audit.** CodeQL flagged 16 logging sites
and missed the only two that leak a credential. Of its 16, none was a
credential: 9 were garden coordinates, 2 were an API key's *length*, 1 was an
int, 1 was a species name, 3 were an int/bool/file-path in dev scripts.

**Two of the todo's own premises were wrong and are corrected here:**

- Step 3 assumed several `py/stack-trace-exposure` sites were "already covered
  by the handler" from todo 320. It covers **1 of 12** (`serializers.py:1471`).
  Five are plain Django `View`/`JsonResponse`, so DRF's `EXCEPTION_HANDLER`
  never runs; three catch-and-return a `Response`, so the exception never
  propagates to it. Also: **none of the 12 was gated on `settings.DEBUG`.**
- The Findings table says 8× `weather_service.py`; the live inventory is **9×**
  (lines 75, 79, 100, 134, 139, 162, 287, 367, 446). All nine are sinks.

**Verification method correction.** The Technical Details' PR-ref query cannot
confirm a fix. GitHub's default-setup PR analysis is **diff-informed**: every
`Analyze` run on these PRs reported `results_count: 0`, and
`?ref=refs/pull/N/head&state=open` returns `[]` for *all* rules — the same
answer whether the pre-existing alerts cleared or not. **Only the post-merge
analysis on `main` confirms closure.**

**Shipped — four slices, all CI-green, none merged yet:**

| PR | Slice | Alerts |
| ---- | ------- | -------- |
| #670 | Redis password + OpenWeather key + coordinate logs + `log_safe_ip` on the ratelimit diagnostic | 9 |
| #671 | `py/stack-trace-exposure` — 11 sites, incl. the 3 anonymous ones | 11 |
| #672 | OAuth `SUPPORTED_PROVIDERS` allowlist, both mounts | 8 |
| #673 | `stripHtml` reuse + `isBlankHtml` dedup + delete `test_plantnet_api.py` | 4 |

Every fix is mutation-checked. Fixes were preferred over dismissals wherever
the taint could be made unreachable, because **`fixed` is durable and
`dismissed` is not** — a dismissal returns under a new number the moment its
fingerprint shifts (todo 353). 32 of 43 close as `fixed`.

**Remaining: 11 dismissals, deliberately last.** They run only after all four
slices merge and `main` re-analyses, because a dismissal applied before a later
slice shifts a file's fingerprints comes straight back:

| Alert(s) | Reason | Rationale |
| --- | --- | --- |
| #64, #65 | false positive | Taint is the `api_key_checks` tuple (`settings.py:1527`); the message at `:1536` interpolates only `key_name`, `len(key_value)`, `min_length`. No key material. |
| #106 | false positive | Flagged expression is `proxy_count`, an int from `getattr(settings, ..., 0)`. (The unmasked client IPs beside it were fixed in #670.) |
| #66 | false positive | Source is the hardcoded `CACHE_KEY_CARE_PLAN` literal (`garden/constants.py:24`); the logged value is a species name + climate zone. |
| #98, #99 | used in tests | `security_tests.py` is a standalone manual script outside `pytest.ini`'s `testpaths`. Values are an int count and file *paths*, never file contents. |
| #122 | false positive | `URL.createObjectURL(file)` blob URL into an `<img src>` — pre-declared benign by todo 353. |
| #123 | false positive | `InvalidPreferences` is a `ValueError` subclass raised only with hand-written literals echoing the client's own input. No stack trace. |
| #87, #115, #82 | used in tests | A template-scanning regex, an `assert b"a.com" in ...`, and a fake `document.cookie` string. |

**Also found, not in the backlog:** `.secrets.baseline` churns on any commit
that shifts a line in `settings.py`; two files (`ForumSkeleton.tsx`,
`types/diagnosis.ts`) were already prettier-dirty on `main` and block every web
commit; several touched backend files carried pre-existing flake8 debt that
blocks any commit touching them, since pre-commit lints whole files.

### 2026-09-06 - Review round 1, and four more leaks the first pass missed

Independent review of the four code slices (django-drf-reviewer,
react-typescript-reviewer). Every finding below was re-verified here by
executing the path before it was acted on.

**The important one: the fix pass was incomplete.** Slice 1 closed OpenWeather
and Redis. It missed **Trefle and PlantNet, which leak by the same mechanism**
— both authenticate with a QUERY PARAMETER (`token`, `api-key`), so the
prepared URL in `requests`' exception message carries the key:

```text
str(HTTPError) == "401 Client Error: Unauthorized for url:
                   https://trefle.io/api/v1/plants/search?token=<THE KEY>&q=rose"
```

`trefle_service.py:126` sets `token` on `session.params`, so it rides *every*
request. Six sites, closed in #671 — and the worst was
`retry_on_failure`, which logged the exception once per attempt, so a failing
call leaked the key three times. Two of the six were `logger.exception` calls
**this todo's own slice 2 had just added**: moving `str(e)` out of the response
body and into a traceback does not redact it, because the traceback ends with
the same message.

How they were found is the transferable part: not by reading, but by listing
every file the *new JIT trigger* would fire on, then asking of each whether its
key rides the URL or a header. Header-authenticated clients (Plant.id,
plant.health, Unsplash, Pexels) are safe by construction. The count in the
entry above is therefore wrong in the todo's favour: CodeQL raised 16
clear-text-logging alerts and **none** of them was one of the four real leaks.

**A test of mine verified nothing.**
`test_service_status_dicts_carry_no_exception_text` built the service with
`__new__` (so `self.session` never existed) and patched the module's `requests`
attribute (which does not affect `self.session.get`). The exception actually
raised was `AttributeError`, so `assert BOOM not in ...` passed whether or not
the fix was present. Rewritten to force a real `HTTPError` with a keyed URL and
assert the key reaches neither body nor log. Second-order version of the same
defect: the first rewrite used `caplog`, and the `apps.*` loggers are
`propagate=False`, so those assertions would also have passed vacuously — the
test now attaches its own handler.

**Other findings, all fixed:**

- `ratelimit.py` — my comment claimed `log_safe_ip` destroys "the identifying
  low bits". False: it shows two IPv4 octets plus an *unsalted* sha256 prefix,
  so the rest is a 2^16 search. Measured: `203.0.113.42` recovered from the
  masked line in **0.014s**. Comment now says obfuscation, not anonymization.
- `oauth_views.py` — the allowlist was pinned to a *copy* of itself in the
  tests, so adding a provider without a dispatch branch would silently 400 with
  the `else` arms marked `pragma: no cover`. Tests now parametrise over
  `SUPPORTED_PROVIDERS`; mutation adding `facebook` fails 4 tests.
- `oauth_views.py` — the raw `?error=` value was logged verbatim (log forging).
  Conforming RFC 6749 codes pass through; anything else logs as a shape.
- `settings.py` — `urlsplit(...).port` is `None` for a portless `REDIS_URL`, so
  the line read `host:None/1`.
- `forumBody.ts` — the JSDoc claimed numeric whitespace entities were "the ONLY
  behavioural difference, measured". Re-probed across 17 inputs: **five**
  classes diverge (add malformed attributes, `<script>`, `<style>`). Two tests
  differentiated nothing — one asserted a case where both implementations
  agree, the other was `typeof x === 'boolean'`.

**Codified** (#670): `docs/rules/security.md` gains the two rules, and
`triggers.json` 92 -> 94 gains `requests-exception-interpolated` and
`connection-url-in-log`, both proven to fire on the pre-fix source and go quiet
on the post-fix source.

**Dependency PRs settled alongside:** #666/#667 (Dependabot) and #669 delivered
the identical wrangler 4.129.0 tree, but #669's locally-regenerated lockfile had
dropped all 16 `libc` glibc/musl discriminators for sharp. #669 now carries the
bot's lockfile blob verbatim; #666/#667 close as superseded.

**Status unchanged — this stays `pending`.** The 11 dismissals above still run
last, after `main` re-analyses. Widening the AST drift guard from the two
query-string services to the whole service layer is **todo 358**.

### 2026-09-06 - Post-merge census: 43 -> 20, and the allowlist did NOT close its cluster

All four slices are on `main` (#670-#673) and CodeQL has re-analysed
(`/language:python` at `2773877a`, the current tip). Measured, not predicted:

| Rule | Before | After | Closed as `fixed` |
| --- | --- | --- | --- |
| `py/clear-text-logging-sensitive-data` | 16 | 6 | 10 |
| `py/stack-trace-exposure` | 12 | 2 | 10 |
| `js/incomplete-multi-character-sanitization` | 3 | **0** | 3 |
| `py/url-redirection` | 8 | **8** | **0** |
| test-only + `js/xss-through-dom` + `js/clear-text-cookie` | 4 | 4 | 0 |
| **total** | **43** | **20** | **23** |

**The plan's central claim about slice 3 was wrong.** It asserted the OAuth
allowlist would close all 8 `py/url-redirection` alerts "durably, by making the
taint unreachable", and preferred that over dismissal for exactly that reason.
It closed **none**. CodeQL does not model a `frozenset` membership test as a
sanitizer, so `provider` is still tainted where the dispatch builds
`f"{frontend_base}/auth/{provider}/callback"`. The fix is still correct and
still worth having — an unknown provider now cannot reach any redirect — but
"make the taint unreachable to close the alert" only works when the barrier is
one the scanner recognises. A membership test against a literal set is not.

So the dismissal set is **19, not 11**, and the 8 url-redirection alerts move to
the todo's own "acceptable alternative": dismissed as false positive, now with a
stronger rationale than originally available (allowlist *plus* the
`str`-converter reasoning, not just the latter).

Two alerts also came back under **new numbers** after a fingerprint shift,
exactly as todo 353 predicted: `#106 -> #126` (ratelimit.py) and a new `#125`
in the url-redirection cluster. This is why the sweep runs by **rule + file**,
never by remembered alert number.

**The remaining 20, with disposition:**

| Alert(s) | File | Disposition |
| --- | --- | --- |
| #8, #9, #10, #11, #13, #69, #103, #125 | `oauth_views.py` | false positive - allowlisted `provider`; `<str:>` cannot escape the path prefix and the host is `settings.FRONTEND_BASE_URL` |
| #126 | `ratelimit.py:152` | false positive - the flagged value is `proxy_count` (an int); the addresses beside it now go through `log_safe_ip` |
| #64, #65 | `settings.py:1702,1709` | false positive - only `key_name`, `len(key_value)`, `min_length` are interpolated |
| #66 | `care_assistant_service.py:75` | false positive - hardcoded cache-key constant; logged value is species + climate zone |
| #98, #99 | `security_tests.py` | used in tests - standalone manual script outside `pytest.ini` testpaths |
| #115, #87, #82 | test files | used in tests |
| #122 | `TipTapEditor.tsx:438` | false positive - blob URL into `<img src>`, pre-declared benign by todo 353 |
| #123 | `wagtail_forum/api/serializers.py:1471` | false positive - `ValueError` subclass, hand-written literals only |
| **#121** | `simple_views.py:146` | **needs triage** - not a clean dismissal. Slice 2 dropped the PIL text at `file_validation.py:98`, which was supposed to close the `#23`/`#121` pair. It did not. Read the SARIF `codeFlows` before dispositioning it. |

**Dismissals are deliberately NOT applied here.** They are outward-facing
statements on a public repository's security tab, and they are the one step of
this todo that no test can undo. They need an explicit go-ahead, and #121 needs
a real answer first.

## Notes

p3, not p2: the two high-count clusters read as false positives and CodeQL is
not a required check, so nothing here blocks a merge. It is above p4 because
the repository is public and 16 high-severity "clear-text logging" alerts sit
in the open, and because the backlog currently hides any genuinely new alert.
