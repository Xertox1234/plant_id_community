# Backend — Django / DRF / Wagtail

## Commands

```bash
# Setup
cd backend
source venv/bin/activate

# Development
python manage.py runserver           # http://localhost:8000
python simple_server.py              # runserver + Redis health check

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

# Cache warming (run after deploy to eliminate cold start penalty)
python manage.py warm_moderation_cache
python manage.py warm_moderation_cache --force

# Forum seeding (run after deploy to ensure the forum has a default board)
python manage.py seed_default_forum    # ensure the forum has a default board (idempotent)

# Redis
brew services start redis
redis-cli ping   # should return PONG
```

## Conventions

- **No magic numbers** — all config (timeouts, limits, cache keys, thresholds) in the app's `constants.py`. Every app has one at `apps/<app>/constants.py`. Import from there; never hardcode.
- **Bracketed log prefixes** — use `[CACHE]`, `[PERF]`, `[ERROR]`, `[CIRCUIT]`, `[SECURITY]` so logs are greppable by category.
- **Type hints on all service methods** — `def identify(self, file) -> Optional[Dict[str, Any]]:`. No bare `def`.
- **Escape search wildcards** — before any `icontains` filter, escape `%` and `_`: `query.replace('%', r'\%').replace('_', r'\_')`. See `docs/patterns/security/input-validation.md`.
- **Wagtail admin** — at `/cms/`, not `/admin/`.

## CI

Two GitHub Actions workflows gate PRs:

- **`backend-checks`** — Django system check + OpenAPI schema validation (`manage.py spectacular`). Uses SQLite, no external services.
- **`backend-tests`** — Full pytest suite against **PostgreSQL 16** + **Redis 7** (spun up as GitHub services). Placeholder API keys are injected for length-validation tests; all external HTTP calls are mocked.

Lint (flake8/black/isort) is **pre-commit only**, not enforced in CI (≈3k pre-existing violations make a full-tree gate impractical). Note: pre-commit lints each **whole file** that appears in the staged diff (`files: ^backend/.*\.py$`), not just the changed *lines* — so touching one line in a file with pre-existing violations surfaces all of that file's violations and can block the commit. Either clean the file's violations or bypass with `SKIP=flake8 git commit …` (last resort).

## Gotcha: stale test DB after migration changes

If a test raises `FieldError` after you changed a migration, the test DB predates the change. Fix:

```bash
python manage.py test apps.<app> --noinput   # drops and rebuilds the test DB
```
