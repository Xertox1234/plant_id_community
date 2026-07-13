# Security — binding rules

Compact checklist auto-injected before edits. Long-form: `backend/docs/patterns/security/`.

- **ViewSet `get_permissions()` MUST call `super().get_permissions()`** for custom
  `@action` endpoints. Overriding without `super()` silently drops action-level
  `permission_classes` — a real auth hole. See `architecture/viewsets.md`.
- **Never f-string table/column names into raw SQL** (migrations included). Use
  `psycopg2.sql.Identifier()` plus an explicit whitelist of allowed names.
- **Escape SQL `LIKE` wildcards** (`%`, `_`, `\`) in user-supplied search terms
  before passing to `__icontains`/`__contains` queries.
- **File uploads: all 4 validation layers** — extension, MIME type, size, and a
  PIL/Pillow decode check. Never trust the client-sent content type alone.
- **No secrets in code, logs, or commits.** API keys and `SECRET_KEY` come from
  `.env`. `SECRET_KEY` must be ≥50 chars and must not contain `django-insecure`.
- **Sanitize all rendered HTML** with DOMPurify (web) before injecting; never
  `dangerouslySetInnerHTML` with unsanitized content.
- **Auth-sensitive code is never delegated** to the cheap worker — review by hand.
- Redact PII (emails, tokens) from logs; GDPR redaction applies to Firebase auth.
- **Never create user accounts in migrations or any other deploy-time path.**
  Blog migration 0004 auto-created superuser `plant_care_admin` with a hardcoded
  password on every `migrate` until 2026-06-10. Dev/demo/E2E seed commands must
  refuse to run in production (`if not settings.DEBUG: raise CommandError(...)`),
  and byline-only accounts get `set_unusable_password()` — never a literal password.
- **Try a bump before suppressing a vuln.** pip-audit's empty "Fix Versions"
  column does NOT mean unfixable — the advisory's affected range may exclude a
  newer release (bleach `GHSA-g75f-g53v-794x` showed no fix at 6.3.0 but was gone
  at 6.4.0). Add an `--ignore-vuln` line (in `.github/workflows/security-scan.yml`)
  only when no bump clears it, with a dated one-line justification. Run
  `npm audit fix` WITHOUT `--force` (`--force` pulls breaking majors).
- **Trust only provider-verified emails.** Never match or create a Django
  account from a provider-supplied email the provider hasn't marked verified;
  fail closed when the verification signal is absent. Each OAuth/federated path
  enforces this with its own local guard (strip / set-if-verified /
  `ImmediateHttpResponse` / 403) — a shared *policy*, not shared code, so do not
  collapse the four guards into one provider-switch helper. When a guard strips
  the email, the downstream user lookup MUST treat a missing email as a hard
  stop. Canonical: `backend/docs/patterns/security/authentication.md` → "Trust
  only provider-verified emails".
- **A shared resource container (collection/bucket/folder) is not an ownership
  check.** Validating that a referenced object lives in the right *container*
  (e.g. an upload collection) closes an existence-guessing IDOR but does not
  stop one user from referencing another user's object BY ID within that same
  container. If the object records an owner/uploader, check it explicitly —
  don't assume container membership implies ownership. Canonical:
  `backend/docs/patterns/domain/forum.md` → "Image blocks are scoped to an
  allowed-uploader set" (audit L21).
- **Gate the drf-spectacular schema/docs endpoints.** `SpectacularAPIView`,
  `SpectacularSwaggerView`, and `SpectacularRedocView` default to
  `SERVE_PERMISSIONS = [AllowAny]`, so the full OpenAPI schema (every path,
  parameter, and the documented auth schemes) plus the interactive Swagger/Redoc
  UIs are anonymous-readable in production. Gate them with
  `SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.IsAdminUser"]`
  — one knob covers all three views (and any future one). `SERVE_INCLUDE_SCHEMA=False`
  does NOT gate them (it only hides the schema's own path). Surfaced in prod (todo 248).
- **Don't trust `claude-code-security-review`'s own `results-file`/`findings-count`
  step outputs.** The action's composite step hardcodes `results-file` to a stale
  relative-path string it never updates, and captures the script's own internal
  severity exit code into a shell variable without ever re-raising it — the job
  always exits success regardless of findings. Read
  `${{ github.workspace }}/claudecode-results.json` directly (unconditionally
  copied there) and parse `.findings[].severity` yourself — the enum is
  `HIGH|MEDIUM|LOW` only, `CRITICAL` is never emitted. See `docs/LEARNINGS.md`
  2026-07-13.
