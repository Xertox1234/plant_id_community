---
status: completed
priority: p4
issue_id: "649"
tags: [email, templates, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Finding 4: replace every hardcoded 'Houseplant-MD' (code defaults, email templates, WAGTAIL_SITE_NAME, forum feed) with 'Houseplant MD', plus a guard test that the old spelling is gone from backend code and templates; fix the other findings (2026-10-12)"
---

# Follow-ups from PR #1108 (todo 639, email text parts, SITE_NAME, blog layout)

## Problem

Todo-sweep run 2026-10-12-1938 merged PR #1108 (todo 639). The non-blocking review findings are below. The curator
merged duplicates and checked each item against main, and the refuter tried to refute what was left; the items that
survived are listed. Owner decision 2026-10-11: follow-ups from this P4 batch are its end state, so this todo is
filed, not swept.

## Findings

PR #1108 (todo sweep run 2026-10-12-1938, group g2, todos 639); follow-ups: verified.

1. **low** `backend/apps/users/email_verification.py:209` The render-failure log includes the raw exception text, and the render context holds verify_url with a signed token. If a template error echoes a context value, the token reaches the logs. Hypothesis, not verified. account_links.py:120 has the same pattern.
2. **low** `backend/apps/users/tests/test_email_presentation.py:237` The verification-subject assert and the blog test's assertNotIn('Houseplant-MD') read settings.SITE_NAME, which config() takes from env. The exact-subject assert passes only while no SITE_NAME env var is set, e.g. a dev .env that still says Houseplant-MD.
3. **low** `backend/apps/core/services/email_service.py:34` _HIDDEN_DIV stops at the first </div>, so a preheader override that nests a div would leave stray text. The comment documents this limit, and base.html's preheader holds no nested div. | also: _HIDDEN_DIV matches the style value with [^"']*, so a style containing the other quote (e.g. font-family:'x'; display:none) is not stripped and the preheader leaks into the text part. The only specimen is base.html's own preheader. | _HIDDEN_DIV stops at the first </div>, so a hidden div that contains a nested div would leak its remainder into the text part. The comment admits this. The new test covers only base.html's flat preheader.
4. **low** `backend/plant_community_backend/settings.py:1198` The brand default was renamed to 'Houseplant MD', but template_service.py (lines 27, 121), apps/core/security.py:290 and forum feeds.py still default to 'Houseplant-MD', so mail from those paths can still carry the old name.
5. **low** `backend/apps/users/tests/test_email_presentation.py:378` The template-error test pins only that a render failure returns False and logs. It does not pin that the Celery task retries on False, which is the stated reason for the change.

7 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: backend/apps/users/email_verification.py:199 The try/except wraps only render_to_string. verification_url(user), built in the context dict above it, still calls settings.SITE_URL.rstrip (line 129), so SITE_URL=None raises AttributeError out of the task raw. The finding-5 guard went to unsubscribe_url and the forum task but not here. (refuted: SITE_URL is always set as config('SITE_URL', default='<https://plantcommunity.com>') in settings.py:1199. decouple's config always returns a str, so a None that would make .rstrip raise cannot happen in a real configuration. An empty value just yields ''.)
- low: backend/apps/forum_host/tasks.py:612 With SITE_URL unset or empty, the batch now sends reply mail whose topic, post and unsubscribe links are relative ('/forum/...'). Those links are dead in a mail client and nothing is logged, so the misconfiguration ships silently instead of failing loudly. | also: An empty SITE_URL now yields relative topic/post URLs in reply emails (href='/forum/...'), which are dead links. The batch no longer fails, but the failure is silent. (refuted: If SITE_URL is unset, the absolute default URL is used. If it is empty in production (DEBUG off), validate_environment adds a critical error and raises ImproperlyConfigured at boot, so it fails loudly. Relative links can only come from an empty SITE_URL in DEBUG/dev.)
- low: backend/apps/users/email_unsubscribe.py:303 With SITE_URL None or empty, unsubscribe_url now returns a relative '/unsubscribe?token=...', which is useless in a mail client. The old code raised; the new code ships a dead link silently. (refuted: unsubscribe_url can only build a relative link from an empty SITE_URL. That cannot ship in production: validate_environment raises ImproperlyConfigured when SITE_URL is empty and DEBUG is off. Unset gives the absolute default. None cannot happen because config returns a str.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1108 review (todo sweep run 2026-10-12-1938)

Filed by the closing step of the run from `state.py followups-md g2`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-2056)

- Finding 1: `backend/apps/users/email_verification.py` and `backend/apps/users/account_links.py` now log only the exception's type on a render failure, never its text; `test_a_template_error_is_a_failed_send_not_a_raise` was changed to feed a fake signed-link string and assert it is absent from the log.
- Finding 2: `test_security_notices_keep_their_meaning` and `BlogPostLayoutTests` pin `SITE_NAME="Houseplant MD"`, so a dev `.env` SITE_NAME can no longer flip them.
- Finding 3: `html_to_text` (`backend/apps/core/services/email_service.py`) matches each quote style separately and strips a hidden div up to its own balanced `</div>`, so a style holding the other quote or a nested div no longer leaks preheader text; two tests cover both.
- Finding 4 (owner decision): every `Houseplant-MD` in backend code and templates (template_service defaults, security alert text, newsletter defaults, forum feed, `WAGTAIL_SITE_NAME`, the `test_email` command, five email templates) is now `Houseplant MD`; `OldBrandSpellingTests` fails if the old spelling returns under `backend/`.
- Finding 5: `test_a_template_error_makes_the_task_retry` runs the verification and sign-in-link Celery tasks with a failing render and asserts `retry` is called.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-2056)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 2 -- venv/bin/python -m pytest apps/core/tests/test_email_links_and_text.py apps/users/tests/test_email_presentation.py apps/users/tests/test_email_verification_hardening.py apps/blog/tests/test_newsletter.py apps/blog/tests/test_newsletter_digest.py --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g8/649-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ============= 172 passed, 3 warnings, 18 subtests passed in 25.59s =============
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-2056)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-12 - Review round 1: findings fixed by hand, the rest declined (owner decision)

Round 1 found nothing blocking. These lows were cheap and in scope, so they were fixed before round 2:

- **An unclosed hidden div emptied the text part** (a regression from finding 3). `_strip_hidden_divs` cut to
  the end of the document when the closing tag was missing, where the old regex removed nothing. An unclosed
  hidden div now loses only its opening tag. New test `test_an_unclosed_hidden_div_keeps_the_body`. With the
  old cut-to-end restored, it fails (mutation check).
- **Finding 1 covered only the two account mails.** `send_email` still logged a render exception's text for
  the `.html` and `.txt` templates, and the newsletter confirmation used `logger.exception`. Those contexts hold
  signed unsubscribe and confirm links. All three now log the exception type only. New test
  `RenderFailureLogTests`. It fails when the `.txt` warning goes back to logging the exception (mutation check).
- **The brand guard walked all of `backend/venv`** and read stale reports (`htmlcov`, `logs`). It now prunes
  skip directories during an `os.walk`, and the skip set adds `htmlcov`, `logs` and `.pytest_cache`.
- Declined: extending the brand guard to `web/src` and the mobile app. The owner decision scoped it to backend
  code and templates, and neither has the old spelling (grep: 0 hits).

Tests: `test_email_links_and_text.py`, `test_email_presentation.py` and `apps/blog/tests` pass: 513 passed,
7 skipped.
