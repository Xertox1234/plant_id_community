# Backend — Django / DRF / Wagtail

## Commands

```bash
# Setup
cd backend
source venv/bin/activate

# Development
python manage.py runserver           # http://localhost:8000

# Database
python manage.py migrate
python manage.py makemigrations
python manage.py createsuperuser

# Testing
# --keepdb skips teardown (faster); --noinput forces fresh rebuild after migration changes
python manage.py test apps.plant_identification --keepdb
python manage.py test apps.blog --keepdb
python manage.py test apps.forum --keepdb
python manage.py test apps.garden_calendar --keepdb
python manage.py test apps.users --keepdb

# Optional cache warming — blog AI cache only (the forum moderation cache was
# retired with django-machina, PR #362; there is no forum cache to warm)
python manage.py warm_ai_cache --force

python manage.py seed_default_forum    # ensure the forum has a default board (idempotent)

# Redis
brew services start redis
redis-cli ping   # should return PONG
```

## Conventions

- **No magic numbers** — all config (timeouts, limits, cache keys, thresholds) in the app's `constants.py`. Every app has one at `apps/<app>/constants.py`. Import from there; never hardcode.
- **Bracketed log prefixes** — use `[CACHE]`, `[PERF]`, `[ERROR]`, `[CIRCUIT]`, `[SECURITY]` so logs are greppable by category.
- **Type hints on all service methods** — `def identify(self, file) -> Optional[Dict[str, Any]]:`. No bare `def`.
- **Don't escape search wildcards before `icontains`/`istartswith`/etc.** — Django's ORM already auto-escapes `%`/`_`/`\` for these lookups (`PatternLookup.process_rhs()`); adding `query.replace('%', r'\%').replace('_', r'\_')` on top double-escapes and breaks real matches. Manual escaping is only for lookups that bypass the ORM's pattern-lookup machinery (raw SQL, `.extra()`). See `docs/patterns/security/input-validation.md`.
- **Wagtail admin** — at `/cms/`, not `/admin/`.

## CI

Two GitHub Actions workflows gate PRs:

- **`backend-checks`** — Django system check, OpenAPI schema validation (`manage.py spectacular --validate --fail-on-warn`: any generator warning fails, so a view drf-spectacular cannot read needs an `@extend_schema`), and `mypy apps/users` (django-stubs plugin; one app gated so far, widened one app at a time). Uses SQLite, no external services.
- **`backend-tests`** — Full pytest suite against **PostgreSQL 16** + **Redis 7** (spun up as GitHub services). Placeholder API keys are injected for length-validation tests; all external HTTP calls are mocked.

Lint (flake8/black/isort) is enforced **twice**: the pre-commit hooks on the staged files, and since PR #1158 (2026-10-18) the required `backend-checks` CI job, which runs the same three pre-commit hooks `--all-files` from the repo root (flake8 reads the root `setup.cfg` from the cwd, and its `per-file-ignores` are `backend/`-prefixed — running it from `backend/` drops every suppression). The tracked tree is clean, so a `git commit --no-verify` is caught in CI rather than landing. Note: pre-commit lints each **whole file** that appears in the staged diff (`files: ^backend/.*\.py$`), not just the changed *lines*. Measure with the pins that gate (`pre-commit run flake8 --all-files`), not the venv's flake8, which is a newer version and disagrees. Never widen `setup.cfg`'s `per-file-ignores`; wrap long prose/prompt strings with implicit concatenation or a backslash continuation and prove the value unchanged (`docs/LEARNINGS.md` 2026-10-18).

## Gotcha: the RemovedInDjango70Warning gate lives in pytest.ini

`backend/pytest.ini` turns `RemovedInDjango70Warning` into an error (todo 364),
and CI runs pytest. `python manage.py test` does NOT read `pytest.ini`, so a
first-party deprecation only warns there: run `pytest` before pushing mail,
ORM or settings changes. There are no third-party exemptions: the django-taggit
and Wagtail admin mail call sites are shimmed in `apps/core/django70_compat.py`
(todo 452), and `apps/core/tests/test_django70_compat.py` fails once an upgrade
makes a shim unnecessary or moves past its version ceiling.

## Gotcha: stale test DB after migration changes

If a test raises `FieldError` after you changed a migration, the test DB predates the change. Fix:

```bash
python manage.py test apps.<app> --noinput   # drops and rebuilds the test DB
```
